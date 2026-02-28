# Composition Patterns

Higher-order constructors from `adk_fluent.patterns` that compose agents into common architectures. Each pattern is a function that returns a ready-to-use builder.

```python
from adk_fluent.patterns import review_loop, cascade, fan_out_merge, chain, conditional, supervised, map_reduce
```

---

## `review_loop` — Refinement Loop

A worker produces output, a reviewer scores it, and the loop repeats until quality meets the target.

```python
pipeline = review_loop(
    worker=Agent("writer").instruct("Write a blog post about {topic}."),
    reviewer=Agent("reviewer").instruct("Score the draft 0-1 for quality."),
    quality_key="review_score",
    target=0.8,
    max_rounds=3,
)
```

**Data flow:**
1. Worker runs, stores output in `{quality_key}_draft`
2. Reviewer reads the draft, stores score in `{quality_key}`
3. Loop checks if score >= target
4. If not, worker runs again with reviewer feedback

---

## `cascade` — Fallback Chain

Tries each agent in order. First successful response wins.

```python
pipeline = cascade(
    Agent("fast").model("gemini-2.0-flash"),
    Agent("smart").model("gemini-2.5-pro"),
    Agent("fallback").model("gemini-2.0-flash").instruct("Provide a safe default."),
)
```

**Data flow:** Each agent receives the same input. The first agent that succeeds provides the response.

---

## `fan_out_merge` — Parallel Research + Merge

Run multiple agents in parallel, then merge their outputs.

```python
pipeline = fan_out_merge(
    Agent("web_search").writes("web"),
    Agent("doc_search").writes("docs"),
    Agent("expert").writes("expert"),
    merge_key="combined",
    merge_fn=lambda results: "\n\n".join(results.values()),
)
```

**Data flow:**
1. All agents run in parallel (FanOut)
2. Each writes to its own state key
3. Merge function combines results into `state[merge_key]`

---

## `chain` — Sequential Composition

Compose a list of steps into a Pipeline.

```python
pipeline = chain(
    Agent("researcher").writes("findings"),
    Agent("writer").reads("findings").writes("draft"),
    Agent("editor").reads("draft").writes("final"),
)
```

**Data flow:** Each agent runs in sequence. State propagates between steps via `.writes()` and `.reads()`.

---

## `conditional` — If/Else Branching

Route to different agents based on a predicate.

```python
pipeline = conditional(
    predicate=lambda state: state.get("category") == "technical",
    if_true=Agent("tech_support").instruct("Handle technical issue."),
    if_false=Agent("general_support").instruct("Handle general inquiry."),
)
```

**Data flow:** The predicate reads from state. Only one branch executes.

---

## `supervised` — Approval Workflow

A worker produces output, a supervisor approves or requests revisions.

```python
pipeline = supervised(
    worker=Agent("drafter").instruct("Draft the contract."),
    supervisor=Agent("lawyer").instruct("Review for legal compliance."),
    approval_key="approved",
    max_revisions=2,
)
```

**Data flow:** Similar to `review_loop` but with approval semantics. The supervisor marks `state[approval_key]` as approved or requests changes.

---

## `map_reduce` — Fan-Out Over Items

Apply a mapper agent to each item, then reduce results.

```python
pipeline = map_reduce(
    mapper=Agent("analyzer").instruct("Analyze this item: {item}"),
    reducer=Agent("synthesizer").instruct("Synthesize all analyses."),
    items_key="items",
)
```

**Data flow:**
1. Reads `state[items_key]` (a list)
2. Runs mapper on each item in parallel
3. Reducer combines all mapper outputs
