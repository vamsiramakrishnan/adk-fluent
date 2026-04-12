# Composition Patterns

Higher-order constructors that compose agents into common architectures. Each pattern is a function that returns a ready-to-use builder. Both packages ship the same pattern set with parallel naming (snake_case in Python, camelCase in TypeScript).

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent.patterns import (
    review_loop,
    cascade,
    fan_out_merge,
    chain,
    conditional,
    supervised,
    map_reduce,
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import {
  reviewLoop,
  cascade,
  fanOutMerge,
  chain,
  conditional,
  supervised,
  mapReduce,
} from "adk-fluent-ts";
```
:::
::::

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

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
pipeline = review_loop(
    worker=Agent("writer").instruct("Write a blog post about {topic}."),
    reviewer=Agent("reviewer").instruct("Score the draft 0-1 for quality."),
    quality_key="review_score",
    target=0.8,
    max_rounds=3,
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const pipeline = reviewLoop(
  new Agent("writer", "gemini-2.5-flash").instruct("Write a blog post about {topic}."),
  new Agent("reviewer", "gemini-2.5-flash").instruct("Score the draft 0-1 for quality."),
  { qualityKey: "review_score", target: 0.8, maxRounds: 3 },
);
```
:::
::::

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

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
pipeline = cascade(
    Agent("fast").model("gemini-2.0-flash"),
    Agent("smart").model("gemini-2.5-pro"),
    Agent("fallback").model("gemini-2.0-flash").instruct("Provide a safe default."),
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const pipeline = cascade(
  new Agent("fast", "gemini-2.0-flash"),
  new Agent("smart", "gemini-2.5-pro"),
  new Agent("fallback", "gemini-2.0-flash").instruct("Provide a safe default."),
);
```
:::
::::

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

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
pipeline = fan_out_merge(
    Agent("web_search").writes("web"),
    Agent("doc_search").writes("docs"),
    Agent("expert").writes("expert"),
    merge_key="combined",
    merge_fn=lambda results: "\n\n".join(results.values()),
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const pipeline = fanOutMerge(
  [
    new Agent("web_search", "gemini-2.5-flash").writes("web"),
    new Agent("doc_search", "gemini-2.5-flash").writes("docs"),
    new Agent("expert", "gemini-2.5-flash").writes("expert"),
  ],
  { mergeKey: "combined" },
);
```
:::
::::

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

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
pipeline = chain(
    Agent("researcher").writes("findings"),
    Agent("writer").reads("findings").writes("draft"),
    Agent("editor").reads("draft").writes("final"),
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const pipeline = chain(
  new Agent("researcher", "gemini-2.5-flash").writes("findings"),
  new Agent("writer", "gemini-2.5-flash").reads("findings").writes("draft"),
  new Agent("editor", "gemini-2.5-flash").reads("draft").writes("final"),
);
```
:::
::::

**Data flow:** Each agent runs in sequence. State propagates between steps via `.writes()` and `.reads()`.

______________________________________________________________________

## `conditional` — If/Else Branching

Route to different agents based on a predicate.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
pipeline = conditional(
    predicate=lambda state: state.get("category") == "technical",
    if_true=Agent("tech_support").instruct("Handle technical issue."),
    if_false=Agent("general_support").instruct("Handle general inquiry."),
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const pipeline = conditional(
  (state) => state.category === "technical",
  new Agent("tech_support", "gemini-2.5-flash").instruct("Handle technical issue."),
  new Agent("general_support", "gemini-2.5-flash").instruct("Handle general inquiry."),
);
```
:::
::::

```
                    ┌─ yes ──► tech_support
    state ──► pred? ─┤
                    └─ no  ──► general_support
```

**Data flow:** The predicate reads from state. Only one branch executes.

______________________________________________________________________

## `supervised` — Approval Workflow

A worker produces output, a supervisor approves or requests revisions.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
pipeline = supervised(
    worker=Agent("drafter").instruct("Draft the contract."),
    supervisor=Agent("lawyer").instruct("Review for legal compliance."),
    approval_key="approved",
    max_revisions=2,
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const pipeline = supervised(
  new Agent("drafter", "gemini-2.5-flash").instruct("Draft the contract."),
  new Agent("lawyer", "gemini-2.5-flash").instruct("Review for legal compliance."),
  { approvedKey: "approved", maxRounds: 2 },
);
```
:::
::::

**Data flow:** Similar to `review_loop` but with approval semantics. The supervisor marks `state[approval_key]` as approved or requests changes.

______________________________________________________________________

## `map_reduce` — Fan-Out Over Items

Apply a mapper agent to each item, then reduce results.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
pipeline = map_reduce(
    mapper=Agent("analyzer").instruct("Analyze this item: {item}"),
    reducer=Agent("synthesizer").instruct("Synthesize all analyses."),
    items_key="items",
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const pipeline = mapReduce(
  new Agent("analyzer", "gemini-2.5-flash").instruct("Analyze this item: {item}"),
  new Agent("synthesizer", "gemini-2.5-flash").instruct("Synthesize all analyses."),
  { itemsKey: "items", resultKey: "report" },
);
```
:::
::::

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

All patterns above work with any execution backend. The definition is identical — only the engine selection changes:

::::{tab-set}
:::{tab-item} ADK (default)
```python
pipeline = review_loop(
    worker=Agent("writer").instruct("Write."),
    reviewer=Agent("reviewer").instruct("Review."),
    quality_key="score",
    target=0.8,
)
response = pipeline.ask("Write about AI safety")
```
:::
:::{tab-item} Temporal (in dev)
```python
from temporalio.client import Client
client = await Client.connect("localhost:7233")

# Same pattern — each review iteration is checkpointed
pipeline = review_loop(
    worker=Agent("writer").instruct("Write."),
    reviewer=Agent("reviewer").instruct("Review."),
    quality_key="score",
    target=0.8,
).engine("temporal", client=client, task_queue="quality")

# If crash occurs mid-loop, completed iterations replay from cache
response = await pipeline.ask_async("Write about AI safety")
```
:::
:::{tab-item} asyncio (in dev)
```python
pipeline = review_loop(
    worker=Agent("writer").instruct("Write."),
    reviewer=Agent("reviewer").instruct("Review."),
    quality_key="score",
    target=0.8,
).engine("asyncio")

response = await pipeline.ask_async("Write about AI safety")
```
:::
::::

Patterns with natural checkpoint boundaries (each step in `chain`, each iteration in `review_loop`) are especially well-suited for durable execution. See [Temporal Guide](temporal-guide.md) for details.

:::{seealso}
- [Execution Backends](execution-backends.md) — backend selection and capability matrix
- [Temporal Guide](temporal-guide.md) — durable execution patterns and constraints
- [Expression Language](expression-language.md) — the operator equivalents of these patterns
:::
