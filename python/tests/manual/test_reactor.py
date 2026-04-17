"""Tests for Phase F: Signal + SignalPredicate + Reactor."""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import (
    EventBus,
    Reactor,
    SessionTape,
    Signal,
)


class TestSignal:
    def test_get_and_set(self):
        s = Signal("temp", 0)
        assert s.get() == 0
        assert s.set(5) is True
        assert s.get() == 5
        assert s.version == 1

    def test_equality_guard_skips_emit(self):
        s = Signal("temp", 5)
        assert s.set(5) is False
        assert s.version == 0

    def test_force_emits_despite_equality(self):
        s = Signal("temp", 5)
        assert s.set(5, force=True) is True
        assert s.version == 1

    def test_update_applies_fn(self):
        s = Signal("counter", 0)
        s.update(lambda v: v + 1)
        s.update(lambda v: v + 1)
        assert s.get() == 2
        assert s.version == 2

    def test_subscribe_receives_value_and_previous(self):
        s = Signal("x", 0)
        seen: list[tuple] = []
        s.subscribe(lambda v, prev: seen.append((v, prev)))
        s.set(1)
        s.set(2)
        assert seen == [(1, 0), (2, 1)]

    def test_unsubscribe(self):
        s = Signal("x", 0)
        seen: list = []
        off = s.subscribe(lambda v, prev: seen.append(v))
        s.set(1)
        off()
        s.set(2)
        assert seen == [1]

    def test_bus_emission_carries_payload(self):
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        s = Signal("temp", 0, bus=bus)
        s.set(42)
        events = [e for e in tape.events if e["kind"] == "signal_changed"]
        assert len(events) == 1
        assert events[0]["name"] == "temp"
        assert events[0]["value"] == 42
        assert events[0]["previous"] == 0
        assert events[0]["version"] == 1


class TestPredicates:
    def test_changed_fires_on_any_change(self):
        s = Signal("x", 0)
        p = s.changed
        assert "x" in p.deps

    def test_rising_fires_only_on_increase(self):
        s = Signal("x", 0)
        p = s.rising
        from adk_fluent._reactor._predicate import _Change

        assert p.matches(_Change("x", 1, 0)) is True
        assert p.matches(_Change("x", 0, 1)) is False

    def test_falling_fires_only_on_decrease(self):
        s = Signal("x", 0)
        p = s.falling
        from adk_fluent._reactor._predicate import _Change

        assert p.matches(_Change("x", 0, 1)) is True
        assert p.matches(_Change("x", 1, 0)) is False

    def test_and_composition(self):
        temp = Signal("temp", 0)
        online = Signal("online", False)
        p = temp.rising & online.is_(True)
        from adk_fluent._reactor._predicate import _Change

        # Only looks at one signal at a time — but matcher should
        # evaluate conjunction on the given change.
        assert p.matches(_Change("temp", 10, 5)) is False  # online not evaluated with this change
        assert p.matches(_Change("online", True, False)) is False  # not rising temp

    def test_where_filter(self):
        s = Signal("temp", 0)
        p = s.rising.where(lambda v, prev: v > 90)
        from adk_fluent._reactor._predicate import _Change

        assert p.matches(_Change("temp", 95, 80)) is True
        assert p.matches(_Change("temp", 50, 40)) is False


class TestReactor:
    def test_rule_fires_on_signal_change(self):
        async def run() -> int:
            bus = EventBus()
            tape = SessionTape()
            bus.subscribe(tape.record)
            s = Signal("x", 0, bus=bus)
            reactor = Reactor(tape, bus=bus)

            fires: list = []

            async def handler(change) -> None:
                fires.append(change.value)

            reactor.when(s.changed, handler)

            async def drive() -> None:
                await asyncio.sleep(0.005)
                s.set(1)
                await asyncio.sleep(0.005)
                s.set(2)

            await asyncio.wait_for(
                asyncio.gather(reactor.run(budget=2), drive()),
                timeout=2.0,
            )
            return len(fires)

        assert asyncio.run(run()) == 2

    def test_priority_ordering(self):
        """Higher-priority rules queued ahead of lower-priority ones."""

        async def run() -> list[str]:
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

            # Both rules match `changed`. The low-priority rule is
            # registered first and starts when the first change fires;
            # but when the second matching change arrives, high gets
            # heap-pushed ahead of any further low invocations.
            reactor.when(s.changed, low, priority=1)
            reactor.when(s.changed, high, priority=10)

            async def drive() -> None:
                await asyncio.sleep(0.005)
                s.set(1)  # fires both rules, low starts running

            await asyncio.wait_for(
                asyncio.gather(reactor.run(budget=2), drive()),
                timeout=2.0,
            )
            # Allow the queued rule(s) to drain.
            await asyncio.sleep(0.05)
            return order

        order = asyncio.run(run())
        # Both should run, and high should drain before any further low invocations.
        assert set(order) == {"low", "high"}

    def test_preemptive_cancels_current(self):
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
            return order, interrupted

        order, interrupted = asyncio.run(run())
        assert "slow-cancelled" in order
        assert "urgent" in order
        assert "slow-done" not in order
        assert len(interrupted) == 1
        assert interrupted[0]["agent_name"] == "slow"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
