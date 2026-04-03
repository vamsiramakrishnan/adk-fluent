"""Token budget lifecycle — observe, trigger, delegate.

``C.budget()`` and ``C.rolling()`` compress context at instruction
time — they shape what the LLM sees on each turn. But they can't
make *session-level* decisions: "we're at 80% capacity, switch from
window(10) to window(3)" or "we're at 95%, summarize everything."

``BudgetMonitor`` fills this gap. It tracks cumulative token usage
across turns and fires callbacks when configurable thresholds are
crossed. It does NOT implement compression itself — it delegates
to whatever handler the harness builder wires up.

Design decisions:
    - **Separate monitoring from compression** — the monitor observes
      tokens; the handler decides what to do. This prevents the
      ContextCompressor's mistake of reimplementing C.window() logic.
    - **Threshold callbacks** — multiple thresholds with different
      actions (warn at 80%, compress at 95%).
    - **Composable** — works with EventBus (emits CompressionTriggered),
      with C.* transforms (handler can swap context strategy), and with
      ContextCompressor (as a replacement for should_compress()).

Usage::

    monitor = (
        H.budget_monitor(200_000)
        .on_threshold(0.8, lambda m: print(f"Warning: {m.utilization:.0%}"))
        .on_threshold(0.95, compress_handler)
    )

    agent = Agent("coder").after_model(monitor.after_model_hook())
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["BudgetMonitor", "Threshold"]


@dataclass(slots=True)
class Threshold:
    """A budget threshold with callback.

    Attributes:
        percent: Utilization percentage (0.0–1.0) to trigger at.
        callback: Called with the BudgetMonitor when threshold is crossed.
        fired: Whether this threshold has already fired this cycle.
        recurring: If True, fires every time (not just first crossing).
    """

    percent: float
    callback: Callable[..., None]
    fired: bool = False
    recurring: bool = False


class BudgetMonitor:
    """Token budget lifecycle monitor.

    Tracks cumulative token usage and fires threshold callbacks.
    Does not implement compression — delegates to handlers.

    Args:
        max_tokens: Total token budget for the session.
    """

    def __init__(self, max_tokens: int = 200_000) -> None:
        self._max_tokens = max_tokens
        self._current_tokens = 0
        self._turn_count = 0
        self._thresholds: list[Threshold] = []
        self._event_bus: Any = None
        self._history: list[tuple[int, int]] = []  # (input, output) per turn

    # -----------------------------------------------------------------
    # Configuration
    # -----------------------------------------------------------------

    def on_threshold(
        self,
        percent: float,
        callback: Callable[..., None],
        *,
        recurring: bool = False,
    ) -> BudgetMonitor:
        """Register a threshold callback.

        Args:
            percent: Utilization percentage (0.0–1.0).
            callback: Called with ``(monitor)`` when threshold is crossed.
            recurring: Fire every turn above threshold (not just once).

        Returns:
            Self for chaining.
        """
        self._thresholds.append(
            Threshold(
                percent=percent,
                callback=callback,
                recurring=recurring,
            )
        )
        # Keep sorted so they fire in order
        self._thresholds.sort(key=lambda t: t.percent)
        return self

    def with_bus(self, bus: Any) -> BudgetMonitor:
        """Wire an EventBus for threshold events.

        Emits ``CompressionTriggered`` when any threshold fires.

        Args:
            bus: An EventBus instance.

        Returns:
            Self for chaining.
        """
        self._event_bus = bus
        return self

    # -----------------------------------------------------------------
    # Token tracking
    # -----------------------------------------------------------------

    def record_usage(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Record token usage from a model call.

        Updates cumulative count and checks thresholds.

        Args:
            input_tokens: Tokens consumed by the prompt.
            output_tokens: Tokens produced by the response.
        """
        total = input_tokens + output_tokens
        self._current_tokens += total
        self._turn_count += 1
        self._history.append((input_tokens, output_tokens))
        self._check_thresholds()

    def _check_thresholds(self) -> None:
        """Fire any thresholds that have been crossed."""
        utilization = self.utilization
        for threshold in self._thresholds:
            if utilization >= threshold.percent and (not threshold.fired or threshold.recurring):
                threshold.fired = True

                # Emit event if bus is wired
                if self._event_bus is not None:
                    from adk_fluent._harness._events import CompressionTriggered

                    self._event_bus.emit(
                        CompressionTriggered(
                            token_count=self._current_tokens,
                            threshold=int(threshold.percent * self._max_tokens),
                        )
                    )

                # Fire callback
                with contextlib.suppress(Exception):
                    threshold.callback(self)

    def reset(self) -> None:
        """Reset token count and threshold states.

        Call after compression to restart the budget cycle.
        """
        self._current_tokens = 0
        self._turn_count = 0
        self._history.clear()
        for t in self._thresholds:
            t.fired = False

    def adjust(self, new_token_count: int) -> None:
        """Adjust the current token count (e.g., after compression).

        Args:
            new_token_count: New estimated token count post-compression.
        """
        self._current_tokens = new_token_count
        # Reset thresholds that are now below the new level
        utilization = self.utilization
        for t in self._thresholds:
            if t.percent > utilization:
                t.fired = False

    # -----------------------------------------------------------------
    # ADK callback hook
    # -----------------------------------------------------------------

    def after_model_hook(self) -> Callable:
        """Create an ``after_model`` callback that tracks token usage.

        Extracts usage metadata from the LLM response and records it.

        Returns:
            ADK-compatible after_model callback.
        """
        monitor = self

        def _hook(callback_context: Any, llm_response: Any) -> Any:
            usage = getattr(llm_response, "usage_metadata", None)
            if usage:
                inp = getattr(usage, "prompt_token_count", 0) or 0
                out = getattr(usage, "candidates_token_count", 0) or 0
                monitor.record_usage(inp, out)
            return llm_response

        return _hook

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------

    @property
    def max_tokens(self) -> int:
        """Total token budget."""
        return self._max_tokens

    @property
    def current_tokens(self) -> int:
        """Cumulative tokens used so far."""
        return self._current_tokens

    @property
    def utilization(self) -> float:
        """Current utilization as a fraction (0.0–1.0)."""
        if self._max_tokens <= 0:
            return 0.0
        return min(self._current_tokens / self._max_tokens, 1.0)

    @property
    def remaining(self) -> int:
        """Remaining token budget."""
        return max(0, self._max_tokens - self._current_tokens)

    @property
    def turn_count(self) -> int:
        """Number of turns recorded."""
        return self._turn_count

    @property
    def avg_tokens_per_turn(self) -> float:
        """Average tokens per turn."""
        if self._turn_count == 0:
            return 0.0
        return self._current_tokens / self._turn_count

    @property
    def estimated_turns_remaining(self) -> int:
        """Estimated turns before budget exhaustion."""
        avg = self.avg_tokens_per_turn
        if avg <= 0:
            return 0
        return int(self.remaining / avg)

    def summary(self) -> dict[str, Any]:
        """Return a summary of budget state."""
        return {
            "max_tokens": self._max_tokens,
            "current_tokens": self._current_tokens,
            "utilization": round(self.utilization, 3),
            "turns": self._turn_count,
            "avg_per_turn": round(self.avg_tokens_per_turn, 1),
            "remaining": self.remaining,
            "est_turns_remaining": self.estimated_turns_remaining,
            "thresholds_fired": sum(1 for t in self._thresholds if t.fired),
        }

    def __repr__(self) -> str:
        return (
            f"BudgetMonitor({self._current_tokens}/{self._max_tokens} "
            f"= {self.utilization:.0%}, turns={self._turn_count})"
        )
