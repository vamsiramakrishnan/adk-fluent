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
| `name` | {py:class}`str` |

### Core Configuration

(method-Loop-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
loop = Loop("loop").describe("...")
```

(method-Loop-sub_agent)=
#### `.transfer_to(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
loop = Loop("loop").transfer_to("...")
```

### Configuration

(method-Loop-eval)=
#### `.eval(prompt: str, *, expect: str | None = None, criteria: Any | None = None) -> Any` {bdg-info}`Configuration`

Inline evaluation. Run a single eval case against this loop.

**Example:**

```python
loop = Loop("loop").eval("...")
```

(method-Loop-eval_suite)=
#### `.eval_suite() -> Any` {bdg-info}`Configuration`

Create an evaluation suite builder for this loop.

**Example:**

```python
loop = Loop("loop").eval_suite("...")
```

(method-Loop-to_ir)=
#### `.to_ir() -> Any` {bdg-info}`Configuration`

Convert this Loop builder to a LoopNode IR node.

**Example:**

```python
loop = Loop("loop").to_ir("...")
```

### Callbacks

(method-Loop-after_agent)=
#### `.after_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
loop = Loop("loop").after_agent(my_callback_fn)
```

(method-Loop-after_agent_if)=
#### `.after_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_agent_callback` only if `condition` is `True`.

**Example:**

```python
loop = Loop("loop").after_agent_if(condition, my_callback_fn)
```

(method-Loop-before_agent)=
#### `.before_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
loop = Loop("loop").before_agent(my_callback_fn)
```

(method-Loop-before_agent_if)=
#### `.before_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_agent_callback` only if `condition` is `True`.

**Example:**

```python
loop = Loop("loop").before_agent_if(condition, my_callback_fn)
```

### Control Flow & Execution

(method-Loop-build)=
#### `.build() -> LoopAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LoopAgent.

**Example:**

```python
loop = Loop("loop").build("...")
```

(method-Loop-step)=
#### `.step(value: BaseAgent) -> Self` {bdg-primary}`Control Flow & Execution`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
loop = Loop("loop").step("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
| `.max_iterations(value)` | `int | None` |

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
| `name` | {py:class}`str` |

### Core Configuration

(method-FanOut-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
fanout = FanOut("fanout").describe("...")
```

(method-FanOut-sub_agent)=
#### `.transfer_to(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
fanout = FanOut("fanout").transfer_to("...")
```

### Configuration

(method-FanOut-eval)=
#### `.eval(prompt: str, *, expect: str | None = None, criteria: Any | None = None) -> Any` {bdg-info}`Configuration`

Inline evaluation. Run a single eval case against this fan-out.

**Example:**

```python
fanout = FanOut("fanout").eval("...")
```

(method-FanOut-eval_suite)=
#### `.eval_suite() -> Any` {bdg-info}`Configuration`

Create an evaluation suite builder for this fan-out.

**Example:**

```python
fanout = FanOut("fanout").eval_suite("...")
```

(method-FanOut-to_ir)=
#### `.to_ir() -> Any` {bdg-info}`Configuration`

Convert this FanOut builder to a ParallelNode IR node.

**Example:**

```python
fanout = FanOut("fanout").to_ir("...")
```

### Callbacks

(method-FanOut-after_agent)=
#### `.after_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
fanout = FanOut("fanout").after_agent(my_callback_fn)
```

(method-FanOut-after_agent_if)=
#### `.after_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_agent_callback` only if `condition` is `True`.

**Example:**

```python
fanout = FanOut("fanout").after_agent_if(condition, my_callback_fn)
```

(method-FanOut-before_agent)=
#### `.before_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
fanout = FanOut("fanout").before_agent(my_callback_fn)
```

(method-FanOut-before_agent_if)=
#### `.before_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_agent_callback` only if `condition` is `True`.

**Example:**

```python
fanout = FanOut("fanout").before_agent_if(condition, my_callback_fn)
```

### Control Flow & Execution

(method-FanOut-branch)=
#### `.branch(value: BaseAgent) -> Self` {bdg-primary}`Control Flow & Execution`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
fanout = FanOut("fanout").branch("...")
```

(method-FanOut-build)=
#### `.build() -> ParallelAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ParallelAgent.

**Example:**

```python
fanout = FanOut("fanout").build("...")
```

(method-FanOut-step)=
#### `.step(value: BaseAgent) -> Self` {bdg-primary}`Control Flow & Execution`

Alias for .branch() — consistent API across workflow builders.

**Example:**

```python
fanout = FanOut("fanout").step("...")
```

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
| `name` | {py:class}`str` |

### Core Configuration

(method-Pipeline-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
pipeline = Pipeline("pipeline").describe("...")
```

(method-Pipeline-sub_agent)=
#### `.transfer_to(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
pipeline = Pipeline("pipeline").transfer_to("...")
```

### Configuration

(method-Pipeline-eval)=
#### `.eval(prompt: str, *, expect: str | None = None, criteria: Any | None = None) -> Any` {bdg-info}`Configuration`

Inline evaluation. Run a single eval case against this pipeline.

**Example:**

```python
pipeline = Pipeline("pipeline").eval("...")
```

(method-Pipeline-eval_suite)=
#### `.eval_suite() -> Any` {bdg-info}`Configuration`

Create an evaluation suite builder for this pipeline.

**Example:**

```python
pipeline = Pipeline("pipeline").eval_suite("...")
```

(method-Pipeline-to_ir)=
#### `.to_ir() -> Any` {bdg-info}`Configuration`

Convert this Pipeline builder to a SequenceNode IR node.

**Example:**

```python
pipeline = Pipeline("pipeline").to_ir("...")
```

### Callbacks

(method-Pipeline-after_agent)=
#### `.after_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
pipeline = Pipeline("pipeline").after_agent(my_callback_fn)
```

(method-Pipeline-after_agent_if)=
#### `.after_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_agent_callback` only if `condition` is `True`.

**Example:**

```python
pipeline = Pipeline("pipeline").after_agent_if(condition, my_callback_fn)
```

(method-Pipeline-before_agent)=
#### `.before_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
pipeline = Pipeline("pipeline").before_agent(my_callback_fn)
```

(method-Pipeline-before_agent_if)=
#### `.before_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_agent_callback` only if `condition` is `True`.

**Example:**

```python
pipeline = Pipeline("pipeline").before_agent_if(condition, my_callback_fn)
```

### Control Flow & Execution

(method-Pipeline-build)=
#### `.build() -> SequentialAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SequentialAgent.

**Example:**

```python
pipeline = Pipeline("pipeline").build("...")
```

(method-Pipeline-step)=
#### `.step(value: BaseAgent) -> Self` {bdg-primary}`Control Flow & Execution`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
pipeline = Pipeline("pipeline").step("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
