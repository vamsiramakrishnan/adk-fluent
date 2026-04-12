"""PlanModePlugin — session-scoped ADK plugin owning a PlanMode latch.

Installing this plugin on the root app gives you one shared latch
across every agent in the invocation tree (root + sub-agents +
subagent specialists), plus a ``before_tool_callback`` that denies
mutating tools while the latch is in ``planning``. The plugin is the
simplest way to get "LLM calls ``enter_plan_mode`` → edits get
blocked until it calls ``exit_plan_mode``" without wiring a latch
into every agent by hand.

Unlike the bare :class:`PlanMode` class, the plugin exposes the latch
publicly via :attr:`PlanModePlugin.latch` so tests and UI surfaces
can observe state transitions.
"""

from __future__ import annotations

from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

from adk_fluent._plan_mode._latch import PlanMode

__all__ = ["PlanModePlugin"]


class PlanModePlugin(BasePlugin):
    """ADK ``BasePlugin`` that denies mutating tools while the latch is planning.

    Args:
        latch: Optional pre-built :class:`PlanMode`. A fresh latch is
            created if omitted.
        name: ADK plugin display name.
    """

    def __init__(
        self,
        latch: PlanMode | None = None,
        *,
        name: str = "adkf_plan_mode_plugin",
    ) -> None:
        super().__init__(name=name)
        self._latch = latch or PlanMode()

    @property
    def latch(self) -> PlanMode:
        return self._latch

    async def before_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: Any = None,
        tool_context: Any = None,
    ) -> Any:
        """Block mutating tool calls while the latch is in ``planning``.

        Returns a deny dict (ADK convention) to short-circuit the tool
        call; otherwise returns ``None`` so the call proceeds.
        """
        if not self._latch.is_planning:
            return None
        tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", "")
        if PlanMode.is_mutating(tool_name):
            return {
                "error": (
                    f"Plan mode denies mutating tool '{tool_name}'. "
                    "Call exit_plan_mode(plan) before touching the workspace."
                ),
                "plan_mode_state": self._latch.current,
            }
        return None
