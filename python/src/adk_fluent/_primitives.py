"""Runtime agent primitives for adk-fluent — backward-compatibility shim.

The canonical implementation now lives at ``adk_fluent.backends.adk._primitives``.
This module re-exports everything for backward compatibility.
"""

from adk_fluent.backends.adk._primitives import *  # noqa: F401,F403
from adk_fluent.backends.adk._primitives import (  # noqa: F401  — explicit re-exports
    _DEFAULT_MAX_TASKS,
    _DEFAULT_TASK_BUDGET,
    _dispatch_tasks,
    _execution_mode,
    _FanOutHookAgent,
    _get_topology_hooks,
    _global_task_budget,
    _LoopHookAgent,
    _middleware_dispatch_hooks,
    _topology_hooks,
)
