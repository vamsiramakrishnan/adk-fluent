# Module: middleware

> `from adk_fluent import M`

Fluent middleware composition. Consistent with P, C, S modules.

## Quick Reference

| Method                                                                                         | Returns      | Description                                                           |
| ---------------------------------------------------------------------------------------------- | ------------ | --------------------------------------------------------------------- |
| `M.retry(max_attempts=3, backoff=1.0)`                                                         | `MComposite` | Retry middleware with exponential backoff                             |
| `M.log()`                                                                                      | `MComposite` | Structured event logging middleware                                   |
| `M.cost()`                                                                                     | `MComposite` | Token usage tracking middleware                                       |
| `M.latency()`                                                                                  | `MComposite` | Per-agent latency tracking middleware                                 |
| `M.topology_log()`                                                                             | `MComposite` | Topology event logging (loops, fanout, routes, fallbacks, timeouts)   |
| `M.dispatch_log()`                                                                             | `MComposite` | Dispatch/join lifecycle logging                                       |
| `M.scope(agents, mw)`                                                                          | `MComposite` | Restrict middleware to specific agents                                |
| `M.when(condition, mw)`                                                                        | `MComposite` | Conditionally apply middleware                                        |
| `M.before_agent(fn)`                                                                           | `MComposite` | Single-hook middleware: fires before each agent                       |
| `M.after_agent(fn)`                                                                            | `MComposite` | Single-hook middleware: fires after each agent                        |
| `M.before_model(fn)`                                                                           | `MComposite` | Single-hook middleware: fires before each LLM request                 |
| `M.after_model(fn)`                                                                            | `MComposite` | Single-hook middleware: fires after each LLM response                 |
| `M.on_loop(fn)`                                                                                | `MComposite` | Single-hook middleware: fires at each loop iteration                  |
| `M.on_timeout(fn)`                                                                             | `MComposite` | Single-hook middleware: fires when a timeout completes/expires        |
| `M.on_route(fn)`                                                                               | `MComposite` | Single-hook middleware: fires when a route selects an agent           |
| `M.on_fallback(fn)`                                                                            | `MComposite` | Single-hook middleware: fires at each fallback attempt                |
| `M.circuit_breaker(threshold=5, reset_after=60)`                                               | `MComposite` | Circuit breaker — trips open after N consecutive model errors         |
| `M.timeout(seconds=30)`                                                                        | `MComposite` | Per-agent execution timeout                                           |
| `M.cache(ttl=300, key_fn=None)`                                                                | `MComposite` | Cache LLM responses keyed by request content                          |
| `M.fallback_model(model='gemini-2.0-flash')`                                                   | `MComposite` | Auto-downgrade to fallback model on primary model failure             |
| `M.dedup(window=10)`                                                                           | `MComposite` | Suppress duplicate model calls within a sliding window                |
| `M.sample(rate, mw)`                                                                           | `MComposite` | Probabilistic middleware — fires inner middleware only N% of the time |
| `M.trace(exporter=None)`                                                                       | `MComposite` | OpenTelemetry span export (no-op if opentelemetry not installed)      |
| `M.metrics(collector=None)`                                                                    | `MComposite` | Metrics collection (no-op if no collector provided)                   |
| `M.a2a_retry(max_attempts=3, backoff=2.0, agents=None, on_retry=None)`                         | `MComposite` | A2A-specific retry middleware for remote agent failures               |
| `M.a2a_circuit_breaker(threshold=5, reset_after=60, agents=None, on_open=None, on_close=None)` | `MComposite` | Circuit breaker for A2A remote agents                                 |
| `M.a2a_timeout(seconds=30, agents=None, on_timeout=None)`                                      | `MComposite` | Per-delegation timeout for A2A remote agent calls                     |

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
    - String shortcut: `"stream"`, `"dispatched"`, `"pipeline"`
      matching ExecutionMode.
    - Callable returning bool, evaluated at hook invocation time.
    - `PredicateSchema` subclass, evaluated against session state
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

## ------------------------------------------------------------

### `M.circuit_breaker(threshold: int = 5, reset_after: float = 60) -> MComposite`

Circuit breaker — trips open after N consecutive model errors.

**Parameters:**

- `threshold` (*int*) — default: `5`
- `reset_after` (*float*) — default: `60`

### `M.timeout(seconds: float = 30) -> MComposite`

Per-agent execution timeout.

**Parameters:**

- `seconds` (*float*) — default: `30`

### `M.cache(ttl: float = 300, key_fn: Any = None) -> MComposite`

Cache LLM responses keyed by request content.

**Parameters:**

- `ttl` (*float*) — default: `300`
- `key_fn` (*Any*) — default: `None`

### `M.fallback_model(model: str = gemini-2.0-flash) -> MComposite`

Auto-downgrade to fallback model on primary model failure.

**Parameters:**

- `model` (*str*) — default: `'gemini-2.0-flash'`

### `M.dedup(window: int = 10) -> MComposite`

Suppress duplicate model calls within a sliding window.

**Parameters:**

- `window` (*int*) — default: `10`

### `M.sample(rate: float, mw: MComposite | Any) -> MComposite`

Probabilistic middleware — fires inner middleware only N% of the time.

**Parameters:**

- `rate` (*float*)
- `mw` (*MComposite | Any*)

### `M.trace(exporter: Any = None) -> MComposite`

OpenTelemetry span export (no-op if opentelemetry not installed).

**Parameters:**

- `exporter` (*Any*) — default: `None`

### `M.metrics(collector: Any = None) -> MComposite`

Metrics collection (no-op if no collector provided).

**Parameters:**

- `collector` (*Any*) — default: `None`

## A2A-specific middleware

### `M.a2a_retry(max_attempts: int = 3, backoff: float = 2.0, *, agents: str | tuple[str, ...] | None = None, on_retry: Callable | None = None) -> MComposite`

A2A-specific retry middleware for remote agent failures.

Handles HTTP transport errors, A2A task FAILED/REJECTED states,
and network-level transient failures. Uses exponential backoff.

**Args:**

- **`max_attempts`**: Maximum number of retry attempts (default 3).
- **`backoff`**: Base delay in seconds for exponential backoff (default 2.0).
- **`agents`**: Scope to specific agent names (default: all agents).
- **`on_retry`**: Optional callback `(ctx, agent_name, attempt, error)`
  called before each retry.

Usage:
    pipeline.middleware(M.a2a_retry(max_attempts=3, backoff=2.0))
    pipeline.middleware(M.scope("remote_*", M.a2a_retry()))

**Parameters:**

- `max_attempts` (*int*) — default: `3`
- `backoff` (*float*) — default: `2.0`
- `agents` (*str | tuple\[str, ...\] | None*) — default: `None`
- `on_retry` (*Callable | None*) — default: `None`

### `M.a2a_circuit_breaker(threshold: int = 5, reset_after: float = 60, *, agents: str | tuple[str, ...] | None = None, on_open: Callable | None = None, on_close: Callable | None = None) -> MComposite`

Circuit breaker for A2A remote agents.

Opens after `threshold` consecutive failures. Stays open for
`reset_after` seconds, then allows a single probe call.

**Args:**

- **`threshold`**: Number of failures before opening (default 5).
- **`reset_after`**: Seconds to stay open before half-open probe (default 60).
- **`agents`**: Scope to specific agent names (default: all agents).
- **`on_open`**: Callback `(ctx, agent_name)` when circuit opens.
- **`on_close`**: Callback `(ctx, agent_name)` when circuit closes.

Usage:
    pipeline.middleware(M.a2a_circuit_breaker(threshold=5, reset_after=60))

**Parameters:**

- `threshold` (*int*) — default: `5`
- `reset_after` (*float*) — default: `60`
- `agents` (*str | tuple\[str, ...\] | None*) — default: `None`
- `on_open` (*Callable | None*) — default: `None`
- `on_close` (*Callable | None*) — default: `None`

### `M.a2a_timeout(seconds: float = 30, *, agents: str | tuple[str, ...] | None = None, on_timeout: Callable | None = None) -> MComposite`

Per-delegation timeout for A2A remote agent calls.

Enforces wall-clock time limits on entire agent invocations.
Critical for remote A2A calls with network latency + remote LLM
processing.

**Args:**

- **`seconds`**: Maximum seconds for the agent invocation (default 30).
- **`agents`**: Scope to specific agent names (default: all agents).
- **`on_timeout`**: Callback `(ctx, agent_name, seconds)` on timeout.

Usage:
    pipeline.middleware(M.a2a_timeout(seconds=30))
    pipeline.middleware(M.scope("slow_agent", M.a2a_timeout(120)))

**Parameters:**

- `seconds` (*float*) — default: `30`
- `agents` (*str | tuple\[str, ...\] | None*) — default: `None`
- `on_timeout` (*Callable | None*) — default: `None`

## Composition Operators

### `|` (compose (MComposite))

Stack middleware into a chain

## Types

| Type         | Description                  |
| ------------ | ---------------------------- |
| `MComposite` | Composable middleware chain. |
