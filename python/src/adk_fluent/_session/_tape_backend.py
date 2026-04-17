"""Pluggable storage backends for :class:`SessionTape`.

The tape holds every event in an in-memory deque for fast in-session
reads. A :class:`TapeBackend` is a *mirror* — every recorded entry is
forwarded so it survives process restarts, crosses process boundaries,
or streams to remote consumers.

Four shapes are shipped:

- :class:`InMemoryBackend` — no-op mirror. The default when no backend
  is wired; kept as a concrete class so tests can assert type
  parametrically.
- :class:`JsonlBackend` — append-only JSONL file with line-buffered
  writes. Crash-safe at the line granularity if the OS flushes.
- :class:`NullBackend` — drops every entry; useful when the tape is
  only needed for the in-memory deque and the mirror would be wasted
  I/O.
- :class:`ChainBackend` — broadcasts each entry to multiple backends
  in order. Stops on the first write that raises; readers fall through
  to the first that returns data.

A future Redis backend lives behind the ``adk-fluent[redis]`` extra
and is intentionally not imported here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ChainBackend",
    "InMemoryBackend",
    "JsonlBackend",
    "NullBackend",
    "TapeBackend",
]


@runtime_checkable
class TapeBackend(Protocol):
    """Mirror target for every recorded tape entry.

    The backend is write-through: tapes own a fast in-memory deque and
    forward each entry to the backend for durability. Readers that need
    durable access (resume after crash, cross-process consumers) talk
    to the backend directly.

    Implementations must be thread-safe for ``append``. ``read_since``
    may return stale data as long as it is eventually consistent with
    the latest append.
    """

    def append(self, entry: dict[str, Any]) -> None:
        """Persist one entry. The ``seq`` field is already set."""

    def read_since(self, seq: int) -> list[dict[str, Any]]:
        """Return all persisted entries with ``entry["seq"] >= seq``."""

    def head(self) -> int:
        """Return ``max(seq)+1`` across persisted entries, or 0 if empty."""

    def clear(self) -> None:
        """Drop all persisted entries."""


class InMemoryBackend:
    """Default no-op mirror — the tape's deque is the only store.

    Kept as a concrete implementation so ``isinstance`` checks succeed
    and tests can detect "no backend configured" cleanly.
    """

    def append(self, entry: dict[str, Any]) -> None:  # noqa: D401 — Protocol method
        return None

    def read_since(self, seq: int) -> list[dict[str, Any]]:
        return []

    def head(self) -> int:
        return 0

    def clear(self) -> None:
        return None


class NullBackend(InMemoryBackend):
    """Explicit "discard events" backend. Semantically identical to InMemory."""


class JsonlBackend:
    """Append-only JSONL file. Crash-safe at line granularity.

    Each entry is serialized to one line and flushed (``os.fsync``
    optional via ``fsync=True``). Reads scan the file from the start
    and filter by ``seq``; fine for sessions up to a few million events.

    Args:
        path: File path. Parent directory is created on first write.
        fsync: If True, call ``os.fsync`` after each append. Safer
            but ~10x slower. Defaults to False.
    """

    def __init__(self, path: str | Path, *, fsync: bool = False) -> None:
        self._path = Path(path)
        self._fsync = fsync
        self._head: int = 0
        if self._path.exists():
            self._head = self._scan_head()

    def _scan_head(self) -> int:
        highest = -1
        with self._path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    seq = int(json.loads(line).get("seq", -1))
                except (ValueError, json.JSONDecodeError):
                    continue
                if seq > highest:
                    highest = seq
        return highest + 1

    def append(self, entry: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry) + "\n"
        # Open append-mode on every call: simple, and the kernel
        # caches the dirent so the cost is small for typical event
        # rates (<10k/s). Long-running high-rate sessions should use
        # a holding backend with a buffered writer instead.
        with self._path.open("a") as f:
            f.write(line)
            if self._fsync:
                f.flush()
                os.fsync(f.fileno())
        seq = int(entry.get("seq", self._head))
        if seq >= self._head:
            self._head = seq + 1

    def read_since(self, seq: int) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self._path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if int(entry.get("seq", -1)) >= seq:
                    out.append(entry)
        return out

    def head(self) -> int:
        return self._head

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
        self._head = 0


class ChainBackend:
    """Broadcast appends to multiple backends; read from the first hit.

    Useful for development ("mirror to memory + JSONL") and for
    production setups that want both a local cache and a remote store.
    """

    def __init__(self, *backends: TapeBackend) -> None:
        self._backends: tuple[TapeBackend, ...] = backends

    def append(self, entry: dict[str, Any]) -> None:
        for b in self._backends:
            b.append(entry)

    def read_since(self, seq: int) -> list[dict[str, Any]]:
        for b in self._backends:
            out = b.read_since(seq)
            if out:
                return out
        return []

    def head(self) -> int:
        # The chain head is the max of its constituents.
        return max((b.head() for b in self._backends), default=0)

    def clear(self) -> None:
        for b in self._backends:
            b.clear()
