# Middleware

*How to add app-global cross-cutting behavior with middleware.*

_Source: n/a (v4 feature)_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.apps.app import App

# Native ADK requires implementing BasePlugin with 13 callbacks
class RetryPlugin(BasePlugin):
    async def before_model_callback(self, callback_context, llm_request):
        pass  # 50+ lines of retry logic
    # ... many more callbacks

agent = LlmAgent(name="a", model="gemini-2.5-flash", instruction="Help.")
app = App(name="app", root_agent=agent, plugins=[RetryPlugin(name="retry")])
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, RetryMiddleware, StructuredLogMiddleware

# Built-in middleware with simple configuration
app = (
    Agent("a").instruct("Help.")
    .middleware(RetryMiddleware(max_retries=3))
    .middleware(StructuredLogMiddleware())
    .to_app()
)
```
:::
::::

## Equivalence

```python
from adk_fluent import RetryMiddleware, StructuredLogMiddleware, Middleware
assert RetryMiddleware is not None
assert StructuredLogMiddleware is not None

# Middleware is available on any builder
from adk_fluent import Agent
a = Agent("a")
assert hasattr(a, "middleware")
```

## Middleware Propagation

Middleware propagates through operators:

```python
from adk_fluent import Agent, RetryMiddleware

# Middleware on either operand propagates to the result
a = Agent("a").middleware(RetryMiddleware())
b = Agent("b")
pipeline = a >> b

# pipeline has the middleware from a
assert hasattr(pipeline, "_middlewares")
assert len(pipeline._middlewares) == 1
```

:::{seealso}
User guide: [Middleware](../user-guide/middleware.md)
:::
