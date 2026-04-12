"""Agent-level before_tool callback adapter for PermissionPolicy.

The canonical runtime for permissions is :class:`PermissionPlugin`, installed
at the ADK ``App`` / ``Runner`` layer. But a number of existing surfaces
(most notably :meth:`adk_fluent._base.BuilderBase.harness`) expose permissions
as agent-level callbacks instead of session-level plugins. For those surfaces
we provide :func:`make_permission_callback` — a thin synchronous adapter that
runs the same policy logic from inside a ``before_tool_callback``.

Adapter semantics mirror the plugin exactly:

- ``allow`` with ``updated_input`` → mutates ``tool_args`` in place, returns ``None``.
- ``allow`` without input → returns ``None``.
- ``deny`` → returns ``{"error": reason}``.
- ``ask`` → consults :class:`ApprovalMemory`, then the interactive handler.

The handler must be synchronous here because ADK agent-level callbacks are
called in a sync path. For async handlers use :class:`PermissionPlugin`
directly at the App layer.
"""

from __future__ import annotations

from typing import Any, Callable

from adk_fluent._permissions._decision import PermissionDecision
from adk_fluent._permissions._memory import ApprovalMemory
from adk_fluent._permissions._policy import PermissionPolicy

__all__ = ["make_permission_callback"]


def make_permission_callback(
    policy: PermissionPolicy,
    handler: Callable[[str, dict], bool] | None = None,
    memory: ApprovalMemory | None = None,
) -> Callable[..., Any]:
    """Return a ``before_tool_callback`` enforcing ``policy``.

    Args:
        policy: The permission policy to enforce.
        handler: Synchronous approval handler ``(tool_name, args) -> bool``.
            Called when the policy returns an ``ask`` decision and the
            memory has no recorded verdict.
        memory: Optional :class:`ApprovalMemory` for persistent decisions.

    Returns:
        An ADK-compatible before_tool callback. Returns ``None`` to allow
        the tool, a dict to short-circuit with an error.
    """

    def _callback(
        callback_context: Any,
        tool: Any,
        args: dict,
        tool_context: Any,
    ) -> Any | None:
        tool_name = getattr(tool, "name", str(tool))
        decision = policy.check(tool_name, args)

        if decision.is_deny:
            return {"error": decision.reason or f"Tool '{tool_name}' denied."}

        if decision.is_allow:
            if decision.updated_input is not None:
                args.clear()
                args.update(decision.updated_input)
            return None

        # ask
        if memory is not None:
            recalled = memory.recall(tool_name, args)
            if recalled is True:
                return None
            if recalled is False:
                return {
                    "error": f"Tool '{tool_name}' was previously denied."
                }

        if handler is None:
            return {
                "error": (
                    f"Tool '{tool_name}' requires approval but no handler "
                    "is installed."
                )
            }

        try:
            granted = bool(handler(tool_name, args))
        except Exception as exc:
            return {"error": f"Permission handler raised: {exc}"}

        if memory is not None:
            memory.remember_specific(tool_name, args, granted)
        if not granted:
            return {"error": f"Tool '{tool_name}' was denied by the user."}
        return None

    return _callback
