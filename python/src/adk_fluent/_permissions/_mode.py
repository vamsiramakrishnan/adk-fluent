"""PermissionMode — preset permission postures.

Mirrors Claude Agent SDK's permission modes. A mode is a string constant
that :class:`PermissionPolicy` consults when the policy's allow / deny / ask
rules do not match a tool. Modes are declarative — they describe "what to do
by default", not a runtime state machine.

Modes
-----

``default``
    Conservative. Unknown tools default to ``ask`` — the user must approve
    every non-allowlisted tool call. This is the safe starting point for
    interactive agents.

``accept_edits``
    Auto-approve mutating file operations (``edit_file``, ``write_file``,
    etc.) but still ask before running shell commands. The canonical
    "trusted coding assistant with cautious shell access" mode.

``plan``
    Read-only. Mutating tools are **denied** outright; the agent is forced
    to describe what it would do rather than do it. This is the mode the
    :mod:`adk_fluent._plan_mode` package builds on.

``bypass``
    Every tool is allowed. Use only for internal automation where the input
    is trusted. Equivalent to running without a permission policy at all,
    but surfaces its intent explicitly in the code.

``dont_ask``
    Honour the explicit allow / deny rules but never prompt. Anything that
    would be ``ask`` is denied. Good for non-interactive runners (CI, batch
    jobs) where no human can answer a prompt.
"""

from __future__ import annotations

__all__ = ["PermissionMode", "ALL_MODES"]


class PermissionMode:
    """Namespace of canonical permission mode names (string constants)."""

    DEFAULT: str = "default"
    ACCEPT_EDITS: str = "accept_edits"
    PLAN: str = "plan"
    BYPASS: str = "bypass"
    DONT_ASK: str = "dont_ask"


ALL_MODES: frozenset[str] = frozenset(
    {
        PermissionMode.DEFAULT,
        PermissionMode.ACCEPT_EDITS,
        PermissionMode.PLAN,
        PermissionMode.BYPASS,
        PermissionMode.DONT_ASK,
    }
)
