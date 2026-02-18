# C Module v2: Atomic Primitives for Context Engineering

**Status**: Supersedes C_MODULE_EXTENSIONS.md — full primitive redesign  
**Philosophy**: Context engineering is not overflow handling. It is the *continuous discipline* of assembling the smallest, highest-signal token set that maximizes an agent's likelihood of producing the desired outcome.  
**ADK Tide**: Builds on `InstructionProvider`, `ReadonlyContext`, `EventsCompactionConfig`, `FnAgent`

---

## 0. Why the v1 Extensions Were Incomplete

The first C module extensions (rolling windows, per-agent windowing, user strategies, summarization) solved *one class* of problem: what to do when context grows too large. Every primitive was reactive — triggered by overflow or nearness to it.

But the research consensus from Anthropic, Manus, LangChain, and production agent builders converges on a broader taxonomy. Context engineering has **five orthogonal operations**, and overflow handling is only one:

| Operation | What it does | v1 Coverage | Gap |
|-----------|-------------|-------------|-----|
| **SELECT** | Choose which information enters context | Partial (event filters) | No relevance scoring, no recency decay, no semantic retrieval |
| **COMPRESS** | Reduce token footprint without losing meaning | Good (summarization, rolling) | No reversible compaction, no dedup, no projection |
| **WRITE** | Produce context artifacts for future consumption | Minimal (C.capture to state) | No scratchpads, no structured extraction, no note-taking |
| **BUDGET** | Token-aware assembly with priority tiers | None | Entirely missing |
| **PROTECT** | Guard context quality and safety | None | No freshness, no redaction, no validation |

The v1 primitives are also *coarse-grained*. `C.rolling(n=5, summarize=True)` is a composite that bundles windowing + summarization + caching into one opaque unit. It works, but it can't be recombined. A developer who wants "windowed history + relevance-scored tool results + token budget" has to reach for raw InstructionProviders.

This document redesigns the C module around **atomic primitives** — small, orthogonal, composable units that each do one thing. The higher-level patterns from v1 (`C.rolling`, `C.from_agents_windowed`) become compositions of these atoms, not primitives themselves.

---

## 1. Design Principles

### 1.1 Atoms, Not Molecules

Every primitive should pass this test: *Can this be meaningfully decomposed into two simpler operations?* If yes, it's a molecule, not an atom. Molecules are valid API sugar, but they must be expressible as atom compositions.

```python
# C.rolling(n=5, summarize=True) is a molecule:
C.rolling(n=5, summarize=True)
# ≡ atom composition:
C.window(n=5) + C.summarize(scope="before_window")

# C.from_agents_windowed(researcher=C.last(1)) is a molecule:
# ≡ atom composition:
C.select(author="researcher") | C.window(n=1)
```

### 1.2 Five Verbs, One Composition Operator

Every primitive is one of five verbs: **select**, **compress**, **write**, **budget**, **protect**. They compose with `+` (union — assemble multiple context blocks) and `|` (pipe — apply transform to preceding selection). The `>>` pipeline operator remains for agent sequencing.

```
+ : union composition  →  CComposite (renders each block, concatenates)
| : pipe composition   →  CPipe (feeds output of left into right as input)
>> : agent sequencing   →  pipeline wiring (unchanged)
```

### 1.3 Every Primitive Compiles to InstructionProvider

The compilation target is unchanged: every C expression becomes `include_contents='none'` + an `InstructionProvider(ReadonlyContext) → str`. Atoms that need writes (caching, scratchpads) emit a companion `FnAgent` before the target agent, per ADR-012.

### 1.4 Proactive, Not Reactive

Primitives should be usable *from the first turn*, not just when context overflows. A `C.budget(tokens=4000)` isn't an overflow handler — it's a proactive constraint that shapes context assembly from turn 1. A `C.relevant(query_key="intent")` isn't a fallback — it's a relevance filter that ensures every turn delivers only signal.

---

## 2. SELECT Primitives — Choose What Enters Context

SELECT primitives answer: "Which information from the session should this agent see?"

### 2.1 `C.window(n)` — Temporal Window

The simplest selector. Include the last N turn-pairs (user + agent response).

```python
.context(C.window(n=5))
```

**Compilation**: Scans `ctx.session.events` backward, extracts last N turn boundaries, formats as conversation text. `include_contents='none'`.

**Performance**: < 2ms (event scan + partition).

**Distinction from v1's `C.last_n_turns(n)`**: Identical behavior, renamed for consistency with the verb taxonomy. `C.last_n_turns` becomes an alias.


### 2.2 `C.select(author=, role=, type=, tag=)` — Attribute-Based Filter

General-purpose event filter by metadata attributes.

```python
# Events from specific agents
.context(C.select(author="researcher"))

# Only tool-call results
.context(C.select(type="tool_result"))

# Events tagged during pipeline execution
.context(C.select(tag="approved"))

# Combine: tool results from researcher
.context(C.select(author="researcher", type="tool_result"))
```

**Semantics**: Filters `ctx.session.events` by matching all specified attributes (AND logic). Unspecified attributes are unconstrained. Returns matching events in chronological order.

**Compilation**: InstructionProvider iterates events, applies predicate, formats matches.

**Performance**: < 2ms (linear scan with predicate).

**Tags**: Events can be tagged via `S.tag("approved")` state transform on preceding agents. Tags stored in `temp:_event_tags_{event_id}`. This is a new S module primitive.


### 2.3 `C.relevant(query_key=, query=, top_k=, model=)` — Semantic Relevance Selection

Select events by semantic relevance to a query, not just recency or authorship.

```python
# Select the 5 most relevant events to the current user intent
.context(C.relevant(query_key="intent", top_k=5))

# Static query relevance
.context(C.relevant(query="billing dispute resolution", top_k=3))

# Dynamic query from current user message
.context(C.relevant(query_key="__user_content__", top_k=5))
```

**Semantics**: Scores each event in `ctx.session.events` against a query string (from state key or literal). Returns top-K by relevance score. The scoring mechanism is pluggable:

- **Default (LLM-based)**: A lightweight LLM call scores event-query pairs. Cached per query+event fingerprint.
- **Embedding-based** (opt-in): `C.relevant(..., scorer="embedding")` uses embedding similarity. Requires embedding service configuration.

**Compilation**:
1. Companion FnAgent computes relevance scores and caches in `temp:_relevance_{agent_name}`.
2. InstructionProvider reads cached scores, selects top-K events, formats.

**Performance**:
- LLM scorer, cache hit: < 3ms
- LLM scorer, cache miss: 100-300ms (batch scoring call)
- Embedding scorer: < 10ms (vector similarity)

**Why this matters beyond overflow**: Relevance selection is not about fitting within limits. It's about *attention efficiency*. Even with abundant context budget, an agent performs better when irrelevant events are excluded. The NOLIMA benchmark shows performance dropping below 50% of baseline at 32K tokens — not because of overflow, but because of diluted attention.


### 2.4 `C.recent(decay=, half_life=, min_score=)` — Recency-Weighted Selection

Select events weighted by temporal recency, with configurable decay.

```python
# Exponential decay with 10-turn half-life
.context(C.recent(half_life=10, min_score=0.1))

# Linear decay over last 20 turns
.context(C.recent(decay="linear", window=20))
```

**Semantics**: Assigns each event a recency score based on its distance from the current turn. Events below `min_score` threshold are excluded. Remaining events are included with their recency metadata (can be used by downstream budget primitives for prioritization).

**Decay functions**:
- `"exponential"` (default): `score = 2^(-distance / half_life)`
- `"linear"`: `score = max(0, 1 - distance / window)`
- `"step"`: `score = 1.0 if distance <= window else 0.0` (equivalent to `C.window(n)`)

**Compilation**: InstructionProvider scores events by turn distance, filters by threshold, formats. No LLM call.

**Performance**: < 2ms.


### 2.5 `C.from_state(*keys, format=)` — State-Based Context

Include structured data from session state (unchanged from v1, included for completeness).

```python
.context(C.from_state("intent", "confidence", "user_profile"))
```

### 2.6 `C.none()` / `C.default()`

Boundary primitives. `C.none()` = empty context (agent sees only its instruction). `C.default()` = ADK's standard `include_contents='default'` behavior.

---

## 3. COMPRESS Primitives — Reduce Without Losing Meaning

COMPRESS primitives answer: "How should information be condensed before entering context?"

### 3.1 `C.summarize(scope=, model=, prompt=, schema=)` — LLM Summarization

Lossy compression via LLM. The fundamental summarization atom.

```python
# Summarize all events before the window
.context(C.window(n=5) + C.summarize(scope="before_window"))

# Summarize specific agent's outputs
.context(C.select(author="researcher") | C.summarize())

# Schema-guided summarization (Manus pattern)
.context(C.summarize(schema={
    "key_decisions": "list[str]",
    "unresolved_issues": "list[str]",
    "current_state": "str"
}))

# Custom summarization prompt
.context(C.summarize(prompt="Focus on factual findings, ignore speculation."))
```

**Semantics**: Takes a set of events (from preceding selector via `|`, or `scope` parameter) and produces a condensed text representation. Schema-guided summarization produces structured JSON output conforming to the schema — this is the Manus pattern of using schemas as contracts for summarization to prevent information loss.

**Scope options** (when not piped):
- `"all"`: Summarize entire event history
- `"before_window"`: Summarize everything before the current window (for use with `C.window(n)` via `+`)
- `"tool_results"`: Summarize only tool call results (often the heaviest payload)

**Compilation**: Companion FnAgent for LLM call + caching. InstructionProvider reads cached summary.

**Compaction awareness**: Checks for existing ADK `EventCompaction` events covering the target range. Reuses if found.

**Performance**: Cache hit < 3ms, cache miss 200-500ms.


### 3.2 `C.compact(strategy=)` — Reversible Compaction

The Manus insight: most context can be *compacted* (reversibly reduced) before it needs to be *summarized* (irreversibly reduced). Compaction replaces large payloads with lightweight references that can be re-fetched if needed.

```python
# Replace tool results with references (file paths, URLs, query identifiers)
.context(C.window(n=10) | C.compact())

# Compact only tool results, keep agent text full
.context(C.compact(strategy="tool_results"))

# Compact all events older than 5 turns
.context(C.compact(strategy="stale", stale_after=5))
```

**Semantics**: For each event in scope, replaces the full content with a compact representation:

| Event type | Full representation | Compact representation |
|-----------|-------------------|----------------------|
| Tool result (file write) | Path + full content | Path only: `"Output saved to /src/main.py"` |
| Tool result (search) | Full search results | Query + result count: `"Search 'billing API' → 12 results (saved to temp:search_3)"` |
| Tool result (web fetch) | Full page content | URL + title + excerpt: `"https://docs.api.com/billing — Billing API Reference (2,340 tokens → ref:web_7)"` |
| Agent output (long) | Full text | First 100 tokens + `"... (full output in state:researcher_output_3)"` |
| Agent output (short) | Full text | Unchanged (below compaction threshold) |

**Reversibility contract**: Every compacted event carries a `_recovery_ref` — a state key, file path, or URL that allows the full content to be reconstructed. The C module's `C.expand(ref)` primitive (see §3.3) can restore compacted content on demand.

**The priority cascade**: `raw > compacted > summarized`. This is the Manus ordering. Always try compaction first. Only summarize when compaction doesn't yield enough savings.

**Compilation**: InstructionProvider scans events, applies compaction rules, formats compact versions. For the "stale" strategy, events within the recent window remain full; older events are compacted.

**Performance**: < 3ms (string truncation + reference generation, no LLM call).

**Key insight**: Compaction is not overflow handling. It's *proactive hygiene*. A 500-line code file in context wastes attention budget even if you're nowhere near the token limit. Replacing it with a path costs nothing in terms of information (the agent can read the file again) but recovers hundreds of tokens of attention.


### 3.3 `C.expand(ref)` — Expand a Compacted Reference

The inverse of compaction. Restores full content from a recovery reference.

```python
# In a sub-agent that needs the full tool output
.context(C.from_state("researcher_output_ref") | C.expand())
```

**Semantics**: Takes a reference (state key, file path, URL) and resolves it to full content. This is how an agent can "zoom in" on a compacted item when it needs the details.

**Compilation**: FnAgent reads the reference, retrieves full content, writes to temp state. InstructionProvider reads and formats.

**Performance**: Depends on source (state lookup < 1ms, file read < 5ms).


### 3.4 `C.dedup(strategy=)` — Deduplication

Remove redundant information across events.

```python
# Remove events whose content is subsumed by later events
.context(C.window(n=10) | C.dedup())

# Semantic deduplication (LLM-judged)
.context(C.window(n=20) | C.dedup(strategy="semantic", model="gemini-2.5-flash"))
```

**Strategies**:
- `"exact"`: Remove events with identical text content. Cost: < 2ms (hash comparison).
- `"structural"`: Remove events where a later event from the same author supersedes an earlier one (e.g., updated search results replace stale ones). Cost: < 3ms (author+type matching).
- `"semantic"`: LLM judges whether two events carry the same information. Cost: 100-300ms (batch LLM call, cached).

**Why this matters beyond overflow**: In iterative agent loops (retry, refine, search-again), events accumulate that carry increasingly refined versions of the same information. Without dedup, the agent sees multiple versions and must waste reasoning capacity determining which is current. Dedup ensures the agent always reasons over the *latest* version.


### 3.5 `C.project(fields=, exclude=)` — Field Projection

For agents that produce structured outputs (JSON, schemas), include only specific fields rather than the entire output.

```python
# From researcher's output, include only findings and confidence
.context(C.select(author="researcher") | C.project(fields=["findings", "confidence"]))

# Exclude verbose reasoning chains, keep conclusions
.context(C.select(author="analyst") | C.project(exclude=["chain_of_thought", "raw_data"]))
```

**Semantics**: Parses event content as structured data (JSON), selects/excludes specified fields, re-serializes. Falls back gracefully to full content if parsing fails.

**Performance**: < 2ms (JSON parse + field selection).

**Why this matters**: Agent outputs often contain both the "answer" and the "work" (chain of thought, intermediate calculations, raw data). Downstream agents usually only need the answer. Projection prevents reasoning artifacts from polluting downstream context.


### 3.6 `C.truncate(max_tokens=, strategy=)` — Hard Truncation

The simplest compression: cut content to fit a token limit.

```python
# Truncate each event to 500 tokens max
.context(C.window(n=10) | C.truncate(max_tokens=500, strategy="tail"))

# Keep head and tail (bookend truncation)
.context(C.select(type="tool_result") | C.truncate(max_tokens=200, strategy="bookend"))
```

**Strategies**:
- `"tail"`: Keep last N tokens (most recent content).
- `"head"`: Keep first N tokens (introductory content).
- `"bookend"`: Keep first N/2 and last N/2 tokens with `[... truncated ...]` marker.

**Performance**: < 1ms (token counting + string slicing).

---

## 4. WRITE Primitives — Produce Context Artifacts

WRITE primitives answer: "What should the agent record for future consumption?" These are *proactive* — they create context before it's needed, not in response to overflow.

### 4.1 `C.capture(key)` — Bridge Conversation to State

Unchanged from v1. Captures the current user message or agent output to a state key for downstream consumption.

```python
C.capture("user_message") >> Agent("classifier")
```

### 4.2 `C.notes(key=, format=)` — Scratchpad / Structured Notes

Read from an agent's structured notepad. Notes are written by the `C.write_notes()` primitive (§4.3) or by explicit agent instructions.

```python
# Read the agent's own notes from previous turns
.context(C.notes(key="progress"))

# Read another agent's notes
.context(C.notes(key="researcher_observations"))

# Notes in structured format
.context(C.notes(key="task_checklist", format="checklist"))
```

**Semantics**: Reads from `state:_notes_{key}`. Notes are persistent across turns within a session (unlike `temp:` which clears per-invocation). The notes primitive is inspired by the Anthropic/Manus patterns where agents maintain structured notes (todo.md, progress trackers, observation logs) as external memory.

**Format options**:
- `"text"` (default): Plain text notes.
- `"checklist"`: Renders as `[x] Done item / [ ] Pending item`.
- `"structured"`: JSON object with labeled sections.
- `"log"`: Append-only log with timestamps.

**Performance**: < 1ms (state read + formatting).


### 4.3 `C.write_notes(key=, strategy=)` — Write to Scratchpad

The write companion to `C.notes()`. Compiles to a companion FnAgent that maintains structured notes in session state.

```python
pipeline = (
    Agent("researcher")
        .instruct("Research the topic. Record key findings.")
        .outputs("findings")
        .context(C.write_notes(key="observations", strategy="append"))
    >> Agent("synthesizer")
        .instruct("Synthesize all observations into a report.")
        .context(C.notes(key="observations"))
)
```

**Strategies**:
- `"append"`: Add new content to existing notes (log-style).
- `"replace"`: Overwrite entirely with latest content.
- `"merge"`: LLM-assisted merge of new content with existing notes (dedup + consolidate). Requires `model` parameter.
- `"checklist"`: Update checklist items (mark complete, add new).

**Compilation**: Emits a post-agent FnAgent that reads the agent's output and writes to `state:_notes_{key}` using the specified strategy.

**Why this matters beyond overflow**: Notes aren't about fitting in the context window. They're about *knowledge accumulation*. A research agent that runs for 50 turns accumulates findings that matter independently of whether the context overflows. Notes provide a structured, persistent, queryable knowledge base that any agent in the pipeline can draw from.


### 4.4 `C.extract(schema=, key=)` — Structured Extraction

Extract structured data from unstructured conversation history and persist to state.

```python
pipeline = (
    # After conversation with user, extract structured profile
    Agent("intake")
        .instruct("Gather user requirements.")
        .context(C.extract(
            schema={"budget": "float", "timeline": "str", "constraints": "list[str]"},
            key="requirements",
            model="gemini-2.5-flash"
        ))
    >> Agent("planner")
        .instruct("Create plan based on requirements: {requirements}")
        .context(C.from_state("requirements"))
)
```

**Semantics**: Uses an LLM to parse the event history and extract structured data conforming to the schema. Result stored in state under `key`. This is a *proactive* transformation — it converts unstructured conversation into structured state, making it efficiently consumable by downstream agents without them having to reason over raw conversation.

**Compilation**: Companion FnAgent performs the extraction LLM call, writes structured result to state.

**Performance**: 200-400ms (LLM call, cached per event fingerprint).

**Distinction from `C.capture`**: `C.capture` copies raw text to state. `C.extract` uses LLM judgment to produce structured data from unstructured input. `C.capture` is a bridge; `C.extract` is a refinery.


### 4.5 `C.distill(key=, model=)` — Fact Distillation

Extract individual facts from conversation history as atomic, retrievable units.

```python
.context(C.distill(key="facts", model="gemini-2.5-flash"))
```

**Semantics**: Extracts discrete facts from conversation (e.g., "User's budget is $5000", "Deadline is March 15", "Prefers vendor A over vendor B"). Each fact is stored individually in `state:_facts_{key}` as a list. Facts can be selected by downstream agents using `C.notes(key="facts")` or filtered with `C.relevant()`.

**Why this matters**: Facts are the atomic unit of knowledge. Summarization is lossy because it must decide what's important *before* knowing what future agents will need. Fact distillation preserves individual facts without a relevance judgment, allowing future agents to select the facts they need via relevance scoring.

---

## 5. BUDGET Primitives — Token-Aware Assembly

BUDGET primitives answer: "How should context be assembled given finite token capacity?" These are *proactive constraints* applied from turn 1, not overflow handlers.

### 5.1 `C.budget(max_tokens=)` — Hard Token Budget

Set a maximum token budget for this agent's assembled context.

```python
.context(
    C.window(n=10) + C.from_state("profile")
    | C.budget(max_tokens=4000)
)
```

**Semantics**: After all SELECT and COMPRESS operations produce their content blocks, the budget primitive measures total tokens. If within budget, pass through. If over budget, apply the configured overflow strategy.

**Overflow strategies** (configurable via `overflow=`):
- `"truncate_oldest"` (default): Remove oldest content blocks first.
- `"truncate_lowest_priority"`: Remove blocks with lowest priority score (see §5.2).
- `"summarize"`: Apply LLM summarization to the largest content block until within budget.
- `"error"`: Raise a configuration error (for strict budget enforcement during development).

**Compilation**: InstructionProvider assembles all content, counts tokens, applies overflow strategy.

**Performance**: < 3ms for truncation strategies, 200-500ms if summarization triggered.

**Why this is different from overflow handling**: `C.budget(max_tokens=4000)` is a *design constraint*, like `max-width` in CSS. It tells the system: "This agent performs best with ≤ 4000 tokens of context." It applies on turn 1 when there's only 200 tokens of context, because it shapes *how* context is assembled, not just *when* to panic.


### 5.2 `C.priority(tier=)` — Priority Tagging

Assign priority tiers to content blocks for budget-aware assembly.

```python
.context(
    C.from_state("intent", "user_profile") | C.priority(tier=1)     # Critical — always included
    + C.window(n=3) | C.priority(tier=2)                             # Important — included if budget allows  
    + C.notes(key="observations") | C.priority(tier=3)               # Supplementary — first to be cut
    | C.budget(max_tokens=8000, overflow="truncate_lowest_priority")
)
```

**Priority tiers**:
| Tier | Label | Behavior |
|------|-------|----------|
| 1 | **Critical** | Always included. System instructions, current intent, active constraints. If tier 1 alone exceeds budget, raise configuration error. |
| 2 | **Important** | Included when budget allows. Recent conversation, key state variables. |
| 3 | **Supplementary** | Included when abundant budget. Historical context, reference information. |
| 4 | **Archive** | Never in context by default. Available via `C.expand()` on demand. |

**Semantics**: Priority tags are metadata on content blocks. The `C.budget()` primitive uses them when overflow strategy is `"truncate_lowest_priority"`: drop tier 4 first, then tier 3, then tier 2. Tier 1 is never dropped.

**Compilation**: Content blocks carry priority metadata through the composition chain. Budget InstructionProvider sorts by priority before applying truncation.

**Performance**: < 1ms (metadata tagging, no computation).


### 5.3 `C.fit(target_tokens=, strategy=)` — Adaptive Fit-to-Budget

A higher-level budget primitive that adaptively fits context to a target token count using a cascade of strategies.

```python
.context(
    C.window(n=20) + C.from_state("requirements")
    | C.fit(target_tokens=6000, strategy="cascade")
)
```

**Cascade strategy** (default):
1. **Compact**: Apply reversible compaction to tool results and long outputs. If within budget, stop.
2. **Dedup**: Remove duplicate events. If within budget, stop.
3. **Truncate lowest priority**: If priority tiers are tagged, drop lowest tier. If within budget, stop.
4. **Summarize**: Summarize the oldest/largest content block. If within budget, stop.
5. **Hard truncate**: If all else fails, truncate oldest content.

**Other strategies**:
- `"compact_then_summarize"`: Manus ordering — compact first, summarize only when compaction yields diminishing returns.
- `"summarize_only"`: Skip compaction, go straight to summarization.
- `"strict"`: Hard truncation only, no LLM calls.

**Performance**: Depends on which cascade steps trigger. Compaction + dedup: < 5ms. Summarization: 200-500ms.

---

## 6. PROTECT Primitives — Guard Context Quality

PROTECT primitives answer: "Is the context accurate, safe, and current?" These are *invariants* enforced at every turn.

### 6.1 `C.fresh(max_age=, stale_action=)` — Freshness Filter

Filter out stale information based on temporal age.

```python
# Exclude events older than 10 turns
.context(C.window(n=20) | C.fresh(max_age=10))

# Mark stale events but include them with a warning
.context(C.window(n=20) | C.fresh(max_age=10, stale_action="warn"))

# Compact stale events instead of removing
.context(C.window(n=20) | C.fresh(max_age=5, stale_action="compact"))
```

**Stale actions**:
- `"exclude"` (default): Remove events older than `max_age` turns.
- `"warn"`: Include with `[STALE — {age} turns old]` annotation.
- `"compact"`: Apply compaction to stale events (replace with references).
- `"summarize"`: Summarize stale events into a single block.

**Why this isn't just `C.window(n)`**: Window is a hard cutoff — it sees exactly N turns. Freshness is a quality annotation — it can be combined with other selectors. `C.select(author="researcher") | C.fresh(max_age=5)` means "researcher's outputs, but only if they're less than 5 turns old." Window can't express this.

**Performance**: < 1ms (turn-distance calculation + filter/annotate).


### 6.2 `C.redact(patterns=, fields=)` — Sensitive Data Redaction

Remove sensitive information before it enters an agent's context.

```python
# Redact PII patterns
.context(C.window(n=10) | C.redact(patterns=["email", "phone", "ssn"]))

# Redact specific state fields
.context(C.from_state("user_profile") | C.redact(fields=["ssn", "credit_card"]))

# Custom regex redaction
.context(C.window(n=10) | C.redact(patterns=[r"\b\d{3}-\d{2}-\d{4}\b"]))
```

**Semantics**: Scans content for sensitive patterns and replaces with `[REDACTED]` placeholders. Built-in patterns cover common PII types. Custom regex patterns supported.

**Why this matters for multi-agent systems**: In pipelines where different agents have different trust levels (e.g., an external API-calling agent vs. an internal summarization agent), redaction ensures sensitive data doesn't leak to agents that shouldn't see it.

**Performance**: < 3ms (regex scanning).


### 6.3 `C.validate(checks=)` — Context Quality Validation

Run quality checks on assembled context and annotate or raise warnings.

```python
.context(
    C.window(n=10) + C.from_state("requirements")
    | C.validate(checks=["contradictions", "completeness"])
)
```

**Available checks**:
- `"contradictions"`: Flag events that assert contradictory facts. (LLM-based, cached.)
- `"completeness"`: Check that required state keys are present and non-empty.
- `"freshness"`: Verify all included events are within acceptable age.
- `"token_efficiency"`: Warn if assembled context has low information density (high duplication or verbosity).

**Compilation**: Validation checks run as a post-assembly step. Failures are either annotated in the context (`<warning>Contradiction detected: ...</warning>`) or raised as pipeline diagnostics during development.

**Performance**: Completeness/freshness < 1ms, contradiction detection 100-300ms (LLM call, cached).

---

## 7. Composition — Building Molecules from Atoms

### 7.1 The `+` Operator (Union)

Combines multiple context blocks into a single assembled context.

```python
context = (
    C.from_state("intent") | C.priority(tier=1)
    + C.window(n=5) | C.priority(tier=2)
    + C.notes(key="observations") | C.priority(tier=3)
)
```

Each operand renders independently, results concatenated with XML section markers:

```xml
<context_block source="state:intent" priority="1">
  Intent: billing_dispute, Confidence: 0.95
</context_block>

<context_block source="window:last_5" priority="2">
  [Turn 12] User: I was charged twice for...
  [Turn 12] Agent: I can see the duplicate charge...
  ...
</context_block>

<context_block source="notes:observations" priority="3">
  - Customer has been waiting 3 days
  - Previous agent promised refund
  ...
</context_block>
```

### 7.2 The `|` Operator (Pipe)

Feeds the output of the left operand as input to the right operand.

```python
# Select researcher's events, then summarize them
C.select(author="researcher") | C.summarize()

# Window the last 10 turns, then compact stale ones
C.window(n=10) | C.compact(strategy="stale", stale_after=5)

# Chain multiple transforms
C.window(n=20) | C.dedup() | C.compact() | C.budget(max_tokens=4000)
```

**Implementation**: `CPipe` wraps two transforms. The left transform produces content; the right transform receives that content as its input scope. Internally, the left renders first, then the right receives the rendered text (or structured event list) as its input.

### 7.3 The `|` Operator (Fallback — overloaded on CTransform vs. literal)

When used between two selectors (not a selector and a compressor), `|` acts as a fallback:

```python
# Use ADK compaction if available, otherwise window the last 5 turns
C.from_compaction() | C.window(n=5)
```

**Disambiguation**: The `|` operator checks the type of its right operand:
- If right operand is a COMPRESS/BUDGET/PROTECT verb → **pipe** (transform the output)
- If right operand is a SELECT verb → **fallback** (try left, use right if left returns empty)

### 7.4 Higher-Level Molecules (Sugar)

The v1 primitives become sugar over atom compositions:

```python
# C.rolling(n=5, summarize=True) ≡
C.window(n=5) + (C.select(scope="before_window") | C.summarize())

# C.from_agents_windowed(researcher=C.last(1), critic=C.all()) ≡
(C.select(author="researcher") | C.window(n=1)) + C.select(author="critic")

# C.user(strategy="bookend") ≡
C.select(author="user", position="first") + C.select(author="user", position="last")

# Manus-style cascade ≡
C.window(n=20) | C.compact(strategy="stale", stale_after=5) | C.fit(target_tokens=128000, strategy="cascade")
```

These molecules remain in the API as convenience methods. Developers who need them don't have to think in atoms. But developers who need fine-grained control can decompose any molecule into its constituent atoms.

---

## 8. End-to-End Example: Production Customer Support Pipeline

```python
pipeline = (
    # Proactive: capture user message + extract structured requirements
    C.capture("user_message")
    >> Agent("classifier", "gemini-2.5-flash")
        .instruct("Classify the customer's intent and urgency.")
        .outputs("intent", "urgency", "category")
        .context(
            C.from_state("user_message") | C.priority(tier=1)
            + C.notes(key="customer_history") | C.priority(tier=2)
        )
    
    >> Route("intent")
        .eq("billing",
            Agent("billing_handler", "gemini-2.5-pro")
                .instruct("Resolve the billing issue.")
                .outputs("resolution", "actions_taken")
                .context(
                    # Tier 1: Current intent + structured requirements
                    C.from_state("intent", "category") | C.priority(tier=1)
                    # Tier 2: Recent conversation, compacted
                    + C.window(n=5) | C.compact() | C.priority(tier=2)
                    # Tier 3: Relevant past observations
                    + C.notes(key="customer_history") 
                      | C.relevant(query_key="intent", top_k=3) 
                      | C.priority(tier=3)
                    # Budget: fit to 8K tokens using priority cascade
                    | C.budget(max_tokens=8000, overflow="truncate_lowest_priority")
                )
                # Proactive: write findings to scratchpad
                .context(C.write_notes(key="customer_history", strategy="append"))
        )
        .eq("technical",
            Agent("tech_support", "gemini-2.5-pro")
                .instruct("Diagnose and resolve the technical issue.")
                .outputs("resolution", "steps_taken")
                .context(
                    # Technical needs full conversation (debugging context matters)
                    C.window(n=15) 
                    | C.dedup(strategy="structural")  # Remove redundant retry outputs
                    | C.fresh(max_age=20, stale_action="compact")  # Compact very old turns
                    | C.budget(max_tokens=16000)
                )
        )
        .eq("escalation",
            Agent("escalation_prep", "gemini-2.5-flash")
                .instruct("Prepare escalation package for human reviewer.")
                .outputs("escalation_package")
                .context(
                    # Fact-distilled conversation (individual retrievable facts)
                    C.distill(key="case_facts", model="gemini-2.5-flash")
                    # Schema-guided summary for handoff
                    + C.summarize(schema={
                        "issue_description": "str",
                        "steps_attempted": "list[str]",
                        "customer_sentiment": "str",
                        "recommended_action": "str"
                    })
                    # Redact PII before escalation
                    | C.redact(patterns=["email", "phone", "ssn"])
                )
        )
    
    >> Agent("responder", "gemini-2.5-flash")
        .instruct("Compose a friendly, helpful response to the customer.")
        .context(
            # Only structured state — no raw conversation
            C.from_state("resolution", "actions_taken") | C.priority(tier=1)
            + C.from_state("user_message") | C.priority(tier=1)
            + C.notes(key="customer_history") | C.relevant(query_key="resolution", top_k=2) | C.priority(tier=3)
            | C.budget(max_tokens=4000)
        )
)
```

**What the contract checker reports**:

```
✓ classifier: C.from_state("user_message") [tier 1] + C.notes("customer_history") [tier 2]
  Budget: unbounded (classifier is lightweight, no overflow risk)

✓ billing_handler: 3-tier priority context with 8K budget
  Tier 1: intent + category (always present, ~100 tokens)
  Tier 2: last 5 turns compacted (~800-1500 tokens)
  Tier 3: relevant history notes (~200-500 tokens)
  Writes: appends to customer_history notes
  Budget headroom: ~5K-7K tokens for instruction + response

✓ tech_support: windowed + deduped + fresh + budgeted at 16K
  Structural dedup removes retry artifacts
  Stale compaction handles deep conversation history
  No notes (debugging needs raw conversation)

✓ escalation_prep: distilled facts + schema summary + PII redaction
  Facts preserved as atomic retrievable units
  Schema prevents information loss in summary
  PII redacted before human handoff

✓ responder: state-only context with relevance-scored history notes
  No raw conversation (all context from structured state)
  Budget: 4K tokens (response composition is lightweight)

✓ All template variables resolved
✓ No circular note dependencies
✓ Priority tiers consistent (tier 1 always < budget)
```

---

## 9. Compilation Architecture

### 9.1 Compilation Pipeline

```
C expression
    → parse into AST of atoms
    → type-check composition (SELECT | COMPRESS ok, COMPRESS | SELECT error)
    → extract companion FnAgents (for WRITE atoms and cached COMPRESS atoms)
    → emit InstructionProvider closure
    → wire FnAgents into pipeline with >>
```

### 9.2 Type Rules for `|` (Pipe)

Not all compositions are valid. The pipe operator enforces type constraints:

```
SELECT | COMPRESS  → valid (filter then reduce)
SELECT | PROTECT   → valid (filter then guard)
SELECT | BUDGET    → valid (filter then constrain)
COMPRESS | BUDGET  → valid (reduce then constrain)
COMPRESS | PROTECT → valid (reduce then guard)
SELECT | SELECT    → fallback semantics (try left, then right)
COMPRESS | SELECT  → ERROR (can't select after compressing)
BUDGET | anything  → ERROR (budget must be terminal)
WRITE | anything   → ERROR (write is a side-effect, not a transform)
```

### 9.3 Companion FnAgent Emission

Atoms that require state writes emit companion FnAgents:

| Atom | Emits FnAgent? | Purpose |
|------|---------------|---------|
| `C.summarize()` | Yes (pre-agent) | Compute + cache summary |
| `C.relevant()` | Yes (pre-agent) | Compute + cache relevance scores |
| `C.extract()` | Yes (pre-agent) | Run extraction LLM + write to state |
| `C.distill()` | Yes (pre-agent) | Run fact distillation + write to state |
| `C.write_notes()` | Yes (post-agent) | Append/merge agent output to notes |
| `C.dedup(strategy="semantic")` | Yes (pre-agent) | Compute + cache dedup judgments |
| `C.validate(checks=["contradictions"])` | Yes (pre-agent) | Run contradiction check |
| All others | No | Pure InstructionProvider |

### 9.4 ReadonlyContext Access Patterns

| Atom | Reads from ReadonlyContext |
|------|--------------------------|
| `C.window(n)` | `ctx.session.events` |
| `C.select(...)` | `ctx.session.events` |
| `C.relevant(...)` | `ctx.state["temp:_relevance_{name}"]` (pre-computed by FnAgent) |
| `C.recent(...)` | `ctx.session.events` (turn counting) |
| `C.from_state(...)` | `ctx.state[key]` |
| `C.notes(...)` | `ctx.state["_notes_{key}"]` |
| `C.summarize(...)` | `ctx.state["temp:_summary_{name}"]` (pre-computed) |
| `C.compact(...)` | `ctx.session.events` |
| `C.budget(...)` | Token count of assembled content |
| `C.fresh(...)` | `ctx.session.events` (turn timestamps) |
| `C.redact(...)` | Content string (pattern matching) |

---

## 10. Performance Budget

| Primitive | Latency | Mechanism | LLM Call? |
|-----------|---------|-----------|-----------|
| `C.window(n)` | < 2ms | Event scan + partition | No |
| `C.select(...)` | < 2ms | Linear scan with predicate | No |
| `C.relevant(...)` cache hit | < 3ms | State lookup | No |
| `C.relevant(...)` cache miss | 100-300ms | Batch scoring call | Yes |
| `C.recent(...)` | < 2ms | Turn distance scoring | No |
| `C.from_state(...)` | < 1ms | State read | No |
| `C.notes(...)` | < 1ms | State read + format | No |
| `C.summarize(...)` cache hit | < 3ms | State lookup | No |
| `C.summarize(...)` cache miss | 200-500ms | LLM summarization | Yes |
| `C.compact(...)` | < 3ms | String truncation + refs | No |
| `C.expand(...)` | < 5ms | State/file read | No |
| `C.dedup("exact")` | < 2ms | Hash comparison | No |
| `C.dedup("semantic")` cache miss | 100-300ms | LLM judgment | Yes |
| `C.project(...)` | < 2ms | JSON parse + field select | No |
| `C.truncate(...)` | < 1ms | Token count + slice | No |
| `C.extract(...)` | 200-400ms | LLM extraction | Yes |
| `C.distill(...)` | 200-400ms | LLM fact extraction | Yes |
| `C.budget(...)` no overflow | < 1ms | Token counting | No |
| `C.budget(...)` with summarize | 200-500ms | LLM summarization | Yes |
| `C.priority(...)` | < 1ms | Metadata tagging | No |
| `C.fit(...)` cascade | 3ms-500ms | Depends on cascade depth | Maybe |
| `C.fresh(...)` | < 1ms | Turn distance filter | No |
| `C.redact(...)` | < 3ms | Regex scanning | No |
| `C.validate(...)` simple | < 1ms | Presence checks | No |
| `C.validate(...)` contradictions | 100-300ms | LLM judgment | Yes |
| `+` composition | Sum of parts | Sequential render | No |
| `\|` pipe | Sum of parts | Chained transform | No |

**Budget rule of thumb**: A pipeline with no LLM-based atoms (window + select + compact + budget) adds < 10ms to each agent invocation. A pipeline with one LLM-based atom (summarize or relevant) adds 200-500ms on cache miss, < 5ms on cache hit. Cache hit rates in practice are 80-95% (events don't change between turns for a given summary scope).

---

## 11. ADR-014: Why Five Verbs, Not Three

**Context**: The original context engineering literature (LangChain, Manus) describes four strategies: Write, Select, Compress, Isolate. Some sources add a fifth (Retrieve). Our taxonomy uses five: Select, Compress, Write, Budget, Protect.

**Decision**: Five verbs: SELECT, COMPRESS, WRITE, BUDGET, PROTECT.

**Rationale**:

- **Isolate** is not a context primitive — it's an *architectural* choice (multi-agent vs. single-agent). In ADK-Fluent, isolation is expressed via the `>>` pipeline operator and the C module's per-agent context declarations. Every agent already has its own context scope. Isolation is the *default*, not an operation.

- **Retrieve** is a subset of SELECT. Retrieval (RAG, semantic search) is one *mechanism* for selection, not a separate *verb*. `C.relevant()` is a SELECT primitive that happens to use retrieval internally.

- **Budget** is genuinely new. No framework has first-class budget primitives. Token budgets are either implicit (context window limit) or handled by ad-hoc code. Making budget a first-class verb allows proactive constraint design.

- **Protect** is genuinely new. Context quality (freshness, redaction, validation) is handled nowhere in existing frameworks. These are invariants, not optimizations — they should be declarable, not buried in custom code.

---

## 12. ADR-015: Compaction Before Summarization (The Priority Cascade)

**Context**: When context exceeds budget, what should happen first?

**Decision**: Always try compaction before summarization. The priority cascade is: `raw > compact > summarize > truncate`.

**Rationale** (from Manus production experience):

- **Compaction is reversible**. If you replace a 500-line file with its path, the agent can read the file again. Information is preserved in the environment.
- **Summarization is irreversible**. Once you summarize 20 turns into 3 sentences, the original detail is gone. You can't predict which detail a future agent step might need.
- **Compaction is free**. No LLM call, < 3ms. Summarization costs 200-500ms and money.
- **Compaction gets you surprisingly far**. Manus found that tool results (search outputs, web fetches, file contents) often constitute 60-80% of context. Compacting these to references recovers most of the token budget without any information loss.

The cascade is:
1. Drop archive-tier content (tier 4)
2. Compact stale tool results → references
3. Compact stale agent outputs → first paragraph + reference
4. Dedup structurally (remove superseded events)
5. Summarize oldest content blocks
6. Hard-truncate as last resort

---

## 13. ADR-016: Why Notes (Scratchpads) Are a Primitive, Not a Pattern

**Context**: Structured note-taking is a well-known pattern (Claude Code's CLAUDE.md, Manus's todo.md). Should it be part of the C module or left to developers?

**Decision**: First-class primitive via `C.notes()` / `C.write_notes()`.

**Rationale**:

- **Notes are context**, not side effects. A developer writes `C.notes(key="observations")` because they want the agent to see accumulated observations. This is a context assembly declaration, not a tool call.
- **Notes compose with other primitives**. `C.notes(key="obs") | C.relevant(query_key="intent", top_k=3)` — select the 3 most relevant observations for the current intent. This composition is impossible if notes are outside the C module.
- **Notes need lifecycle management**. The `strategy` parameter on `C.write_notes()` handles append vs. replace vs. merge semantics that developers otherwise implement ad-hoc.
- **Notes participate in budget**. `C.notes() | C.priority(tier=3)` means observations are supplementary — included when budget allows, cut first when tight. Without first-class integration, notes always consume their full token footprint.

---

## 14. Migration Path (Updated)

**Phase 5i.1** (Current v5.1): `C.capture()`, `C.none()`, `C.default()`, `C.user_only()`, `C.from_agents()`, `C.exclude_agents()`, `C.last_n_turns()`, `C.from_state()`, `C.template()`

**Phase 5i.2** (Atoms — No LLM):
1. `C.window(n)` — renamed `C.last_n_turns` (alias kept)
2. `C.select(author=, type=, tag=)` — general event filter
3. `C.recent(decay=, half_life=)` — recency-weighted selection
4. `C.compact(strategy=)` — reversible compaction
5. `C.truncate(max_tokens=, strategy=)` — hard truncation
6. `C.project(fields=, exclude=)` — field projection
7. `C.dedup(strategy="exact"|"structural")` — non-LLM dedup
8. `C.fresh(max_age=, stale_action=)` — freshness filter
9. `C.redact(patterns=)` — PII redaction
10. `C.priority(tier=)` — priority tagging
11. `C.budget(max_tokens=)` — token budget
12. `+` and `|` composition operators with type rules

**Phase 5i.3** (Atoms — LLM-Powered):
1. `C.summarize(scope=, model=, schema=)` — LLM summarization
2. `C.relevant(query_key=, top_k=, model=)` — semantic relevance
3. `C.dedup(strategy="semantic")` — LLM-judged dedup
4. `C.extract(schema=, key=)` — structured extraction
5. `C.distill(key=)` — fact distillation
6. `C.validate(checks=["contradictions"])` — LLM validation
7. `C.fit(target_tokens=, strategy="cascade")` — adaptive fit

**Phase 5i.4** (Scratchpad / Notes):
1. `C.notes(key=, format=)` — read notes
2. `C.write_notes(key=, strategy=)` — write notes
3. Note lifecycle management (merge, consolidate, decay)
4. Note-aware topology inference

**Phase 5i.5** (Molecules — Sugar):
1. `C.rolling(n, summarize=True)` → `C.window(n) + (select_before | summarize)`
2. `C.from_agents_windowed(...)` → per-agent select + window compositions
3. `C.user(strategy=...)` → user select + position filters
4. `C.manus_cascade(budget=)` → compact → dedup → summarize → truncate

---

## 15. Updated Module Structure

```
adk_fluent/_context.py (~700 lines)
├── CTransform (base protocol)
│
├── SELECT atoms
│   ├── CWindow (window)
│   ├── CSelect (select by attributes)
│   ├── CRelevant (semantic relevance)
│   ├── CRecent (recency-weighted)
│   ├── CFromState (state-based)
│   ├── CNone / CDefault (boundaries)
│   └── CFromCompaction (ADK compaction reuse)
│
├── COMPRESS atoms
│   ├── CSummarize (LLM summarization)
│   ├── CCompact (reversible compaction)
│   ├── CExpand (expand reference)
│   ├── CDedup (deduplication)
│   ├── CProject (field projection)
│   └── CTruncate (hard truncation)
│
├── WRITE atoms
│   ├── CCapture (bridge to state)
│   ├── CNotes (read scratchpad)
│   ├── CWriteNotes (write scratchpad)
│   ├── CExtract (structured extraction)
│   └── CDistill (fact distillation)
│
├── BUDGET atoms
│   ├── CBudget (hard token limit)
│   ├── CPriority (tier tagging)
│   └── CFit (adaptive fit-to-budget)
│
├── PROTECT atoms
│   ├── CFresh (freshness filter)
│   ├── CRedact (PII redaction)
│   └── CValidate (quality checks)
│
├── Composition
│   ├── CComposite (+ operator)
│   ├── CPipe (| operator — transform)
│   ├── CFallback (| operator — selector fallback)
│   └── _type_check_pipe() (composition type rules)
│
├── Compilation
│   ├── _compile_to_instruction_provider()
│   ├── _emit_companion_fn_agents()
│   ├── _find_covering_compaction()
│   ├── _extract_turns()
│   └── _format_context_blocks()
│
├── Molecules (sugar)
│   ├── rolling() → window + summarize
│   ├── from_agents_windowed() → per-agent select + window
│   ├── user() → user select + position
│   └── manus_cascade() → compact + dedup + summarize + truncate
│
└── FnAgent helpers
    ├── SummaryCacheAgent
    ├── RelevanceScorerAgent
    ├── ExtractionAgent
    ├── DistillationAgent
    ├── NoteWriterAgent
    └── ValidationAgent
```

---

## 16. Cross-Framework Comparison (Updated)

| Capability | LangGraph | CrewAI | Manus | Claude Code | ADK-Fluent C Module |
|-----------|-----------|--------|-------|-------------|-------------------|
| **Temporal window** | `trim_messages(strategy="last")` | N/A | Implicit in compaction | Last 5 files after compact | `C.window(n)` |
| **Relevance selection** | `pre_model_hook` + custom | ChromaDB RAG | N/A | `grep` + `glob` | `C.relevant(query_key=, top_k=)` |
| **Recency decay** | Custom | N/A | N/A | N/A | `C.recent(decay=, half_life=)` |
| **Reversible compaction** | `RemoveMessage` (manual) | N/A | Full/compact representations | Context editing (stale tool results) | `C.compact(strategy=)` |
| **LLM summarization** | `SummarizationNode` | Short-term memory RAG | Schema-based summarization | Auto-compact at 95% | `C.summarize(schema=)` |
| **Deduplication** | Manual | N/A | N/A | N/A | `C.dedup(strategy=)` |
| **Field projection** | Manual in `pre_model_hook` | N/A | N/A | N/A | `C.project(fields=)` |
| **Token budget** | Implicit (window limit) | Implicit | Pre-rot threshold monitoring | 95% trigger | `C.budget(max_tokens=)` |
| **Priority tiers** | N/A | N/A | Implicit (recent raw > old compact) | N/A | `C.priority(tier=)` |
| **Scratchpad/notes** | State field in graph | Long-term memory (SQLite) | `todo.md` file | `CLAUDE.md` + memory tool | `C.notes()` / `C.write_notes()` |
| **Structured extraction** | Custom node | N/A | N/A | N/A | `C.extract(schema=)` |
| **Freshness filter** | Manual | N/A | Stale = compact trigger | N/A | `C.fresh(max_age=)` |
| **PII redaction** | Manual | N/A | N/A | N/A | `C.redact(patterns=)` |
| **Composable** | No (imperative hooks) | No (opaque RAG) | No (hardcoded logic) | No (built-in heuristics) | Yes (`+` and `\|` operators) |
| **Declarative** | No | Partially (memory=True) | No | No | Yes |
| **Inspectable/validatable** | Via LangSmith traces | No | No | No | Contract checker + type rules |

**Key differentiator**: Every other framework implements context engineering as *imperative code* — custom hooks, manual state management, hardcoded heuristics. ADK-Fluent's C module is the only *declarative, composable, type-checked* context engineering system. The developer declares what each agent should see using orthogonal atomic primitives; the library compiles it to ADK's InstructionProvider mechanism; the contract checker validates it before execution.

---

*"Context engineering is not what you do when things overflow. It is what you do from the first token to ensure every token earns its place."*