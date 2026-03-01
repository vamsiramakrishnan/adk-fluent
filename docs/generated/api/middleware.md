# Module: middleware

> `from adk_fluent import M`

Fluent middleware composition. Consistent with P, C, S modules.

## Quick Reference

| Method                                 | Returns      | Description                                                         |
| -------------------------------------- | ------------ | ------------------------------------------------------------------- |
| `M.retry(max_attempts=3, backoff=1.0)` | `MComposite` | Retry middleware with exponential backoff                           |
| `M.log()`                              | `MComposite` | Structured event logging middleware                                 |
| `M.cost()`                             | `MComposite` | Token usage tracking middleware                                     |
| `M.latency()`                          | `MComposite` | Per-agent latency tracking middleware                               |
| `M.topology_log()`                     | `MComposite` | Topology event logging (loops, fanout, routes, fallbacks, timeouts) |
| `M.dispatch_log()`                     | `MComposite` | Dispatch/join lifecycle logging                                     |
| `M.scope(agents, mw)`                  | `MComposite` | Restrict middleware to specific agents                              |
| `M.when(condition, mw)`                | `MComposite` | Conditionally apply middleware                                      |
| `M.before_agent(fn)`                   | `MComposite` | Single-hook middleware: fires before each agent                     |
| `M.after_agent(fn)`                    | `MComposite` | Single-hook middleware: fires after each agent                      |
| `M.before_model(fn)`                   | `MComposite` | Single-hook middleware: fires before each LLM request               |
| `M.after_model(fn)`                    | `MComposite` | Single-hook middleware: fires after each LLM response               |
| `M.on_loop(fn)`                        | `MComposite` | Single-hook middleware: fires at each loop iteration                |
| `M.on_timeout(fn)`                     | `MComposite` | Single-hook middleware: fires when a timeout completes/expires      |
| `M.on_route(fn)`                       | `MComposite` | Single-hook middleware: fires when a route selects an agent         |
| `M.on_fallback(fn)`                    | `MComposite` | Single-hook middleware: fires at each fallback attempt              |

## Built-in factories

### `M.retry(max_attempts: int = 3, backoff: float = 1.0) -> MComposite`

Retry middleware with exponential backoff.

**Parameters:**

- `max_attempts` (*int*) — default: `3`
- `backoff` (*float*) — default: `1.0`

### `M.log() -> MComposite`

Structured event logging middleware.

### `M.cost() -> MComposite`

Token usage tracking middleware.

### `M.latency() -> MComposite`

Per-agent latency tracking middleware.

### `M.topology_log() -> MComposite`

Topology event logging (loops, fanout, routes, fallbacks, timeouts).

### `M.dispatch_log() -> MComposite`

Dispatch/join lifecycle logging.

## Composition operators

### `M.scope(agents: str | tuple[str, ...], mw: MComposite | Any) -> MComposite`

Restrict middleware to specific agents.

Usage:
M.scope("writer", M.cost())
M.scope(("writer", "reviewer"), M.log())

**Parameters:**

- `agents` (*str | tuple\[str, ...\]*)
- `mw` (*MComposite | Any*)

### `M.when(condition: str | Callable[[], bool] | type, mw: MComposite | Any) -> MComposite`

Conditionally apply middleware.

`condition` can be:
\- String shortcut: `"stream"`, `"dispatched"`, `"pipeline"`
matching ExecutionMode.
\- Callable returning bool, evaluated at hook invocation time.
\- `PredicateSchema` subclass, evaluated against session state
at hook invocation time.

Usage:
M.when("stream", M.latency())
M.when(lambda: is_debug(), M.log())
M.when(PremiumOnly, M.scope("writer", M.cost()))

**Parameters:**

- `condition` (*str | Callable\[\[\], bool\] | type*)
- `mw` (*MComposite | Any*)

## Single-hook shortcuts

### `M.before_agent(fn: Callable) -> MComposite`

Single-hook middleware: fires before each agent.

**Parameters:**

- `fn` (*Callable*)

### `M.after_agent(fn: Callable) -> MComposite`

Single-hook middleware: fires after each agent.

**Parameters:**

- `fn` (*Callable*)

### `M.before_model(fn: Callable) -> MComposite`

Single-hook middleware: fires before each LLM request.

**Parameters:**

- `fn` (*Callable*)

### `M.after_model(fn: Callable) -> MComposite`

Single-hook middleware: fires after each LLM response.

**Parameters:**

- `fn` (*Callable*)

### `M.on_loop(fn: Callable) -> MComposite`

Single-hook middleware: fires at each loop iteration.

**Parameters:**

- `fn` (*Callable*)

### `M.on_timeout(fn: Callable) -> MComposite`

Single-hook middleware: fires when a timeout completes/expires.

**Parameters:**

- `fn` (*Callable*)

### `M.on_route(fn: Callable) -> MComposite`

Single-hook middleware: fires when a route selects an agent.

**Parameters:**

- `fn` (*Callable*)

### `M.on_fallback(fn: Callable) -> MComposite`

Single-hook middleware: fires at each fallback attempt.

**Parameters:**

- `fn` (*Callable*)

## Composition Operators

### `|` (compose (MComposite))

Stack middleware into a chain

## Types

| Type         | Description                  |
| ------------ | ---------------------------- |
| `MComposite` | Composable middleware chain. |
