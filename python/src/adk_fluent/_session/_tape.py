"""Session tape — event recording and replay.

Records :class:`~adk_fluent._harness._events.HarnessEvent` instances
during a session for replay, debugging, or analysis. Composes with
``EventDispatcher`` as a subscriber::

    tape = SessionTape()
    dispatcher = H.dispatcher()
    dispatcher.subscribe(tape.record)

    # After session
    tape.save("/project/.harness/session.jsonl")

    # Replay later
    tape = SessionTape.load("/project/.harness/session.jsonl")
    for event in tape.events:
        print(event)

The tape is intentionally codec-agnostic: every event is flattened to a
plain dict via :func:`dataclasses.asdict` and persisted as JSONL. This
makes tapes portable across Python versions and allows external tools
(diff, grep, jq) to inspect them without loading the harness.
"""

from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adk_fluent._harness._events import HarnessEvent

__all__ = ["SessionTape"]


class SessionTape:
    """Records and replays harness events.

    A tape is an ordered log of HarnessEvents with timestamps.
    It can be saved to JSONL for persistence and loaded back.

    Args:
        max_events: Maximum events to buffer (0 = unlimited).
    """

    def __init__(self, *, max_events: int = 0) -> None:
        self._max_events = max_events
        # Use a bounded deque when capping — O(1) append with automatic
        # eviction of the oldest entry, versus an O(n) list slice on every
        # overflow.
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events if max_events > 0 else None)
        self._start_time = time.monotonic()

    def record(self, event: HarnessEvent) -> None:
        """Record a single event. Use as ``dispatcher.subscribe(tape.record)``.

        Args:
            event: HarnessEvent to record.
        """
        # Hand-roll the entry instead of ``dataclasses.asdict``. ``asdict``
        # performs a recursive deepcopy of every field which dominates hot
        # paths where tens of thousands of events flow through the tape.
        # All HarnessEvent subclasses are slotted frozen dataclasses, so we
        # iterate __dataclass_fields__ and shallow-copy by reference.
        entry: dict[str, Any] = {
            "t": round(time.monotonic() - self._start_time, 3),
            "kind": event.kind,
            "type": type(event).__name__,
        }
        for field_name in type(event).__dataclass_fields__:  # type: ignore[attr-defined]
            if field_name == "kind":
                continue
            entry[field_name] = getattr(event, field_name)
        self._events.append(entry)

    @property
    def events(self) -> list[dict[str, Any]]:
        """All recorded event entries."""
        return list(self._events)

    @property
    def size(self) -> int:
        """Number of recorded events."""
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
        }

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

        Args:
            path: Path to JSONL file.

        Returns:
            SessionTape with loaded events.
        """
        tape = cls()
        p = Path(path)
        if p.exists():
            with p.open() as f:
                for line in f:
                    line = line.strip()
                    if line:
                        tape._events.append(json.loads(line))
        return tape

    def clear(self) -> None:
        """Clear all recorded events."""
        self._events.clear()
        self._start_time = time.monotonic()

    def replay(self) -> list[dict[str, Any]]:
        """Return events in replay order (alias for .events)."""
        return self.events
