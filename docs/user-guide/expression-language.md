# Expression Language

Nine operators compose any agent topology. All operators are **immutable** -- sub-expressions can be safely reused across different pipelines.

:::{tip}
**Visual learner?** Open the [Operator Algebra Interactive Reference](../operator-algebra-reference.html){target="_blank"} for animated SVG flow diagrams, code examples, and composition rules for all 9 operators.
:::

:::{note} Python uses operators, TypeScript uses method chains
JavaScript has no operator overloading, so the TypeScript package replaces every operator with an explicit method call. Pick your language with the tabs on each example.

| Python | TypeScript | Returns |
| --- | --- | --- |
| `a >> b` | `a.then(b)` | `Pipeline` |
| `a \| b` | `a.parallel(b)` | `FanOut` |
| `a * 3` | `a.times(3)` | `Loop` |
| `a * until(pred, max=5)` | `a.timesUntil(pred, { max: 5 })` | `Loop` |
| `a // b` | `a.fallback(b)` | `Fallback` |
| `a @ Schema` | `a.outputAs(schema)` | `Agent` |
:::

```{raw} html
<div class="arch-diagram-wrapper">
  <svg viewBox="0 0 740 340" fill="none" xmlns="http://www.w3.org/2000/svg" class="arch-diagram" aria-label="Operator visual reference showing all 9 operators">
    <defs>
      <marker id="el-arr" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5" orient="auto">
        <path d="M0 0 L10 4 L0 8Z" fill="#e94560"/>
      </marker>
      <marker id="el-arr-blue" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5" orient="auto">
        <path d="M0 0 L10 4 L0 8Z" fill="#0ea5e9"/>
      </marker>
      <marker id="el-arr-green" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5" orient="auto">
        <path d="M0 0 L10 4 L0 8Z" fill="#10b981"/>
      </marker>
      <marker id="el-arr-purple" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5" orient="auto">
        <path d="M0 0 L10 4 L0 8Z" fill="#a78bfa"/>
      </marker>
      <marker id="el-arr-pink" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5" orient="auto">
        <path d="M0 0 L10 4 L0 8Z" fill="#f472b6"/>
      </marker>
    </defs>

    <!-- Title -->
    <text x="370" y="20" text-anchor="middle" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="700" letter-spacing="0.12em">OPERATOR VISUAL REFERENCE</text>
    <line x1="60" y1="28" x2="680" y2="28" stroke="#1e2d4a" stroke-width="0.5"/>

    <!-- >> Sequence -->
    <g transform="translate(20, 48)">
      <text x="0" y="12" fill="#e94560" font-family="'JetBrains Mono', monospace" font-size="14" font-weight="700">&gt;&gt;</text>
      <text x="30" y="12" fill="#94a3b8" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="600">Sequence</text>
      <rect x="110" y="0" width="44" height="20" rx="6" fill="#e9456018" stroke="#e94560" stroke-width="1"/>
      <text x="132" y="14" text-anchor="middle" fill="#e94560" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">a</text>
      <line x1="160" y1="10" x2="188" y2="10" stroke="#e94560" stroke-width="1.2" marker-end="url(#el-arr)"/>
      <rect x="196" y="0" width="44" height="20" rx="6" fill="#e9456018" stroke="#e94560" stroke-width="1"/>
      <text x="218" y="14" text-anchor="middle" fill="#e94560" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">b</text>
      <line x1="246" y1="10" x2="274" y2="10" stroke="#e94560" stroke-width="1.2" marker-end="url(#el-arr)"/>
      <rect x="282" y="0" width="44" height="20" rx="6" fill="#e9456018" stroke="#e94560" stroke-width="1"/>
      <text x="304" y="14" text-anchor="middle" fill="#e94560" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">c</text>
      <text x="360" y="13" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="8">SequentialAgent</text>
    </g>

    <!-- | Parallel -->
    <g transform="translate(20, 88)">
      <text x="0" y="22" fill="#0ea5e9" font-family="'JetBrains Mono', monospace" font-size="14" font-weight="700">|</text>
      <text x="30" y="22" fill="#94a3b8" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="600">Parallel</text>
      <line x1="120" y1="22" x2="148" y2="2" stroke="#0ea5e9" stroke-width="1.2"/>
      <line x1="120" y1="22" x2="148" y2="22" stroke="#0ea5e9" stroke-width="1.2"/>
      <line x1="120" y1="22" x2="148" y2="42" stroke="#0ea5e9" stroke-width="1.2"/>
      <rect x="152" y="-6" width="44" height="18" rx="5" fill="#0ea5e918" stroke="#0ea5e9" stroke-width="1"/>
      <text x="174" y="8" text-anchor="middle" fill="#0ea5e9" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">a</text>
      <rect x="152" y="14" width="44" height="18" rx="5" fill="#0ea5e918" stroke="#0ea5e9" stroke-width="1"/>
      <text x="174" y="28" text-anchor="middle" fill="#0ea5e9" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">b</text>
      <rect x="152" y="34" width="44" height="18" rx="5" fill="#0ea5e918" stroke="#0ea5e9" stroke-width="1"/>
      <text x="174" y="48" text-anchor="middle" fill="#0ea5e9" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">c</text>
      <line x1="200" y1="2" x2="228" y2="22" stroke="#0ea5e9" stroke-width="1.2"/>
      <line x1="200" y1="22" x2="228" y2="22" stroke="#0ea5e9" stroke-width="1.2"/>
      <line x1="200" y1="42" x2="228" y2="22" stroke="#0ea5e9" stroke-width="1.2"/>
      <circle cx="120" cy="22" r="3" fill="#0ea5e9"/>
      <circle cx="228" cy="22" r="3" fill="#0ea5e9"/>
      <text x="360" y="25" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="8">ParallelAgent</text>
    </g>

    <!-- * Loop -->
    <g transform="translate(20, 156)">
      <text x="0" y="14" fill="#10b981" font-family="'JetBrains Mono', monospace" font-size="14" font-weight="700">*</text>
      <text x="30" y="14" fill="#94a3b8" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="600">Loop</text>
      <rect x="110" y="2" width="80" height="20" rx="6" fill="#10b98118" stroke="#10b981" stroke-width="1"/>
      <text x="150" y="16" text-anchor="middle" fill="#10b981" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">body</text>
      <path d="M195 12 Q220 12 220 -2 Q220 -12 150 -12 Q105 -12 105 -2 Q105 2 110 5" stroke="#10b981" stroke-width="1" fill="none" stroke-dasharray="3,2"/>
      <text x="158" y="-5" text-anchor="middle" fill="#10b981" font-family="'JetBrains Mono', monospace" font-size="7" font-weight="600">n times</text>
      <text x="360" y="15" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="8">LoopAgent</text>
    </g>

    <!-- @ Schema -->
    <g transform="translate(20, 196)">
      <text x="0" y="14" fill="#f59e0b" font-family="'JetBrains Mono', monospace" font-size="14" font-weight="700">@</text>
      <text x="30" y="14" fill="#94a3b8" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="600">Typed</text>
      <rect x="110" y="2" width="50" height="20" rx="6" fill="#f59e0b18" stroke="#f59e0b" stroke-width="1"/>
      <text x="135" y="16" text-anchor="middle" fill="#f59e0b" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">agent</text>
      <text x="172" y="16" fill="#f59e0b" font-family="'JetBrains Mono', monospace" font-size="10" font-weight="700">→</text>
      <rect x="186" y="0" width="80" height="24" rx="6" fill="#f59e0b10" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,2"/>
      <text x="226" y="16" text-anchor="middle" fill="#f59e0b" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="600">Schema{}</text>
      <text x="360" y="15" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="8">output_schema</text>
    </g>

    <!-- // Fallback -->
    <g transform="translate(20, 236)">
      <text x="0" y="14" fill="#a78bfa" font-family="'JetBrains Mono', monospace" font-size="14" font-weight="700">//</text>
      <text x="30" y="14" fill="#94a3b8" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="600">Fallback</text>
      <rect x="110" y="2" width="44" height="20" rx="6" fill="#a78bfa18" stroke="#a78bfa" stroke-width="1"/>
      <text x="132" y="16" text-anchor="middle" fill="#a78bfa" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">a</text>
      <line x1="158" y1="12" x2="170" y2="12" stroke="#e94560" stroke-width="1.2"/>
      <text x="174" y="16" fill="#e94560" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="700">✗</text>
      <line x1="182" y1="12" x2="194" y2="12" stroke="#a78bfa" stroke-width="1.2" marker-end="url(#el-arr-purple)"/>
      <rect x="202" y="2" width="44" height="20" rx="6" fill="#a78bfa18" stroke="#a78bfa" stroke-width="1"/>
      <text x="224" y="16" text-anchor="middle" fill="#a78bfa" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">b</text>
      <line x1="250" y1="12" x2="262" y2="12" stroke="#e94560" stroke-width="1.2"/>
      <text x="266" y="16" fill="#e94560" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="700">✗</text>
      <line x1="274" y1="12" x2="286" y2="12" stroke="#a78bfa" stroke-width="1.2" marker-end="url(#el-arr-purple)"/>
      <rect x="294" y="2" width="44" height="20" rx="6" fill="#a78bfa18" stroke="#a78bfa" stroke-width="1"/>
      <text x="316" y="16" text-anchor="middle" fill="#a78bfa" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600">c</text>
      <text x="360" y="15" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="8">first success</text>
    </g>

    <!-- Route -->
    <g transform="translate(20, 278)">
      <text x="0" y="18" fill="#f472b6" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="700">Route</text>
      <text x="46" y="18" fill="#94a3b8" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="600">Branch</text>
      <rect x="110" y="4" width="64" height="24" rx="6" fill="#f472b618" stroke="#f472b6" stroke-width="1"/>
      <text x="142" y="20" text-anchor="middle" fill="#f472b6" font-family="'JetBrains Mono', monospace" font-size="8" font-weight="600">state[key]</text>
      <line x1="178" y1="10" x2="220" y2="0" stroke="#f472b6" stroke-width="1" marker-end="url(#el-arr-pink)"/>
      <line x1="178" y1="22" x2="220" y2="32" stroke="#f472b6" stroke-width="1" marker-end="url(#el-arr-pink)"/>
      <text x="230" y="4" fill="#f472b6" font-family="'JetBrains Mono', monospace" font-size="8">"a" → handler_a</text>
      <text x="230" y="38" fill="#f472b6" font-family="'JetBrains Mono', monospace" font-size="8">"b" → handler_b</text>
      <text x="360" y="20" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="8">deterministic routing</text>
    </g>
  </svg>
</div>
```

## Operator Summary

| Operator                       | Meaning            | ADK Type                 |
| ------------------------------ | ------------------ | ------------------------ |
| `a >> b`                       | Sequence           | `SequentialAgent`        |
| `a >> fn`                      | Function step      | Zero-cost transform      |
| `a \| b`                       | Parallel           | `ParallelAgent`          |
| `a * 3`                        | Loop (fixed)       | `LoopAgent`              |
| `a * until(pred)`              | Loop (conditional) | `LoopAgent` + checkpoint |
| `a @ Schema`                   | Typed output       | `output_schema`          |
| `a // b`                       | Fallback           | First-success chain      |
| `Route("key").eq(...)`         | Branch             | Deterministic routing    |
| `S.pick(...)`, `S.rename(...)` | State transforms   | Dict operations via `>>` |

## Reading an expression

Operators follow **Python's** precedence, which does not match reading order. In a mixed expression, `*` binds tighter than `@`, which binds tighter than `//`, which binds tighter than `|`, which binds tighter than `>>`.

```{mermaid}
flowchart LR
    T1[tightest] --> P1["*<br/>loop"]
    P1 --> P2["@<br/>typed output"]
    P2 --> P3["//<br/>fallback"]
    P3 --> P4["|<br/>parallel"]
    P4 --> P5["&gt;&gt;<br/>sequence"]
    P5 --> T2[loosest]

    classDef a fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef op fill:#fff3e0,stroke:#e65100,color:#bf360c
    class T1,T2 a
    class P1,P2,P3,P4,P5 op
```

Practical consequence: `a | b >> c` is `(a | b) >> c` — the parallel block runs, then `c`. And `a >> b @ Schema` is `a >> (b @ Schema)` — only `b` is constrained. When in doubt, add parens; they are never wrong.

:::{tip} The "outer" operator is where to start reading
Read expressions from the outermost operator inward. `>>` chains usually frame the whole pipeline, with `|`, `//`, `*`, and `@` nested inside the steps.
:::

## Immutability

All operators produce new expression objects. Sub-expressions can be safely reused:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
review = agent_a >> agent_b
pipeline_1 = review >> agent_c  # Independent
pipeline_2 = review >> agent_d  # Independent
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const review = agentA.then(agentB);
const pipeline1 = review.then(agentC); // Independent
const pipeline2 = review.then(agentD); // Independent
```
:::
::::

## `>>` -- Pipeline (Sequential)

The `>>` operator (Python) / `.then()` method (TypeScript) chains agents into a sequential pipeline. Each agent runs after the previous one completes:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

pipeline = (
    Agent("extractor", "gemini-2.5-flash").instruct("Extract entities.").writes("entities")
    >> Agent("enricher", "gemini-2.5-flash").instruct("Enrich {entities}.")
    >> Agent("formatter", "gemini-2.5-flash").instruct("Format output.")
).build()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const pipeline = new Agent("extractor", "gemini-2.5-flash")
  .instruct("Extract entities.")
  .writes("entities")
  .then(new Agent("enricher", "gemini-2.5-flash").instruct("Enrich {entities}."))
  .then(new Agent("formatter", "gemini-2.5-flash").instruct("Format output."))
  .build();
```
:::
::::

This produces the same `SequentialAgent` as the builder-style `Pipeline("name").step(...).step(...).build()`.

## Function Steps

Plain functions compose as zero-cost workflow nodes (no LLM call):

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
def merge_research(state):
    return {"research": state["web"] + "\n" + state["papers"]}

pipeline = web_agent >> merge_research >> writer_agent
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { tap } from "adk-fluent-ts";

const mergeResearch = tap((state) => {
  state.research = `${state.web}\n${state.papers}`;
});

const pipeline = webAgent.then(mergeResearch).then(writerAgent);
```
:::
::::

Function steps receive the session state and can mutate it (TypeScript) or return a dict of updates (Python). They are useful for data transformations between agent steps.

## `|` / `.parallel()` -- Parallel (Fan-Out)

Run agents concurrently:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

fanout = (
    Agent("web", "gemini-2.5-flash").instruct("Search web.").writes("web_results")
    | Agent("papers", "gemini-2.5-pro").instruct("Search papers.").writes("paper_results")
    | Agent("internal", "gemini-2.5-flash").instruct("Search internal docs.").writes("internal_results")
).build()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const fanout = new Agent("web", "gemini-2.5-flash")
  .instruct("Search web.")
  .writes("web_results")
  .parallel(
    new Agent("papers", "gemini-2.5-pro").instruct("Search papers.").writes("paper_results"),
  )
  .parallel(
    new Agent("internal", "gemini-2.5-flash")
      .instruct("Search internal docs.")
      .writes("internal_results"),
  )
  .build();
```
:::
::::

This produces the same `ParallelAgent` as the builder-style `FanOut("name").branch(...).branch(...).build()`.

## `*` / `.times()` -- Loop

### Fixed Count

Repeat an expression a fixed number of times:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
loop = (
    Agent("writer", "gemini-2.5-flash").instruct("Write draft.")
    >> Agent("reviewer", "gemini-2.5-flash").instruct("Review.")
) * 3
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const loop = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write draft.")
  .then(new Agent("reviewer", "gemini-2.5-flash").instruct("Review."))
  .times(3);
```
:::
::::

### Conditional Loop with `until()`

Loop until a predicate on session state is satisfied:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import until

loop = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write.").writes("quality")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review.")
) * until(lambda s: s.get("quality") == "good", max=5)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const loop = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write.")
  .writes("quality")
  .then(new Agent("reviewer", "gemini-2.5-flash").instruct("Review."))
  .timesUntil((s) => s.quality === "good", { max: 5 });
```
:::
::::

The `max` parameter sets a safety limit on the number of iterations.

## `@` / `.outputAs()` -- Typed Output

Bind a structured-output schema as the agent's response contract:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from pydantic import BaseModel

class Report(BaseModel):
    title: str
    body: str

agent = Agent("writer").model("gemini-2.5-flash").instruct("Write.") @ Report
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
// Use any opaque schema descriptor — Zod, JSON Schema, or a plain object.
const ReportSchema = {
  type: "object",
  properties: {
    title: { type: "string" },
    body: { type: "string" },
  },
  required: ["title", "body"],
} as const;

const agent = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write.")
  .outputAs(ReportSchema);
```
:::
::::

The agent's output is validated against the schema, ensuring structured, typed responses.

## `//` / `.fallback()` -- Fallback Chain

Try each agent in order. The first agent to succeed wins:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
answer = (
    Agent("fast").model("gemini-2.0-flash").instruct("Quick answer.")
    // Agent("thorough").model("gemini-2.5-pro").instruct("Detailed answer.")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const answer = new Agent("fast", "gemini-2.0-flash")
  .instruct("Quick answer.")
  .fallback(new Agent("thorough", "gemini-2.5-pro").instruct("Detailed answer."));
```
:::
::::

This is useful for cost optimization: try a cheaper, faster model first and fall back to a more capable model only if needed.

## `Route("key").eq(...)` -- Deterministic Routing

Route on session state without LLM calls:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, Route

classifier = Agent("classify").model("gemini-2.5-flash").instruct("Classify intent.").writes("intent")
booker = Agent("booker").model("gemini-2.5-flash").instruct("Book flights.")
info = Agent("info").model("gemini-2.5-flash").instruct("Provide info.")

# Route on exact match — zero LLM calls for routing
pipeline = classifier >> Route("intent").eq("booking", booker).eq("info", info)

# Dict shorthand
pipeline = classifier >> {"booking": booker, "info": info}
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, Route } from "adk-fluent-ts";

const classifier = new Agent("classify", "gemini-2.5-flash")
  .instruct("Classify intent.")
  .writes("intent");
const booker = new Agent("booker", "gemini-2.5-flash").instruct("Book flights.");
const info = new Agent("info", "gemini-2.5-flash").instruct("Provide info.");

const pipeline = classifier.then(
  new Route("intent").eq("booking", booker).eq("info", info),
);
```
:::
::::

## Conditional Gating

`.proceedIf()` / `.proceed_if()` gates an agent's execution based on a state predicate:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
enricher = (
    Agent("enricher")
    .model("gemini-2.5-flash")
    .instruct("Enrich the data.")
    .proceed_if(lambda s: s.get("valid") == "yes")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, gate } from "adk-fluent-ts";

const enricher = gate(
  (s) => s.valid === "yes",
  new Agent("enricher", "gemini-2.5-flash").instruct("Enrich the data."),
);
```
:::
::::

The agent only runs if the predicate returns a truthy value.

## Full Composition

All operators compose into a single expression. The following example combines every operator:

```
Full composition topology:

  ┬─ web ────┐
  └─ scholar ┘  (|)
       │
  S.merge(into="research")
       │
  writer @ Report // writer_b @ Report  (//)
       │
  ┌──► critic ──► reviser ──┐
  └── until(confidence≥0.85) ┘  (*)
```

::::{tab-set}
:::{tab-item} Python
:sync: python

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
        Agent("critic").model("gemini-2.5-flash").instruct("Score.").writes("confidence")
        >> Agent("reviser").model("gemini-2.5-flash").instruct("Improve.")
    ) * until(lambda s: s.get("confidence", 0) >= 0.85, max=4)
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, S } from "adk-fluent-ts";

const ReportSchema = {
  type: "object",
  properties: {
    title: { type: "string" },
    body: { type: "string" },
    confidence: { type: "number" },
  },
  required: ["title", "body", "confidence"],
} as const;

const pipeline = new Agent("web", "gemini-2.5-flash")
  .instruct("Search web.")
  .parallel(new Agent("scholar", "gemini-2.5-flash").instruct("Search papers."))
  .then(S.merge_(["web", "scholar"], "research"))
  .then(
    new Agent("writer", "gemini-2.5-flash")
      .instruct("Write.")
      .outputAs(ReportSchema)
      .fallback(
        new Agent("writer_b", "gemini-2.5-pro").instruct("Write.").outputAs(ReportSchema),
      ),
  )
  .then(
    new Agent("critic", "gemini-2.5-flash")
      .instruct("Score.")
      .writes("confidence")
      .then(new Agent("reviser", "gemini-2.5-flash").instruct("Improve."))
      .timesUntil((s) => Number(s.confidence ?? 0) >= 0.85, { max: 4 }),
  );
```
:::
::::

This expression combines parallel fan-out (`|`), state transforms (`S.merge`), typed output (`@ Report`), fallback (`//`), and conditional loops (`* until`).

## Namespace composites attach via the same grammar

The ``>>`` operator is overloaded so that a **namespace composite** on the left attaches itself to a **builder** on the right via the builder's corresponding setter. One grammar, one direction, every namespace:

```python
# Python
from adk_fluent import Agent, C, G, M, P, T

(
    C.window(n=5)                                    # context
    >> P.role("analyst") + P.task("crunch numbers")  # instruction
    >> T.fn(search) | T.fn(fetch)                    # tools
    >> G.pii() | G.length(max=500)                   # guards
    >> M.retry(max_attempts=3) | M.log()             # middleware
    >> Agent("worker", "gemini-2.5-flash")
)
```

Each left-hand composite dispatches to the method listed below:

| Composite       | Dispatches to      | Python            | TypeScript                       |
| --------------- | ------------------ | ----------------- | -------------------------------- |
| ``CTransform``  | ``.context(…)``    | ``C.xxx() >> a``  | ``C.xxx().attachTo(a)``          |
| ``PTransform``  | ``.instruct(…)``   | ``P.xxx() >> a``  | ``P.xxx().attachTo(a)``          |
| ``TComposite``  | ``.tools(…)``      | ``T.xxx() >> a``  | ``T.xxx().attachTo(a)``          |
| ``GComposite``  | ``.guard(…)``      | ``G.xxx() >> a``  | ``G.xxx().attachTo(a)``          |
| ``MComposite``  | ``.middleware(…)`` | ``M.xxx() >> a``  | ``M.xxx().attachTo(a)``          |
| ``AComposite``  | ``.artifacts(…)``  | ``A.xxx() >> a``  | ``A.xxx().attachTo(a)``          |

TypeScript cannot overload ``>>``, so each composite exposes an ``.attachTo(builder)`` method that performs the same dispatch:

```typescript
// TypeScript
import { Agent, C, P, T, G, M } from "adk-fluent-ts";

let a = new Agent("worker", "gemini-2.5-flash");
a = C.window(5).attachTo(a);
a = P.role("analyst").add(P.task("crunch numbers")).attachTo(a);
a = T.fn(search).attachTo(a);
a = G.length({ max: 500 }).attachTo(a);
a = M.retry({ maxAttempts: 3 }).pipe(M.log()).attachTo(a);
```

### Named-word aliases

Every single-letter namespace has a named-word alias that resolves to the exact same class. Pick whichever reads better for your team:

| Single letter | Named alias     | Python | TypeScript                                          |
| ------------- | --------------- | :----: | :-------------------------------------------------: |
| ``S``         | ``State``       |   ✅   | ❌ (``State`` is already an exported type alias)    |
| ``C``         | ``Context``     |   ✅   |                         ✅                          |
| ``P``         | ``Prompt``      |   ✅   |                         ✅                          |
| ``T``         | ``Tool``        |   ✅   |                         ✅                          |
| ``G``         | ``Guard``       |   ✅   |                         ✅                          |
| ``M``         | ``Middleware``  |   ✅   |                         ✅                          |
| ``A``         | ``Artifact``    |   ✅   |                         ✅                          |
| ``E``         | ``Eval``        |   ✅   |                         ✅                          |
| ``R``         | ``Reactive``    |   ✅   |                         ✅                          |
| ``H``         | ``Harness``     |   ✅   |                         ✅                          |
| ``UI``        | ``Ui``          |   ✅   |                         ✅                          |

```python
# equivalent
from adk_fluent import C, Context
C.window(n=5) >> agent
Context.window(n=5) >> agent    # same behavior, no imports change
```

## Backend Compatibility

All expression operators work identically across backends. The *definition* is the same — only execution semantics change:

| Operator | ADK (default) | Temporal (in dev) | asyncio (in dev) |
|----------|--------------|-------------------|------------------|
| `>>` (sequence) | Sequential agents | Sequential activities | Sequential coroutines |
| `\|` (parallel) | Parallel agents | `asyncio.gather()` over activities | `asyncio.gather()` |
| `*` (loop) | Loop agent | Checkpointed `while` loop | `while` loop |
| `//` (fallback) | Fallback agent | try/except over activities | try/except |
| `@ Schema` | output_schema | Same (schema on activity) | Same |
| `Route(...)` | Custom agent | Inline deterministic code | Inline |

When using Temporal, deterministic operators (`>>`, `Route`, `S.*`) become replay-safe workflow code, while non-deterministic operators (anything involving an LLM call) become cached activities. See [Temporal Guide](temporal-guide.md) for details.

:::{seealso}
- [Execution Backends](execution-backends.md) — backend selection and capability matrix
- [Temporal Guide](temporal-guide.md) — how operators map to Temporal concepts
:::
