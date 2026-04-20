"""R + Agent.on() — declarative reactors, zero ceremony.

The 0.17.0 reactor refresh makes signals and rules a first-class part
of the fluent builder surface. Before, wiring a reactor required
hand-building every object in sequence::

    bus = H.event_bus()
    tape = bus.tape()
    temp = Signal("temp", 72, bus=bus)
    reactor = Reactor(tape, bus=bus)
    reactor.when(temp.rising.where(lambda v, _: v > 90), my_handler, priority=10)
    await reactor.run()

Now::

    temp = R.signal("temp", 72)

    cooler = (
        Agent("cooler", "gemini-2.5-flash")
        .instruct("Plan a cool-down.")
        .on(R.rising("temp").where(lambda v, _: v > 90), priority=10)
    )

    reactor = R.compile(cooler, tape=tape, bus=bus)
    await reactor.run()

Run: ``uv run pytest examples/cookbook/81_reactor_native.py -v``
"""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import Agent, FanOut, Pipeline, R, ReactorPlugin, SessionTape
from adk_fluent._harness._event_bus import EventBus


@pytest.fixture(autouse=True)
def _reset():
    R.clear()
    yield
    R.clear()


def test_r_signal_is_name_addressed() -> None:
    """``R.signal(name)`` is a get-or-create; same name → same instance."""
    a = R.signal("temperature", 72)
    b = R.signal("temperature")
    assert a is b
    assert R.get("temperature").value == 72


def test_r_predicates_are_name_addressed() -> None:
    """``R.rising('temp')`` resolves through the registry — no Signal object needed."""
    R.signal("temperature", 0)
    pred = R.rising("temperature").where(lambda v, prev: v > 90)
    from adk_fluent._reactor._predicate import _Change

    assert pred.matches(_Change("temperature", 95, 85))  # rising above 90
    assert not pred.matches(_Change("temperature", 80, 95))  # falling


def test_on_attaches_rule_to_builder() -> None:
    """``.on(predicate)`` stores a declarative rule on the builder."""
    R.signal("temp", 0)
    agent = Agent("cooler").on(R.rising("temp"), lambda c: None, priority=10)
    spec = agent._reactor_rules[0]
    assert spec.predicate.deps == frozenset({"temp"})
    assert spec.priority == 10


def test_compile_walks_composite_builders() -> None:
    """``R.compile`` picks up rules attached anywhere in a Pipeline / FanOut tree."""
    R.signal("a", 0)
    R.signal("b", 0)

    pipeline = Pipeline("flow").step(
        Agent("x").on(R.changed("a"), lambda c: None)
    )
    fanout = (
        FanOut("parallel")
        .branch(Agent("y").on(R.changed("a"), lambda c: None))
        .branch(Agent("z").on(R.changed("b"), lambda c: None))
    )

    tape = SessionTape()
    reactor_p = R.compile(pipeline, tape=tape)
    reactor_f = R.compile(fanout, tape=tape)

    assert len(reactor_p.rules) == 1
    assert len(reactor_f.rules) == 2


@pytest.mark.asyncio
async def test_end_to_end_declarative_reactor() -> None:
    """Full chain: R.signal → .on(R.rising()) → R.compile → reactor fires handler."""
    bus = EventBus()
    tape = SessionTape()
    bus.subscribe(tape.record)
    R.attach(bus)

    temp = R.signal("temp", 72)

    fires: list[tuple] = []

    async def handler(change) -> None:
        fires.append((change.value, change.previous))

    agent = (
        Agent("cooler", "gemini-2.5-flash")
        .instruct("Cool the building.")
        .on(
            R.rising("temp").where(lambda v, prev: v > 90),
            handler,
            priority=10,
        )
    )

    reactor = R.compile(agent, tape=tape, bus=bus)
    task = asyncio.create_task(reactor.run())
    await asyncio.sleep(0.05)

    temp.set(80)   # rising but below 90 — no fire
    temp.set(95)   # rising above 90 — fires
    temp.set(92)   # falling — no fire
    await asyncio.sleep(0.1)

    reactor.stop()
    await asyncio.sleep(0.02)
    task.cancel()

    assert fires == [(95, 80)]


@pytest.mark.asyncio
async def test_reactor_plugin_owns_lifecycle() -> None:
    """``ReactorPlugin`` starts/stops the reactor from ADK session callbacks."""
    bus = EventBus()
    tape = SessionTape()
    bus.subscribe(tape.record)
    R.attach(bus)

    sig = R.signal("ping", False)
    fired = asyncio.Event()

    async def handler(_change) -> None:
        fired.set()

    agent = Agent("listener").on(R.changed("ping"), handler)
    reactor = R.compile(agent, tape=tape, bus=bus)
    plugin = ReactorPlugin(reactor)

    await plugin.on_session_start()
    sig.set(True)
    await asyncio.wait_for(fired.wait(), timeout=0.3)
    await plugin.on_session_end()


def test_debounce_throttle_are_immutable() -> None:
    """Fix from 0.17.0: ``.debounce()`` / ``.throttle()`` return fresh predicates."""
    R.signal("temp", 0)
    base = R.changed("temp")
    debounced = base.debounce(50)
    assert debounced is not base
    assert base._debounce_ms == 0.0
    assert debounced._debounce_ms == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
