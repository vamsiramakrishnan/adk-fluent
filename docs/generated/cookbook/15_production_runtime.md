# Production Runtime Setup

*How to configure agents for production runtime with middleware, resumability, and event compaction.*

_Source: `15_production_runtime.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.apps.app import App, ResumabilityConfig

agent = LlmAgent(
    name="prod",
    model="gemini-2.5-flash",
    instruction="Production agent.",
)
app = App(
    name="prod_app",
    root_agent=agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, ExecutionConfig, CompactionConfig

# to_app() compiles through IR to a native ADK App
app = (
    Agent("prod")
    .model("gemini-2.5-flash")
    .instruct("Production agent.")
    .to_app(config=ExecutionConfig(
        app_name="prod_app",
        resumable=True,
        compaction=CompactionConfig(interval=10, overlap=2),
    ))
)
```
:::
::::

## Equivalence

```python
assert app.name == "prod_app"
assert app.root_agent.name == "prod"
```

## Adding Middleware

Middleware provides app-global cross-cutting behavior:

```python
from adk_fluent import Agent, RetryMiddleware, StructuredLogMiddleware

pipeline = (
    Agent("classifier") >> Agent("resolver")
).middleware(RetryMiddleware(max_retries=3))
 .middleware(StructuredLogMiddleware())

app = pipeline.to_app()
```

```python
from adk_fluent import RetryMiddleware, StructuredLogMiddleware
assert RetryMiddleware is not None
assert StructuredLogMiddleware is not None
```

:::{seealso}
User guide: [IR and Backends](../user-guide/ir-and-backends.md), [Middleware](../user-guide/middleware.md)
:::
