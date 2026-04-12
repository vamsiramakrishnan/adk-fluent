"""Interrupt & resume — cooperative cancellation and state snapshots.

Claude Code supports Ctrl-C to interrupt a running turn and resume
from where it left off. This module provides the framework primitives:

- ``CancellationToken`` — thread-safe signal checked by tool callbacks
- ``TurnSnapshot`` — captures mid-turn state for resumption
- ``make_cancellation_callback`` — before_tool callback that aborts
  tool execution when the token is set

Usage::

    token = H.cancellation_token()
    agent = (
        Agent("coder")
        .before_tool(make_cancellation_callback(token))
    )

    # In the REPL or UI thread
    try:
        async for event in repl.step(prompt):
            handle(event)
    except KeyboardInterrupt:
        token.cancel()            # Signal cancellation
        snapshot = token.snapshot  # Get mid-turn state

    # Resume later
    token.reset()
    resumed = await repl.step(snapshot.resume_prompt())
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CancellationToken",
    "TurnSnapshot",
    "make_cancellation_callback",
]


@dataclass
class TurnSnapshot:
    """Captures mid-turn state for resumption.

    When a turn is interrupted, the snapshot contains enough context
    to construct a resume prompt that picks up where the agent left off.
    """

    prompt: str = ""
    events_so_far: list[Any] = field(default_factory=list)
    tool_calls_completed: list[dict[str, Any]] = field(default_factory=list)
    tool_call_interrupted: str | None = None
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def resume_prompt(self) -> str:
        """Generate a prompt that resumes from the interruption point.

        Includes context about what was already completed so the agent
        can continue without repeating work.
        """
        parts = [f"[Resuming interrupted task]\nOriginal request: {self.prompt}"]

        if self.tool_calls_completed:
            completed = ", ".join(tc.get("tool_name", "unknown") for tc in self.tool_calls_completed)
            parts.append(f"Already completed: {completed}")

        if self.tool_call_interrupted:
            parts.append(f"Interrupted during: {self.tool_call_interrupted}")

        parts.append("Please continue from where you left off.")
        return "\n".join(parts)


class CancellationToken:
    """Thread-safe cooperative cancellation signal.

    The token is checked by ``make_cancellation_callback`` before each
    tool call. When cancelled, tool execution is blocked and the turn
    ends gracefully.

    Thread-safe: ``cancel()`` can be called from a signal handler or
    another thread (e.g., KeyboardInterrupt on the main thread).
    """

    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._snapshot: TurnSnapshot | None = None
        self._current_prompt: str = ""
        self._events: list[Any] = []
        self._tool_calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled.is_set()

    def cancel(self) -> None:
        """Request cancellation. Thread-safe.

        Takes a snapshot of the current turn state at the moment
        of cancellation.
        """
        with self._lock:
            self._snapshot = TurnSnapshot(
                prompt=self._current_prompt,
                events_so_far=list(self._events),
                tool_calls_completed=list(self._tool_calls),
                state_snapshot={},
            )
        self._cancelled.set()

    def reset(self) -> None:
        """Reset the token for a new turn."""
        self._cancelled.clear()
        with self._lock:
            self._snapshot = None
            self._current_prompt = ""
            self._events.clear()
            self._tool_calls.clear()

    @property
    def snapshot(self) -> TurnSnapshot | None:
        """Get the snapshot taken at cancellation time."""
        return self._snapshot

    def begin_turn(self, prompt: str) -> None:
        """Mark the start of a new turn. Called by the REPL/harness."""
        with self._lock:
            self._current_prompt = prompt
            self._events.clear()
            self._tool_calls.clear()

    def record_event(self, event: Any) -> None:
        """Record an event during the turn."""
        with self._lock:
            self._events.append(event)

    def record_tool_call(self, tool_name: str, args: dict[str, Any]) -> None:
        """Record a completed tool call."""
        with self._lock:
            self._tool_calls.append({"tool_name": tool_name, "args": args})


def make_cancellation_callback(token: CancellationToken) -> Callable:
    """Create a before_tool callback that checks the cancellation token.

    When the token is cancelled, the callback returns an error dict
    that prevents the tool from executing. The agent receives the
    cancellation message and can wrap up gracefully.

    Args:
        token: The cancellation token to check.

    Returns:
        An ADK-compatible before_tool callback.
    """

    def check_cancellation(
        callback_context: Any,
        tool: Any,
        args: dict,
        tool_context: Any,
    ) -> Any | None:
        if token.is_cancelled:
            tool_name = getattr(tool, "name", str(tool))
            with threading.Lock():
                if token._snapshot is not None:
                    token._snapshot.tool_call_interrupted = tool_name
            return {"error": ("Operation cancelled by user. Summarize what you've done so far and stop.")}
        # Record that we're about to execute this tool
        tool_name = getattr(tool, "name", str(tool))
        token.record_tool_call(tool_name, dict(args))
        return None

    return check_cancellation
