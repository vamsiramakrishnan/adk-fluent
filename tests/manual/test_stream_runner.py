"""Tests for StreamRunner -- builder mechanics only (no API keys needed)."""

import pytest

from adk_fluent._enums import SessionStrategy
from adk_fluent.agent import Agent
from adk_fluent.stream import StreamRunner, StreamStats

# ======================================================================
# StreamStats
# ======================================================================


class TestStreamStats:
    def test_stream_stats_defaults(self):
        stats = StreamStats()
        assert stats.processed == 0
        assert stats.errors == 0
        assert stats.in_flight == 0

    def test_stream_stats_elapsed(self):
        stats = StreamStats()
        assert stats.elapsed >= 0

    def test_stream_stats_throughput_zero(self):
        stats = StreamStats()
        assert stats.throughput == 0.0


# ======================================================================
# StreamRunner fluent API
# ======================================================================


class TestStreamRunnerFluent:
    def test_stream_runner_fluent_chain(self):
        """All setter methods return self for chaining."""
        builder = Agent("test").model("gemini-2.5-flash")

        async def dummy_source():
            yield "x"

        runner = StreamRunner(builder)
        result = runner.source(dummy_source())
        assert result is runner

        result = runner.concurrency(5)
        assert result is runner

        result = runner.on_result(lambda item, res: None)
        assert result is runner

        result = runner.on_error(lambda item, exc: None)
        assert result is runner

        result = runner.graceful_shutdown(60)
        assert result is runner

    def test_stream_runner_session_strategy_string(self):
        builder = Agent("test").model("gemini-2.5-flash")
        runner = StreamRunner(builder)
        result = runner.session_strategy("shared")
        assert result is runner
        assert runner._session_strategy == "shared"

    def test_stream_runner_session_strategy_enum(self):
        """Accepts SessionStrategy enum."""
        builder = Agent("test").model("gemini-2.5-flash")
        runner = StreamRunner(builder)
        result = runner.session_strategy(SessionStrategy.SHARED)
        assert result is runner
        assert runner._session_strategy == "shared"

    def test_stream_runner_max_tasks(self):
        builder = Agent("test").model("gemini-2.5-flash")
        runner = StreamRunner(builder)
        result = runner.max_tasks(100)
        assert result is runner
        assert runner._task_budget == 100

    def test_stream_runner_task_budget_deprecated(self):
        """task_budget() is a deprecated alias for max_tasks()."""
        builder = Agent("test").model("gemini-2.5-flash")
        runner = StreamRunner(builder)
        result = runner.task_budget(42)
        assert result is runner
        assert runner._task_budget == 42

    def test_stream_runner_middleware(self):
        builder = Agent("test").model("gemini-2.5-flash")
        runner = StreamRunner(builder)

        class DummyMW:
            pass

        mw = DummyMW()
        result = runner.middleware(mw)
        assert result is runner
        assert mw in runner._middlewares

    def test_stream_runner_graceful_shutdown(self):
        builder = Agent("test").model("gemini-2.5-flash")
        runner = StreamRunner(builder)
        runner.graceful_shutdown(120)
        assert runner._shutdown_timeout == 120

    @pytest.mark.asyncio
    async def test_stream_runner_requires_source(self):
        """start() raises ValueError without source."""
        builder = Agent("test").model("gemini-2.5-flash")
        runner = StreamRunner(builder)
        with pytest.raises(ValueError, match="No source configured"):
            await runner.start()
