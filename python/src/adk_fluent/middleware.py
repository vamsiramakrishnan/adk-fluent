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

from cachetools import LRUCache as _LRUCache
from cachetools import TTLCache as _TTLCache
from google.adk.plugins.base_plugin import BasePlugin
from pybreaker import CircuitBreaker as _CircuitBreaker
from pybreaker import CircuitBreakerError as _CircuitBreakerError
from tenacity import wait_exponential_jitter as _wait_exponential_jitter

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
    "RateLimitMiddleware",
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
    # A2A middleware
    "A2ARetryMiddleware",
    "A2ACircuitBreakerMiddleware",
    "A2ACircuitOpenError",
    "A2ATimeoutMiddleware",
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


@dataclass(frozen=True, slots=True)
class DispatchDirective:
    """Returned by ``on_dispatch`` to control dispatch behavior.

    - ``cancel=True``: skip this dispatch entirely.
    - ``inject_state``: merge keys into session state before dispatch.

    Returning ``None`` from ``on_dispatch`` proceeds normally (v1 compat).
    """

    cancel: bool = False
    inject_state: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
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

    # All hook names that _MiddlewarePlugin dispatches. Used at construction
    # time to precompute a hook table, eliminating per-call getattr probing.
    _ALL_HOOK_NAMES: tuple[str, ...] = (
        # Runner lifecycle
        "on_user_message",
        "before_run",
        "after_run",
        "on_event",
        # Agent lifecycle (scoped)
        "before_agent",
        "after_agent",
        # Model lifecycle (scoped)
        "before_model",
        "after_model",
        "on_model_error",
        # Tool lifecycle (scoped)
        "before_tool",
        "after_tool",
        "on_tool_error",
        # Dispatch/Join
        "on_dispatch",
        "on_task_complete",
        "on_task_error",
        "on_join",
        # Topology
        "on_loop_iteration",
        "on_fanout_start",
        "on_fanout_complete",
        "on_route_selected",
        "on_fallback_attempt",
        "on_timeout",
        # Stream lifecycle
        "on_stream_item",
        "on_stream_start",
        "on_stream_end",
        "on_backpressure",
        # Cleanup
        "close",
    )

    def __init__(self, name: str, stack: list) -> None:
        super().__init__(name=name)
        self._stack = list(stack)
        # Precompute hook dispatch table:
        #   hook_name -> (global_entries, scoped_entries)
        # where each entry is ``(mw, bound_fn)``.
        #
        # This eliminates per-call ``getattr(mw, method_name, None)`` lookups,
        # which on hot paths (before_model/after_model/before_tool per turn)
        # dominate middleware dispatch cost. The table is built once at
        # plugin-construction time; hooks not implemented by any middleware
        # become a single ``dict.get()`` miss at dispatch.
        #
        # Wave 4c: partition each hook into (global, scoped) buckets at init
        # so the hot runtime loop can skip the ``_agent_matches`` filter for
        # global middlewares — the common case. Scoped middlewares live in
        # their own tuple and only run through the filter when present.
        #
        # Also resolves ``_ConditionalMiddleware.__getattr__`` eagerly — it
        # creates a new ``_guarded`` closure on every access, so caching the
        # resolved bound fn is itself a secondary win on conditional
        # middleware.
        hook_table: dict[
            str,
            tuple[tuple[tuple[Any, Callable], ...], tuple[tuple[Any, Callable], ...]],
        ] = {}
        for method_name in self._ALL_HOOK_NAMES:
            is_scoped_hook = method_name in _SCOPED_HOOKS
            global_entries: list[tuple[Any, Callable]] = []
            scoped_entries: list[tuple[Any, Callable]] = []
            for mw in self._stack:
                fn = getattr(mw, method_name, None)
                if fn is None:
                    continue
                # Only scoped-hook entries can land in the scoped bucket. An
                # unscoped hook (e.g. on_start) always lives in ``global``.
                if is_scoped_hook and getattr(mw, "agents", None) is not None:
                    scoped_entries.append((mw, fn))
                else:
                    global_entries.append((mw, fn))
            if global_entries or scoped_entries:
                hook_table[method_name] = (tuple(global_entries), tuple(scoped_entries))
        self._hook_table: dict[
            str,
            tuple[tuple[tuple[Any, Callable], ...], tuple[tuple[Any, Callable], ...]],
        ] = hook_table

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

        Uses the precomputed hook table — no per-call getattr probing.
        Wave 4c: hook table is partitioned into ``(global, scoped)`` buckets
        so the global bucket skips the ``_agent_matches`` filter entirely.
        """
        buckets = self._hook_table.get(method_name)
        if buckets is None:
            return None
        global_entries, scoped_entries = buckets
        # Phase 1: global middlewares — no per-agent filter.
        for mw, fn in global_entries:
            try:
                result = await fn(*args)
                if result is not None:
                    return result
            except Exception as exc:
                _log.warning("Middleware %s.%s raised: %s", type(mw).__name__, method_name, exc)
                await self._fire_middleware_error(mw, method_name, exc)
        # Phase 2: scoped middlewares — apply agent filter.
        if scoped_entries:
            for mw, fn in scoped_entries:
                if agent_name is not None and not _agent_matches(mw, agent_name):
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
        Uses the precomputed hook table — no per-call getattr probing.
        Wave 4c: partitioned global/scoped buckets — see ``_run_stack``.
        """
        buckets = self._hook_table.get(method_name)
        if buckets is None:
            return
        global_entries, scoped_entries = buckets
        for mw, fn in global_entries:
            try:
                await fn(*args)
            except Exception as exc:
                _log.warning("Middleware %s.%s raised: %s", type(mw).__name__, method_name, exc)
                await self._fire_middleware_error(mw, method_name, exc)
        if scoped_entries:
            for mw, fn in scoped_entries:
                if agent_name is not None and not _agent_matches(mw, agent_name):
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

    Returns None on error to let ADK retry. Between retries, this middleware
    sleeps for a jittered exponential backoff delay computed by
    ``tenacity.wait_exponential_jitter`` — the de-facto standard retry library.
    Jitter avoids thundering-herd synchronization of retries against upstream
    LLM / tool APIs when many workers fail at once.

    The hook-based middleware design cannot *invoke* the retry itself — ADK is
    responsible for re-issuing the failed call — so this class is intentionally
    limited to computing and applying the inter-attempt wait.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_base: float = 1.0,
        *,
        max_backoff: float = 60.0,
        jitter: float = 1.0,
    ):
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self._max_backoff = max_backoff
        # tenacity computes: min(initial * 2**(attempt-1), max) + uniform(0, jitter)
        self._wait = _wait_exponential_jitter(
            initial=backoff_base,
            max=max_backoff,
            jitter=jitter,
        )
        self._attempts: dict[str, int] = {}

    def _compute_delay(self, attempt_number: int) -> float:
        """Delegate delay computation to tenacity's jittered exponential strategy."""
        # tenacity's wait strategies take a RetryCallState but only read attempt_number.
        # We construct a minimal duck-typed shim to avoid the full RetryCallState setup.
        state = _TenacityRetryState(attempt_number=attempt_number)
        return float(self._wait(state))  # type: ignore[arg-type]

    async def on_model_error(self, ctx, request, error):
        key = f"model_{id(request)}"
        self._attempts[key] = self._attempts.get(key, 0) + 1
        if self._attempts[key] < self.max_attempts:
            delay = self._compute_delay(self._attempts[key])
            if delay > 0:
                await _asyncio.sleep(delay)
        return None

    async def on_tool_error(self, ctx, tool_name, args, error):
        key = f"tool_{tool_name}"
        self._attempts[key] = self._attempts.get(key, 0) + 1
        if self._attempts[key] < self.max_attempts:
            delay = self._compute_delay(self._attempts[key])
            if delay > 0:
                await _asyncio.sleep(delay)
        return None


@dataclass
class _TenacityRetryState:
    """Minimal duck-type of tenacity.RetryCallState for wait strategies.

    Tenacity's ``wait_*`` strategies only read ``attempt_number`` from the
    state object; we avoid constructing a full RetryCallState because that
    requires a live ``Retrying`` instance and real function call context.
    """

    attempt_number: int


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
    """Trips open after N consecutive model errors, auto-resets after cooldown.

    Backed by ``pybreaker.CircuitBreaker``: a thread-safe, well-tested state
    machine with CLOSED → OPEN → HALF_OPEN transitions. Each agent gets its
    own breaker instance keyed by agent name.
    """

    def __init__(self, threshold: int = 5, reset_after: float = 60):
        self._threshold = threshold
        self._reset_after = reset_after
        self._breakers: dict[str, _CircuitBreaker] = {}

    def _get_breaker(self, name: str) -> _CircuitBreaker:
        breaker = self._breakers.get(name)
        if breaker is None:
            breaker = _CircuitBreaker(
                fail_max=self._threshold,
                reset_timeout=self._reset_after,
                name=f"agent:{name}",
            )
            self._breakers[name] = breaker
        return breaker

    async def before_model(self, ctx: Any, request: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        breaker = self._get_breaker(name)
        # Probe the breaker: calling() transitions OPEN → HALF_OPEN after
        # reset_timeout and raises CircuitBreakerError while still open.
        try:
            with breaker.calling():
                pass
        except _CircuitBreakerError as exc:
            raise RuntimeError(f"Circuit open for agent '{name}': {exc}") from exc
        return None

    async def after_model(self, ctx: Any, request: Any, response: Any) -> Any:
        # A successful call in closed / half-open state closes the breaker.
        # Driving the breaker via .calling() with no-op body records the
        # success and resets fail_counter.
        name = getattr(ctx, "agent_name", "unknown")
        breaker = self._get_breaker(name)
        with _contextlib.suppress(_CircuitBreakerError), breaker.calling():
            pass
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        breaker = self._get_breaker(name)
        # Feed the breaker a synthetic failure matching the real error so it
        # increments fail_counter and trips when the threshold is reached.
        try:
            with breaker.calling():
                raise error if isinstance(error, BaseException) else RuntimeError(str(error))
        except _CircuitBreakerError:
            # Circuit opened / already open — absorbed, re-probed on next call.
            pass
        except BaseException:
            # Expected: the synthetic failure re-raised through pybreaker.
            pass
        return None


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


class TimeoutMiddleware:
    """Per-agent execution timeout.

    Deadlines are cleaned up after each agent invocation to prevent
    memory growth in long-running applications.
    """

    def __init__(self, seconds: float = 30):
        self._seconds = seconds
        self._deadlines: dict[str, float] = {}

    async def before_agent(self, ctx: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        self._deadlines[name] = _time.monotonic() + self._seconds
        return None

    async def after_agent(self, ctx: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        self._deadlines.pop(name, None)
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
    """Caches LLM responses keyed by request content.

    Backed by ``cachetools.TTLCache`` which evicts expired entries lazily
    *and* enforces a max-size bound — preventing the unbounded-dict memory
    leak of the previous hand-rolled implementation.
    """

    def __init__(self, ttl: float = 300, key_fn: Any = None, *, max_size: int = 1024):
        self._ttl = ttl
        self._key_fn = key_fn or (lambda req: str(req))
        self._cache: _TTLCache[str, Any] = _TTLCache(maxsize=max_size, ttl=ttl)

    async def before_model(self, ctx: Any, request: Any) -> Any:
        key = self._key_fn(request)
        # TTLCache raises KeyError on expired / missing; __contains__ handles
        # expiry checking for us.
        if key in self._cache:
            return self._cache[key]
        return None

    async def after_model(self, ctx: Any, request: Any, response: Any) -> Any:
        key = self._key_fn(request)
        self._cache[key] = response
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
    """Suppress duplicate model calls within a sliding window.

    Backed by ``cachetools.LRUCache`` keyed on a stable hash of the
    stringified request. O(1) lookup (vs. O(n) list scan previously) and
    automatic eviction once the window size is exceeded.
    """

    def __init__(self, window: int = 10):
        self._window = window
        # value type is bool — we only care about key membership.
        self._seen: _LRUCache[int, bool] = _LRUCache(maxsize=max(1, window))

    async def before_model(self, ctx: Any, request: Any) -> Any:
        key = hash(str(request))
        if key in self._seen:
            return None
        self._seen[key] = True
        return None


# ---------------------------------------------------------------------------
# Sampled middleware wrapper
# ---------------------------------------------------------------------------


class RateLimitMiddleware:
    """Token-bucket rate limiter backed by ``aiolimiter``.

    Blocks inside ``before_model`` until a token is available, so downstream
    model calls are throttled to ``rate`` calls per ``time_period`` seconds.
    Unlike :class:`_SampledMiddleware` (which is probabilistic and can drop
    calls), this middleware delays calls to enforce a true rate ceiling.

    Requires ``pip install adk-fluent[ratelimit]`` (i.e. ``aiolimiter``).
    """

    def __init__(self, rate: float, time_period: float = 1.0):
        try:
            from aiolimiter import AsyncLimiter  # type: ignore[reportMissingImports]
        except ImportError as exc:
            msg = (
                "aiolimiter is required for M.rate_limit(). "
                "Install with: pip install adk-fluent[ratelimit] "
                "(or pip install aiolimiter)."
            )
            raise ImportError(msg) from exc
        self._rate = rate
        self._time_period = time_period
        self._limiter = AsyncLimiter(max_rate=rate, time_period=time_period)

    async def before_model(self, ctx: Any, request: Any) -> Any:
        # Acquire blocks until a token is available from the leaky bucket.
        await self._limiter.acquire()
        return None


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


# ======================================================================
# A2A-specific middleware
# ======================================================================


class A2ARetryMiddleware:
    """Retry middleware specialized for A2A remote agent failures.

    Unlike the generic ``RetryMiddleware`` which retries LLM model errors,
    this middleware handles A2A-specific failure modes:

    - HTTP transport errors (connection refused, timeout, 5xx)
    - A2A task state FAILED / REJECTED
    - Network-level transient failures

    Uses exponential backoff with jitter. Retries are scoped to agents
    whose names match the ``agents`` filter (default: all agents).

    Usage::

        pipeline.middleware(M.a2a_retry(max_attempts=3, backoff=2.0))
        pipeline.middleware(M.scope("remote_*", M.a2a_retry()))
    """

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_base: float = 2.0,
        *,
        max_backoff: float = 60.0,
        jitter: float = 2.0,
        agents: str | tuple[str, ...] | None = None,
        on_retry: Callable | None = None,
    ):
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.agents = agents
        self._on_retry = on_retry
        # Jittered exponential backoff via tenacity. Jitter is particularly
        # important for A2A because remote agents often fail in bursts
        # (network hiccup, 5xx storm) and naive retries would synchronize.
        self._wait = _wait_exponential_jitter(
            initial=backoff_base,
            max=max_backoff,
            jitter=jitter,
        )
        self._attempts: dict[str, int] = {}
        self._log = _logging.getLogger(f"{__name__}.A2ARetryMiddleware")

    def _compute_delay(self, attempt_number: int) -> float:
        return float(self._wait(_TenacityRetryState(attempt_number=attempt_number)))  # type: ignore[arg-type]

    def _should_retry(self, error: Exception) -> bool:
        """Determine if an error is retryable (A2A-specific heuristics)."""
        error_str = str(error).lower()
        # Connection errors
        if any(term in error_str for term in ("connection refused", "connection reset", "timed out", "timeout")):
            return True
        # HTTP 5xx errors
        if any(f"{code}" in error_str for code in range(500, 600)):
            return True
        # A2A task states that are retryable
        return any(term in error_str for term in ("task_state_failed", "failed", "rejected"))

    async def on_tool_error(self, ctx: Any, tool_name: str, args: dict, error: Exception) -> dict | None:
        """Retry on A2A agent tool failures (AgentTool wrapping RemoteA2aAgent)."""
        if not self._should_retry(error):
            return None
        self._attempts[tool_name] = self._attempts.get(tool_name, 0) + 1
        attempt = self._attempts[tool_name]
        if attempt < self.max_attempts:
            delay = self._compute_delay(attempt)
            self._log.info("A2A retry %d/%d for %s in %.1fs", attempt, self.max_attempts, tool_name, delay)
            if self._on_retry:
                await self._on_retry(ctx, tool_name, attempt, error)
            await _asyncio.sleep(delay)
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Exception) -> Any:
        """Retry on model errors that may be A2A-related."""
        if not self._should_retry(error):
            return None
        key = f"model_{id(request)}"
        self._attempts[key] = self._attempts.get(key, 0) + 1
        attempt = self._attempts[key]
        if attempt < self.max_attempts:
            delay = self._compute_delay(attempt)
            self._log.info("A2A model retry %d/%d in %.1fs", attempt, self.max_attempts, delay)
            await _asyncio.sleep(delay)
        return None


class A2ACircuitBreakerMiddleware:
    """Circuit breaker for A2A remote agents.

    Tracks failures per remote agent endpoint. When consecutive failures
    exceed the threshold, the circuit opens and subsequent calls fail fast
    with ``A2ACircuitOpenError`` until the reset period elapses.

    States:
        CLOSED  → normal operation, failures counted
        OPEN    → calls rejected immediately
        HALF_OPEN → one probe call allowed to test recovery

    Usage::

        pipeline.middleware(M.a2a_circuit_breaker(threshold=5, reset_after=60))
    """

    def __init__(
        self,
        threshold: int = 5,
        reset_after: float = 60,
        *,
        agents: str | tuple[str, ...] | None = None,
        on_open: Callable | None = None,
        on_close: Callable | None = None,
    ):
        self._threshold = threshold
        self._reset_after = reset_after
        self.agents = agents
        self._on_open = on_open
        self._on_close = on_close
        # Per-endpoint pybreaker instances. pybreaker handles half-open
        # probe semantics natively (success in half-open → closed,
        # failure in half-open → re-open).
        self._breakers: dict[str, _CircuitBreaker] = {}
        self._open_notified: set[str] = set()
        self._log = _logging.getLogger(f"{__name__}.A2ACircuitBreakerMiddleware")

    def _get_breaker(self, key: str) -> _CircuitBreaker:
        breaker = self._breakers.get(key)
        if breaker is None:
            breaker = _CircuitBreaker(
                fail_max=self._threshold,
                reset_timeout=self._reset_after,
                name=f"a2a:{key}",
            )
            self._breakers[key] = breaker
        return breaker

    @property
    def open_circuits(self) -> dict[str, str]:
        """Return currently open / half-open circuits keyed by name → state."""
        return {
            name: breaker.current_state for name, breaker in self._breakers.items() if breaker.current_state != "closed"
        }

    async def before_agent(self, ctx: Any, agent_name: str) -> Any:
        """Check circuit state before agent execution."""
        breaker = self._get_breaker(agent_name)
        try:
            with breaker.calling():
                pass
        except _CircuitBreakerError as exc:
            raise A2ACircuitOpenError(f"A2A circuit open for '{agent_name}': {exc}") from exc
        return None

    async def after_agent(self, ctx: Any, agent_name: str) -> Any:
        """Reset failure count on success (via pybreaker's state machine)."""
        breaker = self._get_breaker(agent_name)
        with _contextlib.suppress(_CircuitBreakerError), breaker.calling():
            pass
        if agent_name in self._open_notified and breaker.current_state == "closed":
            self._open_notified.discard(agent_name)
            self._log.info("A2A circuit closed for '%s'", agent_name)
            if self._on_close:
                await self._on_close(ctx, agent_name)
        return None

    async def on_tool_error(self, ctx: Any, tool_name: str, args: dict, error: Exception) -> dict | None:
        """Track failures for circuit breaker logic."""
        breaker = self._get_breaker(tool_name)
        previously_closed = breaker.current_state == "closed"
        # Feed the real error through pybreaker so it bumps the counter
        # (and trips when the threshold is reached).
        try:
            with breaker.calling():
                raise error if isinstance(error, BaseException) else RuntimeError(str(error))
        except _CircuitBreakerError:
            pass
        except BaseException:
            pass
        if previously_closed and breaker.current_state == "open" and tool_name not in self._open_notified:
            self._open_notified.add(tool_name)
            self._log.warning("A2A circuit opened for '%s' after %d failures", tool_name, breaker.fail_counter)
            if self._on_open:
                await self._on_open(ctx, tool_name)
        return None


class A2ACircuitOpenError(RuntimeError):
    """Raised when an A2A circuit breaker is open."""


class A2ATimeoutMiddleware:
    """Per-delegation timeout for A2A remote agent calls.

    Unlike the generic ``TimeoutMiddleware`` which tracks LLM model call
    deadlines, this middleware enforces wall-clock time limits on entire
    agent invocations, which is critical for remote A2A calls that may
    involve network latency + remote LLM processing.

    Usage::

        pipeline.middleware(M.a2a_timeout(seconds=30))
        pipeline.middleware(M.scope("slow_remote", M.a2a_timeout(120)))
    """

    def __init__(
        self,
        seconds: float = 30,
        *,
        agents: str | tuple[str, ...] | None = None,
        on_timeout: Callable | None = None,
    ):
        self._seconds = seconds
        self.agents = agents
        self._on_timeout = on_timeout
        self._deadlines: dict[str, float] = {}
        self._log = _logging.getLogger(f"{__name__}.A2ATimeoutMiddleware")

    async def before_agent(self, ctx: Any, agent_name: str) -> Any:
        """Set deadline before agent execution."""
        self._deadlines[agent_name] = _time.monotonic() + self._seconds
        return None

    async def after_agent(self, ctx: Any, agent_name: str) -> Any:
        """Clean up deadline after agent execution."""
        deadline = self._deadlines.pop(agent_name, None)
        if deadline and _time.monotonic() > deadline:
            self._log.warning("A2A agent '%s' exceeded %ss timeout", agent_name, self._seconds)
            if self._on_timeout:
                await self._on_timeout(ctx, agent_name, self._seconds)
        return None

    async def before_model(self, ctx: Any, request: Any) -> Any:
        """Check deadline before each model call within the agent."""
        name = getattr(ctx, "agent_name", "unknown")
        deadline = self._deadlines.get(name)
        if deadline and _time.monotonic() > deadline:
            raise TimeoutError(f"A2A agent '{name}' exceeded {self._seconds}s timeout")
        return None

    async def before_tool(self, ctx: Any, tool_name: str, args: dict) -> dict | None:
        """Check deadline before each tool call within the agent."""
        name = getattr(ctx, "agent_name", "unknown")
        deadline = self._deadlines.get(name)
        if deadline and _time.monotonic() > deadline:
            raise TimeoutError(f"A2A agent '{name}' exceeded {self._seconds}s timeout")
        return None
