"""PlanMode latch — the plan-then-execute state machine.

Claude Agent SDK and Claude Code both ship a "plan mode" where the
agent is asked to describe what it *would* do without actually doing
it. The agent enters plan mode via a tool call, dumps a plan, and
exits with the finalised plan text. While in planning, mutating tools
(``write_file``, ``edit_file``, ``bash``, …) must be denied by the
permission layer.

This module promotes that latch out of ``_harness/_agent_tools.py``
into a first-class package so it can carry observers and feed both
the permission policy and the plugin wrapper.

States
------

- ``off`` — default. Mutating tools follow the underlying permission
  policy.
- ``planning`` — agent has called ``enter_plan_mode``. Mutating tools
  must be denied.
- ``executing`` — agent has called ``exit_plan_mode`` with a finalised
  plan. Mutating tools are allowed again, and the plan text is
  available via :attr:`PlanMode.current_plan`.

Observers
---------

Code that needs to react to state changes (e.g. a permission policy
that flips to :data:`PermissionMode.PLAN`) can register a callback via
:meth:`PlanMode.subscribe`. Observers are called synchronously with
the new state string and the plan text.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Literal

__all__ = ["PlanMode", "PlanState", "MUTATING_TOOLS"]


PlanState = Literal["off", "planning", "executing"]


MUTATING_TOOLS = frozenset(
    {
        "write_file",
        "edit_file",
        "bash",
        "run_code",
        "git_commit",
        "start_process",
    }
)


PlanObserver = Callable[[PlanState, str], None]


class PlanMode:
    """Runtime latch for the plan-then-execute flow.

    When the latch is in ``planning``, the harness should reject every
    write/edit/exec tool call and surface the proposed plan to the
    user instead. The harness wires the latch into a
    :class:`~adk_fluent._permissions.PermissionPolicy` (either directly
    or via :class:`~adk_fluent._plan_mode.PlanModePolicy`), or drives
    it from an ADK plugin.
    """

    def __init__(self) -> None:
        self._state: PlanState = "off"
        self._plan = ""
        self._observers: list[PlanObserver] = []

    # ------------------------------------------------------------------
    # Read-only state
    # ------------------------------------------------------------------

    @property
    def current(self) -> PlanState:
        """Return the current state (``"off" | "planning" | "executing"``)."""
        return self._state

    @property
    def current_plan(self) -> str:
        """Return the plan text captured on ``exit_plan_mode`` (empty if none)."""
        return self._plan

    @property
    def is_planning(self) -> bool:
        return self._state == "planning"

    @property
    def is_executing(self) -> bool:
        return self._state == "executing"

    @staticmethod
    def is_mutating(tool_name: str) -> bool:
        """Return True if ``tool_name`` is in the default mutating-tool set."""
        return tool_name in MUTATING_TOOLS

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def enter(self) -> None:
        """Enter plan mode. Clears any previously-captured plan text."""
        self._state = "planning"
        self._plan = ""
        self._notify()

    def exit(self, plan: str) -> None:
        """Exit plan mode with the finalised plan text."""
        self._state = "executing"
        self._plan = plan
        self._notify()

    def reset(self) -> None:
        """Reset to ``off`` and drop the captured plan."""
        self._state = "off"
        self._plan = ""
        self._notify()

    # ------------------------------------------------------------------
    # Observers
    # ------------------------------------------------------------------

    def subscribe(self, callback: PlanObserver) -> Callable[[], None]:
        """Register a state-change observer.

        Observers are called synchronously whenever the latch
        transitions (``enter``, ``exit``, or ``reset``). They receive
        the new state string and the plan text.

        Returns a zero-arg function that unsubscribes the observer.
        """
        self._observers.append(callback)

        def _unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._observers.remove(callback)

        return _unsubscribe

    def _notify(self) -> None:
        for cb in list(self._observers):
            try:
                cb(self._state, self._plan)
            except Exception:
                # Observers must not break the latch. Swallow and
                # continue — production setups can add logging in the
                # observer itself.
                continue

    # ------------------------------------------------------------------
    # Tool factory (kept on the latch for single-call convenience)
    # ------------------------------------------------------------------

    def tools(self) -> list[Callable]:
        """Return the ``enter_plan_mode`` / ``exit_plan_mode`` tool pair."""
        from adk_fluent._plan_mode._tools import plan_mode_tools

        return plan_mode_tools(self)
