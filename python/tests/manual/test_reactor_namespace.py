"""Tests for the R namespace + Agent.on() integration.

Covers the 100x-native reactor surface: registry-backed signals,
name-addressed predicate factories, declarative rule attachment on
builders, compile-time rule walking, and the debounce/throttle
immutability fix.
"""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import (
    Agent,
    FanOut,
    Pipeline,
    R,
    ReactorPlugin,
    RuleSpec,
    SessionTape,
    Signal,
    SignalRegistry,
)
from adk_fluent._harness._event_bus import EventBus


@pytest.fixture(autouse=True)
def _reset_registry():
    R.clear()
    yield
    R.clear()


# ----------------------------------------------------------------------
# Registry basics
# ----------------------------------------------------------------------


def test_signal_is_idempotent():
    a = R.signal("temp", 72)
    b = R.signal("temp")
    assert a is b
    assert a.value == 72


def test_registered_signal_reuses_bus():
    bus = EventBus()
    R.attach(bus)
    s = R.signal("pressure", 1.0)
    assert s._bus is bus


def test_registry_scope_is_isolated():
    scoped = R.scope()
    s1 = scoped.signal("x", 1)
    assert "x" not in R.names()
    assert scoped.get("x") is s1


def test_get_missing_signal_raises():
    with pytest.raises(KeyError, match="R.signal"):
        R.get("nope")


# ----------------------------------------------------------------------
# Predicate factories
# ----------------------------------------------------------------------


def test_rising_predicate_deps():
    R.signal("temp", 0)
    pred = R.rising("temp")
    assert pred.deps == frozenset({"temp"})


def test_any_all_composition():
    R.signal("a", 0)
    R.signal("b", 0)
    combined = R.any(R.changed("a"), R.changed("b"))
    assert combined.deps == frozenset({"a", "b"})

    both = R.all(R.changed("a"), R.changed("b"))
    assert both.deps == frozenset({"a", "b"})


def test_is_equals_predicate_fires_on_match():
    from adk_fluent._reactor._predicate import _Change

    R.signal("mode", "idle")
    pred = R.is_("mode", "running")
    assert pred.matches(_Change(signal_name="mode", value="running", previous="idle"))
    assert not pred.matches(_Change(signal_name="mode", value="idle", previous="running"))


# ----------------------------------------------------------------------
# Debounce / throttle immutability (fix for the in-place-mutation bug)
# ----------------------------------------------------------------------


def test_debounce_returns_fresh_predicate():
    R.signal("temp", 0)
    base = R.changed("temp")
    debounced = base.debounce(50)
    assert debounced is not base
    assert base._debounce_ms == 0.0
    assert debounced._debounce_ms == 50.0


def test_throttle_returns_fresh_predicate():
    R.signal("temp", 0)
    base = R.changed("temp")
    throttled = base.throttle(100)
    assert throttled is not base
    assert base._throttle_ms == 0.0
    assert throttled._throttle_ms == 100.0


def test_debounce_then_throttle_preserves_both():
    R.signal("temp", 0)
    chained = R.changed("temp").debounce(50).throttle(100)
    assert chained._debounce_ms == 50.0
    assert chained._throttle_ms == 100.0


# ----------------------------------------------------------------------
# Builder.on()
# ----------------------------------------------------------------------


def test_on_attaches_rule_spec_to_builder():
    agent = Agent("cooler", "gemini-2.5-flash").on(R.rising("temp"), lambda c: None)
    specs = agent._reactor_rules
    assert len(specs) == 1
    assert isinstance(specs[0], RuleSpec)
    assert specs[0].predicate.deps == frozenset({"temp"})
    assert specs[0].name == "cooler"


def test_on_accepts_bare_signal():
    sig = R.signal("alert", False)
    agent = Agent("responder").on(sig, lambda c: None)
    assert agent._reactor_rules[0].predicate.deps == frozenset({"alert"})


def test_on_without_handler_uses_builder_handler():
    agent = Agent("responder").on(R.changed("alert"))
    spec = agent._reactor_rules[0]
    assert spec.handler is not None
    assert callable(spec.handler)


def test_on_rejects_non_predicate():
    agent = Agent("responder")
    with pytest.raises(TypeError, match="SignalPredicate or Signal"):
        agent.on("not a predicate", lambda c: None)


def test_on_propagates_priority_and_preempt():
    agent = Agent("x").on(
        R.changed("alert"),
        lambda c: None,
        priority=10,
        preemptive=True,
    )
    spec = agent._reactor_rules[0]
    assert spec.priority == 10
    assert spec.preemptive is True


# ----------------------------------------------------------------------
# Rule discovery through composite builders
# ----------------------------------------------------------------------


def test_compile_walks_pipeline_children():
    R.signal("temp", 0)
    inner = Agent("cool").on(R.rising("temp"), lambda c: None)
    outer = Pipeline("flow").step(inner)

    tape = SessionTape()
    reactor = R.compile(outer, tape=tape)
    assert len(reactor.rules) == 1
    assert reactor.rules[0].predicate.deps == frozenset({"temp"})


def test_compile_walks_fanout_branches():
    R.signal("a", 0)
    R.signal("b", 0)
    fa = FanOut("parallel")
    fa = fa.branch(Agent("x").on(R.changed("a"), lambda c: None))
    fa = fa.branch(Agent("y").on(R.changed("b"), lambda c: None))

    tape = SessionTape()
    reactor = R.compile(fa, tape=tape)
    dep_names = {next(iter(rule.predicate.deps)) for rule in reactor.rules}
    assert dep_names == {"a", "b"}


def test_compile_includes_standalone_rules():
    R.signal("x", 0)
    R.rule(R.changed("x"), lambda c: None, name="manual")

    tape = SessionTape()
    reactor = R.compile(tape=tape)
    names = {rule.name for rule in reactor.rules}
    assert "manual" in names


# ----------------------------------------------------------------------
# End-to-end: compile + run + signal mutation
# ----------------------------------------------------------------------


def test_end_to_end_rule_fires():
    async def run() -> list[tuple]:
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        R.attach(bus)

        temp = R.signal("temp", 72)

        fires: list[tuple] = []

        async def handler(change):
            fires.append((change.signal_name, change.value, change.previous))

        agent = Agent("cooler", "gemini-2.5-flash").on(
            R.rising("temp").where(lambda v, prev: v > 90),
            handler,
            priority=10,
        )

        reactor = R.compile(agent, tape=tape, bus=bus)
        runner = asyncio.create_task(reactor.run())
        await asyncio.sleep(0.05)

        temp.set(80)
        temp.set(95)
        temp.set(92)
        await asyncio.sleep(0.1)

        reactor.stop()
        await asyncio.sleep(0.02)
        runner.cancel()
        return fires

    fires = asyncio.run(run())
    assert fires == [("temp", 95, 80)]


# ----------------------------------------------------------------------
# ReactorPlugin lifecycle
# ----------------------------------------------------------------------


def test_reactor_plugin_owns_lifecycle():
    async def run() -> bool:
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        R.attach(bus)

        sig = R.signal("ping", False)
        fired = asyncio.Event()

        async def handler(_change):
            fired.set()

        agent = Agent("listener").on(R.changed("ping"), handler)
        reactor = R.compile(agent, tape=tape, bus=bus)
        plugin = ReactorPlugin(reactor)

        await plugin.on_session_start()
        sig.set(True)
        await asyncio.wait_for(fired.wait(), timeout=0.3)
        await plugin.on_session_end()
        return fired.is_set()

    assert asyncio.run(run())


# ----------------------------------------------------------------------
# Unused-import nuisance
# ----------------------------------------------------------------------


def test_signal_registry_exported():
    assert SignalRegistry  # re-export check
    assert Signal
