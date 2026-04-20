"""R — the reactive namespace.

``R`` is the reactor facade that mirrors the ergonomics of :mod:`S`
(state transforms), :mod:`C` (context engineering), and :mod:`M`
(middleware). Where those namespaces turn their respective concerns
into declarative builders, ``R`` does the same for signals, predicates,
and reactor rules.

The key move is the :class:`SignalRegistry`. Signals become *named*
addressable cells — ``R.signal("temp", 72)`` — and predicates become
*name-addressed* factories — ``R.rising("temp")``. This removes the
wiring ceremony (manual ``Signal()`` + ``EventBus()`` + ``.attach(bus)``)
and lets predicates survive as first-class values that builders can
attach to via :meth:`BuilderBase.on`.

Every builder with an ``.on(pred, handler=...)`` rule stores a
:class:`_RuleSpec`. ``R.compile(*builders)`` walks those specs (plus
any bare rules registered via :meth:`R.rule`), binds them to a tape
and bus, and returns a ready-to-start :class:`Reactor`.

Example::

    from adk_fluent import Agent, R

    temp = R.signal("temp", 72)

    cooler = (
        Agent("cooler", "gemini-2.5-flash")
        .instruct("Cooling plan for {temp}.")
        .on(R.rising("temp").where(lambda v, _: v > 90))
    )

    # Compile rules against a session's tape + bus.
    reactor = R.compile(cooler, tape=tape, bus=bus)
    await reactor.run()

    # Fire the trigger.
    temp.set(92)
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from adk_fluent._reactor._predicate import SignalPredicate
from adk_fluent._reactor._reactor import Reactor
from adk_fluent._reactor._signal import Signal

if TYPE_CHECKING:
    from adk_fluent._harness._event_bus import EventBus
    from adk_fluent._session._tape import SessionTape


__all__ = [
    "R",
    "SignalRegistry",
    "RuleSpec",
    "default_registry",
]


Handler = Callable[[Any], Awaitable[Any] | Any]


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """A declarative reactor rule attached to a builder via ``.on()``.

    Stored on builders; materialized into a :class:`ReactorRule` by
    :meth:`R.compile` when a tape + bus are available.
    """

    predicate: SignalPredicate
    handler: Handler | None = None
    name: str = ""
    priority: int = 0
    preemptive: bool = False

    def with_handler(self, handler: Handler) -> RuleSpec:
        return RuleSpec(
            predicate=self.predicate,
            handler=handler,
            name=self.name,
            priority=self.priority,
            preemptive=self.preemptive,
        )


class SignalRegistry:
    """Thread-safe name→signal registry backing the :class:`R` facade.

    One registry per logical session. The module-level
    :data:`default_registry` is the default scope used by ``R.*``;
    tests and isolated workflows can create a dedicated instance and
    attach it via :meth:`R.scope`.

    Every signal created through the registry shares the registry's
    bus so mutations flow through a single event stream that the
    reactor can observe.
    """

    def __init__(self, *, bus: EventBus | None = None) -> None:
        self._signals: dict[str, Signal] = {}
        self._rules: list[RuleSpec] = []
        self._bus = bus
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Bus
    # ------------------------------------------------------------------

    @property
    def bus(self) -> EventBus | None:
        return self._bus

    def attach(self, bus: EventBus) -> SignalRegistry:
        """Attach an :class:`EventBus` to this registry.

        Re-binds every already-registered signal to the new bus so
        previously-created handles start flowing events through it.
        Returns ``self`` for chaining.
        """
        with self._lock:
            self._bus = bus
            for sig in self._signals.values():
                sig.attach(bus)
        return self

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def signal(self, name: str, initial: Any = None) -> Signal:
        """Get-or-create the named signal.

        Re-calling ``signal(name, ...)`` with the same ``name`` returns
        the same instance (idempotent). The ``initial`` argument is
        only applied on first creation; subsequent calls ignore it.
        """
        with self._lock:
            existing = self._signals.get(name)
            if existing is not None:
                return existing
            sig = Signal(name, initial, bus=self._bus)
            self._signals[name] = sig
            return sig

    def get(self, name: str) -> Signal:
        """Return an existing signal or raise ``KeyError``."""
        try:
            return self._signals[name]
        except KeyError as exc:
            raise KeyError(f"Signal {name!r} is not registered. Create it with R.signal({name!r}, ...) first.") from exc

    def has(self, name: str) -> bool:
        return name in self._signals

    def names(self) -> tuple[str, ...]:
        """Return registered signal names in insertion order."""
        with self._lock:
            return tuple(self._signals)

    def clear(self) -> None:
        """Drop every registered signal and rule. Primarily for tests."""
        with self._lock:
            self._signals.clear()
            self._rules.clear()

    # ------------------------------------------------------------------
    # Rules (standalone — not attached to a specific builder)
    # ------------------------------------------------------------------

    def rule(
        self,
        predicate: SignalPredicate,
        handler: Handler,
        *,
        name: str = "",
        priority: int = 0,
        preemptive: bool = False,
    ) -> RuleSpec:
        """Register a standalone rule. Returns the :class:`RuleSpec`."""
        spec = RuleSpec(
            predicate=predicate,
            handler=handler,
            name=name,
            priority=priority,
            preemptive=preemptive,
        )
        with self._lock:
            self._rules.append(spec)
        return spec

    def rules(self) -> tuple[RuleSpec, ...]:
        """Standalone (non-builder) rules registered via :meth:`rule`."""
        return tuple(self._rules)


default_registry = SignalRegistry()
"""Module-level default registry backing the ``R`` facade."""


# ----------------------------------------------------------------------
# R — the namespace facade
# ----------------------------------------------------------------------


class _R:
    """The reactive namespace.

    All class methods delegate to :data:`default_registry` for the
    common path. Tests and multi-session workflows that want an
    isolated registry can call :meth:`R.scope` and use the returned
    object directly, or swap the default via :meth:`R.set_registry`.
    """

    # --- Registry access -----------------------------------------------

    @staticmethod
    def registry() -> SignalRegistry:
        """The active default registry."""
        return default_registry

    @staticmethod
    def set_registry(registry: SignalRegistry) -> None:
        """Swap the module-level default registry. Primarily for tests."""
        global default_registry
        default_registry = registry

    @staticmethod
    def scope(*, bus: EventBus | None = None) -> SignalRegistry:
        """Return a fresh isolated :class:`SignalRegistry`.

        Use when you want a self-contained reactor (tests, sub-graphs,
        multi-tenant workflows) without touching the module default.
        """
        return SignalRegistry(bus=bus)

    @staticmethod
    def clear() -> None:
        """Drop every signal and standalone rule from the default registry."""
        default_registry.clear()

    @staticmethod
    def attach(bus: EventBus) -> SignalRegistry:
        """Attach a bus to the default registry. Returns it for chaining."""
        return default_registry.attach(bus)

    # --- Signals -------------------------------------------------------

    @staticmethod
    def signal(name: str, initial: Any = None) -> Signal:
        """Get-or-create a named signal in the default registry."""
        return default_registry.signal(name, initial)

    @staticmethod
    def get(name: str) -> Signal:
        """Return an existing signal by name, or raise ``KeyError``."""
        return default_registry.get(name)

    @staticmethod
    def names() -> tuple[str, ...]:
        return default_registry.names()

    # --- Predicate factories (name-addressed) --------------------------

    @staticmethod
    def changed(name: str) -> SignalPredicate:
        """Predicate that fires on every change of the named signal."""
        return SignalPredicate.on_changed(default_registry.signal(name))

    @staticmethod
    def rising(name: str) -> SignalPredicate:
        """Predicate that fires when the named signal rises (new > prev)."""
        return SignalPredicate.on_rising(default_registry.signal(name))

    @staticmethod
    def falling(name: str) -> SignalPredicate:
        """Predicate that fires when the named signal falls (new < prev)."""
        return SignalPredicate.on_falling(default_registry.signal(name))

    @staticmethod
    def is_(name: str, expected: Any) -> SignalPredicate:
        """Predicate that fires when the named signal equals ``expected``."""
        return SignalPredicate.on_equals(default_registry.signal(name), expected)

    # --- Composition ---------------------------------------------------

    @staticmethod
    def any(*preds: SignalPredicate) -> SignalPredicate:
        """Predicate that fires when any of ``preds`` match.

        Equivalent to ``preds[0] | preds[1] | ...``; supplied as a
        convenient n-ary form.
        """
        if not preds:
            raise ValueError("R.any() requires at least one predicate")
        combined = preds[0]
        for p in preds[1:]:
            combined = combined | p
        return combined

    @staticmethod
    def all(*preds: SignalPredicate) -> SignalPredicate:
        """Predicate that fires when all of ``preds`` match."""
        if not preds:
            raise ValueError("R.all() requires at least one predicate")
        combined = preds[0]
        for p in preds[1:]:
            combined = combined & p
        return combined

    # --- Derived signals -----------------------------------------------

    @staticmethod
    def computed(name: str, fn: Callable[[], Any]) -> Signal:
        """Register and return a derived signal driven by ``fn``.

        ``fn`` is called once to seed the value; ``Signal.get()`` calls
        inside ``fn`` are tracked, so the derived signal re-runs (and
        emits) whenever any dependency changes.
        """
        from adk_fluent._reactor._tracking import computed as _computed

        sig = _computed(name, fn, bus=default_registry.bus)
        # Register so R.get(name) / R.changed(name) can find it.
        with default_registry._lock:
            default_registry._signals.setdefault(name, sig)
        return sig

    # --- Rule helpers --------------------------------------------------

    @staticmethod
    def rule(
        predicate: SignalPredicate,
        handler: Handler,
        *,
        name: str = "",
        priority: int = 0,
        preemptive: bool = False,
    ) -> RuleSpec:
        """Register a standalone rule against the default registry."""
        return default_registry.rule(
            predicate,
            handler,
            name=name,
            priority=priority,
            preemptive=preemptive,
        )

    # --- Compilation ---------------------------------------------------

    @staticmethod
    def compile(
        *builders: Any,
        tape: SessionTape,
        bus: EventBus | None = None,
        registry: SignalRegistry | None = None,
    ) -> Reactor:
        """Build a :class:`Reactor` wired to ``tape`` with all discovered rules.

        Walks ``builders`` for :class:`RuleSpec` entries attached via
        :meth:`BuilderBase.on`, registers them alongside any standalone
        rules from the registry, and returns a ready-to-:meth:`run`
        reactor. The bus attached to the registry is reused unless
        ``bus`` is given explicitly; when present, the registry is
        re-attached to it so signals start flowing through it.
        """
        reg = registry or default_registry
        if bus is not None:
            reg.attach(bus)
        reactor = Reactor(tape, bus=reg.bus)
        for spec in _walk_rules(builders, reg):
            if spec.handler is None:
                raise ValueError(
                    f"Rule {spec.name or '<anonymous>'} has no handler. "
                    f"Pass one via .on(predicate, handler=fn) or R.rule(pred, fn)."
                )
            reactor.when(
                spec.predicate,
                _coerce_handler(spec.handler),
                name=spec.name or _auto_name(spec),
                priority=spec.priority,
                preemptive=spec.preemptive,
            )
        return reactor


R = _R
"""Module-level namespace facade. Import as ``from adk_fluent import R``."""


# ----------------------------------------------------------------------
# Rule discovery
# ----------------------------------------------------------------------


def _walk_rules(
    builders: Iterable[Any],
    registry: SignalRegistry,
) -> list[RuleSpec]:
    """Collect every :class:`RuleSpec` from a tree of builders + the registry.

    Walks ``_reactor_rules`` on each builder, plus ``_lists["steps"]``,
    ``_lists["branches"]``, ``_lists["sub_agents"]`` so rules attached
    to nested agents inside Pipelines / FanOuts / Loops are picked up
    automatically. Also includes standalone rules from the registry.
    """
    seen: set[int] = set()
    out: list[RuleSpec] = []

    def _walk(node: Any) -> None:
        if node is None or id(node) in seen:
            return
        seen.add(id(node))

        rules = getattr(node, "_reactor_rules", None)
        if rules:
            out.extend(rules)

        lists = getattr(node, "_lists", None)
        if isinstance(lists, dict):
            for key in ("steps", "branches", "sub_agents", "agents", "children"):
                for child in lists.get(key, ()):
                    _walk(child)

        # Expression wrappers (Pipeline / FanOut / Loop composites) often
        # stash their children on a ``_children`` attribute.
        for attr in ("_children", "_agents", "_steps", "_branches"):
            seq = getattr(node, attr, None)
            if seq:
                for child in seq:
                    _walk(child)

    for builder in builders:
        _walk(builder)

    out.extend(registry.rules())
    return out


def _auto_name(spec: RuleSpec) -> str:
    deps = sorted(spec.predicate.deps)
    tag = "+".join(deps) if deps else "rule"
    return f"on_{tag}"


def _coerce_handler(handler: Handler) -> Callable[[Any], Awaitable[Any]]:
    """Wrap a sync handler as async so :class:`Reactor` can always await it."""
    import asyncio

    if asyncio.iscoroutinefunction(handler):
        return handler  # type: ignore[return-value]

    async def _wrap(change: Any) -> Any:
        with contextlib.suppress(TypeError):
            return handler(change)  # type: ignore[misc]
        return handler()  # type: ignore[operator]

    return _wrap
