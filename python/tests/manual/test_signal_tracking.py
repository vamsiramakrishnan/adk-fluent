"""Tests for Signal auto-tracking (``computed`` / ``reaction``)."""

from __future__ import annotations

import pytest

from adk_fluent import Signal, computed, reaction, track_reads


class TestTrackReads:
    def test_tracks_signals_read_in_block(self) -> None:
        a = Signal("a", 1)
        b = Signal("b", 2)
        c = Signal("c", 3)  # not read

        with track_reads() as deps:
            _ = a.get() + b.get()

        names = {s.name for s in deps}
        assert names == {"a", "b"}
        assert c not in deps

    def test_nested_trackers_isolated(self) -> None:
        a = Signal("a", 1)
        b = Signal("b", 2)

        with track_reads() as outer:
            a.get()
            with track_reads() as inner:
                b.get()

        assert {s.name for s in outer} == {"a"}
        assert {s.name for s in inner} == {"b"}


class TestComputed:
    def test_initial_value_from_fn(self) -> None:
        price = Signal("price", 100.0)
        tax = Signal("tax", 0.1)
        total = computed("total", lambda: price.get() * (1 + tax.get()))
        assert total.get() == pytest.approx(110.0)

    def test_recomputes_on_dep_change(self) -> None:
        price = Signal("price", 100.0)
        tax = Signal("tax", 0.1)
        total = computed("total", lambda: price.get() * (1 + tax.get()))

        price.set(200.0)
        assert total.get() == pytest.approx(220.0)
        tax.set(0.2)
        assert total.get() == pytest.approx(240.0)

    def test_unread_signal_is_not_a_dep(self) -> None:
        gated = Signal("gated", False)
        base = Signal("base", 10)

        def compute() -> int:
            if gated.get():
                return base.get() * 2
            return 0

        out = computed("out", compute)
        assert out.get() == 0

        # With gated=False the compute didn't read base, so base changes
        # shouldn't re-run the derivation.
        base.set(99)
        assert out.get() == 0

        # Flip the gate: now gated is a dep AND on next recompute base is read.
        gated.set(True)
        assert out.get() == 198


class TestReaction:
    def test_runs_once_and_rereuns_on_change(self) -> None:
        a = Signal("a", 1)
        b = Signal("b", 2)
        seen: list[int] = []

        reaction(lambda: seen.append(a.get() + b.get()))

        assert seen == [3]
        a.set(10)
        assert seen == [3, 12]
        b.set(5)
        assert seen == [3, 12, 15]

    def test_unsubscribe_stops_reactions(self) -> None:
        a = Signal("a", 1)
        seen: list[int] = []

        off = reaction(lambda: seen.append(a.get()))
        assert seen == [1]
        a.set(2)
        assert seen == [1, 2]
        off()
        a.set(3)
        assert seen == [1, 2]  # no more fires after unsubscribe


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
