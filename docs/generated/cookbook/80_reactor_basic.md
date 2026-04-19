# Signals + Reactor — reactive state over the durable tape.

Shows the three reactive primitives added in Phase F / Phase G / auto-tracking:

1. :class:`Signal` — typed state cell with version tracking. Mutations
   emit :class:`SignalChanged` on the ambient :class:`EventBus` (which
   in turn lands on the :class:`SessionTape`).
2. :class:`Reactor` — cursor-following scheduler. Registered rules fire
   when their :class:`SignalPredicate` matches a change on the tape.
3. ``computed(name, fn)`` — derived signal that auto-tracks reads of
   other signals and re-runs on any dep change.

Run: ``uv run pytest examples/cookbook/80_reactor_basic.py -v``

:::{tip} What you'll learn
How to manage interactive sessions with agents.
:::

_Source: `80_reactor_basic.py`_

```python
from __future__ import annotations

import asyncio

import pytest

from adk_fluent import H, Reactor, Signal, computed


def test_signal_emits_on_change() -> None:
    """Setting a new value emits; repeating the value is a no-op."""
    bus = H.event_bus()
    tape = bus.tape()

    temp = Signal("temperature", 72.0, bus=bus)

    assert temp.set(85.0) is True
    assert temp.set(85.0) is False  # equal — skipped
    assert temp.set(85.0, force=True) is True

    kinds = [e["kind"] for e in tape.events]
    assert kinds.count("signal_changed") == 2


def test_signal_predicate_filters_by_edge() -> None:
    """``.rising`` only matches when the value actually rises above 90."""
    temp = Signal("temperature", 72.0)
    rising_90 = temp.rising.where(lambda v, prev: v > 90)

    from adk_fluent._reactor._predicate import _Change

    assert rising_90.matches(_Change("temperature", 95.0, 89.0))  # rising above 90
    assert not rising_90.matches(_Change("temperature", 80.0, 95.0))  # falling
    assert not rising_90.matches(_Change("temperature", 85.0, 72.0))  # rising but below 90


def test_computed_auto_tracks_reads() -> None:
    """``computed`` re-runs when any signal it read changes."""
    price = Signal("price", 100.0)
    tax_rate = Signal("tax", 0.1)

    total = computed("total", lambda: price.get() * (1 + tax_rate.get()))
    assert total.get() == pytest.approx(110.0)

    price.set(200.0)
    assert total.get() == pytest.approx(220.0)

    tax_rate.set(0.2)
    assert total.get() == pytest.approx(240.0)


@pytest.mark.asyncio
async def test_reactor_fires_rule_on_signal() -> None:
    """End-to-end: signal change → predicate match → handler fires."""
    bus = H.event_bus()
    tape = bus.tape()

    temp = Signal("temp", 72.0, bus=bus)
    alerts: list[float] = []
    done = asyncio.Event()

    async def alert_handler(change) -> None:  # noqa: ANN001
        alerts.append(change.value)
        done.set()

    reactor = Reactor(tape, bus=bus)
    reactor.when(temp.rising.where(lambda v, prev: v > 90), alert_handler, name="hot_alert", priority=10)

    # Run the reactor in the background with a small budget so the test ends.
    run_task = asyncio.create_task(reactor.run(budget=1))
    await asyncio.sleep(0)  # hand control to the reactor

    temp.set(95.0)  # should trip the predicate

    fires = await asyncio.wait_for(run_task, timeout=1.0)
    assert fires == 1

    # Wait for the spawned handler task to complete.
    await asyncio.wait_for(done.wait(), timeout=1.0)
    assert alerts == [95.0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```
