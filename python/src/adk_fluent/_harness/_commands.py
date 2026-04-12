"""Slash command registry — user-defined /commands for the REPL.

Harnesses like Claude Code and Gemini CLI support ``/command`` shortcuts
that the user types directly. This module provides the dispatch registry
that maps command names to handlers::

    commands = CommandRegistry()
    commands.register("clear", lambda args: session.clear())
    commands.register("model", lambda args: set_model(args))
    commands.register("help", lambda args: show_help())

    # In the REPL loop
    if user_input.startswith("/"):
        result = commands.dispatch(user_input)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["CommandRegistry", "CommandSpec"]


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Specification for a slash command."""

    name: str
    handler: Callable[[str], str]
    description: str = ""
    usage: str = ""


class CommandRegistry:
    """Registry of slash commands with dispatch.

    Commands are named with a leading ``/`` (stored without it).
    The registry parses user input, finds the matching handler,
    and calls it with the remaining arguments.

    Args:
        prefix: Command prefix character (default: "/").
    """

    def __init__(self, *, prefix: str = "/") -> None:
        self._commands: dict[str, CommandSpec] = {}
        self.prefix = prefix

    def register(
        self,
        name: str,
        handler: Callable[[str], str],
        *,
        description: str = "",
        usage: str = "",
    ) -> CommandRegistry:
        """Register a slash command.

        Args:
            name: Command name (without prefix).
            handler: Function taking args string, returning response.
            description: Human-readable description.
            usage: Usage example (e.g., "/model gemini-2.5-pro").

        Returns:
            Self for chaining.
        """
        self._commands[name] = CommandSpec(
            name=name,
            handler=handler,
            description=description,
            usage=usage or f"{self.prefix}{name}",
        )
        return self

    def is_command(self, text: str) -> bool:
        """Check if text starts with the command prefix."""
        return text.strip().startswith(self.prefix)

    def dispatch(self, text: str) -> str | None:
        """Parse and dispatch a command.

        Args:
            text: Full user input (e.g., "/model gemini-2.5-pro").

        Returns:
            Handler result string, or None if not a recognized command.
        """
        stripped = text.strip()
        if not stripped.startswith(self.prefix):
            return None

        without_prefix = stripped[len(self.prefix) :]
        parts = without_prefix.split(maxsplit=1)
        if not parts:
            return None

        name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        spec = self._commands.get(name)
        if spec is None:
            available = ", ".join(sorted(self._commands.keys()))
            return f"Unknown command: {self.prefix}{name}. Available: {available}"

        return spec.handler(args)

    def help_text(self) -> str:
        """Generate help text listing all commands."""
        if not self._commands:
            return "No commands registered."

        lines = ["Available commands:"]
        for name in sorted(self._commands):
            spec = self._commands[name]
            desc = f" — {spec.description}" if spec.description else ""
            lines.append(f"  {self.prefix}{name}{desc}")
        return "\n".join(lines)

    def list_commands(self) -> list[CommandSpec]:
        """Return all registered command specs."""
        return list(self._commands.values())

    @property
    def size(self) -> int:
        """Number of registered commands."""
        return len(self._commands)
