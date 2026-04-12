"""SessionStore — unified session-scoped storage.

A :class:`SessionStore` bundles a :class:`SessionTape` (event history)
and a :class:`ForkManager` (branch snapshots) behind one API. It is the
"store" half of adk-fluent's session mechanism: one object, one
lifetime, one snapshot artifact.

Why combine them? Because replay and fork are two halves of the same
picture. A tape without branches tells you *what happened*; a set of
branches without a tape tells you *what state survived*. A store
persists both atomically via :class:`SessionSnapshot`.

Typical wiring::

    store = H.session_store()

    dispatcher.subscribe(store.record_event)   # tape: record every event
    agent.after_agent(store.auto_fork("after_step"))  # fork: snapshot state

    # End of session
    store.snapshot().save("/project/.harness/session.json")

    # Replay later
    snapshot = SessionSnapshot.load("/project/.harness/session.json")
    store = SessionStore.from_snapshot(snapshot)
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from adk_fluent._session._fork import Branch, ForkManager
from adk_fluent._session._snapshot import SessionSnapshot
from adk_fluent._session._tape import SessionTape

if TYPE_CHECKING:
    from adk_fluent._harness._events import HarnessEvent

__all__ = ["SessionStore"]


class SessionStore:
    """Session-scoped container for tape + fork manager.

    Args:
        tape: Optional pre-built :class:`SessionTape`. A fresh tape is
            created if omitted.
        forks: Optional pre-built :class:`ForkManager`. A fresh manager
            is created if omitted.
    """

    def __init__(
        self,
        tape: SessionTape | None = None,
        forks: ForkManager | None = None,
    ) -> None:
        self._tape = tape or SessionTape()
        self._forks = forks or ForkManager()

    # ------------------------------------------------------------------
    # Component accessors
    # ------------------------------------------------------------------

    @property
    def tape(self) -> SessionTape:
        return self._tape

    @property
    def forks(self) -> ForkManager:
        return self._forks

    # ------------------------------------------------------------------
    # Convenience passthroughs
    # ------------------------------------------------------------------

    def record_event(self, event: HarnessEvent) -> None:
        """Append an event to the tape.

        Pass this directly to ``EventDispatcher.subscribe``.
        """
        self._tape.record(event)

    def fork(
        self,
        name: str,
        state: dict[str, Any],
        *,
        messages: list[dict[str, Any]] | None = None,
        parent: str | None = None,
        **metadata: Any,
    ) -> Branch:
        """Create a named branch from the given state (see ``ForkManager.fork``)."""
        return self._forks.fork(
            name, state, messages=messages, parent=parent, **metadata
        )

    def switch(self, name: str) -> dict[str, Any]:
        """Switch to a named branch."""
        return self._forks.switch(name)

    # ------------------------------------------------------------------
    # Snapshot / restore
    # ------------------------------------------------------------------

    def snapshot(self) -> SessionSnapshot:
        """Return an immutable :class:`SessionSnapshot` of the current store."""
        branches = {
            name: {
                "name": branch.name,
                "state": copy.deepcopy(branch.state),
                "messages": list(branch.messages),
                "created_at": branch.created_at,
                "parent": branch.parent,
                "metadata": dict(branch.metadata),
            }
            for name, branch in self._forks._branches.items()  # noqa: SLF001
        }
        return SessionSnapshot(
            events=tuple(self._tape.events),
            branches=branches,
            active_branch=self._forks.active,
        )

    @classmethod
    def from_snapshot(cls, snapshot: SessionSnapshot) -> SessionStore:
        """Reconstruct a store from a :class:`SessionSnapshot`."""
        tape = SessionTape()
        for entry in snapshot.events:
            tape._events.append(dict(entry))  # noqa: SLF001
        forks = ForkManager()
        for name, data in snapshot.branches.items():
            forks._branches[name] = Branch(  # noqa: SLF001
                name=data.get("name", name),
                state=copy.deepcopy(data.get("state", {})),
                messages=list(data.get("messages", [])),
                created_at=float(data.get("created_at", 0.0)),
                parent=data.get("parent"),
                metadata=dict(data.get("metadata", {})),
            )
        if snapshot.active_branch and snapshot.active_branch in forks._branches:  # noqa: SLF001
            forks._active = snapshot.active_branch  # noqa: SLF001
        return cls(tape=tape, forks=forks)

    # ------------------------------------------------------------------
    # Callback factories
    # ------------------------------------------------------------------

    def auto_fork(self, branch_name: str) -> Any:
        """Return an ``after_agent`` callback that snapshots state to ``branch_name``."""
        return self._forks.save_callback(branch_name)

    def auto_restore(self, branch_name: str) -> Any:
        """Return a ``before_agent`` callback that restores state from ``branch_name``."""
        return self._forks.restore_callback(branch_name)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a quick-glance summary of tape + fork state."""
        tape_summary = self._tape.summary()
        return {
            "tape": tape_summary,
            "branches": self._forks.size,
            "active_branch": self._forks.active,
        }

    def clear(self) -> None:
        """Drop everything. Tape events and branches are both wiped."""
        self._tape.clear()
        self._forks = ForkManager(
            max_branches=self._forks._max_branches  # noqa: SLF001
        )
