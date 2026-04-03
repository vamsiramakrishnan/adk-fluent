"""Persistent project memory — cross-session context files.

Claude Code has ``CLAUDE.md``, Gemini CLI has ``GEMINI.md``. This module
provides the file I/O layer. For context injection, it composes with
existing adk-fluent primitives:

- ``C.from_state(state_key)`` — inject memory into agent context
- ``C.notes(key)`` — structured scratchpad (session-scoped)
- ``.reads(state_key)`` — inject state into prompt

The ``ProjectMemory`` handles the persistence concern that these
context primitives don't cover: loading from / saving to a file that
survives across sessions.

Usage::

    mem = H.memory("/project/.agent-memory.md")

    # Compose with existing context primitives
    agent = (
        Agent("coder")
        .before_agent(mem.load_callback())
        .reads("project_memory")       # uses existing .reads() mechanism
        .after_agent(mem.save_callback())
    )

    # Or use C.from_state for finer control
    agent = (
        Agent("coder")
        .before_agent(mem.load_callback())
        .context(C.from_state("project_memory"))
    )
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["ProjectMemory"]


@dataclass(frozen=True, slots=True)
class _MemoryEntry:
    """A single memory entry with timestamp."""

    content: str
    timestamp: float


class ProjectMemory:
    """Persistent project-scoped memory file.

    Handles file I/O for a markdown memory file. Integrates with
    the agent lifecycle via callbacks that bridge the file ↔ state.
    Context injection is handled by existing primitives:
    ``.reads()``, ``C.from_state()``, or ``C.notes()``.

    Args:
        path: Path to the memory file (e.g., ``/project/.agent-memory.md``).
        state_key: State key to inject memory content into (default: ``project_memory``).
        max_entries: Maximum number of entries to keep (oldest trimmed first).
    """

    def __init__(
        self,
        path: str | Path,
        *,
        state_key: str = "project_memory",
        max_entries: int = 100,
    ) -> None:
        self.path = Path(path)
        self.state_key = state_key
        self.max_entries = max_entries
        self._entries: list[_MemoryEntry] = []

    def load(self) -> str:
        """Load memory from the file.

        Returns:
            The full memory content as a string, or empty string if
            the file doesn't exist.
        """
        if self.path.exists():
            return self.path.read_text(encoding="utf-8")
        return ""

    def save(self, content: str) -> None:
        """Save content to the memory file.

        Args:
            content: Full content to write.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")

    def append(self, entry: str) -> None:
        """Append a timestamped entry to the memory file.

        Args:
            entry: Text to append.
        """
        self._entries.append(_MemoryEntry(content=entry, timestamp=time.time()))
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries :]

        existing = self.load() if self.path.exists() else ""
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        new_line = f"\n- [{timestamp}] {entry}"
        self.save(existing + new_line)

    def load_callback(self) -> Callable:
        """Create a before_agent callback that loads memory into state.

        Stores content in ``state[self.state_key]`` so it can be
        consumed by ``.reads(key)``, ``C.from_state(key)``, or
        ``C.notes(key)`` — all existing context primitives.

        Returns:
            An ADK-compatible before_agent callback.
        """
        state_key = self.state_key
        memory = self

        def _inject_memory(callback_context: Any) -> None:
            content = memory.load()
            if content:
                state = getattr(callback_context, "state", None)
                if state is not None and hasattr(state, "__setitem__"):
                    state[state_key] = content

        return _inject_memory

    def save_callback(self, *, extract_key: str | None = None) -> Callable:
        """Create an after_agent callback that persists learnings.

        If ``extract_key`` is set, reads ``state[extract_key]`` and
        appends it to the memory file.

        Args:
            extract_key: Optional state key containing new learnings to persist.

        Returns:
            An ADK-compatible after_agent callback.
        """
        memory = self

        def _persist_memory(callback_context: Any) -> None:
            if extract_key is not None:
                state = getattr(callback_context, "state", None)
                if state is not None:
                    value = state.get(extract_key) if hasattr(state, "get") else None
                    if value:
                        memory.append(str(value))

        return _persist_memory

    def clear(self) -> None:
        """Clear the memory file and internal entries."""
        if self.path.exists():
            self.path.unlink()
        self._entries.clear()

    @property
    def exists(self) -> bool:
        """Check if the memory file exists."""
        return self.path.exists()

    def __repr__(self) -> str:
        return f"ProjectMemory({str(self.path)!r})"
