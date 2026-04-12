"""Benchmark: middleware dispatch.

Targets ``_MiddlewarePlugin._run_stack`` — previously did a per-call
``getattr(mw, method_name, None)`` lookup for every middleware. Wave 1
replaced that with a precomputed hook table built at plugin construction
time.

Wave 4c partitions the hook table into ``(global, scoped)`` buckets at
init so the global bucket skips the ``_agent_matches`` filter entirely,
which is the common case.

Numbers below measure the dispatch cost *inside a running event loop*
via ``_bench_async`` (one await per turn). This avoids the ~35 µs per-call
``run_until_complete`` ceremony that dominated the prior version and makes
the actual dispatch cost visible.
"""

from __future__ import annotations

import asyncio
import gc
import time
from collections.abc import Callable
from types import SimpleNamespace

from adk_fluent.middleware import _MiddlewarePlugin, _ScopedMiddleware  # noqa: PLC2701
from tests.bench._common import report_header


class _NoopMiddleware:
    """Implements every hot-path hook as a no-op. Worst case for dispatch."""

    async def before_agent(self, ctx, agent_name):
        return None

    async def after_agent(self, ctx, agent_name):
        return None

    async def before_model(self, ctx, request):
        return None

    async def after_model(self, ctx, response):
        return None

    async def before_tool(self, ctx, tool_name, args):
        return None

    async def after_tool(self, ctx, tool_name, result):
        return None


class _SparseMiddleware:
    """Only implements before_model — exercises the hook-table skip path."""

    async def before_model(self, ctx, request):
        return None


async def _bench_async(name: str, fn_factory: Callable, *, iters: int) -> float:
    """Time an async callable from inside an already-running loop."""
    for _ in range(1_000):
        await fn_factory()
    gc.collect()
    gc.disable()
    try:
        t0 = time.perf_counter_ns()
        for _ in range(iters):
            await fn_factory()
        elapsed = time.perf_counter_ns() - t0
    finally:
        gc.enable()
    ns_per_op = elapsed / iters
    print(f"{name:<48s} {iters:>10,} iters  {ns_per_op:>10.1f} ns/op")
    return ns_per_op


async def _run() -> None:
    fake_ctx = SimpleNamespace(agent=SimpleNamespace(name="bench_agent"))
    fake_req = SimpleNamespace()

    # ---- baseline: empty stack / hook table miss -----------------------
    plugin_empty = _MiddlewarePlugin("bench_empty", [])
    await _bench_async(
        "dispatch[0 mw] before_model (miss)",
        lambda: plugin_empty._run_stack("before_model", fake_ctx, fake_req, agent_name="bench_agent"),
        iters=500_000,
    )

    # Sparse middlewares — hook_table.get() miss on after_tool.
    plugin_sparse = _MiddlewarePlugin("bench_sparse", [_SparseMiddleware() for _ in range(8)])
    await _bench_async(
        "dispatch[8 sparse] after_tool (miss)",
        lambda: plugin_sparse._run_stack("after_tool", fake_ctx, "tool", "result", agent_name="bench_agent"),
        iters=500_000,
    )

    # ---- global-only stacks (all mw have agents=None) ------------------
    # Common case: after Wave 4c these skip _agent_matches entirely.
    for n in (1, 3, 8):
        plugin = _MiddlewarePlugin(f"bench_global_{n}", [_NoopMiddleware() for _ in range(n)])
        await _bench_async(
            f"dispatch[{n} mw global] before_model",
            lambda p=plugin: p._run_stack("before_model", fake_ctx, fake_req, agent_name="bench_agent"),
            iters=200_000,
        )

    # ---- mixed global + scoped stacks ----------------------------------
    # 4 global + 4 scoped(agents="bench_agent") — scoped bucket runs with
    # the filter, global bucket runs without.
    mixed = [_NoopMiddleware() for _ in range(4)]
    mixed += [_ScopedMiddleware("bench_agent", _NoopMiddleware()) for _ in range(4)]
    plugin_mixed = _MiddlewarePlugin("bench_mixed", mixed)
    await _bench_async(
        "dispatch[4 global + 4 scoped hit] before_model",
        lambda: plugin_mixed._run_stack("before_model", fake_ctx, fake_req, agent_name="bench_agent"),
        iters=200_000,
    )
    await _bench_async(
        "dispatch[4 global + 4 scoped miss] before_model",
        lambda: plugin_mixed._run_stack("before_model", fake_ctx, fake_req, agent_name="other_agent"),
        iters=200_000,
    )

    # ---- fully scoped stack (pathological) -----------------------------
    scoped_only = [_ScopedMiddleware("bench_agent", _NoopMiddleware()) for _ in range(8)]
    plugin_scoped = _MiddlewarePlugin("bench_scoped_only", scoped_only)
    await _bench_async(
        "dispatch[8 scoped hit] before_model",
        lambda: plugin_scoped._run_stack("before_model", fake_ctx, fake_req, agent_name="bench_agent"),
        iters=200_000,
    )


def main() -> None:
    report_header("Middleware dispatch benchmarks")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
