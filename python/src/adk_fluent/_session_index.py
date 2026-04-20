"""Cached session event index for context providers.

Context providers (``_context_providers.py``) rebuild ``list(ctx.session.events)``
and rescan it once per provider invocation. A compiled agent commonly has
3–6 providers running per turn (e.g. ``C.none() | C.from_state('topic') |
C.window(5)``), which means the event list is materialized and scanned
several times on every LLM call for the same underlying session.

This module caches a per-session ``SessionEventIndex`` in a
``WeakKeyDictionary`` keyed by the ADK ``Session`` object. The index
precomputes the data structures every hot provider needs:

* ``events`` — materialized tuple of events (snapshot)
* ``user_indices`` — positions of user messages, for turn-window logic
* ``by_author`` — bucket per author, for author-filter providers
* ``non_user_mask`` — cached indices of non-user events

Rebuild is incremental: the index syncs against ``len(session.events)``
and appends only the new events. Rewinds (shorter list) trigger a full
reset.

Callers should not hold on to the index across await points — it is
only consistent with respect to the session state at the moment it
was fetched. Obtain a fresh one per provider call::

    idx = get_session_index(ctx.session)
    user = idx.user_events()
"""

from __future__ import annotations

import contextlib
from typing import Any
from weakref import WeakKeyDictionary

__all__ = ["SessionEventIndex", "get_session_index"]


# Per-session cache. Weak keys so entries drop when ADK releases the session.
_INDEX_CACHE: WeakKeyDictionary[Any, SessionEventIndex] = WeakKeyDictionary()


class SessionEventIndex:
    """Incrementally maintained index over a session's event list.

    All accessors return lists derived from a frozen snapshot of the
    underlying session events taken at sync time. Callers treat the
    returned lists as read-only.
    """

    __slots__ = (
        "_events",
        "_len",
        "_by_author",
        "_user_indices",
        "_non_user_indices",
    )

    def __init__(self) -> None:
        self._events: list[Any] = []
        self._len: int = 0
        # Author values are stored as-is (including None) to preserve the
        # exact semantics of ``getattr(event, "author", None) in names_set``.
        self._by_author: dict[Any, list[int]] = {}
        self._user_indices: list[int] = []
        self._non_user_indices: list[int] = []

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def _sync(self, session: Any) -> None:
        """Bring the index up to date with the session's current events."""
        raw = getattr(session, "events", None)
        if raw is None:
            self._reset()
            return

        # Materialize once — session.events may be a list, tuple, or
        # generator-backed sequence. We iterate once, then cache.
        if isinstance(raw, list):
            current_len = len(raw)
            events_ref = raw  # list is stable across indexing
        else:
            try:
                current_len = len(raw)
                events_ref = raw
            except TypeError:
                materialized = list(raw)
                events_ref = materialized
                current_len = len(materialized)

        if current_len == self._len:
            return  # hot path: cache still valid

        if current_len < self._len:
            # Session was rewound or replaced — full rebuild.
            self._reset()

        # Append any new events to the index.
        for i in range(self._len, current_len):
            ev = events_ref[i]
            author = getattr(ev, "author", None)
            bucket = self._by_author.get(author)
            if bucket is None:
                bucket = []
                self._by_author[author] = bucket
            bucket.append(i)
            if author == "user":
                self._user_indices.append(i)
            else:
                self._non_user_indices.append(i)

        # Snapshot the events list. We always materialize a fresh list
        # so callers can treat ``self._events`` as immutable for the
        # lifetime of their provider call.
        if isinstance(events_ref, list):
            self._events = events_ref[:current_len]
        else:
            self._events = list(events_ref[:current_len])
        self._len = current_len

    def _reset(self) -> None:
        self._events = []
        self._len = 0
        self._by_author.clear()
        self._user_indices.clear()
        self._non_user_indices.clear()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def events(self) -> list[Any]:
        """Materialized event snapshot (treat as read-only)."""
        return self._events

    def user_events(self) -> list[Any]:
        """Return events authored by ``user``."""
        evs = self._events
        return [evs[i] for i in self._user_indices]

    def events_by_authors(self, authors: set[str]) -> list[Any]:
        """Return events whose author is in ``authors``."""
        evs = self._events
        if not authors:
            return []
        # Walk precomputed buckets instead of rescanning the event list.
        # Collect indices, then sort for stable order, then map to events.
        indices: list[int] = []
        for a in authors:
            bucket = self._by_author.get(a)
            if bucket:
                indices.extend(bucket)
        indices.sort()
        return [evs[i] for i in indices]

    def events_excluding_authors(self, authors: set[Any]) -> list[Any]:
        """Return events whose author is NOT in ``authors``."""
        if not authors:
            return list(self._events)
        evs = self._events
        return [e for e in evs if getattr(e, "author", None) not in authors]

    def window_tail(self, n: int) -> list[Any]:
        """Return the slice of events from the start of the last N user turns."""
        if not self._user_indices:
            return []
        user_idxs = self._user_indices
        if len(user_idxs) <= n:
            start = user_idxs[0]
        else:
            start = user_idxs[-n]
        return self._events[start:]


def get_session_index(session: Any) -> SessionEventIndex:
    """Return a sync'd ``SessionEventIndex`` for ``session``.

    Creates and caches the index on first use. Weakly referenced so the
    cache never pins a session beyond ADK's own lifetime.
    """
    idx = _INDEX_CACHE.get(session)
    if idx is None:
        idx = SessionEventIndex()
        # Session not weakref-able (e.g. a test stub) — fall back to
        # a throwaway index. Still saves the work within this call.
        with contextlib.suppress(TypeError):
            _INDEX_CACHE[session] = idx
    idx._sync(session)
    return idx
