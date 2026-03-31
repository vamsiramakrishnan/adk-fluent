# Error Reference

:::{admonition} At a Glance
:class: tip

- Complete catalog of adk-fluent errors with causes, examples, and fixes
- Every error includes a code, message, and suggested resolution
- Use `.validate()` and `check_contracts()` to catch errors early at build time
:::

This page documents every error you may encounter when using adk-fluent,
explains why it happens, and shows how to fix it.

## BuilderError

**Raised by:** `.build()`, `to_app()`, composition operators (`>>`, `|`, `*`, `@`, `//`)

`BuilderError` is the primary exception. It wraps raw pydantic validation
errors into a structured, readable format.

```
BuilderError: Failed to build Agent('my_agent'):
  - model: Field required
  - instruction: Field required
```

**Attributes:**

| Attribute      | Type        | Description                                       |
| -------------- | ----------- | ------------------------------------------------- |
| `builder_name` | `str`       | Name passed to the builder constructor            |
| `builder_type` | `str`       | Builder class name (e.g. `"Agent"`, `"Pipeline"`) |
| `field_errors` | `list[str]` | One message per invalid field                     |
| `original`     | `Exception` | The underlying pydantic `ValidationError`         |

### Common causes

#### Missing required fields

```python
# Bad — model is required for LlmAgent
agent = Agent("helper").instruct("Be helpful.").build()

# Fix — add .model()
agent = Agent("helper").model("gemini-2.5-flash").instruct("Be helpful.").build()
```

#### Invalid field type

```python
# Bad — model expects a string, not an int
agent = Agent("helper").model(42).build()

# Fix
agent = Agent("helper").model("gemini-2.5-flash").build()
```

#### Invalid output schema

```python
# Bad — output_schema must be a Pydantic BaseModel subclass
agent = Agent("helper").model("gemini-2.5-flash").returns(dict).build()

# Fix
from pydantic import BaseModel

class Result(BaseModel):
    answer: str

agent = Agent("helper").model("gemini-2.5-flash").returns(Result).build()
```

______________________________________________________________________

## AttributeError — Unknown field

**Raised by:** Any chained method call on a builder

When you call a method that doesn't correspond to a known ADK field, alias,
or callback, adk-fluent raises `AttributeError` with the list of available
names.

```
AttributeError: 'modle' is not a recognized field on LlmAgent.
Available: after_agent, after_model, before_agent, before_model,
description, instruction, model, name, ...
```

### Common causes

#### Typo in method name

```python
# Bad
Agent("x").modle("gemini-2.5-flash")

# Fix
Agent("x").model("gemini-2.5-flash")
```

#### Using a deprecated method name

```python
# Deprecated — emits DeprecationWarning but still works
Agent("x").outputs("result")

# Preferred
Agent("x").writes("result")
```

#### Method doesn't exist on this builder type

```python
# Bad — Pipeline doesn't have .model()
Pipeline("p").model("gemini-2.5-flash")

# Fix — set model on the child agents, not the pipeline
agent = Agent("a").model("gemini-2.5-flash")
pipeline = Pipeline("p").step(agent)
```

______________________________________________________________________

## ValueError — Validation failed

**Raised by:** `.validate()`

The `.validate()` method calls `.build()` internally and wraps any exception
into a `ValueError`. Use this when you want a quick config check without
keeping the built object.

```
ValueError: Validation failed for Agent('my_agent'): Failed to build Agent('my_agent'):
  - model: Field required
```

### Using validate for early feedback

```python
agent = (
    Agent("helper")
    .model("gemini-2.5-flash")
    .instruct("You are helpful.")
    .validate()  # raises ValueError if config is invalid, returns self if OK
    .build()
)
```

______________________________________________________________________

## TypeError — Invalid contract schema

**Raised by:** `.produces()`, `.consumes()`

Data contract methods require Pydantic `BaseModel` subclasses.

```
TypeError: produces() requires a Pydantic BaseModel subclass, got <class 'dict'>
```

### Fix

```python
from pydantic import BaseModel

class ClaimData(BaseModel):
    claim_id: str
    amount: float

agent = Agent("intake").model("gemini-2.5-flash").produces(ClaimData)
```

______________________________________________________________________

## ValueError — Missing output_key for dict routing

**Raised by:** `>>` operator with a dict on the right side

When using `agent >> {"key": handler}` shorthand, the left-side agent must
have `.writes()` set so the router knows which state key to examine.

```
ValueError: Left side of >> dict must have .writes() set
so the router knows which state key to check.
```

### Fix

```python
classifier = (
    Agent("classifier")
    .model("gemini-2.5-flash")
    .instruct("Classify as: billing, technical, general")
    .writes("category")  # router reads this key
)

pipeline = classifier >> {
    "billing": billing_agent,
    "technical": tech_agent,
    "general": general_agent,
}
```

______________________________________________________________________

## ValueError — Contract errors in pipeline

**Raised by:** `.build()` in strict contract-checking mode

When `_check_mode="strict"` and the contract checker finds data flow
mismatches between agents.

```
ValueError: Contract errors in pipeline:
  agent_b: Expected input schema ClaimData but upstream agent_a produces ReviewResult
```

### Fix

Ensure that each agent's `.produces()` schema matches the next agent's
`.consumes()` schema in the pipeline.

```python
pipeline = (
    intake.produces(ClaimData)
    >> reviewer.consumes(ClaimData).produces(ReviewResult)
    >> summarizer.consumes(ReviewResult)
)
```

______________________________________________________________________

## NotImplementedError — Missing to_ir()

**Raised by:** `.to_ir()` on builders that don't support IR compilation

Some builder types (custom or third-party) may not implement IR conversion.

```
NotImplementedError: MyCustomBuilder.to_ir() is not implemented.
Use .build() for direct ADK object construction.
```

### Fix

Use `.build()` instead of `.to_ir()` or `.to_app()` for builders that
don't support the IR pipeline.

______________________________________________________________________

## Debugging tips

### Use .explain() to inspect builder state

```python
agent = Agent("helper").model("gemini-2.5-flash").instruct("Be helpful.")
agent.explain()
# Agent: helper
#   Config fields: model, instruction
```

With `rich` installed (`pip install adk-fluent[rich]`), `.explain()` renders
a colored box-drawing tree. Use `.inspect()` for full config values.

### Use .validate() before .build()

Chain `.validate()` during development to catch errors early:

```python
agent = Agent("x").model("gemini-2.5-flash").validate()
```

### Use the CLI visualizer

```bash
adk-fluent visualize my_module.py
```

Renders a Mermaid diagram of your agent graph, helping you spot structural
issues like missing connections or unexpected nesting.
