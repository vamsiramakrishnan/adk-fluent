"""Auto-tracking for reactive computations.

Borrowed-idea lineage: Solid.js / MobX / Knockout — when a derived
computation reads a signal, the signal is auto-subscribed so the
derivation re-runs on any dependency change. No explicit dep lists.

The implementation is intentionally small: a contextvar-held ``set`` of
signals collects reads during an ``async with track_reads()`` block, and
:func:`computed` / :func:`reaction` wire the captured deps to re-run the
callable on change.

Only reads via :meth:`Signal.get` are tracked. Direct ``signal.value``
access bypasses tracking by design — use ``.get()`` inside reactive
computations.
"""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adk_fluent._reactor._signal import Signal

__all__ = [
    "computed",
    "current_tracker",
    "reaction",
    "track_reads",
]


_active_tracker: contextvars.ContextVar[set[Signal] | None] = contextvars.ContextVar(
    "adkf_signal_tracker", default=None
)


def current_tracker() -> set[Signal] | None:
    """Return the active read-tracker set, or ``None`` outside a tracking block."""
    return _active_tracker.get()


@contextlib.contextmanager
def track_reads() -> Iterator[set[Signal]]:
    """Collect every signal read via :meth:`Signal.get` inside the block.

    Yields the dependency set. On exit the previous tracker (if any) is
    restored, so nested trackers behave like a stack.
    """
    deps: set[Signal] = set()
    token = _active_tracker.set(deps)
    try:
        yield deps
    finally:
        _active_tracker.reset(token)


def computed(
    name: str,
    fn: Callable[[], Any],
    *,
    bus: Any = None,
) -> Signal:
    """Create a derived :class:`Signal` that re-runs ``fn`` on dep changes.

    The first call to ``fn`` runs under a tracker to collect the signals
    it reads. Each dep is subscribed; any change re-runs ``fn`` and
    writes the new value onto the returned signal.

    Cycle note: if ``fn`` reads the computed signal itself the dep would
    loop. This is not guarded — keep derivations acyclic.
    """
    from adk_fluent._reactor._signal import Signal

    with track_reads() as deps:
        initial = fn()
    out = Signal(name, initial, bus=bus)

    def _recompute(_new: Any, _prev: Any) -> None:
        with track_reads():
            out.set(fn())

    for dep in deps:
        dep.subscribe(_recompute)
    return out


def reaction(
    fn: Callable[[], Any],
) -> Callable[[], None]:
    """Run ``fn`` once, track its reads, re-run on any dep change.

    Returns an unsubscribe callable that detaches from every tracked
    dep. Useful for one-off side effects (logging, UI refresh) that
    should stay in sync with a set of signals without an explicit
    subscription list.
    """
    with track_reads() as deps:
        fn()

    offs: list[Callable[[], None]] = []

    def _rerun(_new: Any, _prev: Any) -> None:
        with track_reads():
            fn()

    for dep in deps:
        offs.append(dep.subscribe(_rerun))

    def _unsubscribe() -> None:
        for off in offs:
            with contextlib.suppress(Exception):
                off()

    return _unsubscribe
