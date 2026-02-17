# Module: `workflow`

# Loop

> Fluent builder for `google.adk.agents.loop_agent.LoopAgent`

A shell agent that run its sub-agents in a loop.

## Constructor

```python
Loop(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Set the `description` field.

## Callbacks

### `.after_agent(*fns)`

Append callback(s) to `after_agent_callback`. Multiple calls accumulate.

### `.after_agent_if(condition, fn)`

Append callback to `after_agent_callback` only if `condition` is `True`.

### `.before_agent(*fns)`

Append callback(s) to `before_agent_callback`. Multiple calls accumulate.

### `.before_agent_if(condition, fn)`

Append callback to `before_agent_callback` only if `condition` is `True`.

## Extra Methods

### `.step(agent: BaseAgent | AgentBuilder) -> Self`

Append an agent as the next step.

### `.clone(new_name: str) -> Self`

Deep-copy this builder with a new name.

## Terminal Methods

### `.build() -> LoopAgent`

Resolve into a native ADK LoopAgent.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
| `.max_iterations(value)` | `Union[int, NoneType]` |

---

# FanOut

> Fluent builder for `google.adk.agents.parallel_agent.ParallelAgent`

A shell agent that runs its sub-agents in parallel in an isolated manner.

## Constructor

```python
FanOut(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Set the `description` field.

## Callbacks

### `.after_agent(*fns)`

Append callback(s) to `after_agent_callback`. Multiple calls accumulate.

### `.after_agent_if(condition, fn)`

Append callback to `after_agent_callback` only if `condition` is `True`.

### `.before_agent(*fns)`

Append callback(s) to `before_agent_callback`. Multiple calls accumulate.

### `.before_agent_if(condition, fn)`

Append callback to `before_agent_callback` only if `condition` is `True`.

## Extra Methods

### `.branch(agent: BaseAgent | AgentBuilder) -> Self`

Add a parallel branch agent.

### `.clone(new_name: str) -> Self`

Deep-copy this builder with a new name.

## Terminal Methods

### `.build() -> ParallelAgent`

Resolve into a native ADK ParallelAgent.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |

---

# Pipeline

> Fluent builder for `google.adk.agents.sequential_agent.SequentialAgent`

A shell agent that runs its sub-agents in sequence.

## Constructor

```python
Pipeline(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Set the `description` field.

## Callbacks

### `.after_agent(*fns)`

Append callback(s) to `after_agent_callback`. Multiple calls accumulate.

### `.after_agent_if(condition, fn)`

Append callback to `after_agent_callback` only if `condition` is `True`.

### `.before_agent(*fns)`

Append callback(s) to `before_agent_callback`. Multiple calls accumulate.

### `.before_agent_if(condition, fn)`

Append callback to `before_agent_callback` only if `condition` is `True`.

## Extra Methods

### `.step(agent: BaseAgent | AgentBuilder) -> Self`

Append an agent as the next step.

### `.clone(new_name: str) -> Self`

Deep-copy this builder with a new name.

## Terminal Methods

### `.build() -> SequentialAgent`

Resolve into a native ADK SequentialAgent.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
