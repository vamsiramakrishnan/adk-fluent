"""Middleware protocol and adapter for adk-fluent.

Middleware provides composable cross-cutting behavior (logging, retry,
cost tracking, etc.) that compiles to ADK BasePlugin instances.

Middleware is app-global (attached via ExecutionConfig). This is separate
from agent-level callbacks (stored per-agent in IR nodes).

Architecture layers::

    M.retry(3) | M.scope("writer", M.cost())   <-- DX surface
             |  compiles to
    [RetryMiddleware(3), _ScopedMiddleware(...)] <-- protocol instances
             |  compiled by
    _MiddlewarePlugin(BasePlugin)               <-- ADK plugin adapter
             |  registered as
    App(plugins=[plugin])                       <-- ADK runtime
"""

from __future__ import annotations

import asyncio as _asyncio
import contextlib as _contextlib
import logging as _logging
import re as _re
import time as _time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4 as _uuid4

from google.adk.plugins.base_plugin import BasePlugin

__all__ = [
    # Core types
    "TraceContext",
    "DispatchDirective",
    "LoopDirective",
    # Protocols
    "Middleware",
    "TopologyHooks",
    # Adapter
    "_MiddlewarePlugin",
    # Built-in middleware
    "RetryMiddleware",
    "StructuredLogMiddleware",
    "DispatchLogMiddleware",
    "TopologyLogMiddleware",
    "LatencyMiddleware",
    "CostTracker",
    # Helpers
    "_agent_matches",
    "_ScopedMiddleware",
    "_ConditionalMiddleware",
    "_SingleHookMiddleware",
    # ContextVars
    "_trace_context",
    "_topology_hooks",
]

_log = _logging.getLogger(__name__)

# ======================================================================
# Mechanism 1: TraceContext (inter-hook state)
# ======================================================================


class TraceContext:
    """Per-invocation state bag flowing through all middleware hooks.

    Created once per ``before_run_callback``, stored in a ContextVar,
    and passed as the first arg to every middleware hook.  Propagates
    to dispatch children via asyncio ContextVar copy-on-write.

    Backward compat: v1 middleware typed ``ctx: Any`` -- ``TraceContext``
    works in that position.  Access the raw ADK invocation context via
    ``ctx.invocation_context``.
    """

    __slots__ = ("_data", "request_id", "start_time", "invocation_context")

    def __init__(self, invocation_context: Any = None) -> None:
        self.request_id: str = _uuid4().hex[:12]
        self.start_time: float = _time.monotonic()
        self.invocation_context = invocation_context
        self._data: dict[str, Any] = {}

    @property
    def elapsed(self) -> float:
        """Seconds since this invocation started."""
        return _time.monotonic() - self.start_time

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"TraceContext(request_id={self.request_id!r}, elapsed={self.elapsed:.3f}s)"


_trace_context: ContextVar[TraceContext | None] = ContextVar("_trace_context", default=None)


# ======================================================================
# Mechanism 4: Directive dataclasses (controllable dispatch/loop)
# ======================================================================


@dataclass(frozen=True)
class DispatchDirective:
    """Returned by ``on_dispatch`` to control dispatch behavior.

    - ``cancel=True``: skip this dispatch entirely.
    - ``inject_state``: merge keys into session state before dispatch.

    Returning ``None`` from ``on_dispatch`` proceeds normally (v1 compat).
    """

    cancel: bool = False
    inject_state: dict[str, Any] | None = None


@dataclass(frozen=True)
class LoopDirective:
    """Returned by ``on_loop_iteration`` to control loop behavior.

    - ``break_loop=True``: exit the loop via ADK's escalate mechanism.
    """

    break_loop: bool = False


# ======================================================================
# Mechanism 3: TopologyHooks protocol
# ======================================================================


@runtime_checkable
class TopologyHooks(Protocol):
    """Protocol for middleware topology lifecycle hooks.

    Generalizes the former ``DispatchHooks`` to cover all workflow
    structure: loops, fanout, routes, fallbacks, timeouts, and
    dispatch/join.
    """

    # --- Dispatch/Join (migrated from DispatchHooks) ---

    async def on_dispatch(self, ctx: Any, task_name: str, agent_name: str) -> DispatchDirective | None: ...
    async def on_task_complete(self, ctx: Any, task_name: str, result: str) -> None: ...
    async def on_task_error(self, ctx: Any, task_name: str, error: Exception) -> None: ...
    async def on_join(self, ctx: Any, joined: list[str], timed_out: list[str]) -> None: ...

    # --- Topology (NEW) ---

    async def on_loop_iteration(self, ctx: Any, loop_name: str, iteration: int) -> LoopDirective | None: ...
    async def on_fanout_start(self, ctx: Any, fanout_name: str, branch_names: list[str]) -> None: ...
    async def on_fanout_complete(self, ctx: Any, fanout_name: str, branch_names: list[str]) -> None: ...
    async def on_route_selected(self, ctx: Any, route_name: str, selected_agent: str) -> None: ...
    async def on_fallback_attempt(
        self, ctx: Any, fallback_name: str, agent_name: str, attempt: int, error: Exception | None
    ) -> None: ...
    async def on_timeout(self, ctx: Any, timeout_name: str, seconds: float, timed_out: bool) -> None: ...

    # --- Stream lifecycle ---

    async def on_stream_item(self, ctx: Any, item: str, result: str | None, error: Exception | None) -> None: ...
    async def on_stream_start(self, ctx: Any, source_info: dict) -> None: ...
    async def on_stream_end(self, ctx: Any, stats: Any) -> None: ...
    async def on_backpressure(self, ctx: Any, in_flight: int, max_concurrency: int) -> None: ...


_topology_hooks: ContextVar[TopologyHooks | None] = ContextVar("_topology_hooks", default=None)


# ======================================================================
# Middleware protocol (extended from v1)
# ======================================================================


@runtime_checkable
class Middleware(Protocol):
    """A composable unit of cross-cutting behavior.

    All methods are optional -- implement only the hooks you need.
    Stack execution: in-order, first non-None return short-circuits.

    Lifecycle groups:
        Runner:   on_user_message, before_run, after_run, on_event
        Agent:    before_agent, after_agent
        Model:    before_model, after_model, on_model_error
        Tool:     before_tool, after_tool, on_tool_error
        Dispatch: on_dispatch, on_task_complete, on_task_error, on_join
        Topology: on_loop_iteration, on_fanout_start, on_fanout_complete,
                  on_route_selected, on_fallback_attempt, on_timeout
        Stream:   on_stream_item, on_stream_start, on_stream_end, on_backpressure
        Error:    on_middleware_error
        Cleanup:  close
    """

    @classmethod
    def __subclasshook__(cls, C):
        # All methods are optional -- any class conforms to Middleware.
        return True

    # --- Runner lifecycle ---

    async def on_user_message(self, ctx: Any, message: Any) -> Any:
        """Called when a user message is received."""
        return None

    async def before_run(self, ctx: Any) -> Any:
        """Called before execution starts."""
        return None

    async def after_run(self, ctx: Any) -> None:
        """Called after execution completes."""
        return None

    async def on_event(self, ctx: Any, event: Any) -> Any:
        """Called for each event during execution."""
        return None

    # --- Agent lifecycle ---

    async def before_agent(self, ctx: Any, agent_name: str) -> Any:
        """Called before an agent executes."""
        return None

    async def after_agent(self, ctx: Any, agent_name: str) -> Any:
        """Called after an agent executes."""
        return None

    # --- Model lifecycle ---

    async def before_model(self, ctx: Any, request: Any) -> Any:
        """Called before an LLM request."""
        return None

    async def after_model(self, ctx: Any, response: Any) -> Any:
        """Called after an LLM response."""
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Exception) -> Any:
        """Called when an LLM request fails."""
        return None

    # --- Tool lifecycle ---

    async def before_tool(self, ctx: Any, tool_name: str, args: dict) -> dict | None:
        """Called before a tool executes."""
        return None

    async def after_tool(self, ctx: Any, tool_name: str, args: dict, result: dict) -> dict | None:
        """Called after a tool executes."""
        return None

    async def on_tool_error(self, ctx: Any, tool_name: str, args: dict, error: Exception) -> dict | None:
        """Called when a tool execution fails."""
        return None

    # --- Dispatch lifecycle ---

    async def on_dispatch(self, ctx: Any, task_name: str, agent_name: str) -> DispatchDirective | None:
        """Called when a task is dispatched as background.

        Return ``DispatchDirective(cancel=True)`` to skip this dispatch.
        Return ``None`` to proceed normally (v1 compat).
        """
        return None

    async def on_task_complete(self, ctx: Any, task_name: str, result: str) -> None:
        """Called when a dispatched task completes successfully."""
        return None

    async def on_task_error(self, ctx: Any, task_name: str, error: Exception) -> None:
        """Called when a dispatched task fails."""
        return None

    async def on_join(self, ctx: Any, joined: list[str], timed_out: list[str]) -> None:
        """Called after a join completes."""
        return None

    # --- Topology lifecycle (NEW) ---

    async def on_loop_iteration(self, ctx: Any, loop_name: str, iteration: int) -> LoopDirective | None:
        """Called at the start of each loop iteration.

        Return ``LoopDirective(break_loop=True)`` to exit the loop.
        """
        return None

    async def on_fanout_start(self, ctx: Any, fanout_name: str, branch_names: list[str]) -> None:
        """Called before parallel branches start executing."""
        return None

    async def on_fanout_complete(self, ctx: Any, fanout_name: str, branch_names: list[str]) -> None:
        """Called after all parallel branches complete."""
        return None

    async def on_route_selected(self, ctx: Any, route_name: str, selected_agent: str) -> None:
        """Called when a route selects a target agent."""
        return None

    async def on_fallback_attempt(
        self, ctx: Any, fallback_name: str, agent_name: str, attempt: int, error: Exception | None
    ) -> None:
        """Called at the start of each fallback attempt."""
        return None

    async def on_timeout(self, ctx: Any, timeout_name: str, seconds: float, timed_out: bool) -> None:
        """Called when a timeout-wrapped agent completes or times out."""
        return None

    # --- Stream lifecycle (extended) ---

    async def on_stream_item(self, ctx: Any, item: str, result: str | None, error: Exception | None) -> None:
        """Called after each stream item is processed."""
        return None

    async def on_stream_start(self, ctx: Any, source_info: dict) -> None:
        """Called before the first stream item is processed."""
        return None

    async def on_stream_end(self, ctx: Any, stats: Any) -> None:
        """Called after all stream items are processed."""
        return None

    async def on_backpressure(self, ctx: Any, in_flight: int, max_concurrency: int) -> None:
        """Called when in-flight items reach the concurrency limit."""
        return None

    # --- Error boundary ---

    async def on_middleware_error(self, ctx: Any, hook_name: str, error: Exception, middleware: Any) -> None:
        """Called when another middleware hook raises an exception.

        Observe-only. Errors in this handler are swallowed.
        """
        return None

    # --- Cleanup ---

    async def close(self) -> None:
        """Called when the app shuts down."""
        pass


# ======================================================================
# Mechanism 2: Per-agent scoping
# ======================================================================

# Agent-scoped hooks -- these check _agent_matches before firing.
_SCOPED_HOOKS = frozenset(
    {
        "before_agent",
        "after_agent",
        "before_model",
        "after_model",
        "on_model_error",
        "before_tool",
        "after_tool",
        "on_tool_error",
    }
)


def _agent_matches(mw: Any, agent_name: str) -> bool:
    """Check whether a middleware should fire for the given agent.

    Supports:
        - ``None`` (absent): global, fires for all agents.
        - ``str``: exact match.
        - ``tuple[str, ...]``: membership test.
        - ``re.Pattern``: regex search.
        - ``Callable[[str], bool]``: predicate.
    """
    scope = getattr(mw, "agents", None)
    if scope is None:
        return True
    if isinstance(scope, str):
        return agent_name == scope
    if isinstance(scope, tuple):
        return agent_name in scope
    if isinstance(scope, _re.Pattern):
        return scope.search(agent_name) is not None
    if callable(scope):
        return bool(scope(agent_name))
    return True


# ======================================================================
# Mechanism 6: Conditional + Scoped wrappers
# ======================================================================


class _ScopedMiddleware:
    """Wraps a middleware instance with an ``agents`` scope."""

    def __init__(self, agents: str | tuple[str, ...], inner: Any) -> None:
        self.agents = agents
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __repr__(self) -> str:
        return f"_ScopedMiddleware(agents={self.agents!r}, inner={self._inner!r})"


class _ConditionalMiddleware:
    """Wraps a middleware to only fire when a condition is met.

    ``condition`` can be:
        - A callable returning bool.
        - A string shortcut: ``"stream"``, ``"dispatched"``, ``"pipeline"``
          matching ``ExecutionMode``.
        - A ``PredicateSchema`` subclass — evaluated against session state
          from ``TraceContext.invocation_context`` at invocation time.
    """

    def __init__(self, condition: str | Callable[[], bool] | type, inner: Any) -> None:
        self._condition = condition
        self._inner = inner
        # Forward agents and schema from inner for static introspection
        agents = getattr(inner, "agents", None)
        if agents is not None:
            self.agents = agents
        schema = getattr(inner, "schema", None)
        if schema is not None:
            self.schema = schema

    def _check(self) -> bool:
        cond = self._condition
        if isinstance(cond, str):
            return self._check_mode(cond)
        if isinstance(cond, type):
            return self._check_predicate(cond)
        if callable(cond):
            return bool(cond())
        return True

    @staticmethod
    def _check_mode(mode_str: str) -> bool:
        from adk_fluent._primitives import get_execution_mode

        return bool(get_execution_mode().value == mode_str)

    @staticmethod
    def _check_predicate(schema_cls: type) -> bool:
        """Evaluate a PredicateSchema against current session state."""
        trace = _trace_context.get()
        if trace is None:
            return True  # no trace context = can't evaluate, allow
        inv_ctx = trace.invocation_context
        if inv_ctx is None:
            return True
        session = getattr(inv_ctx, "session", None)
        if session is None:
            return True
        state = getattr(session, "state", {})
        evaluate = getattr(schema_cls, "evaluate", None)
        if evaluate is None:
            _log.warning(
                "M.when() received type %s with no evaluate() method; treating as always-true",
                schema_cls.__name__,
            )
            return True
        # Extract field values from state using schema introspection
        from adk_fluent._schema_base import Reads

        field_list = getattr(schema_cls, "_field_list", ())
        kwargs: dict[str, Any] = {}
        for f in field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                full_key = f.name if r.scope == "session" else f"{r.scope}:{f.name}"
                kwargs[f.name] = state.get(full_key)
        return bool(evaluate(**kwargs))

    def __getattr__(self, name: str) -> Any:
        val = getattr(self._inner, name, None)
        if val is None or not callable(val):
            if val is None:
                raise AttributeError(name)
            return val  # non-callable attributes forwarded directly

        # Return a guarded wrapper that defers condition check to invocation time
        async def _guarded(*args: Any, **kwargs: Any) -> Any:
            if not self._check():
                return None
            result = val(*args, **kwargs)
            if hasattr(result, "__await__"):
                result = await result  # type: ignore[reportGeneralTypeIssues]
            return result

        return _guarded

    def __repr__(self) -> str:
        return f"_ConditionalMiddleware(inner={self._inner!r})"


class _SingleHookMiddleware:
    """Wraps a single function as a middleware with one hook."""

    def __init__(self, hook_name: str, fn: Callable) -> None:
        self._hook_name = hook_name
        setattr(self, hook_name, fn)

    def __repr__(self) -> str:
        return f"_SingleHookMiddleware({self._hook_name!r})"


# ======================================================================
# Adapter: compile a middleware stack into a single ADK BasePlugin
# ======================================================================


class _MiddlewarePlugin(BasePlugin):
    """Compiles a middleware stack into a single ADK-compatible plugin.

    ADK execution order: plugins first -> agent callbacks second.
    This ensures middleware has priority over user-defined callbacks.

    Mechanisms:
        1. TraceContext: created in before_run, passed as first arg.
        2. Agent scoping: _agent_matches filters per-agent hooks.
        3. Error boundary: try/except around each hook call.
        4. Topology hooks: set self as _topology_hooks ContextVar.
    """

    def __init__(self, name: str, stack: list) -> None:
        super().__init__(name=name)
        self._stack = list(stack)

    # --- Helpers: iterate stack ---

    def _get_trace(self) -> TraceContext:
        """Get or create a TraceContext for the current invocation."""
        trace = _trace_context.get()
        if trace is None:
            trace = TraceContext()
            _trace_context.set(trace)
        return trace

    async def _run_stack(self, method_name: str, *args, agent_name: str | None = None) -> Any:
        """Call *method_name* on each middleware in order.

        Short-circuits on the first non-None return.
        Wraps each call in an error boundary.
        Filters scoped hooks by agent_name.
        """
        is_scoped = method_name in _SCOPED_HOOKS
        for mw in self._stack:
            if is_scoped and agent_name is not None and not _agent_matches(mw, agent_name):
                continue
            fn = getattr(mw, method_name, None)
            if fn is None:
                continue
            try:
                result = await fn(*args)
                if result is not None:
                    return result
            except Exception as exc:
                _log.warning("Middleware %s.%s raised: %s", type(mw).__name__, method_name, exc)
                await self._fire_middleware_error(mw, method_name, exc)
        return None

    async def _run_stack_void(self, method_name: str, *args, agent_name: str | None = None) -> None:
        """Call *method_name* on ALL middleware (no short-circuit).

        Wraps each call in an error boundary.
        """
        is_scoped = method_name in _SCOPED_HOOKS
        for mw in self._stack:
            if is_scoped and agent_name is not None and not _agent_matches(mw, agent_name):
                continue
            fn = getattr(mw, method_name, None)
            if fn is None:
                continue
            try:
                await fn(*args)
            except Exception as exc:
                _log.warning("Middleware %s.%s raised: %s", type(mw).__name__, method_name, exc)
                await self._fire_middleware_error(mw, method_name, exc)

    async def _fire_middleware_error(self, failed_mw: Any, hook_name: str, error: Exception) -> None:
        """Fire on_middleware_error on all *other* middleware.

        Errors in error handlers are swallowed.
        """
        trace = self._get_trace()
        for mw in self._stack:
            if mw is failed_mw:
                continue
            fn = getattr(mw, "on_middleware_error", None)
            if fn is None:
                continue
            with _contextlib.suppress(Exception):
                await fn(trace, hook_name, error, failed_mw)

    # --- Runner lifecycle ---

    async def on_user_message_callback(self, *, invocation_context, user_message):
        trace = self._get_trace()
        trace.invocation_context = invocation_context
        return await self._run_stack("on_user_message", trace, user_message)

    async def before_run_callback(self, *, invocation_context):
        # Create TraceContext for this invocation
        trace = TraceContext(invocation_context=invocation_context)
        _trace_context.set(trace)

        # Set self as topology hooks (replaces old _middleware_dispatch_hooks)
        _topology_hooks.set(self)

        # Backward compat: also set _middleware_dispatch_hooks
        from adk_fluent._primitives import _middleware_dispatch_hooks

        _middleware_dispatch_hooks.set(self)

        return await self._run_stack("before_run", trace)

    async def after_run_callback(self, *, invocation_context):
        trace = self._get_trace()
        await self._run_stack_void("after_run", trace)

    async def on_event_callback(self, *, invocation_context, event):
        trace = self._get_trace()
        return await self._run_stack("on_event", trace, event)

    # --- Agent lifecycle ---

    async def before_agent_callback(self, *, agent, callback_context):
        trace = self._get_trace()
        agent_name = getattr(agent, "name", str(agent))
        return await self._run_stack(
            "before_agent",
            trace,
            agent_name,
            agent_name=agent_name,
        )

    async def after_agent_callback(self, *, agent, callback_context):
        trace = self._get_trace()
        agent_name = getattr(agent, "name", str(agent))
        return await self._run_stack(
            "after_agent",
            trace,
            agent_name,
            agent_name=agent_name,
        )

    # --- Model lifecycle ---

    async def before_model_callback(self, *, callback_context, llm_request):
        trace = self._get_trace()
        agent_name = getattr(callback_context, "agent_name", None)
        return await self._run_stack("before_model", trace, llm_request, agent_name=agent_name)

    async def after_model_callback(self, *, callback_context, llm_response):
        trace = self._get_trace()
        agent_name = getattr(callback_context, "agent_name", None)
        return await self._run_stack("after_model", trace, llm_response, agent_name=agent_name)

    async def on_model_error_callback(self, *, callback_context, llm_request, error):
        trace = self._get_trace()
        agent_name = getattr(callback_context, "agent_name", None)
        return await self._run_stack("on_model_error", trace, llm_request, error, agent_name=agent_name)

    # --- Tool lifecycle ---

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        trace = self._get_trace()
        agent_name = getattr(tool_context, "agent_name", None)
        return await self._run_stack(
            "before_tool",
            trace,
            getattr(tool, "name", str(tool)),
            tool_args,
            agent_name=agent_name,
        )

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
        trace = self._get_trace()
        agent_name = getattr(tool_context, "agent_name", None)
        return await self._run_stack(
            "after_tool",
            trace,
            getattr(tool, "name", str(tool)),
            tool_args,
            result,
            agent_name=agent_name,
        )

    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
        trace = self._get_trace()
        agent_name = getattr(tool_context, "agent_name", None)
        return await self._run_stack(
            "on_tool_error",
            trace,
            getattr(tool, "name", str(tool)),
            tool_args,
            error,
            agent_name=agent_name,
        )

    # --- Dispatch/Topology lifecycle (called from primitives) ---

    async def on_dispatch(self, ctx, task_name, agent_name):
        trace = self._get_trace()
        result = await self._run_stack("on_dispatch", trace, task_name, agent_name)
        return result  # may be DispatchDirective or None

    async def on_task_complete(self, ctx, task_name, result):
        trace = self._get_trace()
        await self._run_stack_void("on_task_complete", trace, task_name, result)

    async def on_task_error(self, ctx, task_name, error):
        trace = self._get_trace()
        await self._run_stack_void("on_task_error", trace, task_name, error)

    async def on_join(self, ctx, joined, timed_out):
        trace = self._get_trace()
        await self._run_stack_void("on_join", trace, joined, timed_out)

    async def on_loop_iteration(self, ctx, loop_name, iteration):
        trace = self._get_trace()
        return await self._run_stack("on_loop_iteration", trace, loop_name, iteration)

    async def on_fanout_start(self, ctx, fanout_name, branch_names):
        trace = self._get_trace()
        await self._run_stack_void("on_fanout_start", trace, fanout_name, branch_names)

    async def on_fanout_complete(self, ctx, fanout_name, branch_names):
        trace = self._get_trace()
        await self._run_stack_void("on_fanout_complete", trace, fanout_name, branch_names)

    async def on_route_selected(self, ctx, route_name, selected_agent):
        trace = self._get_trace()
        await self._run_stack_void("on_route_selected", trace, route_name, selected_agent)

    async def on_fallback_attempt(self, ctx, fallback_name, agent_name, attempt, error):
        trace = self._get_trace()
        await self._run_stack_void("on_fallback_attempt", trace, fallback_name, agent_name, attempt, error)

    async def on_timeout(self, ctx, timeout_name, seconds, timed_out):
        trace = self._get_trace()
        await self._run_stack_void("on_timeout", trace, timeout_name, seconds, timed_out)

    # --- Stream lifecycle ---

    async def on_stream_item(self, ctx, item, result, error):
        trace = self._get_trace()
        await self._run_stack_void("on_stream_item", trace, item, result, error)

    async def on_stream_start(self, ctx, source_info):
        trace = self._get_trace()
        await self._run_stack_void("on_stream_start", trace, source_info)

    async def on_stream_end(self, ctx, stats):
        trace = self._get_trace()
        await self._run_stack_void("on_stream_end", trace, stats)

    async def on_backpressure(self, ctx, in_flight, max_concurrency):
        trace = self._get_trace()
        await self._run_stack_void("on_backpressure", trace, in_flight, max_concurrency)

    # --- Cleanup ---

    async def close(self):
        await self._run_stack_void("close")


# ---------------------------------------------------------------------------
# Built-in middleware implementations
# ---------------------------------------------------------------------------


class RetryMiddleware:
    """Retry middleware for model and tool errors.

    Returns None on error to let ADK retry.
    Uses exponential backoff between retries.
    """

    def __init__(self, max_attempts: int = 3, backoff_base: float = 1.0):
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self._attempts: dict[str, int] = {}

    async def on_model_error(self, ctx, request, error):
        key = f"model_{id(request)}"
        self._attempts[key] = self._attempts.get(key, 0) + 1
        if self._attempts[key] < self.max_attempts:
            delay = self.backoff_base * (2 ** (self._attempts[key] - 1))
            if delay > 0:
                await _asyncio.sleep(delay)
        return None

    async def on_tool_error(self, ctx, tool_name, args, error):
        key = f"tool_{tool_name}"
        self._attempts[key] = self._attempts.get(key, 0) + 1
        if self._attempts[key] < self.max_attempts:
            delay = self.backoff_base * (2 ** (self._attempts[key] - 1))
            if delay > 0:
                await _asyncio.sleep(delay)
        return None


class StructuredLogMiddleware:
    """Observability middleware that captures structured event logs.

    Never short-circuits -- all methods return None.
    Access captured events via the ``log`` attribute.
    """

    def __init__(self):
        self.log: list[dict] = []

    def _record(self, event, **kwargs):
        entry = {"event": event, "timestamp": _time.time()}
        entry.update(kwargs)
        self.log.append(entry)

    async def before_model(self, ctx, request):
        self._record("before_model", request=str(request)[:200])
        return None

    async def after_model(self, ctx, response):
        self._record("after_model", response=str(response)[:200])
        return None

    async def on_model_error(self, ctx, request, error):
        self._record("on_model_error", error=str(error))
        return None

    async def before_agent(self, ctx, agent_name):
        self._record("before_agent", agent_name=agent_name)
        return None

    async def after_agent(self, ctx, agent_name):
        self._record("after_agent", agent_name=agent_name)
        return None

    async def before_tool(self, ctx, tool_name, args):
        self._record("before_tool", tool_name=tool_name)
        return None

    async def after_tool(self, ctx, tool_name, args, result):
        self._record("after_tool", tool_name=tool_name)
        return None

    async def on_tool_error(self, ctx, tool_name, args, error):
        self._record("on_tool_error", tool_name=tool_name, error=str(error))
        return None


class DispatchLogMiddleware:
    """Observability middleware for dispatch/join lifecycle.

    Captures structured logs for dispatch, task completion, task error,
    and join events.  Access via the ``log`` attribute.

    Usage::

        mw = DispatchLogMiddleware()
        pipeline = writer >> dispatch(emailer) >> formatter >> join()
        pipeline.middleware(mw)
        # After execution: mw.log contains dispatch/join events
    """

    def __init__(self) -> None:
        self.log: list[dict] = []

    async def on_dispatch(self, ctx, task_name, agent_name):
        self.log.append(
            {
                "event": "dispatch",
                "task": task_name,
                "agent": agent_name,
                "time": _time.time(),
            }
        )

    async def on_task_complete(self, ctx, task_name, result):
        self.log.append(
            {
                "event": "task_complete",
                "task": task_name,
                "result_len": len(result) if result else 0,
                "time": _time.time(),
            }
        )

    async def on_task_error(self, ctx, task_name, error):
        self.log.append(
            {
                "event": "task_error",
                "task": task_name,
                "error": str(error),
                "time": _time.time(),
            }
        )

    async def on_join(self, ctx, joined, timed_out):
        self.log.append(
            {
                "event": "join",
                "joined": joined,
                "timed_out": timed_out,
                "time": _time.time(),
            }
        )

    async def on_stream_item(self, ctx, item, result, error):
        self.log.append(
            {
                "event": "stream_item",
                "item": item[:200] if item else "",
                "result_len": len(result) if result else 0,
                "error": str(error) if error else None,
                "time": _time.time(),
            }
        )


class TopologyLogMiddleware:
    """Observability middleware for topology events.

    Captures structured logs for loop iterations, fanout start/complete,
    route selections, fallback attempts, and timeouts.
    Access via the ``log`` attribute.
    """

    def __init__(self) -> None:
        self.log: list[dict] = []

    async def on_loop_iteration(self, ctx, loop_name, iteration):
        self.log.append(
            {
                "event": "loop_iteration",
                "loop": loop_name,
                "iteration": iteration,
                "time": _time.time(),
            }
        )
        return None

    async def on_fanout_start(self, ctx, fanout_name, branch_names):
        self.log.append(
            {
                "event": "fanout_start",
                "fanout": fanout_name,
                "branches": list(branch_names),
                "time": _time.time(),
            }
        )

    async def on_fanout_complete(self, ctx, fanout_name, branch_names):
        self.log.append(
            {
                "event": "fanout_complete",
                "fanout": fanout_name,
                "branches": list(branch_names),
                "time": _time.time(),
            }
        )

    async def on_route_selected(self, ctx, route_name, selected_agent):
        self.log.append(
            {
                "event": "route_selected",
                "route": route_name,
                "selected": selected_agent,
                "time": _time.time(),
            }
        )

    async def on_fallback_attempt(self, ctx, fallback_name, agent_name, attempt, error):
        self.log.append(
            {
                "event": "fallback_attempt",
                "fallback": fallback_name,
                "agent": agent_name,
                "attempt": attempt,
                "error": str(error) if error else None,
                "time": _time.time(),
            }
        )

    async def on_timeout(self, ctx, timeout_name, seconds, timed_out):
        self.log.append(
            {
                "event": "timeout",
                "timeout": timeout_name,
                "seconds": seconds,
                "timed_out": timed_out,
                "time": _time.time(),
            }
        )


class LatencyMiddleware:
    """Per-agent latency tracking using TraceContext for start timestamps.

    Access via the ``latencies`` dict: ``{agent_name: [durations_in_seconds]}``.
    """

    def __init__(self) -> None:
        self.latencies: dict[str, list[float]] = {}

    async def before_agent(self, ctx, agent_name):
        if isinstance(ctx, TraceContext):
            ctx[f"_latency_{agent_name}"] = _time.monotonic()
        return None

    async def after_agent(self, ctx, agent_name):
        if isinstance(ctx, TraceContext):
            start = ctx.get(f"_latency_{agent_name}")
            if start is not None:
                duration = _time.monotonic() - start
                self.latencies.setdefault(agent_name, []).append(duration)
        return None


class CostTracker:
    """Token usage tracking via after_model.

    Reads ``response.usage_metadata`` fields. Accumulates totals.

    Access via ``total_input_tokens``, ``total_output_tokens``, ``calls``.
    """

    def __init__(self) -> None:
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.calls: int = 0

    async def after_model(self, ctx, response):
        self.calls += 1
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            self.total_input_tokens += getattr(usage, "prompt_token_count", 0) or 0
            self.total_output_tokens += getattr(usage, "candidates_token_count", 0) or 0
        return None


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreakerMiddleware:
    """Trips open after N consecutive model errors, auto-resets after cooldown."""

    def __init__(self, threshold: int = 5, reset_after: float = 60):
        self._threshold = threshold
        self._reset_after = reset_after
        self._failures: dict[str, int] = {}
        self._tripped_at: dict[str, float] = {}

    async def before_model(self, ctx: Any, request: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        if name in self._tripped_at:
            elapsed = _time.monotonic() - self._tripped_at[name]
            if elapsed < self._reset_after:
                raise RuntimeError(f"Circuit open for agent '{name}' — {self._reset_after - elapsed:.0f}s until reset")
            del self._tripped_at[name]
            self._failures[name] = 0
        return None

    async def after_model(self, ctx: Any, request: Any, response: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        self._failures[name] = 0
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        self._failures[name] = self._failures.get(name, 0) + 1
        if self._failures[name] >= self._threshold:
            self._tripped_at[name] = _time.monotonic()
        return None


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


class TimeoutMiddleware:
    """Per-agent execution timeout."""

    def __init__(self, seconds: float = 30):
        self._seconds = seconds
        self._deadlines: dict[str, float] = {}

    async def before_agent(self, ctx: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        self._deadlines[name] = _time.monotonic() + self._seconds
        return None

    async def before_model(self, ctx: Any, request: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        deadline = self._deadlines.get(name)
        if deadline and _time.monotonic() > deadline:
            raise TimeoutError(f"Agent '{name}' exceeded {self._seconds}s timeout")
        return None


# ---------------------------------------------------------------------------
# Model cache
# ---------------------------------------------------------------------------


class ModelCacheMiddleware:
    """Caches LLM responses keyed by request content."""

    def __init__(self, ttl: float = 300, key_fn: Any = None):
        self._ttl = ttl
        self._key_fn = key_fn or (lambda req: str(req))
        self._cache: dict[str, tuple[Any, float]] = {}

    async def before_model(self, ctx: Any, request: Any) -> Any:
        key = self._key_fn(request)
        if key in self._cache:
            result, ts = self._cache[key]
            if _time.monotonic() - ts < self._ttl:
                return result
        return None

    async def after_model(self, ctx: Any, request: Any, response: Any) -> Any:
        key = self._key_fn(request)
        self._cache[key] = (response, _time.monotonic())
        return None


# ---------------------------------------------------------------------------
# Fallback model
# ---------------------------------------------------------------------------


class FallbackModelMiddleware:
    """Auto-downgrade to fallback model on primary model failure."""

    def __init__(self, fallback_model: str):
        self._fallback = fallback_model

    async def on_model_error(self, ctx: Any, request: Any, error: Any) -> Any:
        if hasattr(request, "model"):
            request.model = self._fallback
        return None


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


class DedupMiddleware:
    """Suppress duplicate model calls within a sliding window."""

    def __init__(self, window: int = 10):
        self._window = window
        self._recent: list[str] = []

    async def before_model(self, ctx: Any, request: Any) -> Any:
        key = str(request)
        if key in self._recent:
            return None
        self._recent.append(key)
        if len(self._recent) > self._window:
            self._recent = self._recent[-self._window :]
        return None


# ---------------------------------------------------------------------------
# Sampled middleware wrapper
# ---------------------------------------------------------------------------


class _SampledMiddleware:
    """Probabilistic middleware wrapper — fires inner middleware only N% of the time."""

    def __init__(self, rate: float, inner: Any):
        self._rate = rate
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        import random

        inner_attr = getattr(self._inner, name, None)
        if inner_attr is None or not callable(inner_attr):
            raise AttributeError(name)

        async def _sampled(*args: Any, **kwargs: Any) -> Any:
            if random.random() < self._rate:
                return await inner_attr(*args, **kwargs)  # type: ignore[reportGeneralTypeIssues]
            return None

        return _sampled


# ---------------------------------------------------------------------------
# Trace (OpenTelemetry)
# ---------------------------------------------------------------------------


class TraceMiddleware:
    """OpenTelemetry span export. Graceful no-op if opentelemetry not installed."""

    def __init__(self, exporter: Any = None):
        self._tracer = None
        self._exporter = exporter
        self._spans: dict[str, Any] = {}
        try:
            from opentelemetry import trace

            self._tracer = trace.get_tracer("adk-fluent")
        except ImportError:
            _logging.getLogger(__name__).debug("opentelemetry not installed — M.trace() is a no-op")

    async def before_agent(self, ctx: Any) -> Any:
        if self._tracer:
            name = getattr(ctx, "agent_name", "unknown")
            self._spans[name] = self._tracer.start_span(f"agent:{name}")
        return None

    async def after_agent(self, ctx: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        span = self._spans.pop(name, None)
        if span:
            span.end()
        return None


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class MetricsMiddleware:
    """Metrics collection. Graceful no-op if no collector provided."""

    def __init__(self, collector: Any = None):
        self._collector = collector
        self._counts: dict[str, int] = {}

    async def after_agent(self, ctx: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        self._counts[name] = self._counts.get(name, 0) + 1
        if self._collector and hasattr(self._collector, "increment"):
            self._collector.increment(f"agent.{name}.calls")
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        if self._collector and hasattr(self._collector, "increment"):
            self._collector.increment(f"agent.{name}.errors")
        return None
