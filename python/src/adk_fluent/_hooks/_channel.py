"""SystemMessageChannel — transient system message injection for hooks.

Hooks that return ``HookDecision.inject(system_message="…")`` append to a
reserved key on the ADK session state: ``_adkf_hook_system_messages``. The
:class:`~adk_fluent._hooks._plugin.HookPlugin` drains this list on every
``before_model`` callback and prepends the drained messages to the outgoing
``LlmRequest`` as a system-role turn, giving hooks the Claude Code "additional
system prompt" affordance without mutating the agent's static instruction.

The channel is deliberately simple — it is a list of strings with append,
drain, and peek operations. All coordination happens via the ADK session state
dict, which means it works uniformly across in-memory, database, and Vertex
session services.
"""

from __future__ import annotations

from typing import Any

__all__ = ["SYSTEM_MESSAGE_STATE_KEY", "SystemMessageChannel"]


SYSTEM_MESSAGE_STATE_KEY: str = "_adkf_hook_system_messages"
"""Reserved ADK session state key used by the hook system message channel."""


class SystemMessageChannel:
    """Append / drain helper over an ADK session state dict.

    The channel does not hold its own list — it reads and writes
    ``state[SYSTEM_MESSAGE_STATE_KEY]``. Construct a new channel per
    invocation with the active state dict::

        channel = SystemMessageChannel(state)
        channel.append("User approved the pending edit.")
        messages = channel.drain()   # returns and clears
    """

    __slots__ = ("_state",)

    def __init__(self, state: dict[str, Any] | None) -> None:
        self._state = state

    def _bucket(self, create: bool = False) -> list[str] | None:
        if self._state is None:
            return None
        bucket = self._state.get(SYSTEM_MESSAGE_STATE_KEY)
        if bucket is None:
            if not create:
                return None
            bucket = []
            self._state[SYSTEM_MESSAGE_STATE_KEY] = bucket
        return bucket

    def append(self, message: str) -> None:
        """Queue ``message`` for the next ``before_model`` drain."""
        if not message:
            return
        bucket = self._bucket(create=True)
        if bucket is not None:
            bucket.append(message)

    def peek(self) -> list[str]:
        """Return a copy of the pending messages without clearing them."""
        bucket = self._bucket()
        return list(bucket) if bucket else []

    def drain(self) -> list[str]:
        """Return pending messages and clear the channel."""
        bucket = self._bucket()
        if not bucket:
            return []
        drained = list(bucket)
        bucket.clear()
        return drained

    @property
    def pending_count(self) -> int:
        bucket = self._bucket()
        return len(bucket) if bucket else 0
