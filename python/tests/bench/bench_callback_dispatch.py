"""Benchmark: composed callback dispatch hot path.

Every ``.before_model(fn)`` / ``.after_model(fn)`` registration ends up
in a list that ``_compose_callbacks`` folds into a single callable at
build time. Wave 4b pre-classifies each entry as sync/async once,
eliminating the per-turn ``asyncio.iscoroutine`` probe for every
callback in the chain.

Numbers below measure the dispatch cost of the composed closure *inside
a running event loop* (one callback invocation per turn per hook). At
3 hooks × 8 agents this path runs ~24 times per LLM round-trip.

The ``_bench_async`` helper uses a single awaiting loop instead of
``run_until_complete`` per call so the numbers reflect actual per-turn
cost rather than loop setup/teardown overhead.
"""

from __future__ import annotations

import asyncio
import gc
import time
from collections.abc import Callable

from adk_fluent._base import _compose_callbacks
from tests.bench._common import report_header


def _sync_noop(*args, **kwargs) -> None:
    return None


async def _async_noop(*args, **kwargs) -> None:
    return None


async def _bench_async(name: str, awaitable_factory: Callable, *, iters: int) -> float:
    """Time an async callable from inside an already-running loop."""
    # Warmup
    for _ in range(1_000):
        await awaitable_factory()
    gc.collect()
    gc.disable()
    try:
        t0 = time.perf_counter_ns()
        for _ in range(iters):
            await awaitable_factory()
        elapsed = time.perf_counter_ns() - t0
    finally:
        gc.enable()
    ns_per_op = elapsed / iters
    print(f"{name:<48s} {iters:>10,} iters  {ns_per_op:>10.1f} ns/op")
    return ns_per_op


async def _run() -> None:
    # Single-callback path: returned raw, so this measures the raw fn.
    single = _compose_callbacks([_sync_noop])
    assert single is _sync_noop, "single callback should be returned raw"

    for n in (2, 3, 5):
        composed = _compose_callbacks([_sync_noop] * n)
        await _bench_async(f"composed {n}x sync", composed, iters=500_000)

    for n in (2, 3, 5):
        mix = [_sync_noop, _async_noop] * (n // 2)
        if len(mix) < n:
            mix.append(_sync_noop)
        composed = _compose_callbacks(mix)
        await _bench_async(f"composed {n}x mixed", composed, iters=500_000)

    for n in (2, 3, 5):
        composed = _compose_callbacks([_async_noop] * n)
        await _bench_async(f"composed {n}x async", composed, iters=500_000)


def main() -> None:
    report_header("Callback dispatch benchmarks")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
