"""SessionSnapshot — frozen, serialisable view of a whole session.

A snapshot bundles together the pieces a session replay tool actually
needs: the event tape, every named branch, and the active-branch
pointer. It is the unit of persistence for
:class:`~adk_fluent._session._store.SessionStore`.

Because the snapshot is a frozen dataclass it is safe to stash in an
audit log, send over the wire, or hash for deduplication.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["SessionSnapshot"]


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    """Immutable bundle of tape events + branches.

    Attributes:
        events: Ordered list of tape entries (plain dicts, already
            serialisable). Each entry matches the shape written by
            :meth:`SessionTape.record`.
        branches: Mapping ``{branch_name: branch_dict}`` where each
            branch dict has ``state``, ``messages``, ``created_at``,
            ``parent``, ``metadata`` — the same shape you get from
            :func:`dataclasses.asdict` on a
            :class:`~adk_fluent._session._fork.Branch`.
        active_branch: Name of the active branch at snapshot time, or
            ``None``.
        version: Snapshot format version. Bumped only on breaking
            changes to the serialisation shape.
    """

    events: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    branches: dict[str, dict[str, Any]] = field(default_factory=dict)
    active_branch: str | None = None
    version: int = 1

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict view, deep-copied for safety."""
        return {
            "version": self.version,
            "active_branch": self.active_branch,
            "events": [dict(e) for e in self.events],
            "branches": copy.deepcopy(self.branches),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionSnapshot:
        """Reconstruct from a previously emitted :meth:`to_dict` payload."""
        return cls(
            version=int(data.get("version", 1)),
            active_branch=data.get("active_branch"),
            events=tuple(dict(e) for e in data.get("events", ())),
            branches=copy.deepcopy(dict(data.get("branches", {}))),
        )

    def save(self, path: str | Path) -> None:
        """Write the snapshot to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> SessionSnapshot:
        """Load a snapshot previously written by :meth:`save`."""
        p = Path(path)
        with p.open() as f:
            return cls.from_dict(json.load(f))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def branch_count(self) -> int:
        return len(self.branches)
