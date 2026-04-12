"""PlanModePolicy — tie a PlanMode latch to a PermissionPolicy.

``PermissionMode.PLAN`` is the declarative half of plan-then-execute:
when a policy is in plan mode, mutating tools are denied outright.
``PlanMode`` (the latch) is the *dynamic* half: it holds the current
state and flips on tool calls.

This module bridges the two. Wrapping a base
:class:`~adk_fluent._permissions.PermissionPolicy` in a
:class:`PlanModePolicy` yields an object that returns a policy whose
``mode`` follows the latch: ``plan`` while the latch says
``planning``, otherwise whatever the base policy had. Callers just use
the result as a drop-in :class:`PermissionPolicy`.

The wrapper is a thin frozen dataclass — it owns no mutable state.
The policy it returns is re-derived on every ``check`` call via the
latch, so there is no "stale" mode window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adk_fluent._permissions import PermissionDecision, PermissionMode, PermissionPolicy
from adk_fluent._plan_mode._latch import PlanMode

__all__ = ["PlanModePolicy"]


@dataclass(frozen=True, slots=True)
class PlanModePolicy:
    """Frozen wrapper that ties a PermissionPolicy to a PlanMode latch.

    Args:
        base: The underlying :class:`PermissionPolicy`. Used verbatim
            outside plan mode; its ``mode`` field is replaced with
            :data:`PermissionMode.PLAN` while the latch is planning.
        latch: The :class:`PlanMode` latch driving the mode switch.
    """

    base: PermissionPolicy
    latch: PlanMode

    def check(self, tool_name: str, arguments: Any = None) -> PermissionDecision:
        """Delegate to ``base.check`` with a plan-mode-aware policy."""
        return self._effective().check(tool_name, arguments)

    def _effective(self) -> PermissionPolicy:
        """Return a :class:`PermissionPolicy` whose mode reflects the latch."""
        if self.latch.is_planning:
            return self.base.with_mode(PermissionMode.PLAN)
        return self.base

    # ------------------------------------------------------------------
    # Read-through fields to allow drop-in compatibility with policy
    # consumers that introspect allow / deny / mode directly.
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._effective().mode

    @property
    def allow(self):  # noqa: ANN201
        return self.base.allow

    @property
    def deny(self):  # noqa: ANN201
        return self.base.deny

    @property
    def ask(self):  # noqa: ANN201
        return self.base.ask
