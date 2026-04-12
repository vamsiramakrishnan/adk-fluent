"""Benchmark: eval-gate hot path.

Wave 1 collapsed ``_resolve_gate_text`` from a three-pass scan into a
single reversed iteration over the state dict, and avoided materializing
``reversed(list(state))``. This bench captures that path so future
changes are measurable.
"""

from __future__ import annotations

from adk_fluent._eval import _resolve_gate_text
from tests.bench._common import bench, report_header


def main() -> None:
    report_header("Eval gate benchmarks")

    # State with the key up front — best case.
    short_state = {"_last_output": "the final answer"}

    # State with the answer at the end of 16 keys.
    medium_state = {f"k{i}": f"v{i}" for i in range(16)}
    medium_state["answer"] = "this is the real answer"

    # State with lots of internal keys and the answer buried.
    long_state: dict[str, object] = {}
    for i in range(64):
        long_state[f"_internal_{i}"] = i
    for i in range(32):
        long_state[f"temp:{i}"] = i
    long_state["conclusion"] = "wave-2 is live"

    def hit_fast_path() -> None:
        _resolve_gate_text(short_state, None)

    def hit_scan_medium() -> None:
        _resolve_gate_text(medium_state, None)

    def hit_scan_long() -> None:
        _resolve_gate_text(long_state, None)

    def hit_explicit_key() -> None:
        _resolve_gate_text(medium_state, "answer")

    bench("fast path (_last_output)", hit_fast_path, iters=500_000)
    bench("explicit output_key", hit_explicit_key, iters=500_000)
    bench("scan 16-key state", hit_scan_medium, iters=200_000)
    bench("scan 96-key state (skips)", hit_scan_long, iters=100_000)


if __name__ == "__main__":
    main()
