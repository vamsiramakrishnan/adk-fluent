"""Usage tracking — token counts and cost estimation.

Both Claude Code and Gemini CLI show per-turn and cumulative token usage.
This module provides a lightweight tracker that integrates as an
after_model callback and emits harness events::

    tracker = UsageTracker()
    agent = Agent("coder").after_model(tracker.callback())

    # After execution
    print(tracker.total_input_tokens)
    print(tracker.total_output_tokens)
    print(tracker.summary())

The tracker does NOT implement a dashboard — harness builders render
the data however they want (terminal, web UI, JSON export).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._harness._events import HarnessEvent

__all__ = ["UsageTracker", "TurnUsage", "UsageUpdate"]


@dataclass(frozen=True, slots=True)
class UsageUpdate(HarnessEvent):
    """Emitted after each model call with usage data."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    kind: str = "usage_update"


@dataclass(frozen=True, slots=True)
class TurnUsage:
    """Usage data for a single model call."""

    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    timestamp: float = 0.0
    duration_ms: float = 0.0


@dataclass
class UsageTracker:
    """Tracks token usage across model calls.

    Attach to an agent via ``.after_model(tracker.callback())``.
    Query cumulative stats via properties or ``.summary()``.

    Args:
        cost_per_million_input: Cost per 1M input tokens (USD).
        cost_per_million_output: Cost per 1M output tokens (USD).
    """

    cost_per_million_input: float = 0.0
    cost_per_million_output: float = 0.0
    _turns: list[TurnUsage] = field(default_factory=list)
    _start_time: float = field(default_factory=time.time)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens across all model calls."""
        return sum(t.input_tokens for t in self._turns)

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens across all model calls."""
        return sum(t.output_tokens for t in self._turns)

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output) across all model calls."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        """Estimated total cost in USD."""
        input_cost = (self.total_input_tokens / 1_000_000) * self.cost_per_million_input
        output_cost = (self.total_output_tokens / 1_000_000) * self.cost_per_million_output
        return input_cost + output_cost

    @property
    def turns(self) -> list[TurnUsage]:
        """All recorded turn usage data."""
        return list(self._turns)

    @property
    def turn_count(self) -> int:
        """Number of model calls tracked."""
        return len(self._turns)

    def record(self, input_tokens: int, output_tokens: int, *, model: str = "", duration_ms: float = 0.0) -> TurnUsage:
        """Manually record a model call's usage.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            model: Model identifier.
            duration_ms: Call duration in milliseconds.

        Returns:
            The recorded TurnUsage.
        """
        turn = TurnUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            timestamp=time.time(),
            duration_ms=duration_ms,
        )
        self._turns.append(turn)
        return turn

    def callback(self) -> Callable:
        """Create an after_model callback that records token usage.

        Extracts token counts from the ADK callback context's
        ``llm_response`` usage metadata.

        Returns:
            An ADK-compatible after_model callback.
        """
        tracker = self

        def _track_usage(callback_context: Any, llm_response: Any) -> Any:
            input_tokens = 0
            output_tokens = 0
            model = ""

            # Extract usage from LLM response metadata
            usage = getattr(llm_response, "usage_metadata", None)
            if usage is not None:
                input_tokens = getattr(usage, "prompt_token_count", 0) or 0
                output_tokens = getattr(usage, "candidates_token_count", 0) or 0

            model = getattr(llm_response, "model", "") or ""
            tracker.record(input_tokens, output_tokens, model=model)
            return llm_response

        return _track_usage

    def summary(self) -> str:
        """Human-readable usage summary.

        Returns:
            A formatted string with token counts and cost.
        """
        lines = [
            f"Turns: {self.turn_count}",
            f"Input tokens: {self.total_input_tokens:,}",
            f"Output tokens: {self.total_output_tokens:,}",
            f"Total tokens: {self.total_tokens:,}",
        ]
        if self.cost_per_million_input > 0 or self.cost_per_million_output > 0:
            lines.append(f"Estimated cost: ${self.total_cost_usd:.4f}")
        elapsed = time.time() - self._start_time
        lines.append(f"Session duration: {elapsed:.1f}s")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all tracked usage data."""
        self._turns.clear()
        self._start_time = time.time()
