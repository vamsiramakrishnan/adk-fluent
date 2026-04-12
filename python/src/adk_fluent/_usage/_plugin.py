"""UsagePlugin — session-scoped ADK plugin that records every LLM call.

``UsageTracker.callback()`` handles per-agent wiring. When you want to
capture the *entire* invocation tree — root agent + sub-agents +
subagent specialists — use this plugin instead. ADK plugins are
session-scoped and inherited across subagents, so a single install
covers everything.

The plugin owns the tracker; access it via :attr:`UsagePlugin.tracker`
for assertions, summaries, and runtime introspection.
"""

from __future__ import annotations

from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

from adk_fluent._usage._tracker import UsageTracker, _extract_usage

__all__ = ["UsagePlugin"]


class UsagePlugin(BasePlugin):
    """ADK ``BasePlugin`` that records token usage into a tracker.

    Args:
        tracker: The :class:`UsageTracker` to feed. If ``None``, a
            fresh tracker is created.
        name: Plugin display name (default ``"adkf_usage_plugin"``).
    """

    def __init__(
        self,
        tracker: UsageTracker | None = None,
        *,
        name: str = "adkf_usage_plugin",
    ) -> None:
        super().__init__(name=name)
        self._tracker = tracker or UsageTracker()

    @property
    def tracker(self) -> UsageTracker:
        return self._tracker

    async def after_model_callback(
        self,
        *,
        callback_context: Any,
        llm_response: Any,
    ) -> Any:
        input_tokens, output_tokens, model = _extract_usage(llm_response)
        agent_name = getattr(callback_context, "agent_name", "") or ""
        self._tracker.record(
            input_tokens,
            output_tokens,
            model=model,
            agent_name=agent_name,
        )
        return None
