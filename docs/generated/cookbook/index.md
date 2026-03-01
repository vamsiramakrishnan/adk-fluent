# Cookbook

Side-by-side examples comparing native ADK code with the adk-fluent
equivalent. Each recipe demonstrates a specific pattern or feature.

## Basics

Foundational patterns: creating agents, adding tools, callbacks, and simple workflows.

- \[Email Classifier Agent -- Simple Agent Creation

Demonstrates creating a minimal LLM agent using both native ADK and
the fluent builder.  The scenario: an agent that classifies incoming
customer emails into categories (billing, technical, general).\](01_simple_agent.md)

- \[Travel Planner with Weather and Flight Lookup -- Agent with Tools

Demonstrates attaching function tools to an agent.  The scenario:
a travel planning assistant that can look up weather forecasts and
search for flights to help users plan trips.\](02_agent_with_tools.md)

- \[Content Moderation with Logging -- Additive Callbacks

Demonstrates before_model and after_model callbacks.  The scenario:
a content moderation agent where we log every request before it
reaches the model and audit every response after generation.\](03_callbacks.md)

- \[Document Processing Pipeline -- Sequential Pipeline

Demonstrates a SequentialAgent that chains steps in order.  The
scenario: a document processing pipeline that extracts key data
from a contract, analyzes legal risks, then produces an executive
summary.

Pipeline topology:
extractor >> risk_analyst >> summarizer\](04_sequential_pipeline.md)

- \[Market Research Fan-Out -- Parallel FanOut

Demonstrates a ParallelAgent that runs branches concurrently.  The
scenario: a market research system that simultaneously gathers
intelligence from web sources, academic papers, and social media
to produce a comprehensive competitive analysis.

Pipeline topology:
( web_analyst | academic_analyst | social_analyst )\](05_parallel_fanout.md)

- \[Essay Refinement Loop -- Loop Agent

Demonstrates a LoopAgent that iterates sub-agents until a maximum
iteration count.  The scenario: an essay refinement workflow where
a critic evaluates the draft and a reviser improves it, repeating
up to 3 times until quality standards are met.

Pipeline topology:
( critic >> reviser ) * 3\](06_loop_agent.md)

- \[Product Launch Coordinator -- Team Coordinator Pattern

Demonstrates an LLM agent that delegates to specialized sub-agents.
The scenario: a product launch coordinator that routes tasks to
marketing, engineering, and legal teams based on the request.

Pipeline topology:
launch_coordinator
|-- marketing
|-- engineering
'-- legal\](07_team_coordinator.md)

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
queries.  The scenario: a code review agent that can be invoked
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
a shared base configuration.  The scenario: A/B testing two customer
support agents -- one using a formal tone and one using a casual tone
-- while sharing the same underlying tool (order lookup).\](10_cloning.md)

- \[Smoke-Testing a Customer Support Bot -- Inline Testing with .test()

Demonstrates the .test() method for validating agent behavior during
development.  The scenario: a customer support bot that is
smoke-tested inline before deployment to ensure it handles common
queries correctly.  No LLM calls are made here -- we verify that
the builder exposes the test API with the right signature.\](11_inline_testing.md)

- \[Medical Advice Safety Guardrails -- Guardrails with .guard()

Demonstrates the .guard() method that registers a function as
both a before_model and after_model callback in one call.  The
scenario: a medical information agent with safety guards that
screen requests and responses for dangerous self-diagnosis or
treatment recommendations.\](12_guards.md)

- [Customer Support Chat Session with .session()](13_interactive_session.md)
- [Medical Advice Safety Guards -- Guards with .guard()](12_guardrails.md)

```{toctree}
---
hidden:
---
08_one_shot_ask
09_streaming
10_cloning
11_inline_testing
12_guards
13_interactive_session
12_guardrails
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

- \[News Analysis Pipeline with Operator Composition: >>, |, \*

Pipeline topologies:
\>>  scraper >> analyzer >> reporter
|   ( politics | markets )
\*   ( draft_writer >> fact_checker ) * 3\](16_operator_composition.md)

- \[E-Commerce Order Routing with Deterministic Branching

Pipeline topology:
Route("category")
├─ "electronics" -> electronics
├─ "clothing"    -> clothing
├─ "grocery"     -> grocery
└─ otherwise     -> general\](17_route_branching.md)

- [Multi-Language Support Routing with Dict >> Shorthand](18_dict_routing.md)
- [Fraud Detection Pipeline with Conditional Gating](19_conditional_gating.md)
- \[Resume Refinement Loop with Conditional Exit

Pipeline topology:
( resume_writer >> resume_reviewer ) * until(quality_score == "excellent")\](20_loop_until.md)

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
- [Senior Architect Delegates to Junior Specialists (LLM-Driven Routing)](27_agent_tool_pattern.md)
- \[Investment Analysis Pipeline: Full Expression Language in Production

Pipeline topology:
asset_classifier
\>> Route("asset_class")
├─ "equity"       -> equity_screener
├─ "fixed_income" -> credit_analyst >> rate_modeler
└─ "alternative"  -> ( quant_modeler | market_sentiment ) >> risk_aggregator
\>> ( portfolio_reviewer >> analysis_refiner ) * until(approved)
\>> report_generator  \[gated: only if approved\]\](28_real_world_pipeline.md)

- [ETL Pipeline: Plain Functions as Data Cleaning Steps (>> fn)](29_function_steps.md)
- [Customer Onboarding: Conditional Loops with * until(pred) Operator](30_until_operator.md)
- [Structured Invoice Parsing: Typed Output Contracts with @ Operator](31_typed_output.md)
- \[Knowledge Retrieval: Primary API + Fallback Search with // Operator

Pipeline topologies:
//  vector_db // fulltext_search          (two-way fallback)
//  internal_kb // web_search // expert   (three-way cascade)

```
RAG pipeline:
    query_rewriter >> ( vector_db // fulltext ) >> answer_generator](32_fallback_operator.md)
```

- \[Research Data Pipeline: State Transforms with S Factories

Pipeline topology:
data_extractor
\>> S.pick("clinical_findings", "lab_results")
\>> S.rename(clinical_findings="analysis_input")
\>> S.default(confidence_interval=0.95)
\>> statistical_analyzer

```
Research pipeline:
    ( literature_agent | trial_agent )
        >> S.merge(into="combined_evidence")
        >> S.default(...)
        >> report_writer
        >> S.compute(word_count=...)](33_state_transforms.md)
```

- \[Code Review Pipeline -- Expression Algebra in Practice

Demonstrates how composition operators (>>, |, @, //) combine naturally
in a real-world code review system. A diff parser extracts changes,
parallel reviewers check style, security, and logic independently,
then findings are aggregated into a structured verdict.

Pipeline topology:
diff_parser
\>> ( style_checker | security_scanner | logic_reviewer )
\>> ( finding_aggregator @ ReviewVerdict // backup_aggregator @ ReviewVerdict )\](34_full_algebra.md)

- [ML Inference Monitoring: Performance Tap for Pure Observation](35_tap_observation.md)
- [Analytics Data Quality: State Contract Assertions with expect()](36_expect_assertions.md)
- [Mock Testing: Customer Onboarding Pipeline with Deterministic Mocks](37_mock_testing.md)
- [Retry If: API Integration Agent That Retries on Transient Failures](38_loop_while.md)
- [Map Over: Batch Processing Customer Feedback with Iteration](39_map_over.md)
- [Timeout: Real-Time Trading Agent with Strict Execution Deadline](40_timeout.md)
- [Gate: Legal Document Review with Human Approval](41_gate_approval.md)
- \[Race: Fastest-Response Search Across Multiple Providers

Pipeline topology:
race( westlaw_search, lexis_search )    -- first to finish wins

```
Research pipeline:
    query_classifier >> race( federal_search, state_search ) >> citation_formatter](42_race.md)
```

- [Primitives Showcase: E-Commerce Order Pipeline Using All Primitives](43_primitives_showcase.md)
- [Senior Architect Delegates to Junior Specialists (LLM-Driven Routing)](27_delegate_pattern.md)
- [Retry If: API Integration Agent That Retries on Transient Failures](38_retry_if.md)

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
27_agent_tool_pattern
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
38_loop_while
39_map_over
40_timeout
41_gate_approval
42_race
43_primitives_showcase
27_delegate_pattern
38_retry_if
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
- \[Capture and Route: IT Helpdesk Triage

Pipeline topology:
S.capture("ticket")
\>> triage \[save_as: priority\]
\>> Route("priority")
├─ "p1" -> incident_commander
├─ "p2" -> senior_support
└─ else -> support_bot\](50_capture_and_route.md)

- [Visibility: Content Review Pipeline](51_visibility_policies.md)
- [Contract Checking: Catch Data Flow Bugs Before Runtime](52_contract_checking.md)
- \[Insurance Claim Processing: Structured Data Pipelines

Demonstrates structured output schemas and the @ operator for typed
agent responses.  The scenario: an insurance company processes claims
through a pipeline -- first ingesting claim details into a structured
form, then assessing risk, then summarizing the outcome.\](53_structured_schemas.md)

- \[Customer Service Hub: Agent Transfer Control

Demonstrates controlling how agents transfer between each other using
disallow_transfer_to_parent, disallow_transfer_to_peers, and the
.isolate() convenience method.  The scenario: a customer service system
where a coordinator routes to specialist agents that must complete their
task before returning control.\](54_transfer_control.md)

- \[Deep Research Agent -- Gemini Deep Research / Perplexity Clone

Demonstrates building a multi-stage research pipeline inspired by
Gemini's Deep Research feature and Perplexity. A query is decomposed
into sub-questions, searched in parallel across multiple sources,
synthesized, quality-reviewed in a loop, and formatted as a report.

Pipeline topology:
query_analyzer
\>> ( web_searcher | academic_searcher | news_searcher )
\>> synthesizer
\>> ( quality_reviewer >> revision_agent ) * until(score >= 0.85)
\>> report_writer @ ResearchReport

Uses: >>, |, *, @, S.*, C.\*, save_as, loop_until\](55_deep_research.md)

- \[Customer Support Triage -- ADK-Samples Inspired Multi-Tier Support

Demonstrates building a customer support triage system inspired by
real call center architectures and Google's ADK agent samples. Uses
state capture, context engineering, routing, and escalation gates.

Pipeline topology:
S.capture("customer_message")
\>> intent_classifier \[C.none, save_as: intent\]
\>> Route("intent")
├─ "billing"   -> billing_specialist
├─ "technical" -> tech_support
├─ "account"   -> account_manager
└─ otherwise   -> general_support
\>> satisfaction_monitor
\>> gate(resolved == "no") -> escalate

Uses: S.capture, C.none, C.from_state, Route, gate, save_as\](56_customer_support_triage.md)

- \[Code Review Agent -- Gemini CLI / GitHub Copilot Inspired

Demonstrates building an automated code review agent inspired by
Gemini CLI's code review and GitHub Copilot's review features.
Uses parallel fan-out for concurrent analysis, typed output for
structured findings, and conditional gating.

Pipeline topology:
diff_parser \[save_as: parsed_changes\]
\>> ( style_checker | security_scanner | logic_reviewer )
\>> tap(log)
\>> finding_aggregator @ ReviewResult
\>> comment_writer \[gated: findings_count > 0\]

Uses: >>, |, @, proceed_if, save_as, tap\](57_code_review_agent.md)

- \[Multi-Tool Task Agent -- Manus / OpenAI Agents SDK Inspired

Demonstrates building a versatile task agent with multiple tools,
safety guardrails, and dependency injection -- inspired by Manus AI's
tool-using agent and the OpenAI Agents SDK patterns.

Pipeline topology:
task_agent \[tools: search, calc, read_file\] \[guardrail\] \[inject: api_key\]
\>> verifier \[C.from_state("task_result")\]

Uses: .tool(), .guard(), .inject(), .sub_agent(), .context()\](58_multi_tool_agent.md)

- \[Dispatch & Join: Fire-and-Continue Background Execution

Demonstrates the dispatch/join primitives for non-blocking background
agent execution.  Unlike FanOut (which blocks until all complete) or
race (which takes first and cancels rest), dispatch fires agents as
background tasks and lets the pipeline continue immediately.

Pipeline topology:
writer
\>> dispatch(email_sender, seo_optimizer)   -- fire-and-continue
\>> formatter                                -- runs immediately
\>> join()                                   -- barrier: wait for all
\>> publisher

```
Selective join:
    writer >> dispatch(email, seo) >> formatter >> join("seo") >> publisher >> join("email")
```

Key concepts:

- dispatch(\*agents): launches agents as asyncio.Tasks, pipeline continues
- join(): barrier that waits for dispatched tasks to complete
- join("name"): selective join -- wait for specific tasks only
- .dispatch(name="x"): method form for any builder
- Named tasks, callbacks, timeout, progress streaming\](59_dispatch_join.md)
- \[StreamRunner: Continuous Userless Agent Execution

Demonstrates the Source and StreamRunner for processing continuous
data streams without a human in the loop.

Key concepts:

- Source.from_iter(): wrap a sync iterable as an async stream
- Source.from_async(): pass through an async generator
- Source.poll(): poll a function at intervals
- Source.callback() / Inbox: push-based source for webhooks
- StreamRunner: bridges AsyncIterator → ADK runner.run_async()
- Session strategies: per_item, shared, keyed
- Callbacks: on_result, on_error (dead-letter queue)
- StreamStats: live counters (processed, errors, throughput)\](60_stream_runner.md)
- \[Dispatch-Aware Middleware: Observability for Background Execution

Demonstrates the dispatch/join middleware hooks for observing
background agent lifecycle events.

Key concepts:

- DispatchLogMiddleware: built-in observability for dispatch/join
- on_dispatch: fired when a task is dispatched as background
- on_task_complete: fired when a dispatched task completes
- on_task_error: fired when a dispatched task fails
- on_join: fired after a join barrier completes
- on_stream_item: fired after each stream item is processed
- get_execution_mode(): query current mode (pipeline/dispatched/stream)
- task_budget(): configure max concurrent dispatch tasks\](61_dispatch_middleware.md)
- \[M Module: Fluent Middleware Composition

Demonstrates the M module -- a fluent composition surface for middleware,
consistent with P (prompts), C (context), S (state transforms).

Key concepts:

- M.retry(), M.log(), M.cost(), M.latency(): built-in factories
- M.topology_log(), M.dispatch_log(): topology and dispatch observability
- | operator: compose middleware chains (M.retry(3) | M.log())
- M.scope("agent", mw): restrict middleware to specific agents
- M.when(condition, mw): conditional middleware (string, callable, PredicateSchema)
- M.before_agent(fn): single-hook shortcut for quick observability
- MComposite: composable chain class with to_stack() for flattening\](62_m_module_composition.md)
- \[TraceContext and Topology Hooks: Cross-Cutting Observability

Demonstrates the TraceContext per-invocation state bag and the
topology hooks protocol for observing workflow structure.

Key concepts:

- TraceContext: request_id, elapsed, key-value store per invocation
- TopologyHooks protocol: on_loop_iteration, on_fanout_start/complete,
  on_route_selected, on_fallback_attempt, on_timeout
- DispatchDirective: cancel dispatches or inject state
- LoopDirective: break out of loops from middleware
- TopologyLogMiddleware: built-in structured topology logging
- \_trace_context ContextVar: access from any hook\](63_trace_context_topology.md)
- \[MiddlewareSchema: Typed Middleware State Declarations

Demonstrates MiddlewareSchema for declaring middleware state dependencies,
enabling the contract checker to validate middleware reads/writes at
compile time.

Key concepts:

- MiddlewareSchema: base class for typed middleware declarations
- Reads(scope=...): field read from state before execution
- Writes(scope=...): field written to state after execution
- reads_keys() / writes_keys(): introspect declared dependencies
- schema attribute: bind a MiddlewareSchema to a middleware class
- agents attribute: scope middleware to specific pipeline agents
- Contract checker Pass 14: validates scoped middleware at build time
- M.when(PredicateSchema, mw): state-aware conditional middleware\](64_middleware_schema.md)
- \[Built-in Middleware: CostTracker, LatencyMiddleware, TopologyLogMiddleware

Demonstrates the built-in middleware classes for production observability
and the error boundary mechanism that prevents middleware failures from
crashing the pipeline.

Key concepts:

- CostTracker: token usage accumulation via after_model
- LatencyMiddleware: per-agent timing via TraceContext
- TopologyLogMiddleware: structured logging for topology events
- Error boundary: middleware exceptions caught, logged, and reported
- on_middleware_error: notification hook for other middleware
- Custom middleware with typed MiddlewareSchema\](65_builtin_middleware.md)
- \[T Module: Fluent Tool Composition and Dynamic Loading

Demonstrates the T module for composing, wrapping, and dynamically
loading tools using the fluent API.

Key concepts:

- TComposite: composable tool chain with | operator
- T.fn(): wrap callable as FunctionTool
- T.agent(): wrap agent as AgentTool
- T.toolset(): wrap any ADK toolset
- T.google_search(): built-in Google Search
- T.schema(): attach ToolSchema for contract checking
- T.search(): BM25-indexed dynamic tool loading
- ToolRegistry: tool catalog with search
- SearchToolset: two-phase discovery/execution\](66_t_module_tools.md)

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
59_dispatch_join
60_stream_runner
61_dispatch_middleware
62_m_module_composition
63_trace_context_topology
64_middleware_schema
65_builtin_middleware
66_t_module_tools
```

## Other

Additional examples.

- [Recipes by Use Case](recipes-by-use-case.md)

```{toctree}
---
hidden:
---
recipes-by-use-case
```
