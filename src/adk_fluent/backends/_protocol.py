"""Backend protocol -- the contract between IR and execution engines."""
from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable

from adk_fluent._ir import AgentEvent, ExecutionConfig


@runtime_checkable
class Backend(Protocol):
    """A backend compiles IR node trees into runnable objects and executes them."""

    def compile(self, node: Any, config: ExecutionConfig | None = None) -> Any:
        """Transform an IR node tree into a backend-specific runnable."""
        ...

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute the compiled runnable and return all events."""
        ...

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Stream events as they occur."""
        ...


def final_text(events: list[AgentEvent]) -> str:
    """Extract the final response text from an event list."""
    for event in reversed(events):
        if event.is_final and event.content:
            return event.content
    return ""
