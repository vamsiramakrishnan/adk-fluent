# Builders

The builder pattern is the foundation of adk-fluent. Every builder wraps a native ADK class and exposes a fluent, chainable API that resolves to a real ADK object at `.build()` time.

## Constructor Arguments

Every builder takes a required `name` as the first positional argument. Some builders accept additional optional positional arguments. For example, the `Agent` builder accepts an optional `model` as a second positional argument:

```python
from adk_fluent import Agent

# These are equivalent:
agent = Agent("helper", "gemini-2.5-flash")
agent = Agent("helper").model("gemini-2.5-flash")
```

## Method Chaining (Fluent API)

Every configuration method returns `self`, enabling fluent chaining:

```python
agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("A general-purpose helper agent")
    .outputs("response")
    .tool(search_fn)
    .build()
)
```

Methods can be called in any order. Each call records a configuration value that is applied when `.build()` is invoked.

## `.build()` -- Terminal Method

`.build()` resolves the builder into a native ADK object:

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop

agent = Agent("x", "gemini-2.5-flash").instruct("Help.").build()       # -> LlmAgent
pipe  = Pipeline("p").step(agent).build()                               # -> SequentialAgent
fan   = FanOut("f").branch(agent).build()                               # -> ParallelAgent
loop  = Loop("l").step(agent).max_iterations(3).build()                 # -> LoopAgent
```

Sub-builders passed to workflow builders (Pipeline, FanOut, Loop) are automatically built at `.build()` time, so you do not need to call `.build()` on each step individually.

## `__getattr__` Forwarding

Any ADK field that does not have an explicit builder method can still be set through dynamic attribute forwarding:

```python
agent = Agent("x").generate_content_config(my_config)  # Works via forwarding
```

The builder inspects the underlying ADK class and forwards the value to the matching field. This means every ADK field is accessible, even if adk-fluent does not define a dedicated method for it.

## Typo Detection

Misspelled method names raise `AttributeError` with the closest match suggestion:

```python
agent = Agent("demo")
agent.instuction("oops")
# AttributeError: 'instuction' is not a recognized field.
#    Did you mean: 'instruction'?
```

Typos are caught at builder definition time, not at runtime, making it easy to spot mistakes early.

## `.explain()` -- Introspection

`.explain()` returns a multi-line summary of the builder's current state:

```python
print(Agent("demo").model("gemini-2.5-flash").instruct("Help.").explain())
# Agent: demo
#   Config fields: model, instruction
```

This is useful for debugging complex builders to verify what configuration has been applied.

## `.validate()` -- Early Error Detection

`.validate()` tries to call `.build()` internally and raises a `ValueError` with a clear message if the configuration is invalid. It returns `self` so it can be chained:

```python
agent = (
    Agent("demo")
    .model("gemini-2.5-flash")
    .instruct("Help.")
    .validate()  # Raises ValueError if config is broken
    .build()
)
```

## `.clone()` and `.with_()` -- Variants

### `.clone(new_name)`

Creates an independent deep copy of the builder with a new name:

```python
base = Agent("base").model("gemini-2.5-flash").instruct("Be helpful.")

math_agent = base.clone("math").instruct("Solve math.")
code_agent = base.clone("code").instruct("Write code.")
```

The cloned builders are fully independent; modifying one does not affect the other or the original.

### `.with_(**overrides)`

Creates an immutable variant. The original builder is not modified:

```python
base = Agent("base").model("gemini-2.5-flash").instruct("Be helpful.")

creative = base.with_(name="creative", model="gemini-2.5-pro")
# base is unchanged
```

## Serialization

Builders can be serialized to and from dictionaries and YAML:

```python
# Serialize
data = agent.to_dict()
yaml_str = agent.to_yaml()

# Reconstruct
agent = Agent.from_dict(data)
agent = Agent.from_yaml(yaml_str)
```

## Workflow Builders

All workflow builders (Pipeline, FanOut, Loop) accept both built ADK agents and fluent builders as arguments. Builders are auto-built at `.build()` time.

### Pipeline (Sequential)

```python
from adk_fluent import Pipeline, Agent

pipeline = (
    Pipeline("data_processing")
    .step(Agent("extractor", "gemini-2.5-flash").instruct("Extract entities.").outputs("entities"))
    .step(Agent("enricher", "gemini-2.5-flash").instruct("Enrich {entities}.").tool(lookup_db))
    .step(Agent("formatter", "gemini-2.5-flash").instruct("Format output.").history("none"))
    .build()
)
```

| Method | Description |
|--------|-------------|
| `.step(agent)` | Append an agent as the next step. Lazy -- built at `.build()` time |
| `.build()` | Resolve into a native ADK `SequentialAgent` |

### FanOut (Parallel)

```python
from adk_fluent import FanOut, Agent

fanout = (
    FanOut("research")
    .branch(Agent("web", "gemini-2.5-flash").instruct("Search the web.").outputs("web_results"))
    .branch(Agent("papers", "gemini-2.5-pro").instruct("Search academic papers.").outputs("paper_results"))
    .build()
)
```

| Method | Description |
|--------|-------------|
| `.branch(agent)` | Add a parallel branch agent. Lazy -- built at `.build()` time |
| `.build()` | Resolve into a native ADK `ParallelAgent` |

### Loop

```python
from adk_fluent import Loop, Agent

loop = (
    Loop("quality_loop")
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write draft.").outputs("quality"))
    .step(Agent("reviewer", "gemini-2.5-flash").instruct("Review and score."))
    .max_iterations(5)
    .until(lambda s: s.get("quality") == "good")
    .build()
)
```

| Method | Description |
|--------|-------------|
| `.step(agent)` | Append a step agent. Lazy -- built at `.build()` time |
| `.max_iterations(n)` | Set maximum loop iterations |
| `.until(pred)` | Set exit predicate. Exits when `pred(state)` is truthy |
| `.build()` | Resolve into a native ADK `LoopAgent` |

## Combining Builder and Operator Styles

The builder and operator styles mix freely. Use builders for complex individual steps and operators for composition:

```python
from adk_fluent import Agent, Pipeline, FanOut, S, until, Prompt

# Define reusable agents with full builder configuration
researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct(Prompt().role("You are a research analyst.").task("Find relevant information."))
    .tool(search_tool)
    .before_model(log_fn)
    .outputs("findings")
)

writer = (
    Agent("writer", "gemini-2.5-pro")
    .instruct("Write a report about {findings}.")
    .static("Company style guide: use formal tone, cite sources...")
    .outputs("draft")
)

reviewer = (
    Agent("reviewer", "gemini-2.5-flash")
    .instruct("Score the draft 1-10 for quality.")
    .outputs("quality_score")
)

# Compose with operators — each sub-expression is reusable
research_phase = (
    FanOut("gather")
    .branch(researcher.clone("web").tool(web_search))
    .branch(researcher.clone("papers").tool(paper_search))
)

pipeline = (
    research_phase
    >> S.merge("web", "papers", into="findings")
    >> writer
    >> (reviewer >> writer) * until(lambda s: int(s.get("quality_score", 0)) >= 8, max=3)
)
```
