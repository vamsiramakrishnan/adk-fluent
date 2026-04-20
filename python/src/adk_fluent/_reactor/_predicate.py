"""SignalPredicate — composable triggers for the reactor.

Build a predicate from signal change patterns and compose them with
boolean operators::

    high_temp = temp.rising.where(lambda v, prev: v > 90)
    online = status.is_("up")
    trigger = high_temp & online

    reactor.when(trigger, cooldown_agent)

The predicate is evaluated on every :class:`SignalChanged` event that
flows through the reactor. Each predicate tracks which signals it
depends on (for routing) and exposes a single :meth:`matches` method.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adk_fluent._reactor._signal import Signal

__all__ = ["SignalPredicate"]


@dataclass(frozen=True, slots=True)
class _Change:
    """Payload handed to predicate matchers."""

    signal_name: str
    value: Any
    previous: Any


class SignalPredicate:
    """A boolean expression over signal change events.

    Construct via :meth:`Signal.changed`, :meth:`Signal.rising`, etc.
    Compose with ``&``, ``|``, ``~``. Add filters with :meth:`where`,
    :meth:`debounce`, :meth:`throttle`.
    """

    __slots__ = ("_match", "_deps", "_last_fire", "_debounce_ms", "_throttle_ms")

    def __init__(
        self,
        match: Callable[[_Change], bool],
        deps: frozenset[str],
    ) -> None:
        self._match = match
        self._deps = deps
        self._last_fire: float = 0.0
        self._debounce_ms: float = 0.0
        self._throttle_ms: float = 0.0

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def on_changed(cls, signal: Signal) -> SignalPredicate:
        name = signal.name
        return cls(lambda c: c.signal_name == name, frozenset({name}))

    @classmethod
    def on_rising(cls, signal: Signal) -> SignalPredicate:
        name = signal.name
        return cls(
            lambda c: c.signal_name == name and _rising(c.value, c.previous),
            frozenset({name}),
        )

    @classmethod
    def on_falling(cls, signal: Signal) -> SignalPredicate:
        name = signal.name
        return cls(
            lambda c: c.signal_name == name and _falling(c.value, c.previous),
            frozenset({name}),
        )

    @classmethod
    def on_equals(cls, signal: Signal, expected: Any) -> SignalPredicate:
        name = signal.name
        return cls(
            lambda c: c.signal_name == name and c.value == expected,
            frozenset({name}),
        )

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def __and__(self, other: SignalPredicate) -> SignalPredicate:
        return SignalPredicate(
            lambda c: self._match(c) and other._match(c),
            self._deps | other._deps,
        )

    def __or__(self, other: SignalPredicate) -> SignalPredicate:
        return SignalPredicate(
            lambda c: self._match(c) or other._match(c),
            self._deps | other._deps,
        )

    def __invert__(self) -> SignalPredicate:
        return SignalPredicate(lambda c: not self._match(c), self._deps)

    def where(self, fn: Callable[[Any, Any], bool]) -> SignalPredicate:
        """Add a value-level filter: ``fn(value, previous) -> bool``."""
        inner = self._match
        return SignalPredicate(
            lambda c: inner(c) and fn(c.value, c.previous),
            self._deps,
        )

    def debounce(self, ms: float) -> SignalPredicate:
        """Only fire after ``ms`` of quiet time since the last match.

        Returns a fresh predicate so the original remains immutable —
        composable with ``&`` / ``|`` / ``~`` without state leakage.
        """
        new = SignalPredicate(self._match, self._deps)
        new._debounce_ms = ms
        new._throttle_ms = self._throttle_ms
        return new

    def throttle(self, ms: float) -> SignalPredicate:
        """Fire at most once every ``ms`` milliseconds.

        Returns a fresh predicate — see :meth:`debounce` for rationale.
        """
        new = SignalPredicate(self._match, self._deps)
        new._debounce_ms = self._debounce_ms
        new._throttle_ms = ms
        return new

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    @property
    def deps(self) -> frozenset[str]:
        """Signal names this predicate observes — used for bus routing."""
        return self._deps

    def matches(self, change: _Change) -> bool:
        """Return True if the change fires this predicate after filters."""
        if not self._match(change):
            return False
        now = time.monotonic() * 1000.0
        if self._throttle_ms > 0 and (now - self._last_fire) < self._throttle_ms:
            return False
        if self._debounce_ms > 0 and (now - self._last_fire) < self._debounce_ms:
            self._last_fire = now
            return False
        self._last_fire = now
        return True


def _rising(new: Any, prev: Any) -> bool:
    try:
        return new > prev  # type: ignore[operator]
    except Exception:
        return False


def _falling(new: Any, prev: Any) -> bool:
    try:
        return new < prev  # type: ignore[operator]
    except Exception:
        return False
