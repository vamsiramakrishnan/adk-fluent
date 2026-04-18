"""adk_fluent._reactor — reactive signals + priority scheduling.

This package adds a small reactive layer on top of the durable tape:

- :class:`Signal` — a typed state cell with version tracking. Mutations
  emit :class:`SignalChanged` events on the harness bus and tape.
- :class:`SignalPredicate` — declarative triggers composed from signals
  (``(temp.rising > 90) & online.is_true``). Supports boolean ops,
  ``.where()``, ``.debounce()``, ``.throttle()``.
- :class:`Reactor` — cursor-following scheduler that runs registered
  agents when their predicates fire, with priority ordering and
  cooperative interrupts.

The reactor reads from :class:`SessionTape` via ``tape.tail()`` so all
reactions are ordered by seq, survive process restarts, and can be
deterministically replayed for tests.
"""

from __future__ import annotations

from adk_fluent._reactor._predicate import SignalPredicate
from adk_fluent._reactor._reactor import Reactor, ReactorRule
from adk_fluent._reactor._signal import Signal
from adk_fluent._reactor._tracking import computed, reaction, track_reads

__all__ = [
    "Reactor",
    "ReactorRule",
    "Signal",
    "SignalPredicate",
    "computed",
    "reaction",
    "track_reads",
]
