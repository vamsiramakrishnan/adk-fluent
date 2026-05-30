"""Regression tests for reactor preemptive scheduling (BUG 1).

Before the fix, a ``preemptive=True`` higher-priority rule cancelled the
running task but was then itself pushed onto ``_pending`` (because the
just-cancelled task's ``.done()`` was still False). The cancelled task's
``finally`` drained ``_pending`` from inside its own cancellation, so the
queued preempting rule was lost — net effect: NOTHING ran.
"""

from __future__ import annotations

import asyncio

from adk_fluent import EventBus, Reactor, SessionTape, Signal


def test_preemptive_runs_preempting_rule_after_clean_cancel():
    """The preempting rule must run after the victim is cleanly cancelled."""

    async def run() -> tuple[list[str], list[dict]]:
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        s = Signal("x", 0, bus=bus)
        reactor = Reactor(tape, bus=bus)

        order: list[str] = []

        async def slow(change) -> None:
            try:
                await asyncio.sleep(0.5)
                order.append("slow-done")
            except asyncio.CancelledError:
                order.append("slow-cancelled")
                raise

        async def urgent(change) -> None:
            order.append("urgent")

        reactor.when(s.is_(1), slow, name="slow", priority=1)
        reactor.when(s.is_(2), urgent, name="urgent", priority=100, preemptive=True)

        async def drive() -> None:
            await asyncio.sleep(0.005)
            s.set(1)
            await asyncio.sleep(0.01)
            s.set(2)

        await asyncio.wait_for(
            asyncio.gather(reactor.run(budget=2), drive()),
            timeout=2.0,
        )
        await asyncio.sleep(0.05)
        interrupted = [e for e in tape.events if e["kind"] == "interrupted"]
        return order, interrupted, list(reactor._pending)

    order, interrupted, pending = asyncio.run(run())
    assert "slow-cancelled" in order, f"victim was not cancelled: {order}"
    assert "urgent" in order, f"preempting rule never ran (BUG 1): {order}"
    assert "slow-done" not in order
    # urgent must run AFTER the victim is cleanly torn down — deterministic
    # ordering is the whole point of awaiting the cancellation in _submit.
    assert order.index("urgent") > order.index("slow-cancelled")
    # The preempting rule must be dispatched directly, never parked on the
    # pending queue (the root cause of BUG 1 was queueing it there and
    # relying on the cancelled task's finally to drain it).
    assert pending == [], f"preempting rule left queued: {pending}"
    assert len(interrupted) == 1
    assert interrupted[0]["agent_name"] == "slow"


def test_two_preemptive_rules_both_eventually_run():
    """Two preemptive rules on one signal: both fire, last preempts first."""

    async def run() -> list[str]:
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        s = Signal("x", 0, bus=bus)
        reactor = Reactor(tape, bus=bus)

        order: list[str] = []

        async def first(change) -> None:
            try:
                await asyncio.sleep(0.5)
                order.append("first-done")
            except asyncio.CancelledError:
                order.append("first-cancelled")
                raise

        async def second(change) -> None:
            order.append("second")

        reactor.when(s.is_(1), first, name="first", priority=1, preemptive=True)
        reactor.when(s.is_(2), second, name="second", priority=100, preemptive=True)

        async def drive() -> None:
            await asyncio.sleep(0.005)
            s.set(1)
            await asyncio.sleep(0.01)
            s.set(2)

        await asyncio.wait_for(
            asyncio.gather(reactor.run(budget=2), drive()),
            timeout=2.0,
        )
        await asyncio.sleep(0.05)
        return order

    order = asyncio.run(run())
    assert "first-cancelled" in order
    assert "second" in order


def test_non_preemptive_both_run():
    """Pin existing correct behaviour: non-preemptive rules both run (queued)."""

    async def run() -> set[str]:
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        s = Signal("x", 0, bus=bus)
        reactor = Reactor(tape, bus=bus)

        order: list[str] = []

        async def low(change) -> None:
            await asyncio.sleep(0.01)
            order.append("low")

        async def high(change) -> None:
            await asyncio.sleep(0.001)
            order.append("high")

        reactor.when(s.is_(1), low, name="low", priority=1)
        reactor.when(s.is_(2), high, name="high", priority=10)

        async def drive() -> None:
            await asyncio.sleep(0.005)
            s.set(1)
            await asyncio.sleep(0.002)
            s.set(2)

        await asyncio.wait_for(
            asyncio.gather(reactor.run(budget=2), drive()),
            timeout=2.0,
        )
        await asyncio.sleep(0.05)
        return set(order)

    assert asyncio.run(run()) == {"low", "high"}
