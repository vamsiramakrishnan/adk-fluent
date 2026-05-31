"""Tests for FEATURE #7: real OpenTelemetry spans/metrics from M.trace()/M.metrics().

When ``opentelemetry`` is installed, ``M.trace()`` emits spans at the agent and
model boundaries and ``M.metrics()`` records counters/histograms. When it is not
installed, both are graceful no-ops that emit a one-time install warning.

These tests exercise the middleware hooks directly with the exact argument shapes
the ``_MiddlewarePlugin`` dispatch uses (``before_agent(ctx, agent_name)``,
``after_model(ctx, response)``, etc.), so they validate the real runtime path
without spinning up a full LLM runner. Where end-to-end coverage matters, the LLM
is mocked via ``.mock([...])``.
"""

from __future__ import annotations

import importlib.util
from types import SimpleNamespace

import pytest

from adk_fluent import M
from adk_fluent._middleware import MComposite
from adk_fluent.middleware import (
    MetricsMiddleware,
    TraceContext,
    TraceMiddleware,
)

_HAS_OTEL = importlib.util.find_spec("opentelemetry") is not None
_OTEL_REASON = "opentelemetry not installed (pip install adk-fluent[observability])"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_ctx(agent_name: str = "writer") -> TraceContext:
    """A TraceContext whose invocation_context exposes ``.agent.name``."""
    inv = SimpleNamespace(agent=SimpleNamespace(name=agent_name))
    return TraceContext(invocation_context=inv)


def _fake_request(model: str = "gemini-2.5-flash") -> SimpleNamespace:
    return SimpleNamespace(model=model)


def _fake_response(input_tokens: int = 11, output_tokens: int = 7) -> SimpleNamespace:
    usage = SimpleNamespace(
        prompt_token_count=input_tokens,
        candidates_token_count=output_tokens,
    )
    return SimpleNamespace(usage_metadata=usage)


# ---------------------------------------------------------------------------
# Composite plumbing (works regardless of otel availability)
# ---------------------------------------------------------------------------


class TestComposites:
    def test_trace_creates_composite(self):
        mc = M.trace()
        assert isinstance(mc, MComposite)
        assert len(mc) == 1
        assert isinstance(mc.to_stack()[0], TraceMiddleware)

    def test_metrics_creates_composite(self):
        mc = M.metrics()
        assert isinstance(mc, MComposite)
        assert len(mc) == 1
        assert isinstance(mc.to_stack()[0], MetricsMiddleware)

    def test_construction_never_requires_otel(self):
        # Constructing the middleware must never raise even with otel absent.
        TraceMiddleware()
        MetricsMiddleware()


# ---------------------------------------------------------------------------
# No-op + one-time warning path (when otel is NOT installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_HAS_OTEL, reason="otel installed — no-op path not exercised")
class TestNoOpWhenOtelMissing:
    def test_trace_noop_emits_warning_once(self, recwarn):
        import adk_fluent.middleware as mw

        mw._OTEL_WARNED = False  # reset latch for the assertion
        tm = TraceMiddleware()
        assert tm._tracer is None
        # A warning explaining how to enable observability was emitted once.
        msgs = [str(w.message) for w in recwarn.list]
        assert any("adk-fluent[observability]" in m for m in msgs)

        # Second construction must NOT emit the warning again (one-time latch).
        recwarn.clear()
        MetricsMiddleware()
        assert not any("adk-fluent[observability]" in str(w.message) for w in recwarn.list)

    @pytest.mark.asyncio
    async def test_trace_hooks_are_safe_noops(self):
        tm = TraceMiddleware()
        ctx = _fake_ctx()
        # None of these should raise even though no tracer exists.
        assert await tm.before_agent(ctx, "writer") is None
        assert await tm.before_model(ctx, _fake_request()) is None
        assert await tm.after_model(ctx, _fake_response()) is None
        assert await tm.after_agent(ctx, "writer") is None

    @pytest.mark.asyncio
    async def test_metrics_hooks_are_safe_noops(self):
        mm = MetricsMiddleware()
        ctx = _fake_ctx()
        assert await mm.before_agent(ctx, "writer") is None
        assert await mm.after_model(ctx, _fake_response()) is None
        assert await mm.after_agent(ctx, "writer") is None
        # Internal fallback counter still works without otel.
        assert mm._counts["writer"] == 1

    @pytest.mark.asyncio
    async def test_legacy_collector_still_honoured(self):
        class Collector:
            def __init__(self):
                self.calls: dict[str, int] = {}

            def increment(self, name: str):
                self.calls[name] = self.calls.get(name, 0) + 1

        collector = Collector()
        mm = MetricsMiddleware(collector=collector)
        ctx = _fake_ctx()
        await mm.after_agent(ctx, "writer")
        await mm.on_model_error(ctx, _fake_request(), RuntimeError("boom"))
        assert collector.calls["agent.writer.calls"] == 1
        assert collector.calls["agent.writer.errors"] == 1


# ---------------------------------------------------------------------------
# Real span/metric emission (when otel IS installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_OTEL, reason=_OTEL_REASON)
class TestRealSpansWhenOtelInstalled:
    def _tracer(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        return provider.get_tracer("adk-fluent-test"), exporter

    @pytest.mark.asyncio
    async def test_agent_and_model_spans_emitted(self):
        tracer, exporter = self._tracer()
        tm = TraceMiddleware(tracer=tracer)
        ctx = _fake_ctx("writer")

        await tm.before_agent(ctx, "writer")
        await tm.before_model(ctx, _fake_request("gemini-2.5-flash"))
        await tm.after_model(ctx, _fake_response(input_tokens=11, output_tokens=7))
        await tm.after_agent(ctx, "writer")

        spans = exporter.get_finished_spans()
        names = {s.name for s in spans}
        assert "agent:writer" in names
        assert "model:writer" in names

        agent_span = next(s for s in spans if s.name == "agent:writer")
        assert agent_span.attributes["adk.agent.name"] == "writer"
        assert "adk.agent.latency_ms" in agent_span.attributes

        model_span = next(s for s in spans if s.name == "model:writer")
        assert model_span.attributes["adk.model.name"] == "gemini-2.5-flash"
        assert model_span.attributes["adk.model.input_tokens"] == 11
        assert model_span.attributes["adk.model.output_tokens"] == 7
        assert "adk.model.latency_ms" in model_span.attributes

    @pytest.mark.asyncio
    async def test_model_error_records_exception_on_span(self):
        from opentelemetry.trace import StatusCode

        tracer, exporter = self._tracer()
        tm = TraceMiddleware(tracer=tracer)
        ctx = _fake_ctx("writer")

        await tm.before_model(ctx, _fake_request())
        await tm.on_model_error(ctx, _fake_request(), ValueError("kaboom"))

        spans = exporter.get_finished_spans()
        model_span = next(s for s in spans if s.name == "model:writer")
        assert model_span.status.status_code == StatusCode.ERROR
        assert any(e.name == "exception" for e in model_span.events)


@pytest.mark.skipif(not _HAS_OTEL, reason=_OTEL_REASON)
class TestRealMetricsWhenOtelInstalled:
    def _meter_reader(self):
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader

        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        return provider.get_meter("adk-fluent-test"), reader

    @staticmethod
    def _all_metrics(reader):
        data = reader.get_metrics_data()
        out = {}
        for rm in data.resource_metrics:
            for sm in rm.scope_metrics:
                for metric in sm.metrics:
                    out[metric.name] = metric
        return out

    @pytest.mark.asyncio
    async def test_counters_and_histograms_recorded(self):
        meter, reader = self._meter_reader()
        mm = MetricsMiddleware(meter=meter)
        ctx = _fake_ctx("writer")

        await mm.before_agent(ctx, "writer")
        await mm.after_model(ctx, _fake_response(input_tokens=11, output_tokens=7))
        await mm.after_agent(ctx, "writer")

        metrics = self._all_metrics(reader)
        assert "adk.agent.calls" in metrics
        assert "adk.agent.latency" in metrics
        assert "adk.model.input_tokens" in metrics
        assert "adk.model.output_tokens" in metrics

        # Counter values sum the recorded data points.
        in_points = list(metrics["adk.model.input_tokens"].data.data_points)
        assert sum(p.value for p in in_points) == 11
        out_points = list(metrics["adk.model.output_tokens"].data.data_points)
        assert sum(p.value for p in out_points) == 7
        call_points = list(metrics["adk.agent.calls"].data.data_points)
        assert sum(p.value for p in call_points) == 1

    @pytest.mark.asyncio
    async def test_error_counter_recorded(self):
        meter, reader = self._meter_reader()
        mm = MetricsMiddleware(meter=meter)
        ctx = _fake_ctx("writer")

        await mm.on_model_error(ctx, _fake_request(), RuntimeError("boom"))

        metrics = self._all_metrics(reader)
        assert "adk.agent.errors" in metrics
        err_points = list(metrics["adk.agent.errors"].data.data_points)
        assert sum(p.value for p in err_points) == 1
