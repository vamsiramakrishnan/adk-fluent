"""Tests for Phase E: effectful tool memoization (T.effectful + EffectCache)."""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import EffectCache, EventBus, T
from adk_fluent._harness._event_bus import use_bus
from adk_fluent._session._effect_cache import use_cache


def _make_counter_tool() -> tuple[object, list[int]]:
    """Return (tool, calls) — tool returns len(calls) on each invocation."""
    calls: list[int] = []

    class _Tool:
        name = "counter"
        description = "counts invocations"

        async def run_async(self, *, args: dict, tool_context: object = None) -> int:
            calls.append(1)
            return sum(calls) + args.get("bump", 0)

    return _Tool(), calls


def test_effectful_cache_hit_skips_inner_tool() -> None:
    tool, calls = _make_counter_tool()
    composite = T.effectful(tool, key="k")
    wrapper = composite._items[0]

    cache = EffectCache()

    async def _run() -> tuple[object, object]:
        with use_cache(cache):
            first = await wrapper.run_async(args={"bump": 0}, tool_context=None)
            second = await wrapper.run_async(args={"bump": 0}, tool_context=None)
        return first, second

    first, second = asyncio.run(_run())

    assert first == second
    assert len(calls) == 1  # second call hit cache, inner tool only fired once
    assert cache.size == 1


def test_effectful_without_cache_passes_through() -> None:
    tool, calls = _make_counter_tool()
    composite = T.effectful(tool, key="k")
    wrapper = composite._items[0]

    async def _run() -> None:
        await wrapper.run_async(args={}, tool_context=None)
        await wrapper.run_async(args={}, tool_context=None)

    asyncio.run(_run())
    # No cache active — both invocations hit the inner tool.
    assert len(calls) == 2


def test_effectful_emits_effect_recorded_events() -> None:
    tool, _calls = _make_counter_tool()
    composite = T.effectful(tool, key="u:{user}")
    wrapper = composite._items[0]

    bus = EventBus()
    records: list = []
    bus.on("effect_recorded", lambda e: records.append(e))

    cache = EffectCache()

    async def _run() -> None:
        with use_cache(cache), use_bus(bus):
            await wrapper.run_async(args={"user": "alice"}, tool_context=None)
            await wrapper.run_async(args={"user": "alice"}, tool_context=None)
            await wrapper.run_async(args={"user": "bob"}, tool_context=None)

    asyncio.run(_run())

    assert [r.source for r in records] == ["fresh", "cache", "fresh"]
    assert [r.key for r in records] == ["u:alice", "u:alice", "u:bob"]


def test_effectful_key_callable() -> None:
    tool, _ = _make_counter_tool()
    composite = T.effectful(tool, key=lambda args: f"req:{args['id']}")
    wrapper = composite._items[0]

    cache = EffectCache()

    async def _run() -> None:
        with use_cache(cache):
            await wrapper.run_async(args={"id": 1}, tool_context=None)
            await wrapper.run_async(args={"id": 2}, tool_context=None)

    asyncio.run(_run())
    assert cache.size == 2


def test_effect_cache_ttl_expires() -> None:
    cache = EffectCache()
    cache.put("tool", "k", "value", ttl_seconds=0.01)
    assert cache.get("tool", "k") is not None

    import time

    time.sleep(0.02)
    assert cache.get("tool", "k") is None


def test_effect_cache_scope_partitioning() -> None:
    cache = EffectCache()
    cache.put("tool", "k", "a", scope="user:alice")
    cache.put("tool", "k", "b", scope="user:bob")

    assert cache.get("tool", "k", scope="user:alice").value == "a"
    assert cache.get("tool", "k", scope="user:bob").value == "b"

    cache.clear_scope("user:alice")
    assert cache.get("tool", "k", scope="user:alice") is None
    assert cache.get("tool", "k", scope="user:bob") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
