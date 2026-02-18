# State in Agent Composition: What ADK Does, What's Missing, What adk-fluent Should Do

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
    Agent("researcher").instruct("Find data.").outputs("findings")
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
# Developer writes:
classifier = Agent("classifier").instruct("Classify intent").outputs("intent")
booker = Agent("booker").instruct("Help book. Intent: {intent}")
pipeline = classifier >> Route("intent").eq("booking", booker)

# Library infers:
# classifier has output_key → it's a data producer
#   → visibility: internal (don't show "booking" to user)
#   → its output is in state as "intent"
# Route reads "intent" from state → contract satisfied
# booker reads {intent} from instruction template → contract satisfied
# booker has no output_key → it's a conversation producer → visibility: user
```

No additional configuration needed. The developer expressed their intent through `.outputs()` and `{intent}`. The library infers the rest.

### 2. Provide a clean user_message capture pattern

The hardest problem in pipeline state is preserving the user's original message for downstream agents that use `include_contents='none'`. Rather than fighting ADK's binary switch, the library provides a standard pattern:

```python
# Explicit: developer captures what they want passed through
pipeline = (
    S.capture("user_message")           # snapshot current user input into state
    >> classifier.outputs("intent")
    >> Route("intent").eq("booking",
        booker.instruct("User said: {user_message}\nIntent: {intent}\nHelp them book.")
    )
)
```

`S.capture(key)` is a new S transform that reads the most recent user message from session events and writes it to state. It's the bridge between Channel 1 and Channel 2 that ADK doesn't provide. Simple, explicit, no magic.

For the 80% case where downstream agents just need the user message + structured state, this eliminates the include_contents problem entirely. The developer opts each agent into `include_contents='none'` (or the library infers it for agents whose instructions contain only `{template}` variables), and all context comes through state.

### 3. Validate contracts at build time with clear diagnostics

Not type-checking. Not compile errors. Diagnostics — like a linter that explains what will happen at runtime and flags likely mistakes:

```
⚠ classifier.outputs("intent") → Route("intent"): OK
  State key "intent" flows from classifier to Route via output_key.

⚠ booker reads {intent} from instruction template: OK
  "intent" is produced by classifier upstream.

⚠ booker reads {user_message} from instruction template: WARN
  No upstream agent produces "user_message" via output_key.
  Did you mean to add S.capture("user_message") before classifier?

⚠ booker has include_contents='default': INFO
  booker will see classifier's raw text "booking" in conversation
  AND "booking" via {intent} in instruction. This is duplication.
  Consider: booker.include_contents('none') if instruction has full context.
```

This is what a cracked engineer builds. Not more knobs. Not more transforms. *Explanations.* The library knows what will happen at runtime because it has the full DAG. It tells the developer, in plain language, what each agent will see and where the data gaps are. The developer makes the call.

### 4. Smart defaults that reduce to zero-config for common patterns

For the simplest pipeline — `a >> b` where a has `output_key` and b's instruction templates reference it — the library should produce correct behavior with zero additional configuration:

```python
# This should just work, no S transforms needed:
pipeline = (
    Agent("extractor")
        .instruct("Extract name and email from the user's message.")
        .outputs("extracted")               # → I'm a data producer
    >> Agent("formatter")
        .instruct("Format this data nicely: {extracted}")  # → I consume from state
)

# Library infers:
#   extractor: output_key="extracted", visibility=internal
#   formatter: has {extracted} template var, all context from state
#     → could suggest include_contents='none' in diagnostics
#     → visibility=user (terminal)
```

The S module exists for when the developer needs explicit wiring — renaming keys, merging outputs, computing derived values, guarding invariants. But for the straight-through case of "produce data, consume data," `>>` plus `.outputs()` plus `{template}` should be sufficient.


## What This Means for adk-fluent

The changes are surgical, not architectural:

**S.capture(key)** — New transform. Reads most recent user message from session events, writes to state. ~15 lines. Bridges Channel 1 → Channel 2.

**Contract checker expansion** — Today checks IR structure. Expand to cross-reference: output_keys declared, instruction template variables referenced, include_contents settings, Route state reads. Produce plain-language diagnostics. ~100 lines.

**>> operator intelligence** — When building the IR, propagate data flow information. If node A has output_key and node B follows, annotate the edge. If node B's instruction references `{key}` and no upstream produces `key`, flag it. ~50 lines in IR builder.

**Default inference** — When compiling IR to ADK agents, apply smart defaults. Agent with output_key + successor → suggest internal visibility. Agent with only `{template}` vars in instruction → candidate for include_contents='none'. These are suggestions in diagnostics, not forced overrides. ~30 lines in backend.

The S module stays as-is. It's already clean. The improvement is in making the *pipeline operator* smart enough that developers rarely need S transforms for the common case, and in making the *contract checker* articulate enough that developers understand what's happening across all three channels without reading ADK source code.


## The Principle

Great composition libraries don't expose plumbing. They let developers declare relationships and infer the wiring. The `>>` operator is the relationship. `.outputs()` is the data contract. `{template}` is the consumption point. The library's job is to connect these declarations across all three channels and tell the developer — clearly, at build time — when the connections don't add up.

The S module is for when the developer needs to be the plumber. The `>>` operator is for when they shouldn't have to be.