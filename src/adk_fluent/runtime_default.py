"""Default runtime — backend-agnostic execution lifecycle manager.

This runtime manages session lifecycle, middleware execution, and event
collection independently of any specific backend. It delegates actual
agent execution to the compiled backend via ``backend.run()`` or
``backend.stream()``.

Usage::

    from adk_fluent.runtime_default import DefaultRuntime
    from adk_fluent.compile import compile

    result = compile(ir, backend="adk")
    runtime = DefaultRuntime()
    execution = await runtime.execute(result, "Hello")
    print(execution.text)
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from adk_fluent._ir import AgentEvent
from adk_fluent.backends._protocol import final_text
from adk_fluent.compile import CompilationResult
from adk_fluent.runtime_protocol import ExecutionResult, SessionHandle

__all__ = ["DefaultRuntime"]


class DefaultRuntime:
    """Backend-agnostic runtime that manages execution lifecycle.

    Handles:
    - Session creation (in-memory by default, or via a StateStore)
    - Middleware before/after hooks
    - Delegation to the backend for actual execution
    - Event collection and result extraction
    - State persistence after execution
    """

    def __init__(
        self,
        *,
        state_store: Any | None = None,
        middleware: list[Any] | None = None,
    ):
        self._state_store = state_store
        self._middleware = middleware or []
        self._session_counter = 0

    async def execute(
        self,
        compiled: CompilationResult | Any,
        prompt: str,
        *,
        session_id: str | None = None,
        user_id: str = "default",
        backend: Any | None = None,
    ) -> ExecutionResult:
        """Execute a compiled runnable and return structured results.

        Args:
            compiled: A CompilationResult from ``compile()``, or a raw
                     backend-specific runnable (for backward compatibility).
            prompt: The user's input text.
            session_id: Optional session ID for resuming a session.
            user_id: User identifier.
            backend: Optional backend instance. Required if ``compiled``
                    is not a CompilationResult.

        Returns:
            An ``ExecutionResult`` with text, events, state, and metadata.
        """
        t0 = time.monotonic()

        # Unwrap CompilationResult
        if isinstance(compiled, CompilationResult):
            runnable = compiled.runnable
            backend_impl = backend or _resolve_backend_from_result(compiled)
        else:
            runnable = compiled
            backend_impl = backend
            if backend_impl is None:
                raise ValueError(
                    "When passing a raw runnable (not CompilationResult), "
                    "you must provide a backend= argument."
                )

        # Create session handle
        session = await self._create_session(session_id, user_id)

        # Run middleware: before_run
        trace_ctx = _create_trace_context()
        await self._run_middleware_hook("before_run", trace_ctx)

        # Delegate to backend
        events = await backend_impl.run(runnable, prompt, session=session)

        # Run middleware: after_run
        await self._run_middleware_hook("after_run", trace_ctx)

        # Persist state
        if self._state_store is not None:
            state_delta = _collect_state_delta(events)
            session.state.update(state_delta)
            await self._state_store.save(session.session_id, session.state)

        # Extract result
        text = final_text(events)
        elapsed = time.monotonic() - t0

        return ExecutionResult(
            text=text,
            events=events,
            state=session.state,
            session_id=session.session_id,
            metadata={"elapsed_seconds": elapsed},
        )

    async def execute_stream(
        self,
        compiled: CompilationResult | Any,
        prompt: str,
        *,
        session_id: str | None = None,
        user_id: str = "default",
        backend: Any | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Stream events from a compiled runnable.

        Args:
            compiled: A CompilationResult or raw runnable.
            prompt: The user's input text.
            session_id: Optional session ID.
            user_id: User identifier.
            backend: Optional backend instance.

        Yields:
            AgentEvent objects as they are produced.
        """
        # Unwrap CompilationResult
        if isinstance(compiled, CompilationResult):
            runnable = compiled.runnable
            backend_impl = backend or _resolve_backend_from_result(compiled)
        else:
            runnable = compiled
            backend_impl = backend
            if backend_impl is None:
                raise ValueError(
                    "When passing a raw runnable (not CompilationResult), "
                    "you must provide a backend= argument."
                )

        # Create session handle
        session = await self._create_session(session_id, user_id)

        # Run middleware: before_run
        trace_ctx = _create_trace_context()
        await self._run_middleware_hook("before_run", trace_ctx)

        # Stream from backend
        async for event in backend_impl.stream(runnable, prompt, session=session):
            yield event

        # Run middleware: after_run
        await self._run_middleware_hook("after_run", trace_ctx)

    async def _create_session(self, session_id: str | None, user_id: str) -> SessionHandle:
        """Create or resume a session."""
        if session_id is not None and self._state_store is not None:
            state = await self._state_store.load(session_id)
            return SessionHandle(
                session_id=session_id,
                user_id=user_id,
                state=state,
            )

        # Generate a new session ID
        self._session_counter += 1
        new_id = session_id or f"session_{self._session_counter}"

        if self._state_store is not None:
            sid = await self._state_store.create("default")
            return SessionHandle(session_id=sid, user_id=user_id)

        return SessionHandle(session_id=new_id, user_id=user_id)

    async def _run_middleware_hook(self, hook_name: str, ctx: Any) -> None:
        """Run a named hook across all middleware in order."""
        for mw in self._middleware:
            fn = getattr(mw, hook_name, None)
            if fn is not None:
                result = fn(ctx)
                # Await if coroutine
                if hasattr(result, "__await__"):
                    await result


def _resolve_backend_from_result(compiled: CompilationResult) -> Any:
    """Resolve backend from CompilationResult metadata."""
    backend_name = compiled.backend_name
    from adk_fluent.backends import get_backend

    return get_backend(backend_name)


def _create_trace_context() -> Any:
    """Create a lightweight trace context for middleware."""
    from adk_fluent.middleware import TraceContext

    return TraceContext()


def _collect_state_delta(events: list[AgentEvent]) -> dict:
    """Collect all state deltas from events into a single dict."""
    merged: dict = {}
    for event in events:
        if event.state_delta:
            merged.update(event.state_delta)
    return merged
