"""Benchmark: agent builder .build() cost.

Every ``.build()`` walks the builder graph, copies the config, and
constructs a native ADK agent. This bench captures:

* Simple single-agent build cost
* Pipeline build cost (N sequential steps)
* FanOut build cost (N parallel branches)
* Nested pipeline-of-fanouts build cost

Numbers serve as a baseline for future improvements in the IR→ADK
lowering pass. The goal is to make build() cheap enough that test
suites and hot reloads rebuild agents on every assertion.
"""

from __future__ import annotations

from adk_fluent import Agent, FanOut, Pipeline
from tests.bench._common import bench, report_header


def main() -> None:
    report_header("Agent build benchmarks")

    # Single agent.
    def build_solo() -> object:
        return Agent("solo", "gemini-2.5-flash").instruct("answer").build()

    bench("build Agent[solo]", build_solo, iters=2_000)

    # Pipeline of N agents.
    for n in (2, 4, 8):

        def build_pipeline(n: int = n) -> object:
            p = Pipeline(f"p{n}")
            for i in range(n):
                p = p.step(Agent(f"s{i}", "gemini-2.5-flash").instruct(f"step {i}"))
            return p.build()

        bench(f"build Pipeline[{n}]", build_pipeline, iters=1_000)

    # FanOut of N branches.
    for n in (2, 4, 8):

        def build_fanout(n: int = n) -> object:
            f = FanOut(f"f{n}")
            for i in range(n):
                f = f.branch(Agent(f"b{i}", "gemini-2.5-flash").instruct(f"branch {i}"))
            return f.build()

        bench(f"build FanOut[{n}]", build_fanout, iters=1_000)

    # Nested pipeline of fanouts — realistic workflow shape.
    _counter = [0]

    def build_nested() -> object:
        def fan(tag: str) -> FanOut:
            return (
                FanOut(f"fan_{tag}")
                .branch(Agent(f"a_{tag}", "gemini-2.5-flash").instruct("a"))
                .branch(Agent(f"b_{tag}", "gemini-2.5-flash").instruct("b"))
            )

        _counter[0] += 1
        tag = str(_counter[0])
        return (
            Pipeline(f"root_{tag}")
            .step(Agent(f"intro_{tag}", "gemini-2.5-flash").instruct("intro"))
            .step(fan(f"{tag}a"))
            .step(fan(f"{tag}b"))
            .step(Agent(f"outro_{tag}", "gemini-2.5-flash").instruct("outro"))
            .build()
        )

    bench("build Pipeline[fan,fan] nested", build_nested, iters=500)

    # Builder with tools + callbacks + context — common real-world weight.
    def tool_fn(query: str) -> str:
        return query.upper()

    async def before_model(ctx, req) -> None:
        pass

    from adk_fluent import C, P

    def build_loaded() -> object:
        return (
            Agent("loaded", "gemini-2.5-flash")
            .instruct(P.role("assistant") | P.task("search") | P.format("json"))
            .tool(tool_fn)
            .tool(tool_fn)
            .before_model(before_model)
            .context(C.window(n=5))
            .writes("result")
            .build()
        )

    bench("build Agent[tools+cbs+ctx]", build_loaded, iters=1_000)


if __name__ == "__main__":
    main()
