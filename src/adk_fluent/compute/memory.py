"""In-memory implementations of compute protocols.

These are the default implementations used for testing and development.
No persistence — all data is lost when the process exits.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

__all__ = [
    "InMemoryStateStore",
    "InMemoryArtifactStore",
    "LocalToolRuntime",
]


class InMemoryStateStore:
    """Dict-based state store for testing and development.

    No persistence — all state is lost when the process exits.
    Thread-safe via asyncio (single-threaded by nature).
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._namespaces: dict[str, list[str]] = {}

    async def create(self, namespace: str, **initial_state: Any) -> str:
        """Create a new session with optional initial state."""
        session_id = uuid4().hex[:16]
        self._sessions[session_id] = dict(initial_state)
        self._namespaces.setdefault(namespace, []).append(session_id)
        return session_id

    async def load(self, session_id: str) -> dict[str, Any]:
        """Load state for a session. Returns empty dict if not found."""
        return dict(self._sessions.get(session_id, {}))

    async def save(self, session_id: str, state: dict[str, Any]) -> None:
        """Save state for a session (overwrites)."""
        self._sessions[session_id] = dict(state)

    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        self._sessions.pop(session_id, None)
        for ns_sessions in self._namespaces.values():
            if session_id in ns_sessions:
                ns_sessions.remove(session_id)

    async def list_sessions(self, namespace: str) -> list[str]:
        """List session IDs in a namespace."""
        return list(self._namespaces.get(namespace, []))


class InMemoryArtifactStore:
    """Dict-based artifact store for testing and development.

    Tracks versions — each save increments the version counter.
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, list[tuple[bytes, dict[str, Any] | None]]] = {}

    async def save(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Save an artifact. Returns version number (0-indexed)."""
        versions = self._artifacts.setdefault(key, [])
        versions.append((data, metadata))
        return len(versions) - 1

    async def load(
        self,
        key: str,
        version: int | None = None,
    ) -> bytes:
        """Load an artifact. Latest version if version is None."""
        versions = self._artifacts.get(key)
        if not versions:
            raise KeyError(f"Artifact {key!r} not found")
        if version is None:
            return versions[-1][0]
        if version < 0 or version >= len(versions):
            raise KeyError(f"Artifact {key!r} version {version} not found")
        return versions[version][0]

    async def list_versions(self, key: str) -> list[int]:
        """List available versions for an artifact."""
        versions = self._artifacts.get(key, [])
        return list(range(len(versions)))

    async def delete(self, key: str, version: int | None = None) -> None:
        """Delete an artifact (all versions if version is None)."""
        if version is None:
            self._artifacts.pop(key, None)
        else:
            versions = self._artifacts.get(key, [])
            if 0 <= version < len(versions):
                versions[version] = (b"", None)  # Tombstone


class LocalToolRuntime:
    """Execute tools in the current process.

    This is the default tool runtime — simply calls the function directly.
    For sandboxed or remote execution, use other ToolRuntime implementations.
    """

    async def execute(
        self,
        tool_name: str,
        fn: Any,
        args: dict[str, Any],
    ) -> Any:
        """Execute a tool function. Handles both sync and async callables."""
        result = fn(**args)
        if asyncio.iscoroutine(result):
            return await result
        return result
