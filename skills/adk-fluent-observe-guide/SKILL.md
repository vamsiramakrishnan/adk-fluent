---
name: adk-fluent-observe-guide
description: >
  MUST READ before setting up observability for adk-fluent agents.
  Observability guide — M namespace middleware (logging, tracing, metrics,
  cost tracking), built-in introspection, Cloud Trace, BigQuery analytics,
  and third-party integrations. Use when monitoring, debugging, or analyzing
  agent behavior in development or production.
metadata:
  license: Apache-2.0
  author: vamsiramakrishnan
  version: "0.13.5"
---

# adk-fluent Observability Guide

> **adk-fluent provides observability at two levels:**
> 1. Build-time introspection (`.explain()`, `.doctor()`, `.data_flow()`)
> 2. Runtime middleware (M namespace — logging, tracing, metrics, cost)
>
> Since `.build()` returns native ADK objects, all ADK observability integrations
> (Cloud Trace, BigQuery, third-party) also work unchanged.

## Reference Files

| File | Contents |
|------|----------|
| [`namespace-methods.md`](namespace-methods.md) | M namespace — all middleware methods and signatures |
| [`api-surface.md`](api-surface.md) | Introspection methods (`.explain()`, `.doctor()`, etc.) |

---

## Observability Tiers

| Tier | What It Does | adk-fluent API | Default |
|------|-------------|----------------|---------|
| **Build-time introspection** | Config inspection, topology, data flow | `.explain()`, `.doctor()`, `.data_flow()` | Always available |
| **Debug tracing** | Runtime stderr tracing | `.debug()` | Off |
| **Structured logging** | Agent lifecycle events | `M.log()` | Opt-in |
| **Token cost tracking** | Usage per agent | `M.cost()` | Opt-in |
| **Latency tracking** | Per-agent timing | `M.latency()` | Opt-in |
| **OpenTelemetry tracing** | Distributed spans | `M.trace()` | Opt-in |
| **Metrics collection** | Custom metrics | `M.metrics()` | Opt-in |
| **Cloud Trace** | GCP distributed tracing | ADK native | Automatic in Agent Engine |
| **BigQuery Analytics** | Structured event logging | ADK plugin | Opt-in |

---

## Build-Time Introspection

Use these before deployment to understand and validate your agent:

```python
from adk_fluent import Agent, P, C

agent = (
    Agent("analyst", "gemini-2.5-flash")
    .instruct(P.role("Data analyst") | P.task("Analyze data"))
    .context(C.window(n=5))
    .writes("analysis")
    .tool(search_fn)
)

# Quick config summary
agent.explain()

# What the LLM actually sees (instruction, tools, context)
agent.llm_anatomy()

# Five-concern data flow view
agent.data_flow()

# Formatted diagnostic report
agent.doctor()

# Validate contracts and configuration
issues = agent.validate()
for issue in issues:
    print(f"  - {issue}")

# Mermaid diagram (copy to mermaid.live)
print(agent.to_mermaid())

# Structured IR tree
agent.to_ir()
```

### Pipeline introspection

```python
pipeline = Agent("a").writes("x") >> Agent("b").reads("x")

# Contract checking — finds mismatched .reads()/.writes()
from adk_fluent import check_contracts
issues = check_contracts(pipeline)

# Topology diagram
print(pipeline.to_mermaid())
```

---

## Runtime Debug Tracing

Quick stderr tracing for development:

```python
agent = Agent("test", "gemini-2.5-flash").instruct("...").debug()
result = agent.ask("prompt")  # Traces appear on stderr
```

---

## M Namespace — Middleware

Attach middleware for runtime observability. Compose with `|` (chain):

```python
from adk_fluent import Agent, M

agent = (
    Agent("prod", "gemini-2.5-flash")
    .instruct("Production agent.")
    .middleware(
        M.log()                          # Structured event logging
        | M.cost()                       # Token usage tracking
        | M.latency()                    # Per-agent latency
        | M.trace()                      # OpenTelemetry spans
        | M.metrics()                    # Custom metrics
    )
)
```

### Logging

```python
# Structured event logging to stderr
agent.middleware(M.log())

# Topology-aware logging (loops, fanout, routes, fallbacks)
agent.middleware(M.topology_log())

# Dispatch/join lifecycle logging
agent.middleware(M.dispatch_log())
```

### Cost & Latency

```python
# Token usage tracking
agent.middleware(M.cost())

# Per-agent latency
agent.middleware(M.latency())
```

### OpenTelemetry Tracing

```python
# Basic (no-op if opentelemetry not installed)
agent.middleware(M.trace())

# With custom exporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
agent.middleware(M.trace(exporter=ConsoleSpanExporter()))
```

### Custom Hooks

```python
# Before/after agent
agent.middleware(M.before_agent(lambda ctx: print(f"Starting {ctx.agent_name}")))
agent.middleware(M.after_agent(lambda ctx: print(f"Done {ctx.agent_name}")))

# Before/after model
agent.middleware(M.before_model(lambda ctx: print("Calling LLM...")))
agent.middleware(M.after_model(lambda ctx: print("LLM responded.")))

# Lifecycle events
agent.middleware(M.on_loop(lambda ctx: print(f"Loop iteration {ctx.iteration}")))
agent.middleware(M.on_timeout(lambda ctx: print("Timeout!")))
agent.middleware(M.on_route(lambda ctx: print(f"Routed to {ctx.target}")))
agent.middleware(M.on_fallback(lambda ctx: print("Falling back...")))
```

### Scoped & Conditional Middleware

```python
# Apply only to specific agents
agent.middleware(M.scope("researcher", M.log()))

# Conditional (e.g., only in production)
agent.middleware(M.when("PRODUCTION", M.log() | M.cost()))

# Probabilistic sampling (10% of requests)
agent.middleware(M.sample(0.1, M.trace()))
```

---

## Resilience Middleware

These also provide observability through failure tracking:

```python
agent.middleware(
    M.retry(max_attempts=3, backoff=1.0)       # Retry with backoff
    | M.timeout(seconds=30)                     # Per-agent timeout
    | M.circuit_breaker(threshold=5, reset_after=60)  # Circuit breaker
    | M.fallback_model("gemini-2.0-flash")     # Auto-downgrade on failure
    | M.cache(ttl=300)                          # Response caching
    | M.dedup(window=10)                        # Suppress duplicates
)
```

---

## ADK Native Observability

Since `.build()` returns ADK objects, all ADK integrations work:

### Cloud Trace

Automatic in Agent Engine. For Cloud Run:

```python
# In your FastAPI app
from google.adk.cli.fast_api import get_fast_api_app
app = get_fast_api_app(agent_dir="app/", otel_to_cloud=True)
```

View traces: **Cloud Console → Trace → Trace explorer**

### BigQuery Agent Analytics

Use the ADK plugin:

```python
from google.adk.plugins import BigQueryAgentAnalyticsPlugin

# Add via .native() escape hatch
agent = (
    Agent("prod", "gemini-2.5-flash")
    .instruct("...")
    .native(lambda adk_agent: setattr(adk_agent, 'plugins', [BigQueryAgentAnalyticsPlugin()]))
    .build()
)
```

Or use the generated plugin builder:

```python
from adk_fluent import Agent, BigQueryAgentAnalyticsPlugin as BQPlugin

agent = Agent("prod", "gemini-2.5-flash").instruct("...").plugin(BQPlugin().build())
```

### Third-Party Integrations

| Platform | Setup | Key Feature |
|----------|-------|-------------|
| **AgentOps** | 2-line setup | Session replays |
| **Phoenix** | Open-source | Custom evaluators |
| **MLflow** | OTel traces | Span visualization |
| **Monocle** | 1-call setup | VS Code Gantt charts |
| **Weave** | W&B platform | Team collaboration |
| **Arize AX** | Commercial | Production monitoring |
| **Freeplay** | SaaS | Prompt management |

These integrate at the ADK level. Fetch the relevant docs:
- `https://google.github.io/adk-docs/integrations/cloud-trace/index.md`
- `https://google.github.io/adk-docs/integrations/phoenix/index.md`

---

## Recommended Observability Stack

### Development

```python
agent = (
    Agent("dev", "gemini-2.5-flash")
    .instruct("...")
    .debug()                                    # stderr tracing
    .middleware(M.log() | M.cost() | M.latency())
)

# Inspect before running
agent.explain()
agent.doctor()
```

### Staging

```python
agent = (
    Agent("staging", "gemini-2.5-flash")
    .instruct("...")
    .middleware(
        M.log()
        | M.cost()
        | M.latency()
        | M.trace()
        | M.retry(max_attempts=2)
        | M.timeout(seconds=30)
    )
)
```

### Production

```python
agent = (
    Agent("prod", "gemini-2.5-flash")
    .instruct("...")
    .middleware(
        M.log()
        | M.cost()
        | M.latency()
        | M.trace()
        | M.metrics()
        | M.retry(max_attempts=3)
        | M.timeout(seconds=30)
        | M.circuit_breaker(threshold=5)
    )
    .guard(G.pii() | G.length(max=5000))
)
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No traces in Cloud Trace | Verify `otel_to_cloud=True`; check SA has `cloudtrace.agent` role |
| `M.trace()` produces nothing | Install `opentelemetry-sdk` and configure an exporter |
| `.explain()` shows unexpected config | Config methods may have been called in wrong order — check chaining |
| Agent silently fails | Add `M.log()` to see lifecycle events |
| High token costs | Add `M.cost()` to track per-agent usage; use `C.window()` to limit context |
| Slow responses | Add `M.latency()` to find bottleneck agent; add `M.timeout()` |
| Circuit breaker tripping | Check error rates with `M.log()`; adjust threshold or fix root cause |
