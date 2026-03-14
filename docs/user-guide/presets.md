# Presets

Presets are reusable configuration bundles that can be applied to any builder via `.use()`. They solve a specific problem: when 10 agents in a pipeline all need the same model, the same logging callbacks, and the same safety checks, you shouldn't repeat that configuration 10 times.

## When to Use Presets vs. Middleware vs. Callbacks

This is the most common question. The answer depends on **scope**:

| Mechanism | Scope | Best for | Applied via |
|---|---|---|---|
| **Callbacks** | Single agent | Agent-specific logic (validation, audit) | `.before_model(fn)` |
| **Presets** | Multiple agents | Shared configuration (model, callbacks) | `.use(preset)` |
| **Middleware** | Entire pipeline | Cross-cutting concerns (retry, logging) | `.middleware(mw)` |

**Use Presets when** you want multiple agents to share the same config but each agent has its own identity and instructions. Presets are applied *before* build time -- they're syntactic sugar for repeating `.model().before_model().after_model()` on every agent.

**Use Middleware when** you want behavior that spans the *entire execution* -- all agents, all tools, all model calls. Middleware runs at the App level, not the agent level.

**Use Callbacks when** the behavior is unique to one agent and shouldn't be shared.

## Basic Usage

```python
from adk_fluent import Agent
from adk_fluent.presets import Preset

production = Preset(model="gemini-2.5-flash", before_model=log_fn, after_model=audit_fn)

agent = Agent("service").instruct("Handle requests.").use(production).build()
```

## How Presets Work

A `Preset` accepts keyword arguments that map to builder fields:

- **Config values** -- `model`, `instruction`, `description`, `output_key`, `include_contents`, `max_iterations`, etc. Applied directly to the builder.
- **Callbacks** -- callable values (functions) are treated as callbacks. The key name determines the callback field (e.g., `before_model`, `after_model`).

```python
preset = Preset(
    model="gemini-2.5-flash",               # Config value
    before_model=log_fn,                      # Callback
    after_model=audit_fn,                     # Callback
)
```

## Composing Presets

Multiple presets can be applied to the same builder. Each `.use()` call accumulates configuration:

```python
logging_preset = Preset(before_model=log_fn, after_model=log_response_fn)
security_preset = Preset(before_model=safety_check)
model_preset = Preset(model="gemini-2.5-flash")

agent = (
    Agent("service")
    .instruct("Handle requests.")
    .use(model_preset)
    .use(logging_preset)
    .use(security_preset)
    .build()
)
```

:::{admonition} Composition Order
:class: important
For config values (like `model`), the **last** `.use()` wins. For callbacks, all presets accumulate -- `logging_preset`'s callbacks run alongside `security_preset`'s callbacks.
:::

## Use Cases

### Environment-Specific Configuration

```python
dev_preset = Preset(model="gemini-2.0-flash", before_model=debug_log)
prod_preset = Preset(model="gemini-2.5-flash", before_model=metrics_fn, after_model=audit_fn)

import os
preset = prod_preset if os.getenv("ENV") == "production" else dev_preset

agent = Agent("service").instruct("Handle requests.").use(preset).build()
```

### Team-Wide Standards

```python
# Shared across all agents in a team
team_standard = Preset(
    model="gemini-2.5-flash",
    before_model=request_logger,
    after_model=response_validator,
)

agent_a = Agent("agent_a").instruct("Task A.").use(team_standard).build()
agent_b = Agent("agent_b").instruct("Task B.").use(team_standard).build()
```

### Callback Stacks

Since callbacks are additive, presets compose naturally into middleware stacks:

```python
observability = Preset(before_model=trace_start, after_model=trace_end)
safety = Preset(before_model=content_filter, after_model=output_filter)

agent = (
    Agent("service")
    .instruct("Handle requests.")
    .use(observability)
    .use(safety)
    .build()
)
# Both observability AND safety callbacks are active
```

## Interplay with Other Modules

### Presets + Middleware

Presets configure individual agents. Middleware configures the entire pipeline. They complement each other:

```python
from adk_fluent import Agent
from adk_fluent._middleware import M
from adk_fluent.presets import Preset

# Preset: every agent uses the same model and logging
agent_config = Preset(model="gemini-2.5-flash", before_model=log_fn)

# Build agents with shared config
classifier = Agent("classifier").instruct("Classify.").use(agent_config)
resolver = Agent("resolver").instruct("Resolve.").use(agent_config)

# Middleware: retry and tracing apply to the ENTIRE pipeline
pipeline = (classifier >> resolver).middleware(M.retry(3) | M.log())
```

### Presets + Guards

Presets can include guard callbacks, but for structured safety, prefer the G module:

```python
from adk_fluent import Agent, G
from adk_fluent.presets import Preset

# Preset for config, G module for safety -- separation of concerns
config = Preset(model="gemini-2.5-flash")
safety = G.pii("redact") | G.length(max=500)

agent = Agent("safe").instruct("Help.").use(config).guard(safety).build()
```

### Presets + Context Engineering

Presets can set `include_contents` but the C module is more expressive:

```python
from adk_fluent import Agent, C
from adk_fluent.presets import Preset

config = Preset(model="gemini-2.5-flash")

# C module is richer than preset's include_contents
agent = Agent("classifier").instruct("Classify.").use(config).context(C.none()).build()
```

## Best Practices

1. **Name presets by their role**, not their contents: `production` not `gemini_flash_with_logging`
2. **Keep presets small and composable.** A `model_preset`, `logging_preset`, and `safety_preset` compose better than one monolithic `everything_preset`
3. **Don't put instructions in presets.** Instructions are agent-specific -- they belong on the agent, not in a shared config
4. **Use presets for agents, middleware for pipelines.** Presets don't have a `retry` or `circuit_breaker` concept -- that's middleware's job
5. **Test that presets apply correctly.** Use `.explain()` to verify the built agent has the expected model and callbacks

:::{seealso}
- [Callbacks](callbacks.md) -- per-agent callback attachment
- [Middleware](middleware.md) -- pipeline-wide cross-cutting concerns
- [Guards](guards.md) -- structured safety with the G module
- [Best Practices](best-practices.md) -- the "Callbacks vs. Middleware" decision tree
:::
