# Middleware

Middleware provides app-global cross-cutting behavior. Unlike [callbacks](callbacks.md) which are per-agent, middleware applies to the entire execution across all agents. Unlike [presets](presets.md) which share config across agents, middleware operates at the *pipeline* level.

## When to Use Middleware vs. Callbacks vs. Presets vs. Guards

| Mechanism | Scope | Purpose | Example |
|---|---|---|---|
| **Callbacks** | Single agent | Agent-specific behavior | Audit logging on one agent |
| **Presets** | Multiple agents | Shared configuration | Same model + callbacks on all agents |
| **Middleware** | Entire pipeline | Cross-cutting infrastructure | Retry, circuit breaker, tracing |
| **Guards** | Single agent | Safety / validation | PII redaction, output length |

**Use Middleware when** the concern is infrastructure-level and should apply uniformly across the pipeline. If you're adding retry logic, logging, or tracing to individual agents, you're doing it wrong -- use middleware.

## Attaching Middleware

Use `.middleware()` on any builder, then `.to_app()` to compile:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, M

pipeline = (
    Agent("a") >> Agent("b")
).middleware(M.retry(3) | M.log())

app = pipeline.to_app()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, M } from "adk-fluent-ts";

const pipeline = new Agent("a", "gemini-2.5-flash")
  .then(new Agent("b", "gemini-2.5-flash"))
  .middleware(M.retry({ maxAttempts: 3 }).pipe(M.log()));

const app = pipeline.toApp();
```
:::
::::

Multiple `.middleware()` calls accumulate. When combined with `>>` / `.then()` or `|` / `.parallel()`, middleware from all operands is merged.

:::{note} TypeScript naming
TypeScript uses camelCase and options objects: `M.retry({ maxAttempts: 3 })`, `M.circuitBreaker({ maxFails: 5 })`, `M.fallbackModel("gemini-2.5-pro")`. Composition uses `.pipe()` instead of Python's `|`.
:::

## The M Module

The M module provides composable middleware factories. Compose with `|` / `.pipe()` (chain):

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, M

# Compose a middleware stack
stack = M.retry(3) | M.log() | M.latency() | M.cost()
pipeline = (Agent("a") >> Agent("b")).middleware(stack)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, M } from "adk-fluent-ts";

// Compose a middleware stack
const stack = M.retry({ maxAttempts: 3 })
  .pipe(M.log())
  .pipe(M.latency())
  .pipe(M.cost());

const pipeline = new Agent("a", "gemini-2.5-flash")
  .then(new Agent("b", "gemini-2.5-flash"))
  .middleware(stack);
```
:::
::::

### Built-in Middleware

| Factory | Purpose | Key args |
|---|---|---|
| `M.retry(max_attempts)` | Retry with exponential backoff | `base_delay=1.0`, `backoff_factor=2.0` |
| `M.log()` | Structured event logging | -- |
| `M.cost()` | Token usage tracking | -- |
| `M.latency()` | Per-agent latency tracking | -- |
| `M.circuit_breaker(max_fails)` | Stop calling a failing model | `reset_timeout=60` |
| `M.timeout(seconds)` | Per-agent timeout | -- |
| `M.cache(ttl)` | Response caching | -- |
| `M.fallback_model(model)` | Fallback to different model on error | -- |
| `M.dedup()` | Deduplicate identical requests | -- |
| `M.sample(rate)` | Probabilistic sampling | -- |
| `M.trace()` | Distributed tracing | -- |
| `M.metrics()` | Metrics collection | -- |
| `M.scope(agents, mw)` | Restrict middleware to specific agents | -- |
| `M.when(condition, mw)` | Conditional middleware | -- |

### Composition Order Matters

Middleware runs in the order you compose it. For non-void hooks (`before_model`, `before_tool`), the first middleware to return a non-None value short-circuits the rest:

```python
# Retry wraps logging wraps cost tracking (Python: |, TypeScript: .pipe())
stack = M.retry(3) | M.log() | M.cost()

# Execution order for before_model:
#   1. retry.before_model (retries if error occurs downstream)
#   2. log.before_model (logs the request)
#   3. cost.before_model (starts token counting)
#
# Execution order for after_model:
#   3. cost.after_model (records tokens)
#   2. log.after_model (logs the response)
#   1. retry.after_model (checks for retryable errors)
```

:::{admonition} Rule of thumb
:class: tip
Put **retry** first (outermost), **logging** next, then specific concerns (cost, latency, caching). This way retry wraps everything, and logging captures both successful and retried calls.
:::

### Scoping Middleware

Apply middleware to specific agents only:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
# Only retry the LLM-calling agents, not the state transforms
stack = M.scope(["classifier", "resolver"], M.retry(3)) | M.log()
pipeline = (Agent("classifier") >> Agent("resolver")).middleware(stack)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
// Only retry the LLM-calling agents, not the state transforms
const stack = M.scope(["classifier", "resolver"], M.retry({ maxAttempts: 3 })).pipe(M.log());
const pipeline = new Agent("classifier", "gemini-2.5-flash")
  .then(new Agent("resolver", "gemini-2.5-flash"))
  .middleware(stack);
```
:::
::::

### Conditional Middleware

Apply middleware based on runtime conditions:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
import os

# Only enable cost tracking in production
stack = M.log() | M.when(os.getenv("ENV") == "production", M.cost())
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
// Only enable cost tracking in production
const stack = M.log().pipe(M.when(process.env.ENV === "production", M.cost()));
```
:::
::::

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

## Writing Custom Middleware

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
import time

class TimingMiddleware:
    """Track execution time for each agent."""

    def __init__(self):
        self.timings = {}

    async def before_agent(self, *, agent, context, **kw):
        context.state["_start"] = time.time()

    async def after_agent(self, *, agent, context, **kw):
        elapsed = time.time() - context.state.get("_start", time.time())
        self.timings[agent.name] = elapsed
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
class TimingMiddleware {
  timings: Record<string, number> = {};

  async beforeAgent({ agent, context }: { agent: { name: string }; context: { state: Record<string, unknown> } }) {
    context.state._start = Date.now();
  }

  async afterAgent({ agent, context }: { agent: { name: string }; context: { state: Record<string, unknown> } }) {
    const start = (context.state._start as number) ?? Date.now();
    this.timings[agent.name] = Date.now() - start;
  }
}
```
:::
::::

## How Middleware Works

When `.to_app()` is called:

1. Builder middleware (from `.middleware()`) is merged with `ExecutionConfig.middlewares`
2. The middleware stack is compiled into a single `_MiddlewarePlugin` (an ADK `BasePlugin`)
3. The plugin is attached to the `App` via `plugins=[plugin]`

```
Middleware Lifecycle (execution order):

  before_run ──────────────────────────────────── after_run
      │                                               │
      ▼                                               │
  before_agent ─────────────────────── after_agent    │
      │                                    │          │
      ▼                                    │          │
  before_model ─► LLM call ─► after_model  │          │
      │               │            │       │          │
      │          on_model_error     │       │          │
      │                            │       │          │
  before_tool ──► tool() ──► after_tool    │          │
                     │                     │          │
                on_tool_error              │          │
                                           │          │
  Stack order: mw[0] → mw[1] → mw[2]     │          │
  Short-circuit: first non-None return wins│          │
  Void hooks: ALL middleware always called ─┘──────────┘
```

## Interplay with Other Modules

### Middleware + Guards

Guards are per-agent safety checks. Middleware is pipeline-wide infrastructure. Use both:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, G, M

agent = Agent("service").instruct("Help.").guard(G.pii("redact") | G.length(max=500))
pipeline = (agent >> Agent("auditor")).middleware(M.retry(3) | M.log())
# Guards: PII redaction on the service agent only
# Middleware: retry + logging on the entire pipeline
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, G, M } from "adk-fluent-ts";

const agent = new Agent("service", "gemini-2.5-flash")
  .instruct("Help.")
  .guard(G.pii({ action: "redact" }).pipe(G.length({ max: 500 })));

const pipeline = agent
  .then(new Agent("auditor", "gemini-2.5-flash"))
  .middleware(M.retry({ maxAttempts: 3 }).pipe(M.log()));
// Guards: PII redaction on the service agent only
// Middleware: retry + logging on the entire pipeline
```
:::
::::

See [Guards](guards.md).

### Middleware + Visibility

Middleware sees *all* agents regardless of visibility. `M.log()` captures events from hidden agents:

```python
pipeline = (
    Agent("hidden").instruct("Internal.").hide()
    >> Agent("visible").instruct("User-facing.")
).middleware(M.log())
# M.log() captures events from BOTH agents
```

See [Visibility](visibility.md).

### Middleware + Context Engineering

Middleware and context engineering don't interact directly, but they complement each other. Context engineering controls what the LLM sees; middleware controls how the pipeline behaves:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, C, M

pipeline = (
    Agent("classifier").context(C.none()).writes("intent")
    >> Agent("resolver").context(C.from_state("intent"))
).middleware(M.retry(3) | M.log() | M.cost())
# Context: each agent sees only what it needs
# Middleware: retry, logging, cost tracking across all agents
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, C, M } from "adk-fluent-ts";

const pipeline = new Agent("classifier", "gemini-2.5-flash")
  .context(C.none())
  .writes("intent")
  .then(new Agent("resolver", "gemini-2.5-flash").context(C.fromState("intent")))
  .middleware(M.retry({ maxAttempts: 3 }).pipe(M.log()).pipe(M.cost()));
// Context: each agent sees only what it needs
// Middleware: retry, logging, cost tracking across all agents
```
:::
::::

### Middleware + Testing

Use `M.log()` in tests to capture events for assertions:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, M

logger = M.log()
pipeline = (Agent("a") >> Agent("b")).middleware(logger)
app = pipeline.to_app()
# After execution: inspect logger.events for assertions
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, M } from "adk-fluent-ts";

const logger = M.log();
const pipeline = new Agent("a", "gemini-2.5-flash")
  .then(new Agent("b", "gemini-2.5-flash"))
  .middleware(logger);
const app = pipeline.toApp();
// After execution: inspect logger events for assertions
```
:::
::::

See [Testing](testing.md).

## Best Practices

1. **Don't scatter callbacks when middleware will do.** If 5 agents all need retry logic, use `M.retry()` once on the pipeline, not `.on_model_error()` 5 times
2. **Put retry outermost in the middleware stack.** `M.retry(3) | M.log()` means retry wraps logging -- retried calls are logged correctly
3. **Use `M.scope()` for agent-specific middleware.** Not all agents need the same middleware -- scope expensive operations (caching, circuit breaker) to agents that benefit
4. **Use `M.when()` for environment-specific behavior.** Don't branch in your pipeline code -- let middleware handle it
5. **Middleware is for infrastructure, not business logic.** Retry, logging, tracing, caching -- these are middleware concerns. Routing, classification, data transformation -- these are agent/function concerns

## Backend Awareness

Middleware works across all execution backends:

- **ADK backend**: Middleware runs as ADK `BasePlugin` instances compiled into the App
- **Temporal backend** (in development): Middleware runs as runtime hooks around workflow/activity execution
- **asyncio backend** (in development): Middleware runs as direct Python hooks

The middleware *definition* is identical regardless of backend. Only the execution mechanism differs:

```python
# Same middleware definition, works with any engine
pipeline = (Agent("a") >> Agent("b")).middleware(M.retry(3) | M.log())

# ADK (default)
app = pipeline.to_app()

# Temporal (in development)
pipeline_t = pipeline.engine("temporal", client=client)
response = await pipeline_t.ask_async("Go")
```

:::{seealso}
- [Execution Backends](execution-backends.md) — backend selection and capability matrix
- [Temporal Guide](temporal-guide.md) — durable execution and how middleware interacts with Temporal
- [Callbacks](callbacks.md) — per-agent callback attachment
- [Presets](presets.md) — shared agent configuration
- [Guards](guards.md) — per-agent safety and validation
- [Visibility](visibility.md) — controlling user-facing output
- [Best Practices](best-practices.md) — the "Callbacks vs. Middleware" decision tree
:::
