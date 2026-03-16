# Composition Patterns

Higher-order constructors from `adk_fluent.patterns` that compose agents into common architectures. Each pattern is a function that returns a ready-to-use builder.

```python
from adk_fluent.patterns import review_loop, cascade, fan_out_merge, chain, conditional, supervised, map_reduce
```

```
Pattern Quick Reference:

  review_loop    ( worker >> reviewer ) * until(score >= target)
  cascade        agent_a // agent_b // agent_c
  fan_out_merge  ( a | b | c ) >> S.merge(into="combined")
  chain          a >> b >> c  (with .writes()/.reads() wiring)
  conditional    pred? ─┬─ true_branch
                        └─ false_branch
  supervised     ( worker >> supervisor ) * until(approved)
  map_reduce     items ──┬─ mapper(item_0)
                         ├─ mapper(item_1) ──>> reducer
                         └─ mapper(item_n)
```

______________________________________________________________________

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

```
    ┌──────────────────────────────────────────────┐
    │             ┌──────────┐    ┌──────────┐     │
    │  ──────────►│  worker  │───►│ reviewer │──┐  │
    │  │          └──────────┘    └──────────┘  │  │
    │  │                          score >= 0.8? │  │
    │  └── no ──────────────────────────────────┘  │
    │                               │ yes          │
    └───────────────────────────────┼──────────────┘
                                    ▼ done
```

**Data flow:**

1. Worker runs, stores output in `{quality_key}_draft`
1. Reviewer reads the draft, stores score in `{quality_key}`
1. Loop checks if score >= target
1. If not, worker runs again with reviewer feedback

______________________________________________________________________

## `cascade` — Fallback Chain

Tries each agent in order. First successful response wins.

```python
pipeline = cascade(
    Agent("fast").model("gemini-2.0-flash"),
    Agent("smart").model("gemini-2.5-pro"),
    Agent("fallback").model("gemini-2.0-flash").instruct("Provide a safe default."),
)
```

```
    fast ──► success? ─── yes ──► done
              │ no
    smart ──► success? ─── yes ──► done
              │ no
    fallback ──────────────────── done
```

**Data flow:** Each agent receives the same input. The first agent that succeeds provides the response.

______________________________________________________________________

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

```
    ┌─ web_search ──► state["web"]  ─┐
    ├─ doc_search ──► state["docs"] ─┼──► merge_fn ──► state["combined"]
    └─ expert ──────► state["expert"]─┘
```

**Data flow:**

1. All agents run in parallel (FanOut)
1. Each writes to its own state key
1. Merge function combines results into `state[merge_key]`

______________________________________________________________________

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

______________________________________________________________________

## `conditional` — If/Else Branching

Route to different agents based on a predicate.

```python
pipeline = conditional(
    predicate=lambda state: state.get("category") == "technical",
    if_true=Agent("tech_support").instruct("Handle technical issue."),
    if_false=Agent("general_support").instruct("Handle general inquiry."),
)
```

```
                    ┌─ yes ──► tech_support
    state ──► pred? ─┤
                    └─ no  ──► general_support
```

**Data flow:** The predicate reads from state. Only one branch executes.

______________________________________________________________________

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

______________________________________________________________________

## `map_reduce` — Fan-Out Over Items

Apply a mapper agent to each item, then reduce results.

```python
pipeline = map_reduce(
    mapper=Agent("analyzer").instruct("Analyze this item: {item}"),
    reducer=Agent("synthesizer").instruct("Synthesize all analyses."),
    items_key="items",
)
```

```
    state["items"] ──┬─ mapper("item_0") ─┐
                     ├─ mapper("item_1") ─┼──► reducer ──► output
                     └─ mapper("item_n") ─┘
```

**Data flow:**

1. Reads `state[items_key]` (a list)
1. Runs mapper on each item in parallel
1. Reducer combines all mapper outputs

## Durable Execution

All patterns above work with any execution backend. When using the Temporal backend (in development), each pattern gains crash recovery — if the process fails mid-pipeline, Temporal replays completed steps from cache.

```python
# Same pattern, durable execution
pipeline = review_loop(
    worker=Agent("writer").instruct("Write."),
    reviewer=Agent("reviewer").instruct("Review."),
    quality_key="score",
    target=0.8,
).engine("temporal", client=client, task_queue="quality")

response = await pipeline.ask_async("Write about AI safety")
```

Patterns with natural checkpoint boundaries (each step in `chain`, each iteration in `review_loop`) are especially well-suited for durable execution. See [Temporal Guide](temporal-guide.md) for details.

:::{seealso}
- [Execution Backends](execution-backends.md) — backend selection and capability matrix
- [Temporal Guide](temporal-guide.md) — durable execution patterns and constraints
- [Expression Language](expression-language.md) — the operator equivalents of these patterns
:::
