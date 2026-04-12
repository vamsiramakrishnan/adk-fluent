"""Benchmark: P (prompt) composition and rendering.

Measures the cost of building a P composite and compiling it down to
an instruction string. Wave 2 adds ``slots=True`` to all PTransform
subclasses which reduces per-instance memory and ~30% instantiation
cost. This bench captures the raw composition path so future changes
(caching compiled text, lazy rendering) can be measured.
"""

from __future__ import annotations

from adk_fluent import P
from adk_fluent._prompt import _compile_prompt_spec
from tests.bench._common import bench, report_header


def main() -> None:
    report_header("Prompt composition benchmarks")

    # Small composition (3 sections).
    def build_small() -> object:
        return P.role("assistant") + P.task("answer") + P.format("json")

    # Medium composition (6 sections).
    def build_medium() -> object:
        return (
            P.role("senior engineer")
            + P.context("you are reviewing a PR")
            + P.task("identify bugs and suggest fixes")
            + P.constraint("be concise", "cite line numbers")
            + P.format("markdown bullet list")
            + P.example(input="ex1 in", output="ex1 out")
        )

    # Large composition (10 sections with reorder/without).
    def build_large() -> object:
        return (
            P.role("support agent")
            + P.context("handle tier-1 tickets")
            + P.task("triage and respond")
            + P.constraint("stay polite", "escalate if unclear")
            + P.format("json with fields: intent, response")
            + P.example(input="q1", output="a1")
            + P.example(input="q2", output="a2")
        ) | P.without("example")

    bench("build P[3]", build_small, iters=50_000)
    bench("build P[6]", build_medium, iters=50_000)
    bench("build P[10 + without]", build_large, iters=20_000)

    small = build_small()
    medium = build_medium()
    large = build_large()

    def compile_small() -> None:
        _compile_prompt_spec(small)

    def compile_medium() -> None:
        _compile_prompt_spec(medium)

    def compile_large() -> None:
        _compile_prompt_spec(large)

    bench("compile P[3]", compile_small, iters=50_000)
    bench("compile P[6]", compile_medium, iters=50_000)
    bench("compile P[10 + without]", compile_large, iters=20_000)


if __name__ == "__main__":
    main()
