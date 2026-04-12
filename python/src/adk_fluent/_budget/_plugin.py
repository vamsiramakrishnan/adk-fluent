"""BudgetPlugin — a session-scoped ADK plugin that records token usage.

The :class:`BudgetMonitor` is a plain Python object — it records usage
when you call :meth:`~BudgetMonitor.record_usage`. In a typical agent
tree you want the monitor to *automatically* observe every LLM call in
the session (root agent, sub-agents, task-tool specialists) without
threading a callback through every builder.

The fix is an ADK ``BasePlugin``. Plugins are session-scoped and their
``after_model_callback`` fires for every LLM call in the invocation
tree, so a single plugin covers the whole session.

Usage::

    policy = H.budget_policy(200_000).with_threshold(0.9, compress_handler)
    plugin = BudgetPlugin(policy)

    app = Agent("coder").plugin(plugin).build()

The plugin owns the tracker; access it via :attr:`BudgetPlugin.monitor`
for assertions or to install additional thresholds at runtime.
"""

from __future__ import annotations

from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

from adk_fluent._budget._policy import BudgetPolicy
from adk_fluent._budget._tracker import BudgetMonitor

__all__ = ["BudgetPlugin"]


class BudgetPlugin(BasePlugin):
    """ADK ``BasePlugin`` that records token usage into a tracker.

    Args:
        policy_or_monitor: Either a :class:`BudgetPolicy` (a fresh tracker
            is materialised from it) or an existing :class:`BudgetMonitor`
            (useful when callers want to share a tracker across multiple
            plugins, e.g. with an event bus).
        name: Plugin display name (default ``"adkf_budget_plugin"``).
    """

    def __init__(
        self,
        policy_or_monitor: BudgetPolicy | BudgetMonitor,
        *,
        name: str = "adkf_budget_plugin",
    ) -> None:
        super().__init__(name=name)
        if isinstance(policy_or_monitor, BudgetPolicy):
            self._monitor = policy_or_monitor.build_monitor()
        elif isinstance(policy_or_monitor, BudgetMonitor):
            self._monitor = policy_or_monitor
        else:
            raise TypeError(
                "BudgetPlugin expected BudgetPolicy or BudgetMonitor, "
                f"got {type(policy_or_monitor).__name__}"
            )

    @property
    def monitor(self) -> BudgetMonitor:
        """Return the underlying tracker (mutable handle for tests/ops)."""
        return self._monitor

    # ------------------------------------------------------------------
    # ADK hook
    # ------------------------------------------------------------------

    async def after_model_callback(
        self,
        *,
        callback_context: Any,
        llm_response: Any,
    ) -> Any:
        """Record usage from the LLM response, if any."""
        usage = getattr(llm_response, "usage_metadata", None)
        if usage:
            inp = getattr(usage, "prompt_token_count", 0) or 0
            out = getattr(usage, "candidates_token_count", 0) or 0
            self._monitor.record_usage(inp, out)
        return None
