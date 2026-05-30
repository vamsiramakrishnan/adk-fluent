"""Regression tests for Signal.update() atomicity (BUG 2).

``update(fn)`` performs a read-modify-write. Under the single-threaded
asyncio model the RMW must be a single synchronous critical section with
no intervening ``await`` — otherwise two concurrently-scheduled updates
can read the same base value and the later write clobbers the earlier one
(a lost update).
"""

from __future__ import annotations

import asyncio

from adk_fluent import Signal


def test_interleaved_updates_no_lost_update():
    """Many concurrent increment tasks must all be reflected — no lost writes."""

    async def run() -> int:
        s = Signal("counter", 0)
        n = 200

        async def bump() -> None:
            # Yield first so the scheduler interleaves all tasks before any
            # of them performs its RMW; if update() leaked an await between
            # read and write, the increments would race and be lost.
            await asyncio.sleep(0)
            s.update(lambda v: v + 1)

        await asyncio.gather(*(bump() for _ in range(n)))
        return s.get()

    assert asyncio.run(run()) == 200


def test_update_snapshots_current_value_for_previous():
    """The emitted ``previous`` must match the value update actually read."""

    s = Signal("x", 10)
    seen: list[tuple] = []
    s.subscribe(lambda v, prev: seen.append((v, prev)))

    s.update(lambda v: v + 5)
    s.update(lambda v: v * 2)

    assert s.get() == 30
    assert seen == [(15, 10), (30, 15)]
    assert s.version == 2


def test_update_equality_guard_skips_emit():
    """update() that produces an equal value is a no-op (delegates to set)."""

    s = Signal("x", 7)
    assert s.update(lambda v: v) is False
    assert s.version == 0
