"""Event dispatcher — translates ADK events into typed HarnessEvents.

The dispatcher sits between the ADK event stream and harness consumers,
converting raw ADK events into the structured HarnessEvent hierarchy.
It also routes events to hooks and observers::

    dispatcher = EventDispatcher()
    dispatcher.subscribe(my_ui_handler)

    async for adk_event in agent.events(prompt):
        for harness_event in dispatcher.translate(adk_event):
            # harness_event is a typed HarnessEvent
            ...

Consumers can subscribe to specific event kinds::

    dispatcher.on("text", print_text)
    dispatcher.on("tool_call_start", show_spinner)
    dispatcher.on("turn_complete", log_turn)

.. note::

    EventDispatcher delegates its pub/sub routing to ``EventBus``.
    The dispatcher adds ADK event *translation*; the bus provides
    the subscriber backbone. Use ``EventBus`` directly when you
    don't need ADK translation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from adk_fluent._harness._event_bus import EventBus
from adk_fluent._harness._events import (
    HarnessEvent,
    TextChunk,
    ToolCallEnd,
    ToolCallStart,
    TurnComplete,
)

__all__ = ["EventDispatcher"]


class EventDispatcher:
    """Translates ADK events into HarnessEvents and routes them.

    Delegates subscriber management to an ``EventBus``. The dispatcher
    adds the ADK-specific ``translate()`` method that converts raw ADK
    events into the typed ``HarnessEvent`` hierarchy.

    Args:
        bus: Optional EventBus to delegate to. Creates one if not provided.
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or EventBus()

    @property
    def bus(self) -> EventBus:
        """The underlying EventBus."""
        return self._bus

    def subscribe(self, handler: Callable[[HarnessEvent], None]) -> EventDispatcher:
        """Subscribe to all events. Delegates to EventBus.

        Args:
            handler: Callback receiving every HarnessEvent.

        Returns:
            Self for chaining.
        """
        self._bus.subscribe(handler)
        return self

    def on(self, kind: str, handler: Callable[[HarnessEvent], None]) -> EventDispatcher:
        """Subscribe to events of a specific kind. Delegates to EventBus.

        Args:
            kind: Event kind to listen for (e.g., "text", "tool_call_start").
            handler: Callback receiving matching events.

        Returns:
            Self for chaining.
        """
        self._bus.on(kind, handler)
        return self

    def emit(self, event: HarnessEvent) -> None:
        """Emit a HarnessEvent to all matching subscribers. Delegates to EventBus.

        Args:
            event: The event to dispatch.
        """
        self._bus.emit(event)

    def translate(self, adk_event: Any) -> list[HarnessEvent]:
        """Translate an ADK event into zero or more HarnessEvents.

        This method inspects the ADK event's structure and produces
        the appropriate typed HarnessEvent(s).

        Args:
            adk_event: A raw ADK Event object.

        Returns:
            List of HarnessEvents (may be empty).
        """
        events: list[HarnessEvent] = []

        # ADK events have various shapes — inspect attributes
        content = getattr(adk_event, "content", None)
        if content is not None:
            parts = getattr(content, "parts", []) if content else []
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    event = TextChunk(text=text)
                    events.append(event)
                    self.emit(event)

                # Check for function calls
                fn_call = getattr(part, "function_call", None)
                if fn_call:
                    name = getattr(fn_call, "name", "")
                    args = dict(getattr(fn_call, "args", {}))
                    event = ToolCallStart(tool_name=name, args=args)
                    events.append(event)
                    self.emit(event)

                # Check for function responses
                fn_resp = getattr(part, "function_response", None)
                if fn_resp:
                    name = getattr(fn_resp, "name", "")
                    result = str(getattr(fn_resp, "response", ""))
                    event = ToolCallEnd(tool_name=name, result=result)
                    events.append(event)
                    self.emit(event)

        # Check for turn completion signals
        is_final = getattr(adk_event, "is_final_response", False)
        if is_final and content:
            text_parts = []
            for part in getattr(content, "parts", []):
                text = getattr(part, "text", None)
                if text:
                    text_parts.append(text)
            if text_parts:
                event = TurnComplete(response="\n".join(text_parts))
                events.append(event)
                self.emit(event)

        return events

    def translate_and_emit(self, adk_event: Any) -> list[HarnessEvent]:
        """Alias for translate() — translates AND emits events."""
        return self.translate(adk_event)
