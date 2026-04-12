"""plan_mode_tools — enter/exit tool factory for a PlanMode latch.

Builds a pair of plain-function tools that the agent can invoke to
drive the latch:

- ``enter_plan_mode()`` — flip to ``planning`` state.
- ``exit_plan_mode(plan: str)`` — flip to ``executing`` and capture
  the finalised plan text.

Kept as a module-level factory so tests and harness presets can build
the pair without instantiating the latch themselves.
"""

from __future__ import annotations

from collections.abc import Callable

from adk_fluent._plan_mode._latch import PlanMode

__all__ = ["plan_mode_tools"]


def plan_mode_tools(latch: PlanMode) -> list[Callable]:
    """Return ``[enter_plan_mode, exit_plan_mode]`` wired to ``latch``."""

    def enter_plan_mode() -> dict:
        """Enter plan mode. The agent should propose a plan, not act."""
        latch.enter()
        return {"state": latch.current}

    def exit_plan_mode(plan: str) -> dict:
        """Exit plan mode with the finalized plan text.

        Args:
            plan: Markdown / numbered list describing the steps.
        """
        latch.exit(plan)
        return {"state": latch.current, "plan": latch.current_plan}

    enter_plan_mode.__name__ = "enter_plan_mode"
    exit_plan_mode.__name__ = "exit_plan_mode"
    return [enter_plan_mode, exit_plan_mode]
