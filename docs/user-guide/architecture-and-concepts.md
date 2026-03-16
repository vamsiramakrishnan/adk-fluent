# Architecture & Core Concepts

Before diving into builders and operators, it's crucial to understand the underlying mechanics of ADK and how `adk-fluent` interacts with them. This conceptual foundation will help you design robust, predictable agent systems.

## The Three Channels

ADK has three independent mechanisms for agents to communicate. Every confusion about state traces back to developers not realizing they're coordinating three systems manually.

**Channel 1: Conversation History**
All events (user messages, agent responses, tool calls) are appended to `session.events`. When the next agent runs, `contents.py` assembles these events into the LLM prompt. Every agent sees every prior agent's raw text output by default. Controlled by `include_contents`: `'default'` (everything) or `'none'` (current turn only). Binary switch. No middle ground.

**Channel 2: Session State (key-value store)**
Flat dictionary at `session.state`. Written via `output_key` (LlmAgent writes its text here automatically), `ctx.session.state[k] = v` (manual), or `event.actions.state_delta` (event-carried). Read via `session.state[k]` in code. Scoped: unprefixed (session), `app:`, `user:`, `temp:`.

**Channel 3: Instruction Templating**
`inject_session_state()` replaces `{key}` placeholders in instruction strings with `session.state[key]` values. Runs every invocation, just before the LLM call. This is the bridge: state values appear inside the system prompt.

These three channels are configured independently but deeply entangled at runtime. In `classifier >> booker`:

```
classifier (output_key="intent") produces "booking"
  → Channel 1: "booking" appended to session.events
  → Channel 2: session.state["intent"] = "booking" (via state_delta on event)

booker (instruction="Help book. The intent is: {intent}") runs
  → Channel 1: LLM context includes classifier's "booking" text
  → Channel 3: instruction becomes "Help book. The intent is: booking"
  → booker's LLM sees "booking" TWICE: once in conversation, once in instruction
```

This duplication is not a bug. It's the natural consequence of three independent channels converging on one LLM prompt. The developer is expected to manage this. Most don't realize it's happening.

## What include_contents Actually Does

The source (`contents.py`) reveals `include_contents='none'` finds the most recent user message or other-agent reply and only includes events from that point forward. In a pipeline:

```
User: "I want to fly to London"          ← turn start
Classifier: "booking"                     ← agent reply

Booker runs with include_contents='none':
  → Looks backward, finds classifier's reply as "other agent reply"
  → Only includes events from classifier's reply onward
  → Booker sees: "booking"
  → Booker does NOT see: "I want to fly to London"
```

The user's original message is lost. `include_contents='none'` was designed for stateless utility agents that get all their context from state variables in the instruction template. It was not designed for pipeline composition where a downstream agent needs the conversation *and* structured data from an upstream agent.

There is no `include_contents='user_only'` or `include_contents='exclude_agents'`. The switch is binary: everything, or current turn. ADK has no mechanism for topology-aware content filtering.

## What output_key Actually Does

`__maybe_save_output_to_state` runs inside `LlmAgent._run_async_impl`:

```python
async for event in self._llm_flow.run_async(ctx):
    self.__maybe_save_output_to_state(event)  # mutates event.actions.state_delta
    yield event                                # yields event WITH content AND state_delta
```

It mutates the event's `state_delta` field in-place. It does not suppress, replace, or redirect the content. The event still carries full text. `append_event` in the Runner then: (1) appends the event to `session.events`, and (2) applies `state_delta` to `session.state`. Both writes happen atomically from the same event.

`output_key` is therefore a *duplication* mechanism, not a *routing* mechanism. It copies the LLM's text response into state under a named key. The original text still exists in conversation history. Downstream agents get it through both channels.

## What the S Module Does Today

The S module provides pure state transforms that compile to `FnAgent` — a zero-cost agent that mutates `ctx.session.state` directly and yields no events:

```python
pipeline = (
    Agent("researcher").instruct("Find data.").writes("findings")
    >> S.pick("findings", "sources")
    >> S.rename(findings="input")
    >> Agent("writer").instruct("Write report using {input}.")
)
```

`S.pick` → keeps only named keys, nulls everything else (session-scoped)
`S.drop` → removes named keys
`S.rename` → renames keys
`S.default` → fills missing keys
`S.merge` → combines keys
`S.transform` → applies function to single key
`S.compute` → derives new keys from full state
`S.set` → sets explicit values
`S.guard` → asserts invariant
`S.log` → debug print

These operate exclusively on Channel 2 (session state). They don't touch Channel 1 (conversation history) or Channel 3 (instruction templating). FnAgent writes directly to `ctx.session.state` and yields nothing — no events, no state_delta, no conversation history entry.

## Data Flow Contracts

The S module is fine for what it does. It's a clean set of state transforms. The real challenge is coordinating all three channels so the common patterns work correctly. adk-fluent provides three layers of support for this.

### Layer 1: Contract Checker (automatic, build-time)

The contract checker runs automatically on every `.build()` call and analyzes cross-channel coherence across 17 passes. It detects:

- **Template variable resolution** — Agent B's instruction references `{intent}`. Does any upstream agent produce `intent` via `.writes()`?
- **Channel duplication** — Agent A writes `output_key="intent"` but Agent B has default `include_contents`. B sees the value twice (state + conversation).
- **Data loss** — Agent A has no `.writes()` and B has `include_contents='none'`. A's output reaches B through neither channel.
- **Route key validation** — `Route("intent")` reads state but no upstream agent writes `"intent"`.
- **Missing writes inference** — Agent A precedes a successor that reads state keys, but A has no `.writes()`. Its output doesn't reach state.
- **Unused writes** — Agent A writes to state but no downstream agent reads that key.

These checks run in advisory mode by default (logged as warnings). Use `.strict()` to make them errors:

```python
pipeline = (
    Agent("classifier").instruct("Classify.")
    >> Route("intent").eq("booking", booker)
).strict().build()  # Raises ValueError: classifier has no .writes() for Route key
```

### Layer 2: Topology-Aware Inference

The `infer_data_flow()` function and `.infer_data_flow()` builder method analyze a pipeline's topology and return specific suggestions:

```python
pipeline = Agent("classifier") >> Route("intent").eq("booking", booker)
for s in pipeline.infer_data_flow():
    print(f"{s.agent}: {s.action}('{s.key}') — {s.reason}")
# classifier: add_writes('intent') — Successor 'intent_routed' reads state keys ['intent'] ...
```

The `DataFlowContract` view shows all three channels for each agent:

```python
for contract in pipeline.data_flow_contract():
    print(contract)
# DataFlowContract(classifier):
#   conversation: full conversation history
#   state reads:  (none)
#   state writes: (none)
#   template vars: (none)
#   issues:
#     - No .writes() but successor needs state keys ['intent'] — output lost to state channel
```

### Layer 3: Automatic Wiring

For pipelines where you want the library to figure out the plumbing, use `.wired()`:

```python
# Library auto-infers .writes("intent") on classifier
pipeline = (
    Agent("classifier").instruct("Classify.")
    >> Route("intent").eq("booking", booker)
).wired().build()
```

Or call `.auto_wire()` explicitly for fine-grained control:

```python
pipeline = Agent("classifier") >> Route("intent").eq("booking", booker)
pipeline.auto_wire()  # Mutates: classifier gets .writes("intent")
```

`auto_wire()` only adds missing `.writes()` — it never overrides explicit configuration. It infers the key name from what downstream agents need (template variables, `.reads()` keys, Route keys).

### Topology-Aware Context: `C.pipeline_aware()`

ADK's `include_contents` is a binary switch: everything or current turn. For pipelines, you often need the user's original message plus structured data from state, but NOT intermediate agent text.

`C.pipeline_aware()` solves this. It includes user messages plus named state keys while suppressing intermediate agent conversation history:

```python
classifier = Agent("classify").writes("intent")
handler = (
    Agent("handle")
    .instruct("Handle the request.")
    .context(C.pipeline_aware("intent"))
)
pipeline = classifier >> handler
# handler sees: user's original message + state["intent"]
# handler does NOT see: classifier's raw text in conversation history
```

This is equivalent to `C.user_only() + C.from_state("intent")` but with clearer intent and better contract checker support.

### The Three-Channel Decision Matrix

| Scenario | `.writes()` | `.context()` | Result |
|----------|-------------|--------------|--------|
| Default (no config) | — | — | Output in conversation only; successor sees full history |
| State pass-through | `.writes("key")` | — | Output in state AND conversation; successor sees both (duplication) |
| Clean pipeline | `.writes("key")` | `C.pipeline_aware("key")` | Output in state; successor sees user + state (no duplication) |
| Reads only | `.writes("key")` | `.reads("key")` | Output in state; successor sees state keys only (no user message) |
| Template bridge | `.writes("key")` | — + `{key}` in instruction | Output in state AND conversation; instruction also gets it (triple) |

---

## Context Engineering: The Five Operations

Context engineering is not just overflow handling. It is the *continuous discipline* of assembling the smallest, highest-signal token set that maximizes an agent's likelihood of producing the desired outcome.
