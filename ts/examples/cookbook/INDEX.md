# Cookbook Index (TypeScript)

75 runnable examples demonstrating the adk-fluent TypeScript surface — from a single-line `Agent` to a full coding-agent harness, with A2UI, middleware, guards, and topology visualization.

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
| 27  | [Dict Routing](27_dict_routing.ts)                     | Route with dict-based matching                             |
| 28  | [Function Steps](28_function_steps.ts)                 | Plain functions as pipeline steps (zero LLM cost)          |
| 29  | [Until Operator](29_until_operator.ts)                 | `.timesUntil(pred, {max})` conditional loops               |
| 30  | [Structured Schemas](30_structured_schemas.ts)         | Schema-driven validation and typing                        |
| 31  | [Transfer Control](31_transfer_control.ts)             | `.subAgent()`, `.isolate()`, `.stay()`, `.noPeers()`       |
| 32  | [Capture and Route](32_capture_and_route.ts)           | `S.capture` → `Route` for input-driven dispatch            |
| 33  | [Dispatch and Join](33_dispatch_join.ts)               | `dispatch()` / `join()` for background tasks               |
| 34  | [M Module Composition](34_m_module_composition.ts)     | `M.*` middleware factories and `.pipe()` composition        |
| 35  | [T Module Tools](35_t_module_tools.ts)                 | `T.fn()`, `T.agent()`, `T.mock()` tool composition         |
| 36  | [Tap Observation](36_tap_observation.ts)               | `tap()` for side-effect observation without mutation        |
| 37  | [Expect Assertions](37_expect_assertions.ts)           | `expect()` for state invariant checking                    |
| 38  | [Gate Approval](38_gate_approval.ts)                   | `gate()` for conditional execution                         |
| 39  | [Race Primitive](39_race_primitive.ts)                 | `race()` — first-to-complete wins                          |
| 40  | [Map Over](40_map_over.ts)                             | `mapOver()` — apply agent to list items                    |
| 41  | [G Module Guards](41_g_module_guards.ts)               | `G.length`, `G.regex`, `G.schema` guard composition        |
| 42  | [Deep Research](42_deep_research.ts)                   | Full deep-research pipeline with tools                     |
| 43  | [Code Review Agent](43_code_review_agent.ts)           | Multi-agent code review with routing                       |
| 44  | [Multi-Tool Agent](44_multi_tool_agent.ts)             | Agent with multiple domain tools                           |
| 45  | [Customer Support Triage](45_customer_support_triage.ts) | `S.capture`, `Route`, `gate` for support routing         |
| 46  | [Visualization Diagram](46_visualization_diagram.ts)   | Mermaid diagram generation from topologies                 |
| 47  | [Full Algebra](47_full_algebra.ts)                     | All operators combined in one example                      |
| 48  | [Visibility](48_visibility.ts)                         | `.show()`, `.hide()`, `.transparent()`, `.filtered()`      |
| 49  | [Native Hook](49_native_hook.ts)                       | `.native(fn)` escape hatch for raw ADK access              |
| 50  | [Introspection](50_introspection.ts)                   | `.inspect()`, `.dataFlow()`, `.llmAnatomy()`               |
| 51  | [Describe Metadata](51_describe_metadata.ts)           | `.describe()` for transfer routing metadata                |
| 52  | [Skills](52_skills.ts)                                 | Skill-based agent composition                              |
| 53  | [Planner Executor](53_planner_executor.ts)             | Plan-then-execute patterns                                 |
| 54  | [Memory](54_memory.ts)                                 | `.memory()` and `.memoryAutoSave()`                        |
| 55  | [Nested Pipelines](55_nested_pipelines.ts)             | Pipelines within pipelines                                 |

### A2A — Agent-to-Agent remote communication

| #   | Example                                                    | What you'll learn                                  |
| --- | ---------------------------------------------------------- | -------------------------------------------------- |
| 56  | [A2A Remote Basics](56_a2a_remote_basics.ts)               | `RemoteAgent` for cross-service agent calls        |
| 57  | [A2A Server Publish](57_a2a_server_publish.ts)             | `A2AServer` to publish agents via A2A protocol     |
| 63  | [A2A Registry Discovery](63_a2a_registry_discovery.ts)     | `AgentRegistry` for service discovery              |

### A2UI — Agent-to-UI composition

| #   | Example                                                    | What you'll learn                                          |
| --- | ---------------------------------------------------------- | ---------------------------------------------------------- |
| 58  | [UI Basics](58_ui_basics.ts)                               | `UI.text`, `UI.button`, `UI.textField`, data binding       |
| 59  | [UI Form Dashboard](59_ui_form_dashboard.ts)               | `UI.form()`, `UI.dashboard()` presets                      |
| 68  | [A2UI Basics](68_a2ui_basics.ts)                           | All component factories, presets, validation checks        |
| 69  | [A2UI Agent Integration](69_a2ui_agent_integration.ts)     | `Agent.ui()`, `T.a2ui()`, `G.a2ui()`, `S.toUi()`          |
| 70  | [A2UI Operators](70_a2ui_operators.ts)                     | Row/column chaining, nested layout composition             |
| 71  | [A2UI LLM-Guided](71_a2ui_llm_guided.ts)                  | `UI.auto()`, `P.uiSchema()`, dynamic UI generation        |
| 72  | [A2UI Pipeline](72_a2ui_pipeline.ts)                       | Surfaces in multi-step pipelines, state-UI bridging        |
| 73  | [A2UI Dynamic](73_a2ui_dynamic.ts)                         | `UI.auto()` with domain tools, LLM-decided UI             |

### Advanced patterns and composition

| #   | Example                                                            | What you'll learn                                  |
| --- | ------------------------------------------------------------------ | -------------------------------------------------- |
| 60  | [Patterns: Chain/Conditional/Supervised](60_patterns_chain_conditional_supervised.ts) | `chain()`, `conditional()`, `supervised()`  |
| 61  | [Patterns: Fan-Out Merge](61_patterns_fan_out_merge.ts)            | `fanOutMerge()` with merge strategies              |
| 62  | [Route Advanced](62_route_advanced.ts)                             | Complex routing with predicates and chains         |
| 64  | [Middleware Schema](64_middleware_schema.ts)                        | Schema-driven middleware with `Reads`/`Writes`     |
| 65  | [Builtin Middleware](65_builtin_middleware.ts)                      | All `M.*` factories: retry, log, cost, circuit breaker |
| 66  | [T Module Tools](66_t_module_tools.ts)                             | Full `T.*` composition: fn, agent, mock, mcp, openapi |
| 67  | [G Module Guards](67_g_module_guards.ts)                           | Full `G.*` guards: pii, toxicity, budget, grounded |
| 74  | [Harness and Skills](74_harness_and_skills.ts)                     | `H.hooks()`, permissions, plan mode, session, budget |
| 75  | [Coding Agent Harness](75_coding_agent_harness.ts)                 | Full `H.codingAgent()` — 5-layer harness assembly  |

---

## By Feature

| Feature                   | Examples                        |
| ------------------------- | ------------------------------- |
| Single agent              | 01, 02, 03, 11, 14, 49, 50, 51 |
| Pipelines / `Pipeline`    | 04, 08, 28, 55                  |
| Parallel / `FanOut`       | 05, 08, 25, 61                  |
| Loops / `Loop`            | 06, 08, 18, 25, 29             |
| Sub-agent transfer        | 07, 31                          |
| Agent-as-tool             | 21                              |
| Operators (chained)       | 08, 10, 47                      |
| Routing / `Route`         | 09, 25, 27, 32, 62             |
| Fallback / `Fallback`     | 10, 20                          |
| Guards / `G`              | 12, 25, 41, 67                  |
| State transforms / `S`    | 13, 32                          |
| Prompt composition / `P`  | 14                              |
| Context engineering / `C` | 15                              |
| Middleware / `M`          | 16, 34, 64, 65                  |
| Primitives                | 17, 33, 36, 37, 38, 39, 40     |
| Review loop               | 18, 25                          |
| Map-reduce                | 19                              |
| Cascade                   | 20                              |
| Artifacts / `A`           | 22                              |
| Coding harness / `H`      | 23, 74, 75                      |
| Evaluation / `E`          | 24                              |
| Visualization             | 26, 46                          |
| Tools / `T`               | 35, 66                          |
| Schemas                   | 30, 64                          |
| A2A                       | 56, 57, 63                      |
| A2UI / `UI`               | 58, 59, 68, 69, 70, 71, 72, 73 |
| Memory                    | 54                              |
| Skills                    | 52                              |
| Visibility                | 48                              |

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
