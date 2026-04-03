"""Hook system — user-configurable shell commands on harness events.

Hooks let users run custom scripts in response to harness events,
similar to git hooks or Claude Code's hook system::

    hooks = HookRegistry()
    hooks.on("tool_call_start", "echo 'Tool: {tool_name}' >> /tmp/audit.log")
    hooks.on("turn_complete", "./scripts/post-turn.sh")

    # Fire hooks
    await hooks.fire("tool_call_start", tool_name="bash", args={"command": "ls"})

Hook scripts receive event data as environment variables prefixed with
``HARNESS_``:
    - ``HARNESS_EVENT`` — event kind
    - ``HARNESS_TOOL_NAME`` — tool name (for tool events)
    - ``HARNESS_WORKSPACE`` — workspace path
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from typing import Any

from adk_fluent._harness._events import HookFired

__all__ = ["HookRegistry", "HookSpec"]


@dataclass(frozen=True, slots=True)
class HookSpec:
    """A single hook registration."""

    event: str
    command: str
    timeout: int = 30
    blocking: bool = False  # If True, waits for completion


class HookRegistry:
    """Registry of user-defined hooks triggered by harness events.

    Thread-safe for adds; fires should happen on one thread/task.
    """

    def __init__(self, workspace: str | None = None) -> None:
        self._hooks: dict[str, list[HookSpec]] = {}
        self.workspace = workspace

    def on(
        self,
        event: str,
        command: str,
        *,
        timeout: int = 30,
        blocking: bool = False,
    ) -> HookRegistry:
        """Register a hook for an event kind.

        Args:
            event: Event kind to trigger on (e.g., "tool_call_start").
            command: Shell command to execute. Supports ``{key}`` placeholders.
            timeout: Maximum execution time in seconds.
            blocking: If True, wait for hook to complete before continuing.

        Returns:
            Self for chaining.
        """
        spec = HookSpec(event=event, command=command, timeout=timeout, blocking=blocking)
        self._hooks.setdefault(event, []).append(spec)
        return self

    def on_tool_start(self, command: str, **kwargs: Any) -> HookRegistry:
        """Shorthand for ``.on("tool_call_start", ...)``.

        The command can use ``{tool_name}`` and ``{args}`` placeholders.
        """
        return self.on("tool_call_start", command, **kwargs)

    def on_tool_end(self, command: str, **kwargs: Any) -> HookRegistry:
        """Shorthand for ``.on("tool_call_end", ...)``.

        The command can use ``{tool_name}`` and ``{result}`` placeholders.
        """
        return self.on("tool_call_end", command, **kwargs)

    def on_turn(self, command: str, **kwargs: Any) -> HookRegistry:
        """Shorthand for ``.on("turn_complete", ...)``."""
        return self.on("turn_complete", command, **kwargs)

    def fire_sync(self, event: str, **context: Any) -> list[HookFired]:
        """Fire all hooks for an event synchronously.

        Args:
            event: Event kind.
            **context: Event-specific data passed as env vars and placeholders.

        Returns:
            List of HookFired events for reporting.
        """
        hooks = self._hooks.get(event, [])
        results: list[HookFired] = []
        for hook in hooks:
            result = self._execute_hook(hook, context)
            results.append(result)
        return results

    async def fire(self, event: str, **context: Any) -> list[HookFired]:
        """Fire all hooks for an event asynchronously.

        Blocking hooks are awaited; non-blocking hooks are fire-and-forget.
        """
        hooks = self._hooks.get(event, [])
        results: list[HookFired] = []
        tasks = []
        for hook in hooks:
            if hook.blocking:
                result = await self._execute_hook_async(hook, context)
                results.append(result)
            else:
                task = asyncio.create_task(self._execute_hook_async(hook, context))
                tasks.append((hook, task))

        for hook, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=hook.timeout)
                results.append(result)
            except TimeoutError:
                results.append(
                    HookFired(
                        hook_name=hook.command,
                        trigger=hook.event,
                        exit_code=-1,
                    )
                )
        return results

    def _execute_hook(self, hook: HookSpec, context: dict[str, Any]) -> HookFired:
        """Execute a single hook synchronously."""
        command = hook.command
        # Substitute placeholders
        for key, value in context.items():
            command = command.replace(f"{{{key}}}", str(value))

        env = self._build_env(hook.event, context)
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                cwd=self.workspace,
                env=env,
            )
            return HookFired(
                hook_name=hook.command,
                trigger=hook.event,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return HookFired(hook_name=hook.command, trigger=hook.event, exit_code=-1)
        except Exception:
            return HookFired(hook_name=hook.command, trigger=hook.event, exit_code=-2)

    async def _execute_hook_async(self, hook: HookSpec, context: dict[str, Any]) -> HookFired:
        """Execute a single hook asynchronously."""
        command = hook.command
        for key, value in context.items():
            command = command.replace(f"{{{key}}}", str(value))

        env = self._build_env(hook.event, context)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
                env=env,
            )
            await asyncio.wait_for(proc.wait(), timeout=hook.timeout)
            return HookFired(
                hook_name=hook.command,
                trigger=hook.event,
                exit_code=proc.returncode or 0,
            )
        except TimeoutError:
            return HookFired(hook_name=hook.command, trigger=hook.event, exit_code=-1)
        except Exception:
            return HookFired(hook_name=hook.command, trigger=hook.event, exit_code=-2)

    def _build_env(self, event: str, context: dict[str, Any]) -> dict[str, str]:
        """Build environment variables for hook execution."""
        env = dict(os.environ)
        env["HARNESS_EVENT"] = event
        if self.workspace:
            env["HARNESS_WORKSPACE"] = self.workspace
        for key, value in context.items():
            env[f"HARNESS_{key.upper()}"] = str(value)
        return env

    @property
    def registered_events(self) -> list[str]:
        """List event kinds that have registered hooks."""
        return list(self._hooks.keys())
