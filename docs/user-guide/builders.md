# Builders

Every adk-fluent builder does one thing: it turns a chain of readable method calls into a native ADK object. No subclassing. No boilerplate. No silent misconfiguration.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("A general-purpose helper")
    .writes("response")
    .tool(search_fn)
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const agent = new Agent("helper", "gemini-2.5-flash")
  .instruct("You are a helpful assistant.")
  .describe("A general-purpose helper")
  .writes("response")
  .tool(searchFn)
  .build();
```
:::
:::{tab-item} Native ADK (Python, 22 lines)
```python
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

agent = LlmAgent(
    name="helper",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    description="A general-purpose helper",
    output_key="response",
    tools=[FunctionTool(search_fn)],
)
```
:::
::::

Both produce the **exact same `LlmAgent`**. The difference: the builder catches typos at definition time, provides IDE autocomplete for every field, and chains naturally.

## Constructor Arguments

Every builder takes a required `name` as the first positional argument. Some builders accept additional optional positional arguments. For example, the `Agent` builder accepts an optional `model` as a second positional argument:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

# These are equivalent:
agent = Agent("helper", "gemini-2.5-flash")
agent = Agent("helper").model("gemini-2.5-flash")
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

// These are equivalent:
const a = new Agent("helper", "gemini-2.5-flash");
const b = new Agent("helper").model("gemini-2.5-flash");
```
:::
::::

## Method Chaining (Fluent API)

Every configuration method returns the builder, enabling fluent chaining. Methods can be called in any order:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("A general-purpose helper agent")
    .writes("response")
    .tool(search_fn)
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const agent = new Agent("helper", "gemini-2.5-flash")
  .instruct("You are a helpful assistant.")
  .describe("A general-purpose helper agent")
  .writes("response")
  .tool(searchFn)
  .build();
```
:::
::::

## `.build()` -- Terminal Method

`.build()` resolves the builder into a native ADK object:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop

agent = Agent("x", "gemini-2.5-flash").instruct("Help.").build()       # -> LlmAgent
pipe  = Pipeline("p").step(agent).build()                               # -> SequentialAgent
fan   = FanOut("f").branch(agent).build()                               # -> ParallelAgent
loop  = Loop("l").step(agent).max_iterations(3).build()                 # -> LoopAgent
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, Pipeline, FanOut, Loop } from "adk-fluent-ts";

const agent = new Agent("x", "gemini-2.5-flash").instruct("Help.").build(); // -> LlmAgent
const pipe = new Pipeline("p").step(agent).build();                          // -> SequentialAgent
const fan = new FanOut("f").branch(agent).build();                           // -> ParallelAgent
const loop = new Loop("l").step(agent).maxIterations(3).build();             // -> LoopAgent
```
:::
::::

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

## IR Compilation

Every builder can produce an Intermediate Representation (IR) -- a frozen dataclass tree that decouples the builder from ADK:

```python
from adk_fluent import Agent

# Inspect the IR tree
ir = Agent("helper").model("gemini-2.5-flash").instruct("Help.").to_ir()
print(ir)  # AgentNode(name='helper', model='gemini-2.5-flash', ...)
```

### `.to_ir()`

Returns a frozen dataclass IR node. Agent builders return `AgentNode`, pipelines return `SequenceNode`, etc.:

| Builder    | IR Node        |
| ---------- | -------------- |
| `Agent`    | `AgentNode`    |
| `Pipeline` | `SequenceNode` |
| `FanOut`   | `ParallelNode` |
| `Loop`     | `LoopNode`     |

### `.to_app(config=None)`

Compiles through IR → ADKBackend → native ADK `App`. An alternative to `.build()` that goes through the full compilation pipeline:

```python
from adk_fluent import Agent, ExecutionConfig

app = Agent("helper").instruct("Help.").to_app(
    config=ExecutionConfig(app_name="my_app", resumable=True)
)
```

### `.to_mermaid()`

Generates a Mermaid graph diagram from the builder's IR tree:

```python
pipeline = Agent("a") >> Agent("b") >> Agent("c")
print(pipeline.to_mermaid())
# graph TD
#     n1[["a_then_b_then_c (sequence)"]]
#     n2["a"]
#     n3["b"]
#     n4["c"]
#     n2 --> n3
#     n3 --> n4
```

## Data Contracts

`.produces()` and `.consumes()` declare the Pydantic schemas an agent writes to and reads from state:

```python
from pydantic import BaseModel
from adk_fluent import Agent

class Intent(BaseModel):
    category: str
    confidence: float

classifier = Agent("classifier").produces(Intent)
resolver = Agent("resolver").consumes(Intent)

pipeline = classifier >> resolver
```

The contract annotations are stored on the IR nodes and can be verified with `check_contracts()`. See [Testing](testing.md) for details.

## Dependency Injection

`.inject()` registers resources that are injected into tool functions at call time. Injected parameters are hidden from the LLM schema:

```python
from adk_fluent import Agent

agent = (
    Agent("lookup")
    .tool(search_db)  # search_db(query: str, db: Database) -> str
    .inject(db=my_database)
)
# LLM sees: search_db(query: str) -> str
# At call time: db=my_database is injected automatically
```

## Middleware

`.middleware()` attaches app-global middleware. Unlike callbacks (which are per-agent), middleware applies to the entire execution:

```python
from adk_fluent import Agent, RetryMiddleware

pipeline = (
    Agent("a") >> Agent("b")
).middleware(RetryMiddleware(max_iterations=3))

app = pipeline.to_app()  # Middleware compiled into App plugins
```

See [Middleware](middleware.md) for the full middleware guide.

## Escape Hatches

When the fluent API doesn't expose an ADK feature you need, two escape hatches let you reach the underlying objects directly.

### `.with_raw_config(**kwargs)` -- Declarative

Sets arbitrary attributes on the built ADK object. This is the recommended approach for simple field overrides:

```python
agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are helpful.")
    .with_raw_config(
        disallow_transfer_to_parent=True,
        include_contents="none",
    )
    .build()
)
```

If a field name doesn't exist on the ADK object, a warning is raised at build time with suggestions -- the same typo protection as the rest of the builder API.

### `.native(fn)` -- Programmatic

Registers a post-build hook that receives the raw ADK object for direct manipulation:

```python
def customize(adk_agent):
    if len(adk_agent.sub_agents) > 3:
        adk_agent.disallow_transfer_to_peers = True

agent = (
    Agent("router", "gemini-2.5-flash")
    .instruct("Route requests.")
    .sub_agent(a).sub_agent(b).sub_agent(c).sub_agent(d)
    .native(customize)
    .build()
)
```

Multiple `.native()` calls chain in order. Each hook receives the same object after the previous hook has run.

### When to use which

| Approach | Best for |
| --- | --- |
| `.with_raw_config()` | Setting one or more known fields to fixed values |
| `.native(fn)` | Conditional logic, complex mutations, or inspecting the built object |

## Workflow Builders

All workflow builders (Pipeline, FanOut, Loop) accept both built ADK agents and fluent builders as arguments. Builders are auto-built at `.build()` time.

### Pipeline (Sequential)

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Pipeline, Agent, C

pipeline = (
    Pipeline("data_processing")
    .step(Agent("extractor", "gemini-2.5-flash").instruct("Extract entities.").writes("entities"))
    .step(Agent("enricher", "gemini-2.5-flash").instruct("Enrich {entities}.").tool(lookup_db))
    .step(Agent("formatter", "gemini-2.5-flash").instruct("Format output.").context(C.none()))
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Pipeline, Agent, C } from "adk-fluent-ts";

const pipeline = new Pipeline("data_processing")
  .step(
    new Agent("extractor", "gemini-2.5-flash")
      .instruct("Extract entities.")
      .writes("entities"),
  )
  .step(
    new Agent("enricher", "gemini-2.5-flash")
      .instruct("Enrich {entities}.")
      .tool(lookupDb),
  )
  .step(
    new Agent("formatter", "gemini-2.5-flash")
      .instruct("Format output.")
      .context(C.none()),
  )
  .build();
```
:::
::::

| Method         | Description                                                        |
| -------------- | ------------------------------------------------------------------ |
| `.step(agent)` | Append an agent as the next step. Lazy -- built at `.build()` time |
| `.build()`     | Resolve into a native ADK `SequentialAgent`                        |

### FanOut (Parallel)

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import FanOut, Agent

fanout = (
    FanOut("research")
    .branch(Agent("web", "gemini-2.5-flash").instruct("Search the web.").writes("web_results"))
    .branch(Agent("papers", "gemini-2.5-pro").instruct("Search academic papers.").writes("paper_results"))
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { FanOut, Agent } from "adk-fluent-ts";

const fanout = new FanOut("research")
  .branch(
    new Agent("web", "gemini-2.5-flash")
      .instruct("Search the web.")
      .writes("web_results"),
  )
  .branch(
    new Agent("papers", "gemini-2.5-pro")
      .instruct("Search academic papers.")
      .writes("paper_results"),
  )
  .build();
```
:::
::::

| Method           | Description                                                   |
| ---------------- | ------------------------------------------------------------- |
| `.branch(agent)` | Add a parallel branch agent. Lazy -- built at `.build()` time |
| `.build()`       | Resolve into a native ADK `ParallelAgent`                     |

### Loop

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Loop, Agent

loop = (
    Loop("quality_loop")
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write draft.").writes("quality"))
    .step(Agent("reviewer", "gemini-2.5-flash").instruct("Review and score."))
    .max_iterations(5)
    .until(lambda s: s.get("quality") == "good")
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Loop, Agent } from "adk-fluent-ts";

const loop = new Loop("quality_loop")
  .step(
    new Agent("writer", "gemini-2.5-flash").instruct("Write draft.").writes("quality"),
  )
  .step(new Agent("reviewer", "gemini-2.5-flash").instruct("Review and score."))
  .maxIterations(5)
  .until((s) => s.quality === "good")
  .build();
```
:::
::::

| Method               | Description                                            |
| -------------------- | ------------------------------------------------------ |
| `.step(agent)`       | Append a step agent. Lazy -- built at `.build()` time  |
| `.max_iterations(n)` | Set maximum loop iterations                            |
| `.until(pred)`       | Set exit predicate. Exits when `pred(state)` is truthy |
| `.build()`           | Resolve into a native ADK `LoopAgent`                  |

## Combining Builder and Operator Styles

The builder and operator styles mix freely. Use builders for complex individual steps and operators (Python `>>`/`|`/`*` or TypeScript `.then()`/`.parallel()`/`.times()`) for composition:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, Pipeline, FanOut, S, until, Prompt

# Define reusable agents with full builder configuration
researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct(Prompt().role("You are a research analyst.").task("Find relevant information."))
    .tool(search_tool)
    .before_model(log_fn)
    .writes("findings")
)

writer = (
    Agent("writer", "gemini-2.5-pro")
    .instruct("Write a report about {findings}.")
    .static("Company style guide: use formal tone, cite sources...")
    .writes("draft")
)

reviewer = (
    Agent("reviewer", "gemini-2.5-flash")
    .instruct("Score the draft 1-10 for quality.")
    .writes("quality_score")
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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, FanOut, S, P } from "adk-fluent-ts";

const researcher = new Agent("researcher", "gemini-2.5-flash")
  .instruct(
    P.role("You are a research analyst.").add(P.task("Find relevant information.")),
  )
  .tool(searchTool)
  .beforeModel(logFn)
  .writes("findings");

const writer = new Agent("writer", "gemini-2.5-pro")
  .instruct("Write a report about {findings}.")
  .static("Company style guide: use formal tone, cite sources...")
  .writes("draft");

const reviewer = new Agent("reviewer", "gemini-2.5-flash")
  .instruct("Score the draft 1-10 for quality.")
  .writes("quality_score");

const researchPhase = new FanOut("gather")
  .branch(researcher.clone("web").tool(webSearch))
  .branch(researcher.clone("papers").tool(paperSearch));

const pipeline = researchPhase
  .then(S.merge_(["web", "papers"], "findings"))
  .then(writer)
  .then(
    reviewer
      .then(writer)
      .timesUntil((s) => Number(s.quality_score ?? 0) >= 8, { max: 3 }),
  );
```
:::
::::
