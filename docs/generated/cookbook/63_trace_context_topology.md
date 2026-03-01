# TraceContext and Topology Hooks: Cross-Cutting Observability

Demonstrates the TraceContext per-invocation state bag and the
topology hooks protocol for observing workflow structure.

Key concepts:

- TraceContext: request_id, elapsed, key-value store per invocation
- TopologyHooks protocol: on_loop_iteration, on_fanout_start/complete,
  on_route_selected, on_fallback_attempt, on_timeout
- DispatchDirective: cancel dispatches or inject state
- LoopDirective: break out of loops from middleware
- TopologyLogMiddleware: built-in structured topology logging
- \_trace_context ContextVar: access from any hook

*How to run agents in parallel using FanOut.*

_Source: `63_trace_context_topology.py`_

::::\{tab-set}
:::\{tab-item} adk-fluent

```python
from adk_fluent.middleware import (
    DispatchDirective,
    LoopDirective,
    TopologyHooks,
    TopologyLogMiddleware,
    TraceContext,
    _trace_context,
)

# --- 1. TraceContext lifecycle ---
ctx = TraceContext()

# Auto-generated request ID (12-char hex)
assert isinstance(ctx.request_id, str)
assert len(ctx.request_id) == 12

# Elapsed time since creation
import time

time.sleep(0.01)
assert ctx.elapsed > 0

# Key-value store for inter-hook state
ctx["total_tokens"] = 1500
ctx["agent_count"] = 3
assert ctx["total_tokens"] == 1500
assert ctx.get("agent_count") == 3
assert ctx.get("missing_key", "default") == "default"
assert "total_tokens" in ctx
assert "missing_key" not in ctx

# TraceContext with invocation_context
ctx_with_inv = TraceContext(invocation_context="mock_inv_ctx")
assert ctx_with_inv.invocation_context == "mock_inv_ctx"

# Repr
r = repr(ctx)
assert "TraceContext" in r
assert ctx.request_id in r

# --- 2. ContextVar storage ---
# TraceContext is stored in a ContextVar for cross-hook access
assert _trace_context.get() is None  # not set yet
token = _trace_context.set(ctx)
assert _trace_context.get() is ctx
_trace_context.reset(token)  # clean up

# --- 3. DispatchDirective ---
# Default: proceed normally
d = DispatchDirective()
assert d.cancel is False
assert d.inject_state is None

# Cancel a dispatch
cancel = DispatchDirective(cancel=True)
assert cancel.cancel is True

# Inject state before dispatch
inject = DispatchDirective(inject_state={"priority": "high"})
assert inject.inject_state == {"priority": "high"}
assert inject.cancel is False

# --- 4. LoopDirective ---
# Default: continue looping
ld = LoopDirective()
assert ld.break_loop is False

# Break out of a loop
break_it = LoopDirective(break_loop=True)
assert break_it.break_loop is True

# --- 5. TopologyLogMiddleware captures events ---
topo_log = TopologyLogMiddleware()
assert isinstance(topo_log.log, list)
assert len(topo_log.log) == 0

# Has all the topology hooks
assert hasattr(topo_log, "on_loop_iteration")
assert hasattr(topo_log, "on_fanout_start")
assert hasattr(topo_log, "on_fanout_complete")
assert hasattr(topo_log, "on_route_selected")
assert hasattr(topo_log, "on_fallback_attempt")
assert hasattr(topo_log, "on_timeout")

# --- 6. TopologyHooks protocol conformance ---
# Any class with topology hook methods conforms to the protocol


class MyTopologyObserver:
    """Custom observer implementing topology hooks."""

    def __init__(self):
        self.loop_count = 0
        self.routes = []
        self.timeouts = []

    async def on_loop_iteration(self, ctx, loop_name, iteration):
        self.loop_count += 1
        # Return LoopDirective to control loop behavior
        if iteration >= 5:
            return LoopDirective(break_loop=True)
        return None

    async def on_route_selected(self, ctx, route_name, selected_agent):
        self.routes.append(selected_agent)

    async def on_timeout(self, ctx, timeout_name, seconds, timed_out):
        self.timeouts.append({"name": timeout_name, "timed_out": timed_out})

    async def on_fanout_start(self, ctx, fanout_name, branch_names):
        pass

    async def on_fanout_complete(self, ctx, fanout_name, branch_names):
        pass

    async def on_fallback_attempt(self, ctx, fallback_name, agent_name, attempt, error):
        pass

    async def on_dispatch(self, ctx, task_name, agent_name):
        return None

    async def on_task_complete(self, ctx, task_name, result):
        pass

    async def on_task_error(self, ctx, task_name, error):
        pass

    async def on_join(self, ctx, joined, timed_out):
        pass

    async def on_stream_item(self, ctx, item, result, error):
        pass

    async def on_stream_start(self, ctx, source_info):
        pass

    async def on_stream_end(self, ctx, stats):
        pass

    async def on_backpressure(self, ctx, in_flight, max_concurrency):
        pass


observer = MyTopologyObserver()
assert isinstance(observer, TopologyHooks)

# --- 7. Test topology hooks fire correctly ---
import asyncio

ctx = TraceContext()


async def _run_observer():
    await observer.on_loop_iteration(ctx, "review_loop", 1)
    await observer.on_loop_iteration(ctx, "review_loop", 2)
    await observer.on_route_selected(ctx, "intent_router", "support_agent")
    await observer.on_timeout(ctx, "slow_agent", 30.0, False)
    await observer.on_timeout(ctx, "stuck_agent", 10.0, True)


asyncio.run(_run_observer())

assert observer.loop_count == 2
assert observer.routes == ["support_agent"]
assert len(observer.timeouts) == 2
assert observer.timeouts[0]["timed_out"] is False
assert observer.timeouts[1]["timed_out"] is True

# --- 8. LoopDirective from middleware ---


async def _run_loop_break():
    directive = await observer.on_loop_iteration(ctx, "loop", 5)
    assert isinstance(directive, LoopDirective)
    assert directive.break_loop is True


asyncio.run(_run_loop_break())

# --- 9. Integration with M module ---
from adk_fluent._middleware import M

# M.topology_log() wraps TopologyLogMiddleware
topo = M.topology_log()
assert len(topo) == 1
inner = topo.to_stack()[0]
assert isinstance(inner, TopologyLogMiddleware)

# Scope topology logging to specific agents
scoped = M.scope("classifier", M.topology_log())
assert scoped.to_stack()[0].agents == "classifier"

print("All TraceContext and topology hook assertions passed!")
```

:::
::::
