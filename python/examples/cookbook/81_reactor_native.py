"""Declarative Reactive Agents — R Namespace + Builder.on()

Real-world scenario: a debt collection pipeline where conversation phases
drive agent activation. Each specialist (greeter, verifier, negotiator,
closer) declares when it should fire via ``.on(R.is_("phase", ...))``.
A de-escalation agent preempts the negotiator when sentiment drops.
R.compile() wires everything — zero manual dispatch.

Before (manual wiring — hand-built sequence)::

    reactor = Reactor(tape, bus)
    reactor.when(phase_pred, greeter_fn, priority=10)
    reactor.when(verify_pred, verifier_fn, priority=10)
    reactor.when(negotiate_pred, negotiator_fn, priority=10)
    reactor.when(sentiment_pred, de_escalate_fn, priority=1)

After (declarative — rules live on the builders)::

    greeter      = Agent("greeter").on(R.is_("phase", "greeting"))
    negotiator   = Agent("negotiator").on(R.is_("phase", "negotiate"))
    de_escalator = Agent("de_escalator").on(R.falling("sentiment"), preemptive=True)
    reactor = R.compile(greeter, negotiator, de_escalator, tape=tape, bus=bus)

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
    """``R.signal(name)`` is get-or-create: same name → same instance."""
    phase = R.signal("phase", "greeting")
    phase2 = R.signal("phase")
    assert phase is phase2
    assert R.get("phase").value == "greeting"


def test_r_predicates_for_conversation_phases() -> None:
    """``R.is_()`` matches exact phase; ``R.falling()`` detects sentiment drops."""
    R.signal("phase", "greeting")
    R.signal("sentiment", 0.7)

    at_negotiate = R.is_("phase", "negotiate")
    upset = R.falling("sentiment").where(lambda v, prev: v < 0.3)

    from adk_fluent._reactor._predicate import _Change

    assert at_negotiate.matches(_Change("phase", "negotiate", "greeting"))
    assert not at_negotiate.matches(_Change("phase", "greeting", "negotiate"))
    assert upset.matches(_Change("sentiment", 0.2, 0.7))
    assert not upset.matches(_Change("sentiment", 0.5, 0.7))  # fell but not below 0.3


def test_builder_on_for_phase_agents() -> None:
    """``.on()`` attaches declarative rules — each agent knows when to activate."""
    R.signal("phase", "greeting")
    R.signal("sentiment", 0.7)

    greeter = (
        Agent("greeter", "gemini-2.5-flash")
        .instruct("Greet the customer. Introduce yourself as Acme Collections.")
        .on(R.is_("phase", "greeting"), priority=10)
    )
    de_escalator = (
        Agent("de_escalator", "gemini-2.5-flash")
        .instruct("Acknowledge frustration. Offer the most flexible payment plan.")
        .on(R.falling("sentiment").where(lambda v, prev: v < 0.3), priority=1, preemptive=True)
    )

    assert greeter._reactor_rules[0].priority == 10
    assert de_escalator._reactor_rules[0].preemptive is True
    assert de_escalator._reactor_rules[0].priority == 1


def test_compile_collects_all_phase_agents() -> None:
    """``R.compile()`` wires greeter + verifier + negotiator + closer into one reactor."""
    R.signal("phase", "greeting")
    R.signal("sentiment", 0.7)

    greeter = Agent("greeter").on(R.is_("phase", "greeting"), priority=10)
    verifier = Agent("verifier").on(R.is_("phase", "verify"), priority=10)
    negotiator = Agent("negotiator").on(R.is_("phase", "negotiate"), priority=10)
    de_escalator = Agent("de_escalator").on(
        R.falling("sentiment").where(lambda v, prev: v < 0.3), priority=1, preemptive=True
    )
    closer = Agent("closer").on(R.is_("phase", "commit"), priority=10)

    tape = SessionTape()
    reactor = R.compile(greeter, verifier, negotiator, de_escalator, closer, tape=tape)
    assert len(reactor.rules) == 5


def test_compile_walks_composite_builders() -> None:
    """Rules inside Pipeline/FanOut are collected by R.compile()."""
    R.signal("phase", "greeting")
    R.signal("sentiment", 0.7)

    pipeline = (
        Pipeline("intake")
        .step(Agent("greeter").on(R.changed("phase"), lambda c: None))
        .step(Agent("logger").on(R.changed("sentiment"), lambda c: None))
    )

    tape = SessionTape()
    reactor = R.compile(pipeline, tape=tape)
    assert len(reactor.rules) == 2


@pytest.mark.asyncio
async def test_phase_transition_fires_handler() -> None:
    """Setting phase to 'negotiate' fires the negotiator's handler."""
    bus = EventBus()
    tape = SessionTape()
    bus.subscribe(tape.record)
    R.attach(bus)

    phase = R.signal("phase", "greeting")
    fired: list[str] = []

    async def handler(change) -> None:
        fired.append(f"activated:{change.value}")

    negotiator = (
        Agent("negotiator", "gemini-2.5-flash")
        .instruct("Present the outstanding balance. Offer 3 payment plans.")
        .on(R.is_("phase", "negotiate"), handler, priority=10)
    )

    reactor = R.compile(negotiator, tape=tape, bus=bus)
    task = asyncio.create_task(reactor.run())
    await asyncio.sleep(0.05)

    phase.set("verify")    # not negotiate — no fire
    phase.set("negotiate")  # match — fires
    phase.set("commit")    # not negotiate — no fire
    await asyncio.sleep(0.1)

    reactor.stop()
    await asyncio.sleep(0.02)
    task.cancel()

    assert fired == ["activated:negotiate"]


@pytest.mark.asyncio
async def test_reactor_plugin_owns_lifecycle() -> None:
    """``ReactorPlugin`` starts/stops the reactor from ADK session callbacks."""
    bus = EventBus()
    tape = SessionTape()
    bus.subscribe(tape.record)
    R.attach(bus)

    phase = R.signal("phase", "greeting")
    fired = asyncio.Event()

    async def handler(_change) -> None:
        fired.set()

    listener = Agent("listener").on(R.changed("phase"), handler)
    reactor = R.compile(listener, tape=tape, bus=bus)
    plugin = ReactorPlugin(reactor)

    await plugin.on_session_start()
    phase.set("verify")
    await asyncio.wait_for(fired.wait(), timeout=0.3)
    await plugin.on_session_end()


def test_debounce_throttle_are_immutable() -> None:
    """``.debounce()`` / ``.throttle()`` return fresh predicates (0.17.0 fix)."""
    R.signal("sentiment", 0.7)
    base = R.changed("sentiment")
    debounced = base.debounce(50)
    assert debounced is not base
    assert base._debounce_ms == 0.0
    assert debounced._debounce_ms == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
