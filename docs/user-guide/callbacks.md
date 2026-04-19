# Callbacks

adk-fluent provides a fluent API for attaching callbacks to agents. All callback methods are **additive** -- multiple calls accumulate handlers, never replace.

:::{tip}
**Visual learner?** Open the [Module Lifecycle Interactive Reference](../module-lifecycle-reference.html){target="_blank"} for a swim-lane timeline showing exactly when each callback fires during agent execution.
:::

## When each callback fires

A single agent turn runs through six ordered phases. Callbacks are hooks into those phases — the table shows exactly where each one lands.

```{mermaid}
sequenceDiagram
    autonumber
    participant U as user input
    participant A as agent turn
    participant L as LLM
    participant T as tool
    participant S as state

    U->>A: invocation
    A->>A: before_agent
    loop until model emits final answer
        A->>L: before_model
        L-->>A: response
        A->>A: after_model
        alt response contains tool call
            A->>T: before_tool
            T-->>A: result
            A->>A: after_tool
        end
    end
    A->>S: .writes() persists response
    A->>A: after_agent
    A-->>U: final response
```

| Phase | Callback | Receives | Typical use |
|---|---|---|---|
| ① agent entry | `before_agent(ctx)` | invocation context | Inject preamble, seed state, short-circuit with a cached answer |
| ② each LLM call | `before_model(ctx, req)` | outgoing `LlmRequest` | Modify the prompt, add tool hints, block unsafe requests |
| ③ each LLM reply | `after_model(ctx, resp)` | raw `LlmResponse` | Output validation, redaction, scoring — **this is where guards run** |
| ④ each tool call | `before_tool(ctx, tool, args)` | tool name + args | Argument rewriting, authz checks, dry-run mode |
| ⑤ each tool reply | `after_tool(ctx, tool, result)` | tool result | Log, cache, transform the return value |
| ⑥ agent exit | `after_agent(ctx)` | final state | Audit, post-processing of `state[writes_key]` |

Errors in ② or ④ divert to `on_model_error` / `on_tool_error` instead of continuing.

:::{note} Additive, not overriding
Every callback slot is a list. `.before_model(a).before_model(b)` runs **both** in registration order. This is different from native ADK, where setting a callback replaces the previous one.
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

::::{tab-set}
:::{tab-item} Python
:sync: python

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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const logFn = (ctx: unknown, req: unknown) => {
  console.log(`Request: ${JSON.stringify(req)}`);
};

const metricsFn = (ctx: unknown, req: unknown) => {
  console.log(`Metrics: ${JSON.stringify(req)}`);
};

// Both handlers run before every LLM call
const agent = new Agent("service", "gemini-2.5-flash")
  .instruct("Handle requests.")
  .beforeModel(logFn)
  .beforeModel(metricsFn)
  .build();
```
:::
::::

:::{note} TypeScript naming
TypeScript uses camelCase for all callback methods: `beforeModel`, `afterModel`, `beforeAgent`, `afterAgent`, `beforeTool`, `afterTool`, `onModelError`, `onToolError`. Semantics and additive behavior are identical to Python.
:::

## Conditional Callbacks

Conditional variants append only when the condition is true:

::::{tab-set}
:::{tab-item} Python
:sync: python

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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const debugMode = true;
const auditEnabled = false;

const agent = new Agent("service", "gemini-2.5-flash")
  .instruct("Handle requests.")
  .beforeModelIf(debugMode, logFn)        // Added (debugMode is true)
  .afterModelIf(auditEnabled, auditFn)    // Skipped (auditEnabled is false)
  .build();
```
:::
::::

This is useful for toggling callbacks based on environment variables or feature flags without cluttering your code with if-else blocks.

## Guards

`.guard(fn)` is a shorthand that registers the function as both `before_model` and `after_model`:

::::{tab-set}
:::{tab-item} Python
:sync: python

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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const safetyCheck = (ctx: unknown, data: unknown) => {
  // Runs both before and after model calls
  if (JSON.stringify(data).includes("dangerous")) {
    throw new Error("Safety violation detected");
  }
};

const agent = new Agent("service", "gemini-2.5-flash")
  .instruct("Handle requests.")
  .guard(safetyCheck)
  .build();
```
:::
::::

## Middleware Stacks with `.apply()`

For agents that need multiple layers of callbacks, use Presets to bundle them into reusable middleware stacks:

::::{tab-set}
:::{tab-item} Python
:sync: python

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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Preset } from "adk-fluent-ts";

// Define reusable middleware
const loggingPreset = new Preset({ beforeModel: logFn, afterModel: logResponseFn });
const securityPreset = new Preset({ beforeModel: safetyCheck, afterModel: auditFn });

// Apply multiple presets
const agent = new Agent("service", "gemini-2.5-flash")
  .instruct("Handle requests.")
  .use(loggingPreset)
  .use(securityPreset)
  .build();
```
:::
::::

See [Presets](presets.md) for more on reusable configuration bundles.

## Error Handling

Error callbacks handle failures in LLM calls and tool executions:

::::{tab-set}
:::{tab-item} Python
:sync: python

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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const handleModelError = (ctx: unknown, error: Error) => {
  console.log(`Model error: ${error.message}`);
  // Optionally return a fallback response
};

const handleToolError = (ctx: unknown, error: Error) => {
  console.log(`Tool error: ${error.message}`);
  // Optionally return a fallback result
};

const agent = new Agent("service", "gemini-2.5-flash")
  .instruct("Handle requests.")
  .onModelError(handleModelError)
  .onToolError(handleToolError)
  .build();
```
:::
::::

## Complete Example

::::{tab-set}
:::{tab-item} Python
:sync: python

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
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const logRequest = (ctx: { agentName: string }, req: unknown) =>
  console.log(`[LOG] Model request at ${ctx.agentName}`);

const logResponse = (ctx: { agentName: string }, resp: unknown) =>
  console.log(`[LOG] Model response at ${ctx.agentName}`);

const validateOutput = (ctx: unknown, resp: unknown) => {
  if (!resp) throw new Error("Empty response");
};

const auditTool = (ctx: unknown, result: unknown) =>
  console.log(`[AUDIT] Tool result: ${JSON.stringify(result)}`);

const agent = new Agent("production_agent", "gemini-2.5-flash")
  .instruct("You are a production service.")
  .beforeModel(logRequest)
  .afterModel(logResponse)
  .afterModel(validateOutput)
  .beforeTool((ctx, tool) => console.log(`Calling tool: ${String(tool)}`))
  .afterTool(auditTool)
  .onModelError((ctx, e) => console.log(`Error: ${(e as Error).message}`))
  .build();
```
:::
::::

## Callbacks vs. Middleware

Callbacks are **per-agent** -- they apply only to the agent they're attached to. For cross-cutting concerns that should apply to the entire execution (all agents in a pipeline), use **middleware** instead.

| Aspect       | Callbacks           | Middleware                      |
| ------------ | ------------------- | ------------------------------- |
| Scope        | Single agent        | Entire execution                |
| Attachment   | `.before_model(fn)` | `.middleware(mw)`               |
| Multiplicity | Multiple per agent  | Stack of middleware on pipeline |
| Compilation  | Stored on IR node   | Stored in ExecutionConfig       |

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, M

# Per-agent callback: only affects this agent
agent = Agent("a").before_model(log_fn)

# App-global middleware: affects all agents in the pipeline
pipeline = (Agent("a") >> Agent("b")).middleware(M.retry(3))
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, M } from "adk-fluent-ts";

// Per-agent callback: only affects this agent
const agent = new Agent("a", "gemini-2.5-flash").beforeModel(logFn);

// App-global middleware: affects all agents in the pipeline
const pipeline = new Agent("a", "gemini-2.5-flash")
  .then(new Agent("b", "gemini-2.5-flash"))
  .middleware(M.retry({ maxAttempts: 3 }));
```
:::
::::

See [Middleware](middleware.md) for the full middleware guide.

## Interplay with Other Modules

### Callbacks + Guards

`.guard(fn)` registers a function as both `before_model` and `after_model`. The G module provides structured guards that compile to callbacks automatically. Prefer G for safety/validation, raw callbacks for custom logic:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, G

# G module: declarative, composable, phase-aware
agent = Agent("safe").guard(G.pii("redact") | G.length(max=500))

# Raw callback: custom logic that doesn't fit G
agent = Agent("custom").before_model(my_custom_check)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, G } from "adk-fluent-ts";

// G module: declarative, composable, phase-aware
const safe = new Agent("safe", "gemini-2.5-flash")
  .guard(G.pii({ action: "redact" }).pipe(G.length({ max: 500 })));

// Raw callback: custom logic that doesn't fit G
const custom = new Agent("custom", "gemini-2.5-flash").beforeModel(myCustomCheck);
```
:::
::::

See [Guards](guards.md).

### Callbacks + Presets

Bundle callbacks into reusable Presets to avoid repetition across agents:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent.presets import Preset

observability = Preset(before_model=log_fn, after_model=metrics_fn)
agent_a = Agent("a").use(observability)
agent_b = Agent("b").use(observability)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, Preset } from "adk-fluent-ts";

const observability = new Preset({ beforeModel: logFn, afterModel: metricsFn });
const agentA = new Agent("a", "gemini-2.5-flash").use(observability);
const agentB = new Agent("b", "gemini-2.5-flash").use(observability);
```
:::
::::

See [Presets](presets.md).

### Callbacks + Context Engineering

Callbacks run *after* context engineering. The LLM request that `before_model` receives already has context filtering applied:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, C

agent = (
    Agent("classifier")
    .context(C.none())            # Context filtered first
    .before_model(log_request)    # Sees the filtered request
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, C } from "adk-fluent-ts";

const agent = new Agent("classifier", "gemini-2.5-flash")
  .context(C.none())            // Context filtered first
  .beforeModel(logRequest);     // Sees the filtered request
```
:::
::::

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
