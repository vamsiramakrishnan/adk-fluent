"""adk_fluent._permissions — decision-based permission layer with modes.

The permission foundation mirrors Claude Agent SDK's ``canUseTool`` surface
and the five permission modes (default / accept_edits / plan / bypass /
dont_ask). It is session-scoped via an ADK ``BasePlugin`` so a single policy
covers every tool call in the invocation tree, including subagents.

Pieces:

- :class:`PermissionDecision` / :class:`PermissionBehavior` — structured
  return protocol.
- :class:`PermissionMode` — mode string constants.
- :class:`PermissionPolicy` — declarative rules + mode, consulted by the
  plugin at every tool call.
- :class:`ApprovalMemory` — session-scoped record of interactive approvals.
- :class:`PermissionPlugin` — the ADK plugin that enforces the policy.

Users interact with the layer via the ``H`` namespace helpers
(``H.permissions()``, ``H.ask_before()``, ``H.auto_allow()``, ``H.deny()``,
``H.plan_mode()``, ``H.bypass_mode()``) and install the resulting policy via
``.harness(permissions=...)``.
"""

from adk_fluent._permissions._decision import (
    PermissionBehavior,
    PermissionDecision,
)
from adk_fluent._permissions._memory import ApprovalMemory
from adk_fluent._permissions._mode import ALL_MODES, PermissionMode
from adk_fluent._permissions._plugin import PermissionHandler, PermissionPlugin
from adk_fluent._permissions._policy import (
    DEFAULT_MUTATING_TOOLS,
    DEFAULT_READ_ONLY_TOOLS,
    PermissionPolicy,
)

__all__ = [
    "ALL_MODES",
    "ApprovalMemory",
    "DEFAULT_MUTATING_TOOLS",
    "DEFAULT_READ_ONLY_TOOLS",
    "PermissionBehavior",
    "PermissionDecision",
    "PermissionHandler",
    "PermissionMode",
    "PermissionPlugin",
    "PermissionPolicy",
]
