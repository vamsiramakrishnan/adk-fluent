"""adk_fluent._usage — unified LLM usage tracking.

This package is the session-scoped usage foundation. It covers token
accounting, per-agent breakdown, and USD cost estimation through a
frozen cost table.

Pieces:

- :class:`TurnUsage` — frozen per-call record.
- :class:`AgentUsage` — frozen cumulative view for one agent.
- :class:`ModelRate` / :class:`CostTable` — frozen per-model pricing.
- :class:`UsageTracker` — mutable aggregator. Owns the list of turns
  and exposes cumulative properties + a ``by_agent()`` breakdown.
- :class:`UsagePlugin` — ADK ``BasePlugin`` that wires the tracker to
  ``after_model_callback`` so every LLM call in the invocation tree
  is captured automatically.

Use :meth:`UsageTracker.callback` for per-agent wiring, or install a
:class:`UsagePlugin` on the root app for session-wide capture. The
``UsageUpdate`` harness event continues to live in
:mod:`adk_fluent._harness._events` because it is part of the harness
event bus taxonomy.
"""

from adk_fluent._usage._cost_table import CostTable, ModelRate
from adk_fluent._usage._plugin import UsagePlugin
from adk_fluent._usage._tracker import AgentUsage, UsageTracker
from adk_fluent._usage._turn import TurnUsage

__all__ = [
    "AgentUsage",
    "CostTable",
    "ModelRate",
    "TurnUsage",
    "UsagePlugin",
    "UsageTracker",
]
