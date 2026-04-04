# Callbacks

adk-fluent provides a fluent API for attaching callbacks to agents. All callback methods are **additive** -- multiple calls accumulate handlers, never replace.

:::{tip}
**Visual learner?** Open the [Module Lifecycle Interactive Reference](../module-lifecycle-reference.html){target="_blank"} for a swim-lane timeline showing exactly when each callback fires during agent execution.
:::

## Callback Methods

| Method                | Alias for                 | Description                                                           |
| --------------------- | ------------------------- | --------------------------------------------------------------------- |
| `.before_model(fn)`   | `before_model_callback`   | Runs before each LLM call. Receives `(callback_context, llm_request)` |
| `.after_model(fn)`    | `after_model_callback`    | Runs after each LLM call. Receives `(callback_context, llm_response)` |
| `.before_agent(fn)`   | `before_agent_callback`   | Runs before agent execution                                           |
| `.after_agent(fn)`    | `after_agent_callback`    | Runs after agent execution                                            |
| `.before_tool(fn)`    | `before_tool_callback`    | Runs before each tool call                                            |
| `.after_tool(fn)`     | `after_tool_callback`     | Runs after each tool call                                             |
| `.on_model_error(fn)` | `on_model_error_callback` | Handles LLM errors                                                    |
| `.on_tool_error(fn)`  | `on_tool_error_callback`  | Handles tool errors                                                   |

## Additive Semantics

Each call appends to the list of handlers for that callback type. This is different from native ADK where setting a callback replaces the previous one:

```python
from adk_fluent import Agent

def log_fn(ctx, req):
    print(f"Request: {req}")

def metrics_fn(ctx, req):
    print(f"Metrics: {req}")

# Both handlers run before every LLM call
agent = (
    Agent("service", "gemini-2.5-flash")
    .instruct("Handle requests.")
    .before_model(log_fn)
    .before_model(metrics_fn)
    .build()
)
```

## Conditional Callbacks

Conditional variants append only when the condition is true:

```python
debug_mode = True
audit_enabled = False

agent = (
    Agent("service", "gemini-2.5-flash")
    .instruct("Handle requests.")
    .before_model_if(debug_mode, log_fn)      # Added (debug_mode is True)
    .after_model_if(audit_enabled, audit_fn)   # Skipped (audit_enabled is False)
    .build()
)
```

This is useful for toggling callbacks based on environment variables or feature flags without cluttering your code with if-else blocks.

## Guards

`.guard(fn)` is a shorthand that registers the function as both `before_model` and `after_model`:

```python
def safety_check(ctx, data):
    # Runs both before and after model calls
    if "dangerous" in str(data):
        raise ValueError("Safety violation detected")

agent = (
    Agent("service", "gemini-2.5-flash")
    .instruct("Handle requests.")
    .guard(safety_check)
    .build()
)
```

## Middleware Stacks with `.apply()`

For agents that need multiple layers of callbacks, use Presets to bundle them into reusable middleware stacks:

```python
from adk_fluent.presets import Preset

# Define reusable middleware
logging_preset = Preset(before_model=log_fn, after_model=log_response_fn)
security_preset = Preset(before_model=safety_check, after_model=audit_fn)

# Apply multiple presets
agent = (
    Agent("service", "gemini-2.5-flash")
    .instruct("Handle requests.")
    .use(logging_preset)
    .use(security_preset)
    .build()
)
```

See [Presets](presets.md) for more on reusable configuration bundles.

## Error Handling

Error callbacks handle failures in LLM calls and tool executions:

```python
def handle_model_error(ctx, error):
    print(f"Model error: {error}")
    # Optionally return a fallback response

def handle_tool_error(ctx, error):
    print(f"Tool error: {error}")
    # Optionally return a fallback result

agent = (
    Agent("service", "gemini-2.5-flash")
    .instruct("Handle requests.")
    .on_model_error(handle_model_error)
    .on_tool_error(handle_tool_error)
    .build()
)
```

## Complete Example

```python
from adk_fluent import Agent

def log_request(ctx, req):
    print(f"[LOG] Model request at {ctx.agent_name}")

def log_response(ctx, resp):
    print(f"[LOG] Model response at {ctx.agent_name}")

def validate_output(ctx, resp):
    if not resp:
        raise ValueError("Empty response")

def audit_tool(ctx, result):
    print(f"[AUDIT] Tool result: {result}")

agent = (
    Agent("production_agent", "gemini-2.5-flash")
    .instruct("You are a production service.")
    .before_model(log_request)
    .after_model(log_response)
    .after_model(validate_output)
    .before_tool(lambda ctx, tool: print(f"Calling tool: {tool}"))
    .after_tool(audit_tool)
    .on_model_error(lambda ctx, e: print(f"Error: {e}"))
    .build()
)
```

## Callbacks vs. Middleware

Callbacks are **per-agent** -- they apply only to the agent they're attached to. For cross-cutting concerns that should apply to the entire execution (all agents in a pipeline), use **middleware** instead.

| Aspect       | Callbacks           | Middleware                      |
| ------------ | ------------------- | ------------------------------- |
| Scope        | Single agent        | Entire execution                |
| Attachment   | `.before_model(fn)` | `.middleware(mw)`               |
| Multiplicity | Multiple per agent  | Stack of middleware on pipeline |
| Compilation  | Stored on IR node   | Stored in ExecutionConfig       |

```python
# Per-agent callback: only affects this agent
agent = Agent("a").before_model(log_fn)

# App-global middleware: affects all agents in the pipeline
from adk_fluent import RetryMiddleware
pipeline = (Agent("a") >> Agent("b")).middleware(RetryMiddleware())
```

See [Middleware](middleware.md) for the full middleware guide.

## Interplay with Other Modules

### Callbacks + Guards

`.guard(fn)` registers a function as both `before_model` and `after_model`. The G module provides structured guards that compile to callbacks automatically. Prefer G for safety/validation, raw callbacks for custom logic:

```python
from adk_fluent import Agent, G

# G module: declarative, composable, phase-aware
agent = Agent("safe").guard(G.pii("redact") | G.length(max=500))

# Raw callback: custom logic that doesn't fit G
agent = Agent("custom").before_model(my_custom_check)
```

See [Guards](guards.md).

### Callbacks + Presets

Bundle callbacks into reusable Presets to avoid repetition across agents:

```python
from adk_fluent.presets import Preset

observability = Preset(before_model=log_fn, after_model=metrics_fn)
agent_a = Agent("a").use(observability)
agent_b = Agent("b").use(observability)
```

See [Presets](presets.md).

### Callbacks + Context Engineering

Callbacks run *after* context engineering. The LLM request that `before_model` receives already has context filtering applied:

```python
from adk_fluent import Agent, C

agent = (
    Agent("classifier")
    .context(C.none())            # Context filtered first
    .before_model(log_request)    # Sees the filtered request
)
```

See [Context Engineering](context-engineering.md).

### Callbacks + Testing

Test that callbacks are attached correctly by inspecting the IR:

```python
ir = agent.to_ir()
assert ir.before_model_callbacks  # Callbacks preserved in IR
```

See [Testing](testing.md).

## Best Practices

1. **Use callbacks for agent-specific behavior.** Logging one agent's requests? Callback. Logging all agents? Middleware
2. **Use additive semantics intentionally.** Multiple `.before_model()` calls accumulate. If you want to replace, build a new agent
3. **Use `.guard()` for safety, not `.before_model()`.** Guards are semantically clearer and compose with the G module
4. **Use Presets for shared callbacks.** Don't repeat the same `.before_model().after_model()` chain on 10 agents
5. **Keep callbacks pure.** Side effects (DB writes, API calls) in callbacks make testing hard. Log, validate, or transform -- don't orchestrate

:::{seealso}
- [Middleware](middleware.md) -- pipeline-wide cross-cutting concerns
- [Presets](presets.md) -- reusable callback bundles
- [Guards](guards.md) -- structured safety with the G module
- [Testing](testing.md) -- verifying callbacks are attached correctly
- [Best Practices](best-practices.md) -- the "Callbacks vs. Middleware" decision tree
:::
