"""adk_fluent._plan_mode — plan-then-execute policy + latch + plugin.

This package unifies adk-fluent's plan-mode mechanism. It promotes the
latch class that used to live in ``_harness/_agent_tools.py`` into a
top-level package and adds the missing wiring to make the latch talk
to permissions automatically.

Pieces:

- :class:`PlanMode` — runtime latch with three states
  (``off``/``planning``/``executing``) and an observer subscription
  surface for external code that needs to react to transitions.
- :data:`MUTATING_TOOLS` — the default set of tool names treated as
  mutating. Consulted by the plugin and by
  :class:`~adk_fluent._permissions.PermissionPolicy`.
- :func:`plan_mode_tools` — factory for the
  ``enter_plan_mode`` / ``exit_plan_mode`` tool pair.
- :class:`PlanModePolicy` — frozen wrapper that ties a
  :class:`PermissionPolicy` to a latch. The effective policy's mode
  switches to :data:`PermissionMode.PLAN` whenever the latch is in
  ``planning``.
- :class:`PlanModePlugin` — session-scoped ADK ``BasePlugin`` that
  owns a latch and installs a ``before_tool_callback`` which denies
  mutating tools while the latch is planning.
"""

from adk_fluent._plan_mode._latch import MUTATING_TOOLS, PlanMode, PlanState
from adk_fluent._plan_mode._plugin import PlanModePlugin
from adk_fluent._plan_mode._policy import PlanModePolicy
from adk_fluent._plan_mode._tools import plan_mode_tools

__all__ = [
    "MUTATING_TOOLS",
    "PlanMode",
    "PlanModePlugin",
    "PlanModePolicy",
    "PlanState",
    "plan_mode_tools",
]
