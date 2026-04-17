"""Tests for Phase D: resumable streaming via stream_from_cursor."""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import SessionTape, stream_from_cursor
from adk_fluent._harness._events import TextChunk, ToolCallStart


class TestStreamFromCursor:
    def test_drains_history(self):
        tape = SessionTape()
        for word in ("hello ", "world", "!"):
            tape.record(TextChunk(text=word))

        async def collect() -> list[str]:
            out: list[str] = []
            gen = stream_from_cursor(tape, from_seq=0)
            # Only drain the history, not the infinite tail.
            try:
                for _ in range(3):
                    out.append(await gen.__anext__())
            finally:
                await gen.aclose()
            return out

        assert asyncio.run(collect()) == ["hello ", "world", "!"]

    def test_filters_by_kind(self):
        tape = SessionTape()
        tape.record(TextChunk(text="hi"))
        tape.record(ToolCallStart(tool_name="bash"))
        tape.record(TextChunk(text="bye"))

        async def collect() -> list[str]:
            out: list[str] = []
            gen = stream_from_cursor(tape, from_seq=0)
            try:
                for _ in range(2):
                    out.append(await gen.__anext__())
            finally:
                await gen.aclose()
            return out

        assert asyncio.run(collect()) == ["hi", "bye"]

    def test_resumes_from_mid_stream(self):
        tape = SessionTape()
        for word in ("a", "b", "c", "d"):
            tape.record(TextChunk(text=word))

        async def collect() -> list[str]:
            out: list[str] = []
            gen = stream_from_cursor(tape, from_seq=2)
            try:
                for _ in range(2):
                    out.append(await gen.__anext__())
            finally:
                await gen.aclose()
            return out

        assert asyncio.run(collect()) == ["c", "d"]

    def test_follows_live_tail(self):
        tape = SessionTape()
        tape.record(TextChunk(text="first"))

        async def run() -> list[str]:
            collected: list[str] = []

            async def consume() -> None:
                async for chunk in stream_from_cursor(tape, from_seq=0):
                    collected.append(chunk)
                    if len(collected) >= 3:
                        return

            async def produce() -> None:
                await asyncio.sleep(0.01)
                tape.record(TextChunk(text="second"))
                await asyncio.sleep(0.01)
                tape.record(TextChunk(text="third"))

            await asyncio.wait_for(
                asyncio.gather(consume(), produce()),
                timeout=2.0,
            )
            return collected

        assert asyncio.run(run()) == ["first", "second", "third"]

    def test_kind_none_yields_raw_entries(self):
        tape = SessionTape()
        tape.record(TextChunk(text="hi"))
        tape.record(ToolCallStart(tool_name="bash"))

        async def collect() -> list[dict]:
            out: list[dict] = []
            gen = stream_from_cursor(tape, from_seq=0, kind=None)
            try:
                for _ in range(2):
                    out.append(await gen.__anext__())
            finally:
                await gen.aclose()
            return out

        entries = asyncio.run(collect())
        assert entries[0]["kind"] == "text"
        assert entries[1]["kind"] == "tool_call_start"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
