"""Mock backend for deterministic testing without LLM calls."""
from __future__ import annotations

from typing import Any, AsyncIterator

from adk_fluent._ir import AgentEvent, ExecutionConfig


class MockBackend:
    """A backend that returns canned responses for each agent name.

    Satisfies the Backend protocol without making any LLM calls.
    """

    def __init__(self, responses: dict[str, Any]):
        self._responses = responses

    def compile(self, node: Any, config: ExecutionConfig | None = None) -> Any:
        return node  # Pass-through; we walk the IR directly in run()

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        self._walk(compiled, events)
        return events

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        events = await self.run(compiled, prompt, **kwargs)
        for event in events:
            yield event

    def _walk(self, node: Any, events: list[AgentEvent]):
        """Walk the IR tree and generate events from canned responses."""
        name = getattr(node, "name", "")
        children = getattr(node, "children", ())

        if children:
            for child in children:
                self._walk(child, events)
        else:
            response = self._responses.get(name)
            if response is None:
                events.append(AgentEvent(
                    author=name,
                    content=f"[no mock for '{name}']",
                    is_final=True,
                ))
            elif isinstance(response, dict):
                events.append(AgentEvent(
                    author=name,
                    state_delta=response,
                    is_final=True,
                ))
            else:
                events.append(AgentEvent(
                    author=name,
                    content=str(response),
                    is_final=True,
                ))


def mock_backend(responses: dict[str, Any]) -> MockBackend:
    """Create a mock backend with canned responses.

    Args:
        responses: Mapping of agent name -> response.
            str values become content, dict values become state_delta.
    """
    return MockBackend(responses)
