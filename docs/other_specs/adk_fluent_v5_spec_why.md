# SPEC v5 — Appendix F: Why This Exists

## What adk-fluent v5 Actually Buys You — With Proof

This appendix makes the case for every major v5 feature by putting native ADK code next to adk-fluent code and asking one question: **does this remove real pain, or is it engineering tourism?**

Some features clear the bar decisively. Others need honest caveats. One (dependency injection) we argue against.

______________________________________________________________________

## 1. The Composition Problem: Where ADK's Pythonic Simplicity Breaks Down

ADK's single-agent story is excellent. Define an agent, give it tools, run it. The Google Developers Blog calls it "Pythonic simplicity" and they're right — for one agent:

```python
# ADK: One agent. Clean. No complaints.
from google.adk.agents import Agent

root_agent = Agent(
    model="gemini-2.5-flash",
    name="support_agent",
    instruction="Help customers with billing questions.",
    tools=[lookup_account, create_ticket],
)
```

The pain starts when you compose agents. Here's a real pattern from ADK's own documentation — a code pipeline with write → review → refactor:

```python
# ADK: Three agents in sequence. 38 lines. Mostly boilerplate.
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.llm_agent import LlmAgent

code_writer_agent = LlmAgent(
    name="CodeWriterAgent",
    model="gemini-2.5-flash",
    instruction="""You are a Python Code Generator.
        Based only on the user's request, write Python code.
        Output only the code block.""",
    description="Writes initial Python code based on a specification.",
    output_key="generated_code",
)

code_reviewer_agent = LlmAgent(
    name="CodeReviewerAgent",
    model="gemini-2.5-flash",
    instruction="""You are an expert Code Reviewer.
        Review the code: {generated_code}
        Provide feedback.""",
    description="Reviews generated code and provides feedback.",
    output_key="review_comments",
)

code_refactorer_agent = LlmAgent(
    name="CodeRefactorerAgent",
    model="gemini-2.5-flash",
    instruction="""Improve the code based on review.
        Original: {generated_code}
        Comments: {review_comments}""",
    description="Refactors code based on review comments.",
    output_key="refactored_code",
)

code_pipeline_agent = SequentialAgent(
    name="CodePipelineAgent",
    sub_agents=[code_writer_agent, code_reviewer_agent, code_refactorer_agent],
    description="Executes a sequence of code writing, reviewing, and refactoring.",
)

root_agent = code_pipeline_agent
```

```python
# adk-fluent: Same pipeline. 7 lines. Same ADK objects at runtime.
from adk_fluent import Agent

root_agent = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write Python code.").outputs("generated_code")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review: {generated_code}").outputs("review_comments")
    >> Agent("refactorer").model("gemini-2.5-flash").instruct("Refactor: {generated_code} per {review_comments}")
).build()
```

This isn't syntactic sugar. The `>>` operator produces a `SequentialAgent` with the same `sub_agents` list, the same `output_key` bindings, the same `{placeholder}` state injection. `adk web` sees identical agent trees. The difference is that the pipeline's *shape* — "these three steps happen in order, passing state through these keys" — is visible in the code's *structure* instead of buried in constructor arguments.

**The win scales with complexity.** Three agents, the ADK version is tolerable. Ten agents with parallel branches, routing, and loops? The ADK version becomes a wall of constructors where the topology vanishes. The fluent version stays readable because topology *is* the syntax.

______________________________________________________________________

## 2. State: The Largest Source of Runtime Failures

ADK's state system is a dictionary with string keys and scope prefixes (`app:`, `user:`, `temp:`). It's flexible. It's also where most production pipelines break, because nothing prevents this:

```python
# ADK: The bugs that eat production teams alive

# Bug 1: Misspelled key (silent failure — reads None, agent hallucinates)
ctx.state["inten"] = "billing"  # Should be "intent"

# Bug 2: Type mismatch (classifier writes string, resolver parses as float)
ctx.state["confidence"] = "0.85"  # String, not float
# ... three agents later ...
if float(ctx.state["confidence"]) > 0.8:  # Works! Until someone writes "high"

# Bug 3: Scope confusion (temp vanishes between invocations)
ctx.state["preference"] = "dark_mode"         # Session-scoped (persisted)
ctx.state["temp:preference"] = "dark_mode"    # Temp (gone next invocation)
# Which one did you mean? Both compile. Both run. One loses data.

# Bug 4: Key collision in composed pipelines
# Team A's agent writes ctx.state["result"]
# Team B's agent also writes ctx.state["result"]
# Whoever runs second silently overwrites.
```

None of these fail at definition time. They all surface at runtime, usually in production, usually at 2 AM. The ADK documentation itself warns: "directly modifying the state on a Session object you retrieve from the SessionService ... bypasses the ADK's event tracking and can lead to lost data."

**v5's `StateSchema` catches all four at build time:**

```python
# adk-fluent v5: Every one of these bugs becomes a build-time error

from adk_fluent.state import StateSchema, UserScoped, Temp
from typing import Annotated

class BillingState(StateSchema):
    intent: str                                        # Session-scoped (default)
    confidence: float                                  # Typed as float
    user_tier: Annotated[str, UserScoped]               # Explicitly cross-session
    scratch: Annotated[dict, Temp]                      # Explicitly ephemeral

# In a tool or callback:
def create_ticket(query: str, tool_context):
    state = BillingState.bind(tool_context)
    state.inten = "billing"        # → AttributeError (no such field)
    state.confidence = "0.85"      # → TypeError (str, expected float)
    state.intent                   # → str (typed, autocomplete works)
    state.user_tier                # → reads from ctx.state["user:user_tier"]
    state.scratch                  # → reads from ctx.state["temp:scratch"]
```

And the contract checker catches cross-agent problems before any LLM call:

```python
pipeline = (
    Agent("classifier").writes(BillingState.intent, BillingState.confidence)
    >> Agent("resolver").reads(BillingState.intent).writes(BillingState.ticket_id)
)

# check_contracts(pipeline.to_ir(), BillingState)
# → Error: BillingState has no field 'ticket_id'
#   (catches it before you spend a dollar on inference)
```

**This is the same pattern that made Pydantic win over raw dicts, that made TypeScript win over JavaScript, that made dataclasses win over tuples.** The underlying runtime is the same (ADK's `State` dict). The schema is a development-time lens that evaporates at runtime. You get IDE autocomplete, typo detection, type checking, and scope documentation — all while producing identical ADK state operations underneath.

**Backward compatible:** `StateSchema` is opt-in. Existing untyped agents keep working. Mixed typed/untyped pipelines work — the checker only enforces types where both sides declare them.

______________________________________________________________________

## 3. The Operator Algebra: Topology as Syntax

The real test of a composition system isn't a three-step pipeline. It's what happens when the topology gets complex. ADK's documentation shows a fan-out/gather pattern:

```python
# ADK: Parallel fetch then synthesize. Reasonable at this scale.
from google.adk.agents import SequentialAgent, ParallelAgent, LlmAgent

fetch_api1 = LlmAgent(name="API1Fetcher", instruction="Fetch data from API 1.", output_key="api1_data")
fetch_api2 = LlmAgent(name="API2Fetcher", instruction="Fetch data from API 2.", output_key="api2_data")

gather = ParallelAgent(name="ConcurrentFetch", sub_agents=[fetch_api1, fetch_api2])

synthesizer = LlmAgent(
    name="Synthesizer",
    instruction="Combine results from {api1_data} and {api2_data}."
)

root_agent = SequentialAgent(
    name="FetchAndSynthesize",
    sub_agents=[gather, synthesizer]
)
```

Now compose this with a refinement loop (writer → critic, loop until approved) and conditional routing (different handlers for different intents). In ADK, you need a `LoopAgent` with an `exit_loop` tool that sets `escalate=True`, wired inside a `SequentialAgent` that feeds into a custom `BaseAgent` subclass with `_run_async_impl` for the routing logic.

ADK's documentation on loop exit shows why this gets complex:

```python
# ADK: Loop with exit condition. The exit mechanism requires a dedicated tool
# that sets escalate=True on the tool_context.actions, plus skip_summarization.
from google.adk.tools.tool_context import ToolContext

def exit_loop(tool_context: ToolContext):
    """Call this function ONLY when the critique indicates no further changes."""
    tool_context.actions.escalate = True
    tool_context.actions.skip_summarization = True
    return {}

# The critic agent must be instructed to call this tool,
# and the instruction must precisely describe when to call it.
critic = LlmAgent(
    name="CriticAgent",
    instruction="""Review the document. If satisfactory, call exit_loop.
        If not, provide criticism.""",
    tools=[exit_loop],
    output_key="criticism"
)
```

The exit mechanism works, but it's an *implementation pattern* — you're encoding control flow into an LLM's tool-calling behavior and hoping it calls `exit_loop` at the right time rather than never or too early.

```python
# adk-fluent: Same topology, declarative exit condition

writer = Agent("writer").instruct("Write a draft.").outputs("draft")
critic = Agent("critic").instruct("Review {draft}. Rate quality.").outputs("quality")

# Deterministic exit: predicate on state, not LLM tool-calling behavior
pipeline = (
    writer >> critic
).loop_until(lambda s: s.get("quality") == "approved", max_iterations=5)
```

The `loop_until` compiles to a `LoopAgent` with a `_CheckpointAgent` that evaluates the predicate and escalates. Same ADK machinery underneath. But the exit condition is a Python predicate, not an instruction to an LLM — deterministic, testable, visible in the IR.

For the full pattern — parallel fetch, then route, then conditional refinement:

```python
# adk-fluent: Complex topology, still readable
from adk_fluent import Agent, S, Route

pipeline = (
    (Agent("api1").instruct("Fetch API 1.").outputs("api1_data")
     | Agent("api2").instruct("Fetch API 2.").outputs("api2_data"))
    >> S.merge("api1_data", "api2_data", into="combined")
    >> Agent("classifier").instruct("Classify: {combined}").outputs("intent")
    >> Route("intent")
        .eq("billing", Agent("billing").instruct("Handle billing: {combined}"))
        .eq("technical", Agent("tech").instruct("Handle tech: {combined}"))
        .otherwise(Agent("general").instruct("Handle: {combined}"))
)
```

Eight lines. The topology is the code. Parallel (`|`), sequential (`>>`), state transform (`S.merge`), deterministic routing (`Route`). Each produces the corresponding ADK agent type. No custom `BaseAgent` subclasses, no `_run_async_impl`, no `EventActions(escalate=True)`.

______________________________________________________________________

## 4. Zero-Cost State Transforms: What ADK Forces You to Put in Agents

ADK's agent communication is through shared state. One agent writes `output_key="findings"`, the next reads `{findings}` from its instruction. This works for simple pipelines.

But real pipelines need to massage state between agents: rename keys, drop intermediate data, merge parallel outputs, set defaults, validate invariants. In ADK, the only mechanism is... another agent:

```python
# ADK: You need a whole LlmAgent (or custom BaseAgent) just to rename a key
# There is no built-in "transform state without calling an LLM" primitive.
# You either:

# Option A: Write a custom BaseAgent with _run_async_impl
class RenameAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        ctx.session.state["research_data"] = ctx.session.state.get("findings", "")
        yield Event(...)  # Must yield at least one event

# Option B: Use a callback on the next agent to do the rename
def rename_before_writer(callback_context):
    callback_context.state["research_data"] = callback_context.state.get("findings", "")
    return None
```

Both work. Neither is discoverable. Neither is composable with `>>`. Neither expresses "this is a zero-cost operation that should never call an LLM."

```python
# adk-fluent: Zero-cost transforms compose naturally

pipeline = (
    Agent("researcher").instruct("Research.").outputs("findings")
    >> S.pick("findings", "sources")                         # Drop everything else
    >> S.rename(findings="research_data")                    # Rename for downstream
    >> S.default(confidence=0.0, draft_count=0)              # Fill defaults
    >> S.guard(lambda s: "research_data" in s, "Missing!")   # Validate
    >> Agent("writer").instruct("Write from {research_data}")
)
```

Each `S.*` call returns a plain function. `>>` wraps it in a `TransformNode` that compiles to a zero-cost `FnAgent` — a `BaseAgent` subclass that reads state, applies the function, writes the delta, and yields exactly one event. No LLM call. No token cost. The IR knows it's a transform (not an agent), so `estimate_cost()` correctly reports \$0 for these steps and the Mermaid visualization renders them as arrows rather than boxes.

This pattern — functional state transforms between agents — comes directly from pipeline architectures in data engineering (Spark transforms, dbt macros, Unix pipes). It's not a new idea. It's an idea ADK doesn't provide a first-class primitive for.

______________________________________________________________________

## 5. Deterministic Routing Without LLM Delegation

ADK's multi-agent routing relies on LLM delegation: the parent agent's instruction tells it when to transfer to which sub-agent, and the LLM decides based on the conversation. ADK's docs describe this as "LLM-driven dynamic routing."

This is powerful for open-ended conversations. It is expensive and unpredictable for deterministic classification results. If your classifier already wrote `intent="billing"` to state, you don't need another LLM call to decide to route to the billing handler — you need an `if` statement.

```python
# ADK: Deterministic routing requires a custom BaseAgent
# (ADK provides no built-in "route on state key" agent)

class IntentRouter(BaseAgent):
    async def _run_async_impl(self, ctx):
        intent = ctx.session.state.get("intent")
        if intent == "billing":
            async for event in self.sub_agents[0].run_async(ctx):
                yield event
        elif intent == "technical":
            async for event in self.sub_agents[1].run_async(ctx):
                yield event
        else:
            async for event in self.sub_agents[2].run_async(ctx):
                yield event

router = IntentRouter(
    name="router",
    sub_agents=[billing_agent, tech_agent, general_agent]
)
```

This is 15 lines of boilerplate for an `if/elif/else`. Every team writes this. Every team writes it slightly differently. None of it is visible to static analysis.

```python
# adk-fluent: Deterministic routing as a first-class primitive

pipeline = (
    Agent("classifier").instruct("Classify intent.").outputs("intent")
    >> Route("intent")
        .eq("billing", billing_agent)
        .eq("technical", tech_agent)
        .otherwise(general_agent)
)
```

`Route` compiles to a `_RouteAgent(BaseAgent)` that does exactly the `if/elif/else` above — zero LLM calls, pure state inspection. But because it's a declarative IR node (`RouteNode`), the contract checker can verify that the classifier's `output_key` matches the route's `key`, the Mermaid visualization renders it as a diamond, and `estimate_cost()` correctly excludes it from LLM cost calculations.

You can also route on thresholds (`Route("score").gt(0.8, premium).otherwise(basic)`), substring matches (`Route("text").contains("URGENT", escalation)`), or arbitrary predicates (`Route().when(lambda s: complex_logic(s), handler)`). All zero-cost. All visible in the IR.

______________________________________________________________________

## 6. Cost Simulation: Know What You'll Spend Before You Spend It

This is a v5-only capability with no ADK equivalent. ADK tracks costs after execution via OTel spans. There is no way to estimate what a pipeline *will* cost given traffic assumptions.

```python
# adk-fluent v5: Simulate cost from the IR without executing anything

from adk_fluent.cost import estimate_cost, TrafficAssumptions

estimate = estimate_cost(
    pipeline.to_ir(),
    TrafficAssumptions(
        invocations_per_day=10_000,
        avg_input_tokens=500,
        avg_output_tokens=200,
        branch_probabilities={"billing": 0.6, "technical": 0.3, "general": 0.1},
    ),
)
# estimate.daily_cost_usd → $47.20
# estimate.monthly_cost_usd → $1,416.00
# estimate.per_agent_breakdown → {"classifier": $12.50, "billing": $18.90, ...}
# estimate.cost_per_invocation → $0.00472
```

This works because the IR knows the graph topology, each node's model, and the cost-per-token rates for each model. `TransformNode` and `RouteNode` contribute \$0. `ParallelNode` costs are additive. `LoopNode` costs multiply by expected iterations. Branch probabilities weight the cost of `RouteNode` branches.

**Why this matters for enterprise:** At Google Cloud, the question a CTO asks before approving an AI deployment isn't "does it work?" — it's "what will it cost at 10,000 invocations per day?" Being able to answer that from the IR, before writing a single prompt, before making a single API call, is the difference between a POC that gets approved and one that dies in committee.

The v5 `CostAttributionMiddleware` then emits OTel metrics (`adk_fluent.llm.cost`, `adk_fluent.llm.tokens`) during execution, allowing you to compare estimates against actuals. The spec targets \<20% estimation error.

______________________________________________________________________

## 7. Evaluation: Fluent Cases That Run on ADK's Infrastructure

ADK has a substantial evaluation system — `EvalSet`, `EvalCase`, `LocalEvalService`, `TrajectoryEvaluator`, `ResponseEvaluator`, user simulation, multi-run aggregation, a CLI (`adk eval`), and a web UI for golden dataset management.

The problem isn't the evaluation engine. It's the ergonomics of authoring test cases. Here's an ADK eval set:

```json
{
    "eval_set_id": "billing_tests",
    "eval_cases": [
        {
            "eval_id": "billing_dispute_1",
            "conversation": [
                {
                    "invocation_id": "inv_1",
                    "user_content": {
                        "role": "user",
                        "parts": [{"text": "My bill is $200 too high"}]
                    },
                    "expected_tool_use": [
                        {"tool_name": "classify_intent"},
                        {"tool_name": "create_ticket"}
                    ],
                    "reference": "I've created a ticket for your billing dispute."
                }
            ],
            "initial_session": {"state": {}}
        }
    ]
}
```

This is 22 lines of JSON for one test case with one turn. It's structurally correct — `EvalCase` is a Pydantic model and this is its serialization — but writing 50 test cases this way is grinding.

```python
# adk-fluent v5: Same test case, runs on the same LocalEvalService

suite = FluentEvalSuite(
    name="billing_tests",
    pipeline=pipeline,
    cases=[
        FluentCase(
            input="My bill is $200 too high",
            expected_trajectory=["classify_intent", "create_ticket"],
            expected_response_contains="ticket",
            tags=["billing", "dispute"],
        ),
        FluentCase(
            input="I want a refund",
            expected_trajectory=["classify_intent", "process_refund"],
            tags=["billing", "refund"],
        ),
    ],
    metrics=[PrebuiltMetrics.TOOL_TRAJECTORY_AVG_SCORE],
    thresholds={PrebuiltMetrics.TOOL_TRAJECTORY_AVG_SCORE: 1.0},
    num_runs=2,
)

report = await suite.run()
# report.passed → True/False
# report.per_tag("billing") → {avg_trajectory: 1.0, avg_response: 0.85}
# report.compare(baseline) → RegressionReport (what got worse?)
```

`FluentCase` compiles to ADK's `EvalCase` with `Invocation` objects. `FluentEvalSuite.run()` calls `LocalEvalService.evaluate()` internally. The output `.to_eval_set_file("billing.evalset.json")` produces a file that `adk eval` can consume directly. The web UI's golden dataset capture produces files that `FluentEvalSuite.from_eval_set()` can load.

**What v5 adds that ADK doesn't have:**

- **Tag-based aggregation:** "How do billing cases perform vs. technical cases?" ADK reports per-case; you aggregate manually.
- **Regression detection:** `report.compare(baseline_report)` diffs scores and flags regressions. ADK has no built-in baseline comparison.
- **Sub-graph targeting:** `FluentCase(target_node="classifier")` evaluates just the classifier agent, not the whole pipeline. ADK evaluates the root agent.
- **Typed state assertions:** `FluentCase(state_assertions={"intent": "billing"})` verifies intermediate state after execution. ADK checks tool trajectories and final responses, not intermediate state.
- **Cost per eval case:** OTel metrics from `CostAttributionMiddleware` attach cost data to each case result.

**What v5 does NOT build:** Its own trajectory evaluator, response evaluator, user simulator, multi-run aggregation, `.evalset.json` format, or eval CLI. Those are ADK's. Building parallel versions would be the DI mistake — engineering effort that doesn't produce user value.

______________________________________________________________________

## 8. Telemetry: Enrich ADK's Spans, Don't Duplicate Them

ADK already emits OpenTelemetry spans at every lifecycle point — agent invocation, LLM calls, tool execution — following GenAI Semantic Conventions 1.37. It has exporters for Cloud Trace, OTLP, in-memory, and the web UI's trace viewer.

Building a parallel observability layer — which is what a `StructuredLogMiddleware` that captures events in a separate list effectively does — creates two sources of truth, doubles storage, and means the built-in trace viewer shows different data than your custom logs.

v5 replaces this with span enrichment:

```python
# adk-fluent v5: Annotate ADK's existing spans, don't create new ones

class OTelEnrichmentMiddleware:
    async def before_agent(self, ctx, agent_name):
        span = trace.get_current_span()           # ADK's span, not ours
        span.set_attribute("adk_fluent.pipeline", "billing_v2")
        span.set_attribute("adk_fluent.node_type", "agent")
        return None                                 # Don't short-circuit

    async def after_model(self, ctx, response):
        span = trace.get_current_span()           # ADK's call_llm span
        usage = extract_usage(response)
        _llm_cost.add(compute_cost(usage), {"agent": ctx.agent_name, "model": usage.model})
        return None
```

Three consequences: (1) `adk_fluent.*` attributes show up in ADK's web UI trace viewer automatically. (2) Cloud Trace / Datadog / Grafana see enriched spans with no additional exporter configuration. (3) The `adk_fluent.llm.cost` OTel counter is a real metric that Prometheus can scrape, alert on, and dashboard — not a log entry someone has to parse.

______________________________________________________________________

## 9. Contract Checking: Catch Wiring Bugs Before LLM Calls

v5's unified contract checker runs on the IR and catches entire categories of bugs at build time:

```python
from adk_fluent.contracts import check_all

report = check_all(pipeline.to_ir(), schema=BillingState)

# Checks that run in <100ms for a 100-node graph:
# - Dataflow:  Does every reader have a prior writer? Any dead state?
# - Types:     Does classifier write str but resolver expect float?
# - Streaming: Token-streaming upstream of a RouteNode? (impossible — route needs full output)
# - Modality:  Routing video output to a text-only agent?
# - Cost:      Budget key referenced but no ModelSelectorNode provides it?
# - A2A:       Remote agent's AgentCard satisfies input requirements?

if report.errors:
    for error in report.errors:
        print(f"  {error}")  # Human-readable, actionable
    sys.exit(1)  # Fail fast in CI
```

This is the "dry-run your architecture" principle. Every production concern — data flow, types, streaming semantics, modality compatibility, cost configuration — is verifiable from the IR without making a single LLM call. The IR is a structural artifact, not just an intermediate representation; it's the thing you analyze, visualize, cost-estimate, and contract-check.

______________________________________________________________________

## 10. What About Dependency Injection?

The v4 spec includes a DI model. Let's be honest about whether it belongs.

**The case for DI:** In web frameworks like FastAPI, DI is essential because HTTP handlers need database connections, auth tokens, configuration objects, and test mocks. The handler's signature declares its dependencies; the framework injects them. Without DI, every handler manually constructs its dependencies — untestable, unconfigurable.

**The case against DI in agent systems:** An LLM agent's interface to the external world is *tool calling*. Tools are already injected — you pass them to the agent at construction time. The agent doesn't import `database_connection`; it calls `query_database(sql)` and the tool function handles the connection. Tool functions can close over whatever dependencies they need:

```python
# This is already dependency injection. It just doesn't need a framework.
def make_query_tool(db_connection):
    def query_database(sql: str) -> dict:
        return db_connection.execute(sql)
    return query_database

agent = Agent("analyst").tool(make_query_tool(production_db))
test_agent = Agent("analyst").tool(make_query_tool(mock_db))
```

Closure-based injection is simpler, more Pythonic, and more transparent than a DI container. The LLM doesn't know or care where the tool's dependencies come from. The developer can see exactly what's injected by reading the tool factory.

**Where DI might matter:** If your pipeline has 20 agents, each needing the same session service, artifact service, and credentials — and you want to swap all of them for testing — a DI container saves repetition. But ADK's `App` already centralizes `session_service`, `artifact_service`, and `memory_service` at the app level. You don't inject them per-agent; you set them once.

**Our recommendation:** Don't build a DI framework. Tool closures + ADK's app-level service configuration cover the real needs. If v4's DI model stays in the spec, it should be documented as "available for advanced cases" rather than a primary pattern. The progressive disclosure curve should lead users toward tool closures first.

______________________________________________________________________

## 11. Replay and Time-Travel Debugging: The Production Debugging Story

When a production pipeline produces a wrong answer, the debugging loop in ADK is: read the trace in the web UI, try to understand what happened, modify the agent, re-run with a similar prompt, hope to reproduce it.

v5's replay system records the full execution — events, OTel spans, state snapshots, LLM responses — and deterministically replays it:

```python
from adk_fluent.debug import Recorder, ReplayerBackend

# Record
recorder = Recorder()
events = await pipeline.run("My bill is too high", middlewares=[recorder])
recording = recorder.to_recording()

# Replay (deterministic — uses recorded LLM responses)
replayer = ReplayerBackend(recording)
replay_events = await replayer.run(pipeline.to_ir(), "My bill is too high")

# Diff
from adk_fluent.debug import diff_events
changes = diff_events(events, replay_events)
assert changes == []  # Identical replay
```

Change the pipeline, replay the same recording, diff the events. You see exactly which agent produced different output and why. This is the same principle behind record/replay debugging in distributed systems (Hermit, rr, Ditto) applied to agent pipelines.

The Recorder builds on ADK's `InMemoryExporter` for span data and the middleware event hooks for `AgentEvent` capture. The ReplayerBackend intercepts `call_llm` spans and returns recorded responses instead of calling the LLM. Mismatch strategies (error, skip, live) handle cases where the pipeline has changed.

______________________________________________________________________

## 12. What v5 Does NOT Do (And Why)

**No new agent runtime.** adk-fluent doesn't replace ADK's Runner, InMemoryRunner, or App. It produces native ADK agents that run in ADK's runtime.

**No custom session service.** State flows through ADK's session service. `StateSchema` is a development-time lens over ADK's `State` dict — it doesn't change how state is stored or persisted.

**No parallel evaluation engine.** `FluentEvalSuite` calls `LocalEvalService`. It doesn't reimplement trajectory evaluation, response scoring, or user simulation.

**No parallel telemetry.** `OTelEnrichmentMiddleware` annotates ADK's spans. It doesn't create its own tracer, its own span hierarchy, or its own exporter chain.

**No GUI.** adk-fluent agents work in `adk web` and `adk run` because they *are* ADK agents. The Mermaid visualization (`ir_to_mermaid`) is a developer tool, not a runtime UI.

**No opinion on model choice.** `Agent("x").model("gemini-2.5-flash")` passes through to ADK's model resolution. adk-fluent doesn't wrap the model layer, doesn't add prompt optimization, doesn't modify the generation config unless you tell it to. `ModelSelectorNode` is opt-in cost routing, not a model abstraction layer.

The principle is consistent: **build what ADK doesn't have, wrap what ADK has but isn't fluent, never replace what ADK already does well.**

______________________________________________________________________

## 13. The Progressive Disclosure Ladder

One of v5's structural contributions is making the complexity curve explicit. You adopt features as you need them — nothing forces you up the ladder:

| Level | What You Use                           | What You Get                                 | ADK Equivalent                                 |
| ----- | -------------------------------------- | -------------------------------------------- | ---------------------------------------------- |
| 0     | `Agent("x").instruct("...").build()`   | Fluent single agent                          | Same as native ADK with less typing            |
| 1     | `a >> b`, `a \| b`, `a * 3`            | Pipeline composition                         | Manual SequentialAgent/ParallelAgent/LoopAgent |
| 2     | `S.pick()`, `Route()`, `until()`       | State transforms, routing, conditional loops | Custom BaseAgent subclasses                    |
| 3     | `.to_ir()`, `check_contracts()`        | Static analysis, visualization               | Nothing (ADK has no IR)                        |
| 4     | `StateSchema`, `check_all()`           | Typed state, full contract checking          | Nothing                                        |
| 5     | `estimate_cost()`, `ModelSelectorNode` | Cost simulation and governance               | Nothing                                        |
| 6     | `FluentEvalSuite`, `FluentCase`        | Eval authoring over ADK's engine             | Raw `.evalset.json` + `adk eval` CLI           |
| 7     | `Recorder`, `ReplayerBackend`          | Deterministic replay and diff                | ADK's RecordingsPlugin (different scope)       |
| 8     | `OTelEnrichmentMiddleware`             | Pipeline-aware telemetry                     | ADK's built-in OTel (extended, not replaced)   |
| 9     | `RemoteAgentNode`, `ExecutionBoundary` | Distributed, cross-system pipelines          | Manual A2A integration + custom deployment     |

Level 0 users get IDE autocomplete and typo detection. Level 2 users get readable pipeline topology. Level 4+ users get production infrastructure. Every level produces native ADK objects. No level requires the levels above it.

______________________________________________________________________

## 14. Summary: The Real Wins

The features that clear the bar decisively:

1. **Composition operators** (`>>`, `|`, `*`, `//`) — topology as syntax. This is the core value proposition and it's already shipped. Not debatable.

1. **Typed state** (`StateSchema`) — catches the most common production failures at build time. Same pattern as Pydantic over dicts. High confidence this earns its complexity.

1. **Zero-cost transforms** (`S.*`) — fills a real gap. ADK has no "transform state without an LLM call" primitive. Every team builds this ad hoc.

1. **Deterministic routing** (`Route`) — same. ADK's routing is LLM-driven. When you already have the classification result in state, you need an if-statement, not another LLM call.

1. **Cost simulation** (`estimate_cost`) — no ADK equivalent. Enables budget conversations before deployment. Enterprise-critical.

1. **Contract checking** (`check_all`) — no ADK equivalent. Static analysis on agent pipelines is a new capability, not a convenience wrapper.

The features that are strong but require ADK's infrastructure to mature:

7. **Evaluation harness** — good fluent API over a good ADK engine. Value depends on how stable ADK's eval API is across releases.

1. **Telemetry enrichment** — correct architecture (enrich, don't duplicate). Value depends on teams actually using OTel dashboards.

The features that are forward-looking (less immediate ROI):

9. **Streaming edge semantics** — matters when you build real-time UIs over agent pipelines. Most teams don't today.

1. **A2A interop, execution boundaries** — matters for large-scale distributed deployments. Most teams are single-process today.

The feature we'd reconsider:

11. **Dependency injection** — tool closures already handle this. Don't add framework complexity for a problem that's already solved idiomatically.
