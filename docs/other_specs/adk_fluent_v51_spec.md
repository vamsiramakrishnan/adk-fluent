# ADK-FLUENT: Specification v5.1 — Context-Aware Agent Composition

**Status:** Supersedes SPEC_v5.md\
**ADK Baseline:** google-adk v1.25.0+ (`adk-python` main branch, Feb 2026)\
**Philosophy:** The expression graph is the product. ADK is one backend. The IR evolves with ADK automatically. Every cross-cutting concern — telemetry, evaluation, context — extends ADK's existing infrastructure rather than replacing it.\
**Architecture:** Expression IR → Backend Protocol → ADK (or anything else)

______________________________________________________________________

## 0. Preamble: What Changed Since v5

v5 established typed state, streaming edges, cost routing, A2A, telemetry, evaluation, multi-modal, replay, and execution boundaries. These are retained in full.

v5.1 addresses the foundational problem that v5 left unmodeled: **agents in a DAG don't just execute in sequence — each agent has a different view of the world, and that view must be engineered.** ADK provides three independent communication channels (conversation history, session state, instruction templating) with minimal coordination between them. Developers manage this coordination manually. Most don't realize the coordination is needed.

| v5 State                                      | v5.1 Change                                                                                      | Rationale                                                                                           |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `include_contents` is binary (all or nothing) | **Context Engineering (C module)**: declarative content transforms per agent                     | ADK's two-mode switch is insufficient for DAG composition; downstream agents need selective context |
| `output_key` is a storage mechanism           | **`.outputs()` as role declaration**: data producer semantics for visibility, context, contracts | output_key duplicates text into state AND conversation; the library should manage the coordination  |
| All events reach client                       | **Event Visibility**: topology-inferred presentation filtering via `on_event_callback` plugin    | Intermediate agent outputs leak to users; topology determines which agents are user-facing          |
| Contract checking is state-only               | **Cross-channel contract validation**: state + contents + instructions analyzed together         | A state contract can pass while the developer loses data because include_contents is wrong          |
| S module transforms state between agents      | **S module + C module**: state transforms AND content transforms as orthogonal capabilities      | State is one of three channels; the library needs to address all three                              |

v5's sections on streaming, cost routing, A2A, telemetry, evaluation, multi-modal, replay, and execution boundaries are **incorporated by reference** and not repeated. Their section numbers are preserved.

______________________________________________________________________

## 1. ADK's Three Communication Channels

This section establishes the foundational model that Context Engineering, State, and Event Visibility build upon. All claims are source-verified against `google-adk v1.25.0`.

### 1.1 The Channels

ADK provides three independent mechanisms for agents to communicate:

**Channel 1 — Conversation History.** All events (user messages, agent responses, tool calls) are appended to `session.events` by `Runner._exec_with_plugin` via `session_service.append_event()`. When the next agent runs, `contents.request_processor` calls `_get_contents()` which assembles these events into the `LlmRequest.contents` list — the conversational turn history the LLM sees. Controlled by `include_contents`: `'default'` (full history) or `'none'` (current turn only). Binary. No selective filtering.

**Channel 2 — Session State.** Flat key-value dictionary at `session.state`. Written via `output_key` (automatic: `__maybe_save_output_to_state` copies LLM text to `event.actions.state_delta`), direct mutation (`ctx.session.state[k] = v`), or event-carried state deltas. Scoped: unprefixed (session), `app:`, `user:`, `temp:`. The `S` module provides transforms over this channel.

**Channel 3 — Instruction Templating.** `inject_session_state()` replaces `{key}` placeholders in instruction strings with `session.state[key]` values. Runs every invocation, just before the LLM call. This is the bridge: Channel 2 values appear inside the system prompt.

### 1.2 The Entanglement Problem

These channels are configured independently but converge on one LLM prompt. In `classifier >> booker`:

```
classifier (output_key="intent") produces "booking":
  → Channel 1: "booking" appended to session.events
  → Channel 2: session.state["intent"] = "booking"

booker (instruction="Help book. Intent: {intent}") runs:
  → Channel 1: LLM context includes classifier's "booking" in conversation
  → Channel 3: instruction becomes "Help book. Intent: booking"
  → booker's LLM sees "booking" TWICE
```

This duplication is the natural consequence of three channels converging on one prompt. ADK doesn't coordinate them because in single-agent systems there's nothing to coordinate. In multi-agent DAGs, the developer must manage this manually.

### 1.3 The include_contents Gap

Source-verified behavior of `include_contents='none'`:

```python
# contents.py - _get_current_turn_contents
for i in range(len(events) - 1, -1, -1):
    event = events[i]
    if event.author == 'user' or _is_other_agent_reply(agent_name, event):
        return _get_contents(branch, events[i:], agent_name, ...)
```

It scans backward for the most recent user message or other-agent reply and includes events from that point forward. In a pipeline, the previous agent's output is the "other-agent reply." The user's original message may be lost.

There is no `include_contents='user_only'`, no `include_contents='exclude_agents'`, no selective filtering. ADK has no mechanism for topology-aware content assembly.

### 1.4 The output_key Reality

Source-verified: `output_key` **duplicates**, it does not **route**.

```python
# LlmAgent._run_async_impl
async for event in self._llm_flow.run_async(ctx):
    self.__maybe_save_output_to_state(event)  # mutates event.actions.state_delta
    yield event  # yields event WITH content AND state_delta
```

The event still carries full text content. `append_event` then applies `state_delta` to session state AND appends the event to session history. Downstream agents get the classifier's text through both Channel 1 (conversation) and Channel 2 (state).

### 1.5 The InstructionProvider Escape Hatch

ADK's `InstructionProvider` is a callable receiving `ReadonlyContext` that returns an instruction string. When used, `bypass_state_injection` is set — the library won't do `{key}` replacement. Critically, `ReadonlyContext` provides:

- `ctx.state` — read-only view of session state (Channel 2)
- `ctx.session.events` — full event history (Channel 1)
- `ctx.user_content` — the user message that started this invocation

This means an `InstructionProvider` can read all three channels and assemble context however it wants. Combined with `include_contents='none'` (which suppresses default content assembly), this gives complete control over what the LLM sees.

This is the compilation target for Context Engineering.

______________________________________________________________________

## 2. Context Engineering — The C Module

### 2.1 The Idea

The `S` module transforms state between agents (Channel 2). The `C` module transforms context — what each agent sees from conversation history (Channel 1) and how that history is assembled into the prompt.

Together, `S` and `C` form the information-flow DAG that sits inside the execution DAG. The execution DAG says "classifier runs before booker." The information-flow DAG says "booker sees the user's message and the intent from state, but not the classifier's raw text."

### 2.2 C Transforms

```python
from adk_fluent import C
```

**Content Filters** — what events to include in the agent's context:

| Transform                        | Effect                                                      | Compiles To                                     |
| -------------------------------- | ----------------------------------------------------------- | ----------------------------------------------- |
| `C.default()`                    | Full conversation history                                   | `include_contents='default'`                    |
| `C.none()`                       | No conversation history; all context from state/instruction | `include_contents='none'`                       |
| `C.user_only()`                  | Only user messages (exclude all intermediate agent outputs) | InstructionProvider + `include_contents='none'` |
| `C.from_agents("a", "b")`        | User messages + outputs from named agents only              | InstructionProvider + `include_contents='none'` |
| `C.exclude_agents("classifier")` | Full history minus named agents                             | InstructionProvider + `include_contents='none'` |
| `C.last_n_turns(n)`              | Only the last N user-agent turn pairs                       | InstructionProvider + `include_contents='none'` |

**Context Captures** — bridge conversation into state for downstream agents:

| Transform                         | Effect                                             | Compiles To                         |
| --------------------------------- | -------------------------------------------------- | ----------------------------------- |
| `C.capture("user_message")`       | Snapshot latest user message text into state       | FnAgent reading from session.events |
| `C.capture_turns("history", n=5)` | Snapshot last N turns as formatted text into state | FnAgent reading from session.events |

**Context Templates** — declare exactly what the agent should see:

```python
C.template("""
User request: {user_message}
Classification: {intent} (confidence: {confidence})
Previous attempts: {attempt_history?}
""")
```

Compiles to an InstructionProvider that prepends the rendered template to the developer's instruction. Uses `{key}` for required state, `{key?}` for optional (empty string if missing). Combined with `include_contents='none'`.

### 2.3 Usage Patterns

**Pattern 1: Zero-config pipeline** (inferred from topology)

```python
pipeline = (
    Agent("classifier").instruct("Classify the user's intent.").outputs("intent")
    >> Route("intent").eq("booking", booker).eq("info", info_agent)
)
```

The library infers:

- `classifier` has `.outputs("intent")` and a successor → data producer, internal visibility
- `Route` reads `"intent"` from state → contract satisfied
- `booker` is terminal → user-facing, `C.default()`
- Diagnostic: "booker will see classifier's raw text 'booking' in conversation AND 'booking' via state in instruction. Consider `C.user_only()` if instruction provides full context."

**Pattern 2: Explicit context capture**

```python
pipeline = (
    C.capture("user_message")
    >> Agent("classifier").instruct("Classify intent.").outputs("intent")
    >> Route("intent").eq("booking",
        Agent("booker")
            .instruct("Help book. Intent: {intent}")
            .context(C.from_state("user_message", "intent"))
    )
)
```

`C.capture("user_message")` snapshots the user's input to state. `C.from_state(...)` tells booker to get all its context from state variables — no conversation history needed. Compiles to `include_contents='none'` + InstructionProvider that reads `user_message` and `intent` from state.

**Pattern 3: Selective conversation**

```python
pipeline = (
    Agent("drafter").instruct("Write initial draft.")
    >> Agent("reviewer").instruct("Review the draft.").context(C.user_only())
    >> Agent("editor").instruct("Edit based on review.").context(C.from_agents("drafter", "reviewer"))
)
```

Reviewer sees user's original request but not drafter's output in conversation (gets it from context instead). Editor sees user, drafter, and reviewer — but would exclude any other intermediate agents if the pipeline were longer.

**Pattern 4: Iterative refinement**

```python
pipeline = (
    Agent("drafter").outputs("draft")
    >> loop_until(
        lambda s: s.get("approved"),
        Agent("reviewer")
            .instruct("Review: {draft}")
            .outputs("feedback")
            .context(C.from_state("draft"))
        >> Agent("refiner")
            .instruct("Refine based on feedback: {feedback}")
            .outputs("draft")
            .context(C.from_state("draft", "feedback"))
    )
    >> Agent("presenter")
        .instruct("Present the final version: {draft}")
        .context(C.from_state("draft"))
)
```

Each agent in the loop gets clean context from state. No accumulation of prior iteration outputs in conversation. Presenter only sees the final draft.

### 2.4 Compilation to ADK

**C.default()** → No transformation. `include_contents='default'`.

**C.none()** → `include_contents='none'`. No InstructionProvider needed.

**C.user_only()** and other filters → compile to an `InstructionProvider`:

```python
def _compile_context_filter(developer_instruction: str, filter_spec: CFilter) -> InstructionProvider:
    """Compile a C filter into an ADK InstructionProvider."""
    
    async def _instruction_provider(ctx: ReadonlyContext) -> str:
        # 1. Assemble filtered conversation from session events
        filtered_events = filter_spec.apply(ctx.session.events, ctx.agent_name)
        conversation_text = _format_events_as_context(filtered_events)
        
        # 2. Template the developer's instruction with state values
        instruction = _template_with_state(developer_instruction, ctx.state)
        
        # 3. Combine
        if conversation_text:
            return f"{instruction}\n\n<conversation_context>\n{conversation_text}\n</conversation_context>"
        return instruction
    
    return _instruction_provider
```

The compiled agent gets:

- `include_contents='none'` (suppress ADK's default content assembly)
- `instruction=_instruction_provider` (custom context assembly)
- `bypass_state_injection=True` (InstructionProvider handles its own templating)

**C.capture(key)** → compiles to a `FnAgent` (zero-cost, no LLM call):

```python
class CaptureAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        # Find most recent user message in session events
        for event in reversed(ctx.session.events):
            if event.author == 'user' and event.content and event.content.parts:
                text = ''.join(p.text for p in event.content.parts if p.text)
                ctx.session.state[self._key] = text
                break
        # yield nothing — pure capture
```

**C.template(...)** → compiles to InstructionProvider that prepends context:

```python
def _compile_template(developer_instruction: str, template: str) -> InstructionProvider:
    async def _provider(ctx: ReadonlyContext) -> str:
        context = _template_with_state(template, ctx.state)
        return f"{developer_instruction}\n\n{context}"
    return _provider
```

### 2.5 Limitations and Honest Boundaries

**What C transforms cannot do:**

1. **Multi-modal content in filtered context.** When C compiles to InstructionProvider, conversation history becomes text in the system instruction. Images, audio, and other modalities in prior events are lost. For agents that need multi-modal history, use `C.default()`.

1. **Tool call/response chains.** Proper tool execution requires tool calls and responses in `contents` format, not in system instruction text. Agents with tools that reference prior tool interactions should use `C.default()` or `C.from_agents()` with the tool-using agent included.

1. **Context caching optimization.** ADK's context cache works on `contents`. When C moves conversation into the system instruction, caching behavior changes. For latency-sensitive agents with stable conversation prefixes, `C.default()` may be more efficient.

**The diagnostic tells the developer.** When a C transform might lose multi-modal content or break tool chains, the contract checker flags it:

```
⚠ Agent "analyzer" has C.user_only() but upstream "vision_agent" produces image content.
  Image content will not be included in filtered context. Consider C.from_agents("vision_agent").

⚠ Agent "executor" has C.none() and uses tools that reference prior tool calls.
  Tool call history will not be available. Consider C.default() for tool-using agents.
```

### 2.6 Why C and S Are Orthogonal

The S module transforms **what's in state** — the key-value pairs. The C module transforms **what's in context** — the conversation history the agent sees in its prompt.

They compose:

```python
pipeline = (
    C.capture("user_message")          # C: bridge conversation → state
    >> classifier.outputs("intent")     # Agent: produce data to state
    >> S.set(attempt=0)                 # S: initialize state
    >> S.rename(intent="classification") # S: reshape state
    >> booker
        .instruct("...")
        .context(C.from_state("user_message", "classification"))  # C: assemble context from state
)
```

`S` reshapes the data. `C` controls the view. The execution DAG runs left to right. The information-flow DAG — which agent sees what data through which channel — is declared by `S` and `C` together.

______________________________________________________________________

## 3. Typed State & Data Flow

### 3.1 The Problem

v4/v5 §1 identified state typing as the biggest source of runtime errors. v5.1 extends this: the problem isn't just types and typos. It's that `output_key`, `include_contents`, `{template}` variables, and S/C transforms form a data-flow graph that ADK doesn't model. Errors in any channel manifest as silent failures — the agent runs, gets the wrong context, produces a subtly wrong answer.

### 3.2 `.outputs()` as Role Declaration

`.outputs(key)` is not syntactic sugar for `output_key`. It's a declaration of the agent's role in the data flow:

```python
classifier = Agent("classifier").instruct("Classify intent.").outputs("intent")
```

This declaration triggers four consequences:

1. **ADK compilation:** `output_key="intent"` set on the LlmAgent.
1. **Visibility inference:** Agent has a successor and produces data → classified as `internal` (see §4).
1. **Contract validation:** Downstream agents that reference `{intent}` in instructions or `Route("intent")` in routing are validated.
1. **Context engineering hint:** Downstream agents are informed that `"intent"` is available from state, enabling `C.from_state("intent")`.

Without `.outputs()`, an agent's text goes only to conversation history (Channel 1). With `.outputs()`, it goes to both conversation history AND state (Channel 2). The library uses this distinction to infer visibility, suggest C transforms, and validate contracts.

### 3.3 `StateSchema` — Typed Declarations

Retained from v5 §1.2–1.7 with one addition. `StateSchema` fields can be annotated with their producer:

```python
class BillingState(StateSchema):
    intent: str                              # session-scoped
    confidence: float
    user_message: Annotated[str, CapturedBy(C.capture)]  # produced by C.capture
    ticket_id: str | None = None
    user_tier: Annotated[str, UserScoped]    # cross-session
```

`CapturedBy` is a documentation annotation — it doesn't affect runtime. It tells the contract checker which channel produces this key.

### 3.4 S Module (Retained)

The S module is retained in full from v5. `S.pick`, `S.drop`, `S.rename`, `S.default`, `S.merge`, `S.transform`, `S.compute`, `S.set`, `S.guard`, `S.log` — all compile to `FnAgent` instances that mutate `ctx.session.state` and yield no events.

**New addition: `S.capture()`**

`S.capture(key)` is a semantic alias for `C.capture(key)`. It exists in the S namespace because it writes to state, but its implementation reads from conversation events. This is the explicit bridge between Channel 1 and Channel 2.

```python
pipeline = (
    S.capture("user_message")  # same as C.capture("user_message")
    >> classifier.outputs("intent")
    >> booker.instruct("User: {user_message}\nIntent: {intent}")
)
```

### 3.5 The >> Operator and Data Flow

When the developer writes `a >> b`, the library records the execution edge AND analyzes the data flow:

```python
# What >> does at IR construction time:
# 1. Create SequenceNode([a, b])
# 2. Analyze:
#    - a.outputs_key → key enters state after a runs
#    - b.instruction_template_vars → keys b expects from state
#    - b.context_spec → what conversation history b expects
#    - Route dependencies → what state keys routing reads
# 3. Populate IR edges with data-flow metadata
```

This metadata feeds the contract checker (§13) and enables topology-inferred defaults for visibility (§4) and context (§2).

______________________________________________________________________

## 4. Event Visibility

### 4.1 The Problem

ADK's event channel is singular. `SequentialAgent._run_async_impl` yields every sub-agent's events unchanged:

```python
for sub_agent in self.sub_agents:
    async for event in sub_agent.run_async(ctx):
        yield event  # every event from every agent reaches the client
```

In `classifier >> Route >> booker`, the client receives the classifier's "booking" text AND the booker's conversational response. The user sees both — an internal routing label followed by the actual answer.

### 4.2 The Mechanism

Source-verified: `Runner._exec_with_plugin` processes events in this order:

```
1. append_event(session, event)         ← history recorded, state_delta applied
2. run_on_event_callback(event)         ← plugin can modify/replace event
3. yield modified_event to client       ← client sees this
```

Step 1 happens before step 2. **The plugin cannot affect state or history — only what the client sees.** This separation is the foundation of the visibility mechanism.

### 4.3 Topology-Inferred Visibility

The IR knows which agents are terminal (user-facing) and which are intermediate (internal). The inference rules:

```
VISIBILITY(node, has_successor) =
  | node.visibility_override != None → node.visibility_override
  | node ∈ {Transform, Tap, Route, Checkpoint, Capture} → zero_cost
  | node.has_output_key AND has_successor → internal
  | has_successor → internal
  | ¬has_successor → user
```

Key insight: visibility is determined by position in the DAG, not by what the agent does. An agent is internal not because of what it IS, but where it SITS.

For compound nodes (Sequence, Parallel, Loop, Route), the rule propagates:

```
Sequence([a, b, c]):  a=internal, b=internal, c=inherits parent's has_successor
Parallel([a, b]):     all inherit parent's has_successor
Loop(body):           body=internal (loop body is never final)
MapOver(body):        body=internal (individual iterations are never final)
Route(branches):      each branch target=inherits parent's has_successor
```

### 4.4 VisibilityPlugin

```python
class VisibilityPlugin(BasePlugin):
    """Annotates events with topology-inferred visibility.
    
    Runs in on_event_callback — after session history is recorded, before client sees event.
    Two modes:
      'annotate': adds metadata, yields all events (client filters)
      'filter':   suppresses content of internal events
    """
    
    def __init__(self, visibility_map: dict[str, str], mode: str = "annotate"):
        self._visibility = visibility_map  # agent_name → "user"|"internal"|"zero_cost"
        self._mode = mode
    
    async def on_event_callback(self, *, invocation_context, event):
        vis = self._visibility.get(event.author, "user")
        
        # Always annotate
        event.custom_metadata = event.custom_metadata or {}
        event.custom_metadata["adk_fluent.visibility"] = vis
        event.custom_metadata["adk_fluent.is_user_facing"] = (vis == "user")
        
        if self._mode == "filter" and vis != "user":
            if event.content and event.content.parts:
                # Strip text content, preserve state_delta and actions
                event.content = None
        
        return event
```

### 4.5 Builder API

**Level 0 — Automatic** (default):

```python
pipeline = classifier.outputs("intent") >> Route("intent").eq("booking", booker)
root_agent = pipeline.build()
# Visibility inferred: classifier=internal, route=zero_cost, booker=user
# VisibilityPlugin attached automatically
```

**Level 1 — Per-agent override:**

```python
analyzer = Agent("analyzer").instruct("...").show()   # force user-facing
logger = Agent("logger").instruct("...").hide()        # force internal
```

**Level 2 — Pipeline-level policy:**

```python
pipeline = (drafter >> reviewer >> editor).transparent()  # all visible
pipeline = (classifier >> booker).filtered()              # only terminal visible
```

### 4.6 Compatibility

- **Session history:** Complete regardless of visibility. All events recorded before plugin runs.
- **adk web Events tab:** Shows all events (debugging view). Chat view respects visibility.
- **OTel spans:** Generated for all agents. Visibility is a span attribute, not a filter.
- **Callbacks:** `before_agent_callback` and `after_agent_callback` fire for all agents.
- **Replay:** Session replay sees all events. Visibility metadata allows reconstructing filtered view.

______________________________________________________________________

## 5. Streaming Edge Semantics

### 5.1 The Problem

v4 models streaming as `ExecutionConfig.streaming_mode: Literal["none", "sse", "bidi"]` — a runtime toggle applied uniformly. But streaming changes composition semantics:

- In `A >> B`, does B wait for A's full output or begin processing partial tokens?
- In `A | B` (parallel), how do interleaved streams merge?
- In `Route(key="intent", ...)`, the key may not be available until the stream completes.
- Middleware that inspects `after_model` responses may receive partial chunks.

These are design-time decisions, not runtime flags.

### 5.2 Edge Semantics in the IR

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

### 5.3 Builder API and IR Representation

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

### 5.4 ADK Backend Compilation

- `full`: Standard `SequentialAgent` behavior.
- `chunked`/`token`: Backend wraps downstream in a streaming adapter using `on_event_callback`.
- `first_complete`: Backend wraps parallel agent with cancellation on first completion.

### 5.5 Contract Checking for Streams

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

## 6. Cost-Aware Routing

### 6.1 The Problem

v4's `cost_tracker` middleware observes costs after they occur. Enterprise deployments need budget governance, cost-optimized routing, cost simulation, and cost attribution via standard observability tooling.

### 6.2 `ModelSelectorNode`

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

### 6.3 Builder API

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

### 6.4 `CostModel` — Simulation Without Execution

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

### 6.5 Cost Attribution via OpenTelemetry Metrics

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

## 7. A2A Protocol Interop

### 7.1 `RemoteAgentNode`

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

### 7.2 Builder API

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

### 7.3 ADK Backend Compilation

`RemoteAgentNode` compiles to `_A2AAgent(BaseAgent)` that serializes state into A2A `Task` messages, streams `TaskStatus` updates as ADK `Event` objects, and falls back on failure. Overrides `_run_async_impl()` (not `run_async()`, which is `@final`).

### 7.4 `AgentCard` — Advertising Capabilities

```python
card = pipeline.to_agent_card(
    description="Billing support agent with refund processing",
    endpoint="https://support.example.com/a2a",
)

from adk_fluent.serve import A2AServer
server = A2AServer(pipeline, card=card, config=config)
await server.start(port=8080)
```

### 7.5 Discovery

```python
from adk_fluent.a2a import AgentDirectory
directory = AgentDirectory("https://directory.internal/a2a")
agents = await directory.discover(capabilities=["process_refund"])
pipeline = Agent("classifier") >> RemoteAgent.from_card(agents[0]) >> Agent("responder")
```

______________________________________________________________________

## 8. Telemetry Integration

### 8.1 ADK's Existing Telemetry Architecture

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

### 8.2 The Design Principle: Enrich, Don't Duplicate

adk-fluent's telemetry strategy is **span enrichment** — adding pipeline-level metadata to ADK's existing spans, not creating parallel spans that duplicate ADK's work.

ADK already emits spans at every lifecycle point: agent invocation, LLM calls, tool execution. Creating additional middleware spans at the same points would produce duplicate telemetry, confuse trace visualization, and double storage costs.

### 8.3 `OTelEnrichmentMiddleware`

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

### 8.4 OTel Metrics for adk-fluent

Beyond span enrichment, adk-fluent emits its own OTel metrics for concepts ADK doesn't track:

```python
_meter = metrics.get_meter("adk_fluent")

_llm_cost = _meter.create_counter("adk_fluent.llm.cost", unit="USD")
_llm_tokens = _meter.create_counter("adk_fluent.llm.tokens", unit="tokens")
_pipeline_duration = _meter.create_histogram("adk_fluent.pipeline.duration", unit="ms")
_pipeline_errors = _meter.create_counter("adk_fluent.pipeline.errors")
_contract_violations = _meter.create_counter("adk_fluent.contracts.violations")
```

### 8.5 Integration with ADK's Debug Endpoints

adk-fluent's enrichment attributes appear naturally in ADK's `/debug/trace/:event_id` because they're set on the same spans. No additional debug infrastructure needed.

### 8.6 Configuration Pass-Through

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

## 9. Evaluation Harness

### 9.1 ADK's Existing Evaluation Architecture

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

### 9.2 The Design Principle: Fluent API Over ADK's Eval Infrastructure

adk-fluent's evaluation layer compiles to ADK's native `EvalSet`/`LocalEvalService`, just as the agent builder compiles to native ADK agents. It extends where ADK has gaps (sub-graph targeting, typed state assertions, regression detection, per-tag aggregation, cost tracking) without replacing the evaluation engine, the metrics, or the file formats.

### 9.3 `FluentEvalSuite`

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

### 9.4 `FluentCase` → `EvalCase` Compilation

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
    target_node: str | None = None                    # Sub-graph targeting (§9.8)
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

### 9.5 Execution via `LocalEvalService`

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

### 9.6 `FluentEvalReport` — Extends `EvalCaseResult`

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

### 9.7 Custom Judges → ADK `MetricEvaluatorRegistry`

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

### 9.8 Sub-Graph Targeting

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

### 9.9 Typed State Assertions

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

### 9.10 User Simulation

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

### 9.11 File Format Interop

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

### 9.12 CLI Compatibility

Because `FluentEvalSuite` compiles to native `EvalSet`, output is compatible with ADK's CLI:

```bash
python -c "from my_pipeline import suite; suite.to_eval_set_file('billing.evalset.json')"
adk eval my_agent/ billing.evalset.json --num_runs 3 --print_detailed_results
```

______________________________________________________________________

## 10. Multi-Modal Content Contracts

### 10.1 `ContentSpec`

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

### 10.2 Builder API

```python
agent = (
    Agent("vision_analyzer", "gemini-2.5-pro")
    .accepts(Modality.IMAGE, Modality.TEXT)
    .produces_modality(Modality.TEXT, Modality.STRUCTURED)
)
```

### 10.3 Contract Checking

Verifies that producer output modalities are accepted by downstream consumers. Mismatches flagged at build time.

______________________________________________________________________

## 11. Event Replay and Time-Travel Debugging

### 11.1 Built on ADK's Capture Infrastructure

ADK's telemetry already provides `InMemoryExporter` (spans by session ID) and `ApiServerSpanExporter` (spans by event ID). The `call_llm` span captures request/response when content capture is enabled. adk-fluent's `Recorder` builds on this.

### 11.2 `Recorder`

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

### 11.3 `Recording` Format

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

### 11.4 `ReplayerBackend`

Uses recorded `call_llm` span data for deterministic LLM responses. On mismatch: `error` (raise), `skip` (return empty), or `live` (real call).

### 11.5 Event Stream Diff

```python
from adk_fluent.debug import diff_events
diff = diff_events(recording.events, new_events)
print(diff.summary)
```

______________________________________________________________________

## 12. Execution Boundaries for Distributed Pipelines

### 12.1 `ExecutionBoundary`

```python
@dataclass(frozen=True)
class ExecutionBoundary:
    serialization: Literal["json", "protobuf", "arrow"] = "json"
    transport: TransportConfig | None = None
    isolation: Literal["none", "process", "container"] = "none"
    scaling: ScalingConfig | None = None
```

### 12.2 Builder API

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

### 12.3 Compilation

Backend splits pipeline at boundaries into separate `App` objects. Each independently deployable with its own `ResumabilityConfig`. State serialization uses `StateSchema` when available.

______________________________________________________________________

______________________________________________________________________

## 13. Unified Contract Checker

### 13.1 Cross-Channel Validation

The contract checker now validates across all three channels. For each agent in the DAG:

```python
_CHECKERS = [
    # State contracts (Channel 2)
    check_dataflow_contracts,      # reads-after-writes for state keys
    check_type_contracts,          # typed state matching via StateSchema
    
    # Context contracts (Channel 1 ↔ Channel 2 ↔ Channel 3)
    check_context_contracts,       # C transform validity
    check_template_contracts,      # instruction {variables} resolvable
    check_output_key_contracts,    # .outputs() reaches downstream readers
    check_channel_coherence,       # detect duplication, data loss across channels
    
    # Structural contracts
    check_streaming_contracts,     # streaming edge validation
    check_modality_contracts,      # content type matching
    check_boundary_contracts,      # serialization at boundaries
    check_a2a_contracts,           # remote agent input satisfaction
    check_cost_contracts,          # budget bounds present
    check_visibility_contracts,    # visibility inference consistency
]
```

### 13.2 Channel Coherence Diagnostics

`check_channel_coherence` produces plain-language diagnostics:

```python
def check_channel_coherence(root: Node) -> list[ContractIssue]:
    issues = []
    for node in topological_order(root):
        # 1. Template variable without state producer
        for var in node.instruction_template_vars:
            if not any_upstream_produces(root, node, var):
                issues.append(UnresolvedTemplateVar(
                    node.name, var,
                    hint=f'No upstream agent produces "{var}" via .outputs(). '
                         f'Did you mean to add .outputs("{var}") to an upstream agent, '
                         f'or S.capture("{var}") / S.set({var}=...)?'
                ))
        
        # 2. Duplication: output_key + include_contents='default'
        for pred in predecessors(root, node):
            if pred.output_key and node.context_spec.includes_agent(pred.name):
                issues.append(ChannelDuplication(
                    node.name, pred.name, pred.output_key,
                    hint=f'"{node.name}" will see "{pred.name}"\'s text via conversation '
                         f'AND via {{{{pred.output_key}}}} in state. '
                         f'Consider .context(C.exclude_agents("{pred.name}")) '
                         f'or .context(C.from_state("{pred.output_key}")).'
                ))
        
        # 3. Data loss: no output_key + include_contents='none'
        for pred in predecessors(root, node):
            if not pred.output_key and node.context_spec == C.none():
                if not node.context_spec.includes_agent(pred.name):
                    issues.append(DataLoss(
                        node.name, pred.name,
                        hint=f'"{pred.name}" has no .outputs() and "{node.name}" uses '
                             f'C.none(). "{pred.name}"\'s output reaches "{node.name}" '
                             f'through neither state nor conversation. Data is lost.'
                    ))
        
        # 4. Route reads key not in state
        if isinstance(node, RouteNode):
            if not any_upstream_produces(root, node, node.state_key):
                issues.append(RouteMissingKey(
                    node.name, node.state_key,
                    hint=f'Route reads "{node.state_key}" from state, but no upstream '
                         f'agent produces it via .outputs("{node.state_key}").'
                ))
    
    return issues
```

### 13.3 Diagnostic Output Format

```
✓ classifier.outputs("intent") → Route("intent"): OK
  State key "intent" produced by classifier, consumed by route.

⚠ booker reads {intent} in instruction: OK
  "intent" is produced by classifier upstream via .outputs("intent").

⚠ booker has C.default() with predecessor classifier.outputs("intent"): INFO
  booker will see "booking" in conversation AND "booking" via {intent}.
  This is duplication. Consider: .context(C.user_only())

✗ presenter reads {summary} in instruction: ERROR
  No upstream agent produces "summary" via .outputs() or S.set().
  Did you mean to add .outputs("summary") to an upstream agent?
```

Diagnostics are **advisory by default**. `check_all(..., strict=True)` promotes INFO and WARN to errors.

______________________________________________________________________

## 14. Updated Middleware

### 14.1 Built-In Middleware — v5.1

```python
from adk_fluent.middleware import (
    token_budget, cache, rate_limiter,           # Model-layer
    retry, circuit_breaker,                       # Error-layer
    tool_approval,                                # Tool-layer
    otel_enrichment,                              # Telemetry (§8)
    cost_attribution,                             # OTel metrics (§6.5)
    pii_filter,                                   # Privacy
    recorder,                                     # Debug (§11)
    visibility,                                   # Event visibility (§4)
)
```

**New:** `visibility` — compiles to `VisibilityPlugin`, attached automatically when pipeline has non-trivial topology.

______________________________________________________________________

## 15. Module Architecture

```
adk_fluent/
├── __init__.py              # Public API: Agent, S, C, Pipeline, ...
├── _ir.py                   # IR node types (generated + hand-written)
├── _ir_generated.py         # Seed-generated IR from ADK introspection
├── _transforms.py           # S module: state transforms
├── _context.py              # C module: context transforms (NEW)
├── _visibility.py           # Event visibility inference (NEW)
├── _routing.py              # Route builder
├── _prompt.py               # Instruction templating utilities
├── _base.py                 # FnAgent, TapAgent, MapOverAgent, CaptureAgent
├── agent.py                 # Agent builder
├── workflow.py              # Pipeline, FanOut, Loop builders
├── backends/
│   ├── _protocol.py         # Backend protocol
│   └── adk.py               # ADK backend (compiles IR → ADK agents)
├── middleware.py             # Middleware protocol + built-ins
├── plugin.py                # VisibilityPlugin, RecordingsPlugin, ...
├── testing/
│   ├── contracts.py         # Contract checker (expanded)
│   ├── harness.py           # Test harness
│   └── mock_backend.py      # Mock backend
├── viz.py                   # Mermaid rendering (visibility annotations)
├── eval/                    # Evaluation harness (§9)
├── state.py                 # StateSchema, scoping annotations
├── config.py                # Generated configuration classes
├── runtime.py               # App, Runner wrappers
├── service.py               # Session, artifact, memory services
├── di.py                    # Dependency injection
├── presets.py               # Pre-built pipeline patterns
├── decorators.py            # @agent decorator
└── planner.py               # NL planning integration
```

**New files:** `_context.py` (~200 lines), `_visibility.py` (~150 lines). Contract checker expansion in `contracts.py` (~150 lines).

______________________________________________________________________

## 16. Migration Path

### Phase 1–4: v4 Phases (Retained)

### Phase 5a: Typed State (Foundation) — Retained

### Phase 5b: Telemetry Integration — Retained

### Phase 5c–5h: Retained

### Phase 5i: Context Engineering (New)

**Depends on:** 5a (state system), Phase 4 (FnAgent, backend)

1. `C.capture()` and `C.none()` — simplest transforms, FnAgent compilation
1. `C.user_only()`, `C.from_agents()`, `C.exclude_agents()` — InstructionProvider compilation
1. `C.template()` — template-based context assembly
1. `C.last_n_turns()` — history windowing
1. Topology-inferred context defaults (suggest C transforms in diagnostics)

### Phase 5j: Event Visibility (New)

**Depends on:** Phase 4 (IR topology), 5i (context engineering for coherent UX)

1. `infer_visibility()` — IR topology analysis
1. `VisibilityPlugin` — on_event_callback implementation
1. Builder API: `.show()`, `.hide()`, `.transparent()`, `.filtered()`
1. Mermaid annotations for visibility in `viz.py`
1. `adk web` integration guidance

### Phase 5k: Cross-Channel Contract Checker (New)

**Depends on:** 5a, 5i, 5j

1. `check_template_contracts` — \{variable} resolution across graph
1. `check_output_key_contracts` — .outputs() reaches consumers
1. `check_channel_coherence` — duplication and data loss detection
1. `check_visibility_contracts` — topology inference consistency
1. Plain-language diagnostic formatting

______________________________________________________________________

## 17. Design Principles

### 17.1 The Tide Principle (Strengthened)

Retained from v5. Extended: Context Engineering uses ADK's `InstructionProvider` and `include_contents` as compilation targets. It does not monkey-patch `contents.request_processor` or replace `_get_contents()`.

### 17.2 Progressive Disclosure

Retained from v5. Context Engineering follows this precisely:

- **Level 0:** No C transforms. Pipeline works with ADK defaults. Diagnostics suggest improvements.
- **Level 1:** `.outputs()` + topology inference. Visibility and basic context handled automatically.
- **Level 2:** Explicit C transforms for agents that need selective context.
- **Level 3:** `C.template()` for full control over context assembly.

### 17.3 Declare Relationships, Infer Wiring

The `>>` operator is the relationship. `.outputs()` is the data contract. `{template}` is the consumption point. `.context(C.xxx)` is the view declaration. The library's job is to connect these declarations across all three channels and tell the developer — clearly, at build time — when the connections don't add up.

The S module is for when the developer needs to be the plumber. The C module is for when they need to control the view. The `>>` operator is for when they shouldn't have to think about either.

### 17.4 Dry Run Your Architecture — Retained

### 17.5 Zero Surprise — Retained

______________________________________________________________________

## 18. Success Criteria

Retained from v5, with additions:

| Criterion                                                         | Target                                                                | Measurement                                     |
| ----------------------------------------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------- |
| Context Engineering reduces client-visible noise                  | Zero intermediate events in default `filtered` mode                   | Event count comparison: with/without visibility |
| C transforms prevent data duplication                             | Agents with `.outputs()` predecessors get duplication diagnostic      | Contract checker coverage of all pipelines      |
| Cross-channel contract checker catches 90%+ of state/context bugs | Coverage of template vars, output_keys, include_contents combinations | Integration test suite                          |
| InstructionProvider compilation is correct                        | Filtered context matches expected content                             | Unit tests with session event fixtures          |

______________________________________________________________________

## 19. Performance Budgets

Retained from v5, with additions:

| Operation                      | Budget              | Mechanism                                        |
| ------------------------------ | ------------------- | ------------------------------------------------ |
| C.capture() execution          | < 1ms               | Single reverse scan of session.events            |
| InstructionProvider (C filter) | < 5ms               | Event filtering + string formatting              |
| Visibility inference           | < 1ms at build time | Single DAG traversal                             |
| VisibilityPlugin per event     | < 0.1ms             | Dictionary lookup + metadata write               |
| Cross-channel contract check   | < 50ms              | Single DAG traversal with multi-channel analysis |

______________________________________________________________________

## 20. Compatibility Matrix

Retained from v5, with additions:

| Feature           | ADK Mechanism                                            | adk-fluent Compilation         |
| ----------------- | -------------------------------------------------------- | ------------------------------ |
| C.default()       | `include_contents='default'`                             | Direct pass-through            |
| C.none()          | `include_contents='none'`                                | Direct pass-through            |
| C.user_only()     | InstructionProvider + `include_contents='none'`          | Generated callable             |
| C.from_state()    | InstructionProvider + `include_contents='none'`          | Generated callable             |
| C.capture()       | FnAgent reading session.events                           | CaptureAgent subclass          |
| Event visibility  | `BasePlugin.on_event_callback` + `Event.custom_metadata` | VisibilityPlugin               |
| .outputs()        | `LlmAgent.output_key`                                    | Direct pass-through + metadata |
| .show() / .hide() | `Event.custom_metadata` via VisibilityPlugin             | Visibility override in IR      |

______________________________________________________________________

## Appendix A: Architectural Decision Records

### ADR-001 through ADR-008: Retained from v5

### ADR-009: Why Context Engineering Compiles to InstructionProvider

**Context:** Developers need selective conversation history per agent. ADK only provides binary `include_contents`. Options: (a) patch `contents.request_processor`, (b) custom `_get_contents` override, (c) compile to InstructionProvider + `include_contents='none'`.

**Decision:** Compile to InstructionProvider.

**Rationale:** InstructionProvider receives `ReadonlyContext` which provides full access to `session.events` (conversation history) and `session.state`. Combined with `include_contents='none'`, the InstructionProvider has complete control over what the agent sees. This uses ADK's documented extension point — no monkey-patching. The tradeoff is that filtered conversation goes into the system instruction as formatted text rather than as proper role-alternating `contents`. For 80% of DAG composition use cases (text-only, no tool chains in intermediate agents), this is sufficient. For the 20% requiring proper contents format, `C.default()` is the right choice, and the diagnostic says so.

**Rejected:** Patching `contents.request_processor` — violates Tide Principle.
**Rejected:** Adding new `include_contents` modes to ADK — we don't control ADK.

### ADR-010: Why Event Visibility Uses on_event_callback, Not before_agent_callback

**Context:** Intermediate agent events leak to clients. Options: (a) suppress events in before_agent_callback, (b) filter in on_event_callback plugin, (c) wrap SequentialAgent to not yield intermediate events.

**Decision:** Filter via `on_event_callback` in BasePlugin.

**Rationale:** Source-verified: `Runner._exec_with_plugin` calls `append_event` BEFORE `run_on_event_callback`. This means the plugin runs after session history is recorded and state_delta is applied. The plugin can modify or suppress what the client sees without affecting the historical record. `before_agent_callback` runs too early — the event doesn't exist yet. Wrapping SequentialAgent violates Tide Principle.

**Rejected:** Custom SequentialAgent subclass — creates maintenance burden, breaks when ADK updates.
**Rejected:** Post-processing event stream — would miss state_delta application timing.

### ADR-011: Why .outputs() Is More Than output_key

**Context:** `output_key` writes agent text to state. It also creates duplication (text in both conversation and state). Options: (a) treat .outputs() as pure sugar, (b) treat it as a role declaration with downstream consequences.

**Decision:** Role declaration.

**Rationale:** `.outputs("intent")` tells the library four things: the agent produces structured data, the data has a name, downstream agents can read it from state, and the agent is likely an internal data producer (not user-facing). This single declaration drives visibility inference, context engineering hints, and contract validation. Treating it as sugar would miss the architectural signal — that the agent's text is data, not conversation.

______________________________________________________________________

## Appendix B: Glossary

Retained from v5, with additions:

| Term                    | Definition                                                                                                 |
| ----------------------- | ---------------------------------------------------------------------------------------------------------- |
| **C Module**            | Context transform library controlling what conversation history each agent sees                            |
| **CFilter**             | A declarative specification of which events to include in an agent's context                               |
| **InstructionProvider** | ADK callable receiving ReadonlyContext, returning instruction string — compilation target for C transforms |
| **Visibility**          | Classification of whether an agent's events are shown to the end user (user/internal/zero_cost)            |
| **VisibilityPlugin**    | BasePlugin that annotates/filters events based on topology-inferred visibility                             |
| **Channel Coherence**   | Property of a pipeline where data flows correctly across all three communication channels                  |
| **Data Loss**           | Contract violation where an agent's output reaches no downstream consumer through any channel              |
| **Channel Duplication** | Diagnostic where the same data reaches an agent through multiple channels simultaneously                   |

______________________________________________________________________

## Appendix C: ADK Source Verification Index

All mechanism claims in this specification are verified against `google-adk v1.25.0` source. This index maps claims to source locations for future re-verification as ADK evolves.

| Claim                                           | Source Location                                                                        |
| ----------------------------------------------- | -------------------------------------------------------------------------------------- |
| Events recorded before plugin runs              | `Runner._exec_with_plugin`: `append_event()` at L88, `run_on_event_callback()` at L115 |
| `output_key` mutates event, doesn't suppress    | `LlmAgent.__maybe_save_output_to_state`: writes to `state_delta`, returns void         |
| `include_contents='none'` scans for latest turn | `contents._get_current_turn_contents`: reverse scan for user/other-agent               |
| InstructionProvider bypasses state injection    | `instructions._process_agent_instruction`: `bypass_state_injection=True` for callables |
| ReadonlyContext exposes session.events          | `ReadonlyContext.session` → `Session.events` field                                     |
| `custom_metadata` is first-class Event field    | `Event.custom_metadata: Optional[dict[str, Any]]`                                      |
| FnAgent yields nothing                          | Source: `adk_fluent._base.FnAgent._run_async_impl` — no yield statements               |
| `state_delta` applied in `append_event`         | `InMemorySessionService.append_event`: extracts and applies state deltas               |
| `is_final_response()` returns True for any text | Checks: not function_calls, not partial, not trailing code execution                   |
| SequentialAgent yields all sub-agent events     | `SequentialAgent._run_async_impl`: `async for event in agen: yield event`              |

______________________________________________________________________

*"v4 made the IR the product. v5 made it model production concerns. v5.1 addresses the compositional reality: in a DAG, each agent has a different view of the world. Context Engineering makes that view explicit, controllable, and validatable — but only by compiling to ADK's own InstructionProvider, BasePlugin, and include_contents mechanisms. The three channels are ADK's. The coordination is ours."*
