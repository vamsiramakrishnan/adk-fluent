"""TurnUsage — the frozen per-call record.

One :class:`TurnUsage` represents exactly one LLM call's usage: tokens in,
tokens out, which model produced them, when they arrived, and how long
the call took. It is the atom the :class:`UsageTracker` aggregates.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["TurnUsage"]


@dataclass(frozen=True, slots=True)
class TurnUsage:
    """Usage data for a single model call.

    Attributes:
        input_tokens: Prompt tokens consumed.
        output_tokens: Completion tokens generated.
        model: Model identifier (e.g. ``"gemini-2.5-flash"``).
        agent_name: Name of the agent that produced the call, if known.
        timestamp: Unix timestamp of the call.
        duration_ms: Call duration in milliseconds.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    agent_name: str = ""
    timestamp: float = 0.0
    duration_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        """Sum of input and output tokens."""
        return self.input_tokens + self.output_tokens
