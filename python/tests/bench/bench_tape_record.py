"""Benchmark: SessionTape.record + save.

Measures the hot recording path on the harness tape. Wave 1 replaces
``dataclasses.asdict`` with hand-rolled slot iteration and swaps the
list slice-cap for a bounded deque.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from adk_fluent._harness._events import (
    TextChunk,
    ToolCallEnd,
    ToolCallStart,
    UsageUpdate,
)
from adk_fluent._harness._tape import SessionTape

from tests.bench._common import bench, report_header


def main() -> None:
    report_header("SessionTape hot-path benchmarks")

    text = TextChunk(text="hello world")
    tool_start = ToolCallStart(tool_name="search", args={"q": "foo", "k": 10})
    tool_end = ToolCallEnd(tool_name="search", result="[]", duration_ms=12.5)
    usage = UsageUpdate(input_tokens=120, output_tokens=40, total_tokens=160, model="flash")

    tape = SessionTape()

    def record_text() -> None:
        tape.record(text)

    def record_tool_start() -> None:
        tape.record(tool_start)

    def record_tool_end() -> None:
        tape.record(tool_end)

    def record_usage() -> None:
        tape.record(usage)

    bench("record(TextChunk)", record_text, iters=200_000)
    bench("record(ToolCallStart)", record_tool_start, iters=200_000)
    bench("record(ToolCallEnd)", record_tool_end, iters=200_000)
    bench("record(UsageUpdate)", record_usage, iters=200_000)

    # Bounded tape — make sure the deque cap path is also fast.
    capped = SessionTape(max_events=1_000)
    bench(
        "record(TextChunk) [cap=1000]",
        lambda: capped.record(text),
        iters=200_000,
    )

    # Save path: one write per flush.
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "tape.jsonl"
        small = SessionTape()
        for _ in range(1_000):
            small.record(text)

        def save_once() -> None:
            small.save(target)

        bench("save(1000 events)", save_once, iters=200)


if __name__ == "__main__":
    main()
