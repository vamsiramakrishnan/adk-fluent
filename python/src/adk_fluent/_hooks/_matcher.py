"""HookMatcher — event + tool-name regex + argument glob filter.

A ``HookMatcher`` decides whether a given :class:`HookContext` should trigger a
particular hook callable. Matching is layered:

1. ``event`` — exact string match against the firing event name.
2. ``tool_name`` — optional regex anchored match against ``ctx.tool_name``.
3. ``args`` — optional per-key ``fnmatch`` glob against ``ctx.tool_input``.
4. ``predicate`` — optional callable with full access to the context for the
   rare case the other filters are not expressive enough.

All predicates are ANDed. A matcher with no filters matches every context for
its declared event — the normal case for session-wide hooks.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from adk_fluent._hooks._events import ALL_EVENTS, HookContext

__all__ = ["HookMatcher"]


@dataclass(frozen=True, slots=True)
class HookMatcher:
    """Filter controlling which contexts a hook callable sees.

    Args:
        event: Canonical event name (see :class:`HookEvent`). Required.
        tool_name: Regex matched against ``ctx.tool_name``. The regex is
            anchored with ``re.fullmatch`` so ``"edit_file"`` matches exactly
            and ``"edit_.*"`` matches any edit tool.
        args: Per-key glob patterns matched against ``ctx.tool_input`` values.
            Values are stringified before matching. All declared keys must
            match; extra keys in the tool input are ignored.
        predicate: Optional callable taking the ``HookContext`` and returning
            a bool. Evaluated last, only if the structural filters pass.
    """

    event: str
    tool_name: str | None = None
    args: dict[str, str] = field(default_factory=dict)
    predicate: Callable[[HookContext], bool] | None = None

    def __post_init__(self) -> None:
        if self.event not in ALL_EVENTS:
            raise ValueError(
                f"Unknown hook event {self.event!r}. "
                f"Valid events: {sorted(ALL_EVENTS)}"
            )

    def matches(self, ctx: HookContext) -> bool:
        """Return True if ``ctx`` should trigger the associated hook."""
        if ctx.event != self.event:
            return False

        if self.tool_name is not None:
            name = ctx.tool_name or ""
            if not re.fullmatch(self.tool_name, name):
                return False

        if self.args:
            tool_input = ctx.tool_input or {}
            for key, pattern in self.args.items():
                value = tool_input.get(key)
                if value is None:
                    return False
                if not fnmatch.fnmatchcase(str(value), pattern):
                    return False

        if self.predicate is not None:
            try:
                if not self.predicate(ctx):
                    return False
            except Exception:
                return False

        return True

    @classmethod
    def any(cls, event: str) -> HookMatcher:
        """Match every context for ``event`` (no additional filters)."""
        return cls(event=event)

    @classmethod
    def for_tool(
        cls,
        event: str,
        tool_name: str,
        **args: Any,
    ) -> HookMatcher:
        """Shorthand for matching a specific tool by name with optional arg globs."""
        return cls(
            event=event,
            tool_name=tool_name,
            args={k: str(v) for k, v in args.items()},
        )
