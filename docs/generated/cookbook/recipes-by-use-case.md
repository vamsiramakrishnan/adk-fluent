# Recipes by Use Case

Can't find the right cookbook example? This page organizes all 58 recipes
by real-world use case so you can jump straight to the pattern you need.

## Customer Support & Triage

Build agents that classify tickets, route conversations, and escalate issues.

| Recipe                          | Key features                           | Cookbook                             |
| ------------------------------- | -------------------------------------- | ------------------------------------ |
| Email Classifier Agent          | Simple agent creation                  | [#01](01_simple_agent.md)            |
| Customer Support Chat Session   | Interactive `.session()` API           | [#13](13_interactive_session.md)     |
| Multi-Department Ticket Routing | Dynamic field forwarding               | [#14](14_dynamic_forwarding.md)      |
| Customer Support Triage         | `S.capture`, `C.none`, `Route`, `gate` | [#56](56_customer_support_triage.md) |
| Customer Service Hub            | Transfer control, `.isolate()`         | [#54](54_transfer_control.md)        |
| IT Helpdesk Triage              | Capture and route pattern              | [#50](50_capture_and_route.md)       |

## Data Processing & ETL

Transform, validate, and pipeline structured data through multi-step workflows.

| Recipe                             | Key features                       | Cookbook                         |
| ---------------------------------- | ---------------------------------- | -------------------------------- |
| Document Processing Pipeline       | Sequential pipeline                | [#04](04_sequential_pipeline.md) |
| ETL Pipeline with Function Steps   | `>> fn` plain function composition | [#29](29_function_steps.md)      |
| Research Data Pipeline             | `S.*` state transforms             | [#33](33_state_transforms.md)    |
| Analytics Data Quality             | `expect()` state assertions        | [#36](36_expect_assertions.md)   |
| Batch Processing Customer Feedback | `map_over` iteration               | [#39](39_map_over.md)            |
| Insurance Claim Processing         | Structured schemas, `@` operator   | [#53](53_structured_schemas.md)  |

## Search & Research

Build research agents, deep search pipelines, and knowledge retrieval systems.

| Recipe                            | Key features                         | Cookbook                          |
| --------------------------------- | ------------------------------------ | --------------------------------- |
| Market Research Fan-Out           | Parallel `FanOut`                    | [#05](05_parallel_fanout.md)      |
| News Analysis Pipeline            | Operator composition `>>`, `\|`, `*` | [#16](16_operator_composition.md) |
| Investment Analysis Pipeline      | Full expression language             | [#28](28_real_world_pipeline.md)  |
| Knowledge Retrieval with Fallback | `//` fallback operator               | [#32](32_fallback_operator.md)    |
| Fastest-Response Search (Race)    | `race` across providers              | [#42](42_race.md)                 |
| Deep Research Agent               | `>>`, `\|`, `*`, `@`, `S.*`, `C.*`   | [#55](55_deep_research.md)        |

## Content Generation & Review

Generate, refine, and review text content with iterative quality loops.

| Recipe                      | Key features                         | Cookbook                         |
| --------------------------- | ------------------------------------ | -------------------------------- |
| Essay Refinement Loop       | `Loop` agent with iterations         | [#06](06_loop_agent.md)          |
| Resume Refinement with Exit | `loop_until` conditional exit        | [#20](20_loop_until.md)          |
| Customer Onboarding Loop    | `* until(pred)` operator             | [#30](30_until_operator.md)      |
| A/B Prompt Testing          | `.with_()` for variants              | [#23](23_with_variants.md)       |
| Code Review Pipeline        | Full expression algebra              | [#34](34_full_algebra.md)        |
| Code Review Agent           | `>>`, `\|`, `@`, `proceed_if`, `tap` | [#57](57_code_review_agent.md)   |
| Content Review Pipeline     | Visibility policies                  | [#51](51_visibility_policies.md) |

## E-Commerce & Finance

Order routing, fraud detection, invoice parsing, and financial analysis.

| Recipe                           | Key features                    | Cookbook                         |
| -------------------------------- | ------------------------------- | -------------------------------- |
| E-Commerce Order Routing         | `Route` deterministic branching | [#17](17_route_branching.md)     |
| Fraud Detection Pipeline         | `proceed_if` conditional gating | [#19](19_conditional_gating.md)  |
| Order Processing with State Keys | `StateKey` typed descriptors    | [#21](21_statekey.md)            |
| Structured Invoice Parsing       | `@` typed output operator       | [#31](31_typed_output.md)        |
| E-Commerce Primitives Showcase   | All primitives combined         | [#43](43_primitives_showcase.md) |

## Team Coordination & Delegation

Multi-agent systems with coordinators, specialists, and routing.

| Recipe                     | Key features                           | Cookbook                      |
| -------------------------- | -------------------------------------- | ----------------------------- |
| Product Launch Coordinator | Team coordinator pattern               | [#07](07_team_coordinator.md) |
| Senior Architect Delegates | LLM-driven routing, `.delegate()`      | [#27](27_delegate_pattern.md) |
| Multi-Language Routing     | Dict `>>` shorthand                    | [#18](18_dict_routing.md)     |
| Multi-Tool Task Agent      | `.tool()`, `.guardrail()`, `.inject()` | [#58](58_multi_tool_agent.md) |

## Safety, Guardrails & Compliance

Content moderation, medical safety, legal approval gates, and contracts.

| Recipe                           | Key features                                   | Cookbook                           |
| -------------------------------- | ---------------------------------------------- | ---------------------------------- |
| Content Moderation with Logging  | `before_model`, `after_model` callbacks        | [#03](03_callbacks.md)             |
| Medical Advice Safety Guardrails | `.guardrail()` method                          | [#12](12_guardrails.md)            |
| Legal Document Review            | `gate` with human approval                     | [#41](41_gate_approval.md)         |
| Medical Imaging Contracts        | `.produces()`, `.consumes()`, strict contracts | [#46](46_contracts_and_testing.md) |
| Contract Checking                | Catch data flow bugs early                     | [#52](52_contract_checking.md)     |
| Enterprise Compliance Preset     | `Preset` for shared config                     | [#22](22_presets.md)               |

## Production & Deployment

Deploying, testing, serializing, and monitoring agents in production.

| Recipe                      | Key features                          | Cookbook                          |
| --------------------------- | ------------------------------------- | --------------------------------- |
| Production Deployment       | `to_app()` with middleware            | [#15](15_production_runtime.md)   |
| Deployment Serialization    | `to_dict`, `to_yaml`, `from_dict`     | [#26](26_serialization.md)        |
| Mock Testing Pipeline       | `mock_backend()`, deterministic tests | [#37](37_mock_testing.md)         |
| Dependency Injection        | Dev/staging/prod environments         | [#47](47_dependency_injection.md) |
| ML Inference Monitoring     | `tap` for pure observation            | [#35](35_tap_observation.md)      |
| Middleware Stack            | Production middleware for healthcare  | [#45](45_middleware.md)           |
| Retry on Transient Failures | `retry_if` pattern                    | [#38](38_retry_if.md)             |
| Timeout for Trading Agent   | `timeout` execution deadline          | [#40](40_timeout.md)              |

## Developer Experience & Tooling

Introspection, visualization, debugging, and IDE workflow.

| Recipe                        | Key features                              | Cookbook                         |
| ----------------------------- | ----------------------------------------- | -------------------------------- |
| Travel Planner with Tools     | Attaching function tools                  | [#02](02_agent_with_tools.md)    |
| Quick Code Review with .ask() | One-shot execution                        | [#08](08_one_shot_ask.md)        |
| Live Translation Streaming    | `.stream()` token-by-token                | [#09](09_streaming.md)           |
| A/B Testing Agent Variants    | `.clone()` for independent copies         | [#10](10_cloning.md)             |
| Smoke-Testing with .test()    | Inline testing                            | [#11](11_inline_testing.md)      |
| Validate & Explain            | `.validate()`, `.explain()`, `.inspect()` | [#25](25_validate_explain.md)    |
| Domain Expert via @agent      | `@agent` decorator                        | [#24](24_agent_decorator.md)     |
| Architecture Diagrams         | `.to_mermaid()` visualization             | [#48](48_visualization.md)       |
| IR and Backends               | Inspecting and compiling agent graphs     | [#44](44_ir_and_backends.md)     |
| Context Engineering           | `C.*` context transforms                  | [#49](49_context_engineering.md) |
