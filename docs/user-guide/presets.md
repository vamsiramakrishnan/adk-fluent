# Presets

Presets are reusable configuration bundles that can be applied to any builder via `.use()`.

## Basic Usage

```python
from adk_fluent import Agent
from adk_fluent.presets import Preset

production = Preset(model="gemini-2.5-flash", before_model=log_fn, after_model=audit_fn)

agent = Agent("service").instruct("Handle requests.").use(production).build()
```

## How Presets Work

A `Preset` accepts keyword arguments that map to builder fields. Fields are classified into two categories:

- **Config values** -- plain configuration like `model`, `instruction`, `description`, `output_key`, `include_contents`, `max_iterations`, etc. These are applied directly to the builder.
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
