# Getting Started

## Install

```bash
pip install adk-fluent
```

Autocomplete works immediately -- the package ships with `.pyi` type stubs for every builder. Type `Agent("name").` and your IDE shows all available methods with type hints.

## IDE Setup

**VS Code** -- install the [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) extension (included in the Python extension pack). Autocomplete and type checking work out of the box.

**PyCharm** -- works automatically. The `.pyi` stubs are bundled in the package and PyCharm discovers them on install.

**Neovim (LSP)** -- use [pyright](https://github.com/microsoft/pyright) as your language server. Stubs are picked up automatically.

## Discover the API

```python
from adk_fluent import Agent

agent = Agent("demo")
agent.  # <- autocomplete shows: .model(), .instruct(), .tool(), .build(), ...

# Typos are caught at definition time, not runtime:
agent.instuction("oops")  # -> AttributeError: 'instuction' is not a recognized field.
                          #    Did you mean: 'instruction'?

# Inspect any builder's current state:
print(agent.model("gemini-2.5-flash").instruct("Help.").explain())
# Agent: demo
#   Config fields: model, instruction

# See everything available:
print(dir(agent))  # All methods including forwarded ADK fields
```

## Quick Start

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop

# Simple agent — model as optional second arg or via .model()
agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.").build()

# Pipeline — build with .step() or >> operator
pipeline = (
    Pipeline("research")
    .step(Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
    .build()
)

# Fan-out — build with .branch() or | operator
fanout = (
    FanOut("parallel_research")
    .branch(Agent("web", "gemini-2.5-flash").instruct("Search the web."))
    .branch(Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
    .build()
)

# Loop — build with .step() + .max_iterations() or * operator
loop = (
    Loop("refine")
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write draft."))
    .step(Agent("critic", "gemini-2.5-flash").instruct("Critique."))
    .max_iterations(3)
    .build()
)
```

Every `.build()` returns a real ADK object (`LlmAgent`, `SequentialAgent`, etc.). Fully compatible with `adk web`, `adk run`, and `adk deploy`.

## Two Styles, Same Result

Every workflow can be expressed two ways -- the explicit builder API or the expression operators. Both produce identical ADK objects:

````{tab-set}

```{tab-item} Builder Style
```python
pipeline = (
    Pipeline("research")
    .step(Agent("web", "gemini-2.5-flash").instruct("Search web.").outputs("web_data"))
    .step(Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}."))
    .build()
)
```
```

```{tab-item} Operator Style
```python
pipeline = (
    Agent("web", "gemini-2.5-flash").instruct("Search web.").outputs("web_data")
    >> Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}.")
).build()
```
```

````

The builder style shines for complex multi-step workflows where each step is configured with callbacks, tools, and context. The operator style excels at composing reusable sub-expressions:

```python
# Complex builder-style pipeline with tools and callbacks
pipeline = (
    Pipeline("customer_support")
    .step(
        Agent("classifier", "gemini-2.5-flash")
        .instruct("Classify the customer's intent.")
        .outputs("intent")
        .before_model(log_fn)
    )
    .step(
        Agent("resolver", "gemini-2.5-flash")
        .instruct("Resolve the {intent} issue.")
        .tool(lookup_customer)
        .tool(create_ticket)
        .history("none")
    )
    .step(
        Agent("responder", "gemini-2.5-flash")
        .instruct("Draft a response to the customer.")
        .after_model(audit_fn)
    )
    .build()
)

# Same complexity, composed from reusable parts with operators
classify = Agent("classifier", "gemini-2.5-flash").instruct("Classify intent.").outputs("intent")
resolve = Agent("resolver", "gemini-2.5-flash").instruct("Resolve {intent}.").tool(lookup_customer)
respond = Agent("responder", "gemini-2.5-flash").instruct("Draft response.")

support_pipeline = classify >> resolve >> respond
# Reuse sub-expressions in different pipelines
escalation_pipeline = classify >> Agent("escalate", "gemini-2.5-flash").instruct("Escalate.")
```

## What's Next

- **[User Guide](user-guide/index.md)** -- deep dive into builders, operators, prompts, callbacks, and more
- **[API Reference](generated/api/index.md)** -- complete method reference for all 130+ builders
- **[Cookbook](generated/cookbook/index.md)** -- 34 annotated examples with side-by-side Native ADK vs Fluent comparisons
- **[Migration Guide](generated/migration/from-native-adk.md)** -- migrate existing ADK code to adk-fluent
