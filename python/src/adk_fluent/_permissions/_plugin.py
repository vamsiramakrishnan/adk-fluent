"""PermissionPlugin — session-scoped ADK plugin that enforces a policy.

The plugin intercepts every ``before_tool_callback`` in the agent tree and
dispatches through the :class:`PermissionPolicy`. Because ADK plugins are
session-scoped and subagent-inherited, a single plugin covers every tool call
regardless of depth — there is no need to walk the agent hierarchy.

Lifecycle of a single check::

    policy.check(tool_name, tool_input)
        │
        ├── allow  → mutate tool_args in place (if updated_input), return None
        │
        ├── deny   → return {"error": reason}
        │
        └── ask    → consult ApprovalMemory
                     │
                     ├── remembered allow → return None
                     ├── remembered deny  → return {"error": ...}
                     └── no memory        → call handler
                                            │
                                            ├── handler=None     → return {"error": ...}
                                            ├── handler returns True  → remember + return None
                                            └── handler returns False → remember + return {"error": ...}

Interactive handlers run inside an async-compatible wrapper: sync handlers
are called directly, async handlers are awaited. Handler exceptions are
converted to deny decisions (same defensive stance as :mod:`adk_fluent._hooks`).

The plugin does **not** fire the ``pre_tool_use`` hook event — that remains
the job of :class:`~adk_fluent._hooks.HookPlugin`. Permissions and hooks are
orthogonal plugins that can be installed side by side; the permission plugin
sits *before* the hook plugin in the ADK plugin chain so a denied tool never
fires its hooks.
"""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Optional, Union

from google.adk.plugins.base_plugin import BasePlugin

from adk_fluent._permissions._decision import PermissionBehavior, PermissionDecision
from adk_fluent._permissions._memory import ApprovalMemory
from adk_fluent._permissions._policy import PermissionPolicy

__all__ = ["PermissionPlugin", "PermissionHandler"]


PermissionHandler = Callable[
    [str, dict, PermissionDecision],
    Union[bool, Awaitable[bool]],
]
"""Signature of an interactive permission handler.

Receives the tool name, the tool argument dict, and the ``ask`` decision the
policy produced (so the handler can show the policy's suggested prompt).
Returns True to allow, False to deny. Async handlers are awaited."""


class PermissionPlugin(BasePlugin):
    """ADK ``BasePlugin`` enforcing a :class:`PermissionPolicy`.

    Args:
        policy: The permission policy to enforce.
        handler: Optional interactive handler invoked when the policy
            returns an ``ask`` decision.
        memory: Optional :class:`ApprovalMemory` for persistent decisions.
        name: Plugin display name (default ``"adkf_permission_plugin"``).
    """

    def __init__(
        self,
        policy: PermissionPolicy,
        *,
        handler: PermissionHandler | None = None,
        memory: ApprovalMemory | None = None,
        name: str = "adkf_permission_plugin",
    ) -> None:
        super().__init__(name=name)
        self._policy = policy
        self._handler = handler
        self._memory = memory

    @property
    def policy(self) -> PermissionPolicy:
        return self._policy

    @property
    def memory(self) -> ApprovalMemory | None:
        return self._memory

    # ------------------------------------------------------------------
    # ADK hook
    # ------------------------------------------------------------------

    async def before_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: dict[str, Any],
        tool_context: Any,
    ) -> Optional[dict]:
        tool_name = getattr(tool, "name", str(tool))
        decision = self._policy.check(tool_name, tool_args)

        if decision.is_deny:
            return {"error": decision.reason or f"Tool '{tool_name}' denied."}

        if decision.is_allow:
            self._apply_updated_input(tool_args, decision)
            return None

        # ask flow
        resolved = await self._resolve_ask(tool_name, tool_args, decision)
        if resolved.is_allow:
            self._apply_updated_input(tool_args, resolved)
            return None
        return {"error": resolved.reason or f"Tool '{tool_name}' denied."}

    # ------------------------------------------------------------------
    # Ask resolution
    # ------------------------------------------------------------------

    async def _resolve_ask(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        decision: PermissionDecision,
    ) -> PermissionDecision:
        # 1. Memory
        if self._memory is not None:
            recalled = self._memory.recall(tool_name, tool_args)
            if recalled is True:
                return PermissionDecision.allow()
            if recalled is False:
                return PermissionDecision.deny(
                    reason=f"Tool '{tool_name}' was previously denied."
                )

        # 2. Handler
        if self._handler is None:
            return PermissionDecision.deny(
                reason=(
                    f"Tool '{tool_name}' requires approval but no permission "
                    "handler is installed."
                )
            )

        try:
            result = self._handler(tool_name, tool_args, decision)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            return PermissionDecision.deny(
                reason=f"Permission handler raised: {exc}"
            )

        granted = bool(result)
        if self._memory is not None:
            self._memory.remember_specific(tool_name, tool_args, granted)
        if granted:
            return PermissionDecision.allow()
        return PermissionDecision.deny(
            reason=f"Tool '{tool_name}' was denied by the user."
        )

    # ------------------------------------------------------------------
    # Updated input application
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_updated_input(
        tool_args: dict[str, Any],
        decision: PermissionDecision,
    ) -> None:
        """Mutate ``tool_args`` in place with the decision's updated input.

        ADK passes ``tool_args`` by reference to the tool invocation, so
        mutating the dict here rewrites what the tool actually sees —
        same trick :class:`adk_fluent._hooks.HookPlugin` uses for
        :meth:`HookDecision.modify`.
        """
        if decision.updated_input is None:
            return
        tool_args.clear()
        tool_args.update(decision.updated_input)
