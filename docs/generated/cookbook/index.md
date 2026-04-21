# Cookbook

Side-by-side examples comparing native ADK code with the adk-fluent
equivalent. Each recipe demonstrates a specific pattern or feature.

:::{note}
Looking for a specific scenario? Check out the [Recipes by Use Case](recipes-by-use-case.md) guide.
:::

## Basics

Foundational patterns: creating agents, adding tools, callbacks, and simple workflows.

````{grid} 1 2 2 2
---
gutter: 3
---
```{grid-item-card} Email Classifier Agent -- Simple Agent Creation

Demonstrates creating a minimal LLM agent using both native ADK and
the fluent builder.  The scenario: an agent that classifies incoming
customer emails into categories (billing, technical, general).
:link: 01_simple_agent
:link-type: doc

How to create a basic agent with the fluent API.
```
```{grid-item-card} Travel Planner with Weather and Flight Lookup -- Agent with Tools

Demonstrates attaching function tools to an agent.  The scenario:
a travel planning assistant that can look up weather forecasts and
search for flights to help users plan trips.
:link: 02_agent_with_tools
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Content Moderation with Logging -- Additive Callbacks

Demonstrates before_model and after_model callbacks.  The scenario:
a content moderation agent where we log every request before it
reaches the model and audit every response after generation.
:link: 03_callbacks
:link-type: doc

How to register lifecycle callbacks with accumulation semantics.
```
```{grid-item-card} Document Processing Pipeline -- Sequential Pipeline

Real-world use case: Contract review system used by legal teams to process
vendor agreements at scale. Extracts key terms, identifies legal risks,
and produces executive summaries -- replacing hours of manual review.

In other frameworks: LangGraph requires a StateGraph with TypedDict state,
3 node functions, and 5 edge declarations (~35 lines). CrewAI needs 3 Agent
objects with role/goal/backstory plus 3 Task objects (~30 lines). Native ADK
needs 3 LlmAgent + 1 SequentialAgent (~20 lines). adk-fluent composes the
same pipeline in a single expression.

Pipeline topology:
    extractor >> risk_analyst >> summarizer
:link: 04_sequential_pipeline
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Market Research Fan-Out -- Parallel FanOut

Demonstrates a ParallelAgent that runs branches concurrently.  The
scenario: a market research system that simultaneously gathers
intelligence from web sources, academic papers, and social media
to produce a comprehensive competitive analysis.

Real-world use case: Competitive intelligence system that simultaneously
gathers data from web, academic, and social media sources. Used by market
research teams to produce comprehensive analysis in minutes instead of days.

In other frameworks: LangGraph requires a StateGraph with fan-out nodes and
edge wiring (~30 lines). CrewAI supports parallel via Crew(process="parallel")
but lacks explicit fan-out composition. adk-fluent uses the | operator for
declarative parallel execution.

Pipeline topology:
    ( web_analyst | academic_analyst | social_analyst )
:link: 05_parallel_fanout
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Essay Refinement Loop -- Loop Agent

Demonstrates a LoopAgent that iterates sub-agents until a maximum
iteration count.  The scenario: an essay refinement workflow where
a critic evaluates the draft and a reviser improves it, repeating
up to 3 times until quality standards are met.

Real-world use case: Essay refinement loop where a writer drafts and a critic
provides feedback iteratively. Used by content teams to improve quality through
structured iteration.

In other frameworks: LangGraph models loops as conditional back-edges in a
StateGraph, requiring a routing function to decide continue vs stop (~25 lines).
adk-fluent uses * N for fixed iterations or * until() for conditional loops.

Pipeline topology:
    ( critic >> reviser ) * 3
:link: 06_loop_agent
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Product Launch Coordinator -- Team Coordinator Pattern

Demonstrates an LLM agent that delegates to specialized sub-agents.
The scenario: a product launch coordinator that routes tasks to
marketing, engineering, and legal teams based on the request.

Pipeline topology:
    launch_coordinator
        |-- marketing
        |-- engineering
        '-- legal
:link: 07_team_coordinator
:link-type: doc

How to compose agents into a sequential pipeline.
```
````

```{toctree}
:hidden:

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

````{grid} 1 2 2 2
---
gutter: 3
---
```{grid-item-card} Quick Code Review -- One-Shot Execution with .ask()

Demonstrates the .ask() convenience method for fire-and-forget
queries.  The scenario: a code review agent that can be invoked
with a single line to get feedback on a code snippet.
No LLM calls are made here -- we only verify builder mechanics.
:link: 08_one_shot_ask
:link-type: doc

How to use one-shot execution for quick queries.
```
```{grid-item-card} Live Translation Pipeline -- Streaming with .stream()

Real-world use case: Real-time translation pipeline for live event
transcription. Transcribes audio, translates, and formats subtitles --
all streaming. Critical for live conferences, court interpreting, and
broadcast captioning where latency matters.

In other frameworks: LangGraph supports streaming via astream_events but
requires graph compilation and manual event filtering. adk-fluent exposes
.stream() directly on any pipeline, making token-by-token output a single
async for loop.
:link: 09_streaming
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} A/B Testing Agent Variants -- Agent Cloning with .clone()

Demonstrates .clone() for creating independent agent variants from
a shared base configuration.  The scenario: A/B testing two customer
support agents -- one using a formal tone and one using a casual tone
-- while sharing the same underlying tool (order lookup).
:link: 10_cloning
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Smoke-Testing a Customer Support Bot -- Inline Testing with .test()

Demonstrates the .test() method for validating agent behavior during
development.  The scenario: a customer support bot that is
smoke-tested inline before deployment to ensure it handles common
queries correctly.  No LLM calls are made here -- we verify that
the builder exposes the test API with the right signature.
:link: 11_inline_testing
:link-type: doc

How to run inline smoke tests on agents.
```
```{grid-item-card} Medical Advice Safety Guardrails -- Guardrails with .guard()

Demonstrates guard mechanisms for agent safety and policy enforcement:
1. Legacy callable guards (backward compatibility)
2. G namespace composable guards (new declarative API)

The scenario: a medical information agent with safety guards that
screen requests and responses for dangerous self-diagnosis or
treatment recommendations, enforce output constraints, and prevent
PII leakage.
:link: 12_guards
:link-type: doc

How to attach guardrails to agent model calls.
```
```{grid-item-card} Customer Support Chat Session with .session()
:link: 13_interactive_session
:link-type: doc

How to manage interactive sessions with agents.
```
```{grid-item-card} Medical Advice Safety Guards -- Guards with .guard()
:link: 12_guardrails
:link-type: doc

How to attach guardrails to agent model calls.
```
````

```{toctree}
:hidden:

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

````{grid} 1 2 2 2
---
gutter: 3
---
```{grid-item-card} Multi-Department Ticket Routing via Dynamic Field Forwarding
:link: 14_dynamic_forwarding
:link-type: doc

How to use dynamic field forwarding.
```
```{grid-item-card} Production Deployment -- to_app() with Middleware Stack

Real-world use case: E-commerce order processing with retry middleware
for transient failures. Production systems need resilience -- this shows
how middleware and pipelines compose to handle validation, payment, and
fulfillment with automatic retries and structured logging.

In other frameworks: LangGraph handles retries via custom node wrappers
that must be applied to each node individually. adk-fluent uses middleware
composition with the M module, applying cross-cutting concerns uniformly
across the entire pipeline.
:link: 15_production_runtime
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} News Analysis Pipeline with Operator Composition: >>, |, *

Pipeline topologies:
    >>  scraper >> analyzer >> reporter
    |   ( politics | markets )
    *   ( draft_writer >> fact_checker ) * 3
:link: 16_operator_composition
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} E-Commerce Order Routing with Deterministic Branching

Real-world use case: E-commerce order routing system that directs orders to
different fulfillment handlers based on order type (standard, express,
international).

In other frameworks: LangGraph uses conditional_edges with a routing function
that returns the target node name. adk-fluent uses Route("key").eq() for
declarative, readable branching without routing functions.

Pipeline topology:
    Route("category")
        ├─ "electronics" -> electronics
        ├─ "clothing"    -> clothing
        ├─ "grocery"     -> grocery
        └─ otherwise     -> general
:link: 17_route_branching
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Multi-Language Support Routing with Dict >> Shorthand
:link: 18_dict_routing
:link-type: doc

How to use dict-based routing.
```
```{grid-item-card} Fraud Detection Pipeline with Conditional Gating
:link: 19_conditional_gating
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Resume Refinement Loop with Conditional Exit

Pipeline topology:
    ( resume_writer >> resume_reviewer ) * until(quality_score == "excellent")
:link: 20_loop_until
:link-type: doc

How to compose agents into a sequential pipeline.
```
````

```{toctree}
:hidden:

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

````{grid} 1 2 2 2
---
gutter: 3
---
```{grid-item-card} Order Processing with Typed State Keys
:link: 21_statekey
:link-type: doc

How to work with state keys and state transforms.
```
```{grid-item-card} Enterprise Agent with Shared Compliance Preset
:link: 22_presets
:link-type: doc

How to define and apply reusable configuration presets.
```
```{grid-item-card} A/B Prompt Testing for Marketing Copy with .with_()
:link: 23_with_variants
:link-type: doc

How to run inline smoke tests on agents.
```
```{grid-item-card} Domain Expert Agent via @agent Decorator
:link: 24_agent_decorator
:link-type: doc

How to use the agent decorator pattern.
```
```{grid-item-card} Introspection & Debugging -- validate(), explain(), inspect()

Demonstrates the introspection methods that help debug and understand
agent configurations before deployment. The scenario: a compliance
team reviewing an insurance claims pipeline to verify correct wiring
before going live.
:link: 25_validate_explain
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Deployment Pipeline: Serialize Agent Configs with to_dict and to_yaml
:link: 26_serialization
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Senior Architect Delegates to Junior Specialists (LLM-Driven Routing)
:link: 27_agent_tool_pattern
:link-type: doc

How to delegate tasks between agents.
```
```{grid-item-card} Investment Analysis Pipeline: Full Expression Language in Production

Real-world use case: Investment analysis pipeline for portfolio managers.
Classifies assets, routes to specialized analysts, and performs quality
review before delivery. Replaces manual triage and review cycles that
typically span multiple teams and days of back-and-forth.

In other frameworks: LangGraph requires StateGraph with conditional_edges
for routing (~50 lines). adk-fluent uses Route() and >> to express the
same topology declaratively.

Pipeline topology:
    asset_classifier
        >> Route("asset_class")
            ├─ "equity"       -> equity_screener
            ├─ "fixed_income" -> credit_analyst >> rate_modeler
            └─ "alternative"  -> ( quant_modeler | market_sentiment ) >> risk_aggregator
        >> ( portfolio_reviewer >> analysis_refiner ) * until(approved)
        >> report_generator  [gated: only if approved]
:link: 28_real_world_pipeline
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} ETL Pipeline: Plain Functions as Data Cleaning Steps (>> fn)
:link: 29_function_steps
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Customer Onboarding: Conditional Loops with * until(pred) Operator

Real-world use case: Customer onboarding flow that collects required information
iteratively until all fields are complete. Used by fintech and insurance
applications for guided data collection.

In other frameworks: LangGraph requires conditional_edges with a custom routing
function to implement loop-until semantics (~30 lines). adk-fluent uses
* until(predicate) for declarative conditional loops.
:link: 30_until_operator
:link-type: doc

How to create looping agent workflows.
```
```{grid-item-card} Structured Invoice Parsing: Typed Output Contracts with @ Operator
:link: 31_typed_output
:link-type: doc

How to use operator syntax for composing agents.
```
```{grid-item-card} Knowledge Retrieval: Primary API + Fallback Search with // Operator

Pipeline topologies:
    //  vector_db // fulltext_search          (two-way fallback)
    //  internal_kb // web_search // expert   (three-way cascade)

    RAG pipeline:
        query_rewriter >> ( vector_db // fulltext ) >> answer_generator
:link: 32_fallback_operator
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Research Data Pipeline: State Transforms with S Factories

Pipeline topology:
    data_extractor
        >> S.pick("clinical_findings", "lab_results")
        >> S.rename(clinical_findings="analysis_input")
        >> S.default(confidence_interval=0.95)
        >> statistical_analyzer

    Research pipeline:
        ( literature_agent | trial_agent )
            >> S.merge(into="combined_evidence")
            >> S.default(...)
            >> report_writer
            >> S.compute(word_count=...)
:link: 33_state_transforms
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Code Review Pipeline -- Expression Algebra in Practice

Demonstrates how composition operators (>>, |, @, //) combine naturally
in a real-world code review system. A diff parser extracts changes,
parallel reviewers check style, security, and logic independently,
then findings are aggregated into a structured verdict.

Real-world use case: Automated code review pipeline that runs style, security,
and logic reviewers in parallel, then merges findings. Used by engineering teams
as a pre-merge quality gate.

In other frameworks: LangGraph models this as a fan-out subgraph with merge
node (~45 lines). adk-fluent composes parallel reviewers with | and sequences
with >> in a single expression.

Pipeline topology:
    diff_parser
        >> ( style_checker | security_scanner | logic_reviewer )
        >> ( finding_aggregator @ ReviewVerdict // backup_aggregator @ ReviewVerdict )
:link: 34_full_algebra
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} ML Inference Monitoring: Performance Tap for Pure Observation
:link: 35_tap_observation
:link-type: doc

How to use ml inference monitoring: performance tap for pure observation with the fluent API.
```
```{grid-item-card} Analytics Data Quality: State Contract Assertions with expect()
:link: 36_expect_assertions
:link-type: doc

How to work with state keys and state transforms.
```
```{grid-item-card} Mock Testing: Customer Onboarding Pipeline with Deterministic Mocks
:link: 37_mock_testing
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Retry If: API Integration Agent That Retries on Transient Failures
:link: 38_loop_while
:link-type: doc

How to use retry if: api integration agent that retries on transient failures with the fluent API.
```
```{grid-item-card} Map Over: Batch Processing Customer Feedback with Iteration
:link: 39_map_over
:link-type: doc

How to use map over: batch processing customer feedback with iteration with the fluent API.
```
```{grid-item-card} Timeout: Real-Time Trading Agent with Strict Execution Deadline
:link: 40_timeout
:link-type: doc

How to use timeout: real-time trading agent with strict execution deadline with the fluent API.
```
```{grid-item-card} Gate: Legal Document Review with Human Approval
:link: 41_gate_approval
:link-type: doc

How to use gate: legal document review with human approval with the fluent API.
```
```{grid-item-card} Race: Fastest-Response Search Across Multiple Providers

Pipeline topology:
    race( westlaw_search, lexis_search )    -- first to finish wins

    Research pipeline:
        query_classifier >> race( federal_search, state_search ) >> citation_formatter
:link: 42_race
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Primitives Showcase: E-Commerce Order Pipeline Using All Primitives
:link: 43_primitives_showcase
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Senior Architect Delegates to Junior Specialists (LLM-Driven Routing)
:link: 27_delegate_pattern
:link-type: doc

How to delegate tasks between agents.
```
```{grid-item-card} Retry If: API Integration Agent That Retries on Transient Failures
:link: 38_retry_if
:link-type: doc

How to use retry if: api integration agent that retries on transient failures with the fluent API.
```
````

```{toctree}
:hidden:

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

````{grid} 1 2 2 2
---
gutter: 3
---
```{grid-item-card} Pipeline Optimization with IR -- Inspecting, Compiling, and Selecting Backends

Demonstrates to_ir() for pipeline analysis, to_app() for production
compilation, to_mermaid() for architecture documentation, and the new
compile layer for backend-selectable execution. The scenario: a mortgage
approval pipeline where the platform team inspects the agent graph for
optimization before deploying to different execution backends.
:link: 44_ir_and_backends
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Middleware: Production Middleware Stack for a Healthcare API Agent
:link: 45_middleware
:link-type: doc

How to configure agents for production runtime.
```
```{grid-item-card} Contracts and Testing: Medical Imaging Pipeline with Strict Data Contracts
:link: 46_contracts_and_testing
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Dependency Injection: Multi-Environment Deployment (Dev/Staging/Prod)
:link: 47_dependency_injection
:link-type: doc

How to use dependency injection: multi-environment deployment (dev/staging/prod) with the fluent API.
```
```{grid-item-card} Architecture Documentation -- Mermaid Diagrams from Live Code

Demonstrates to_mermaid() for generating architecture diagrams that
stay in sync with code. The scenario: a DevOps team documenting their
incident response platform's agent topology for runbooks and onboarding.
:link: 48_visualization
:link-type: doc

How to build a team of agents with a coordinator.
```
````

```{toctree}
:hidden:

44_ir_and_backends
45_middleware
46_contracts_and_testing
47_dependency_injection
48_visualization
```

## v5.1 Features

Context engineering, visibility, memory, and contract verification.

````{grid} 1 2 2 2
---
gutter: 3
---
```{grid-item-card} Context Engineering: Customer Support Pipeline

Real-world use case: Customer support pipeline with context-aware routing.
Uses context engineering to control what each agent sees -- stateless
classifiers see only the current message while specialists see full history.

In other frameworks: LangGraph manages context through TypedDict state slicing,
requiring manual state key management. adk-fluent uses the C module (C.none(),
C.from_state(), C.user_only()) for declarative context control.

Key design principle: data-injection transforms (C.from_state, C.template,
C.notes) are neutral — they inject state without suppressing conversation
history. History-filtering transforms (C.none, C.window, C.user_only)
explicitly control visibility. Compose them to get both::

    C.none() | C.from_state("key")   # inject state, no history
    C.from_state("key")              # inject state, keep history
    C.window(n=3) | C.from_state("key")  # last 3 turns + state
:link: 49_context_engineering
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Capture and Route: IT Helpdesk Triage

Real-world use case: IT helpdesk ticket capture and routing system. Captures
incoming messages into state, classifies urgency, and routes to appropriate
support tiers.

In other frameworks: LangGraph requires custom state capture via TypedDict
updates and conditional_edges for routing. adk-fluent uses S.capture() for
state injection and Route() for declarative branching.

Pipeline topology:
    S.capture("ticket")
        >> triage [save_as: priority]
        >> Route("priority")
            ├─ "p1" -> incident_commander
            ├─ "p2" -> senior_support
            └─ else -> support_bot
:link: 50_capture_and_route
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Visibility: Content Review Pipeline
:link: 51_visibility_policies
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Contract Checking: Catch Data Flow Bugs Before Runtime
:link: 52_contract_checking
:link-type: doc

How to configure agents for production runtime.
```
```{grid-item-card} Insurance Claim Processing: Structured Data Pipelines

Demonstrates structured output schemas and the @ operator for typed
agent responses.  The scenario: an insurance company processes claims
through a pipeline -- first ingesting claim details into a structured
form, then assessing risk, then summarizing the outcome.

Real-world use case: Insurance claim processing pipeline with typed data flow.
Extracts claim details into structured schemas, validates coverage, and
produces typed assessment reports.

In other frameworks: LangGraph uses Pydantic with output_parser on chain calls.
CrewAI uses output_pydantic on Task objects. adk-fluent uses the @ operator for
inline schema binding on any agent.
:link: 53_structured_schemas
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Customer Service Hub: Agent Transfer Control

Demonstrates controlling how agents transfer between each other using
disallow_transfer_to_parent, disallow_transfer_to_peers, and the
.isolate() convenience method.  The scenario: a customer service system
where a coordinator routes to specialist agents that must complete their
task before returning control.
:link: 54_transfer_control
:link-type: doc

How to build a team of agents with a coordinator.
```
```{grid-item-card} Deep Research Agent -- Gemini Deep Research / Perplexity Clone

Demonstrates building a multi-stage research pipeline inspired by
Gemini's Deep Research feature and Perplexity. A query is decomposed
into sub-questions, searched in parallel across multiple sources,
synthesized, quality-reviewed in a loop, and formatted as a report.

Real-world use case: Deep research agent inspired by Gemini Deep Research and
Perplexity. Decomposes queries, searches multiple sources in parallel,
synthesizes with quality review loop, and produces typed reports. Used by
analysts for comprehensive research briefs.

In other frameworks: LangGraph requires StateGraph with conditional back-edges
for the quality loop, fan-out nodes for parallel search, and Pydantic
integration for typed output (~60 lines of graph wiring). adk-fluent expresses
the entire topology -- parallel search, quality loop, typed output -- in one
expression using >>, |, *, and @.

Pipeline topology:
    query_analyzer
        >> ( web_searcher | academic_searcher | news_searcher )
        >> synthesizer
        >> ( quality_reviewer >> revision_agent ) * until(score >= 0.85)
        >> report_writer @ ResearchReport

Uses: >>, |, *, @, S.*, C.*, save_as, loop_until
:link: 55_deep_research
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Customer Support Triage -- ADK-Samples Inspired Multi-Tier Support

Demonstrates building a customer support triage system inspired by
real call center architectures and Google's ADK agent samples. Uses
state capture, context engineering, routing, and escalation gates.

Real-world use case: Multi-tier IT helpdesk triage system inspired by real
call center architectures and Google's ADK agent samples. Classifies tickets
by intent and routes to billing, technical, account, or general support
specialists with satisfaction monitoring and escalation.

In other frameworks: LangGraph requires a StateGraph with conditional_edges
for intent routing, custom node functions per handler, and manual state
management (~50 lines). CrewAI handles routing implicitly through LLM
delegation, lacking deterministic control. adk-fluent uses Route() with
explicit .eq() branches for deterministic, testable routing.

Pipeline topology:
    S.capture("customer_message")
        >> intent_classifier [C.none, save_as: intent]
        >> Route("intent")
            ├─ "billing"   -> billing_specialist
            ├─ "technical" -> tech_support
            ├─ "account"   -> account_manager
            └─ otherwise   -> general_support
        >> satisfaction_monitor
        >> gate(resolved == "no") -> escalate

Uses: S.capture, C.none, C.from_state, C.user_only, Route, gate, save_as

Note: C.from_state() is a pure data-injection transform — it injects state
values without suppressing conversation history. To suppress history AND
inject state, compose: C.none() | C.from_state("key").
:link: 56_customer_support_triage
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Code Review Agent -- Gemini CLI / GitHub Copilot Inspired

Demonstrates building an automated code review agent inspired by
Gemini CLI's code review and GitHub Copilot's review features.
Uses parallel fan-out for concurrent analysis, typed output for
structured findings, and conditional gating.

Real-world use case: Automated code review agent inspired by Gemini CLI and
GitHub Copilot code review. Analyzes code for style, bugs, and security
issues, then produces structured feedback.

In other frameworks: LangGraph and CrewAI both require separate agent/node
definitions for each review dimension plus aggregation logic. adk-fluent
composes parallel reviewers with | and sequences with >> for a concise review
pipeline.

Pipeline topology:
    diff_parser [save_as: parsed_changes]
        >> ( style_checker | security_scanner | logic_reviewer )
        >> tap(log)
        >> finding_aggregator @ ReviewResult
        >> comment_writer [gated: findings_count > 0]

Uses: >>, |, @, proceed_if, save_as, tap
:link: 57_code_review_agent
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Multi-Tool Task Agent -- Manus / OpenAI Agents SDK Inspired

Demonstrates building a versatile task agent with multiple tools,
safety guardrails, and dependency injection -- inspired by Manus AI's
tool-using agent and the OpenAI Agents SDK patterns.

Pipeline topology:
    task_agent [tools: search, calc, read_file] [guardrail] [inject: api_key]
        >> verifier [C.from_state("task_result")]

Uses: .tool(), .guard(), .inject(), .transfer_to(), .context()
:link: 58_multi_tool_agent
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Dispatch & Join: Fire-and-Continue Background Execution

Demonstrates the dispatch/join primitives for non-blocking background
agent execution.  Unlike FanOut (which blocks until all complete) or
race (which takes first and cancels rest), dispatch fires agents as
background tasks and lets the pipeline continue immediately.

Pipeline topology:
    writer
        >> dispatch(email_sender, seo_optimizer)   -- fire-and-continue
        >> formatter                                -- runs immediately
        >> join()                                   -- barrier: wait for all
        >> publisher

    Selective join:
        writer >> dispatch(email, seo) >> formatter >> join("seo") >> publisher >> join("email")

Key concepts:
  - dispatch(*agents): launches agents as asyncio.Tasks, pipeline continues
  - join(): barrier that waits for dispatched tasks to complete
  - join("name"): selective join -- wait for specific tasks only
  - .dispatch(name="x"): method form for any builder
  - Named tasks, callbacks, timeout, progress streaming
:link: 59_dispatch_join
:link-type: doc

How to register lifecycle callbacks with accumulation semantics.
```
```{grid-item-card} StreamRunner: Continuous Userless Agent Execution

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
  - StreamStats: live counters (processed, errors, throughput)
:link: 60_stream_runner
:link-type: doc

How to register lifecycle callbacks with accumulation semantics.
```
```{grid-item-card} Dispatch-Aware Middleware: Observability for Background Execution

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
  - task_budget(): configure max concurrent dispatch tasks
:link: 61_dispatch_middleware
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} M Module: Fluent Middleware Composition

Demonstrates the M module -- a fluent composition surface for middleware,
consistent with P (prompts), C (context), S (state transforms).

Key concepts:
  - M.retry(), M.log(), M.cost(), M.latency(): built-in factories
  - M.topology_log(), M.dispatch_log(): topology and dispatch observability
  - | operator: compose middleware chains (M.retry(3) | M.log())
  - M.scope("agent", mw): restrict middleware to specific agents
  - M.when(condition, mw): conditional middleware (string, callable, PredicateSchema)
  - M.before_agent(fn): single-hook shortcut for quick observability
  - MComposite: composable chain class with to_stack() for flattening
:link: 62_m_module_composition
:link-type: doc

How to use operator syntax for composing agents.
```
```{grid-item-card} TraceContext and Topology Hooks: Cross-Cutting Observability

Demonstrates the TraceContext per-invocation state bag and the
topology hooks protocol for observing workflow structure.

Key concepts:
  - TraceContext: request_id, elapsed, key-value store per invocation
  - TopologyHooks protocol: on_loop_iteration, on_fanout_start/complete,
    on_route_selected, on_fallback_attempt, on_timeout
  - DispatchDirective: cancel dispatches or inject state
  - LoopDirective: break out of loops from middleware
  - TopologyLogMiddleware: built-in structured topology logging
  - _trace_context ContextVar: access from any hook
:link: 63_trace_context_topology
:link-type: doc

How to run agents in parallel using FanOut.
```
```{grid-item-card} MiddlewareSchema: Typed Middleware State Declarations

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
  - M.when(PredicateSchema, mw): state-aware conditional middleware
:link: 64_middleware_schema
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} Built-in Middleware: CostTracker, LatencyMiddleware, TopologyLogMiddleware

Demonstrates the built-in middleware classes for production observability
and the error boundary mechanism that prevents middleware failures from
crashing the pipeline.

Key concepts:
  - CostTracker: token usage accumulation via after_model
  - LatencyMiddleware: per-agent timing via TraceContext
  - TopologyLogMiddleware: structured logging for topology events
  - Error boundary: middleware exceptions caught, logged, and reported
  - on_middleware_error: notification hook for other middleware
  - Custom middleware with typed MiddlewareSchema
:link: 65_builtin_middleware
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} T Module: Fluent Tool Composition and Dynamic Loading

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
  - SearchToolset: two-phase discovery/execution
:link: 66_t_module_tools
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} G Module: Declarative Guard Composition

Demonstrates the G module -- a fluent composition surface for safety,
validation, and policy guards. Guards compile into before/after model
callbacks automatically.

Key concepts:
  - GGuard: single guard unit with phase and compile function
  - GComposite: composable chain with | operator
  - G.json(), G.length(), G.regex(): structural guards
  - G.output(), G.input(): schema validation guards
  - G.pii(), G.toxicity(), G.topic(): content safety guards
  - G.budget(), G.rate_limit(), G.max_turns(): policy guards
  - G.grounded(), G.hallucination(): grounding guards
  - G.when(predicate, guard): conditional guards
  - Provider protocols: PIIDetector, ContentJudge
:link: 67_g_module_guards
:link-type: doc

How to register lifecycle callbacks with accumulation semantics.
```
```{grid-item-card} Engine Selection -- Backend-Selectable Agent Execution

The same agent definition can run on different execution backends:
ADK (default), asyncio (zero-dependency), or Temporal (durable).
Use .engine() per-agent or configure() globally. The agent logic
stays identical -- only the execution engine changes.

This is the core concept of the five-layer architecture:
  Definition → Compile → Runtime → Backend → Compute
:link: 68_engine_selection
:link-type: doc

How to configure agents for production runtime.
```
```{grid-item-card} Asyncio Backend -- Zero-Dependency IR Interpreter

The asyncio backend executes agent pipelines directly using Python
asyncio — no ADK, no Temporal, no external dependencies. It interprets
the IR tree and calls a ModelProvider for LLM invocations.

Use cases: testing without API keys, lightweight deployments, custom
model integrations (local models, OpenAI, Anthropic), and proving
that the five-layer architecture works with any backend.
:link: 69_asyncio_backend
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} A2UI Basics: Declarative Agent-to-UI Composition

Demonstrates the UI namespace for building rich agent UIs declaratively.

Key concepts:
  - UIComponent: frozen dataclass with composition operators
  - UI.text(), UI.button(), UI.text_field(): component factories
  - UI.bind(), UI.required(): data binding and validation
  - UI.surface(): named UI surface (compilation root)
  - compile_surface(): nested Python tree → flat A2UI JSON
  - Operators: | (Row), >> (Column), + (sibling group)
:link: 70_a2ui_basics
:link-type: doc

How to use operator syntax for composing agents.
```
```{grid-item-card} Temporal Backend -- Durable Execution for Agent Pipelines

The Temporal backend compiles IR nodes to Temporal workflows and
activities. If a 10-step pipeline crashes at step 7, Temporal replays
steps 1-6 from cached results (zero LLM cost) and re-executes only
step 7+.

Key mappings:
  AgentNode     → Activity  (non-deterministic: LLM call, cached on replay)
  SequenceNode  → Workflow  (deterministic orchestration)
  ParallelNode  → Workflow  (concurrent activities)
  LoopNode      → Workflow  (iteration with checkpoints)
  TransformNode → Inline    (deterministic, replayed from history)
  GateNode      → Signal    (human-in-the-loop approval)
  DispatchNode  → Child WF  (durable background task)

Usage requires: pip install adk-fluent[temporal]
:link: 70_temporal_backend
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} A2UI Agent Integration: Wiring UI to Agents (the wedge devex)

Demonstrates the ergonomic ``Agent.ui()`` overload introduced in the A2UI
devex wedge:

- ``.ui(spec)``                — declarative surface (prompt-only, no tool wiring)
- ``.ui(llm_guided=True)``     — auto-wires ``T.a2ui()`` + ``G.a2ui()`` for you
- ``.ui(spec, log=True)``      — also auto-wires ``M.a2ui_log()``
- ``.ui(spec, validate=False)``— skip ``surface.validate()`` at build time

Plus the schema-driven helpers:

- ``UI.form(MyPydanticModel)`` — generate a typed form from a BaseModel
- ``UI.paths(MyPydanticModel)``— typed two-way binding proxy
:link: 71_a2ui_agent_integration
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Compute Layer -- Pluggable Model, State, Tool, and Artifact Providers

The compute layer decouples WHERE work runs from HOW it's orchestrated.
Four independent protocols let you swap infrastructure without changing
agent logic:

  ModelProvider   → LLM backend (Gemini, OpenAI, local, mock)
  StateStore      → Session persistence (memory, Redis, SQL)
  ToolRuntime     → Tool execution sandbox
  ArtifactStore   → Binary artifact storage (files, GCS, S3)

Use ComputeConfig to bundle providers, then attach via .compute()
on any builder or configure() globally.
:link: 71_compute_layer
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} A2UI Operators: UI Composition with |, >>, +

Demonstrates declarative UI layout using Python operators.

Key concepts:
  - | operator: horizontal Row layout
  - >> operator: vertical Column layout
  - + operator: sibling group (UIGroup)
  - Nesting: combine operators for complex layouts
  - compile_surface(): nested tree → flat A2UI JSON
:link: 72_a2ui_operators
:link-type: doc

How to use operator syntax for composing agents.
```
```{grid-item-card} A2UI LLM-Guided Mode: Let the Agent Design the UI

Demonstrates LLM-guided UI mode — the agent has full control over the A2UI
surface via the ``a2ui-agent`` toolset and a catalog schema injected into
the prompt.

The wedge ergonomics:

- ``Agent.ui(llm_guided=True)``  — auto-wires ``T.a2ui()`` + ``G.a2ui()`` and
                                    promotes the spec to ``UI.auto()``.
- ``UI.auto()``                  — explicit form for those who want the marker.
- ``T.a2ui()``                   — raises ``A2UINotInstalled`` when the
                                    optional ``a2ui-agent`` package is missing.
:link: 73_a2ui_llm_guided
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} A2UI Pipeline: UI in Multi-Agent Pipelines

Demonstrates using S.to_ui() and S.from_ui() to bridge state data
between agents and A2UI surfaces.

Key concepts:
  - S.to_ui(): bridge agent state → A2UI data model
  - S.from_ui(): bridge A2UI data model → agent state
  - M.a2ui_log(): log A2UI surface operations
  - C.with_ui(): include UI surface state in context
:link: 74_a2ui_pipeline
:link-type: doc

How to compose agents into a sequential pipeline.
```
````

```{toctree}
:hidden:

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
67_g_module_guards
68_engine_selection
69_asyncio_backend
70_a2ui_basics
70_temporal_backend
71_a2ui_agent_integration
71_compute_layer
72_a2ui_operators
73_a2ui_llm_guided
74_a2ui_pipeline
```

## Skills & Harness

Declarative agent packages from SKILL.md files and autonomous coding runtimes with the H namespace. Two of adk-fluent's [three development pathways](../../user-guide/index.md#three-pathways).

````{grid} 1 2 2 2
---
gutter: 3
---
```{grid-item-card} Prefect Backend -- Flow Orchestration for Agent Pipelines

The Prefect backend compiles IR nodes to Prefect flows and tasks.
Task results are cached by Prefect, so on retry, completed tasks
return their cached results instead of re-executing (reducing LLM costs).

Key mappings:
  AgentNode     → Task     (non-deterministic: LLM call, cached on retry)
  SequenceNode  → Flow     (sequential task orchestration)
  ParallelNode  → Flow     (concurrent .submit() + wait)
  LoopNode      → Flow     (iteration in flow body)
  TransformNode → Inline   (pure function, no caching)
  GateNode      → Pause    (pause_flow_run for HITL)
  MapOverNode   → task.map (parallel map over list)

Usage requires: pip install adk-fluent[prefect]
:link: 75_prefect_backend
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} DBOS Backend -- Durable Functions for Agent Pipelines

The DBOS backend compiles IR nodes to DBOS durable workflows and steps
backed by PostgreSQL. Steps (LLM calls) are durably recorded -- on
recovery, completed steps return their cached results (zero LLM cost).

Key mappings:
  AgentNode     → @DBOS.step()    (non-deterministic, durably recorded in PG)
  SequenceNode  → @DBOS.workflow() (deterministic, replayed from DB log)
  ParallelNode  → asyncio.gather   (concurrent steps in workflow)
  LoopNode      → for loop         (iteration in workflow body)
  TransformNode → Inline           (deterministic, replayed)
  GateNode      → DBOS.recv()      (external signal for HITL)
  DispatchNode  → DBOS.start_workflow() (child workflow)

Key difference from Temporal: DBOS requires only PostgreSQL (no separate
server process). Lighter infrastructure, similar durability guarantees.

Usage requires: pip install adk-fluent[dbos]
:link: 76_dbos_backend
:link-type: doc

How to compose agents into a sequential pipeline.
```
```{grid-item-card} A2UI Dynamic: LLM-Driven UI Generation

Demonstrates the core A2UI value proposition: the LLM itself designs
interactive UI surfaces based on user intent. .ui(UI.auto()) handles
everything — it attaches the SendA2uiToClientToolset which injects
the full A2UI JSON Schema at LLM request time and gives the LLM a
send_a2ui_json_to_client tool.

Key concepts:
  - .ui(UI.auto()): one-line A2UI setup (schema + toolset)
  - SendA2uiToClientToolset injects schema via process_llm_request
  - The LLM generates valid A2UI JSON — no Python UI construction
  - Domain tools provide data, the LLM designs the presentation
:link: 77_a2ui_dynamic
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Skill-Based Agents -- Composable Skills from SKILL.md Files

Skills are the 100x multiplier for agent development. Instead of writing
Python agent code, you declare agent topologies in YAML inside SKILL.md
files and compose them with the same operators you already know.

A single SKILL.md file serves four purposes:
  1. Documentation for coding agents (Claude Code, Gemini CLI)
  2. Progressive disclosure for ADK SkillToolset (L1/L2/L3)
  3. Executable agent graph for adk-fluent runtime
  4. Publishable artifact via npx skills

Skill topology (research_pipeline):
    researcher >> fact_checker >> synthesizer

Skill topology (code_reviewer):
    (analyzer | style_checker | security_auditor) >> summarizer
:link: 77_skill_based_agents
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Agent Collaboration Mechanisms — Six Ways Agents Work Together

Demonstrates all six collaboration primitives in adk-fluent:

1. Transfer — Agent A hands off to Agent B (LLM-routed or deterministic)
2. Tool-call — Agent A calls Agent B as a function, stays in control
3. Shared state — Agents read/write a common key-value store
4. Interrupt — External signals stop or reroute a running agent
5. Notify — Fire-and-forget: send without waiting
6. Observe — Watch agent output and react to state changes

Each pattern maps to a real-world collaboration analogy:
  Transfer = handing off a customer to another department
  Tool-call = asking a colleague a question and waiting for the answer
  Shared state = whiteboard in a shared office
  Interrupt = tapping someone on the shoulder while they're working
  Notify = sending a Slack message
  Observe = monitoring a live dashboard
:link: 78_collaboration_mechanisms
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Skill-Powered Harness — Building a CodAct Coding Agent

Demonstrates how to build a Claude-Code-like coding agent harness using
adk-fluent's three-layer skill architecture:

  L1: .use_skill()  — expertise loading (SKILL.md body → static_instruction)
  L2: T.skill()     — progressive disclosure (SkillToolset, LLM loads on demand)
  L3: Skill()       — recipe (pre-composed agent workflow from SKILL.md)

Plus the H namespace for harness runtime primitives:

  H.workspace()     — sandboxed file/shell tools (read, edit, write, glob, grep, bash)
  H.ask_before()    — permission policies (which tools need approval)
  H.auto_allow()    — auto-approved tools
  H.workspace_only()— sandbox policies (restrict fs to workspace)

Architecture:
    ┌──────────────────────────────────────┐
    │          Agent + Skills              │
    │  .use_skill("code-review/")         │  ← L1: expertise (static, cached)
    │  .use_skill("python-best-practices/")│
    │  .instruct("Review the code.")       │  ← per-task instruction
    │  .tools(H.workspace("/project"))     │  ← sandboxed tools
    │  .harness(permissions=..., sandbox=.)│  ← permission + sandbox
    └──────────────────────────────────────┘
:link: 78_harness_and_skills
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Gemini CLI / Claude Code Clone — Production Coding Agent Harness

Builds a fully-functional autonomous coding runtime using adk-fluent's
harness primitives. This is the proof: the same framework that builds
single-purpose agents can build a Claude-Code-class system.

Architecture (5 layers):

    ┌──────────────────────────────────────────────────────────┐
    │  5. RUNTIME         REPL, slash commands, interrupt      │
    │  4. OBSERVABILITY   EventBus, tape, hooks, renderer      │
    │  3. SAFETY          Permissions, sandbox, budgets         │
    │  2. TOOLS           Workspace, web, git, processes, MCP   │
    │  1. INTELLIGENCE    Agent + skills + manifold             │
    └──────────────────────────────────────────────────────────┘

Every test builds a real, wirable harness component. Together they
compose into the complete system shown in test_full_coding_agent().

Run: uv run pytest examples/cookbook/79_coding_agent_harness.py -v
:link: 79_coding_agent_harness
:link-type: doc

How to attach tools to an agent using the fluent API.
```
```{grid-item-card} Signals + Reactor — reactive state over the durable tape.

Shows the three reactive primitives added in Phase F / Phase G / auto-tracking:

1. :class:`Signal` — typed state cell with version tracking. Mutations
   emit :class:`SignalChanged` on the ambient :class:`EventBus` (which
   in turn lands on the :class:`SessionTape`).
2. :class:`Reactor` — cursor-following scheduler. Registered rules fire
   when their :class:`SignalPredicate` matches a change on the tape.
3. ``computed(name, fn)`` — derived signal that auto-tracks reads of
   other signals and re-runs on any dep change.

Run: ``uv run pytest examples/cookbook/80_reactor_basic.py -v``
:link: 80_reactor_basic
:link-type: doc

How to manage interactive sessions with agents.
```
```{grid-item-card} R + Agent.on() — declarative reactors, zero ceremony.

The 0.17.0 reactor refresh makes signals and rules a first-class part
of the fluent builder surface. Before, wiring a reactor required
hand-building every object in sequence::

    bus = H.event_bus()
    tape = bus.tape()
    temp = Signal("temp", 72, bus=bus)
    reactor = Reactor(tape, bus=bus)
    reactor.when(temp.rising.where(lambda v, _: v > 90), my_handler, priority=10)
    await reactor.run()

Now::

    temp = R.signal("temp", 72)

    cooler = (
        Agent("cooler", "gemini-2.5-flash")
        .instruct("Plan a cool-down.")
        .on(R.rising("temp").where(lambda v, _: v > 90), priority=10)
    )

    reactor = R.compile(cooler, tape=tape, bus=bus)
    await reactor.run()

Run: ``uv run pytest examples/cookbook/81_reactor_native.py -v``
:link: 81_reactor_native
:link-type: doc

How to run inline smoke tests on agents.
```
````

```{toctree}
:hidden:

75_prefect_backend
76_dbos_backend
77_a2ui_dynamic
77_skill_based_agents
78_collaboration_mechanisms
78_harness_and_skills
79_coding_agent_harness
80_reactor_basic
81_reactor_native
```

```{toctree}
:hidden:

recipes-by-use-case
```
