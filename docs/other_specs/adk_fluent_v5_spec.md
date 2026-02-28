# ADK-FLUENT: Specification v5 — Production Agent Systems

**Status:** Supersedes SPEC_v4.md\
**ADK Baseline:** google-adk v1.25.0+ (`adk-python` main branch, Feb 2026)\
**Philosophy:** The expression graph is the product. ADK is one backend. The IR evolves with ADK automatically. Every cross-cutting concern — telemetry, evaluation, cost — extends ADK's existing infrastructure rather than replacing it.\
**Architecture:** Expression IR → Backend Protocol → ADK (or anything else)

______________________________________________________________________

## 0. Preamble: What Changed Since v4

v4 established the seed-based IR generator, the 13-callback middleware protocol aligned with ADK v1.25.0's `BasePlugin`, and the backend protocol abstraction. These are structural achievements. They are retained in full.

v5 addresses what v4 left unmodeled: the production realities of enterprise agent systems. Crucially, v5 applies the Tide Principle to two areas that v4's drafting process missed: **telemetry** and **evaluation**. Both ADK subsystems are mature, opinionated, and structurally integrated — building parallel versions would violate the core design philosophy.

| v4 State                                                       | v5 Change                                                                                 | Rationale                                                                                 |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| State is `dict[str, Any]` with string-key conventions          | **`StateSchema`**: typed, scoped, validated at build time                                 | Largest source of runtime errors in production pipelines                                  |
| Streaming is `ExecutionConfig.streaming_mode` (a runtime flag) | **Stream edge semantics**: IR-level buffering and backpressure                            | Streaming changes composition semantics; a runtime toggle is insufficient                 |
| `cost_tracker` middleware (observability only)                 | **Cost-aware routing**: `ModelSelectorNode` with budget constraints, OTel metric emission | Enterprise buyers need cost governance, not just cost visibility                          |
| No cross-system interop                                        | **A2A boundary nodes**: `RemoteAgentNode`, `AgentCard`                                    | Agent-to-Agent protocol interop for federated enterprise deployments                      |
| Mock-based testing only                                        | **Evaluation harness**: fluent API over ADK's `EvalSet`/`LocalEvalService`                | Mock tests verify mechanics; evals verify reasoning — using ADK's existing infrastructure |
| No telemetry awareness                                         | **OTel integration**: enrichment of ADK's span hierarchy, not parallel capture            | ADK already emits OTel spans at every lifecycle point; duplicating is wasteful            |
| Content is strings                                             | **Multi-modal content spec**: declared modality contracts                                 | Prevents routing video to text-only agents                                                |
| No replay capability                                           | **Event replay and time-travel debugging**: built on ADK's `InMemoryExporter`             | Production debugging requires reproducing event streams locally                           |
| Single-process execution assumed                               | **Execution boundaries**: serialization and queue annotations                             | Conglomerate-scale deployments require distributed execution                              |
| Decisions implicit                                             | **ADR appendix**: rejected alternatives documented                                        | Spec consumers need "why not" as much as "what"                                           |

v4's core constructs — the IR node types, the `Backend` protocol, the `Middleware` protocol, the ADK construct map (§1), the disfluency catalog (§2), the state transform semantics (§6), the dependency injection model (§8), and the module architecture (§10) — are **incorporated by reference** and not repeated except where v5 modifies them.

______________________________________________________________________

## 1. Typed State System

### 1.1 The Problem

v4 §6 confirms that ADK's `State` is a string-keyed dict with scope prefixes and no `__delitem__`. v4's `produces()`/`consumes()` (§7) checks contracts at adjacent agent boundaries. Neither mechanism prevents:

- Misspelled state keys (`ctx.state["inten"]` vs `ctx.state["intent"]`)
- Type mismatches (classifier writes `confidence` as `str`, resolver reads it as `float`)
- Scope confusion (`user:preference` written where `temp:preference` was intended)
- Cross-graph key collisions in composed pipelines

These are the most common production failures in agent pipelines and they all surface at runtime.

### 1.2 `StateSchema` — First-Class IR Concept

```python
from adk_fluent.state import StateSchema, SessionScoped, UserScoped, AppScoped, Temp

class BillingState(StateSchema):
    # Session-scoped (default)
    intent: str
    confidence: float
    ticket_id: str | None = None
    resolution: str | None = None

    # Explicitly scoped
    user_tier: Annotated[str, UserScoped]
    app_version: Annotated[str, AppScoped]
    scratch: Annotated[dict, Temp]
```

**Scope annotations compile to ADK prefix conventions:**

| Annotation      | ADK Key           | Persistence                  |
| --------------- | ----------------- | ---------------------------- |
| (default)       | `intent`          | Session storage              |
| `SessionScoped` | `intent`          | Session storage              |
| `UserScoped`    | `user:user_tier`  | User storage (cross-session) |
| `AppScoped`     | `app:app_version` | App storage (cross-user)     |
| `Temp`          | `temp:scratch`    | Ephemeral (never persisted)  |

### 1.3 Schema-Bound Agents

```python
pipeline = (
    Agent("classifier")
        .writes(BillingState.intent, BillingState.confidence)
    >> Agent("resolver")
        .reads(BillingState.intent)
        .writes(BillingState.ticket_id, BillingState.resolution)
)
```

**Builder mechanics:** `.writes(BillingState.intent)` resolves the field descriptor to a `StateFieldRef(name="intent", type=str, scope="session")`. This populates `AgentNode.writes_keys` with typed entries instead of bare strings. `.reads(BillingState.intent)` does the same for `AgentNode.reads_keys`.

### 1.4 Typed State Access in Tools and Callbacks

```python
def create_ticket(query: str, tool_context: Context) -> str:
    state = BillingState.bind(tool_context)
    # state.intent → typed str (reads ctx.state["intent"])
    # state.ticket_id = "T-1234" → writes ctx.state["ticket_id"]
    # state.ticket_id = 42 → raises TypeError at runtime
    intent = state.intent
    state.ticket_id = f"T-{generate_id()}"
    return f"Created ticket for {intent}"
```

**Implementation:** `StateSchema.bind(ctx)` returns a descriptor proxy that:

1. Reads: `ctx.state[prefix + field_name]` with type validation
1. Writes: `ctx.state[prefix + field_name] = value` with type check
1. Raises `StateKeyError` (not `KeyError`) with diagnostic context on missing keys

### 1.5 Pipeline-Wide Contract Checking

v4's `check_contracts()` verified adjacent pairs. v5 verifies the full graph:

```python
def check_contracts(root: Node, schema: type[StateSchema] | None = None) -> list[ContractIssue]:
    """Verify reads-after-writes ordering across the entire IR graph."""
    issues = []
    available_keys: dict[str, StateFieldRef] = {}

    for node in topological_order(root):
        for ref in node.reads_keys:
            if ref.name not in available_keys:
                issues.append(ReadBeforeWrite(node.name, ref))
            elif schema and available_keys[ref.name].type != ref.type:
                issues.append(TypeMismatch(
                    node.name, ref,
                    expected=ref.type,
                    actual=available_keys[ref.name].type,
                ))
        for ref in node.writes_keys:
            available_keys[ref.name] = ref

    all_reads = {ref.name for node in topological_order(root) for ref in node.reads_keys}
    for name, ref in available_keys.items():
        if name not in all_reads and not ref.scope == "temp":
            issues.append(DeadState(ref))

    return issues
```

**Issue types:** `ReadBeforeWrite`, `TypeMismatch`, `ScopeMismatch`, `DeadState`, `SchemaViolation`.

### 1.6 Backward Compatibility

`StateSchema` is entirely optional. Untyped agents continue to work. Typed and untyped agents interoperate; the contract checker only enforces types when both sides declare them.

### 1.7 Schema Composition for Pipelines

```python
class ClassifierState(StateSchema):
    intent: str
    confidence: float

class ResolverState(StateSchema):
    ticket_id: str
    resolution: str

class BillingPipelineState(ClassifierState, ResolverState):
    pass
```

Multiple inheritance on `StateSchema` produces a merged schema. Field name collisions across parent schemas raise `SchemaCompositionError` at class definition time if types differ.

______________________________________________________________________

## 2. Streaming Edge Semantics

### 2.1 The Problem

v4 models streaming as `ExecutionConfig.streaming_mode: Literal["none", "sse", "bidi"]` — a runtime toggle applied uniformly. But streaming changes composition semantics:

- In `A >> B`, does B wait for A's full output or begin processing partial tokens?
- In `A | B` (parallel), how do interleaved streams merge?
- In `Route(key="intent", ...)`, the key may not be available until the stream completes.
- Middleware that inspects `after_model` responses may receive partial chunks.

These are design-time decisions, not runtime flags.

### 2.2 Edge Semantics in the IR

```python
@dataclass(frozen=True)
class EdgeSemantics:
    """Describes how data flows between connected IR nodes."""
    buffering: Literal["full", "chunked", "token"] = "full"
    backpressure: bool = False
    chunk_size: int | None = None

    merge: Literal["wait_all", "first_complete", "interleave"] = "wait_all"
```

| Mode      | Behavior                                                     | Use Case                           |
| --------- | ------------------------------------------------------------ | ---------------------------------- |
| `full`    | Downstream waits for complete output                         | Default; safe for all compositions |
| `chunked` | Downstream receives content in chunks of `chunk_size` tokens | Progressive UI rendering           |
| `token`   | Downstream receives each token as emitted                    | Real-time typing indicators        |

### 2.3 Builder API and IR Representation

```python
pipeline = (
    Agent("classifier").stream_to(buffering="full")
    >> Agent("synthesizer").stream_to(buffering="token")
)

parallel = FanOut(
    Agent("search_a"),
    Agent("search_b"),
    merge="first_complete",
)
```

`SequenceNode` gains `edge_semantics: tuple[EdgeSemantics, ...]`. `ParallelNode` gains `merge: Literal["wait_all", "first_complete", "interleave"]`.

### 2.4 ADK Backend Compilation

- `full`: Standard `SequentialAgent` behavior.
- `chunked`/`token`: Backend wraps downstream in a streaming adapter using `on_event_callback`.
- `first_complete`: Backend wraps parallel agent with cancellation on first completion.

### 2.5 Contract Checking for Streams

```python
def check_streaming_contracts(root: Node) -> list[StreamingIssue]:
    issues = []
    for node in walk(root):
        match node:
            case RouteNode() if has_upstream_token_streaming(node):
                issues.append(StreamingRouteConflict(node.name))
            case SequenceNode(edge_semantics=edges):
                for i, edge in enumerate(edges):
                    downstream = node.children[i + 1]
                    if edge.buffering == "token" and isinstance(downstream, RouteNode):
                        issues.append(StreamingRouteConflict(downstream.name))
    return issues
```

______________________________________________________________________

## 3. Cost-Aware Routing

### 3.1 The Problem

v4's `cost_tracker` middleware observes costs after they occur. Enterprise deployments need budget governance, cost-optimized routing, cost simulation, and cost attribution via standard observability tooling.

### 3.2 `ModelSelectorNode`

```python
@dataclass(frozen=True)
class ModelCandidate:
    model: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    quality_tier: int
    max_tokens: int | None = None
    condition: Callable | None = None

@dataclass(frozen=True)
class ModelSelectorNode:
    name: str
    strategy: Literal["cost_optimized", "quality_optimized", "budget_bounded", "adaptive"]
    candidates: tuple[ModelCandidate, ...]
    budget_key: str | None = None
    fallback_model: str | None = None
```

| Strategy            | Behavior                                                             |
| ------------------- | -------------------------------------------------------------------- |
| `cost_optimized`    | Cheapest candidate whose `condition` passes                          |
| `quality_optimized` | Highest `quality_tier` whose `condition` passes                      |
| `budget_bounded`    | Cheapest candidate; switch to `fallback_model` when budget exhausted |
| `adaptive`          | Start cheap; promote on quality feedback                             |

### 3.3 Builder API

```python
agent = (
    Agent("classifier")
    .model_select(
        strategy="budget_bounded",
        candidates=[
            ModelCandidate("gemini-2.5-flash", 0.15, 0.60, quality_tier=1),
            ModelCandidate("gemini-2.5-pro", 1.25, 5.00, quality_tier=2),
        ],
        budget_key="remaining_budget",
        fallback_model="gemini-2.5-flash",
    )
    .instruct("Classify: {user_query}")
)
```

### 3.4 `CostModel` — Simulation Without Execution

```python
from adk_fluent.cost import estimate_cost, TrafficAssumptions

model = estimate_cost(
    pipeline.build(),
    TrafficAssumptions(
        invocations_per_day=10_000,
        avg_input_tokens=500,
        avg_output_tokens=200,
        branch_probabilities={"billing": 0.6, "technical": 0.3, "general": 0.1},
    ),
)
print(f"Estimated daily cost: ${model.total_estimated:.2f}")
```

### 3.5 Cost Attribution via OpenTelemetry Metrics

**Design principle:** Cost attribution emits OTel metrics, not state writes. This ensures cost data flows into whatever observability backend the deployment uses (Cloud Monitoring, Datadog, Prometheus) without polluting agent state.

ADK's telemetry module provides an OTel tracer with span attributes for `gen_ai.request.model`. Cost attribution extends this with OTel metrics:

```python
from opentelemetry import metrics, trace

_meter = metrics.get_meter("adk_fluent.cost")
_llm_cost_counter = _meter.create_counter("adk_fluent.llm.cost", unit="USD")
_llm_token_counter = _meter.create_counter("adk_fluent.llm.tokens", unit="tokens")

class CostAttributionMiddleware:
    """Emits OTel metrics for per-agent, per-model cost tracking.

    Integrates with ADK's existing OTel span hierarchy — the cost metric
    shares the same trace context as ADK's call_llm spans.
    """
    async def after_model(self, ctx: Context, response: Any) -> None:
        usage = extract_usage(response)
        model = ctx.run_config.model or "unknown"
        cost = compute_cost(model, usage)

        labels = {"agent_name": ctx.agent_name, "model": model}
        _llm_cost_counter.add(cost, labels)
        _llm_token_counter.add(usage.input_tokens + usage.output_tokens, labels)

        # Annotate ADK's current call_llm span
        span = trace.get_current_span()
        span.set_attribute("adk_fluent.cost_usd", cost)
        span.set_attribute("adk_fluent.input_tokens", usage.input_tokens)
        span.set_attribute("adk_fluent.output_tokens", usage.output_tokens)

        # Decrement budget if budget-bounded
        budget_key = ctx.state.get("temp:_budget_key")
        if budget_key:
            remaining = ctx.state.get(budget_key, float('inf'))
            ctx.state[budget_key] = remaining - cost

        return None
```

**Bridge between estimated and actual cost:** `VizBackend` renders `estimate_cost()` data per node. OTel metrics capture actual cost. Dashboards compare both using shared `agent_name` labels.

______________________________________________________________________

## 4. A2A Protocol Interop

### 4.1 `RemoteAgentNode`

```python
@dataclass(frozen=True)
class RemoteAgentNode:
    name: str
    endpoint: str
    capabilities: tuple[str, ...] = ()
    input_schema: type | None = None
    output_schema: type | None = None
    auth: AuthConfig | None = None
    timeout_seconds: float = 30.0
    retry: RetryConfig | None = None
    fallback: 'Node | None' = None
```

### 4.2 Builder API

```python
pipeline = (
    Agent("classifier", "gemini-2.5-flash")
        .instruct("Classify intent: {user_query}")
        .outputs("intent")
    >> RemoteAgent(
        "payment_processor",
        endpoint="https://payments.internal/a2a",
        capabilities=("process_refund", "check_balance"),
        timeout=15.0,
        fallback=Agent("fallback_processor").instruct("Handle payment manually"),
    )
    >> Agent("responder", "gemini-2.5-flash")
        .instruct("Compose response based on: {resolution}")
)
```

### 4.3 ADK Backend Compilation

`RemoteAgentNode` compiles to `_A2AAgent(BaseAgent)` that serializes state into A2A `Task` messages, streams `TaskStatus` updates as ADK `Event` objects, and falls back on failure. Overrides `_run_async_impl()` (not `run_async()`, which is `@final`).

### 4.4 `AgentCard` — Advertising Capabilities

```python
card = pipeline.to_agent_card(
    description="Billing support agent with refund processing",
    endpoint="https://support.example.com/a2a",
)

from adk_fluent.serve import A2AServer
server = A2AServer(pipeline, card=card, config=config)
await server.start(port=8080)
```

### 4.5 Discovery

```python
from adk_fluent.a2a import AgentDirectory
directory = AgentDirectory("https://directory.internal/a2a")
agents = await directory.discover(capabilities=["process_refund"])
pipeline = Agent("classifier") >> RemoteAgent.from_card(agents[0]) >> Agent("responder")
```

______________________________________________________________________

## 5. Telemetry Integration

### 5.1 ADK's Existing Telemetry Architecture

**Source:** `src/google/adk/telemetry/tracing.py`, `src/google/adk/cli/adk_web_server.py`

ADK provides an integrated OpenTelemetry implementation following Semantic Conventions 1.37 for generative AI workloads:

**Centralized tracer:** `telemetry.tracing.tracer` — a single OTel tracer across all ADK modules.

**Span hierarchy:**

```
invocation                    (Runner.run_async — top-level)
  └── invoke_agent            (BaseAgent.run_async — @final)
        ├── call_llm          (BaseLlmFlow._call_llm_async)
        ├── execute_tool      (per individual tool call)
        └── execute_tool      (merged — for parallel tool calls)
```

**Span attributes (OTel GenAI conventions):**

- `gen_ai.agent.name`, `gen_ai.agent.description`, `gen_ai.operation.name` on `invoke_agent`
- `gen_ai.request.model`, `gen_ai.system`, `gcp.vertex.agent.event_id` on `call_llm`
- `gen_ai.tool.name`, `gen_ai.tool.description`, `gen_ai.tool.call.id` on `execute_tool`
- `gcp.vertex.agent.session_id`, `gcp.vertex.agent.user_id` on `invocation`

**Content capture:** Toggled via `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`. When enabled, `trace_call_llm` records request/response content in span attributes.

**Built-in exporters:**

- `InMemoryExporter` — stores spans indexed by session ID (dev/debug)
- `ApiServerSpanExporter` — indexes by event ID (web UI `/debug/trace/:event_id`)
- `CloudTraceSpanExporter` — production export via `--trace_to_cloud`
- OTLP export via standard `OTEL_EXPORTER_OTLP_ENDPOINT` environment variables

### 5.2 The Design Principle: Enrich, Don't Duplicate

adk-fluent's telemetry strategy is **span enrichment** — adding pipeline-level metadata to ADK's existing spans, not creating parallel spans that duplicate ADK's work.

ADK already emits spans at every lifecycle point: agent invocation, LLM calls, tool execution. Creating additional middleware spans at the same points would produce duplicate telemetry, confuse trace visualization, and double storage costs.

### 5.3 `OTelEnrichmentMiddleware`

Replaces v4's `structured_log` middleware. Annotates ADK's existing spans with adk-fluent metadata:

```python
from opentelemetry import trace

class OTelEnrichmentMiddleware:
    """Adds adk-fluent metadata to ADK's existing OTel spans.

    Does NOT create new spans — enriches the current span created by ADK's
    own telemetry (call_llm, execute_tool, invoke_agent).
    """
    def __init__(self, pipeline_name: str | None = None):
        self._pipeline_name = pipeline_name

    async def before_agent(self, ctx: Context, agent_name: str) -> None:
        span = trace.get_current_span()
        if self._pipeline_name:
            span.set_attribute("adk_fluent.pipeline", self._pipeline_name)
        span.set_attribute("adk_fluent.node_type", ctx.state.get("temp:_node_type", "agent"))
        return None

    async def before_model(self, ctx: Context, request: Any) -> None:
        span = trace.get_current_span()
        span.set_attribute("adk_fluent.agent_name", ctx.agent_name)
        if hasattr(request, 'model'):
            span.set_attribute("adk_fluent.cost_estimate_usd", self._estimate_cost(request))
        return None

    async def after_model(self, ctx: Context, response: Any) -> None:
        span = trace.get_current_span()
        usage = extract_usage(response)
        if usage:
            span.set_attribute("adk_fluent.actual_input_tokens", usage.input_tokens)
            span.set_attribute("adk_fluent.actual_output_tokens", usage.output_tokens)
        return None

    async def before_tool(self, ctx: Context, tool_name: str, args: dict) -> None:
        span = trace.get_current_span()
        span.set_attribute("adk_fluent.tool_agent", ctx.agent_name)
        return None
```

### 5.4 OTel Metrics for adk-fluent

Beyond span enrichment, adk-fluent emits its own OTel metrics for concepts ADK doesn't track:

```python
_meter = metrics.get_meter("adk_fluent")

_llm_cost = _meter.create_counter("adk_fluent.llm.cost", unit="USD")
_llm_tokens = _meter.create_counter("adk_fluent.llm.tokens", unit="tokens")
_pipeline_duration = _meter.create_histogram("adk_fluent.pipeline.duration", unit="ms")
_pipeline_errors = _meter.create_counter("adk_fluent.pipeline.errors")
_contract_violations = _meter.create_counter("adk_fluent.contracts.violations")
```

### 5.5 Integration with ADK's Debug Endpoints

adk-fluent's enrichment attributes appear naturally in ADK's `/debug/trace/:event_id` because they're set on the same spans. No additional debug infrastructure needed.

### 5.6 Configuration Pass-Through

```python
config = ExecutionConfig(
    app_name="support",
    telemetry=TelemetryConfig(
        trace_to_cloud=True,
        capture_content=False,
        custom_exporters=[my_exporter],
        enable_cost_metrics=True,
    ),
)
```

`TelemetryConfig` compiles to environment variables and exporter setup by the ADK backend.

______________________________________________________________________

## 6. Evaluation Harness

### 6.1 ADK's Existing Evaluation Architecture

**Source:** `src/google/adk/evaluation/`

ADK has a mature evaluation framework:

**Data model:**

- `EvalSet` → Pydantic model containing multiple `EvalCase` objects
- `EvalCase` → multi-turn conversation with expected tool trajectories, intermediate agent responses, and reference final responses
- `EvalSetsManager` / `InMemoryEvalSetsManager` / `LocalEvalSetsManager` → dataset CRUD

**Evaluation service:**

- `LocalEvalService` → orchestrates inference (running the agent) + evaluation (scoring)
- `EvaluationGenerator` → runs agent turn-by-turn, intercepts tool calls for mocking via `mock_tool_output`
- `InferenceConfig` / `InferenceRequest` → controls agent inference
- `EvaluateConfig` / `EvaluateRequest` → controls metric evaluation

**Built-in evaluators via `MetricEvaluatorRegistry`:**

- `TrajectoryEvaluator` → compares actual vs expected tool call sequences
- `ResponseEvaluator` → ROUGE (`response_match_score`) + LLM-as-judge (`response_evaluation_score`)
- `_CustomMetricEvaluator` → user-provided evaluation functions

**Built-in metrics (`PrebuiltMetrics`):**

- `tool_trajectory_avg_score` — 1.0 = perfect trajectory match
- `response_match_score` — ROUGE text similarity
- `response_evaluation_score` — LLM-as-judge (source notes: "not very stable")

**Infrastructure:**

- `num_runs` — run each case multiple times, aggregate scores
- `EvalCaseResult` → per-case results with per-metric breakdowns and `EvalStatus`
- `LlmBackedUserSimulatorCriterion` + `UserSimulatorProvider` → dynamic multi-turn evals
- File formats: `.test.json` (single-case) and `.evalset.json` (multi-case, Pydantic-backed)
- CLI: `adk eval <agent_path> <eval_set_file>`
- Web UI: interactive eval creation, golden dataset capture, trace-linked inspection

### 6.2 The Design Principle: Fluent API Over ADK's Eval Infrastructure

adk-fluent's evaluation layer compiles to ADK's native `EvalSet`/`LocalEvalService`, just as the agent builder compiles to native ADK agents. It extends where ADK has gaps (sub-graph targeting, typed state assertions, regression detection, per-tag aggregation, cost tracking) without replacing the evaluation engine, the metrics, or the file formats.

### 6.3 `FluentEvalSuite`

```python
from adk_fluent.eval import FluentEvalSuite, FluentCase, PrebuiltMetrics

suite = FluentEvalSuite(
    name="billing_pipeline_v2",
    pipeline=pipeline,
    cases=[
        FluentCase(
            input="My bill is $200 too high",
            expected_trajectory=["classify_intent", "create_ticket"],
            expected_response_contains="ticket",
            tags=["billing", "dispute"],
        ),
        FluentCase(
            input="I want a refund for my last order",
            expected_trajectory=["classify_intent", "process_refund"],
            tags=["billing", "refund"],
        ),
        FluentCase(
            input="How do I reset my password?",
            expected_trajectory=["classify_intent", "lookup_docs"],
            tags=["technical"],
        ),
    ],
    metrics=[
        PrebuiltMetrics.TOOL_TRAJECTORY_AVG_SCORE,
        PrebuiltMetrics.RESPONSE_EVALUATION_SCORE,
    ],
    thresholds={
        PrebuiltMetrics.TOOL_TRAJECTORY_AVG_SCORE: 1.0,
        PrebuiltMetrics.RESPONSE_EVALUATION_SCORE: 0.7,
    },
    num_runs=2,
)
```

### 6.4 `FluentCase` → `EvalCase` Compilation

```python
@dataclass
class FluentCase:
    input: str | list[str]                          # Single turn or multi-turn
    expected_trajectory: list[str] | None = None     # Tool call sequence
    expected_response_contains: str | None = None    # Substring match
    reference_response: str | None = None            # Full reference for ROUGE/LLM-judge
    mock_tool_outputs: dict[str, Any] | None = None  # Tool name → mock return value
    initial_state: dict[str, Any] | None = None      # Pre-populated session state
    tags: list[str] = field(default_factory=list)     # For grouping in report
    target_node: str | None = None                    # Sub-graph targeting (§6.8)
    state_assertions: dict[str, Any] | None = None   # Verify intermediate state
    metadata: dict[str, Any] = field(default_factory=dict)
```

Compilation builds ADK-native `EvalCase` objects:

```python
def _to_eval_case(self, case: FluentCase) -> EvalCase:
    turns = case.input if isinstance(case.input, list) else [case.input]
    conversation = []
    for i, turn_input in enumerate(turns):
        invocation = Invocation(
            user_content=Content(role="user", parts=[Part.from_text(turn_input)]),
        )
        if case.expected_trajectory and i == len(turns) - 1:
            invocation.expected_tool_use = [
                ToolUse(tool_name=name) for name in case.expected_trajectory
            ]
        if case.mock_tool_outputs:
            for tool_name, output in case.mock_tool_outputs.items():
                for tu in (invocation.expected_tool_use or []):
                    if tu.tool_name == tool_name:
                        tu.mock_tool_output = output
        if case.reference_response and i == len(turns) - 1:
            invocation.reference = case.reference_response
        conversation.append(invocation)

    return EvalCase(
        eval_id=case.metadata.get("id", str(uuid.uuid4())),
        conversation=conversation,
        initial_session=InitialSession(state=case.initial_state or {}),
    )
```

### 6.5 Execution via `LocalEvalService`

```python
class FluentEvalSuite:
    async def run(self, **kwargs) -> FluentEvalReport:
        agent = self.pipeline.to_agent()
        eval_set = EvalSet(
            eval_set_id=self.name,
            eval_cases=[self._to_eval_case(c) for c in self.cases],
        )

        eval_sets_manager = InMemoryEvalSetsManager()
        await eval_sets_manager.create_eval_set(app_name="_fluent", eval_set=eval_set)

        eval_service = LocalEvalService(
            root_agent=agent,
            eval_sets_manager=eval_sets_manager,
            session_service=kwargs.get("session_service", InMemorySessionService()),
            artifact_service=kwargs.get("artifact_service"),
        )

        eval_metrics = [
            EvalMetric(metric_name=m.value, threshold=self.thresholds.get(m, 0.5))
            for m in self.metrics
        ]

        for judge in self._custom_judges:
            self._register_judge(judge, DEFAULT_METRIC_EVALUATOR_REGISTRY)

        case_results = await eval_service.evaluate(
            EvaluateRequest(
                app_name="_fluent",
                eval_set_id=self.name,
                eval_case_ids=[c.eval_id for c in eval_set.eval_cases],
                eval_config=EvaluateConfig(eval_metrics=eval_metrics, num_runs=self.num_runs),
            )
        )

        return FluentEvalReport(case_results=case_results, fluent_cases=self.cases)
```

### 6.6 `FluentEvalReport` — Extends `EvalCaseResult`

```python
@dataclass
class FluentEvalReport:
    case_results: list[EvalCaseResult]  # ADK native — pass-through
    fluent_cases: list[FluentCase]

    @property
    def pass_rate(self) -> float:
        passed = sum(1 for r in self.case_results if r.final_eval_status == EvalStatus.PASSED)
        return passed / len(self.case_results) if self.case_results else 0.0

    @property
    def per_tag(self) -> dict[str, TagSummary]:
        """Aggregate metrics by FluentCase.tags — not available in ADK natively."""
        tag_groups: dict[str, list[EvalCaseResult]] = defaultdict(list)
        for case, result in zip(self.fluent_cases, self.case_results):
            for tag in case.tags:
                tag_groups[tag].append(result)
        return {tag: TagSummary.from_results(results) for tag, results in tag_groups.items()}

    def compare(self, baseline: 'FluentEvalReport') -> RegressionReport:
        """Regression detection against a baseline."""
        regressed, improved = [], []
        for current, base in zip(self.case_results, baseline.case_results):
            if current.final_eval_status == EvalStatus.FAILED and base.final_eval_status == EvalStatus.PASSED:
                regressed.append(current)
            elif current.final_eval_status == EvalStatus.PASSED and base.final_eval_status == EvalStatus.FAILED:
                improved.append(current)
        return RegressionReport(regressed=regressed, improved=improved)

    def to_markdown(self) -> str: ...
    def to_json(self) -> str: ...
    def save(self, path: str) -> None: ...

    @classmethod
    def load(cls, path: str) -> 'FluentEvalReport': ...
```

### 6.7 Custom Judges → ADK `MetricEvaluatorRegistry`

```python
from adk_fluent.eval import FluentJudge

def my_domain_judge(actual_response: str, reference: str | None, tool_trajectory: list[str]) -> float:
    """Returns 0.0-1.0 score."""
    ...

suite = FluentEvalSuite(
    pipeline=pipeline,
    cases=[...],
    metrics=[PrebuiltMetrics.TOOL_TRAJECTORY_AVG_SCORE],
    custom_judges=[FluentJudge(name="domain_quality", fn=my_domain_judge, threshold=0.8)],
)
```

**Compilation:** `FluentJudge` wraps the function in ADK's `Evaluator` interface and registers it into `MetricEvaluatorRegistry`. This makes custom judges compatible with ADK's entire eval pipeline — they're invoked by `LocalEvalService` alongside built-in evaluators.

### 6.8 Sub-Graph Targeting

ADK evaluates the full agent tree. adk-fluent adds evaluation of isolated sub-graphs:

```python
FluentCase(
    input="My bill is $200 too high",
    target_node="classifier",
    expected_trajectory=["classify_intent"],
    state_assertions={"intent": "billing_dispute", "confidence": lambda v: v > 0.8},
)
```

When `target_node` is set, `FluentEvalSuite.run()` extracts the sub-graph from the pipeline IR, compiles only that sub-graph to a native agent, and evaluates against it.

### 6.9 Typed State Assertions

When a `StateSchema` (§1) is available:

```python
FluentCase(
    input="Refund my order",
    state_assertions={
        BillingState.intent: "refund",
        BillingState.confidence: lambda v: v > 0.8,
    },
)
```

State assertions are checked by a middleware injected during eval runs that captures `state_delta` after each agent and validates against assertions. This is an adk-fluent addition — ADK's evaluation only checks trajectories and final responses.

### 6.10 User Simulation

ADK's `UserSimulatorProvider` with `LlmBackedUserSimulatorCriterion` enables LLM-simulated users. v5 exposes via fluent API:

```python
from adk_fluent.eval import FluentEvalSuite, UserSimulation

suite = FluentEvalSuite(
    pipeline=pipeline,
    simulation=UserSimulation(
        model="gemini-2.5-flash",
        persona="Frustrated customer, provides order info reluctantly",
        success_criteria="Agent processes refund within 5 turns",
        stop_signal="</finished>",
        max_turns=10,
    ),
    metrics=[PrebuiltMetrics.TOOL_TRAJECTORY_AVG_SCORE],
)
```

Compiles to ADK's `UserSimulatorProvider` configuration. The persona becomes the simulator's system prompt. The stop signal maps to `LlmBackedUserSimulatorCriterion.stop_signal`.

### 6.11 File Format Interop

```python
# Load ADK-native eval sets
suite = FluentEvalSuite.from_eval_set("billing.evalset.json", pipeline=pipeline)

# Load from fluent YAML
suite = FluentEvalSuite.from_yaml("eval/billing_cases.yaml", pipeline=pipeline)

# Export to ADK-native format (compatible with `adk eval` CLI and web UI)
suite.to_eval_set_file("billing.evalset.json")
```

```yaml
# eval/billing_cases.yaml
name: billing_pipeline_v2
metrics: [tool_trajectory_avg_score, response_evaluation_score]
thresholds:
  tool_trajectory_avg_score: 1.0
  response_evaluation_score: 0.7
num_runs: 2
cases:
  - input: "My bill is $200 too high"
    expected_trajectory: [classify_intent, create_ticket]
    tags: [billing, dispute]
  - input: "I want a refund"
    expected_trajectory: [classify_intent, process_refund]
    tags: [billing, refund]
```

### 6.12 CLI Compatibility

Because `FluentEvalSuite` compiles to native `EvalSet`, output is compatible with ADK's CLI:

```bash
python -c "from my_pipeline import suite; suite.to_eval_set_file('billing.evalset.json')"
adk eval my_agent/ billing.evalset.json --num_runs 3 --print_detailed_results
```

______________________________________________________________________

## 7. Multi-Modal Content Contracts

### 7.1 `ContentSpec`

```python
@dataclass(frozen=True)
class ContentSpec:
    input_modalities: frozenset[Modality] = frozenset({Modality.TEXT})
    output_modalities: frozenset[Modality] = frozenset({Modality.TEXT})
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None

class Modality(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    STRUCTURED = "structured"
    CODE = "code"
```

### 7.2 Builder API

```python
agent = (
    Agent("vision_analyzer", "gemini-2.5-pro")
    .accepts(Modality.IMAGE, Modality.TEXT)
    .produces_modality(Modality.TEXT, Modality.STRUCTURED)
)
```

### 7.3 Contract Checking

Verifies that producer output modalities are accepted by downstream consumers. Mismatches flagged at build time.

______________________________________________________________________

## 8. Event Replay and Time-Travel Debugging

### 8.1 Built on ADK's Capture Infrastructure

ADK's telemetry already provides `InMemoryExporter` (spans by session ID) and `ApiServerSpanExporter` (spans by event ID). The `call_llm` span captures request/response when content capture is enabled. adk-fluent's `Recorder` builds on this.

### 8.2 `Recorder`

```python
from adk_fluent.debug import Recorder

recorder = Recorder(capture_content=True, capture_state=True)
events = await pipeline.run("test", middleware=[recorder])
recorder.save("recordings/issue_1234.json")
```

**Implementation:**

```python
class Recorder:
    def __init__(self, capture_content=True, capture_state=True):
        self._span_exporter = InMemorySpanExporter()
        self._events: list[AgentEvent] = []
        self._state_snapshots: list[dict] = []

    def install(self, tracer_provider: TracerProvider):
        """Add our exporter alongside ADK's existing exporters."""
        tracer_provider.add_span_processor(SimpleSpanProcessor(self._span_exporter))

    async def on_event(self, ctx: Context, event: AgentEvent) -> None:
        self._events.append(event)
        if self._capture_state:
            self._state_snapshots.append(dict(ctx.state.to_dict()))
        return None

    def get_recording(self) -> Recording:
        return Recording(
            events=self._events,
            spans=self._span_exporter.get_finished_spans(),
            state_snapshots=self._state_snapshots,
        )
```

### 8.3 `Recording` Format

```python
@dataclass
class Recording:
    pipeline_ir_hash: str
    events: list[AgentEvent]
    spans: list[ReadableSpan]           # OTel spans from ADK's tracing
    state_snapshots: list[dict]
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_llm_interactions(self) -> list[LLMInteraction]:
        """Extract from call_llm spans."""
        return [
            LLMInteraction(
                agent_name=span.attributes.get("gen_ai.agent.name"),
                model=span.attributes.get("gen_ai.request.model"),
                request_content=span.attributes.get("gen_ai.request.messages"),
                response_content=span.attributes.get("gen_ai.response.messages"),
                latency_ms=span.end_time - span.start_time,
            )
            for span in self.spans if span.name == "call_llm"
        ]

    def get_tool_interactions(self) -> list[ToolInteraction]:
        """Extract from execute_tool spans."""
        return [
            ToolInteraction(
                tool_name=span.attributes.get("gen_ai.tool.name"),
                call_id=span.attributes.get("gen_ai.tool.call.id"),
            )
            for span in self.spans if span.name == "execute_tool"
        ]
```

### 8.4 `ReplayerBackend`

Uses recorded `call_llm` span data for deterministic LLM responses. On mismatch: `error` (raise), `skip` (return empty), or `live` (real call).

### 8.5 Event Stream Diff

```python
from adk_fluent.debug import diff_events
diff = diff_events(recording.events, new_events)
print(diff.summary)
```

______________________________________________________________________

## 9. Execution Boundaries for Distributed Pipelines

### 9.1 `ExecutionBoundary`

```python
@dataclass(frozen=True)
class ExecutionBoundary:
    serialization: Literal["json", "protobuf", "arrow"] = "json"
    transport: TransportConfig | None = None
    isolation: Literal["none", "process", "container"] = "none"
    scaling: ScalingConfig | None = None
```

### 9.2 Builder API

```python
pipeline = (
    Agent("classifier")
    >> Agent("heavy_processor")
        .execution_boundary(
            transport=TransportConfig(type="queue", endpoint="pubsub://projects/my-proj/topics/heavy"),
            scaling=ScalingConfig(max_instances=20),
        )
    >> Agent("responder")
)
```

### 9.3 Compilation

Backend splits pipeline at boundaries into separate `App` objects. Each independently deployable with its own `ResumabilityConfig`. State serialization uses `StateSchema` when available.

______________________________________________________________________

## 10. Unified Contract Checker

```python
from adk_fluent.contracts import check_all, ContractReport

report = check_all(pipeline.build(), schema=BillingState)
```

**Checker registry:**

```python
_CHECKERS = [
    check_dataflow_contracts,      # reads-after-writes
    check_type_contracts,          # typed state matching
    check_streaming_contracts,     # streaming edge validation
    check_modality_contracts,      # content type matching
    check_boundary_contracts,      # serialization at boundaries
    check_a2a_contracts,           # remote agent input satisfaction
    check_cost_contracts,          # budget bounds present
]

def register_checker(fn: Callable) -> None:
    _CHECKERS.append(fn)
```

______________________________________________________________________

## 11. Updated Middleware

### 11.1 Built-In Middleware — v5

```python
from adk_fluent.middleware import (
    token_budget, cache, rate_limiter,           # Model-layer
    retry, circuit_breaker,                       # Error-layer
    tool_approval,                                # Tool-layer
    otel_enrichment,                              # REPLACES structured_log (§5.3)
    cost_attribution,                             # OTel metrics (§3.5)
    pii_filter,                                   # Privacy
    recorder,                                     # Debug (§8.2)
)
```

**Removed:** `structured_log` → replaced by `otel_enrichment`.\
**Removed:** `cost_tracker` → replaced by `cost_attribution` with OTel metrics.

______________________________________________________________________

## 12. Module Architecture

```
adk_fluent/
  __init__.py              # Layer 0: Agent, Pipeline, FanOut, Loop, S, Route, RemoteAgent
  _ir.py  _base.py  _operators.py  _transforms.py  _routing.py  _helpers.py  _presets.py

  state/                   # §1: Typed State
    _schema.py  _field_ref.py  _proxy.py

  cost/                    # §3: Cost Routing
    _model.py  _selector.py  _estimator.py

  a2a/                     # §4: A2A Interop
    _remote.py  _card.py  _client.py  _server.py  _directory.py

  telemetry/               # §5: OTel Enrichment (not duplication)
    _enrichment.py  _metrics.py  _config.py

  eval/                    # §6: Fluent API over ADK's eval module
    _suite.py  _case.py  _judge.py  _report.py  _simulation.py  _loader.py  _state_assertions.py

  debug/                   # §8: Built on ADK's InMemoryExporter
    _recorder.py  _recording.py  _replayer.py  _diff.py

  streaming/               # §2: Edge Semantics
    _edge.py  _adapters.py

  content/                 # §7: Multi-Modal
    _spec.py  _validation.py

  distributed/             # §9: Execution Boundaries
    _boundary.py  _serialization.py  _segmenter.py

  contracts/               # §10: Unified Checker
    _checker.py  _dataflow.py  _types.py  _streaming.py  _modality.py
    _boundary.py  _a2a.py  _cost.py  _registry.py

  backends/
    _protocol.py  adk.py  mock.py  trace.py  viz.py  dry_run.py  replay.py

  middleware/
    _protocol.py  _plugin_adapter.py  token_budget.py  cache.py  rate_limiter.py
    retry.py  circuit_breaker.py  tool_approval.py  otel_enrichment.py
    cost_attribution.py  pii_filter.py  recorder.py

  testing/
    mock_backend.py  contracts.py  harness.py  pytest_plugin.py

  generated/
    _ir_nodes.py  _builders.py  _adk_compile.py

  _codegen/
    ir_generator.py  builder_generator.py  backend_generator.py  diff_report.py
```

______________________________________________________________________

## 13. Migration Path

### Phase 1–4: v4 Phases (Retained)

### Phase 5a: Typed State (Foundation)

### Phase 5b: Telemetry Integration (Must precede 5c, 5f, 5g)

1. `OTelEnrichmentMiddleware` — annotate ADK's spans
1. OTel metric definitions
1. `TelemetryConfig` pass-through
1. Replace `structured_log` → `otel_enrichment`, `cost_tracker` → `cost_attribution`

### Phase 5c: Cost-Aware Routing (Depends on 5b)

### Phase 5d: Streaming Edge Semantics

### Phase 5e: A2A Interop (Parallel Track)

### Phase 5f: Evaluation Harness (Depends on 5a, 5b)

1. `FluentEvalSuite` → `EvalSet`/`LocalEvalService` compilation
1. `FluentCase` → `EvalCase` conversion
1. `FluentJudge` → `MetricEvaluatorRegistry` registration
1. `FluentEvalReport` wrapping `EvalCaseResult` + tags/regression
1. `UserSimulation` → `UserSimulatorProvider` compilation
1. File format interop (`.evalset.json` ↔ fluent YAML)
1. Sub-graph targeting and typed state assertions

### Phase 5g: Replay (Depends on 5b)

### Phase 5h: Execution Boundaries

______________________________________________________________________

## 14. Design Principles

### 14.1 The Tide Principle (Strengthened)

> If ADK gets better, adk-fluent gets better for free.

v5 extends this explicitly to **telemetry** (enrich ADK's OTel spans), **evaluation** (compile to ADK's `EvalSet`/`LocalEvalService`), and **cost** (emit via OTel).

### 14.2 Progressive Disclosure

| Level | Imports                  | Capability                              |
| ----- | ------------------------ | --------------------------------------- |
| 0     | `adk_fluent`             | Agent, Pipeline, FanOut, Loop, S, Route |
| 1     | `adk_fluent.config`      | ExecutionConfig, TelemetryConfig        |
| 2     | `adk_fluent.middleware`  | Built-in middleware                     |
| 3     | `adk_fluent.state`       | StateSchema, typed state                |
| 4     | `adk_fluent.cost`        | Cost modeling, model selection          |
| 5     | `adk_fluent.eval`        | Evaluation (fluent API over ADK's eval) |
| 6     | `adk_fluent.a2a`         | Remote agents, Agent Cards              |
| 7     | `adk_fluent.debug`       | Recording, replay (built on ADK's OTel) |
| 8     | `adk_fluent.distributed` | Execution boundaries                    |

### 14.3 Dry Run Your Architecture

Every production concern is verifiable before a single LLM call.

### 14.4 Zero Surprise

- `FluentEvalSuite` compiles to ADK's `EvalSet` (compatible with `adk eval` CLI)
- `OTelEnrichmentMiddleware` annotates existing spans (no duplicate telemetry)
- `Recorder` uses ADK's `InMemoryExporter` (no parallel capture)
- `CostAttributionMiddleware` emits OTel metrics (visible in Cloud Monitoring)

______________________________________________________________________

## 15. Success Criteria

v4 criteria retained. v5 adds:

| #   | Criterion                                       | Measurement                                     |
| --- | ----------------------------------------------- | ----------------------------------------------- |
| 8   | Typed state catches errors at build time        | Zero runtime `KeyError` in typed pipelines      |
| 9   | Cost estimation within 20% of actual            | `estimate_cost()` vs OTel `adk_fluent.llm.cost` |
| 10  | Eval runs via ADK's `LocalEvalService`          | Valid `EvalCaseResult` objects produced         |
| 11  | Eval output compatible with `adk eval` CLI      | `.to_eval_set_file()` runnable by `adk eval`    |
| 12  | No duplicate telemetry                          | Span count with middleware ≤ span count without |
| 13  | `adk_fluent.*` attributes visible in ADK web UI | Appear in `/debug/trace/:event_id`              |
| 14  | Replay deterministic                            | Empty diff on unmodified pipeline replay        |
| 15  | `check_all()` < 100ms                           | 100-node graphs                                 |

______________________________________________________________________

## 16. Performance Budgets

| Operation                              | Budget              |
| -------------------------------------- | ------------------- |
| IR compilation (100 nodes)             | < 50ms              |
| Contract checking (100 nodes, full v5) | < 100ms             |
| Cost estimation (100 nodes)            | < 10ms              |
| Backend compile (100 nodes → ADK App)  | < 200ms             |
| Runtime dispatch overhead per event    | < 1% of LLM latency |
| OTel enrichment per span               | < 0.5ms             |
| State schema bind() per access         | < 0.1ms             |
| FluentCase → EvalCase compilation      | < 1ms per case      |
| Test suite (1000 tests, mock)          | < 10s               |
| Eval suite (100 cases, mock)           | < 60s               |

______________________________________________________________________

## 17. Compatibility Matrix

| ADK Version | adk-fluent v5            | Notes                                                  |
| ----------- | ------------------------ | ------------------------------------------------------ |
| v1.25.0+    | Full support             | Baseline                                               |
| v1.24.x     | Core, no error callbacks | `on_model_error_callback` unavailable                  |
| v1.23.x     | Core, limited eval       | `MetricEvaluatorRegistry` available                    |
| v1.22.x     | Core, basic eval         | `AgentEvaluator.evaluate()` only                       |
| < v1.22.0   | Not supported            | Missing eval module and OTel Semantic Conventions 1.37 |

**Behavioral changes requiring manual review:**

- `@final` on `BaseAgent.run_async()` — breaks custom agent compilation
- `PluginManager` execution order — breaks middleware priority
- `State._delta` semantics — breaks state transforms
- OTel span names (`call_llm`, `execute_tool`) — breaks Recorder span extraction
- `MetricEvaluatorRegistry` API — breaks FluentJudge compilation
- `EvalCase`/`EvalSet` Pydantic schema — breaks FluentCase compilation

______________________________________________________________________

## Appendix A: Architectural Decision Records

### ADR-001: Why Middleware Compiles to Plugins, Not Agent Callbacks

**Decision:** Compile to plugins. **Rationale:** ADK executes plugins first, then agent callbacks. Middleware (rate limiting, auth) must run first. Compiling to agent callbacks inverts priority.

### ADR-002: Why StateSchema Uses Annotations, Not Pydantic Subclassing

**Decision:** Custom `StateSchema` with `Annotated` hints. **Rationale:** ADK's `State` is a dict wrapper with delta tracking. Pydantic would create impedance mismatch — the schema wants to own data, but `State` must own it for delta tracking. `StateSchema` is a typed lens over the dict.

### ADR-003: Why A2A Compiles to BaseAgent, Not a Tool

**Decision:** `BaseAgent` subclass. **Rationale:** A2A agents produce event streams, support streaming, manage state. Tools are single request/response. BaseAgent subclasses participate in full ADK lifecycle.

### ADR-004: Why Evaluation Is Not Just Testing

**Decision:** Separate `eval/` subsystem built on ADK's infrastructure. **Rationale:** Testing verifies mechanics; evaluation verifies behavior. Different lifecycles, different consumers. The evaluation *engine* should not be duplicated.

### ADR-005: Why Edge Semantics Are IR-Level, Not Middleware

**Decision:** IR annotations. **Rationale:** Streaming affects execution structure, not just observation. Middleware runs after events are yielded — too late to buffer.

### ADR-006: Why Execution Boundaries Split Into Separate Apps

**Decision:** Separate `App` objects. **Rationale:** Independent deployment, scaling, resumability. ADK's `ResumabilityConfig` works at App level.

### ADR-007: Why Telemetry Enriches ADK's Spans, Not Creates Parallel Ones

**Context:** adk-fluent needs observability for pipeline-level concerns. Options: (a) new spans, (b) structured logs, (c) enrichment of existing spans.

**Decision:** Enrich existing spans + OTel metrics for adk-fluent-specific counters.

**Rationale:** ADK's telemetry (`src/google/adk/telemetry/tracing.py`) creates spans at every lifecycle point: `invocation`, `invoke_agent`, `call_llm`, `execute_tool`, following OTel Semantic Conventions 1.37. Creating additional spans doubles storage, confuses trace visualization, creates ambiguity about authoritative timing. Enrichment via `trace.get_current_span().set_attribute()` adds metadata without duplication. OTel metrics handle aggregatable data (cost, violations).

**Rejected:** `structured_log` middleware — duplicates OTel span data, lacks correlation.
**Rejected:** Parallel `Recorder` capture — now rebuilt on `InMemoryExporter` for span data.

### ADR-008: Why Evaluation Wraps ADK's Eval Module, Not Replaces It

**Context:** adk-fluent needs evaluation capability. Options: (a) independent framework, (b) fluent API over ADK's eval infrastructure.

**Decision:** Fluent API over ADK's `EvalSet`/`LocalEvalService`/`MetricEvaluatorRegistry`.

**Rationale:** ADK's eval module is substantial: `LocalEvalService` orchestrates multi-turn inference with tool mocking; `TrajectoryEvaluator`/`ResponseEvaluator` provide built-in metrics; `MetricEvaluatorRegistry` supports custom evaluators; `UserSimulatorProvider` enables LLM-simulated users; `num_runs` aggregation; `.evalset.json` Pydantic format; web UI golden dataset capture. Building parallel versions means double maintenance, CLI incompatibility, missing user simulation, re-implementing trajectory evaluation. The fluent API adds what ADK lacks (sub-graph targeting, typed state assertions, tag aggregation, regression reports) while delegating hard problems to ADK.

**Rejected:** Independent `EvalSuite` with own `Case`/`Judge`/`Report`. Violates Tide Principle.

______________________________________________________________________

## Appendix B: Glossary

| Term                  | Definition                                                              |
| --------------------- | ----------------------------------------------------------------------- |
| **IR**                | Intermediate Representation — frozen dataclass graph before compilation |
| **Backend**           | Protocol that compiles IR to a runnable and executes it                 |
| **Middleware**        | Composable cross-cutting behavior, compiled to an ADK plugin            |
| **StateSchema**       | Typed declaration of pipeline state with scope annotations              |
| **ContentSpec**       | Declaration of agent input/output modalities                            |
| **EdgeSemantics**     | How data flows between IR nodes (buffering, merge strategy)             |
| **ExecutionBoundary** | IR annotation for distributed pipeline splitting                        |
| **AgentEvent**        | Backend-agnostic representation of an ADK Event                         |
| **AgentCard**         | A2A capability advertisement from pipeline IR                           |
| **Recording**         | Captured events + OTel spans for deterministic replay                   |
| **FluentEvalSuite**   | Fluent builder compiling to ADK's `EvalSet`/`LocalEvalService`          |
| **FluentCase**        | Evaluation case compiling to ADK's `EvalCase`                           |
| **FluentJudge**       | Custom evaluator registering into ADK's `MetricEvaluatorRegistry`       |
| **OTel Enrichment**   | Adding adk-fluent metadata to ADK's existing OTel spans                 |
| **Seed-based IR**     | IR nodes generated from ADK's Pydantic model introspection              |

______________________________________________________________________

*"v4 made the IR the product. v5 makes the IR a complete model of production agent systems — but only by extending ADK's own infrastructure for telemetry and evaluation, not by rebuilding it. The Tide Principle is not just about agent compilation. It applies everywhere."*
