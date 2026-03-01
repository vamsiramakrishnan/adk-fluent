"""Dispatch-Aware Middleware: Observability for Background Execution

Demonstrates the dispatch/join middleware hooks for observing
background agent lifecycle events.

Key concepts:
  - DispatchLogMiddleware: built-in observability for dispatch/join
  - on_dispatch: fired when a task is dispatched as background
  - on_task_complete: fired when a dispatched task completes
  - on_task_error: fired when a dispatched task fails
  - on_join: fired after a join barrier completes
  - on_stream_item: fired after each stream item is processed
  - get_execution_mode(): query current mode (pipeline/dispatched/stream)
  - task_budget(): configure max concurrent dispatch tasks
"""

# --- FLUENT ---
from adk_fluent import Agent, dispatch, get_execution_mode, join
from adk_fluent._primitive_builders import BackgroundTask
from adk_fluent._base import _execution_mode
from adk_fluent._primitives import _middleware_dispatch_hooks
from adk_fluent.middleware import (
    DispatchLogMiddleware,
    Middleware,
    _MiddlewarePlugin,
)
from adk_fluent.stream import StreamRunner

# --- 1. DispatchLogMiddleware exists and has the right hooks ---
mw = DispatchLogMiddleware()
assert hasattr(mw, "on_dispatch")
assert hasattr(mw, "on_task_complete")
assert hasattr(mw, "on_task_error")
assert hasattr(mw, "on_join")
assert hasattr(mw, "on_stream_item")
assert isinstance(mw.log, list)
assert len(mw.log) == 0

# --- 2. Middleware protocol includes dispatch/stream hooks ---
assert hasattr(Middleware, "on_dispatch")
assert hasattr(Middleware, "on_task_complete")
assert hasattr(Middleware, "on_task_error")
assert hasattr(Middleware, "on_join")
assert hasattr(Middleware, "on_stream_item")

# --- 3. _MiddlewarePlugin has dispatch adapter methods ---
plugin = _MiddlewarePlugin(name="test", stack=[mw])
assert hasattr(plugin, "on_dispatch")
assert hasattr(plugin, "on_task_complete")
assert hasattr(plugin, "on_task_error")
assert hasattr(plugin, "on_join")
assert hasattr(plugin, "on_stream_item")

# --- 4. get_execution_mode() works ---
assert get_execution_mode() in ("pipeline", "dispatched", "stream")
# Default mode is pipeline
assert get_execution_mode() == "pipeline"

# --- 5. Configurable task_budget on dispatch() ---
writer = Agent("writer").model("gemini-2.5-flash").instruct("Write.")
emailer = Agent("emailer").model("gemini-2.5-flash").instruct("Email.")

# Via factory parameter
d = dispatch(emailer, task_budget=25)
assert isinstance(d, BackgroundTask)
assert d._max_tasks == 25
built = d.build()
assert built._max_tasks == 25

# Via fluent method
d2 = dispatch(emailer).task_budget(10)
assert d2._max_tasks == 10
built2 = d2.build()
assert built2._max_tasks == 10

# --- 6. StreamRunner has .middleware() and .task_budget() ---
sr = StreamRunner(writer)
assert hasattr(sr, "middleware")
assert hasattr(sr, "task_budget")
sr.task_budget(100).middleware(mw)
assert sr._max_tasks == 100
assert len(sr._middlewares) == 1

# --- 7. Custom middleware with dispatch hooks ---


class TrackingMiddleware:
    """Custom middleware that tracks dispatch lifecycle."""

    def __init__(self):
        self.dispatched = []
        self.completed = []
        self.errors = []
        self.joins = []

    async def on_dispatch(self, ctx, task_name, agent_name):
        self.dispatched.append(task_name)

    async def on_task_complete(self, ctx, task_name, result):
        self.completed.append(task_name)

    async def on_task_error(self, ctx, task_name, error):
        self.errors.append(task_name)

    async def on_join(self, ctx, joined, timed_out):
        self.joins.append({"joined": joined, "timed_out": timed_out})


tracker = TrackingMiddleware()
plugin2 = _MiddlewarePlugin(name="tracker", stack=[tracker])
assert hasattr(plugin2, "on_dispatch")

# --- 8. Prelude exports ---
from adk_fluent.prelude import DispatchLogMiddleware as DLM, get_execution_mode as gem

assert DLM is DispatchLogMiddleware
assert gem is get_execution_mode

# --- 9. Top-level exports ---
from adk_fluent import DispatchLogMiddleware as DLM2, get_execution_mode as gem2

assert DLM2 is DispatchLogMiddleware
assert gem2 is get_execution_mode

print("All dispatch middleware assertions passed!")
