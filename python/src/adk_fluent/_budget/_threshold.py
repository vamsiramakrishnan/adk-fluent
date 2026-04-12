"""Threshold — a frozen budget checkpoint with a callback.

A :class:`Threshold` is a pure config value. It says *"when cumulative
utilisation crosses ``percent``, invoke ``callback``."* It does **not**
carry any runtime state — fired-state lives inside the tracker so a single
threshold config can be shared across sessions without leaking state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["Threshold"]


@dataclass(frozen=True, slots=True)
class Threshold:
    """A budget checkpoint.

    Attributes:
        percent: Utilisation fraction (0.0–1.0) at which the threshold
            fires. A value of 0.8 means "when we have burnt 80% of the
            budget".
        callback: Called with ``(tracker)`` when the threshold is crossed.
            The callback is free to inspect state, mutate the tracker
            (e.g. via :meth:`BudgetMonitor.reset`), or emit events.
        recurring: If True the callback fires on every record above the
            threshold. If False (default) it fires once per reset cycle.
    """

    percent: float
    callback: Callable[..., Any]
    recurring: bool = False

    def __post_init__(self) -> None:
        if not 0.0 < self.percent <= 1.0:
            raise ValueError(f"Threshold percent must be in (0.0, 1.0], got {self.percent}")
