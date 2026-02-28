"""Runtime agent primitives for adk-fluent.

Custom BaseAgent subclasses that have no ADK counterpart — they are
adk-fluent inventions compiled to real agents by the ADK backend.

Extracted from ``_base.py`` to keep it focused on ``BuilderBase``.
"""

from __future__ import annotations

import asyncio as _asyncio
import types
from collections.abc import AsyncGenerator, Callable
from contextvars import ContextVar
from typing import Any, Protocol, runtime_checkable

from google.adk.agents.base_agent import BaseAgent
from google.adk.events.event import Event

from adk_fluent._enums import ExecutionMode

__all__ = [
    "FnAgent",
    "TapAgent",
    "CaptureAgent",
    "FallbackAgent",
    "MapOverAgent",
    "TimeoutAgent",
    "GateAgent",
    "RaceAgent",
    "DispatchAgent",
    "JoinAgent",
    "_LoopHookAgent",
    "_FanOutHookAgent",
    "get_execution_mode",
    "_dispatch_tasks",
    "_global_task_budget",
    "_middleware_dispatch_hooks",
    "_topology_hooks",
    "_execution_mode",
    "_DEFAULT_MAX_TASKS",
]

# ---------------------------------------------------------------------------
# Dispatch/Join: per-invocation task tracking via ContextVar
# ---------------------------------------------------------------------------
# ContextVar auto-scopes to the execution context (per runner invocation).
# asyncio.create_task() propagates contextvars to child tasks, so nested
# dispatch chains each get their own scope (copy-on-write semantics).
_dispatch_tasks: ContextVar[dict[str, _asyncio.Task] | None] = ContextVar("_dispatch_tasks", default=None)
# Global task budget: shared semaphore across ALL dispatch levels to prevent
# exponential task explosion in deep dispatch chains (dispatch->dispatch->dispatch).
_global_task_budget: ContextVar[_asyncio.Semaphore | None] = ContextVar("_global_task_budget", default=None)


# ---------------------------------------------------------------------------
# Typed protocol for middleware dispatch hooks (v1 compat)
# ---------------------------------------------------------------------------


@runtime_checkable
class DispatchHooks(Protocol):
    """Protocol for middleware dispatch/join lifecycle hooks.

    Deprecated: use ``TopologyHooks`` from ``middleware.py`` instead.
    Kept for backward compat -- ``_middleware_dispatch_hooks`` still works.
    """

    async def on_dispatch(self, ctx: Any, task_name: str, agent_name: str) -> None: ...
    async def on_task_complete(self, ctx: Any, task_name: str, result: str) -> None: ...
    async def on_task_error(self, ctx: Any, task_name: str, error: Exception) -> None: ...
    async def on_join(self, ctx: Any, joined: list[str], timed_out: list[str]) -> None: ...


# Deprecated: use _topology_hooks instead.  Kept as backward compat alias.
_middleware_dispatch_hooks: ContextVar[DispatchHooks | None] = ContextVar("_middleware_dispatch_hooks", default=None)

# Canonical topology hooks ContextVar -- set by _MiddlewarePlugin.
# Import from middleware.py at module level would create circular import,
# so we define our own and middleware.py also defines one. The _MiddlewarePlugin
# sets BOTH ContextVars in before_run_callback.
_topology_hooks: ContextVar[Any | None] = ContextVar("_topology_hooks", default=None)

# Execution mode: "pipeline" (default), "dispatched", or "stream".
_execution_mode: ContextVar[str] = ContextVar("_execution_mode", default="pipeline")


def get_execution_mode() -> ExecutionMode:
    """Return the current execution mode.

    Returns one of :attr:`ExecutionMode.PIPELINE`,
    :attr:`ExecutionMode.DISPATCHED`, or :attr:`ExecutionMode.STREAM`.
    """
    return ExecutionMode(_execution_mode.get("pipeline"))


def _get_topology_hooks() -> Any | None:
    """Get topology hooks, preferring _topology_hooks over deprecated alias."""
    hooks = _topology_hooks.get()
    if hooks is not None:
        return hooks
    return _middleware_dispatch_hooks.get()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MAX_TASKS = 50
"""Default maximum concurrent dispatch tasks across all levels."""

# Deprecated alias -- will be removed in a future release.
_DEFAULT_TASK_BUDGET = _DEFAULT_MAX_TASKS


# ======================================================================
# Runtime agent classes
# ======================================================================


class FnAgent(BaseAgent):
    """Zero-cost function agent. No LLM call."""

    _fn_ref: Callable

    def __init__(self, *, fn: Callable, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_fn_ref", fn)

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        from adk_fluent._transforms import _SCOPE_PREFIXES, StateDelta, StateReplacement

        result = self._fn_ref(dict(ctx.session.state))
        if isinstance(result, StateReplacement):
            # Only affect session-scoped (unprefixed) keys
            current_session_keys = {k for k in ctx.session.state if not k.startswith(_SCOPE_PREFIXES)}
            new_keys = set(result.new_state.keys())
            for k, v in result.new_state.items():
                ctx.session.state[k] = v
            for k in current_session_keys - new_keys:
                ctx.session.state[k] = None
        elif isinstance(result, StateDelta):
            for k, v in result.updates.items():
                ctx.session.state[k] = v
        elif isinstance(result, dict):
            for k, v in result.items():
                ctx.session.state[k] = v
        return
        yield  # noqa: RET504 -- required for async generator protocol


class FallbackAgent(BaseAgent):
    """Tries each child agent in order. First success wins."""

    async def _run_async_impl(self, ctx):
        last_exc = None
        for attempt, child in enumerate(self.sub_agents):
            # Fire topology hook
            hooks = _get_topology_hooks()
            if hooks:
                fn = getattr(hooks, "on_fallback_attempt", None)
                if fn is not None:
                    await fn(ctx, self.name, child.name, attempt, last_exc)

            try:
                async for event in child.run_async(ctx):
                    yield event
                return  # success -- stop trying
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            raise last_exc


class TapAgent(BaseAgent):
    """Zero-cost observation agent. No LLM call, no state mutation."""

    _fn_ref: Callable

    def __init__(self, *, fn: Callable, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_fn_ref", fn)

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        # Pass read-only view -- tap should never mutate state
        self._fn_ref(types.MappingProxyType(dict(ctx.session.state)))
        return
        yield  # noqa: RET504 -- required for async generator protocol


class CaptureAgent(BaseAgent):
    """Capture the most recent user message from session events into state."""

    _capture_key: str

    def __init__(self, *, key: str, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_capture_key", key)

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        for event in reversed(ctx.session.events):
            if getattr(event, "author", None) == "user":
                parts = getattr(getattr(event, "content", None), "parts", None) or []
                texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
                if texts:
                    ctx.session.state[self._capture_key] = "\n".join(texts)
                    break
        return
        yield  # noqa: RET504 -- required for async generator protocol


class MapOverAgent(BaseAgent):
    """Iterates sub-agent over each item in a state list."""

    _list_key: str
    _item_key: str
    _output_key: str

    def __init__(self, *, list_key: str, item_key: str, output_key: str, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_list_key", list_key)
        object.__setattr__(self, "_item_key", item_key)
        object.__setattr__(self, "_output_key", output_key)

    async def _run_async_impl(self, ctx):
        items = ctx.session.state.get(self._list_key, [])
        results = []
        for item in items:
            ctx.session.state[self._item_key] = item
            async for event in self.sub_agents[0].run_async(ctx):
                yield event
            # Collect result after sub-agent runs
            result_val = ctx.session.state.get(self._item_key, None)
            results.append(result_val)
        ctx.session.state[self._output_key] = results


class TimeoutAgent(BaseAgent):
    """Wraps a sub-agent with a time limit."""

    _seconds: float

    def __init__(self, *, seconds: float, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_seconds", seconds)

    async def _run_async_impl(self, ctx):
        import asyncio

        queue = asyncio.Queue()
        sentinel = object()

        async def _consume():
            async for event in self.sub_agents[0].run_async(ctx):
                await queue.put(event)
            await queue.put(sentinel)

        task = asyncio.create_task(_consume())
        try:
            deadline = asyncio.get_event_loop().time() + self._seconds
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"Agent '{self.sub_agents[0].name}' exceeded {self._seconds}s timeout")
                item = await asyncio.wait_for(queue.get(), timeout=remaining)
                if item is sentinel:
                    break
                yield item
        except TimeoutError:
            task.cancel()
            # Fire topology hook
            hooks = _get_topology_hooks()
            if hooks:
                fn = getattr(hooks, "on_timeout", None)
                if fn is not None:
                    await fn(ctx, self.name, self._seconds, True)
            raise
        else:
            # Completed without timeout -- fire hook with timed_out=False
            hooks = _get_topology_hooks()
            if hooks:
                fn = getattr(hooks, "on_timeout", None)
                if fn is not None:
                    await fn(ctx, self.name, self._seconds, False)
        finally:
            if not task.done():
                task.cancel()


class GateAgent(BaseAgent):
    """Human-in-the-loop approval gate."""

    _predicate: Callable
    _message: str
    _gate_key: str

    def __init__(self, *, predicate: Callable, message: str, gate_key: str, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_predicate", predicate)
        object.__setattr__(self, "_message", message)
        object.__setattr__(self, "_gate_key", gate_key)

    async def _run_async_impl(self, ctx):
        from google.adk.events.event import Event
        from google.adk.events.event_actions import EventActions
        from google.genai import types

        state = ctx.session.state
        approved_key = f"{self._gate_key}_approved"

        try:
            needs_gate = self._predicate(state)
        except (KeyError, TypeError, ValueError):
            needs_gate = False

        if not needs_gate:
            return  # Condition not met, proceed

        if state.get(approved_key):
            # Already approved, clear and proceed
            state[approved_key] = False
            state[self._gate_key] = False
            return

        # Need approval: set flag and escalate
        state[self._gate_key] = True
        state[f"{self._gate_key}_message"] = self._message
        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(role="model", parts=[types.Part(text=self._message)]),
            actions=EventActions(escalate=True),
        )


class RaceAgent(BaseAgent):
    """Runs sub-agents concurrently, keeps first to finish."""

    async def _run_async_impl(self, ctx):
        import asyncio

        async def _run_one(agent):
            events = []
            async for event in agent.run_async(ctx):
                events.append(event)
            return events

        tasks = {asyncio.create_task(_run_one(agent)): i for i, agent in enumerate(self.sub_agents)}

        try:
            done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
            # Cancel remaining
            for task in pending:
                task.cancel()

            # Yield events from the winner
            winner = done.pop()
            for event in winner.result():
                yield event
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()


# ======================================================================
# Topology Hook Agents (injected by backend during compilation)
# ======================================================================


class _LoopHookAgent(BaseAgent):
    """Zero-cost agent injected at the start of each loop iteration.

    Reads _topology_hooks ContextVar and fires on_loop_iteration.
    Tracks iteration count via a mutable dict (survives ADK state resets).
    If LoopDirective(break_loop=True) is returned, yields escalate event.
    """

    _loop_name: str
    _iteration_counter: dict[str, int]

    def __init__(self, *, loop_name: str, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_loop_name", loop_name)
        object.__setattr__(self, "_iteration_counter", {"n": 0})

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        from google.adk.events.event_actions import EventActions

        iteration = self._iteration_counter["n"]
        self._iteration_counter["n"] += 1

        hooks = _get_topology_hooks()
        if hooks:
            fn = getattr(hooks, "on_loop_iteration", None)
            if fn is not None:
                directive = await fn(ctx, self._loop_name, iteration)
                # Check for LoopDirective(break_loop=True)
                if directive is not None and getattr(directive, "break_loop", False):
                    yield Event(
                        invocation_id=ctx.invocation_id,
                        author=self.name,
                        branch=ctx.branch,
                        actions=EventActions(escalate=True),
                    )
                    return
        return
        yield  # noqa: RET504 -- required for async generator protocol


class _FanOutHookAgent(BaseAgent):
    """Zero-cost agent injected before/after parallel execution.

    Fires on_fanout_start or on_fanout_complete based on ``phase``.
    """

    _fanout_name: str
    _branch_names: list[str]
    _phase: str  # "start" or "complete"

    def __init__(self, *, fanout_name: str, branch_names: list[str], phase: str, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_fanout_name", fanout_name)
        object.__setattr__(self, "_branch_names", branch_names)
        object.__setattr__(self, "_phase", phase)

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        hooks = _get_topology_hooks()
        if hooks:
            if self._phase == "start":
                fn = getattr(hooks, "on_fanout_start", None)
            else:
                fn = getattr(hooks, "on_fanout_complete", None)
            if fn is not None:
                await fn(ctx, self._fanout_name, self._branch_names)
        return
        yield  # noqa: RET504 -- required for async generator protocol


# ======================================================================
# Dispatch/Join: fire-and-continue background execution
# ======================================================================


class DispatchAgent(BaseAgent):
    """Launches sub-agents as background tasks, returns immediately.

    Tasks are tracked via ContextVar so JoinAgent can await them later.
    A global task budget (asyncio.Semaphore) prevents exponential
    explosion in deep dispatch chains (dispatch->dispatch->dispatch).
    """

    _task_names: tuple[str, ...]
    _on_complete: Callable | None
    _on_error: Callable | None
    _stream_to: str | None
    _max_tasks: int | None

    def __init__(
        self,
        *,
        task_names: tuple[str, ...] = (),
        stream_to: str | None = None,
        max_tasks: int | None = None,
        on_complete: Callable | None = None,
        on_error: Callable | None = None,
        # Deprecated aliases -- accept but forward
        progress_key: str | None = None,
        task_budget: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        object.__setattr__(self, "_task_names", task_names)
        object.__setattr__(self, "_on_complete", on_complete)
        object.__setattr__(self, "_on_error", on_error)
        object.__setattr__(self, "_stream_to", stream_to or progress_key)
        object.__setattr__(self, "_max_tasks", max_tasks or task_budget)

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        import asyncio

        # Get or initialize per-invocation task registry
        tasks = _dispatch_tasks.get()
        if tasks is None:
            tasks = {}
            _dispatch_tasks.set(tasks)

        # Get or initialize global task budget (shared across dispatch depths)
        budget = _global_task_budget.get()
        if budget is None:
            limit = self._max_tasks or _DEFAULT_MAX_TASKS
            budget = asyncio.Semaphore(limit)
            _global_task_budget.set(budget)

        for i, child in enumerate(self.sub_agents):
            task_name = self._task_names[i] if i < len(self._task_names) else child.name

            # Fire on_dispatch topology hook (may return DispatchDirective)
            hooks = _get_topology_hooks()
            if hooks:
                fn = getattr(hooks, "on_dispatch", None)
                if fn is not None:
                    directive = await fn(ctx, task_name, child.name)
                    # Check for DispatchDirective
                    if directive is not None:
                        if getattr(directive, "cancel", False):
                            continue  # skip this dispatch
                        inject = getattr(directive, "inject_state", None)
                        if inject:
                            for k, v in inject.items():
                                ctx.session.state[k] = v

            # Capture loop vars
            _child = child
            _name = task_name
            _on_complete = self._on_complete
            _on_error = self._on_error
            _stream_to = self._stream_to

            async def _run_child(agent=_child, tname=_name, on_ok=_on_complete, on_err=_on_error, skey=_stream_to):
                _execution_mode.set("dispatched")
                await budget.acquire()
                try:
                    events = []
                    last_text = ""
                    async for event in agent.run_async(ctx):
                        events.append(event)
                        # Stream partial results if stream_to is set
                        if skey and event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.text:
                                    last_text = part.text
                                    ctx.session.state[skey] = last_text

                    # Store final result in state
                    if last_text:
                        results = ctx.session.state.get("_dispatch_results")
                        if results is None:
                            results = {}
                            ctx.session.state["_dispatch_results"] = results
                        results[tname] = last_text

                    # Update status
                    status = ctx.session.state.get("_dispatch_status")
                    if status and tname in status:
                        status[tname]["status"] = "completed"

                    if on_ok:
                        on_ok(tname, last_text)

                    # Fire middleware hook
                    mw_hooks = _get_topology_hooks()
                    if mw_hooks:
                        fn = getattr(mw_hooks, "on_task_complete", None)
                        if fn is not None:
                            await fn(ctx, tname, last_text)

                    return events
                except Exception as exc:
                    status = ctx.session.state.get("_dispatch_status")
                    if status and tname in status:
                        status[tname]["status"] = "error"
                        status[tname]["error"] = str(exc)
                    if on_err:
                        on_err(tname, exc)
                    # Fire middleware hook
                    mw_hooks = _get_topology_hooks()
                    if mw_hooks:
                        fn = getattr(mw_hooks, "on_task_error", None)
                        if fn is not None:
                            await fn(ctx, tname, exc)
                    raise
                finally:
                    budget.release()

            task = _asyncio.create_task(_run_child())
            tasks[task_name] = task

            # Serializable metadata in session state
            status = ctx.session.state.get("_dispatch_status")
            if status is None:
                status = {}
                ctx.session.state["_dispatch_status"] = status
            status[task_name] = {"status": "running", "agent": child.name}

        # Return immediately -- pipeline continues without waiting
        return
        yield  # noqa: RET504 -- required for async generator protocol


class JoinAgent(BaseAgent):
    """Blocks until dispatched tasks complete, yields their events.

    Supports selective join (by name), timeout, and status reporting
    via session state.
    """

    _target_names: tuple[str, ...] | None
    _timeout: float | None

    def __init__(
        self,
        *,
        target_names: tuple[str, ...] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        object.__setattr__(self, "_target_names", target_names)
        object.__setattr__(self, "_timeout", timeout)

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        import asyncio

        tasks = _dispatch_tasks.get()
        if not tasks:
            return
            yield  # noqa: RET504 -- required for async generator protocol

        # Select tasks to wait for
        if self._target_names:
            to_wait = {k: v for k, v in tasks.items() if k in self._target_names}
        else:
            to_wait = dict(tasks)

        if not to_wait:
            return
            yield  # noqa: RET504 -- required for async generator protocol

        # stdlib: asyncio.wait with optional timeout
        done, pending = await asyncio.wait(
            to_wait.values(),
            timeout=self._timeout,
        )

        # Cancel timed-out tasks
        for task in pending:
            task.cancel()

        # Yield events from completed tasks into the main stream
        for task in done:
            if not task.cancelled() and task.exception() is None:
                for event in task.result():
                    yield event

        # Update session state metadata
        task_to_name = {v: k for k, v in to_wait.items()}

        status_map = ctx.session.state.get("_dispatch_status", {})
        for task in done:
            name = task_to_name.get(task)
            if name and name in status_map:
                if task.cancelled():
                    status_map[name]["status"] = "cancelled"
                elif task.exception():
                    status_map[name]["status"] = "error"
                    status_map[name]["error"] = str(task.exception())
                else:
                    status_map[name]["status"] = "completed"
        for task in pending:
            name = task_to_name.get(task)
            if name and name in status_map:
                status_map[name]["status"] = "timed_out"

        # Fire on_join topology hook
        joined = [task_to_name[t] for t in done if not t.cancelled() and t.exception() is None]
        timed_out = [task_to_name[t] for t in pending]
        hooks = _get_topology_hooks()
        if hooks:
            fn = getattr(hooks, "on_join", None)
            if fn is not None:
                await fn(ctx, joined, timed_out)

        # Remove joined tasks from registry
        for name in to_wait:
            tasks.pop(name, None)
