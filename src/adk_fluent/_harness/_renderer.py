"""Event renderer — translate HarnessEvents into display strings.

Both Claude Code and Gemini CLI render tool calls, diffs, and agent
output nicely in the terminal. This module provides a protocol and
built-in renderers that convert HarnessEvents into formatted strings.

Harness builders plug a renderer into their own I/O layer::

    renderer = PlainRenderer()
    dispatcher = H.dispatcher()
    dispatcher.subscribe(lambda e: print(renderer.render(e), end=""))

    # Or use Rich for formatted output (if installed)
    renderer = RichRenderer()
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from adk_fluent._harness._events import (
    ArtifactSaved,
    CompressionTriggered,
    GitCheckpoint,
    HarnessEvent,
    HookFired,
    PermissionRequest,
    PermissionResult,
    TextChunk,
    ToolCallEnd,
    ToolCallStart,
    TurnComplete,
)

__all__ = ["Renderer", "PlainRenderer", "RichRenderer", "JsonRenderer"]


class Renderer(Protocol):
    """Protocol for event renderers.

    Renderers convert HarnessEvents into display strings.
    They do NOT handle I/O — the caller decides where to write.
    """

    def render(self, event: HarnessEvent) -> str:
        """Render an event to a display string."""
        ...


class PlainRenderer:
    """Plain-text event renderer.

    Produces human-readable output without any formatting codes.
    Suitable for logging, piping, and simple terminals.

    Args:
        show_timing: Include duration in tool_call_end events.
        show_args: Include tool arguments in tool_call_start events.
        verbose: Show all event types (otherwise skip internal events).
    """

    def __init__(
        self,
        *,
        show_timing: bool = True,
        show_args: bool = False,
        verbose: bool = False,
    ) -> None:
        self.show_timing = show_timing
        self.show_args = show_args
        self.verbose = verbose

    def render(self, event: HarnessEvent) -> str:
        """Render an event to plain text."""
        match event:
            case TextChunk(text=text):
                return text
            case ToolCallStart(tool_name=name, args=args):
                line = f"[tool] {name}"
                if self.show_args and args:
                    line += f"({', '.join(f'{k}={v!r}' for k, v in args.items())})"
                return line + "\n"
            case ToolCallEnd(tool_name=name, duration_ms=ms):
                line = f"[done] {name}"
                if self.show_timing and ms > 0:
                    line += f" ({ms:.0f}ms)"
                return line + "\n"
            case PermissionRequest(tool_name=name):
                return f"[permission] Allow {name}? "
            case PermissionResult(tool_name=name, granted=granted):
                status = "granted" if granted else "denied"
                return f"[permission] {name}: {status}\n"
            case TurnComplete():
                return ""  # Text already emitted via TextChunk
            case GitCheckpoint(commit_sha=sha, action=action):
                if self.verbose:
                    return f"[git] {action}: {sha[:8]}\n"
                return ""
            case CompressionTriggered(token_count=tokens, threshold=threshold):
                if self.verbose:
                    return f"[compress] {tokens:,} tokens (threshold: {threshold:,})\n"
                return ""
            case HookFired(hook_name=name, exit_code=code):
                if self.verbose:
                    return f"[hook] {name} (exit {code})\n"
                return ""
            case ArtifactSaved(name=name, size_bytes=size):
                if self.verbose:
                    return f"[artifact] {name} ({size:,} bytes)\n"
                return ""
            case _:
                if self.verbose:
                    return f"[event] {event.kind}\n"
                return ""

    def handler(self) -> Callable[[HarnessEvent], None]:
        """Return a handler function suitable for ``dispatcher.subscribe()``."""
        import sys

        renderer = self

        def _handle(event: HarnessEvent) -> None:
            text = renderer.render(event)
            if text:
                sys.stdout.write(text)
                sys.stdout.flush()

        return _handle


class JsonRenderer:
    """JSON event renderer.

    Produces one JSON object per event, suitable for structured logging
    or piping to monitoring tools.
    """

    def render(self, event: HarnessEvent) -> str:
        """Render an event to a JSON line."""
        import json

        data: dict[str, Any] = {"kind": event.kind}
        match event:
            case TextChunk(text=text):
                data["text"] = text
            case ToolCallStart(tool_name=name, args=args):
                data["tool_name"] = name
                data["args"] = args
            case ToolCallEnd(tool_name=name, result=result, duration_ms=ms):
                data["tool_name"] = name
                data["result"] = result[:200]  # Truncate
                data["duration_ms"] = ms
            case TurnComplete(response=resp, token_count=tokens):
                data["response_length"] = len(resp)
                data["token_count"] = tokens
            case _:
                # Include all dataclass fields
                for field_name in event.__dataclass_fields__:
                    if field_name != "kind":
                        data[field_name] = getattr(event, field_name)
        return json.dumps(data) + "\n"


class RichRenderer:
    """Rich-formatted event renderer.

    Uses the ``rich`` library for colored, formatted terminal output.
    Falls back to ``PlainRenderer`` if ``rich`` is not installed.

    Args:
        show_timing: Include duration in tool events.
        show_args: Include tool arguments.
    """

    def __init__(self, *, show_timing: bool = True, show_args: bool = False) -> None:
        self.show_timing = show_timing
        self.show_args = show_args
        self._fallback: PlainRenderer | None = None
        try:
            import rich  # noqa: F401  # pyright: ignore[reportMissingImports]

            self._has_rich = True
        except ImportError:
            self._has_rich = False
            self._fallback = PlainRenderer(show_timing=show_timing, show_args=show_args)

    def render(self, event: HarnessEvent) -> str:
        """Render an event with Rich markup (or plain text fallback)."""
        if not self._has_rich:
            assert self._fallback is not None
            return self._fallback.render(event)

        match event:
            case TextChunk(text=text):
                return text
            case ToolCallStart(tool_name=name, args=args):
                line = f"[bold cyan]⚡ {name}[/]"
                if self.show_args and args:
                    line += f" [dim]({', '.join(f'{k}={v!r}' for k, v in args.items())})[/]"
                return line + "\n"
            case ToolCallEnd(tool_name=name, duration_ms=ms):
                line = f"[green]✓ {name}[/]"
                if self.show_timing and ms > 0:
                    line += f" [dim]({ms:.0f}ms)[/]"
                return line + "\n"
            case PermissionRequest(tool_name=name):
                return f"[bold yellow]🔒 Allow {name}?[/] "
            case _:
                return ""
