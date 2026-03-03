# Recipes by Use Case

Can't find the right cookbook example? This page organizes all 58 recipes
by real-world use case so you can jump straight to the pattern you need.

## Quick find by primitive

Jump to recipes that demonstrate a specific adk-fluent primitive.

| Primitive          | What it does                 | Recipes                                                                                                                                                                                                                   |
| ------------------ | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `>>` (chain)       | Sequential composition       | [#04](04_sequential_pipeline.md), [#16](16_operator_composition.md), [#28](28_real_world_pipeline.md), [#29](29_function_steps.md), [#34](34_full_algebra.md), [#55](55_deep_research.md), [#57](57_code_review_agent.md) |
| `\|` (parallel)    | Concurrent branches          | [#05](05_parallel_fanout.md), [#16](16_operator_composition.md), [#28](28_real_world_pipeline.md), [#34](34_full_algebra.md), [#55](55_deep_research.md), [#57](57_code_review_agent.md)                                  |
| `*` (repeat)       | Loop N times                 | [#06](06_loop_agent.md), [#16](16_operator_composition.md), [#30](30_until_operator.md)                                                                                                                                   |
| `@` (typed output) | Structured output schema     | [#31](31_typed_output.md), [#53](53_structured_schemas.md), [#55](55_deep_research.md), [#57](57_code_review_agent.md)                                                                                                    |
| `//` (fallback)    | Try A, fall back to B        | [#32](32_fallback_operator.md)                                                                                                                                                                                            |
| `Route`            | Deterministic branching      | [#17](17_route_branching.md), [#18](18_dict_routing.md), [#50](50_capture_and_route.md), [#56](56_customer_support_triage.md)                                                                                             |
| `S.*` transforms   | State manipulation           | [#33](33_state_transforms.md), [#50](50_capture_and_route.md), [#55](55_deep_research.md), [#56](56_customer_support_triage.md)                                                                                           |
| `C.*` context      | Context engineering          | [#49](49_context_engineering.md), [#55](55_deep_research.md), [#56](56_customer_support_triage.md)                                                                                                                        |
| `tap`              | Observe without side effects | [#35](35_tap_observation.md), [#57](57_code_review_agent.md)                                                                                                                                                              |
| `expect`           | State assertions             | [#36](36_expect_assertions.md), [#43](43_primitives_showcase.md)                                                                                                                                                          |
| `gate`             | Human-in-the-loop approval   | [#41](41_gate_approval.md), [#56](56_customer_support_triage.md)                                                                                                                                                          |
| `proceed_if`       | Conditional gating           | [#19](19_conditional_gating.md), [#57](57_code_review_agent.md)                                                                                                                                                           |
| `loop_while`       | Retry on transient failure   | [#38](38_retry_if.md)                                                                                                                                                                                                     |
| `timeout`          | Execution deadline           | [#40](40_timeout.md)                                                                                                                                                                                                      |
| `race`             | First response wins          | [#42](42_race.md)                                                                                                                                                                                                         |
| `loop_until`       | Loop until predicate         | [#20](20_loop_until.md), [#28](28_real_world_pipeline.md)                                                                                                                                                                 |
| `map_over`         | Iterate over items           | [#39](39_map_over.md)                                                                                                                                                                                                     |
| `Preset`           | Reusable config bundle       | [#22](22_presets.md), [#28](28_real_world_pipeline.md)                                                                                                                                                                    |
| `.guard()`         | Safety guards                | [#12](12_guardrails.md), [#58](58_multi_tool_agent.md)                                                                                                                                                                    |
| `.agent_tool()`    | LLM-driven routing           | [#27](27_delegate_pattern.md)                                                                                                                                                                                             |
| `.session()`       | Interactive sessions         | [#13](13_interactive_session.md)                                                                                                                                                                                          |
| `.explain()`       | Builder introspection        | [#25](25_validate_explain.md)                                                                                                                                                                                             |
| `.to_mermaid()`    | Architecture diagrams        | [#48](48_visualization.md)                                                                                                                                                                                                |
| `mock_backend()`   | Deterministic testing        | [#37](37_mock_testing.md)                                                                                                                                                                                                 |
| `E.*` eval         | Structured evaluation        | [#11](11_inline_testing.md), [#37](37_mock_testing.md), [#46](46_contracts_and_testing.md)                                                                                                                                |
| `E.compare()`      | Model comparison             | [#32](32_fallback_operator.md)                                                                                                                                                                                            |
| `E.gate()`         | Quality gate in pipeline     | [#46](46_contracts_and_testing.md)                                                                                                                                                                                        |
| `@agent` decorator | Decorator syntax             | [#24](24_agent_decorator.md)                                                                                                                                                                                              |

## Quick find by question

| I need to...                        | Start here                                                                                         |
| ----------------------------------- | -------------------------------------------------------------------------------------------------- |
| Build a simple agent                | [#01](01_simple_agent.md)                                                                          |
| Add tools to an agent               | [#02](02_agent_with_tools.md), [#58](58_multi_tool_agent.md)                                       |
| Build a chatbot with memory         | [#13](13_interactive_session.md), [#49](49_context_engineering.md)                                 |
| Chain agents into a pipeline        | [#04](04_sequential_pipeline.md), [#29](29_function_steps.md)                                      |
| Run agents in parallel              | [#05](05_parallel_fanout.md), [#42](42_race.md)                                                    |
| Route to different agents           | [#17](17_route_branching.md), [#18](18_dict_routing.md), [#27](27_delegate_pattern.md)             |
| Add guardrails and safety           | [#12](12_guardrails.md), [#19](19_conditional_gating.md), [#46](46_contracts_and_testing.md)       |
| Test my agents                      | [#11](11_inline_testing.md), [#36](36_expect_assertions.md), [#37](37_mock_testing.md)             |
| Evaluate agent quality              | [#11](11_inline_testing.md), [#37](37_mock_testing.md), [#46](46_contracts_and_testing.md)         |
| Compare models / agents             | [#32](32_fallback_operator.md)                                                                     |
| Retry / handle failures             | [#38](38_retry_if.md), [#32](32_fallback_operator.md), [#40](40_timeout.md)                        |
| Deploy to production                | [#15](15_production_runtime.md), [#45](45_middleware.md), [#47](47_dependency_injection.md)        |
| Serialize / save agents             | [#26](26_serialization.md)                                                                         |
| Debug data flow issues              | [#25](25_validate_explain.md), [#52](52_contract_checking.md), [#48](48_visualization.md)          |
| Build a complex real-world pipeline | [#28](28_real_world_pipeline.md), [#55](55_deep_research.md), [#56](56_customer_support_triage.md) |

______________________________________________________________________

## Customer Support & Triage

Build agents that classify tickets, route conversations, and escalate issues.

Every support system needs the same core capabilities: classify intent, route to
the right specialist, and escalate when the specialist fails. Without
deterministic routing, an LLM coordinator wastes API calls deciding where to
send a billing question -- a decision that should be instant and free. Without
context engineering, each specialist sees the classifier's internal reasoning
mixed in with the customer's actual message, leading to confused responses.
Without escalation gates, unresolved tickets silently close instead of reaching
a human. These recipes show how adk-fluent handles each of these concerns
declaratively.

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

Data pipelines break in predictable ways: missing fields crash downstream
agents, renamed columns produce garbage, and unchecked nulls propagate silently
until they corrupt the final output. In native ADK, every transform requires a
custom BaseAgent subclass -- 15-30 lines of boilerplate per step. In adk-fluent,
`S.pick`, `S.rename`, `S.guard`, and `S.compute` are composable one-liners that
slot into any pipeline with `>>`. The result is a pipeline where data
transformations are visible in the topology, not hidden in class files.

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

Research pipelines have a unique failure mode: they need to be both broad and
deep. A single-source search misses critical information. A sequential search
wastes time when sources are independent. And a search without quality review
produces reports full of contradictions that nobody trusts. adk-fluent's
parallel operator `|` runs searches concurrently, the `//` fallback operator
adds graceful degradation when a source is down, and the `* until()` loop
operator iterates quality reviews until confidence thresholds are met. Without
these, you end up with brittle pipelines that either miss sources or produce
low-quality output.

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

Content quality is inherently iterative -- first drafts are rarely good enough.
Without structured iteration, teams resort to manual copy-paste cycles between
a writer and reviewer, losing context and version history with each round. The
`* N` and `* until()` operators in adk-fluent formalize this iteration pattern,
making it testable and bounded. The `@` operator ensures output conforms to
a schema, and `tap()` lets you observe quality metrics without mutating the
pipeline. Without these, quality loops are ad-hoc and unbounded, leading to
either infinite loops or premature termination.

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

E-commerce and financial systems demand deterministic behavior -- routing a
payment to the wrong processor is not a "hallucination," it's a financial
incident. LLM-based routing is too slow and too unpredictable for decisions
that can be made on a single state key. adk-fluent's `Route` primitive provides
instant, deterministic branching based on state values. `proceed_if()` gates
prevent unauthorized transactions from reaching downstream processors. `@`
typed output ensures invoices and reports conform to expected schemas rather
than returning free-form text that breaks downstream systems.

| Recipe                           | Key features                    | Cookbook                         |
| -------------------------------- | ------------------------------- | -------------------------------- |
| E-Commerce Order Routing         | `Route` deterministic branching | [#17](17_route_branching.md)     |
| Fraud Detection Pipeline         | `proceed_if` conditional gating | [#19](19_conditional_gating.md)  |
| Order Processing with State Keys | `StateKey` typed descriptors    | [#21](21_statekey.md)            |
| Structured Invoice Parsing       | `@` typed output operator       | [#31](31_typed_output.md)        |
| E-Commerce Primitives Showcase   | All primitives combined         | [#43](43_primitives_showcase.md) |

## Team Coordination & Delegation

Multi-agent systems with coordinators, specialists, and routing.

Most multi-agent systems start the same way: a coordinator decides which
specialist to call. The critical design choice is whether the coordinator uses
the LLM to decide (flexible but expensive and unpredictable) or uses
deterministic rules (fast and testable but rigid). adk-fluent supports both:
`.agent_tool()` lets the LLM pick the specialist when the decision is complex,
while `Route()` provides instant deterministic dispatch when the decision is
simple. Without this distinction, teams either waste API calls on trivial
routing or lose flexibility on complex delegation.

| Recipe                     | Key features                        | Cookbook                      |
| -------------------------- | ----------------------------------- | ----------------------------- |
| Product Launch Coordinator | Team coordinator pattern            | [#07](07_team_coordinator.md) |
| Senior Architect Delegates | LLM-driven routing, `.agent_tool()` | [#27](27_delegate_pattern.md) |
| Multi-Language Routing     | Dict `>>` shorthand                 | [#18](18_dict_routing.md)     |
| Multi-Tool Task Agent      | `.tool()`, `.guard()`, `.inject()`  | [#58](58_multi_tool_agent.md) |

## Safety, Guardrails & Compliance

Content moderation, medical safety, legal approval gates, and contracts.

In regulated domains, an unguarded AI response can create legal liability,
violate compliance requirements, or cause patient harm. Guardrails are not
optional -- they are the difference between a prototype and a deployable
system. adk-fluent's `.guard()` method registers safety checks as both
pre-model and post-model hooks in a single call. `gate()` pauses the pipeline
for human approval on high-risk decisions. Data contracts (`.produces()`,
`.consumes()`) catch missing fields at build time rather than letting them
surface in production with patient data at stake. Without these, every
safety check is a hand-written callback scattered across the codebase with
no guarantee of consistent application.

| Recipe                          | Key features                                   | Cookbook                           |
| ------------------------------- | ---------------------------------------------- | ---------------------------------- |
| Content Moderation with Logging | `before_model`, `after_model` callbacks        | [#03](03_callbacks.md)             |
| Medical Advice Safety Guards    | `.guard()` method                              | [#12](12_guardrails.md)            |
| Legal Document Review           | `gate` with human approval                     | [#41](41_gate_approval.md)         |
| Medical Imaging Contracts       | `.produces()`, `.consumes()`, strict contracts | [#46](46_contracts_and_testing.md) |
| Contract Checking               | Catch data flow bugs early                     | [#52](52_contract_checking.md)     |
| Enterprise Compliance Preset    | `Preset` for shared config                     | [#22](22_presets.md)               |

## Production & Deployment

Deploying, testing, serializing, and monitoring agents in production.

The gap between a working prototype and a production system is filled with
concerns that have nothing to do with the agent's core logic: retries for
transient failures, cost tracking for budget management, latency monitoring for
SLA compliance, dependency injection for environment-specific configuration,
and serialization for CI/CD pipelines. In native ADK, each of these requires
custom boilerplate. adk-fluent's middleware system (`M.retry()`, `M.cost()`,
`M.latency()`), dependency injection (`.inject()`), and serialization
(`to_dict()`, `to_yaml()`) handle these cross-cutting concerns declaratively.
Without them, production concerns leak into agent logic, making the code
harder to test, harder to maintain, and harder to reason about.

| Recipe                      | Key features                          | Cookbook                          |
| --------------------------- | ------------------------------------- | --------------------------------- |
| Production Deployment       | `to_app()` with middleware            | [#15](15_production_runtime.md)   |
| Deployment Serialization    | `to_dict`, `to_yaml`, `from_dict`     | [#26](26_serialization.md)        |
| Mock Testing Pipeline       | `mock_backend()`, deterministic tests | [#37](37_mock_testing.md)         |
| Dependency Injection        | Dev/staging/prod environments         | [#47](47_dependency_injection.md) |
| ML Inference Monitoring     | `tap` for pure observation            | [#35](35_tap_observation.md)      |
| Middleware Stack            | Production middleware for healthcare  | [#45](45_middleware.md)           |
| Retry on Transient Failures | `loop_while` pattern                  | [#38](38_retry_if.md)             |
| Timeout for Trading Agent   | `timeout` execution deadline          | [#40](40_timeout.md)              |

## Developer Experience & Tooling

Introspection, visualization, debugging, and IDE workflow.

When an agent pipeline does something unexpected, you need to answer three
questions fast: what is the pipeline topology, what data flows between agents,
and which agent produced the wrong output? Without introspection tools, you
resort to print-debugging across a graph of async agents -- a miserable
experience. adk-fluent provides `.explain()` for human-readable pipeline
summaries, `.validate()` for configuration errors, `.to_mermaid()` for
architecture diagrams that stay in sync with code, and `.inspect()` for
raw builder state. These tools turn debugging from guesswork into systematic
investigation.

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
