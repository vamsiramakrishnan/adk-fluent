# Module: `workflow`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [Loop](builder-Loop) | A shell agent that run its sub-agents in a loop. |
| [FanOut](builder-FanOut) | A shell agent that runs its sub-agents in parallel in an isolated manner. |
| [Pipeline](builder-Pipeline) | A shell agent that runs its sub-agents in sequence. |

(builder-Loop)=
## Loop

> Fluent builder for `google.adk.agents.loop_agent.LoopAgent`

A shell agent that run its sub-agents in a loop.

**Quick start:**

```python
from adk_fluent import Loop

result = (
    Loop("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
Loop(name: str)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Set the `description` field.

#### `.sub_agent(value: BaseAgent) -> Self`

Append to ``sub_agents`` (lazy — built at .build() time).

### Configuration

#### `.to_ir()`

Convert this Loop builder to a LoopNode IR node.

### Callbacks

#### `.after_agent(*fns: Callable) -> Self`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.after_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_agent_callback` only if `condition` is `True`.

#### `.before_agent(*fns: Callable) -> Self`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.before_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_agent_callback` only if `condition` is `True`.

### Control Flow & Execution

#### `.build() -> LoopAgent`

Resolve into a native ADK LoopAgent.

#### `.step(value: BaseAgent) -> Self`

Append to ``sub_agents`` (lazy — built at .build() time).

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
| `.max_iterations(value)` | `Union[int, NoneType]` |

---

(builder-FanOut)=
## FanOut

> Fluent builder for `google.adk.agents.parallel_agent.ParallelAgent`

A shell agent that runs its sub-agents in parallel in an isolated manner.

**Quick start:**

```python
from adk_fluent import FanOut

result = (
    FanOut("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
FanOut(name: str)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Set the `description` field.

#### `.sub_agent(value: BaseAgent) -> Self`

Append to ``sub_agents`` (lazy — built at .build() time).

### Configuration

#### `.to_ir()`

Convert this FanOut builder to a ParallelNode IR node.

### Callbacks

#### `.after_agent(*fns: Callable) -> Self`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.after_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_agent_callback` only if `condition` is `True`.

#### `.before_agent(*fns: Callable) -> Self`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.before_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_agent_callback` only if `condition` is `True`.

### Control Flow & Execution

#### `.branch(value: BaseAgent) -> Self`

Append to ``sub_agents`` (lazy — built at .build() time).

#### `.build() -> ParallelAgent`

Resolve into a native ADK ParallelAgent.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |

---

(builder-Pipeline)=
## Pipeline

> Fluent builder for `google.adk.agents.sequential_agent.SequentialAgent`

A shell agent that runs its sub-agents in sequence.

**Quick start:**

```python
from adk_fluent import Pipeline

result = (
    Pipeline("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
Pipeline(name: str)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Set the `description` field.

#### `.sub_agent(value: BaseAgent) -> Self`

Append to ``sub_agents`` (lazy — built at .build() time).

### Configuration

#### `.to_ir()`

Convert this Pipeline builder to a SequenceNode IR node.

### Callbacks

#### `.after_agent(*fns: Callable) -> Self`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.after_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_agent_callback` only if `condition` is `True`.

#### `.before_agent(*fns: Callable) -> Self`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.before_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_agent_callback` only if `condition` is `True`.

### Control Flow & Execution

#### `.build() -> SequentialAgent`

Resolve into a native ADK SequentialAgent.

#### `.step(value: BaseAgent) -> Self`

Append to ``sub_agents`` (lazy — built at .build() time).

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
