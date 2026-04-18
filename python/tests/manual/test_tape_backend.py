"""Tests for Phase B: pluggable TapeBackend implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from adk_fluent import SessionTape
from adk_fluent._harness._events import HarnessEvent
from adk_fluent._session._tape_backend import (
    ChainBackend,
    InMemoryBackend,
    JsonlBackend,
    NullBackend,
    TapeBackend,
)


@dataclass(frozen=True)
class _E(HarnessEvent):
    kind: str = "fake"
    payload: str = ""


class TestProtocolConformance:
    def test_in_memory_matches_protocol(self):
        assert isinstance(InMemoryBackend(), TapeBackend)

    def test_null_matches_protocol(self):
        assert isinstance(NullBackend(), TapeBackend)

    def test_jsonl_matches_protocol(self, tmp_path: Path):
        assert isinstance(JsonlBackend(tmp_path / "t.jsonl"), TapeBackend)

    def test_chain_matches_protocol(self):
        assert isinstance(ChainBackend(InMemoryBackend()), TapeBackend)


class TestInMemoryBackend:
    def test_append_is_noop(self):
        b = InMemoryBackend()
        b.append({"seq": 0, "kind": "x"})
        assert b.read_since(0) == []
        assert b.head() == 0

    def test_clear_is_noop(self):
        b = InMemoryBackend()
        b.clear()  # must not raise


class TestNullBackend:
    def test_explicit_discard(self):
        b = NullBackend()
        b.append({"seq": 0, "kind": "x"})
        assert b.read_since(0) == []
        assert b.head() == 0


class TestJsonlBackend:
    def test_appends_survive_roundtrip(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        b = JsonlBackend(path)
        b.append({"seq": 0, "kind": "a", "type": "X"})
        b.append({"seq": 1, "kind": "b", "type": "X"})

        # Reopen — the new instance rescans the file on construction.
        b2 = JsonlBackend(path)
        assert b2.head() == 2
        entries = b2.read_since(0)
        assert [e["seq"] for e in entries] == [0, 1]

    def test_read_since_filters_by_seq(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        b = JsonlBackend(path)
        for i in range(5):
            b.append({"seq": i, "kind": "k", "type": "X"})
        entries = b.read_since(3)
        assert [e["seq"] for e in entries] == [3, 4]

    def test_head_tracks_max_seq(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        b = JsonlBackend(path)
        b.append({"seq": 10, "kind": "k", "type": "X"})
        assert b.head() == 11

    def test_clear_removes_file(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        b = JsonlBackend(path)
        b.append({"seq": 0, "kind": "k", "type": "X"})
        assert path.exists()
        b.clear()
        assert not path.exists()
        assert b.head() == 0
        assert b.read_since(0) == []

    def test_skips_corrupt_lines_on_scan(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        path.write_text('not json\n{"seq": 0, "kind": "a"}\n\n{"seq": 1, "kind": "b"}\n')
        b = JsonlBackend(path)
        assert b.head() == 2
        entries = b.read_since(0)
        assert len(entries) == 2

    def test_fsync_flag_writes(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        b = JsonlBackend(path, fsync=True)
        b.append({"seq": 0, "kind": "k", "type": "X"})
        # Just verify the data hit disk through the fsync path.
        data = path.read_text().strip().splitlines()
        assert json.loads(data[0])["seq"] == 0


class TestChainBackend:
    def test_broadcasts_to_all(self, tmp_path: Path):
        mem_like = JsonlBackend(tmp_path / "a.jsonl")
        disk = JsonlBackend(tmp_path / "b.jsonl")
        chain = ChainBackend(mem_like, disk)

        chain.append({"seq": 0, "kind": "k", "type": "X"})
        chain.append({"seq": 1, "kind": "k", "type": "X"})

        assert mem_like.head() == 2
        assert disk.head() == 2

    def test_read_falls_through_to_first_nonempty(self, tmp_path: Path):
        empty = InMemoryBackend()  # always returns []
        disk = JsonlBackend(tmp_path / "disk.jsonl")
        disk.append({"seq": 0, "kind": "k", "type": "X"})
        chain = ChainBackend(empty, disk)

        out = chain.read_since(0)
        assert [e["seq"] for e in out] == [0]

    def test_head_is_max_of_constituents(self, tmp_path: Path):
        a = JsonlBackend(tmp_path / "a.jsonl")
        a.append({"seq": 2, "kind": "k"})
        b = JsonlBackend(tmp_path / "b.jsonl")
        b.append({"seq": 5, "kind": "k"})
        chain = ChainBackend(a, b)
        assert chain.head() == 6

    def test_clear_clears_all(self, tmp_path: Path):
        a = JsonlBackend(tmp_path / "a.jsonl")
        a.append({"seq": 0, "kind": "k"})
        b = JsonlBackend(tmp_path / "b.jsonl")
        b.append({"seq": 0, "kind": "k"})
        chain = ChainBackend(a, b)
        chain.clear()
        assert a.head() == 0
        assert b.head() == 0


class TestTapeBackendIntegration:
    def test_tape_defaults_to_inmemory_backend(self):
        tape = SessionTape()
        tape.record(_E(payload="a"))
        # No persistence — but no crash either.
        assert tape.size == 1

    def test_tape_forwards_record_to_backend(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        backend = JsonlBackend(path)
        tape = SessionTape(backend=backend)
        tape.record(_E(payload="a"))
        tape.record(_E(payload="b"))

        # Backend was mirrored write-through.
        assert backend.head() == 2
        entries = backend.read_since(0)
        assert [e["seq"] for e in entries] == [0, 1]
        assert entries[0]["payload"] == "a"

    def test_tape_forwards_record_dict_to_backend(self, tmp_path: Path):
        path = tmp_path / "tape.jsonl"
        backend = JsonlBackend(path)
        tape = SessionTape(backend=backend)
        tape.record_dict({"seq": 0, "kind": "custom", "type": "X", "foo": 1})
        assert backend.head() == 1
        assert backend.read_since(0)[0]["foo"] == 1

    def test_tape_recovers_from_backend(self, tmp_path: Path):
        """Crash-safe: process restarts, tape loads from backend's JSONL."""
        path = tmp_path / "tape.jsonl"
        backend = JsonlBackend(path)
        tape = SessionTape(backend=backend)
        for i in range(3):
            tape.record(_E(payload=str(i)))

        # Simulate process restart — new tape reading persisted data.
        restored = SessionTape.load(path)
        assert restored.size == 3
        assert [e["seq"] for e in restored.events] == [0, 1, 2]

    def test_tape_with_chain_backend(self, tmp_path: Path):
        primary = JsonlBackend(tmp_path / "primary.jsonl")
        mirror = JsonlBackend(tmp_path / "mirror.jsonl")
        chain = ChainBackend(primary, mirror)
        tape = SessionTape(backend=chain)
        tape.record(_E(payload="a"))

        assert primary.head() == 1
        assert mirror.head() == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
