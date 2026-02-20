# Middleware

Middleware provides app-global cross-cutting behavior. Unlike [callbacks](callbacks.md) which are per-agent, middleware applies to the entire execution across all agents.

## Attaching Middleware

Use `.middleware()` on any builder, then `.to_app()` to compile:

```python
from adk_fluent import Agent, RetryMiddleware, StructuredLogMiddleware

pipeline = (
    Agent("a") >> Agent("b")
).middleware(RetryMiddleware(max_retries=3))
 .middleware(StructuredLogMiddleware())

app = pipeline.to_app()
```

Multiple `.middleware()` calls accumulate. When combined with `>>` or `|`, middleware from all operands is merged.

## Middleware Protocol

A middleware is any object with optional async lifecycle methods:

```python
class Middleware(Protocol):
    # Runner lifecycle
    async def before_run(self, *, runner, session, **kw): ...
    async def after_run(self, *, runner, session, **kw): ...

    # Agent lifecycle
    async def before_agent(self, *, agent, context, **kw): ...
    async def after_agent(self, *, agent, context, **kw): ...

    # Model lifecycle
    async def before_model(self, *, agent, request, context, **kw): ...
    async def after_model(self, *, agent, response, context, **kw): ...
    async def on_model_error(self, *, agent, error, context, **kw): ...

    # Tool lifecycle
    async def before_tool(self, *, agent, tool, args, context, **kw): ...
    async def after_tool(self, *, agent, tool, result, context, **kw): ...
    async def on_tool_error(self, *, agent, tool, error, context, **kw): ...

    # Cleanup
    async def close(self): ...
```

All methods are optional. Implement only what you need.

## Built-in Middleware

### RetryMiddleware

Retries on model or tool errors with exponential backoff:

```python
from adk_fluent import RetryMiddleware

retry = RetryMiddleware(
    max_retries=3,       # Maximum retry attempts (default: 3)
    base_delay=1.0,      # Initial delay in seconds (default: 1.0)
    backoff_factor=2.0,  # Multiplier per retry (default: 2.0)
)
```

### StructuredLogMiddleware

Captures all lifecycle events as structured log entries:

```python
from adk_fluent import StructuredLogMiddleware

logger = StructuredLogMiddleware()
app = pipeline.middleware(logger).to_app()
# After execution: logger.events contains all captured events
```

## Writing Custom Middleware

Implement any subset of the lifecycle methods:

```python
from adk_fluent import Middleware

class TimingMiddleware:
    """Track execution time for each agent."""

    def __init__(self):
        self.timings = {}

    async def before_agent(self, *, agent, context, **kw):
        import time
        context.state["_start"] = time.time()

    async def after_agent(self, *, agent, context, **kw):
        import time
        elapsed = time.time() - context.state.get("_start", time.time())
        self.timings[agent.name] = elapsed
```

## How Middleware Works

When `.to_app()` is called:

1. Builder middleware (from `.middleware()`) is merged with `ExecutionConfig.middlewares`
1. The middleware stack is compiled into a single `_MiddlewarePlugin` (an ADK `BasePlugin`)
1. The plugin is attached to the `App` via `plugins=[plugin]`

The stack executes in order. For non-void hooks (before_model, before_tool), the first middleware to return a non-None value short-circuits the rest.
