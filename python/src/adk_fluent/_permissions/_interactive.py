"""InteractiveApprovalHandler — a shipped human-in-the-loop permission handler.

The permission layer (:mod:`adk_fluent._permissions`) knows how to *ask* — a
policy returns :meth:`PermissionDecision.ask` and the :class:`PermissionPlugin`
defers to an installed handler. What was missing was a batteries-included
handler: until now every user had to hand-write a :data:`PermissionHandler`
from scratch and bridge it to a UI by themselves.

:class:`InteractiveApprovalHandler` is that shipped handler. It:

1. Receives the ``ask`` decision the policy produced (tool name + args +
   suggested prompt).
2. Renders an approval **request** and a matching ``UI.confirm`` surface
   ("Run ``bash``(...)?") so any front-end can display the same dialog the
   console flow uses.
3. Asks a pluggable **responder** ``responder(request) -> bool | ApprovalVerdict``
   for the verdict. The default responder is a console ``input()`` prompt for
   real CLI use; tests inject a fake responder so no real stdin/human is
   required.
4. Optionally records the verdict in an :class:`ApprovalMemory`. A verdict of
   :data:`ApprovalVerdict.ALWAYS` calls :meth:`ApprovalMemory.remember_tool`
   so the *same memory* short-circuits the next ``ask`` for that tool before
   the handler is even consulted (the plugin's tool-level recall wins over the
   specific recall).

The handler is callable with the exact :data:`PermissionHandler` signature
``(tool_name, tool_args, decision) -> bool`` so it drops straight into
``H.permission_plugin(policy=..., handler=UI.approval(responder=fn))``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._permissions._decision import PermissionDecision
from adk_fluent._permissions._memory import ApprovalMemory

__all__ = [
    "ApprovalRequest",
    "ApprovalVerdict",
    "InteractiveApprovalHandler",
    "Responder",
]


class ApprovalVerdict:
    """String constants a responder may return instead of a plain ``bool``.

    ``ALLOW`` / ``DENY`` are one-shot decisions for this call only.
    ``ALWAYS`` / ``NEVER`` are remembered for every future call of the tool
    (via :meth:`ApprovalMemory.remember_tool`) when a memory is wired.
    """

    ALLOW: str = "allow"
    DENY: str = "deny"
    ALWAYS: str = "always"
    NEVER: str = "never"

    _ALLOWING = frozenset({ALLOW, ALWAYS})
    _REMEMBERED = frozenset({ALWAYS, NEVER})


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """A single approval request handed to the responder.

    Carries everything a console prompt or a UI surface needs to render the
    question, plus the compiled ``UI.confirm`` surface itself.
    """

    tool_name: str
    tool_args: dict[str, Any]
    prompt: str
    surface: Any  # UISurface — typed Any to avoid a hard import cycle with _ui.
    decision: PermissionDecision = field(repr=False, default=None)  # type: ignore[assignment]


# A responder receives the request and returns either a bool (allow/deny) or
# an ApprovalVerdict string (allow/deny/always/never).
Responder = Callable[[ApprovalRequest], "bool | str"]


def _format_args(args: dict[str, Any]) -> str:
    """Render ``{"path": "/x", "n": 3}`` as ``path='/x', n=3`` for a prompt."""
    if not args:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def _default_message(tool_name: str, tool_args: dict[str, Any], prompt: str) -> str:
    """Build the human-facing approval message.

    Prefers the policy's suggested ``prompt``; otherwise synthesises
    ``Run `bash`(path='/x')?``.
    """
    if prompt:
        return prompt
    rendered = _format_args(tool_args)
    return f"Run `{tool_name}`({rendered})?"


def _console_responder(request: ApprovalRequest) -> str:
    """Default responder: a blocking console prompt for real CLI use.

    Returns an :class:`ApprovalVerdict` string. ``y``/``yes`` → allow,
    ``a``/``always`` → always, ``n``/``no``/anything-else → deny.
    """
    answer = input(f"{request.prompt} [y]es / [n]o / [a]lways: ").strip().lower()
    if answer in {"a", "always"}:
        return ApprovalVerdict.ALWAYS
    if answer in {"y", "yes"}:
        return ApprovalVerdict.ALLOW
    return ApprovalVerdict.DENY


class InteractiveApprovalHandler:
    """A shipped, UI-bridged :data:`PermissionHandler`.

    Usage::

        from adk_fluent import UI, H

        handler = UI.approval(responder=my_responder, memory=mem)
        plugin = H.permission_plugin(policy=policy, handler=handler, memory=mem)

    Pass the *same* :class:`ApprovalMemory` to both the handler and the plugin
    so an "always" verdict short-circuits future asks.

    Args:
        responder: ``responder(ApprovalRequest) -> bool | ApprovalVerdict``.
            Defaults to a console ``input()`` prompt.
        memory: Optional :class:`ApprovalMemory`. When supplied, ``always`` /
            ``never`` verdicts are persisted via
            :meth:`ApprovalMemory.remember_tool`.
        message: Optional ``message(tool_name, tool_args, prompt) -> str`` to
            customise the rendered question.
    """

    def __init__(
        self,
        *,
        responder: Responder | None = None,
        memory: ApprovalMemory | None = None,
        message: Callable[[str, dict[str, Any], str], str] | None = None,
    ) -> None:
        self._responder: Responder = responder or _console_responder
        self._memory = memory
        self._message = message or _default_message

    @property
    def memory(self) -> ApprovalMemory | None:
        return self._memory

    # ------------------------------------------------------------------
    # Surface rendering
    # ------------------------------------------------------------------

    def build_request(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        decision: PermissionDecision | None = None,
    ) -> ApprovalRequest:
        """Build the :class:`ApprovalRequest` (message + confirm surface)."""
        prompt = decision.prompt if decision is not None else ""
        message = self._message(tool_name, dict(tool_args), prompt)
        # Import lazily to avoid an import cycle (_ui imports this module).
        from adk_fluent._ui import UI

        surface = UI.confirm(
            message,
            yes="Allow",
            no="Deny",
            yes_action="approval_allow",
            no_action="approval_deny",
        )
        return ApprovalRequest(
            tool_name=tool_name,
            tool_args=dict(tool_args),
            prompt=message,
            surface=surface,
            decision=decision,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------
    # PermissionHandler protocol — (tool_name, tool_args, decision) -> bool
    # ------------------------------------------------------------------

    def __call__(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        decision: PermissionDecision,
    ) -> bool:
        # A previously-remembered tool-level verdict short-circuits the prompt.
        # (The plugin also checks this, but the handler is defensive in case it
        # is invoked without the plugin's pre-check, e.g. directly in tests.)
        if self._memory is not None:
            recalled = self._memory.recall(tool_name)
            if recalled is not None:
                return recalled

        request = self.build_request(tool_name, tool_args, decision)
        verdict = self._responder(request)
        return self._resolve(tool_name, verdict)

    # ------------------------------------------------------------------
    # Verdict resolution
    # ------------------------------------------------------------------

    def _resolve(self, tool_name: str, verdict: bool | str) -> bool:
        if isinstance(verdict, bool):
            return verdict
        if not isinstance(verdict, str):
            raise TypeError(
                f"approval responder must return a bool or an ApprovalVerdict string, got {type(verdict).__name__}"
            )

        normalised = verdict.strip().lower()
        if normalised not in {
            ApprovalVerdict.ALLOW,
            ApprovalVerdict.DENY,
            ApprovalVerdict.ALWAYS,
            ApprovalVerdict.NEVER,
        }:
            raise ValueError(f"unknown approval verdict: {verdict!r}")

        granted = normalised in ApprovalVerdict._ALLOWING
        if normalised in ApprovalVerdict._REMEMBERED and self._memory is not None:
            self._memory.remember_tool(tool_name, granted)
        return granted
