"""HookDecision — the return protocol for hook callables.

A hook callable takes a :class:`HookContext` and returns a :class:`HookDecision`.
The decision has six variants, each mapping onto an ADK callback return
contract depending on the firing event:

``allow``
    Pass-through. Equivalent to returning ``None`` from an ADK callback. This
    is ALWAYS the correct "no opinion" return — never return an empty dict,
    because ADK uses first-**truthy**-wins and an empty dict would count as
    "I made a decision, stop calling other hooks".

``deny(reason)``
    Short-circuit with a failure. For ``pre_tool_use`` the plugin synthesizes a
    tool response dict carrying the error so the LLM sees why. For ``pre_model``
    and ``pre_agent`` it builds a terminal response with the deny reason.

``modify(tool_input=...)``
    Rewrite tool arguments before execution. Only meaningful for
    ``pre_tool_use``. The plugin mutates the ADK ``function_args`` dict in
    place (ADK passes it by reference) and returns ``None`` to continue.

``replace(output=...)``
    Short-circuit the wrapped call and use ``output`` as if the tool / model had
    produced it. For tools, ``output`` should be a dict; for models, an
    ``LlmResponse``; for agents, a ``Content`` object.

``ask(prompt=...)``
    Raise a permission request that the harness runtime handles. Until the
    runtime surfaces an approval decision this behaves as ``deny`` so the
    agent stops. The ``prompt`` is surfaced via ``H.ask_user`` or the REPL.

``inject(system_message=...)``
    Append a transient system message to the :class:`SystemMessageChannel`.
    Drained and prepended to the next ``LlmRequest`` by a built-in
    ``before_model`` hook. Composes with any other decision — returning
    ``inject`` from a ``post_tool_use`` hook is a common pattern for "tell the
    model what just changed".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["HookAction", "HookDecision"]


class HookAction:
    """Enumeration of decision actions (string constants)."""

    ALLOW: str = "allow"
    DENY: str = "deny"
    MODIFY: str = "modify"
    REPLACE: str = "replace"
    ASK: str = "ask"
    INJECT: str = "inject"


@dataclass(frozen=True, slots=True)
class HookDecision:
    """A structured decision returned by a hook callable.

    Use the classmethod constructors (``HookDecision.allow()``,
    ``.deny(reason)``, etc.) rather than building instances directly.
    """

    action: str
    reason: str = ""
    tool_input: dict[str, Any] | None = None
    output: Any = None
    prompt: str = ""
    system_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # -------------------------------------------------------------------
    # Constructors
    # -------------------------------------------------------------------

    @classmethod
    def allow(cls) -> HookDecision:
        """Pass-through — no opinion."""
        return cls(action=HookAction.ALLOW)

    @classmethod
    def deny(cls, reason: str = "Denied by hook") -> HookDecision:
        """Block the wrapped call and surface ``reason`` to the LLM."""
        return cls(action=HookAction.DENY, reason=reason)

    @classmethod
    def modify(cls, tool_input: dict[str, Any]) -> HookDecision:
        """Rewrite tool arguments. Only valid for ``pre_tool_use``."""
        if not isinstance(tool_input, dict):
            raise TypeError("HookDecision.modify requires a dict of tool arguments")
        return cls(action=HookAction.MODIFY, tool_input=dict(tool_input))

    @classmethod
    def replace(cls, output: Any) -> HookDecision:
        """Short-circuit the wrapped call and return ``output`` instead."""
        return cls(action=HookAction.REPLACE, output=output)

    @classmethod
    def ask(cls, prompt: str) -> HookDecision:
        """Raise a permission request with ``prompt``."""
        return cls(action=HookAction.ASK, prompt=prompt)

    @classmethod
    def inject(cls, system_message: str) -> HookDecision:
        """Append ``system_message`` to the system message channel."""
        return cls(action=HookAction.INJECT, system_message=system_message)

    # -------------------------------------------------------------------
    # Predicates
    # -------------------------------------------------------------------

    @property
    def is_allow(self) -> bool:
        return self.action == HookAction.ALLOW

    @property
    def is_terminal(self) -> bool:
        """True if this decision short-circuits the call (deny/replace/ask)."""
        return self.action in {HookAction.DENY, HookAction.REPLACE, HookAction.ASK}

    @property
    def is_side_effect(self) -> bool:
        """True if this decision does not alter the wrapped call's output."""
        return self.action in {HookAction.ALLOW, HookAction.INJECT}
