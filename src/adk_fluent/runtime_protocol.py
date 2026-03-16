"""Runtime protocol — manages execution lifecycle independent of backend.

The runtime layer sits between the compile layer and the execution backend.
It handles:
- Session creation and persistence
- Middleware stack execution (before/after hooks)
- Event routing and collection
- Structured output parsing

The key insight: middleware is a runtime concern, NOT an engine concern.
The same middleware stack works identically across ADK, Temporal, asyncio,
or any other backend.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from adk_fluent._ir import AgentEvent

__all__ = [
    "Runtime",
    "ExecutionResult",
    "SessionHandle",
]


@dataclass
class SessionHandle:
    """Lightweight reference to a session managed by a StateStore.

    Carries the session_id and current state snapshot. The runtime
    creates this before execution and updates it after.
    """

    session_id: str
    user_id: str = "default"
    state: dict[str, Any] = field(default_factory=dict)
    app_name: str = "adk_fluent_app"


@dataclass
class ExecutionResult:
    """Structured output of an execution.

    Returned by ``Runtime.execute()`` with all events, final text,
    state snapshot, and metadata.
    """

    text: str
    """Final response text from the agent."""

    events: list[AgentEvent]
    """All events produced during execution."""

    state: dict[str, Any]
    """Final state snapshot after execution."""

    session_id: str
    """Session ID used for this execution."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Execution metadata (timings, token counts, etc.)."""

    parsed: Any = None
    """Parsed structured output (if .returns() was set)."""


@runtime_checkable
class Runtime(Protocol):
    """Manages the execution lifecycle independent of backend.

    A Runtime orchestrates:
    1. Session creation/resume (via StateStore)
    2. Pre-execution middleware hooks
    3. Delegation to the compiled backend
    4. Post-execution middleware hooks
    5. State persistence
    6. Result collection and structuring
    """

    async def execute(
        self,
        compiled: Any,
        prompt: str,
        *,
        session_id: str | None = None,
        user_id: str = "default",
    ) -> ExecutionResult:
        """Execute a compiled runnable and return structured results."""
        ...

    async def execute_stream(
        self,
        compiled: Any,
        prompt: str,
        *,
        session_id: str | None = None,
        user_id: str = "default",
    ) -> AsyncIterator[AgentEvent]:
        """Stream events from a compiled runnable."""
        ...
