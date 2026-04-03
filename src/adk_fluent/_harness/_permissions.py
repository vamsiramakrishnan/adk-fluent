"""Permission policies — composable tool approval rules.

Policies declare which tools need user approval, which are auto-allowed,
and which are denied entirely. Policies compose via ``.merge()``.

Approval persistence remembers user decisions across a session so the
same tool+args pattern isn't asked twice::

    store = ApprovalMemory()
    policy = PermissionPolicy(allow=frozenset(["read_file"]))
    cb = make_permission_callback(policy, handler=my_prompt, memory=store)
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "PermissionPolicy",
    "ApprovalMemory",
    "make_permission_callback",
]


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    """Declares which tools need approval and which are auto-allowed.

    Tools not mentioned in either list default to ``ask``.

    Supports both exact names and patterns (glob or regex)::

        # Exact names
        PermissionPolicy(allow=frozenset(["read_file"]))

        # Glob patterns
        PermissionPolicy(allow_patterns=("read_*", "list_*"))

        # Regex patterns
        PermissionPolicy(deny_patterns=(".*dangerous.*",), pattern_mode="regex")
    """

    ask: frozenset[str] = frozenset()
    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()
    # Pattern-based rules (glob by default, regex with pattern_mode="regex")
    allow_patterns: tuple[str, ...] = ()
    deny_patterns: tuple[str, ...] = ()
    ask_patterns: tuple[str, ...] = ()
    pattern_mode: str = "glob"  # "glob" or "regex"

    def _matches_any(self, tool_name: str, patterns: tuple[str, ...]) -> bool:
        """Check if tool_name matches any of the patterns."""
        for pattern in patterns:
            if self.pattern_mode == "regex":
                if re.fullmatch(pattern, tool_name):
                    return True
            else:
                if fnmatch.fnmatch(tool_name, pattern):
                    return True
        return False

    def check(self, tool_name: str) -> str:
        """Return ``'allow'``, ``'ask'``, or ``'deny'`` for a tool.

        Exact names take priority over patterns. Deny wins over ask
        wins over allow within each tier.
        """
        # Exact matches first (highest priority)
        if tool_name in self.deny:
            return "deny"
        if tool_name in self.allow:
            return "allow"
        if tool_name in self.ask:
            return "ask"

        # Pattern matches (second priority)
        if self._matches_any(tool_name, self.deny_patterns):
            return "deny"
        if self._matches_any(tool_name, self.allow_patterns):
            return "allow"
        if self._matches_any(tool_name, self.ask_patterns):
            return "ask"

        return "ask"

    def merge(self, other: PermissionPolicy) -> PermissionPolicy:
        """Merge two policies. Deny wins over ask wins over allow."""
        return PermissionPolicy(
            ask=self.ask | other.ask,
            allow=(self.allow | other.allow) - other.ask - other.deny,
            deny=self.deny | other.deny,
            allow_patterns=self.allow_patterns + other.allow_patterns,
            deny_patterns=self.deny_patterns + other.deny_patterns,
            ask_patterns=self.ask_patterns + other.ask_patterns,
            pattern_mode=other.pattern_mode if other.pattern_mode != "glob" else self.pattern_mode,
        )


class ApprovalMemory:
    """Remembers permission decisions to avoid re-asking.

    Decisions can be remembered per-tool (``"always allow bash"``) or
    per-tool+args (``"allow edit_file on main.py"``).

    Thread-safe for single-process use (GIL protected).
    """

    def __init__(self) -> None:
        self._tool_decisions: dict[str, bool] = {}
        self._specific_decisions: dict[str, bool] = {}

    @staticmethod
    def _args_key(tool_name: str, args: dict[str, Any]) -> str:
        """Create a stable hash key for tool+args combination."""
        canonical = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def remember_tool(self, tool_name: str, granted: bool) -> None:
        """Remember a blanket decision for a tool."""
        self._tool_decisions[tool_name] = granted

    def remember_specific(self, tool_name: str, args: dict[str, Any], granted: bool) -> None:
        """Remember a decision for a specific tool+args combination."""
        key = self._args_key(tool_name, args)
        self._specific_decisions[key] = granted

    def recall(self, tool_name: str, args: dict[str, Any] | None = None) -> bool | None:
        """Check if a decision was previously remembered.

        Returns True/False if remembered, None if not.
        """
        if tool_name in self._tool_decisions:
            return self._tool_decisions[tool_name]
        if args is not None:
            key = self._args_key(tool_name, args)
            if key in self._specific_decisions:
                return self._specific_decisions[key]
        return None

    def clear(self) -> None:
        """Clear all remembered decisions."""
        self._tool_decisions.clear()
        self._specific_decisions.clear()


def make_permission_callback(
    policy: PermissionPolicy,
    handler: Callable[[str, dict], bool] | None = None,
    memory: ApprovalMemory | None = None,
) -> Callable:
    """Create a before_tool callback that enforces permission policy.

    Args:
        policy: The permission policy to enforce.
        handler: Interactive approval handler ``(tool_name, args) -> bool``.
        memory: Optional approval memory for persistent decisions.
    """

    def permission_check(callback_context: Any, tool: Any, args: dict, tool_context: Any) -> Any | None:
        tool_name = getattr(tool, "name", str(tool))
        decision = policy.check(tool_name)

        if decision == "allow":
            return None
        if decision == "deny":
            return {"error": f"Tool '{tool_name}' is denied by permission policy."}

        # decision == "ask" — check memory first
        if memory is not None:
            recalled = memory.recall(tool_name, args)
            if recalled is not None:
                if recalled:
                    return None
                return {"error": f"Tool '{tool_name}' was previously denied."}

        if handler is not None:
            approved = handler(tool_name, args)
            if memory is not None:
                memory.remember_specific(tool_name, args, approved)
            if not approved:
                return {"error": f"Tool '{tool_name}' was denied by user."}
            return None

        # No handler — default allow
        return None

    return permission_check
