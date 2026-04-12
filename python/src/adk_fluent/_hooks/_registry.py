"""HookRegistry — user-facing registry of hook callables and shell commands.

A ``HookRegistry`` collects :class:`HookEntry` records and produces a single
:class:`~adk_fluent._hooks._plugin.HookPlugin` that dispatches them. Typical
usage::

    hooks = (
        H.hooks(workspace="/project")
        .on("pre_tool_use", block_rm_rf, match=HookMatcher.for_tool(
            "pre_tool_use", "bash", command="rm -rf*"))
        .on("post_tool_use", lint_after_edit, match=HookMatcher.for_tool(
            "post_tool_use", "edit_file", file_path="*.py"))
        .shell("post_tool_use", "ruff check {tool_input[file_path]}",
               match=HookMatcher.for_tool("post_tool_use", "edit_file"))
        .on("user_prompt_submit", log_prompt)
    )

    app = App(...).plugin(hooks.as_plugin())

Registry methods are chainable; ``.merge(other)`` produces a new registry that
contains entries from both sides.

Two entry kinds are supported:

- **Callable entries** added via ``.on(event, fn, match=...)``. The callable
  receives a :class:`HookContext` and returns a :class:`HookDecision`. Sync and
  async callables are both accepted.

- **Shell entries** added via ``.shell(event, command, match=..., timeout=..., blocking=...)``.
  The command is executed via ``asyncio.create_subprocess_shell``. Shell entries
  are notification-only: they always resolve to ``HookDecision.allow()`` and
  their exit code is surfaced through the event bus as a ``HookFired`` event.
  Shell commands support ``{key}`` placeholders drawn from the hook context
  fields (``{tool_name}``, ``{event}``, ``{agent_name}``, etc.) and
  ``{tool_input[...]}`` dotted access into the tool arguments.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import os
import shlex
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._hooks._decision import HookDecision
from adk_fluent._hooks._events import HookContext
from adk_fluent._hooks._matcher import HookMatcher

__all__ = ["HookEntry", "HookRegistry", "HookCallable"]


HookCallable = Callable[[HookContext], HookDecision | Awaitable[HookDecision] | None]
"""A hook callable. Must accept a :class:`HookContext` and return a
:class:`HookDecision`. Sync and async both supported. Returning ``None`` is
treated as :meth:`HookDecision.allow`."""


@dataclass(frozen=True, slots=True)
class HookEntry:
    """A single registered hook.

    Exactly one of ``fn`` or ``command`` is populated:

    - ``fn`` entries run the callable with a ``HookContext`` and return its
      :class:`HookDecision`.
    - ``command`` entries run a shell command and always resolve to
      :meth:`HookDecision.allow`.
    """

    matcher: HookMatcher
    fn: HookCallable | None = None
    command: str | None = None
    name: str = ""
    timeout: float = 30.0
    blocking: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fn is None and self.command is None:
            raise ValueError("HookEntry requires either fn or command")
        if self.fn is not None and self.command is not None:
            raise ValueError("HookEntry cannot have both fn and command")


class HookRegistry:
    """User-facing registry of hook entries.

    Thread-safe for adds. The registry is event-partitioned internally for
    O(1) event lookup during dispatch.
    """

    def __init__(self, workspace: str | None = None) -> None:
        self._entries_by_event: dict[str, list[HookEntry]] = {}
        self._workspace = workspace

    @property
    def workspace(self) -> str | None:
        return self._workspace

    # -------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------

    def on(
        self,
        event: str,
        fn: HookCallable,
        *,
        match: HookMatcher | None = None,
        name: str | None = None,
    ) -> HookRegistry:
        """Register a callable hook for ``event``.

        Args:
            event: Canonical event name (see :class:`HookEvent`).
            fn: Hook callable. Receives a :class:`HookContext`, returns a
                :class:`HookDecision` (or ``None`` for allow).
            match: Optional matcher for additional filtering. If omitted, the
                hook fires for every context of ``event``.
            name: Optional display name for introspection and events.
        """
        matcher = match or HookMatcher.any(event)
        if matcher.event != event:
            raise ValueError(f"HookMatcher event {matcher.event!r} must equal {event!r}")
        entry = HookEntry(
            matcher=matcher,
            fn=fn,
            name=name or getattr(fn, "__name__", "hook"),
        )
        self._entries_by_event.setdefault(event, []).append(entry)
        return self

    def shell(
        self,
        event: str,
        command: str,
        *,
        match: HookMatcher | None = None,
        timeout: float = 30.0,
        blocking: bool = False,
        name: str | None = None,
    ) -> HookRegistry:
        """Register a shell-command hook for ``event``.

        The command supports ``{key}`` placeholder substitution drawn from
        the hook context: ``{event}``, ``{tool_name}``, ``{agent_name}``,
        ``{session_id}``, ``{invocation_id}``, ``{user_message}``, and
        ``{tool_input[key]}`` for dotted access into tool arguments.

        Args:
            event: Canonical event name.
            command: Shell command to execute.
            match: Optional matcher.
            timeout: Maximum execution time in seconds.
            blocking: If True, the plugin awaits completion before continuing.
                If False (default), the command is fire-and-forget via
                ``asyncio.create_task``. Shell hooks never block the tool call
                — ``blocking`` only controls whether the dispatch awaits the
                subprocess exit.
            name: Optional display name.
        """
        matcher = match or HookMatcher.any(event)
        if matcher.event != event:
            raise ValueError(f"HookMatcher event {matcher.event!r} must equal {event!r}")
        entry = HookEntry(
            matcher=matcher,
            command=command,
            name=name or "shell_hook",
            timeout=timeout,
            blocking=blocking,
        )
        self._entries_by_event.setdefault(event, []).append(entry)
        return self

    def as_plugin(self, name: str = "adkf_hook_plugin") -> Any:
        """Return an ADK ``BasePlugin`` that dispatches this registry.

        Install via ``App(...).plugin(registry.as_plugin())`` or by passing
        to the harness builder: ``agent.harness(hooks=registry)``.
        """
        from adk_fluent._hooks._plugin import HookPlugin

        return HookPlugin(self, name=name)

    def merge(self, other: HookRegistry) -> HookRegistry:
        """Return a new registry containing entries from ``self`` and ``other``."""
        merged = HookRegistry(workspace=self._workspace or other._workspace)
        for event, entries in self._entries_by_event.items():
            merged._entries_by_event.setdefault(event, []).extend(entries)
        for event, entries in other._entries_by_event.items():
            merged._entries_by_event.setdefault(event, []).extend(entries)
        return merged

    # -------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------

    def entries_for(self, event: str) -> list[HookEntry]:
        """Return a snapshot of entries registered for ``event``."""
        return list(self._entries_by_event.get(event, ()))

    @property
    def registered_events(self) -> list[str]:
        return list(self._entries_by_event.keys())

    def __repr__(self) -> str:
        counts = {e: len(v) for e, v in self._entries_by_event.items()}
        return f"HookRegistry(workspace={self._workspace!r}, entries={counts})"

    # -------------------------------------------------------------------
    # Dispatch
    # -------------------------------------------------------------------

    async def dispatch(self, ctx: HookContext) -> HookDecision:
        """Run every matching entry for ``ctx.event`` and return the decision.

        Entries run in registration order. Iteration stops at the first
        terminal decision (``deny`` / ``replace`` / ``ask``). Non-terminal
        decisions are folded together:

        - ``inject`` is collected and appended to the final decision so the
          plugin can drain them to the system message channel.
        - ``modify`` rewrites the tool input slot on ``ctx`` and continues so
          downstream hooks see the rewritten args.

        Returns:
            The final collapsed decision. Always returns a ``HookDecision``
            (never ``None``) — callers can treat ``.is_allow`` as "pass".
        """
        entries = self._entries_by_event.get(ctx.event, ())
        if not entries:
            return HookDecision.allow()

        final: HookDecision = HookDecision.allow()
        pending_injects: list[str] = []

        for entry in entries:
            if not entry.matcher.matches(ctx):
                continue
            decision = await self._run_entry(entry, ctx)
            if decision.is_allow:
                continue
            if decision.action == "inject":
                pending_injects.append(decision.system_message)
                continue
            if decision.action == "modify":
                if decision.tool_input is not None and ctx.tool_input is not None:
                    ctx.tool_input.clear()
                    ctx.tool_input.update(decision.tool_input)
                continue
            # Terminal: deny / replace / ask
            final = decision
            break

        if pending_injects:
            # Attach pending injects to the final decision's metadata so the
            # plugin can drain them to the SystemMessageChannel after the
            # primary decision is applied.
            final = HookDecision(
                action=final.action,
                reason=final.reason,
                tool_input=final.tool_input,
                output=final.output,
                prompt=final.prompt,
                system_message=final.system_message,
                metadata={**final.metadata, "pending_injects": pending_injects},
            )
        return final

    async def _run_entry(self, entry: HookEntry, ctx: HookContext) -> HookDecision:
        if entry.command is not None:
            return await self._run_shell(entry, ctx)
        assert entry.fn is not None
        try:
            result = entry.fn(ctx)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            return HookDecision.deny(reason=f"hook {entry.name!r} raised: {exc}")
        if result is None:
            return HookDecision.allow()
        if not isinstance(result, HookDecision):
            return HookDecision.deny(
                reason=f"hook {entry.name!r} must return HookDecision, got {type(result).__name__}"
            )
        return result

    async def _run_shell(self, entry: HookEntry, ctx: HookContext) -> HookDecision:
        assert entry.command is not None
        command = _render_shell_command(entry.command, ctx)
        env = _build_shell_env(ctx, self._workspace)

        async def _execute() -> int:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._workspace,
                env=env,
            )
            try:
                await asyncio.wait_for(proc.wait(), timeout=entry.timeout)
            except TimeoutError:
                with _suppress():
                    proc.kill()
                return -1
            return proc.returncode if proc.returncode is not None else 0

        if entry.blocking:
            try:
                exit_code = await _execute()
            except Exception:
                exit_code = -2
            return HookDecision(
                action="allow",
                metadata={"shell_exit_code": exit_code, "shell_command": command},
            )

        # Fire-and-forget: schedule without awaiting.
        try:
            asyncio.create_task(_execute())
        except RuntimeError:
            # No running loop — fall back to blocking subprocess.
            with contextlib.suppress(Exception):
                subprocess.run(
                    command,
                    shell=True,
                    cwd=self._workspace,
                    env=env,
                    timeout=entry.timeout,
                    capture_output=True,
                )
        return HookDecision.allow()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _suppress:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: Any) -> bool:
        return True


def _render_shell_command(template: str, ctx: HookContext) -> str:
    """Substitute ``{key}`` and ``{tool_input[k]}`` placeholders in ``template``.

    Missing keys substitute to empty strings. Values are shell-quoted so that
    spaces and special characters do not break the resulting command.
    """
    tool_input = ctx.tool_input or {}
    fields: dict[str, str] = {
        "event": ctx.event,
        "tool_name": ctx.tool_name or "",
        "agent_name": ctx.agent_name or "",
        "session_id": ctx.session_id or "",
        "invocation_id": ctx.invocation_id or "",
        "user_message": ctx.user_message or "",
        "model": ctx.model or "",
        "error": str(ctx.error) if ctx.error else "",
    }

    # Also populate top-level tool_input keys directly for convenience.
    for key, value in tool_input.items():
        fields.setdefault(key, str(value))

    out = template
    # {tool_input[key]} dotted access
    import re

    def _tool_input_sub(match: re.Match[str]) -> str:
        key = match.group(1)
        return shlex.quote(str(tool_input.get(key, "")))

    out = re.sub(r"\{tool_input\[([^\]]+)\]\}", _tool_input_sub, out)

    # Plain {key} substitution with shell quoting
    def _plain_sub(match: re.Match[str]) -> str:
        key = match.group(1)
        return shlex.quote(fields.get(key, ""))

    out = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", _plain_sub, out)
    return out


def _build_shell_env(ctx: HookContext, workspace: str | None) -> dict[str, str]:
    env = dict(os.environ)
    env["ADKF_HOOK_EVENT"] = ctx.event
    if workspace:
        env["ADKF_HOOK_WORKSPACE"] = workspace
    if ctx.tool_name:
        env["ADKF_HOOK_TOOL_NAME"] = ctx.tool_name
    if ctx.agent_name:
        env["ADKF_HOOK_AGENT_NAME"] = ctx.agent_name
    if ctx.session_id:
        env["ADKF_HOOK_SESSION_ID"] = ctx.session_id
    if ctx.invocation_id:
        env["ADKF_HOOK_INVOCATION_ID"] = ctx.invocation_id
    if ctx.user_message:
        env["ADKF_HOOK_USER_MESSAGE"] = ctx.user_message
    return env
