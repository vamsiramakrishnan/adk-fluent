"""adk_fluent._session — session-scoped tape + fork + store.

This package is the session-scoped mechanism that handles three
concerns the harness used to spread across three files:

- :class:`SessionTape` — event recorder/replayer (JSONL persistence).
- :class:`ForkManager` + :class:`Branch` — named state branches with
  merge and diff primitives.
- :class:`SessionStore` — unified container bundling a tape and a fork
  manager behind one API.
- :class:`SessionSnapshot` — frozen, serialisable view of a whole
  session (tape + branches + active pointer).
- :class:`SessionPlugin` — ADK ``BasePlugin`` that wires a store into
  the full invocation tree through ``after_agent_callback``.

The split mirrors the rest of adk-fluent: the *value* pieces (tape
entries, snapshots, branches) are serialisable plain-data objects, and
the *state* pieces (store, fork manager) are mutable runtime
containers. Use :meth:`SessionStore.snapshot` / :meth:`from_snapshot`
to move between them cleanly.
"""

from adk_fluent._session._fork import Branch, ForkManager
from adk_fluent._session._plugin import SessionPlugin
from adk_fluent._session._snapshot import SessionSnapshot
from adk_fluent._session._store import SessionStore
from adk_fluent._session._tape import Cursor, EventRecord, SessionTape
from adk_fluent._session._tape_backend import (
    ChainBackend,
    InMemoryBackend,
    JsonlBackend,
    NullBackend,
    TapeBackend,
)

__all__ = [
    "Branch",
    "ChainBackend",
    "Cursor",
    "EventRecord",
    "ForkManager",
    "InMemoryBackend",
    "JsonlBackend",
    "NullBackend",
    "SessionPlugin",
    "SessionSnapshot",
    "SessionStore",
    "SessionTape",
    "TapeBackend",
]
