# Cookbook Index

59 runnable examples demonstrating every adk-fluent feature — from single agents to production pipelines.
Each example includes native ADK code alongside the fluent equivalent so you can see exactly what the builder generates.

Run all examples as tests: `uv run pytest examples/cookbook/ -q`

______________________________________________________________________

## By Difficulty

### Crawl — Single Agent, 1-2 Features

Start here. Each example introduces one concept with a simple, self-contained agent.

| #   | Example                                    | What You'll Learn                                    |
| --- | ------------------------------------------ | ---------------------------------------------------- |
| 01  | [Simple Agent](01_simple_agent.py)         | Create a minimal agent with name, model, instruction |
| 02  | [Agent with Tools](02_agent_with_tools.py) | Attach tool functions to an agent                    |
| 03  | [Callbacks](03_callbacks.py)               | Register before/after model callbacks                |
| 08  | [One-Shot Ask](08_one_shot_ask.py)         | `.ask()` for single-turn execution                   |
| 10  | [Cloning](10_cloning.py)                   | `.clone()` and `.with_()` for agent variants         |
| 11  | [Inline Testing](11_inline_testing.py)     | `.test()` for quick smoke tests                      |
| 21  | [Typed State Keys](21_statekey.py)         | `StateKey` typed state descriptors                   |
| 22  | [Presets](22_presets.py)                   | Reusable `Preset` configuration bundles              |
| 23  | [With Variants](23_with_variants.py)       | `.with_()` for A/B prompt testing                    |
| 24  | [Agent Decorator](24_agent_decorator.py)   | `@agent` decorator for FastAPI-style definition      |
| 26  | [Serialization](26_serialization.py)       | `.to_dict()`, `.to_yaml()`, `.from_dict()`           |

### Walk — Multi-Agent or 3+ Features

Combine agents into teams, pipelines, and routed systems.

| #   | Example                                                  | What You'll Learn                              |
| --- | -------------------------------------------------------- | ---------------------------------------------- |
| 04  | [Sequential Pipeline](04_sequential_pipeline.py)         | `>>` operator for sequential agent chains      |
| 05  | [Parallel FanOut](05_parallel_fanout.py)                 | `\|` operator for parallel execution           |
| 06  | [Loop Agent](06_loop_agent.py)                           | `Loop` builder for iterative refinement        |
| 07  | [Team Coordinator](07_team_coordinator.py)               | `.sub_agent()` for LLM-driven delegation       |
| 12  | [Guardrails](12_guardrails.py)                           | `.guardrail()` for safety screening            |
| 13  | [Interactive Session](13_interactive_session.py)         | `.session()` for multi-turn chat               |
| 14  | [Dynamic Forwarding](14_dynamic_forwarding.py)           | Dynamic field-based routing                    |
| 16  | [Operator Composition](16_operator_composition.py)       | Combining `>>`, `\|`, `*` operators            |
| 17  | [Route Branching](17_route_branching.py)                 | `Route` for deterministic state-based routing  |
| 18  | [Dict Routing](18_dict_routing.py)                       | `>> {"key": agent}` shorthand                  |
| 19  | [Conditional Gating](19_conditional_gating.py)           | `.proceed_if()` for conditional execution      |
| 20  | [Loop Until](20_loop_until.py)                           | `.loop_until()` for conditional loop exit      |
| 27  | [Delegate Pattern](27_delegate_pattern.py)               | `.delegate()` for coordinator pattern          |
| 29  | [Function Steps](29_function_steps.py)                   | `>> fn` for plain function pipeline steps      |
| 30  | [Until Operator](30_until_operator.py)                   | `* until(pred)` operator for conditional loops |
| 31  | [Typed Output](31_typed_output.py)                       | `@ Schema` operator for Pydantic output        |
| 32  | [Fallback Operator](32_fallback_operator.py)             | `//` operator for graceful degradation         |
| 33  | [State Transforms](33_state_transforms.py)               | `S.pick`, `S.merge`, `S.rename`, etc.          |
| 35  | [Tap Observation](35_tap_observation.py)                 | `tap()` for side-effect monitoring             |
| 36  | [Expect Assertions](36_expect_assertions.py)             | `expect()` for data contract assertions        |
| 37  | [Mock Testing](37_mock_testing.py)                       | `mock_backend()` for deterministic tests       |
| 38  | [Retry If](38_retry_if.py)                               | `retry_if()` for transient failure handling    |
| 39  | [Map Over](39_map_over.py)                               | `map_over()` for batch processing              |
| 40  | [Timeout](40_timeout.py)                                 | `timeout()` for execution deadlines            |
| 41  | [Gate Approval](41_gate_approval.py)                     | `gate()` for human-in-the-loop approval        |
| 42  | [Race](42_race.py)                                       | `race()` for fastest-response selection        |
| 56  | [Customer Support Triage](56_customer_support_triage.py) | `S.capture`, `Route`, `gate`, `C.none()`       |

### Run — Complex Pipelines, Multiple Patterns

Production-grade architectures combining many features.

| #   | Example                                                | What You'll Learn                                        |
| --- | ------------------------------------------------------ | -------------------------------------------------------- |
| 09  | [Live Translation Pipeline](09_streaming.py)           | `.stream()` in a real pipeline                           |
| 15  | [Production Deployment](15_production_runtime.py)      | `to_app()`, middleware stack                             |
| 25  | [Introspection & Debugging](25_validate_explain.py)    | `.validate()`, `.show()`, `.show("plain")`, copy-on-write |
| 28  | [Investment Analysis](28_real_world_pipeline.py)       | Route, Preset, loop_until, proceed_if                    |
| 34  | [Code Review Pipeline](34_full_algebra.py)             | `>>`, `\|`, `@`, `//` in a real workflow                 |
| 43  | [Primitives Showcase](43_primitives_showcase.py)       | All primitives in e-commerce order system                |
| 44  | [Pipeline Optimization with IR](44_ir_and_backends.py) | `to_ir()`, `to_app()`, `to_mermaid()`                    |
| 45  | [Middleware](45_middleware.py)                         | `RetryMiddleware`, `StructuredLogMiddleware`             |
| 46  | [Contracts & Testing](46_contracts_and_testing.py)     | `.produces()`, `.consumes()`, `check_contracts()`        |
| 47  | [Dependency Injection](47_dependency_injection.py)     | `.inject()`, `inject_resources()`                        |
| 48  | [Architecture Documentation](48_visualization.py)      | `to_mermaid()`, `.show()`, diagrams                   |
| 49  | [Context Engineering](49_context_engineering.py)       | `C.none()`, `C.from_state()`, `C.window()`               |
| 50  | [Capture & Route](50_capture_and_route.py)             | `S.capture` + `Route` pattern                            |
| 51  | [Visibility Policies](51_visibility_policies.py)       | `.reveal()`, `.hide()`, visibility inference             |
| 52  | [Contract Checking](52_contract_checking.py)           | Cross-channel data flow verification                     |
| 53  | [Structured Schemas](53_structured_schemas.py)         | Pydantic schemas in multi-agent pipelines                |
| 54  | [Transfer Control](54_transfer_control.py)             | `.stay()`, `.no_peers()`, `.isolate()`                   |
| 55  | [Deep Research Agent](55_deep_research.py)             | Full pipeline: FanOut + Loop + typed output              |
| 57  | [Code Review Agent](57_code_review_agent.py)           | FanOut + typed output + conditional gating               |
| 58  | [Multi-Tool Task Agent](58_multi_tool_agent.py)        | Tools + guardrails + DI + context                        |
| 67  | [G Module Guards](67_g_module_guards.py)               | `G.json()`, `G.pii()`, `G.budget()`, `\|` composition   |
| 77  | [Skill-Based Agents](77_skill_based_agents.py)         | `Skill()`, `SkillRegistry`, `T.skill()`, YAML topology   |

______________________________________________________________________

## By Feature Group

### Core — Agent, Model, Instruction

| #   | Example          | Key Methods                              |
| --- | ---------------- | ---------------------------------------- |
| 01  | Simple Agent     | `.model()`, `.instruct()`, `.describe()` |
| 02  | Agent with Tools | `.tool()`, `.tools()`                    |
| 03  | Callbacks        | `.before_model()`, `.after_model()`      |
| 08  | One-Shot Ask     | `.ask()`                                 |

### Composition Operators — >>, |, \*, @, //

| #   | Example              | Operators             |
| --- | -------------------- | --------------------- |
| 04  | Sequential Pipeline  | `>>`                  |
| 05  | Parallel FanOut      | `\|`                  |
| 06  | Loop Agent           | `Loop` builder        |
| 16  | Operator Composition | `>>`, `\|`, `*`       |
| 30  | Until Operator       | `* until()`           |
| 31  | Typed Output         | `@ Schema`            |
| 32  | Fallback Operator    | `//`                  |
| 34  | Code Review Pipeline | `>>`, `\|`, `@`, `//` |

### State & Routing

| #   | Example            | Key Methods                           |
| --- | ------------------ | ------------------------------------- |
| 17  | Route Branching    | `Route().eq().otherwise()`            |
| 18  | Dict Routing       | `>> {"key": agent}`                   |
| 19  | Conditional Gating | `.proceed_if()`                       |
| 20  | Loop Until         | `.loop_until()`                       |
| 21  | Typed State Keys   | `StateKey`                            |
| 29  | Function Steps     | `>> fn`                               |
| 33  | State Transforms   | `S.pick`, `S.merge`, `S.rename`, etc. |
| 50  | Capture & Route    | `S.capture` + `Route`                 |

### Context Engineering

| #   | Example             | Key Methods                                                 |
| --- | ------------------- | ----------------------------------------------------------- |
| 49  | Context Engineering | `C.none()`, `C.from_state()`, `C.window()`, `C.user_only()` |
| 51  | Visibility Policies | `.reveal()`, `.hide()`                                      |
| 54  | Transfer Control    | `.stay()`, `.no_peers()`, `.isolate()`                      |

### Callbacks & Guardrails

| #   | Example           | Key Methods                         |
| --- | ----------------- | ----------------------------------- |
| 03  | Callbacks         | `.before_model()`, `.after_model()`                   |
| 12  | Guardrails        | `.guard()` with callables and G composites            |
| 35  | Tap Observation   | `tap()`                                               |
| 36  | Expect Assertions | `expect()`                                            |
| 67  | G Module Guards   | `G.json()`, `G.pii()`, `G.budget()`, `\|` composition |

### Testing & Contracts

| #   | Example             | Key Methods                                       |
| --- | ------------------- | ------------------------------------------------- |
| 11  | Inline Testing      | `.test()`                                         |
| 37  | Mock Testing        | `mock_backend()`                                  |
| 46  | Contracts & Testing | `.produces()`, `.consumes()`, `check_contracts()` |
| 52  | Contract Checking   | Cross-channel verification                        |

### Production — IR, Backends, Middleware

| #   | Example               | Key Methods                                  |
| --- | --------------------- | -------------------------------------------- |
| 15  | Production Deployment | `to_app()`, middleware                       |
| 44  | Pipeline Optimization | `to_ir()`, `to_app()`, `to_mermaid()`        |
| 45  | Middleware            | `RetryMiddleware`, `StructuredLogMiddleware` |
| 47  | Dependency Injection  | `.inject()`, `inject_resources()`            |

### Visualization & Introspection

| #   | Example                    | Key Methods                               |
| --- | -------------------------- | ----------------------------------------- |
| 25  | Introspection & Debugging  | `.validate()`, `.show()`, `.show("plain")` |
| 48  | Architecture Documentation | `to_mermaid()`, `.show()`              |

### Primitives — tap, expect, gate, race, etc.

| #   | Example             | Primitive               |
| --- | ------------------- | ----------------------- |
| 35  | Tap Observation     | `tap()`                 |
| 36  | Expect Assertions   | `expect()`              |
| 38  | Retry If            | `retry_if()`            |
| 39  | Map Over            | `map_over()`            |
| 40  | Timeout             | `timeout()`             |
| 41  | Gate Approval       | `gate()`                |
| 42  | Race                | `race()`                |
| 43  | Primitives Showcase | All primitives combined |

### Advanced Patterns

| #   | Example             | Pattern                       |
| --- | ------------------- | ----------------------------- |
| 07  | Team Coordinator    | LLM-driven delegation         |
| 13  | Interactive Session | Multi-turn `.session()`       |
| 14  | Dynamic Forwarding  | Field-based routing           |
| 22  | Presets             | `Preset` bundles              |
| 23  | With Variants       | `.with_()` immutable variants |
| 24  | Agent Decorator     | `@agent` decorator            |
| 26  | Serialization       | `.to_dict()`, `.to_yaml()`    |
| 27  | Delegate Pattern    | `.delegate()`                 |
| 53  | Structured Schemas  | Pydantic in multi-agent       |

### Skills — Composable Agent Packages

| #   | Example              | Key Methods                                          |
| --- | -------------------- | ---------------------------------------------------- |
| 77  | Skill-Based Agents   | `Skill()`, `.inject()`, `.configure()`, `SkillRegistry` |

### Capstones — Real-World Systems

| #   | Example                      | Inspired By                      |
| --- | ---------------------------- | -------------------------------- |
| 28  | Investment Analysis Pipeline | Financial services               |
| 55  | Deep Research Agent          | Gemini Deep Research, Perplexity |
| 56  | Customer Support Triage      | ADK-samples, real call centers   |
| 57  | Code Review Agent            | Gemini CLI, GitHub Copilot       |
| 58  | Multi-Tool Task Agent        | Manus AI, OpenAI Agents SDK      |

______________________________________________________________________

## By Architecture Pattern

### Single Agent

01, 02, 03, 08, 10, 11, 12, 21, 22, 23, 24, 26

### Sequential Pipeline

04, 09, 15, 28, 29, 34, 44, 55, 57

### Parallel FanOut

05, 39, 42

### Loop / Iteration

06, 20, 30, 38

### Coordinator / Delegation

07, 14, 27, 56

### Router / Branching

17, 18, 19, 50

### Multi-Pattern Composition

28, 43, 49, 55, 57, 58, 77

______________________________________________________________________

## Suggested Learning Path

**Week 1 — Foundations:**
01 → 02 → 03 → 08 → 10

**Week 2 — Composition:**
04 → 05 → 06 → 16 → 07

**Week 3 — Control Flow:**
17 → 19 → 20 → 29 → 30 → 31 → 32 → 33

**Week 4 — Primitives:**
35 → 36 → 38 → 39 → 40 → 41 → 42 → 43

**Week 5 — Production:**
12 → 45 → 46 → 47 → 44 → 15

**Week 6 — Context & Transfer:**
49 → 50 → 51 → 53 → 54

**Week 7 — Capstones:**
28 → 34 → 55 → 56 → 57 → 58

**Week 8 — Skills:**
77 (Skill-Based Agents — YAML topologies, registry, composition)
