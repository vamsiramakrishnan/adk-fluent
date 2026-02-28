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

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE THREE CHANNELS                           │
│                                                                 │
│  ① CONVERSATION HISTORY          ② SESSION STATE               │
│  ┌─────────────────────┐         ┌──────────────────┐          │
│  │ session.events       │         │ session.state     │          │
│  │                     │         │                  │          │
│  │ user: "fly to LDN"  │         │ intent: "booking"│          │
│  │ classifier:"booking"│         │ dest:   "London" │          │
│  │ booker: "..."       │         │                  │          │
│  └────────┬────────────┘         └────────┬─────────┘          │
│           │                               │                    │
│           │    ③ INSTRUCTION TEMPLATING    │                    │
│           │    ┌──────────────────────┐    │                    │
│           │    │ "Help book. Intent:  │    │                    │
│           │    │  {intent}" → "Help   │◄───┘                    │
│           │    │  book. Intent:       │                         │
│           │    │  booking"            │                         │
│           │    └──────────┬───────────┘                         │
│           │               │                                    │
│           ▼               ▼                                    │
│        ┌─────────────────────────────┐                         │
│        │        LLM PROMPT           │                         │
│        │  sees "booking" from ① AND  │                         │
│        │  sees "booking" from ③      │                         │
│        │  (duplication by design)    │                         │
│        └─────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

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
    Agent("researcher").instruct("Find data.").save_as("findings")
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

## What's Actually Missing

The S module is fine for what it does. It's a clean set of state transforms. The problem isn't the transforms — it's that the developer has to manually coordinate all three channels, and the common patterns require getting the coordination exactly right.

### Missing: The >> operator doesn't encode data flow

When a developer writes `a >> b`, they mean "a's output feeds b." But `>>` in adk-fluent compiles to `SequentialAgent`, which just runs agents in order within the same session. The operator implies data flow but implements sequential execution. The gap between these is where every state management mistake lives.

Unix pipes work because `|` means "stdout of left connects to stdin of right." The shell handles the plumbing. Programs don't think about it. `>>` should carry that same weight: the developer declares the relationship, the library figures out the wiring.

### Missing: output_key should be inferred from topology, not manually assigned

If an agent has a successor in a pipeline and the successor reads from state, the intermediate agent needs an `output_key`. Today the developer has to know this. There's no signal from the library that says "you put classifier before a Route that reads 'intent', but classifier has no output_key — its output won't be in state."

### Missing: include_contents should have a topology-aware mode

The binary choice (everything / current turn) is insufficient for pipelines. A downstream agent often needs: the user's original message (conversational context) + structured data from state (routing info, extracted entities) — but NOT the raw text of intermediate agents (noise, duplication).

This isn't something adk-fluent can fix at the ADK level. But it could provide a mechanism: a custom `InstructionProvider` that assembles context from state rather than relying on ADK's conversation history. Agents with `include_contents='none'` plus a carefully constructed instruction that includes `{user_message}` from state — where `{user_message}` was captured by an earlier agent or S transform.

### Missing: Contract validation across all three channels

The build-time check the developer actually needs isn't "does key X exist in state." It's a coherence analysis across channels:

- Agent B's instruction template references `{intent}`. Does any upstream agent produce `intent` via `output_key`?
- Agent A has `output_key="intent"` but agent B has `include_contents='default'`. B will see "booking" twice (state + conversation). Is this intentional?
- Agent A has no `output_key` and B has `include_contents='none'`. A's output reaches B through neither channel. Data is lost.
- Route reads `state["intent"]` but classifier has no `output_key`. Route will read stale or missing state.

## What the Thoughtful Library Does

The 100x team doesn't add more S transforms. The S module is already complete for explicit state manipulation. They focus on three things:

### 1. Make >> aware of data contracts

`output_key` is not just a storage mechanism — it's a declaration of agent role. An agent with `output_key` is saying "my text is data, not conversation." An agent without `output_key` is saying "my text IS the conversation."

The `>>` operator should respect this:

```python

---

## Context Engineering: The Five Operations

Context engineering is not just overflow handling. It is the *continuous discipline* of assembling the smallest, highest-signal token set that maximizes an agent's likelihood of producing the desired outcome.

| Operation | What it does | v1 Coverage | Gap |
|-----------|-------------|-------------|-----|
| **SELECT** | Choose which information enters context | Partial (event filters) | No relevance scoring, no recency decay, no semantic retrieval |
| **COMPRESS** | Reduce token footprint without losing meaning | Good (summarization, rolling) | No reversible compaction, no dedup, no projection |
| **WRITE** | Produce context artifacts for future consumption | Minimal (C.capture to state) | No scratchpads, no structured extraction, no note-taking |
| **BUDGET** | Token-aware assembly with priority tiers | None | Entirely missing |
| **PROTECT** | Guard context quality and safety | None | No freshness, no redaction, no validation |
```
