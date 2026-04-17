"""Tests for Phase A: seq numbers + cursor reads on SessionTape."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from adk_fluent import EventRecord, SessionTape
from adk_fluent._harness._events import HarnessEvent


@dataclass(frozen=True)
class _E(HarnessEvent):
    kind: str = "fake"
    payload: str = ""


class TestSeqNumbers:
    def test_seq_starts_at_zero(self):
        tape = SessionTape()
        seq = tape.record(_E(payload="a"))
        assert seq == 0

    def test_seq_is_monotonic(self):
        tape = SessionTape()
        seqs = [tape.record(_E(payload=str(i))) for i in range(5)]
        assert seqs == [0, 1, 2, 3, 4]

    def test_seq_is_on_entry(self):
        tape = SessionTape()
        tape.record(_E(payload="a"))
        tape.record(_E(payload="b"))
        entries = tape.events
        assert entries[0]["seq"] == 0
        assert entries[1]["seq"] == 1

    def test_head_and_watermark(self):
        tape = SessionTape()
        assert tape.head == 0
        assert tape.watermark == 0
        tape.record(_E(payload="a"))
        tape.record(_E(payload="b"))
        assert tape.head == 2
        assert tape.watermark == 0

    def test_watermark_advances_with_eviction(self):
        tape = SessionTape(max_events=2)
        tape.record(_E(payload="a"))
        tape.record(_E(payload="b"))
        tape.record(_E(payload="c"))  # evicts seq 0
        assert tape.head == 3
        assert tape.watermark == 1

    def test_clear_resets_seq(self):
        tape = SessionTape()
        tape.record(_E(payload="a"))
        tape.record(_E(payload="b"))
        assert tape.head == 2
        tape.clear()
        assert tape.head == 0
        new_seq = tape.record(_E(payload="c"))
        assert new_seq == 0


class TestSinceCursor:
    def test_since_returns_all_when_cursor_zero(self):
        tape = SessionTape()
        for i in range(3):
            tape.record(_E(payload=str(i)))
        entries = list(tape.since(0))
        assert len(entries) == 3
        assert [e["seq"] for e in entries] == [0, 1, 2]

    def test_since_skips_older_entries(self):
        tape = SessionTape()
        for i in range(5):
            tape.record(_E(payload=str(i)))
        entries = list(tape.since(3))
        assert [e["seq"] for e in entries] == [3, 4]

    def test_since_head_yields_empty(self):
        tape = SessionTape()
        tape.record(_E(payload="a"))
        tape.record(_E(payload="b"))
        entries = list(tape.since(tape.head))
        assert entries == []

    def test_since_handles_expired_cursor(self):
        # Cursor below watermark — consumer gets only the surviving tail.
        tape = SessionTape(max_events=2)
        for i in range(5):
            tape.record(_E(payload=str(i)))
        entries = list(tape.since(0))
        assert [e["seq"] for e in entries] == [3, 4]

    def test_records_since_returns_typed(self):
        tape = SessionTape()
        tape.record(_E(payload="hi"))
        records = list(tape.records_since(0))
        assert len(records) == 1
        assert isinstance(records[0], EventRecord)
        assert records[0].seq == 0
        assert records[0].kind == "fake"
        assert records[0].payload == {"payload": "hi"}


class TestEventRecord:
    def test_from_dict_roundtrip(self):
        entry = {
            "seq": 7,
            "t": 0.123,
            "kind": "fake",
            "type": "_E",
            "payload": "hi",
            "extra": 42,
        }
        rec = EventRecord.from_dict(entry)
        assert rec.seq == 7
        assert rec.t == 0.123
        assert rec.kind == "fake"
        assert rec.type == "_E"
        assert rec.payload == {"payload": "hi", "extra": 42}

    def test_from_dict_with_missing_fields(self):
        rec = EventRecord.from_dict({})
        assert rec.seq == -1
        assert rec.t == 0.0
        assert rec.kind == ""
        assert rec.payload == {}


class TestAsyncTail:
    def test_tail_yields_existing_then_follows(self):
        async def run() -> list[int]:
            tape = SessionTape()
            tape.record(_E(payload="a"))
            tape.record(_E(payload="b"))
            collected: list[int] = []

            async def consume() -> None:
                async for entry in tape.tail(from_seq=0):
                    collected.append(int(entry["seq"]))
                    if len(collected) >= 4:
                        return

            async def produce() -> None:
                await asyncio.sleep(0.01)
                tape.record(_E(payload="c"))
                await asyncio.sleep(0.01)
                tape.record(_E(payload="d"))

            await asyncio.wait_for(asyncio.gather(consume(), produce()), timeout=2.0)
            return collected

        collected = asyncio.run(run())
        assert collected == [0, 1, 2, 3]

    def test_tail_resumes_from_cursor(self):
        async def run() -> list[int]:
            tape = SessionTape()
            for _ in range(5):
                tape.record(_E(payload="x"))
            collected: list[int] = []

            async def consume() -> None:
                async for entry in tape.tail(from_seq=3):
                    collected.append(int(entry["seq"]))
                    if len(collected) >= 3:
                        return

            async def produce() -> None:
                await asyncio.sleep(0.01)
                tape.record(_E(payload="new"))

            await asyncio.wait_for(asyncio.gather(consume(), produce()), timeout=2.0)
            return collected

        collected = asyncio.run(run())
        assert collected == [3, 4, 5]


class TestRecordDict:
    def test_record_dict_assigns_seq(self):
        tape = SessionTape()
        seq = tape.record_dict({"kind": "custom", "type": "X", "foo": 1})
        assert seq == 0
        assert tape.head == 1

    def test_record_dict_preserves_existing_seq(self):
        tape = SessionTape()
        tape.record_dict({"seq": 10, "kind": "custom", "type": "X"})
        # Counter must advance past imported seq.
        next_seq = tape.record(_E(payload="a"))
        assert next_seq == 11


class TestLoadBackfill:
    def test_load_backfills_missing_seq(self, tmp_path: Path):
        # Simulate a pre-cursor tape: JSONL without ``seq`` keys.
        path = tmp_path / "old.jsonl"
        path.write_text('{"kind": "a", "type": "X", "t": 0.0}\n{"kind": "b", "type": "X", "t": 0.1}\n')
        tape = SessionTape.load(path)
        assert tape.size == 2
        assert tape.events[0]["seq"] == 0
        assert tape.events[1]["seq"] == 1
        # New records continue the sequence.
        next_seq = tape.record(_E(payload="c"))
        assert next_seq == 2

    def test_save_load_roundtrip_preserves_seq(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        tape = SessionTape()
        for i in range(3):
            tape.record(_E(payload=str(i)))
        tape.save(path)

        loaded = SessionTape.load(path)
        assert [e["seq"] for e in loaded.events] == [0, 1, 2]
        assert loaded.head == 3


class TestSummary:
    def test_summary_includes_head_and_watermark(self):
        tape = SessionTape()
        tape.record(_E(payload="a"))
        tape.record(_E(payload="b"))
        summary = tape.summary()
        assert summary["head"] == 2
        assert summary["watermark"] == 0
        assert summary["total_events"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
