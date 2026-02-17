# Expression Language

Nine operators compose any agent topology. All operators are **immutable** -- sub-expressions can be safely reused across different pipelines.

## Operator Summary

| Operator | Meaning | ADK Type |
|----------|---------|----------|
| `a >> b` | Sequence | `SequentialAgent` |
| `a >> fn` | Function step | Zero-cost transform |
| `a \| b` | Parallel | `ParallelAgent` |
| `a * 3` | Loop (fixed) | `LoopAgent` |
| `a * until(pred)` | Loop (conditional) | `LoopAgent` + checkpoint |
| `a @ Schema` | Typed output | `output_schema` |
| `a // b` | Fallback | First-success chain |
| `Route("key").eq(...)` | Branch | Deterministic routing |
| `S.pick(...)`, `S.rename(...)` | State transforms | Dict operations via `>>` |

## Immutability

All operators produce new expression objects. Sub-expressions can be safely reused:

```python
review = agent_a >> agent_b
pipeline_1 = review >> agent_c  # Independent
pipeline_2 = review >> agent_d  # Independent
```

## `>>` -- Pipeline (Sequential)

The `>>` operator chains agents into a sequential pipeline. Each agent runs after the previous one completes:

```python
from adk_fluent import Agent

pipeline = (
    Agent("extractor", "gemini-2.5-flash").instruct("Extract entities.").outputs("entities")
    >> Agent("enricher", "gemini-2.5-flash").instruct("Enrich {entities}.")
    >> Agent("formatter", "gemini-2.5-flash").instruct("Format output.")
).build()
```

This produces the same `SequentialAgent` as the builder-style `Pipeline("name").step(...).step(...).build()`.

## `>> fn` -- Function Steps

Plain Python functions compose with `>>` as zero-cost workflow nodes (no LLM call):

```python
def merge_research(state):
    return {"research": state["web"] + "\n" + state["papers"]}

pipeline = web_agent >> merge_research >> writer_agent
```

Functions receive the session state dict and return a dict of state updates. They are useful for data transformations between agent steps.

## `|` -- Parallel (Fan-Out)

The `|` operator runs agents in parallel:

```python
from adk_fluent import Agent

fanout = (
    Agent("web", "gemini-2.5-flash").instruct("Search web.").outputs("web_results")
    | Agent("papers", "gemini-2.5-pro").instruct("Search papers.").outputs("paper_results")
    | Agent("internal", "gemini-2.5-flash").instruct("Search internal docs.").outputs("internal_results")
).build()
```

This produces the same `ParallelAgent` as the builder-style `FanOut("name").branch(...).branch(...).build()`.

## `*` -- Loop

### Fixed Count

Multiply an expression by an integer to loop a fixed number of times:

```python
loop = (
    Agent("writer", "gemini-2.5-flash").instruct("Write draft.")
    >> Agent("reviewer", "gemini-2.5-flash").instruct("Review.")
) * 3
```

### Conditional Loop with `until()`

`* until(pred)` loops until a predicate on session state is satisfied:

```python
from adk_fluent import until

loop = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write.").outputs("quality")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review.")
) * until(lambda s: s.get("quality") == "good", max=5)
```

The `max` parameter sets a safety limit on the number of iterations.

## `@` -- Typed Output

`@` binds a Pydantic schema as the agent's output contract:

```python
from pydantic import BaseModel

class Report(BaseModel):
    title: str
    body: str

agent = Agent("writer").model("gemini-2.5-flash").instruct("Write.") @ Report
```

The agent's output is validated against the schema, ensuring structured, typed responses.

## `//` -- Fallback Chain

`//` tries each agent in order. The first agent to succeed wins:

```python
answer = (
    Agent("fast").model("gemini-2.0-flash").instruct("Quick answer.")
    // Agent("thorough").model("gemini-2.5-pro").instruct("Detailed answer.")
)
```

This is useful for cost optimization: try a cheaper, faster model first and fall back to a more capable model only if needed.

## `Route("key").eq(...)` -- Deterministic Routing

Route on session state without LLM calls:

```python
from adk_fluent import Agent
from adk_fluent._routing import Route

classifier = Agent("classify").model("gemini-2.5-flash").instruct("Classify intent.").outputs("intent")
booker = Agent("booker").model("gemini-2.5-flash").instruct("Book flights.")
info = Agent("info").model("gemini-2.5-flash").instruct("Provide info.")

# Route on exact match — zero LLM calls for routing
pipeline = classifier >> Route("intent").eq("booking", booker).eq("info", info)

# Dict shorthand
pipeline = classifier >> {"booking": booker, "info": info}
```

The dict shorthand `>> {"key": agent}` is equivalent to `Route` with `.eq()` for each key-value pair.

## Conditional Gating

`.proceed_if()` gates an agent's execution based on a state predicate:

```python
enricher = (
    Agent("enricher")
    .model("gemini-2.5-flash")
    .instruct("Enrich the data.")
    .proceed_if(lambda s: s.get("valid") == "yes")
)
```

The agent only runs if the predicate returns a truthy value.

## Full Composition

All operators compose into a single expression:

```python
from pydantic import BaseModel
from adk_fluent import Agent, S, until

class Report(BaseModel):
    title: str
    body: str
    confidence: float

pipeline = (
    (   Agent("web").model("gemini-2.5-flash").instruct("Search web.")
      | Agent("scholar").model("gemini-2.5-flash").instruct("Search papers.")
    )
    >> S.merge("web", "scholar", into="research")
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write.") @ Report
       // Agent("writer_b").model("gemini-2.5-pro").instruct("Write.") @ Report
    >> (
        Agent("critic").model("gemini-2.5-flash").instruct("Score.").outputs("confidence")
        >> Agent("reviser").model("gemini-2.5-flash").instruct("Improve.")
    ) * until(lambda s: s.get("confidence", 0) >= 0.85, max=4)
)
```

This expression combines parallel fan-out (`|`), state transforms (`S.merge`), typed output (`@ Report`), fallback (`//`), and conditional loops (`* until`).
