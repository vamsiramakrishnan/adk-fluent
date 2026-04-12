"""BudgetPolicy — a frozen, declarative budget configuration.

A policy is the inert description of a budget. It names the maximum
token count and the thresholds to install. Instantiate it once at build
time, pass it around by value, and hand it to :class:`BudgetMonitor` or
:class:`BudgetPlugin` to produce a live tracker.

Separating the policy from the tracker keeps the configuration pure:
you can diff two policies, hash them, ship them via YAML, or hold them
as a module-level constant without worrying about accidental mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from adk_fluent._budget._threshold import Threshold
from adk_fluent._budget._tracker import BudgetMonitor

__all__ = ["BudgetPolicy"]


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    """Declarative budget configuration.

    Attributes:
        max_tokens: Total token budget for the session.
        thresholds: Tuple of :class:`Threshold` values to install on the
            tracker. Order does not matter — the tracker sorts by
            ``percent`` internally.
    """

    max_tokens: int = 200_000
    thresholds: tuple[Threshold, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.max_tokens <= 0:
            raise ValueError(f"BudgetPolicy.max_tokens must be positive, got {self.max_tokens}")

    def build_monitor(self) -> BudgetMonitor:
        """Materialise a fresh :class:`BudgetMonitor` from this policy.

        Returns:
            A new tracker with every configured threshold installed.
        """
        monitor = BudgetMonitor(max_tokens=self.max_tokens)
        for threshold in self.thresholds:
            monitor.add_threshold(threshold)
        return monitor

    def with_threshold(
        self,
        percent: float,
        callback,
        *,
        recurring: bool = False,
    ) -> BudgetPolicy:
        """Return a copy of this policy with an extra threshold appended.

        Args:
            percent: Utilisation fraction (0.0–1.0).
            callback: Callback fired with ``(monitor)`` when crossed.
            recurring: Whether to fire on every record above threshold.

        Returns:
            A new frozen :class:`BudgetPolicy`.
        """
        new_threshold = Threshold(percent=percent, callback=callback, recurring=recurring)
        return BudgetPolicy(
            max_tokens=self.max_tokens,
            thresholds=self.thresholds + (new_threshold,),
        )
