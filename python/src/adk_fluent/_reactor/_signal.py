"""Signal — typed, reactive state cell.

A :class:`Signal` holds a single value with a monotonic version. Every
mutation emits a :class:`SignalChanged` event on the harness bus and
(via the bus) on the durable tape. Observers subscribe to the signal
directly (sync callback) or via the :class:`Reactor` (async, priority-
scheduled).

Design decisions
----------------

- **Equality guard by default**. ``s.set(v)`` is a no-op when ``v ==
  current``. Pass ``force=True`` to emit anyway — useful when mutable
  values are modified in place.
- **No deep copy on read**. ``s.get()`` returns the stored reference.
  Treat signal values as immutable to avoid surprise updates.
- **Version is monotonic**. Even when equality-guarded emissions are
  skipped, the version never rewinds. Consumers can memoize on version.
- **Bus is optional**. A bare ``Signal()`` works in tests without any
  harness wiring; set ``signal.bus = bus`` (or pass via ``.attach``) to
  flow changes through the reactor.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from adk_fluent._harness._events import SignalChanged

if TYPE_CHECKING:
    from adk_fluent._harness._event_bus import EventBus

__all__ = ["Signal"]


class Signal:
    """Typed reactive state cell.

    Args:
        name: Stable identifier used by observers and emitted events.
        initial: Starting value. ``None`` by default.
        bus: Optional :class:`EventBus` to emit :class:`SignalChanged`
            on. Can be attached later via :meth:`attach`.
    """

    __slots__ = ("_name", "_value", "_version", "_bus", "_subs")

    def __init__(
        self,
        name: str,
        initial: Any = None,
        *,
        bus: EventBus | None = None,
    ) -> None:
        self._name = name
        self._value = initial
        self._version = 0
        self._bus = bus
        self._subs: list[Callable[[Any, Any], None]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> int:
        """Monotonic mutation counter. Survives equality-guarded no-ops."""
        return self._version

    @property
    def value(self) -> Any:
        return self._value

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def get(self) -> Any:
        # Auto-tracking: if a reactive derivation is collecting deps, add
        # this signal to the set so changes re-run the derivation.
        from adk_fluent._reactor._tracking import current_tracker

        tracker = current_tracker()
        if tracker is not None:
            tracker.add(self)
        return self._value

    def set(self, value: Any, *, force: bool = False) -> bool:
        """Set the signal's value. Emits SignalChanged unless unchanged.

        Args:
            value: New value.
            force: If True, emit even when ``value == current``.

        Returns:
            True if an emission happened, False if skipped.
        """
        prev = self._value
        if not force and prev == value:
            return False
        self._value = value
        self._version += 1
        for sub in list(self._subs):
            # Observer isolation — one failing subscriber never blocks
            # another or the mutation itself.
            with contextlib.suppress(Exception):
                sub(value, prev)
        if self._bus is not None:
            self._bus.emit(
                SignalChanged(
                    name=self._name,
                    version=self._version,
                    value=_safe(value),
                    previous=_safe(prev),
                )
            )
        return True

    def update(self, fn: Callable[[Any], Any]) -> bool:
        """Apply ``fn(current) -> new_value`` atomically. Returns whether emission occurred."""
        return self.set(fn(self._value))

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    def subscribe(self, fn: Callable[[Any, Any], None]) -> Callable[[], None]:
        """Register a sync observer. Returns an unsubscribe callable."""
        self._subs.append(fn)

        def _off() -> None:
            with contextlib.suppress(ValueError):
                self._subs.remove(fn)

        return _off

    def attach(self, bus: EventBus) -> Signal:
        """Wire this signal to a bus. Returns self for chaining."""
        self._bus = bus
        return self

    # ------------------------------------------------------------------
    # Predicate helpers
    # ------------------------------------------------------------------

    @property
    def changed(self):
        """Predicate that fires on every change."""
        from adk_fluent._reactor._predicate import SignalPredicate

        return SignalPredicate.on_changed(self)

    @property
    def rising(self):
        """Predicate that fires when value rises (new > prev)."""
        from adk_fluent._reactor._predicate import SignalPredicate

        return SignalPredicate.on_rising(self)

    @property
    def falling(self):
        """Predicate that fires when value falls (new < prev)."""
        from adk_fluent._reactor._predicate import SignalPredicate

        return SignalPredicate.on_falling(self)

    def is_(self, expected: Any):
        """Predicate that fires when value == ``expected`` after a change."""
        from adk_fluent._reactor._predicate import SignalPredicate

        return SignalPredicate.on_equals(self, expected)

    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return f"Signal(name={self._name!r}, value={self._value!r}, v={self._version})"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _safe(value: Any) -> Any:
    """Return a JSONL-friendly form of ``value`` for event payloads."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    return repr(value)
