# Cookbook Index (TypeScript)

26 runnable examples demonstrating the adk-fluent TypeScript surface — from a single-line `Agent` to a full deep-research capstone, plus topology visualization.

Each cookbook is self-contained and exercises a specific slice of the API. The examples assert their own invariants at top level, so importing the file is enough to run the smoke test.

Run all cookbooks as part of the test suite:

```sh
cd ts
npm test                                # all tests
npm test -- tests/manual/cookbook.test.ts   # cookbooks only
```

The runner is at [`ts/tests/manual/cookbook.test.ts`](../../tests/manual/cookbook.test.ts) — it dynamically imports every numbered file in this directory.

---

## By Difficulty

### Crawl — One agent, one feature

Start here. Each example introduces one concept with a self-contained agent.

| #   | Example                                        | What you'll learn                                |
| --- | ---------------------------------------------- | ------------------------------------------------ |
| 01  | [Simple Agent](01_simple_agent.ts)             | Build a minimal agent: name, model, instruction  |
| 02  | [Agent with Tools](02_agent_with_tools.ts)     | Attach tool functions via `.tool()` and `T.fn()` |
| 03  | [Callbacks](03_callbacks.ts)                   | `.beforeModel()` / `.afterModel()` hooks         |
| 11  | [Typed Output](11_typed_output.ts)             | `.outputAs(Schema)` for structured JSON          |
| 14  | [Prompt Composition](14_prompt_composition.ts) | `P.role().add(P.task()).add(P.constraint())`     |

### Walk — Multiple agents, real composition

Combine agents into pipelines, fan-outs, loops, and routed systems.

| #   | Example                                            | What you'll learn                                          |
| --- | -------------------------------------------------- | ---------------------------------------------------------- |
| 04  | [Sequential Pipeline](04_sequential_pipeline.ts)   | `Pipeline.step(...)` for sequential chains                 |
| 05  | [Parallel FanOut](05_parallel_fanout.ts)           | `FanOut.branch(...)` and `.parallel()` operator            |
| 06  | [Loop Agent](06_loop_agent.ts)                     | `Loop.step().maxIterations().until()`                      |
| 07  | [Team Coordinator](07_team_coordinator.ts)         | `.subAgent()` + `.isolate()` for LLM-driven delegation     |
| 08  | [Operator Composition](08_operator_composition.ts) | `.then()` / `.parallel()` / `.times()` chaining            |
| 09  | [Route Branching](09_route_branching.ts)           | `Route.eq().contains().otherwise()`                        |
| 10  | [Fallback Operator](10_fallback_operator.ts)       | `.fallback()` and `Fallback.attempt()`                     |
| 12  | [Guards](12_guards.ts)                             | `G.length` and `G.regex` with `.pipe()` composition        |
| 13  | [State Transforms](13_state_transforms.ts)         | `S.pick`, `S.drop`, `S.rename`, `S.transform`, `S.compute` |
| 15  | [Context Engineering](15_context_engineering.ts)   | `C.none`, `C.window`, `C.fromState`                        |
| 16  | [Middleware-style telemetry](16_middleware.ts)     | `.beforeModel`/`.afterModel` for latency tracking          |
| 17  | [Primitives](17_primitives.ts)                     | `tap`, `expect`, `gate`, `race`, `mapOver`                 |
| 21  | [Agent-as-Tool](21_agent_tool_pattern.ts)          | `.agentTool()` vs `.subAgent()`                            |
| 22  | [Artifacts](22_artifacts.ts)                       | `A.publish` / `A.snapshot` for state ↔ artifact bridges    |

### Run — Higher-order patterns and the harness

Reusable patterns and the coding-agent harness.

| #   | Example                                                | What you'll learn                                          |
| --- | ------------------------------------------------------ | ---------------------------------------------------------- |
| 18  | [Review Loop Pattern](18_review_loop_pattern.ts)       | `reviewLoop(worker, reviewer, …)`                          |
| 19  | [Map-Reduce](19_map_reduce.ts)                         | `mapReduce(mapper, reducer, …)`                            |
| 20  | [Cascade Fallback](20_cascade_fallback.ts)             | `cascade(tier1, tier2, tier3)`                             |
| 23  | [Coding Harness](23_coding_harness.ts)                 | `H.codingAgent(workspace)` — full Claude-Code-style bundle |
| 24  | [Evaluation](24_evaluation.ts)                         | `E.suite`, `E.compare`, criteria composition               |
| 25  | [Deep Research Capstone](25_deep_research_capstone.ts) | FanOut → review loop → Route → guards, end-to-end          |
| 26  | [Visualize Topologies](26_visualize.ts)                | `.visualize()` → ascii / mermaid / markdown / json         |

---

## By Feature

| Feature                   | Examples           |
| ------------------------- | ------------------ |
| Single agent              | 01, 02, 03, 11, 14 |
| Pipelines / `Pipeline`    | 04, 08             |
| Parallel / `FanOut`       | 05, 08, 25         |
| Loops / `Loop`            | 06, 08, 18, 25     |
| Sub-agent transfer        | 07                 |
| Agent-as-tool             | 21                 |
| Operators (chained)       | 08, 10             |
| Routing / `Route`         | 09, 25             |
| Fallback / `Fallback`     | 10, 20             |
| Guards / `G`              | 12, 25             |
| State transforms / `S`    | 13                 |
| Prompt composition / `P`  | 14                 |
| Context engineering / `C` | 15                 |
| Telemetry callbacks       | 16                 |
| Primitives                | 17                 |
| Review loop               | 18, 25             |
| Map-reduce                | 19                 |
| Cascade                   | 20                 |
| Artifacts / `A`           | 22                 |
| Coding harness / `H`      | 23                 |
| Evaluation / `E`          | 24                 |
| Visualization             | 26                 |

---

## TypeScript ↔ Python operator map

JavaScript has no operator overloading — every Python operator becomes a method call. Cookbook examples use the TS form throughout.

| Python      | TypeScript                       | Returns    |
| ----------- | -------------------------------- | ---------- |
| `a >> b`    | `a.then(b)`                      | `Pipeline` |
| `a \| b`    | `a.parallel(b)`                  | `FanOut`   |
| `a * 3`     | `a.times(3)`                     | `Loop`     |
| `a * until` | `a.timesUntil(pred, { max: 5 })` | `Loop`     |
| `a // b`    | `a.fallback(b)`                  | `Fallback` |
| `a @ S`     | `a.outputAs(S)`                  | `Agent`    |

Sub-builders passed to workflow builders are auto-built — never call `.build()` on individual steps.
