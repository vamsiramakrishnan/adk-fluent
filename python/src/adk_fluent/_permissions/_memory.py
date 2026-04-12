"""ApprovalMemory — persistent record of interactive permission decisions.

A memory sits next to a :class:`PermissionPolicy` at runtime. When the policy
says "ask" and an interactive handler returns a verdict, the memory remembers
it so the user is not asked again for the same tool (or same tool+args).

Two scopes are supported:

- **Tool-level** memory: "always allow ``bash``" — applies to every invocation
  of the tool, regardless of arguments. Stored in a simple dict.
- **Tool+args** memory: "allow ``edit_file`` with ``path=main.py``" — applies
  only to the exact argument combination. Stored in a sha256-keyed dict so
  ordering and nested dicts produce stable keys.

Tool-level decisions override tool+args decisions — once a user says "always
allow bash" any previously-specific decisions are shadowed.

The memory is deliberately in-memory only. Durable storage (across process
restarts) is the job of the session store foundation (Phase 8); this module
stays lightweight and testable in isolation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = ["ApprovalMemory"]


class ApprovalMemory:
    """Session-scoped record of permission decisions.

    Thread-safe for the single-process GIL case: all mutations go through a
    dict assignment which is atomic in CPython.
    """

    def __init__(self) -> None:
        self._tool_decisions: dict[str, bool] = {}
        self._specific_decisions: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _args_key(tool_name: str, args: dict[str, Any]) -> str:
        """Return a stable short hash for a tool+args combination."""
        canonical = json.dumps(
            {"tool": tool_name, "args": args},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def remember_tool(self, tool_name: str, granted: bool) -> None:
        """Remember a blanket decision for every invocation of ``tool_name``."""
        self._tool_decisions[tool_name] = granted

    def remember_specific(
        self,
        tool_name: str,
        args: dict[str, Any],
        granted: bool,
    ) -> None:
        """Remember a decision for a specific tool+args combination."""
        self._specific_decisions[self._args_key(tool_name, args)] = granted

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def recall(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> bool | None:
        """Return the remembered decision, or ``None`` if unknown.

        Tool-level decisions take priority over tool+args decisions.
        """
        if tool_name in self._tool_decisions:
            return self._tool_decisions[tool_name]
        if args is not None:
            specific = self._specific_decisions.get(self._args_key(tool_name, args))
            if specific is not None:
                return specific
        return None

    def clear(self) -> None:
        """Drop every remembered decision."""
        self._tool_decisions.clear()
        self._specific_decisions.clear()

    def __repr__(self) -> str:
        return (
            "ApprovalMemory("
            f"tool_decisions={len(self._tool_decisions)}, "
            f"specific_decisions={len(self._specific_decisions)})"
        )
