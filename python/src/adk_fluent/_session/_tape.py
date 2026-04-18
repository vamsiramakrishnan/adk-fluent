"""Session tape — durable, sequenced event log with cursors.

Records :class:`~adk_fluent._harness._events.HarnessEvent` instances
during a session for replay, debugging, or analysis. Every recorded
event is assigned a monotonic ``seq`` number so consumers can address
the log by position: read everything since cursor ``N``, or follow
the tail asynchronously as new events land.

The tape is the **durable substrate** for the harness. ``EventBus``
is a synchronous notification bus that sits *in front of* the tape;
if you need to resume, replay, or fan out to multiple consumers with
independent cursors, you read from the tape.

Composes with ``EventDispatcher`` as a subscriber::

    tape = SessionTape()
    dispatcher = H.dispatcher()
    dispatcher.subscribe(tape.record)

    # After session
    tape.save("/project/.harness/session.jsonl")

    # Replay later
    tape = SessionTape.load("/project/.harness/session.jsonl")
    for event in tape.events:
        print(event)

    # Resume from a cursor
    for entry in tape.since(last_seen_seq):
        handle(entry)

    # Follow the tail
    async for entry in tape.tail(from_seq=tape.head):
        render(entry)

The tape is intentionally codec-agnostic: every event is flattened to
a plain dict (with ``seq``, ``t``, ``kind``, ``type``, plus the event's
own fields) and persisted as JSONL. This makes tapes portable across
Python versions and allows external tools (diff, grep, jq) to inspect
them without loading the harness.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NewType

from adk_fluent._session._tape_backend import InMemoryBackend, TapeBackend

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from adk_fluent._harness._events import HarnessEvent

__all__ = ["Cursor", "EventRecord", "SessionTape"]


Cursor = NewType("Cursor", int)
"""A position in the tape. Opaque — treat as an integer for ordering only."""


@dataclass(frozen=True, slots=True)
class EventRecord:
    """Typed view over one recorded tape entry.

    The tape stores entries as plain dicts (for JSONL portability),
    but readers that want type safety can wrap entries in
    ``EventRecord`` via :meth:`SessionTape.record_at` or the
    convenience classmethod :meth:`from_dict`.

    Attributes:
        seq: Monotonic position in the tape, assigned at record time.
        t: Seconds since the tape started (monotonic clock).
        kind: Event kind (e.g. ``"text"``, ``"tool_call_start"``).
        type: Event dataclass name (e.g. ``"TextChunk"``).
        payload: Remaining fields of the event (everything except
            ``seq``/``t``/``kind``/``type``).
    """

    seq: int
    t: float
    kind: str
    type: str
    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, entry: dict[str, Any]) -> EventRecord:
        """Wrap a raw tape entry as an ``EventRecord``."""
        known = {"seq", "t", "kind", "type"}
        return cls(
            seq=int(entry.get("seq", -1)),
            t=float(entry.get("t", 0.0)),
            kind=str(entry.get("kind", "")),
            type=str(entry.get("type", "")),
            payload={k: v for k, v in entry.items() if k not in known},
        )


class SessionTape:
    """Records and replays harness events with cursor-based reads.

    A tape is an ordered log of ``HarnessEvent`` instances with
    timestamps and monotonic sequence numbers. It can be saved to
    JSONL for persistence and loaded back.

    Args:
        max_events: Maximum events to buffer in memory (0 = unlimited).
            When capped the oldest entries are evicted from the deque;
            sequence numbers remain monotonic, so cursor arithmetic
            stays correct even after eviction. Readers that asked for
            a cursor below the low-watermark receive only the
            surviving tail from the in-memory buffer — to guarantee
            full history, wire a :class:`TapeBackend`.
        backend: Optional durable mirror. Every ``record()`` forwards
            the entry. Defaults to an in-memory no-op backend.
    """

    def __init__(
        self,
        *,
        max_events: int = 0,
        backend: TapeBackend | None = None,
    ) -> None:
        self._max_events = max_events
        # Bounded deque when capping — O(1) append with automatic
        # eviction of the oldest entry, versus an O(n) list slice on
        # every overflow.
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events if max_events > 0 else None)
        self._start_time = time.monotonic()
        self._next_seq: int = 0
        # Created lazily on first tail() call — avoids paying for an
        # asyncio primitive in sync-only sessions.
        self._cond: asyncio.Condition | None = None
        self._backend: TapeBackend = backend if backend is not None else InMemoryBackend()

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record(self, event: HarnessEvent) -> int:
        """Record a single event. Use as ``dispatcher.subscribe(tape.record)``.

        Args:
            event: HarnessEvent to record.

        Returns:
            The ``seq`` assigned to the recorded entry. Callers that
            don't care (the dispatcher subscribe path) can ignore it.
        """
        # Hand-roll the entry instead of ``dataclasses.asdict``. ``asdict``
        # performs a recursive deepcopy of every field which dominates hot
        # paths where tens of thousands of events flow through the tape.
        # All HarnessEvent subclasses are slotted frozen dataclasses, so we
        # iterate __dataclass_fields__ and shallow-copy by reference.
        seq = self._next_seq
        self._next_seq += 1
        entry: dict[str, Any] = {
            "seq": seq,
            "t": round(time.monotonic() - self._start_time, 3),
            "kind": event.kind,
            "type": type(event).__name__,
        }
        for field_name in type(event).__dataclass_fields__:  # type: ignore[attr-defined]
            if field_name == "kind":
                continue
            entry[field_name] = getattr(event, field_name)
        self._events.append(entry)
        self._backend.append(entry)
        self._notify_waiters()
        return seq

    def record_dict(self, entry: dict[str, Any]) -> int:
        """Append a pre-built entry dict. Assigns seq if absent.

        Used by loaders and backends that produce entries directly
        without going through a HarnessEvent (e.g. cross-process
        replication).
        """
        if "seq" not in entry:
            entry = dict(entry)
            entry["seq"] = self._next_seq
            self._next_seq += 1
        else:
            # Keep the counter ahead of any imported seq so later
            # record() calls stay monotonic.
            self._next_seq = max(self._next_seq, int(entry["seq"]) + 1)
        entry.setdefault("t", round(time.monotonic() - self._start_time, 3))
        self._events.append(entry)
        self._backend.append(entry)
        self._notify_waiters()
        return int(entry["seq"])

    # ------------------------------------------------------------------
    # Cursor reads
    # ------------------------------------------------------------------

    @property
    def head(self) -> int:
        """Next seq that will be assigned. ``head - 1`` is the last recorded seq."""
        return self._next_seq

    @property
    def watermark(self) -> int:
        """Lowest seq still retained in the buffer.

        When ``max_events`` is unbounded this is always 0. When capped
        and full, it advances as entries are evicted.
        """
        if not self._events:
            return self._next_seq
        return int(self._events[0].get("seq", 0))

    def since(self, seq: int) -> Iterator[dict[str, Any]]:
        """Iterate entries with ``entry.seq >= seq``.

        Consumers that pass a cursor below :attr:`watermark` silently
        receive only the surviving tail — matches Kafka consumer
        semantics for expired offsets.

        Args:
            seq: Inclusive lower bound. Pass ``tape.head`` to start
                fresh (no historical entries).

        Yields:
            Raw entry dicts (with ``seq``/``t``/``kind``/``type``/...).
        """
        # Linear scan — fine for typical session sizes. If this ever
        # becomes a hot path we can bisect on a secondary sorted index.
        for entry in self._events:
            if int(entry.get("seq", -1)) >= seq:
                yield entry

    def records_since(self, seq: int) -> Iterator[EventRecord]:
        """Typed variant of :meth:`since`."""
        for entry in self.since(seq):
            yield EventRecord.from_dict(entry)

    async def tail(self, from_seq: int = 0) -> AsyncIterator[dict[str, Any]]:
        """Async iterator that yields all entries from ``from_seq`` onward and then follows the tail.

        Once caught up to :attr:`head`, awaits on an internal condition
        variable until :meth:`record` or :meth:`record_dict` appends a
        new entry, at which point the new entries are yielded. Loops
        forever until the consumer exits; cancel the task to stop.

        Args:
            from_seq: Inclusive starting seq. Default 0 replays the
                whole retained buffer first.

        Yields:
            Raw entry dicts in seq order.
        """
        cond = self._ensure_cond()
        next_seq = from_seq
        while True:
            # Drain everything already buffered >= next_seq.
            drained: list[dict[str, Any]] = []
            for entry in self._events:
                s = int(entry.get("seq", -1))
                if s >= next_seq:
                    drained.append(entry)
            for entry in drained:
                yield entry
                next_seq = int(entry.get("seq", next_seq)) + 1

            # Wait for more.
            async with cond:
                while self._next_seq <= next_seq:
                    await cond.wait()

    def _ensure_cond(self) -> asyncio.Condition:
        if self._cond is None:
            self._cond = asyncio.Condition()
        return self._cond

    def _notify_waiters(self) -> None:
        cond = self._cond
        if cond is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _wake() -> None:
            async with cond:
                cond.notify_all()

        loop.create_task(_wake())

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def events(self) -> list[dict[str, Any]]:
        """All recorded event entries."""
        return list(self._events)

    @property
    def size(self) -> int:
        """Number of recorded events currently retained."""
        return len(self._events)

    def filter(self, kind: str) -> list[dict[str, Any]]:
        """Filter events by kind.

        Args:
            kind: Event kind (e.g., "text", "tool_call_start").
        """
        return [e for e in self._events if e.get("kind") == kind]

    def summary(self) -> dict[str, Any]:
        """Return a summary of the recorded session."""
        kinds: dict[str, int] = {}
        for e in self._events:
            k = e.get("kind", "unknown")
            kinds[k] = kinds.get(k, 0) + 1

        duration = self._events[-1]["t"] if self._events else 0.0
        return {
            "total_events": len(self._events),
            "duration_seconds": duration,
            "event_counts": kinds,
            "head": self._next_seq,
            "watermark": self.watermark,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Save tape to a JSONL file.

        Args:
            path: Output file path.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Serialize all entries up-front and issue a single write — one
        # syscall instead of one per event.
        payload = "".join(json.dumps(entry) + "\n" for entry in self._events)
        with p.open("w") as f:
            f.write(payload)

    @classmethod
    def load(cls, path: str | Path) -> SessionTape:
        """Load tape from a JSONL file.

        Entries without an explicit ``seq`` field — i.e. tapes written
        by a pre-cursor version of adk-fluent — are back-filled using
        their line index, so old tapes remain fully usable.

        Args:
            path: Path to JSONL file.

        Returns:
            SessionTape with loaded events.
        """
        tape = cls()
        p = Path(path)
        if p.exists():
            with p.open() as f:
                for idx, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if "seq" not in entry:
                        entry["seq"] = idx
                    tape._events.append(entry)
            if tape._events:
                tape._next_seq = int(tape._events[-1].get("seq", -1)) + 1
        return tape

    def clear(self) -> None:
        """Clear all recorded events.

        Resets the start time and the seq counter — the next recorded
        event will be seq 0 again. Intended for session boundaries;
        do not call mid-session or cursors held by consumers will
        dangle.
        """
        self._events.clear()
        self._start_time = time.monotonic()
        self._next_seq = 0

    def replay(self) -> list[dict[str, Any]]:
        """Return events in replay order (alias for .events)."""
        return self.events
