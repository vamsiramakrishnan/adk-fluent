"""PermissionDecision — structured return for permission policies.

A permission policy checks a tool call and returns a :class:`PermissionDecision`.
The decision shape mirrors Claude Agent SDK's ``canUseTool`` contract:

``allow``
    The tool may run. Optionally carries ``updated_input`` — the rewritten
    argument dict the tool should actually see. This is how policies sanitise
    arguments (strip a secret, clamp a path) before the tool executes.

``deny``
    Block the tool. The ``reason`` is surfaced to the LLM as an error so it
    can self-correct. Terminal.

``ask``
    Defer the decision to an interactive handler. The ``prompt`` is the
    question to show the user. The permission plugin runs the handler,
    records the response in the approval memory, and re-dispatches as
    allow or deny. If no handler is installed, ``ask`` is treated as
    deny with the prompt as the reason.

Unlike :class:`adk_fluent._hooks.HookDecision`, permission decisions do not
carry ``modify`` / ``replace`` / ``inject`` — those are orthogonal concerns
handled by the hook layer. A permission decision answers exactly one question:
"should this tool run, and with what arguments?".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["PermissionBehavior", "PermissionDecision"]


class PermissionBehavior:
    """Enumeration of permission outcomes (string constants)."""

    ALLOW: str = "allow"
    DENY: str = "deny"
    ASK: str = "ask"


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    """A structured permission decision.

    Use the classmethod constructors (``PermissionDecision.allow()``, etc.)
    rather than building instances directly.
    """

    behavior: str
    reason: str = ""
    updated_input: dict[str, Any] | None = None
    prompt: str = ""

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def allow(cls, *, updated_input: dict[str, Any] | None = None) -> PermissionDecision:
        """Allow the tool. Optionally rewrite its argument dict."""
        if updated_input is not None and not isinstance(updated_input, dict):
            raise TypeError("PermissionDecision.allow(updated_input=...) must be a dict")
        return cls(
            behavior=PermissionBehavior.ALLOW,
            updated_input=dict(updated_input) if updated_input is not None else None,
        )

    @classmethod
    def deny(cls, reason: str = "Denied by permission policy") -> PermissionDecision:
        """Block the tool and surface ``reason`` to the LLM."""
        return cls(behavior=PermissionBehavior.DENY, reason=reason)

    @classmethod
    def ask(cls, prompt: str = "") -> PermissionDecision:
        """Defer to an interactive handler with the given ``prompt``."""
        return cls(behavior=PermissionBehavior.ASK, prompt=prompt)

    # ------------------------------------------------------------------
    # Predicates
    # ------------------------------------------------------------------

    @property
    def is_allow(self) -> bool:
        return self.behavior == PermissionBehavior.ALLOW

    @property
    def is_deny(self) -> bool:
        return self.behavior == PermissionBehavior.DENY

    @property
    def is_ask(self) -> bool:
        return self.behavior == PermissionBehavior.ASK

    @property
    def is_terminal(self) -> bool:
        """True if this decision resolves the check without further input."""
        return self.behavior in {PermissionBehavior.ALLOW, PermissionBehavior.DENY}
