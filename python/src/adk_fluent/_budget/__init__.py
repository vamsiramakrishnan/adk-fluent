"""adk_fluent._budget — cumulative token budget with threshold triggers.

This package is the session-scoped budget foundation. It splits a
budget into three orthogonal pieces so tests can exercise each in
isolation:

- :class:`Threshold` — a frozen checkpoint (percent + callback) with
  no runtime state.
- :class:`BudgetPolicy` — a frozen, declarative bundle of
  ``max_tokens`` + thresholds. Immutable; safe to share.
- :class:`BudgetMonitor` — the live tracker. Records cumulative
  usage, fires threshold callbacks, and exposes utilisation metrics.
- :class:`BudgetPlugin` — an ADK ``BasePlugin`` that auto-records
  usage for every LLM call in the session (root + sub-agents +
  subagent specialists) so you don't have to wire an after-model
  callback by hand.

Users interact via the ``H`` namespace helpers (``H.budget_monitor()``,
``H.budget_policy()``, ``H.budget_plugin()``) or by constructing the
classes directly.
"""

from adk_fluent._budget._plugin import BudgetPlugin
from adk_fluent._budget._policy import BudgetPolicy
from adk_fluent._budget._threshold import Threshold
from adk_fluent._budget._tracker import BudgetMonitor

__all__ = [
    "BudgetMonitor",
    "BudgetPlugin",
    "BudgetPolicy",
    "Threshold",
]
