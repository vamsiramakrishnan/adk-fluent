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

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """Search memory entries by relevance.

        Uses BM25 when ``rank_bm25`` is installed, falls back to
        substring matching. Reuses the same optional dependency as
        ``ToolRegistry``.

        Args:
            query: Natural language search query.
            top_k: Maximum results to return.

        Returns:
            List of matching memory entry strings, most relevant first.
        """
        content = self.load()
        if not content:
            return []

        # Split into entries (lines starting with "- [")
        entries = []
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- ["):
                entries.append(stripped)
            elif stripped and entries:
                # Continuation of previous entry
                entries[-1] += " " + stripped

        if not entries:
            # Fall back to paragraph splitting
            entries = [p.strip() for p in content.split("\n\n") if p.strip()]

        if not entries:
            return []

        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

            corpus = [e.lower().split() for e in entries]
            bm25 = BM25Okapi(corpus)
            scores = bm25.get_scores(query.lower().split())
            ranked = sorted(zip(entries, scores), key=lambda x: x[1], reverse=True)
            return [e for e, s in ranked[:top_k] if s > 0] or entries[:top_k]
        except ImportError:
            pass

        # Substring fallback
        query_lower = query.lower()
        matches = [e for e in entries if any(w in e.lower() for w in query_lower.split())]
        return matches[:top_k] if matches else entries[:top_k]

    def search_callback(self) -> Callable:
        """Create a tool function for LLM-driven memory search.

        Returns a callable suitable for use with ``.tool()``::

            mem = H.memory("/project/.agent-memory.md")
            agent = Agent("coder").tool(mem.search_callback())
        """
        memory = self

        def search_memory(query: str) -> str:
            """Search project memory for relevant entries.

            Args:
                query: What to search for in project memory.
            """
            results = memory.search(query)
            if not results:
                return "No matching entries found in project memory."
            return "\n".join(results)

        return search_memory

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
