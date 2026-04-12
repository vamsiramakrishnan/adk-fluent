"""Dedicated tests for ``adk_fluent._compression``.

Covers:

- :class:`CompressionStrategy` constructors and frozen semantics.
- :class:`ContextCompressor` sync and async message rewriting.
- ``pre_compact`` hook integration: allow / deny / replace / modify.
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from adk_fluent import CompressionStrategy, ContextCompressor
from adk_fluent._hooks._decision import HookDecision
from adk_fluent._hooks._events import HookEvent
from adk_fluent._hooks._registry import HookRegistry

# ======================================================================
# CompressionStrategy
# ======================================================================


class TestCompressionStrategy:
    def test_drop_old_constructor(self):
        s = CompressionStrategy.drop_old(keep_turns=7)
        assert s.method == "drop_old"
        assert s.keep_turns == 7

    def test_keep_recent_constructor(self):
        s = CompressionStrategy.keep_recent(n=4)
        assert s.method == "keep_recent"
        assert s.keep_turns == 4

    def test_summarize_constructor(self):
        s = CompressionStrategy.summarize(model="gemini-2.5-flash")
        assert s.method == "summarize"
        assert s.summary_model == "gemini-2.5-flash"

    def test_strategy_is_frozen(self):
        s = CompressionStrategy.keep_recent()
        with pytest.raises(FrozenInstanceError):
            s.method = "drop_old"  # type: ignore[misc]


# ======================================================================
# ContextCompressor — sync
# ======================================================================


def _fake_messages(n: int) -> list[dict]:
    return [{"role": "user", "content": f"msg-{i}"} for i in range(n)]


class TestContextCompressorSync:
    def test_should_compress_threshold(self):
        c = ContextCompressor(threshold=1000)
        assert c.should_compress(1001) is True
        assert c.should_compress(999) is False

    def test_empty_list_passthrough(self):
        c = ContextCompressor(threshold=100)
        assert c.compress_messages([]) == []
        assert c.compression_count == 0

    def test_keep_recent_keeps_last_n_pairs(self):
        c = ContextCompressor(
            threshold=10, strategy=CompressionStrategy.keep_recent(n=2)
        )
        msgs = _fake_messages(20)
        out = c.compress_messages(msgs)
        assert len(out) == 4  # 2 turn-pairs = 4 messages
        assert out[-1] == msgs[-1]

    def test_drop_old_preserves_system(self):
        c = ContextCompressor(
            threshold=10, strategy=CompressionStrategy.drop_old(keep_turns=1)
        )
        msgs = [
            {"role": "system", "content": "sys"},
            *_fake_messages(10),
        ]
        out = c.compress_messages(msgs)
        assert out[0]["role"] == "system"
        assert len(out) == 3  # system + 2 message pair

    def test_compression_count_increments(self):
        c = ContextCompressor(
            threshold=10, strategy=CompressionStrategy.keep_recent(n=1)
        )
        c.compress_messages(_fake_messages(10))
        c.compress_messages(_fake_messages(10))
        assert c.compression_count == 2

    def test_on_compress_callback_fires(self):
        fired: list[int] = []
        c = ContextCompressor(
            threshold=10,
            strategy=CompressionStrategy.keep_recent(n=1),
            on_compress=lambda tokens: fired.append(tokens),
        )
        c.compress_messages(_fake_messages(10))
        assert len(fired) == 1
        assert fired[0] > 0

    def test_estimate_tokens_handles_str_and_parts(self):
        c = ContextCompressor(threshold=1)
        msgs = [
            {"role": "user", "content": "abcd" * 100},
            {"role": "assistant", "content": [{"text": "efgh" * 100}]},
        ]
        assert c.estimate_tokens(msgs) == 200


# ======================================================================
# ContextCompressor — async summariser
# ======================================================================


class TestContextCompressorAsync:
    def test_summarize_path_with_sync_summarizer(self):
        strategy = CompressionStrategy(method="summarize", keep_turns=2)
        c = ContextCompressor(threshold=10, strategy=strategy)
        msgs = [
            {"role": "system", "content": "sys"},
            *_fake_messages(20),
        ]
        out = asyncio.run(
            c.compress_messages_async(msgs, summarizer=lambda text: "SUMMARY")
        )
        assert out[0]["role"] == "system"
        assert "SUMMARY" in out[1]["content"]
        # system + summary + 2*2 retained = 6 messages
        assert len(out) == 6
        assert out[-1] == msgs[-1]

    def test_summarize_without_summarizer_falls_back(self):
        strategy = CompressionStrategy(method="summarize", keep_turns=2)
        c = ContextCompressor(threshold=10, strategy=strategy)
        msgs = _fake_messages(20)
        out = asyncio.run(c.compress_messages_async(msgs, summarizer=None))
        # Falls back to keep_recent(2) → last 4 messages.
        assert len(out) == 4

    def test_summarize_with_async_summarizer(self):
        async def async_summarizer(text: str) -> str:
            return f"ASYNC:{len(text)}"

        c = ContextCompressor(
            threshold=10,
            strategy=CompressionStrategy.summarize(),
        )
        msgs = _fake_messages(30)
        out = asyncio.run(
            c.compress_messages_async(msgs, summarizer=async_summarizer)
        )
        assert any("ASYNC:" in (m.get("content") or "") for m in out)


# ======================================================================
# pre_compact hook integration
# ======================================================================


class TestPreCompactHook:
    def _compressor_with_hooks(self, registry: HookRegistry) -> ContextCompressor:
        return ContextCompressor(
            threshold=10,
            strategy=CompressionStrategy.keep_recent(n=1),
            hook_registry=registry,
        )

    def test_allow_hook_lets_compression_run(self):
        registry = HookRegistry()
        registry.on(HookEvent.PRE_COMPACT, lambda ctx: HookDecision.allow())
        c = self._compressor_with_hooks(registry)
        out = c.compress_messages(_fake_messages(20))
        assert len(out) == 2  # 1 turn-pair = 2 messages
        assert c.compression_count == 1

    def test_deny_hook_cancels_compression(self):
        registry = HookRegistry()
        registry.on(
            HookEvent.PRE_COMPACT,
            lambda ctx: HookDecision.deny(reason="nope"),
        )
        c = self._compressor_with_hooks(registry)
        original = _fake_messages(20)
        out = c.compress_messages(original)
        assert out == original  # unchanged
        assert c.compression_count == 0

    def test_replace_hook_supplies_custom_messages(self):
        custom = [{"role": "user", "content": "REPLACED"}]
        registry = HookRegistry()
        registry.on(
            HookEvent.PRE_COMPACT,
            lambda ctx: HookDecision.replace(output=custom),
        )
        c = self._compressor_with_hooks(registry)
        out = c.compress_messages(_fake_messages(20))
        assert out == custom
        assert c.compression_count == 1

    def test_pre_compact_context_carries_token_count(self):
        captured: list[int] = []

        def capture(ctx):
            captured.append(ctx.extra.get("token_count", -1))
            return HookDecision.allow()

        registry = HookRegistry()
        registry.on(HookEvent.PRE_COMPACT, capture)
        c = self._compressor_with_hooks(registry)
        c.compress_messages(_fake_messages(10))
        assert captured and captured[0] >= 0

    def test_with_hooks_is_pure(self):
        base = ContextCompressor(
            threshold=10, strategy=CompressionStrategy.keep_recent(n=1)
        )
        registry = HookRegistry()
        wired = base.with_hooks(registry)
        assert base.hook_registry is None
        assert wired.hook_registry is registry
        assert wired.threshold == base.threshold


# ======================================================================
# Bridge to BudgetMonitor
# ======================================================================


class TestCompressorBudgetBridge:
    def test_to_monitor_returns_budget_monitor(self):
        from adk_fluent import BudgetMonitor

        c = ContextCompressor(threshold=10_000)
        m = c.to_monitor()
        assert isinstance(m, BudgetMonitor)
        assert m.max_tokens == 10_000

    def test_to_monitor_wires_threshold_at_95_percent(self):
        fired: list[int] = []
        c = ContextCompressor(
            threshold=100,
            on_compress=lambda t: fired.append(t),
        )
        monitor = c.to_monitor()
        monitor.record_usage(95, 0)
        assert len(fired) == 1
