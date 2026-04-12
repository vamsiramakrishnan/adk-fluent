"""Test harness for agent builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adk_fluent._ir import AgentEvent


@dataclass
class HarnessResponse:
    """Result from a harness send() call."""

    events: list[AgentEvent]
    final_text: str = ""
    errors: list[str] = field(default_factory=list)


class AgentHarness:
    """Wraps a builder + mock backend for ergonomic testing."""

    def __init__(self, builder: Any, *, backend: Any):
        self._builder = builder
        self._backend = backend

    async def send(self, prompt: str) -> HarnessResponse:
        ir = self._builder.to_ir()
        compiled = self._backend.compile(ir)
        events = await self._backend.run(compiled, prompt)
        final = ""
        for event in reversed(events):
            if event.is_final and event.content:
                final = event.content
                break
        return HarnessResponse(events=events, final_text=final)
