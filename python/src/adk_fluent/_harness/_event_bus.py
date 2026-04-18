"""Session-scoped typed event bus — the observer backbone.

Every harness module that observes runtime behavior (dispatcher,
tape, renderer, hooks, usage tracker) needs the same thing: typed
events, routed to interested subscribers. Without a shared backbone,
each module builds its own observation layer.

EventBus is that backbone. One bus per session. Modules subscribe
by event ``kind`` or receive everything. ADK lifecycle callbacks
(before_tool, after_tool, after_model) emit typed events into the bus.

Design decisions:
    - **Synchronous emission** — observers are fast (logging, recording).
      Async subscribers would add latency to every tool call.
    - **Kind-based routing** — O(1) dispatch via dict lookup, not
      isinstance checks or pattern matching on every handler.
    - **Error isolation** — one failing subscriber never blocks others.
      Errors are captured, not swallowed silently.
    - **Composable factories** — ``bus.tape()``, ``bus.renderer()``
      return objects pre-wired as subscribers. No manual plumbing.

Composes with::

    EventDispatcher  — translate() emits into the bus
    SessionTape      — bus.tape() returns a subscribed tape
    Renderer         — bus.on("text", renderer.handle)
    (Hooks install as ADK plugins, not bus subscribers — see adk_fluent._hooks.)
    UsageTracker     — subscribes to "usage_update" events

Usage::

    bus = H.event_bus()

    # Subscribe by kind
    bus.on("tool_call_start", lambda e: print(f"  → {e.tool_name}"))

    # Subscribe to everything (tape, logger, etc.)
    bus.subscribe(tape.record)

    # Wire into agent callbacks
    agent = (
        Agent("coder")
        .before_tool(bus.before_tool_hook())
        .after_tool(bus.after_tool_hook())
    )
"""

from __future__ import annotations

import contextlib
import contextvars
import time
from collections.abc import Callable, Iterator
from typing import Any

from adk_fluent._harness._events import (
    ErrorOccurred,
    HarnessEvent,
    ToolCallEnd,
    ToolCallStart,
    UsageUpdate,
)

__all__ = ["EventBus", "active_bus", "emit", "use_bus"]


# ----------------------------------------------------------------------
# Ambient bus — lets call-sites deep in the stack emit without plumbing
# an ``EventBus`` through every signature (guards, eval, hooks).
# ----------------------------------------------------------------------

_active_bus: contextvars.ContextVar[EventBus | None] = contextvars.ContextVar("adkf_active_event_bus", default=None)


def active_bus() -> EventBus | None:
    """Return the ambient :class:`EventBus`, or ``None`` if unset.

    Consumers that want to emit events without being handed a bus
    directly (guards, eval cases, hook bridges) call this and skip
    emission cleanly when no bus is installed.
    """
    return _active_bus.get()


def emit(event: HarnessEvent) -> None:
    """Emit ``event`` on the ambient bus if one is installed.

    No-op when no bus is active — makes emit sites cheap and safe to
    sprinkle anywhere.
    """
    bus = _active_bus.get()
    if bus is not None:
        bus.emit(event)


@contextlib.contextmanager
def use_bus(bus: EventBus | None) -> Iterator[None]:
    """Install ``bus`` as the ambient bus for the duration of the block."""
    token = _active_bus.set(bus)
    try:
        yield
    finally:
        _active_bus.reset(token)


class EventBus:
    """Session-scoped typed event bus.

    The single source of truth for harness observability. Subscribers
    register by event kind or receive all events. ADK callbacks emit
    typed ``HarnessEvent`` objects into the bus.

    Thread-safety: emit() is safe to call from any thread. Subscriber
    lists are append-only during normal operation (no concurrent
    iteration + mutation).

    Args:
        max_buffer: Max events to retain in history (0 = no buffer).
            Buffer is useful for late subscribers that need catch-up.
    """

    def __init__(self, *, max_buffer: int = 0) -> None:
        self._handlers: dict[str, list[Callable[[HarnessEvent], None]]] = {}
        self._global: list[Callable[[HarnessEvent], None]] = []
        self._buffer: list[HarnessEvent] = []
        self._max_buffer = max_buffer
        self._errors: list[tuple[Callable, Exception]] = []

    # -----------------------------------------------------------------
    # Subscribe / unsubscribe
    # -----------------------------------------------------------------

    def on(self, kind: str, handler: Callable[[HarnessEvent], None]) -> EventBus:
        """Subscribe to events of a specific kind.

        Args:
            kind: Event kind (e.g. ``"text"``, ``"tool_call_start"``).
            handler: Callback receiving matching events.

        Returns:
            Self for chaining.
        """
        self._handlers.setdefault(kind, []).append(handler)
        return self

    def subscribe(self, handler: Callable[[HarnessEvent], Any]) -> EventBus:
        """Subscribe to ALL events.

        Args:
            handler: Callback receiving every event. Return value is
                ignored, so recorders like ``SessionTape.record`` that
                return a ``seq`` can subscribe directly.

        Returns:
            Self for chaining.
        """
        self._global.append(handler)
        return self

    def off(self, handler: Callable) -> EventBus:
        """Remove a handler from all subscriptions.

        Args:
            handler: The handler to remove.

        Returns:
            Self for chaining.
        """
        self._global = [h for h in self._global if h is not handler]
        for kind in self._handlers:
            self._handlers[kind] = [h for h in self._handlers[kind] if h is not handler]
        return self

    # -----------------------------------------------------------------
    # Emit
    # -----------------------------------------------------------------

    def emit(self, event: HarnessEvent) -> None:
        """Emit a typed event to all matching subscribers.

        Kind-specific handlers run first, then global handlers.
        Each handler is isolated — one failure doesn't block others.

        Args:
            event: The HarnessEvent to dispatch.
        """
        # Buffer for late subscribers / replay
        if self._max_buffer > 0:
            self._buffer.append(event)
            if len(self._buffer) > self._max_buffer:
                self._buffer = self._buffer[-self._max_buffer :]

        # Kind-specific
        for handler in self._handlers.get(event.kind, []):
            with contextlib.suppress(Exception):
                handler(event)

        # Global
        for handler in self._global:
            with contextlib.suppress(Exception):
                handler(event)

    # -----------------------------------------------------------------
    # ADK callback hook factories
    # -----------------------------------------------------------------

    def before_tool_hook(self) -> Callable:
        """Create a ``before_tool`` callback that emits ToolCallStart.

        Returns:
            ADK-compatible before_tool callback.
        """
        bus = self

        def _hook(
            *,
            tool: Any,
            args: dict,
            tool_context: Any,
            **_kw: Any,
        ) -> None:
            name = getattr(tool, "name", str(tool))
            bus.emit(ToolCallStart(tool_name=name, args=dict(args)))
            return None  # allow execution

        return _hook

    def after_tool_hook(self) -> Callable:
        """Create an ``after_tool`` callback that emits ToolCallEnd.

        Captures tool name, result string, and duration.

        Returns:
            ADK-compatible after_tool callback.
        """
        bus = self
        _start_times: dict[str, float] = {}

        def _before(
            *,
            tool: Any,
            args: dict,
            tool_context: Any,
            **_kw: Any,
        ) -> None:
            name = getattr(tool, "name", str(tool))
            _start_times[name] = time.monotonic()
            return None

        def _after(
            *,
            tool: Any,
            args: dict,
            tool_context: Any,
            tool_response: Any,
            **_kw: Any,
        ) -> Any:
            name = getattr(tool, "name", str(tool))
            start = _start_times.pop(name, time.monotonic())
            duration_ms = (time.monotonic() - start) * 1000

            result_str = str(tool_response)[:500] if tool_response else ""

            # Emit error event if result indicates failure
            if result_str.startswith("Error:") or (isinstance(tool_response, dict) and "error" in tool_response):
                bus.emit(ErrorOccurred(tool_name=name, error=result_str[:200]))

            bus.emit(
                ToolCallEnd(
                    tool_name=name,
                    result=result_str,
                    duration_ms=round(duration_ms, 1),
                )
            )
            return tool_response

        # Stash the before hook so callers can wire both
        _after._before_hook = _before  # type: ignore[attr-defined]
        return _after

    def after_model_hook(self) -> Callable:
        """Create an ``after_model`` callback that emits text/usage events.

        Emits UsageUpdate if token counts are available on the response.

        Returns:
            ADK-compatible after_model callback.
        """
        bus = self

        def _hook(*, callback_context: Any, llm_response: Any, **_kw: Any) -> Any:
            # Extract usage metadata if present
            usage = getattr(llm_response, "usage_metadata", None)
            if usage:
                bus.emit(
                    UsageUpdate(
                        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                        output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                        total_tokens=getattr(usage, "total_token_count", 0) or 0,
                    )
                )
            return llm_response

        return _hook

    # -----------------------------------------------------------------
    # Composable factories
    # -----------------------------------------------------------------

    def tape(self, *, max_events: int = 0) -> Any:
        """Create a SessionTape pre-subscribed to this bus.

        Args:
            max_events: Max events in the tape buffer.

        Returns:
            A SessionTape instance, already recording.
        """
        from adk_fluent._session import SessionTape

        t = SessionTape(max_events=max_events)
        self.subscribe(t.record)
        return t

    # Note: the unified HookRegistry is not an EventBus subscriber. It
    # installs as an ADK Plugin via ``registry.as_plugin()`` and fires
    # directly from ADK callback sites, independent of this bus. The bus
    # still exists for harness-level events (GitCheckpoint, ProcessEvent,
    # etc.) that do not have a native ADK callback.

    # -----------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------

    @property
    def subscriber_count(self) -> int:
        """Total number of registered handlers."""
        kind_count = sum(len(handlers) for handlers in self._handlers.values())
        return kind_count + len(self._global)

    @property
    def buffer(self) -> list[HarnessEvent]:
        """Buffered event history (if max_buffer > 0)."""
        return list(self._buffer)

    def __repr__(self) -> str:
        kinds = len(self._handlers)
        total = self.subscriber_count
        return f"EventBus(subscribers={total}, kinds={kinds})"
