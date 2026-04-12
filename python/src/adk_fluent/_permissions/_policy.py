"""PermissionPolicy — declarative rules + mode for permission decisions.

A ``PermissionPolicy`` is a pure data object that knows how to translate a
tool name + tool input into a :class:`PermissionDecision`. It composes with
other policies via :meth:`merge`, and is consumed by the
:class:`~adk_fluent._permissions._plugin.PermissionPlugin` at runtime.

Design rules
------------

1. **Deny always wins.** An explicit deny rule (name or pattern) short-circuits
   every other consideration. The only way to reverse a deny is to build a new
   policy without it.
2. **Explicit allow beats the mode.** If a tool is in ``allow`` it runs even
   when the mode would otherwise have asked.
3. **Mode is the fallback, not an override.** Modes set the posture for
   unknown tools (neither explicitly allowed nor explicitly denied).
4. **Plan mode denies mutating tools outright.** Even if a mutating tool is in
   ``allow``, plan mode denies it — the whole point of plan mode is to prove
   the agent can describe its plan without side effects.
5. **Arguments are never inspected by the policy itself.** Content-level
   filtering (file path globs, command substrings) belongs in user-registered
   hook callables, not in the policy object. This keeps the policy small and
   composable.

Rule precedence for ``check(tool_name, tool_input)``::

    1. tool_name in deny               -> deny
    2. pattern matches deny_patterns   -> deny
    3. mode == BYPASS                  -> allow
    4. mode == PLAN and tool is mutating -> deny
    5. tool_name in allow              -> allow
    6. pattern matches allow_patterns  -> allow
    7. mode == ACCEPT_EDITS and tool is mutating -> allow
    8. mode == DONT_ASK                -> deny
    9. tool_name in ask                -> ask
    10. pattern matches ask_patterns   -> ask
    11. fallback                        -> ask (DEFAULT / ACCEPT_EDITS / PLAN)
                                          or deny (DONT_ASK)
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._permissions._decision import PermissionDecision
from adk_fluent._permissions._mode import ALL_MODES, PermissionMode

__all__ = ["PermissionPolicy", "DEFAULT_MUTATING_TOOLS", "DEFAULT_READ_ONLY_TOOLS"]


DEFAULT_MUTATING_TOOLS: frozenset[str] = frozenset(
    {
        "edit_file",
        "write_file",
        "apply_edit",
        "delete_file",
        "create_file",
        "move_file",
        "bash",
        "streaming_bash",
        "shell",
        "run_command",
    }
)
"""Tools that mutate state by default. Consulted by ``plan`` and
``accept_edits`` modes. Override via :attr:`PermissionPolicy.mutating_tools`."""


DEFAULT_READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "read_file",
        "list_files",
        "list_dir",
        "glob_search",
        "grep",
        "search",
        "web_search",
        "web_fetch",
    }
)
"""Tools considered read-only by default. Informational — not used by the
default precedence rules, but available to user code that wants to reason
about tool classes."""


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    """Declarative permission rules + mode.

    Policies are frozen; use :meth:`merge` or :meth:`with_mode` to derive
    new instances.

    Args:
        mode: A :class:`PermissionMode` string. Default: ``"default"``.
        allow: Tool names auto-allowed (exact match, highest priority
            besides deny).
        deny: Tool names blocked outright. Wins over every other rule.
        ask: Tool names that always require user approval.
        allow_patterns: Glob or regex patterns auto-allowed.
        deny_patterns: Glob or regex patterns denied.
        ask_patterns: Glob or regex patterns that require approval.
        pattern_mode: ``"glob"`` (default) or ``"regex"``.
        mutating_tools: Set of tool names considered mutating. Defaults to
            :data:`DEFAULT_MUTATING_TOOLS`. Used by ``plan`` and
            ``accept_edits`` modes.
    """

    mode: str = PermissionMode.DEFAULT
    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()
    ask: frozenset[str] = frozenset()
    allow_patterns: tuple[str, ...] = ()
    deny_patterns: tuple[str, ...] = ()
    ask_patterns: tuple[str, ...] = ()
    pattern_mode: str = "glob"
    mutating_tools: frozenset[str] = field(default_factory=lambda: DEFAULT_MUTATING_TOOLS)

    def __post_init__(self) -> None:
        if self.mode not in ALL_MODES:
            raise ValueError(
                f"Unknown permission mode {self.mode!r}. Valid: {sorted(ALL_MODES)}"
            )
        if self.pattern_mode not in {"glob", "regex"}:
            raise ValueError(
                f"pattern_mode must be 'glob' or 'regex', got {self.pattern_mode!r}"
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def _matches_any(self, tool_name: str, patterns: tuple[str, ...]) -> bool:
        for pattern in patterns:
            if self.pattern_mode == "regex":
                if re.fullmatch(pattern, tool_name):
                    return True
            else:
                if fnmatch.fnmatchcase(tool_name, pattern):
                    return True
        return False

    def is_mutating(self, tool_name: str) -> bool:
        """Return True if ``tool_name`` is considered mutating by this policy."""
        return tool_name in self.mutating_tools

    def check(
        self,
        tool_name: str,
        tool_input: dict[str, Any] | None = None,
    ) -> PermissionDecision:
        """Return the :class:`PermissionDecision` for ``tool_name``.

        ``tool_input`` is accepted for symmetry with Claude Agent SDK's
        ``canUseTool`` signature and for forward compatibility with
        argument-aware rules, but the default precedence does not inspect
        it. Policies that need argument inspection should subclass this or
        compose with a hook callable.
        """

        # 1. Explicit deny (name then patterns) always wins.
        if tool_name in self.deny:
            return PermissionDecision.deny(
                reason=f"Tool '{tool_name}' is in the permission deny list."
            )
        if self._matches_any(tool_name, self.deny_patterns):
            return PermissionDecision.deny(
                reason=f"Tool '{tool_name}' matches a deny pattern."
            )

        mode = self.mode

        # 2. Bypass mode allows everything else.
        if mode == PermissionMode.BYPASS:
            return PermissionDecision.allow()

        # 3. Plan mode denies mutating tools regardless of allow list.
        if mode == PermissionMode.PLAN and self.is_mutating(tool_name):
            return PermissionDecision.deny(
                reason=(
                    f"Plan mode denies mutating tool '{tool_name}'. "
                    "Describe your plan without executing side effects."
                )
            )

        # 4. Explicit allow.
        if tool_name in self.allow:
            return PermissionDecision.allow()
        if self._matches_any(tool_name, self.allow_patterns):
            return PermissionDecision.allow()

        # 5. Accept-edits auto-allows mutating tools.
        if mode == PermissionMode.ACCEPT_EDITS and self.is_mutating(tool_name):
            return PermissionDecision.allow()

        # 6. Dont-ask mode denies anything that would otherwise ask.
        if mode == PermissionMode.DONT_ASK:
            return PermissionDecision.deny(
                reason=(
                    f"Tool '{tool_name}' requires approval, but the policy is "
                    "in 'dont_ask' mode (non-interactive)."
                )
            )

        # 7. Explicit ask list.
        if tool_name in self.ask or self._matches_any(tool_name, self.ask_patterns):
            return PermissionDecision.ask(
                prompt=f"Allow tool '{tool_name}'?"
            )

        # 8. Mode-based fallback.
        if mode in {PermissionMode.DEFAULT, PermissionMode.ACCEPT_EDITS, PermissionMode.PLAN}:
            return PermissionDecision.ask(
                prompt=f"Allow tool '{tool_name}'?"
            )

        # Unreachable: all modes covered above.
        return PermissionDecision.deny(
            reason=f"Unhandled mode {mode!r} for tool '{tool_name}'"
        )

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def merge(self, other: PermissionPolicy) -> PermissionPolicy:
        """Combine two policies into a new one.

        Semantics:

        - ``deny`` unions; an entry in either side's deny list wins.
        - ``allow`` unions but is stripped of anything in the combined deny.
        - ``ask`` unions but is stripped of anything in the combined allow
          or deny.
        - Pattern tuples are concatenated.
        - ``other.mode`` wins if it differs from the default; otherwise
          ``self.mode`` wins. This lets policy chaining pick up whichever
          side explicitly sets a mode.
        - ``mutating_tools`` unions.
        - Pattern mode: if either side uses ``regex`` the result is
          ``regex``.
        """
        combined_deny = self.deny | other.deny
        combined_allow = (self.allow | other.allow) - combined_deny
        combined_ask = (self.ask | other.ask) - combined_allow - combined_deny

        if other.mode != PermissionMode.DEFAULT:
            mode = other.mode
        else:
            mode = self.mode

        pattern_mode = (
            "regex" if "regex" in {self.pattern_mode, other.pattern_mode} else "glob"
        )

        return PermissionPolicy(
            mode=mode,
            allow=combined_allow,
            deny=combined_deny,
            ask=combined_ask,
            allow_patterns=self.allow_patterns + other.allow_patterns,
            deny_patterns=self.deny_patterns + other.deny_patterns,
            ask_patterns=self.ask_patterns + other.ask_patterns,
            pattern_mode=pattern_mode,
            mutating_tools=self.mutating_tools | other.mutating_tools,
        )

    def with_mode(self, mode: str) -> PermissionPolicy:
        """Return a copy of this policy with ``mode`` replaced."""
        if mode not in ALL_MODES:
            raise ValueError(
                f"Unknown permission mode {mode!r}. Valid: {sorted(ALL_MODES)}"
            )
        return PermissionPolicy(
            mode=mode,
            allow=self.allow,
            deny=self.deny,
            ask=self.ask,
            allow_patterns=self.allow_patterns,
            deny_patterns=self.deny_patterns,
            ask_patterns=self.ask_patterns,
            pattern_mode=self.pattern_mode,
            mutating_tools=self.mutating_tools,
        )
