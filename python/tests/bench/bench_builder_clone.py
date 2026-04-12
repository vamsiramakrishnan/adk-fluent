"""Benchmark: BuilderBase deep copy.

Wave 1 replaced three independent ``copy.deepcopy`` calls inside
``deep_clone_builder`` with a single ``__deepcopy__`` that walks
``_config``, ``_callbacks`` and ``_lists`` under one shared memo. This
bench measures a representative agent graph clone.
"""

from __future__ import annotations

import copy

from adk_fluent import Agent, FanOut, Pipeline

from tests.bench._common import bench, report_header


def _build_graph() -> Pipeline:
    leaf_a = Agent("a", "gemini-2.5-flash").instruct("step a")
    leaf_b = Agent("b", "gemini-2.5-flash").instruct("step b")
    leaf_c = Agent("c", "gemini-2.5-flash").instruct("step c")
    fan = FanOut("fan").branch(leaf_b).branch(leaf_c)
    return Pipeline("pipe").step(leaf_a).step(fan)


def main() -> None:
    report_header("Builder deepcopy benchmarks")

    graph = _build_graph()

    bench(
        "deepcopy(pipeline w/ fanout)",
        lambda: copy.deepcopy(graph),
        iters=2_000,
    )

    simple = Agent("solo", "gemini-2.5-flash").instruct("a").tool(lambda: None)
    bench(
        "deepcopy(Agent w/ 1 tool)",
        lambda: copy.deepcopy(simple),
        iters=5_000,
    )


if __name__ == "__main__":
    main()
