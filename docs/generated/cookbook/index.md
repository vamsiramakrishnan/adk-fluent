# Cookbook

Side-by-side examples comparing native ADK code with the adk-fluent
equivalent. Each recipe demonstrates a specific pattern or feature.

:::\{tip}
Looking for a specific use case? See **[Recipes by Use Case](recipes-by-use-case.md)**
for all 58 examples organized by domain (customer support, e-commerce,
research, production deployment, etc.).
:::

## How to run these examples

Cookbook examples are **equivalence tests** — they verify that fluent
builders produce identical ADK objects to native constructors. They
do **not** call any LLM APIs.

```bash
# Install (no API key needed for cookbook tests)
pip install adk-fluent

# Run all 58 cookbook tests
pytest examples/cookbook/ -v

# Run a single example
pytest examples/cookbook/01_simple_agent.py -v

# Run and see output
python examples/cookbook/01_simple_agent.py
```

Each file is self-contained: copy it, paste it into a file, and run
`python file.py`. If it imports from `adk_fluent`, you need the package
installed. If it imports from `google.adk`, you need `google-adk`
installed (which `adk-fluent` pulls in automatically).

## Basics

Foundational patterns: creating agents, adding tools, callbacks, and simple workflows.

- \[Email Classifier Agent -- Simple Agent Creation

Demonstrates creating a minimal LLM agent using both native ADK and
the fluent builder. The scenario: an agent that classifies incoming
customer emails into categories (billing, technical, general).\](01_simple_agent.md)

- \[Travel Planner with Weather and Flight Lookup -- Agent with Tools

Demonstrates attaching function tools to an agent. The scenario:
a travel planning assistant that can look up weather forecasts and
search for flights to help users plan trips.\](02_agent_with_tools.md)

- \[Content Moderation with Logging -- Additive Callbacks

Demonstrates before_model and after_model callbacks. The scenario:
a content moderation agent where we log every request before it
reaches the model and audit every response after generation.\](03_callbacks.md)

- \[Document Processing Pipeline -- Sequential Pipeline

Demonstrates a SequentialAgent that chains steps in order. The
scenario: a document processing pipeline that extracts key data
from a contract, analyzes legal risks, then produces an executive
summary.\](04_sequential_pipeline.md)

- \[Market Research Fan-Out -- Parallel FanOut

Demonstrates a ParallelAgent that runs branches concurrently. The
scenario: a market research system that simultaneously gathers
intelligence from web sources, academic papers, and social media
to produce a comprehensive competitive analysis.\](05_parallel_fanout.md)

- \[Essay Refinement Loop -- Loop Agent

Demonstrates a LoopAgent that iterates sub-agents until a maximum
iteration count. The scenario: an essay refinement workflow where
a critic evaluates the draft and a reviser improves it, repeating
up to 3 times until quality standards are met.\](06_loop_agent.md)

- \[Product Launch Coordinator -- Team Coordinator Pattern

Demonstrates an LLM agent that delegates to specialized sub-agents.
The scenario: a product launch coordinator that routes tasks to
marketing, engineering, and legal teams based on the request.\](07_team_coordinator.md)

```{toctree}
---
hidden:
---
01_simple_agent
02_agent_with_tools
03_callbacks
04_sequential_pipeline
05_parallel_fanout
06_loop_agent
07_team_coordinator
```

## Execution

Running agents: one-shot, streaming, cloning, testing, and sessions.

- \[Quick Code Review -- One-Shot Execution with .ask()

Demonstrates the .ask() convenience method for fire-and-forget
queries. The scenario: a code review agent that can be invoked
with a single line to get feedback on a code snippet.
No LLM calls are made here -- we only verify builder mechanics.\](08_one_shot_ask.md)

- \[Live Translation Pipeline -- Streaming with .stream()

Demonstrates the .stream() method for token-by-token output. The
scenario: a real-time multilingual translation service that transcribes
audio input and streams translated text as it generates -- critical
for live conferences, court interpreting, and broadcast captioning.
No LLM calls are made here -- we verify builder and pipeline mechanics.\](09_streaming.md)

- \[A/B Testing Agent Variants -- Agent Cloning with .clone()

Demonstrates .clone() for creating independent agent variants from
a shared base configuration. The scenario: A/B testing two customer
support agents -- one using a formal tone and one using a casual tone
-- while sharing the same underlying tool (order lookup).\](10_cloning.md)

- \[Smoke-Testing a Customer Support Bot -- Inline Testing with .test()

Demonstrates the .test() method for validating agent behavior during
development. The scenario: a customer support bot that is
smoke-tested inline before deployment to ensure it handles common
queries correctly. No LLM calls are made here -- we verify that
the builder exposes the test API with the right signature.\](11_inline_testing.md)

- \[Medical Advice Safety Guards -- Guards with .guard()

Demonstrates the .guard() method that registers a function as
both a before_model and after_model callback in one call. The
scenario: a medical information agent with safety guards that
screen requests and responses for dangerous self-diagnosis or
treatment recommendations.\](12_guardrails.md)

- [Customer Support Chat Session with .session()](13_interactive_session.md)

```{toctree}
---
hidden:
---
08_one_shot_ask
09_streaming
10_cloning
11_inline_testing
12_guardrails
13_interactive_session
```

## Advanced

Advanced composition: dynamic forwarding, operators, routing, and conditional logic.

- [Multi-Department Ticket Routing via Dynamic Field Forwarding](14_dynamic_forwarding.md)
- \[Production Deployment -- to_app() with Middleware Stack

Demonstrates deploying a fluent builder to production using to_app(),
which compiles through the IR to a native ADK App with middleware.
The scenario: an e-commerce order processing agent deployed with
retry logic for transient failures and structured logging for
operational visibility.\](15_production_runtime.md)

- [News Analysis Pipeline with Operator Composition: >>, |, \*](16_operator_composition.md)
- [E-Commerce Order Routing with Deterministic Branching](17_route_branching.md)
- [Multi-Language Support Routing with Dict >> Shorthand](18_dict_routing.md)
- [Fraud Detection Pipeline with Conditional Gating](19_conditional_gating.md)
- [Resume Refinement Loop with Conditional Exit](20_loop_until.md)

```{toctree}
---
hidden:
---
14_dynamic_forwarding
15_production_runtime
16_operator_composition
17_route_branching
18_dict_routing
19_conditional_gating
20_loop_until
```

## Patterns

Real-world patterns: state management, presets, decorators, serialization, and more.

- [Order Processing with Typed State Keys](21_statekey.md)
- [Enterprise Agent with Shared Compliance Preset](22_presets.md)
- [A/B Prompt Testing for Marketing Copy with .with\_()](23_with_variants.md)
- [Domain Expert Agent via @agent Decorator](24_agent_decorator.md)
- \[Introspection & Debugging -- validate(), explain(), inspect()

Demonstrates the introspection methods that help debug and understand
agent configurations before deployment. The scenario: a compliance
team reviewing an insurance claims pipeline to verify correct wiring
before going live.\](25_validate_explain.md)

- [Deployment Pipeline: Serialize Agent Configs with to_dict and to_yaml](26_serialization.md)
- [Senior Architect Delegates to Junior Specialists (LLM-Driven Routing)](27_delegate_pattern.md)
- [Investment Analysis Pipeline: Full Expression Language in Production](28_real_world_pipeline.md)
- [ETL Pipeline: Plain Functions as Data Cleaning Steps (>> fn)](29_function_steps.md)
- [Customer Onboarding: Conditional Loops with * until(pred) Operator](30_until_operator.md)
- [Structured Invoice Parsing: Typed Output Contracts with @ Operator](31_typed_output.md)
- [Knowledge Retrieval: Primary API + Fallback Search with // Operator](32_fallback_operator.md)
- [Research Data Pipeline: State Transforms with S Factories](33_state_transforms.md)
- \[Code Review Pipeline -- Expression Algebra in Practice

Demonstrates how composition operators (>>, |, @, //) combine naturally
in a real-world code review system. A diff parser extracts changes,
parallel reviewers check style, security, and logic independently,
then findings are aggregated into a structured verdict.\](34_full_algebra.md)

- [ML Inference Monitoring: Performance Tap for Pure Observation](35_tap_observation.md)
- [Analytics Data Quality: State Contract Assertions with expect()](36_expect_assertions.md)
- [Mock Testing: Customer Onboarding Pipeline with Deterministic Mocks](37_mock_testing.md)
- [Retry If: API Integration Agent That Retries on Transient Failures](38_retry_if.md)
- [Map Over: Batch Processing Customer Feedback with Iteration](39_map_over.md)
- [Timeout: Real-Time Trading Agent with Strict Execution Deadline](40_timeout.md)
- [Gate: Legal Document Review with Human Approval](41_gate_approval.md)
- [Race: Fastest-Response Search Across Multiple Providers](42_race.md)
- [Primitives Showcase: E-Commerce Order Pipeline Using All Primitives](43_primitives_showcase.md)

```{toctree}
---
hidden:
---
21_statekey
22_presets
23_with_variants
24_agent_decorator
25_validate_explain
26_serialization
27_delegate_pattern
28_real_world_pipeline
29_function_steps
30_until_operator
31_typed_output
32_fallback_operator
33_state_transforms
34_full_algebra
35_tap_observation
36_expect_assertions
37_mock_testing
38_retry_if
39_map_over
40_timeout
41_gate_approval
42_race
43_primitives_showcase
```

## v4 Features

IR compilation, middleware, contracts, testing, dependency injection, and visualization.

- \[Pipeline Optimization with IR -- Inspecting and Compiling Agent Graphs

Demonstrates to_ir() for pipeline analysis, to_app() for production
compilation, and to_mermaid() for architecture documentation. The
scenario: a mortgage approval pipeline where the platform team
inspects the agent graph for optimization before deployment.\](44_ir_and_backends.md)

- [Middleware: Production Middleware Stack for a Healthcare API Agent](45_middleware.md)
- [Contracts and Testing: Medical Imaging Pipeline with Strict Data Contracts](46_contracts_and_testing.md)
- [Dependency Injection: Multi-Environment Deployment (Dev/Staging/Prod)](47_dependency_injection.md)
- \[Architecture Documentation -- Mermaid Diagrams from Live Code

Demonstrates to_mermaid() for generating architecture diagrams that
stay in sync with code. The scenario: a DevOps team documenting their
incident response platform's agent topology for runbooks and onboarding.\](48_visualization.md)

```{toctree}
---
hidden:
---
44_ir_and_backends
45_middleware
46_contracts_and_testing
47_dependency_injection
48_visualization
```

## v5.1 Features

Context engineering, visibility, memory, and contract verification.

- [Context Engineering: Customer Support Pipeline](49_context_engineering.md)
- [Capture and Route: IT Helpdesk Triage](50_capture_and_route.md)
- [Visibility: Content Review Pipeline](51_visibility_policies.md)
- [Contract Checking: Catch Data Flow Bugs Before Runtime](52_contract_checking.md)
- \[Insurance Claim Processing: Structured Data Pipelines

Demonstrates structured output schemas and the @ operator for typed
agent responses. The scenario: an insurance company processes claims
through a pipeline -- first ingesting claim details into a structured
form, then assessing risk, then summarizing the outcome.\](53_structured_schemas.md)

- \[Customer Service Hub: Agent Transfer Control

Demonstrates controlling how agents transfer between each other using
disallow_transfer_to_parent, disallow_transfer_to_peers, and the
.isolate() convenience method. The scenario: a customer service system
where a coordinator routes to specialist agents that must complete their
task before returning control.\](54_transfer_control.md)

- \[Deep Research Agent -- Gemini Deep Research / Perplexity Clone

Demonstrates building a multi-stage research pipeline inspired by
Gemini's Deep Research feature and Perplexity. A query is decomposed
into sub-questions, searched in parallel across multiple sources,
synthesized, quality-reviewed in a loop, and formatted as a report.

Uses: >>, |, *, @, S.*, C.\*, writes, loop_until\](55_deep_research.md)

- \[Customer Support Triage -- ADK-Samples Inspired Multi-Tier Support

Demonstrates building a customer support triage system inspired by
real call center architectures and Google's ADK agent samples. Uses
state capture, context engineering, routing, and escalation gates.

Uses: S.capture, C.none, C.from_state, Route, gate, writes\](56_customer_support_triage.md)

- \[Code Review Agent -- Gemini CLI / GitHub Copilot Inspired

Demonstrates building an automated code review agent inspired by
Gemini CLI's code review and GitHub Copilot's review features.
Uses parallel fan-out for concurrent analysis, typed output for
structured findings, and conditional gating.

Uses: >>, |, @, proceed_if, writes, tap\](57_code_review_agent.md)

- \[Multi-Tool Task Agent -- Manus / OpenAI Agents SDK Inspired

Demonstrates building a versatile task agent with multiple tools,
safety guardrails, and dependency injection -- inspired by Manus AI's
tool-using agent and the OpenAI Agents SDK patterns.

Uses: .tool(), .guard(), .inject(), .sub_agent(), .context()\](58_multi_tool_agent.md)

```{toctree}
---
hidden:
---
49_context_engineering
50_capture_and_route
51_visibility_policies
52_contract_checking
53_structured_schemas
54_transfer_control
55_deep_research
56_customer_support_triage
57_code_review_agent
58_multi_tool_agent
```

```{toctree}
---
hidden:
---
recipes-by-use-case
```
