"""UsageTracker — cumulative LLM usage with optional cost table.

The tracker is a plain Python object that records a :class:`TurnUsage`
every time an LLM call completes, and exposes cumulative counts plus an
optional USD cost estimate.

Two integration patterns:

- **Callback mode** — attach ``tracker.callback()`` to a single agent
  via ``.after_model()``. Useful for per-agent tracking.
- **Plugin mode** — wrap the tracker in :class:`UsagePlugin` and
  install it on the root app. The plugin's ``after_model_callback`` is
  session-scoped so it captures every LLM call in the invocation tree
  (root + sub-agents + subagent specialists) without extra wiring.

The tracker supports per-agent breakdown: call
:meth:`UsageTracker.by_agent` to get a ``{agent_name: cumulative}`` view,
handy for splitting coordinator vs specialist costs.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._usage._cost_table import CostTable
from adk_fluent._usage._turn import TurnUsage

__all__ = ["UsageTracker", "AgentUsage"]


@dataclass(frozen=True, slots=True)
class AgentUsage:
    """Cumulative usage for one named agent."""

    agent_name: str
    input_tokens: int
    output_tokens: int
    calls: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class UsageTracker:
    """Track LLM usage across model calls.

    Args:
        cost_table: Optional :class:`CostTable` for USD estimation.
        cost_per_million_input: Convenience — if ``cost_table`` is None,
            a flat table is built from these two values.
        cost_per_million_output: See ``cost_per_million_input``.
    """

    cost_table: CostTable | None = None
    cost_per_million_input: float = 0.0
    cost_per_million_output: float = 0.0
    _turns: list[TurnUsage] = field(default_factory=list)
    _start_time: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.cost_table is None and (
            self.cost_per_million_input or self.cost_per_million_output
        ):
            self.cost_table = CostTable.flat(
                self.cost_per_million_input, self.cost_per_million_output
            )

    # ------------------------------------------------------------------
    # Cumulative totals
    # ------------------------------------------------------------------

    @property
    def total_input_tokens(self) -> int:
        return sum(t.input_tokens for t in self._turns)

    @property
    def total_output_tokens(self) -> int:
        return sum(t.output_tokens for t in self._turns)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        if self.cost_table is None:
            return 0.0
        return sum(self.cost_table.cost_for(t) for t in self._turns)

    @property
    def turns(self) -> list[TurnUsage]:
        """Return a defensive copy of the recorded turns."""
        return list(self._turns)

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    # ------------------------------------------------------------------
    # Per-agent breakdown
    # ------------------------------------------------------------------

    def by_agent(self) -> dict[str, AgentUsage]:
        """Return cumulative usage grouped by agent name.

        Returns:
            Mapping ``{agent_name: AgentUsage}``. Turns without an
            agent name are grouped under ``""``.
        """
        counter: dict[str, dict[str, int]] = defaultdict(
            lambda: {"input": 0, "output": 0, "calls": 0}
        )
        for t in self._turns:
            bucket = counter[t.agent_name]
            bucket["input"] += t.input_tokens
            bucket["output"] += t.output_tokens
            bucket["calls"] += 1
        return {
            name: AgentUsage(
                agent_name=name,
                input_tokens=data["input"],
                output_tokens=data["output"],
                calls=data["calls"],
            )
            for name, data in counter.items()
        }

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        input_tokens: int,
        output_tokens: int,
        *,
        model: str = "",
        agent_name: str = "",
        duration_ms: float = 0.0,
    ) -> TurnUsage:
        """Manually record one call's usage.

        Returns:
            The :class:`TurnUsage` that was appended.
        """
        turn = TurnUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            agent_name=agent_name,
            timestamp=time.time(),
            duration_ms=duration_ms,
        )
        self._turns.append(turn)
        return turn

    # ------------------------------------------------------------------
    # ADK integration helpers
    # ------------------------------------------------------------------

    def callback(self) -> Callable:
        """Return an ``after_model`` callback that records usage.

        The callback reads ``llm_response.usage_metadata`` and the
        agent name from ``callback_context.agent_name`` when available.
        """
        tracker = self

        def _track(callback_context: Any, llm_response: Any) -> Any:
            input_tokens, output_tokens, model = _extract_usage(llm_response)
            agent_name = getattr(callback_context, "agent_name", "") or ""
            tracker.record(
                input_tokens,
                output_tokens,
                model=model,
                agent_name=agent_name,
            )
            return llm_response

        return _track

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Human-readable summary (for terminals / logs)."""
        lines = [
            f"Turns: {self.turn_count}",
            f"Input tokens: {self.total_input_tokens:,}",
            f"Output tokens: {self.total_output_tokens:,}",
            f"Total tokens: {self.total_tokens:,}",
        ]
        if self.cost_table is not None:
            lines.append(f"Estimated cost: ${self.total_cost_usd:.4f}")
        elapsed = time.time() - self._start_time
        lines.append(f"Session duration: {elapsed:.1f}s")
        return "\n".join(lines)

    def reset(self) -> None:
        """Drop every recorded turn and reset the start time."""
        self._turns.clear()
        self._start_time = time.time()


def _extract_usage(llm_response: Any) -> tuple[int, int, str]:
    """Pull (input, output, model) out of an LLM response, defensively."""
    usage = getattr(llm_response, "usage_metadata", None)
    input_tokens = 0
    output_tokens = 0
    if usage is not None:
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
    model = getattr(llm_response, "model", "") or ""
    return input_tokens, output_tokens, model
