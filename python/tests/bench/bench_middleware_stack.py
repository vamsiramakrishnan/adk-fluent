"""Benchmark: middleware dispatch.

Targets ``_MiddlewarePlugin._run_stack`` — previously did a per-call
``getattr(mw, method_name, None)`` lookup for every middleware. Wave 1
replaced that with a precomputed hook table built at plugin construction
time.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from adk_fluent.middleware import _MiddlewarePlugin  # noqa: PLC2701

from tests.bench._common import bench, report_header


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


def main() -> None:
    report_header("Middleware dispatch benchmarks")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    fake_ctx = SimpleNamespace(agent=SimpleNamespace(name="bench_agent"))
    fake_req = SimpleNamespace()

    # Empty stack — should be near-free after hook table lookup.
    plugin_empty = _MiddlewarePlugin("bench_empty", [])
    bench(
        "dispatch[0 mw] before_model",
        lambda: loop.run_until_complete(
            plugin_empty._run_stack("before_model", fake_ctx, fake_req)
        ),
        iters=50_000,
    )

    # Single no-op middleware.
    plugin_one = _MiddlewarePlugin("bench_one", [_NoopMiddleware()])
    bench(
        "dispatch[1 mw] before_model",
        lambda: loop.run_until_complete(
            plugin_one._run_stack("before_model", fake_ctx, fake_req)
        ),
        iters=50_000,
    )

    # 8 middlewares in the stack.
    plugin_many = _MiddlewarePlugin(
        "bench_many", [_NoopMiddleware() for _ in range(8)]
    )
    bench(
        "dispatch[8 mw] before_model",
        lambda: loop.run_until_complete(
            plugin_many._run_stack("before_model", fake_ctx, fake_req)
        ),
        iters=50_000,
    )

    # Sparse middlewares where hot path is empty → hook_table.get() miss.
    plugin_sparse = _MiddlewarePlugin(
        "bench_sparse", [_SparseMiddleware() for _ in range(8)]
    )
    bench(
        "dispatch[8 sparse] after_tool (empty)",
        lambda: loop.run_until_complete(
            plugin_sparse._run_stack("after_tool", fake_ctx, "some_tool", "result")
        ),
        iters=100_000,
    )

    loop.close()


if __name__ == "__main__":
    main()
