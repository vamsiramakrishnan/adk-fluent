"""Interactive REPL loop — the agent runtime.

The REPL is the outer loop that drives a CodAct harness: read user
input → send to agent → stream response → handle tool calls → repeat.

This module provides the loop mechanics. The actual agent execution
is delegated to ADK's Runner::

    repl = HarnessRepl(agent, config)
    await repl.run()           # Interactive terminal loop
    await repl.step(prompt)    # Single turn (for embedding in UIs)

The REPL integrates:
    - Event dispatching (ADK events → HarnessEvents)
    - Permission checking (tool approval)
    - Auto-compression (context management)
    - Hook firing (user-defined scripts)
    - Git checkpoints (undo support)
    - Artifact tracking
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._harness._compression import ContextCompressor
from adk_fluent._harness._dispatcher import EventDispatcher
from adk_fluent._harness._events import (
    CompressionTriggered,
    HarnessEvent,
    TextChunk,
    TurnComplete,
)
from adk_fluent._harness._hooks import HookRegistry

__all__ = ["HarnessRepl", "ReplConfig"]


@dataclass
class ReplConfig:
    """Configuration for the REPL loop.

    Args:
        prompt_prefix: The prompt shown to the user (default: "> ").
        welcome_message: Message shown at startup.
        exit_commands: Commands that exit the REPL.
        max_turns: Maximum turns before auto-exit (0 = unlimited).
        auto_checkpoint: Create git checkpoints before tool calls.
    """

    prompt_prefix: str = "> "
    welcome_message: str | None = None
    exit_commands: frozenset[str] = frozenset({"/exit", "/quit", "exit", "quit"})
    max_turns: int = 0
    auto_checkpoint: bool = False


class HarnessRepl:
    """Interactive REPL for running a harness agent.

    The REPL handles the outer loop: reading input, dispatching to the
    agent, streaming output, and managing session state.

    Args:
        agent: An adk-fluent Agent builder (not yet built).
        dispatcher: Event dispatcher for routing HarnessEvents.
        hooks: Hook registry for user scripts.
        compressor: Context compressor for auto-compression.
        config: REPL configuration.
    """

    def __init__(
        self,
        agent: Any,
        *,
        dispatcher: EventDispatcher | None = None,
        hooks: HookRegistry | None = None,
        compressor: ContextCompressor | None = None,
        config: ReplConfig | None = None,
    ) -> None:
        self.agent = agent
        self.dispatcher = dispatcher or EventDispatcher()
        self.hooks = hooks
        self.compressor = compressor
        self.config = config or ReplConfig()
        self._turn_count = 0
        self._running = False

    async def run(
        self,
        *,
        input_fn: Callable[[], str] | None = None,
        output_fn: Callable[[str], None] | None = None,
    ) -> None:
        """Run the interactive REPL loop.

        Args:
            input_fn: Custom input function (default: stdin).
            output_fn: Custom output function (default: stdout).
        """
        _input = input_fn or (lambda: input(self.config.prompt_prefix))
        _output = output_fn or (lambda s: sys.stdout.write(s))

        if self.config.welcome_message:
            _output(self.config.welcome_message + "\n")

        self._running = True
        while self._running:
            try:
                user_input = _input()
            except (EOFError, KeyboardInterrupt):
                _output("\n")
                break

            if user_input.strip() in self.config.exit_commands:
                break

            if not user_input.strip():
                continue

            async for event in self.step(user_input):
                if isinstance(event, TextChunk):
                    _output(event.text)
                elif isinstance(event, TurnComplete):
                    _output("\n")

            self._turn_count += 1
            if 0 < self.config.max_turns <= self._turn_count:
                _output(f"\n(Reached max turns: {self.config.max_turns})\n")
                break

    async def step(self, prompt: str) -> AsyncIterator[HarnessEvent]:
        """Execute a single turn and yield HarnessEvents.

        This is the core method for embedding the REPL in custom UIs.
        Each call sends a prompt to the agent and yields events as
        they occur.

        Args:
            prompt: User prompt.

        Yields:
            HarnessEvents as they occur.
        """
        # Fire pre-turn hooks
        if self.hooks:
            await self.hooks.fire("turn_start", prompt=prompt)

        # Stream agent events
        try:
            async for adk_event in self.agent.events(prompt):
                harness_events = self.dispatcher.translate(adk_event)
                for event in harness_events:
                    yield event
        except Exception as e:
            error_chunk = TextChunk(text=f"\nError: {e}\n")
            self.dispatcher.emit(error_chunk)
            yield error_chunk

        # Fire post-turn hooks
        if self.hooks:
            await self.hooks.fire("turn_complete", turn=self._turn_count)

    def stop(self) -> None:
        """Signal the REPL to stop after the current turn."""
        self._running = False

    @property
    def turn_count(self) -> int:
        """Number of completed turns."""
        return self._turn_count
