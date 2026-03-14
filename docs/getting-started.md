# Getting Started

This page gets you from zero to a working agent in 5 minutes.
By the end, you'll understand the builder pattern, the expression operators,
and when to use each.

## Install

```bash
pip install adk-fluent
```

Autocomplete works immediately -- the package ships with `.pyi` type stubs for every builder. Type `Agent("name").` and your IDE shows all available methods with type hints.

## IDE Setup

**VS Code** -- install the [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) extension (included in the Python extension pack). Autocomplete and type checking work out of the box.

**PyCharm** -- works automatically. The `.pyi` stubs are bundled in the package and PyCharm discovers them on install.

**Neovim (LSP)** -- use [pyright](https://github.com/microsoft/pyright) as your language server. Stubs are picked up automatically.

:::{tip} AI Coding Agents
adk-fluent ships pre-configured rules for Claude Code, Cursor, Copilot, Windsurf, Cline, and Zed. See [Editor & AI Agent Setup](editor-setup/index.md) for details.
:::

## Discover the API

The builder pattern catches mistakes **at definition time**, not runtime:

```python
from adk_fluent import Agent

agent = Agent("demo")
agent.  # <- autocomplete shows: .model(), .instruct(), .tool(), .build(), ...

# Typos are caught immediately:
agent.instuction("oops")  # -> AttributeError: 'instuction' is not a recognized field.
                          #    Did you mean: 'instruction'?

# Inspect any builder's current state:
print(agent.model("gemini-2.5-flash").instruct("Help.").explain())
# Agent: demo
#   Config fields: model, instruction

# See everything available:
print(dir(agent))  # All methods including forwarded ADK fields
```

:::{admonition} Why this matters
:class: important
In native ADK, `LlmAgent(instuction="...")` silently ignores the misspelled keyword. The agent runs with no instruction and you debug for an hour wondering why it produces garbage. adk-fluent raises immediately.
:::

## Your First Agent

```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.").build()
```

That's it. `agent` is a real `google.adk.agents.llm_agent.LlmAgent` -- use it with `adk web`, `adk run`, or pass it to any ADK API.

## Your First Pipeline

Chain agents sequentially with `.step()` or the `>>` operator:

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

Both produce an identical `SequentialAgent`. The builder style shines when each step needs callbacks, tools, and context engineering. The operator style excels at composing reusable sub-expressions.

## Parallel Execution

Run agents concurrently with `.branch()` or the `|` operator:

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

## Loops

Iterate until a condition is met:

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

## Two Styles, Same Result

Every workflow can be expressed two ways. Both produce identical ADK objects:

::::{tab-set}
:::{tab-item} Builder Style
```python
pipeline = (
    Pipeline("research")
    .step(Agent("web", "gemini-2.5-flash").instruct("Search web.").writes("web_data"))
    .step(Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}."))
    .build()
)
```
:::
:::{tab-item} Operator Style
```python
pipeline = (
    Agent("web", "gemini-2.5-flash").instruct("Search web.").writes("web_data")
    >> Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}.")
).build()
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
67 recipes from simple agents to hero workflows like deep research and customer support triage.
```

```{grid-item-card} API Reference
:link: generated/api/index
:link-type: doc
Complete reference for all 132 builders with type signatures, ADK mappings, and examples.
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
