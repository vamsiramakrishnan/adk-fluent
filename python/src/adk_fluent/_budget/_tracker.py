"""BudgetMonitor — cumulative token tracking with threshold triggers.

``C.budget()`` and ``C.rolling()`` compress context at instruction time.
They shape what the LLM sees on each turn, but they cannot make
*session-level* decisions like "we're at 80% capacity, switch from
``window(10)`` to ``window(3)``" or "we're at 95%, summarise everything."

``BudgetMonitor`` fills that gap. It tracks cumulative token usage across
turns and fires callbacks when configurable thresholds are crossed. It
does **not** implement compression itself — it delegates to whatever
handler the caller wires up.

Design decisions:

- **Separate monitoring from compression** — the monitor observes tokens;
  the handler decides what to do. This keeps policies testable without
  spinning up a compressor.
- **Threshold callbacks** — multiple thresholds with different actions
  (warn at 80%, compress at 95%).
- **Composable** — works with the event bus (emits
  ``CompressionTriggered``) and with ``C.*`` transforms (handler swaps
  the context strategy).

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
from typing import Any

from adk_fluent._budget._threshold import Threshold

__all__ = ["BudgetMonitor"]


class BudgetMonitor:
    """Token budget lifecycle monitor.

    Tracks cumulative token usage across turns and fires threshold
    callbacks. The monitor does not implement compression — it delegates
    to handlers.

    Args:
        max_tokens: Total token budget for the session.
    """

    def __init__(self, max_tokens: int = 200_000) -> None:
        self._max_tokens = max_tokens
        self._current_tokens = 0
        self._turn_count = 0
        self._thresholds: list[Threshold] = []
        self._fired: set[int] = set()
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
            percent: Utilisation fraction (0.0–1.0).
            callback: Called with ``(monitor)`` when threshold is crossed.
            recurring: Fire on every record above threshold (not just once).

        Returns:
            Self, for chaining.
        """
        self._thresholds.append(Threshold(percent=percent, callback=callback, recurring=recurring))
        # Keep sorted so they fire in ascending order.
        self._thresholds.sort(key=lambda t: t.percent)
        return self

    def add_threshold(self, threshold: Threshold) -> BudgetMonitor:
        """Register a pre-built :class:`Threshold`.

        Args:
            threshold: The threshold to add.

        Returns:
            Self, for chaining.
        """
        self._thresholds.append(threshold)
        self._thresholds.sort(key=lambda t: t.percent)
        return self

    def with_bus(self, bus: Any) -> BudgetMonitor:
        """Wire an ``EventBus`` for threshold events.

        When any threshold fires the monitor emits a
        ``CompressionTriggered`` event so subscribers can react.

        Args:
            bus: An EventBus instance.

        Returns:
            Self, for chaining.
        """
        self._event_bus = bus
        return self

    # -----------------------------------------------------------------
    # Token tracking
    # -----------------------------------------------------------------

    def record_usage(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Record token usage from one model call.

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
        for idx, threshold in enumerate(self._thresholds):
            already_fired = idx in self._fired
            if utilization >= threshold.percent and (not already_fired or threshold.recurring):
                self._fired.add(idx)

                if self._event_bus is not None:
                    from adk_fluent._harness._events import CompressionTriggered

                    self._event_bus.emit(
                        CompressionTriggered(
                            token_count=self._current_tokens,
                            threshold=int(threshold.percent * self._max_tokens),
                        )
                    )

                with contextlib.suppress(Exception):
                    threshold.callback(self)

    def reset(self) -> None:
        """Reset cumulative count and threshold firing state.

        Call after a compression pass to restart the budget cycle.
        """
        self._current_tokens = 0
        self._turn_count = 0
        self._history.clear()
        self._fired.clear()

    def adjust(self, new_token_count: int) -> None:
        """Adjust the current token count (e.g. after compression).

        Any thresholds whose ``percent`` is above the new utilisation
        become re-armable.

        Args:
            new_token_count: New estimated token count post-compression.
        """
        self._current_tokens = new_token_count
        utilization = self.utilization
        for idx, threshold in enumerate(self._thresholds):
            if threshold.percent > utilization:
                self._fired.discard(idx)

    # -----------------------------------------------------------------
    # ADK callback hook
    # -----------------------------------------------------------------

    def after_model_hook(self) -> Callable:
        """Return an ``after_model`` callback that records usage.

        Extracts usage metadata from the LLM response and calls
        :meth:`record_usage`.

        Returns:
            ADK-compatible ``after_model`` callback.
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
        """Current utilisation as a fraction (0.0–1.0)."""
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

    @property
    def thresholds(self) -> tuple[Threshold, ...]:
        """Return the registered thresholds in ascending percent order."""
        return tuple(self._thresholds)

    def thresholds_fired(self) -> int:
        """Return the count of thresholds that have fired in this cycle."""
        return len(self._fired)

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
            "thresholds_fired": len(self._fired),
        }

    def __repr__(self) -> str:
        return (
            f"BudgetMonitor({self._current_tokens}/{self._max_tokens} "
            f"= {self.utilization:.0%}, turns={self._turn_count})"
        )
