# Getting Started

:::{note}
This documentation is for adk-fluent **v{{version}}** ([PyPI](https://pypi.org/project/adk-fluent/)).
:::

This page gets you from zero to a working agent in 5 minutes.
By the end, you'll understand the builder pattern, the expression operators,
and when to use each.

:::{note} Python and TypeScript — click a tab once
Most samples ship with a **Python** / **TypeScript** tab. Click
either — your choice syncs across every tab on the site and
sticks as you navigate. The semantics are identical; only the
operator syntax differs (Python uses `>>` / `|` / `*` / `//` /
`@`; TypeScript uses `.then()` / `.parallel()` / `.times()` /
`.fallback()` / `.outputAs()`). If you picked TypeScript, also
see the {doc}`user-guide/typescript` landing page.
:::

## Install

::::{tab-set}
:::{tab-item} Python
:sync: python

```bash
pip install adk-fluent
```

Autocomplete works immediately -- the package ships with `.pyi` type stubs for every builder. Type `Agent("name").` and your IDE shows all available methods with type hints.
:::
:::{tab-item} TypeScript
:sync: ts

```bash
# adk-fluent-ts lives in the monorepo (not yet on npm)
git clone https://github.com/vamsiramakrishnan/adk-fluent.git
cd adk-fluent/ts
npm install
npm run build
```

Autocomplete works out of the box — the package is written in TypeScript, so hover-docs and type inference light up immediately in VS Code, JetBrains, Neovim (with `tsserver`), and any LSP-aware editor. See {doc}`user-guide/typescript` for install, imports, and the operator-mapping reference.
:::
::::

## Your First Agent

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.").build()
# Returns a real google.adk.agents.llm_agent.LlmAgent — not a wrapper.

print(agent.ask("Hello, who are you?"))
# => Hi! I'm a helpful assistant. How can I help you today?
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const agent = new Agent("helper", "gemini-2.5-flash")
  .instruct("You are a helpful assistant.")
  .build();
// Returns a real @google/adk LlmAgent — not a wrapper.

console.log(await agent.ask("Hello, who are you?"));
// => Hi! I'm a helpful assistant. How can I help you today?
```
:::
::::

That's a full agent. `agent` is a real native ADK `LlmAgent` — it
works with `adk web`, `adk run`, `adk deploy`, or any ADK API.

:::{warning} Jupyter, FastAPI, or any running event loop?
Python's `.ask()` and `.map()` are **sync and blocking** — they
raise `RuntimeError` inside an already-running event loop. Use
`await agent.ask_async(...)` and `await agent.map_async(...)`
instead. See [Execution](user-guide/execution.md) for the full
async surface. (TypeScript is async-only; no equivalent footgun.)
:::

## Your First Pipeline

Chain agents sequentially with the `Pipeline` builder or the sequential operator — `>>` in Python, `.then()` in TypeScript.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, Pipeline

# Builder style -- explicit, great for complex configurations
pipeline = (
    Pipeline("research")
    .step(Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
    .build()
)

# Operator style -- concise, great for composing reusable parts
pipeline = (
    Agent("searcher", "gemini-2.5-flash").instruct("Search for information.")
    >> Agent("writer", "gemini-2.5-flash").instruct("Write a summary.")
).build()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, Pipeline } from "adk-fluent-ts";

// Builder style -- explicit, great for complex configurations
const pipeline = new Pipeline("research")
  .step(new Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
  .step(new Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
  .build();

// Method-chain style -- concise, great for composing reusable parts
const pipeline2 = new Agent("searcher", "gemini-2.5-flash")
  .instruct("Search for information.")
  .then(new Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
  .build();
```
:::
::::

Both produce an identical `SequentialAgent`. The builder style shines when each step needs callbacks, tools, and context engineering. The operator / method-chain style excels at composing reusable sub-expressions.

## Parallel Execution

Run agents concurrently with `FanOut` or the parallel operator — `|` in Python, `.parallel()` in TypeScript.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, FanOut

fanout = (
    FanOut("parallel_research")
    .branch(Agent("web", "gemini-2.5-flash").instruct("Search the web."))
    .branch(Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
    .build()
)

# Or with operators:
fanout = (
    Agent("web", "gemini-2.5-flash").instruct("Search the web.")
    | Agent("papers", "gemini-2.5-flash").instruct("Search papers.")
).build()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, FanOut } from "adk-fluent-ts";

const fanout = new FanOut("parallel_research")
  .branch(new Agent("web", "gemini-2.5-flash").instruct("Search the web."))
  .branch(new Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
  .build();

// Or with the method-chain operator:
const fanout2 = new Agent("web", "gemini-2.5-flash")
  .instruct("Search the web.")
  .parallel(new Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
  .build();
```
:::
::::

## Loops

Iterate a fixed number of times — `* 3` in Python, `.times(3)` in TypeScript. Use `Loop` / `loop_until` / `timesUntil` when you need a predicate-driven exit.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, Loop

loop = (
    Loop("refine")
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write draft."))
    .step(Agent("critic", "gemini-2.5-flash").instruct("Critique."))
    .max_iterations(3)
    .build()
)

# Or with operators:
loop = (
    Agent("writer", "gemini-2.5-flash").instruct("Write draft.")
    >> Agent("critic", "gemini-2.5-flash").instruct("Critique.")
) * 3
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, Loop } from "adk-fluent-ts";

const loop = new Loop("refine")
  .step(new Agent("writer", "gemini-2.5-flash").instruct("Write draft."))
  .step(new Agent("critic", "gemini-2.5-flash").instruct("Critique."))
  .maxIterations(3)
  .build();

// Or with the method-chain operator:
const loop2 = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write draft.")
  .then(new Agent("critic", "gemini-2.5-flash").instruct("Critique."))
  .times(3)
  .build();
```
:::
::::

## Two Styles, Same Result

Every workflow can be expressed two ways. Both produce identical ADK objects:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
# Builder style
pipeline = (
    Pipeline("research")
    .step(Agent("web", "gemini-2.5-flash").instruct("Search web.").writes("web_data"))
    .step(Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}."))
    .build()
)

# Operator style
pipeline = (
    Agent("web", "gemini-2.5-flash").instruct("Search web.").writes("web_data")
    >> Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}.")
).build()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
// Builder style
const pipeline = new Pipeline("research")
  .step(
    new Agent("web", "gemini-2.5-flash")
      .instruct("Search web.")
      .writes("web_data"),
  )
  .step(new Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}."))
  .build();

// Method-chain style
const pipeline2 = new Agent("web", "gemini-2.5-flash")
  .instruct("Search web.")
  .writes("web_data")
  .then(new Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}."))
  .build();
```
:::
::::

The builder style shines for complex multi-step workflows where each step is configured with callbacks, tools, and context. The operator style excels at composing reusable sub-expressions:

```python
# Reusable sub-expressions with operators
classify = Agent("classifier", "gemini-2.5-flash").instruct("Classify intent.").writes("intent")
resolve = Agent("resolver", "gemini-2.5-flash").instruct("Resolve {intent}.").tool(lookup_customer)
respond = Agent("responder", "gemini-2.5-flash").instruct("Draft response.")

support_pipeline = classify >> resolve >> respond
# Reuse classify in a different pipeline
escalation_pipeline = classify >> Agent("escalate", "gemini-2.5-flash").instruct("Escalate.")
```

## Putting It Together

Here's a real-world pipeline combining sequential, parallel, state flow, and context isolation:

```{raw} html
<div class="arch-diagram-wrapper">
  <svg viewBox="0 0 680 200" fill="none" xmlns="http://www.w3.org/2000/svg" class="arch-diagram" aria-label="Support pipeline architecture: capture → classify → resolve → respond">
    <defs>
      <linearGradient id="gs-grad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#E65100"/>
        <stop offset="100%" stop-color="#F57C00"/>
      </linearGradient>
      <marker id="gs-arrow" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5" orient="auto">
        <path d="M0 0 L10 4 L0 8Z" fill="#64748b"/>
      </marker>
      <marker id="gs-arrow-accent" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5" orient="auto">
        <path d="M0 0 L10 4 L0 8Z" fill="#F57C00"/>
      </marker>
    </defs>

    <!-- S.capture node -->
    <g>
      <rect x="10" y="60" width="100" height="56" rx="10" fill="#10b98112" stroke="#10b981" stroke-width="1.5"/>
      <text x="60" y="82" text-anchor="middle" fill="#10b981" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="700">S.capture</text>
      <text x="60" y="102" text-anchor="middle" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="8">→ state</text>
    </g>

    <!-- Arrow -->
    <line x1="118" y1="88" x2="158" y2="88" stroke="#64748b" stroke-width="1.2" marker-end="url(#gs-arrow)"/>

    <!-- Classifier node -->
    <g>
      <rect x="166" y="52" width="110" height="72" rx="10" fill="#e9456012" stroke="#e94560" stroke-width="1.5"/>
      <text x="221" y="74" text-anchor="middle" fill="#e94560" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="700">Classifier</text>
      <text x="221" y="90" text-anchor="middle" fill="#64748b" font-family="'JetBrains Mono', monospace" font-size="8">C.none()</text>
      <text x="221" y="108" text-anchor="middle" fill="#94a3b8" font-family="'JetBrains Mono', monospace" font-size="8">.writes("intent")</text>
    </g>

    <!-- Arrow -->
    <line x1="284" y1="88" x2="324" y2="88" stroke="#64748b" stroke-width="1.2" marker-end="url(#gs-arrow)"/>

    <!-- Resolver node -->
    <g>
      <rect x="332" y="44" width="130" height="88" rx="10" fill="#0ea5e912" stroke="#0ea5e9" stroke-width="1.5"/>
      <text x="397" y="68" text-anchor="middle" fill="#0ea5e9" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="700">Resolver</text>
      <text x="397" y="86" text-anchor="middle" fill="#94a3b8" font-family="'JetBrains Mono', monospace" font-size="8">.tool(lookup)</text>
      <text x="397" y="100" text-anchor="middle" fill="#94a3b8" font-family="'JetBrains Mono', monospace" font-size="8">.tool(create_ticket)</text>
      <text x="397" y="118" text-anchor="middle" fill="#64748b" font-family="'JetBrains Mono', monospace" font-size="8">.writes("resolution")</text>
    </g>

    <!-- Arrow -->
    <line x1="470" y1="88" x2="510" y2="88" stroke="#64748b" stroke-width="1.2" marker-end="url(#gs-arrow)"/>

    <!-- Responder node -->
    <g>
      <rect x="518" y="56" width="110" height="64" rx="10" fill="#FFB74D12" stroke="#FFB74D" stroke-width="1.5"/>
      <text x="573" y="82" text-anchor="middle" fill="#FFB74D" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="700">Responder</text>
      <text x="573" y="100" text-anchor="middle" fill="#64748b" font-family="'JetBrains Mono', monospace" font-size="8">{resolution}</text>
    </g>

    <!-- State flow annotations (curved lines below) -->
    <path d="M60 124 Q60 160 130 160 Q221 160 221 132" stroke="#10b981" stroke-width="1" fill="none" stroke-dasharray="3,3" opacity="0.5"/>
    <text x="140" y="172" fill="#10b981" font-family="'JetBrains Mono', monospace" font-size="7" opacity="0.6">customer_message</text>

    <path d="M221 132 Q221 148 310 148 Q397 148 397 140" stroke="#e94560" stroke-width="1" fill="none" stroke-dasharray="3,3" opacity="0.5"/>
    <text x="310" y="158" fill="#e94560" font-family="'JetBrains Mono', monospace" font-size="7" opacity="0.6">intent</text>

    <path d="M397 140 Q397 152 485 152 Q573 152 573 128" stroke="#0ea5e9" stroke-width="1" fill="none" stroke-dasharray="3,3" opacity="0.5"/>
    <text x="485" y="162" fill="#0ea5e9" font-family="'JetBrains Mono', monospace" font-size="7" opacity="0.6">resolution</text>

    <!-- Pipeline label -->
    <text x="340" y="24" text-anchor="middle" fill="#64748b" font-family="'IBM Plex Sans', sans-serif" font-size="9" font-weight="600" letter-spacing="0.1em">PIPELINE FLOW WITH STATE DATA CONTRACTS</text>
    <line x1="100" y1="32" x2="580" y2="32" stroke="#1e2d4a" stroke-width="0.5"/>
  </svg>
</div>
```

```python
from adk_fluent import Agent, S, C

MODEL = "gemini-2.5-flash"

# Capture the user's message into state
# Classify with no history (C.none() = sees only the current message)
# Route to specialist agents
# Each agent writes to a named state key for explicit data contracts

support = (
    S.capture("customer_message")
    >> Agent("classifier", MODEL)
       .instruct("Classify intent: billing, technical, or general.")
       .context(C.none())
       .writes("intent")
    >> Agent("resolver", MODEL)
       .instruct("Resolve the {intent} issue for: {customer_message}")
       .tool(lookup_customer)
       .tool(create_ticket)
       .writes("resolution")
    >> Agent("responder", MODEL)
       .instruct("Draft a response summarizing: {resolution}")
)
```

This pipeline:
- **Captures** the user message into state with `S.capture()` ([State Transforms](user-guide/state-transforms.md))
- **Isolates context** with `C.none()` so the classifier sees only the current message ([Context Engineering](user-guide/context-engineering.md))
- **Flows data** through named keys with `.writes()` ([Data Flow](user-guide/data-flow.md))
- **Attaches tools** with `.tool()` ([Builders](user-guide/builders.md))

## Test Without an API Key

You don't need a Gemini API key to verify your agent logic works. `.mock()` replaces the LLM with canned responses:

```python
from adk_fluent import Agent

agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .mock(["Hello! I'm here to help."])
)

# Runs instantly, no API call, no cost
print(agent.ask("Hi there"))
# => Hello! I'm here to help.
```

This is how all 68 cookbook examples run in CI — every example uses `.mock()` so tests pass without credentials. Use `.mock()` during development, remove it when you're ready for real LLM calls.

:::{tip} `.test()` — inline smoke tests
For quick validation, chain `.test()` directly:
```python
agent.test("What's 2+2?", contains="4")  # passes silently or raises AssertionError
```
:::

## See What the LLM Sees

One of the most powerful debugging tools: `.llm_anatomy()` shows the exact prompt, context, and tools the LLM receives.

```python
from adk_fluent import Agent, C

agent = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the customer's intent.")
    .context(C.none())
    .writes("intent")
)

agent.llm_anatomy()
# System prompt:  Classify the customer's intent.
# Context:        none (C.none() — current turn only)
# Output key:     intent
# Tools:          (none)
```

This prevents the #1 debugging nightmare: "why is my agent producing garbage?" The answer is always in what the LLM sees.

## Validate and Debug

```python
# Catch config errors before runtime
agent = Agent("x", "gemini-2.5-flash").instruct("Help.").validate()

# See what the builder has configured
agent.explain()

# Generate a visual topology diagram
pipeline.to_mermaid()

# Full diagnostic report
pipeline.doctor()
```

See [Error Reference](user-guide/error-reference.md) for every error type with fix-it examples.

## Async environments (Jupyter, FastAPI)

The warning earlier covers the one-line case: use `ask_async()`
instead of `ask()`. The same rule applies to every sync method.
Here are the three patterns you'll actually use:

```python
# One-shot
result = await agent.ask_async("What is the capital of France?")

# Streaming — yields text chunks as they arrive
async for chunk in agent.stream("Tell me a story"):
    print(chunk, end="")

# Multi-turn conversation in a persisted session
async with agent.session() as chat:
    print(await chat.send("Hi"))
    print(await chat.send("Tell me more"))
```

See [Execution](user-guide/execution.md) for the full async surface.

## Choose Your Path

Now that you know the basics, adk-fluent offers three distinct pathways for agent building. All produce native ADK objects -- they solve different problems at different abstraction levels.

````{grid} 1 2 3 3
---
gutter: 3
---

```{grid-item-card} Pipeline Path -- Python-First Builders
:link: user-guide/expression-language
:link-type: doc

Full Python control with expression operators (`>>` `|` `*` `@` `//`) and 9 namespace modules. Build any topology with type-checked, IDE-friendly builders.

**Best for:** Custom workflows, complex routing, dynamic topologies, callback-heavy agents.

+++
`Agent("a") >> (Agent("b") | Agent("c")) * 3`
```

```{grid-item-card} Skills Path -- Declarative Agent Packages
:link: user-guide/skills
:link-type: doc

Turn YAML + Markdown into executable agent graphs. Domain experts write prompts and topology; engineers inject tools and deploy. One file is docs AND runtime.

**Best for:** Stable topologies, reusable capability libraries, teams with non-Python domain experts.

+++
`Skill("skills/research/") >> Skill("skills/writing/")`
```

```{grid-item-card} Harness Path -- Autonomous Coding Runtimes
:link: user-guide/harness
:link-type: doc

Build Claude-Code-class autonomous agents with the `H` namespace. Five composable layers: intelligence, tools, safety, observability, and runtime.

**Best for:** Agents that need file/shell access, permissions, sandboxing, token budgets, multi-turn REPL.

+++
`H.workspace() + H.web() + H.git_tools()`
```
````

**Not sure which?** See the [Decision Guide](decision-guide.md) for a flowchart. All three compose together -- a harness can load skills for domain expertise, and skills wire agents as pipelines internally.

## What's Next

````{grid} 1 2 2 2
---
gutter: 3
---
```{grid-item-card} User Guide
:link: user-guide/index
:link-type: doc
Deep dive into builders, operators, callbacks, context engineering, and all 9 namespace modules.
```

```{grid-item-card} Cookbook
:link: cookbook/index
:link-type: doc
68 recipes from simple agents to hero workflows like deep research and customer support triage.
```

```{grid-item-card} API Reference
:link: generated/api/index
:link-type: doc
Complete reference for all 135 builders with type signatures, ADK mappings, and examples.
```

```{grid-item-card} Framework Comparison
:link: user-guide/comparison
:link-type: doc
Side-by-side with LangGraph, CrewAI, and native ADK -- see exactly where adk-fluent wins.
```
````

:::{seealso}
- [Expression Language](user-guide/expression-language.md) -- all 9 operators with composition rules
- [Patterns](user-guide/patterns.md) -- higher-order constructors (review_loop, map_reduce, cascade, fan_out_merge)
- [Testing](user-guide/testing.md) -- `.mock()`, `.test()`, and `check_contracts()` for testing without API calls
- [Migration Guide](generated/migration/from-native-adk.md) -- migrate existing native ADK code incrementally
:::
