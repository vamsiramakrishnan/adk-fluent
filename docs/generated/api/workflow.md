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
#### `.sub_agent(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
loop = Loop("loop").sub_agent("...")
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

(method-Loop-ask)=
#### `.ask(prompt: str) -> str` {bdg-primary}`Control Flow & Execution`

One-shot SYNC execution (blocking). Builds loop, sends prompt, returns response text.

**Example:**

```python
loop = Loop("loop").ask("...")
```

(method-Loop-ask_async)=
#### `.ask_async(prompt: str) -> str` {bdg-primary}`Control Flow & Execution`

One-shot ASYNC execution (non-blocking, use with await).

**Example:**

```python
loop = Loop("loop").ask_async("...")
```

(method-Loop-build)=
#### `.build() -> LoopAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LoopAgent.

**Example:**

```python
loop = Loop("loop").build("...")
```

(method-Loop-events)=
#### `.events(prompt: str) -> AsyncIterator[Any]` {bdg-primary}`Control Flow & Execution`

Stream raw ADK Event objects. Yields every event including state deltas and function calls.

**Example:**

```python
loop = Loop("loop").events("...")
```

(method-Loop-map)=
#### `.map(prompts: list[str], *, concurrency: int = 5) -> list[str]` {bdg-primary}`Control Flow & Execution`

Batch SYNC execution (blocking). Run loop against multiple prompts with bounded concurrency.

**Example:**

```python
loop = Loop("loop").map("...")
```

(method-Loop-map_async)=
#### `.map_async(prompts: list[str], *, concurrency: int = 5) -> list[str]` {bdg-primary}`Control Flow & Execution`

Batch ASYNC execution (non-blocking, use with await).

**Example:**

```python
loop = Loop("loop").map_async("...")
```

(method-Loop-session)=
#### `.session() -> Any` {bdg-primary}`Control Flow & Execution`

Create an interactive multi-turn chat session. Returns an async context manager.

**Example:**

```python
loop = Loop("loop").session("...")
```

(method-Loop-step)=
#### `.step(value: BaseAgent) -> Self` {bdg-primary}`Control Flow & Execution`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
loop = Loop("loop").step("...")
```

(method-Loop-stream)=
#### `.stream(prompt: str) -> AsyncIterator[str]` {bdg-primary}`Control Flow & Execution`

ASYNC streaming execution. Yields response text chunks as they arrive.

**Example:**

```python
loop = Loop("loop").stream("...")
```

(method-Loop-test)=
#### `.test(prompt: str, *, contains: str | None = None, matches: str | None = None, equals: str | None = None) -> Self` {bdg-primary}`Control Flow & Execution`

Run a smoke test. Calls .ask() internally, asserts output matches condition.

**Example:**

```python
loop = Loop("loop").test("...")
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
#### `.sub_agent(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
fanout = FanOut("fanout").sub_agent("...")
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

(method-FanOut-ask)=
#### `.ask(prompt: str) -> str` {bdg-primary}`Control Flow & Execution`

One-shot SYNC execution (blocking). Builds fan-out, sends prompt, returns response text.

**Example:**

```python
fanout = FanOut("fanout").ask("...")
```

(method-FanOut-ask_async)=
#### `.ask_async(prompt: str) -> str` {bdg-primary}`Control Flow & Execution`

One-shot ASYNC execution (non-blocking, use with await).

**Example:**

```python
fanout = FanOut("fanout").ask_async("...")
```

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

(method-FanOut-events)=
#### `.events(prompt: str) -> AsyncIterator[Any]` {bdg-primary}`Control Flow & Execution`

Stream raw ADK Event objects. Yields every event including state deltas and function calls.

**Example:**

```python
fanout = FanOut("fanout").events("...")
```

(method-FanOut-map)=
#### `.map(prompts: list[str], *, concurrency: int = 5) -> list[str]` {bdg-primary}`Control Flow & Execution`

Batch SYNC execution (blocking). Run fan-out against multiple prompts with bounded concurrency.

**Example:**

```python
fanout = FanOut("fanout").map("...")
```

(method-FanOut-map_async)=
#### `.map_async(prompts: list[str], *, concurrency: int = 5) -> list[str]` {bdg-primary}`Control Flow & Execution`

Batch ASYNC execution (non-blocking, use with await).

**Example:**

```python
fanout = FanOut("fanout").map_async("...")
```

(method-FanOut-session)=
#### `.session() -> Any` {bdg-primary}`Control Flow & Execution`

Create an interactive multi-turn chat session. Returns an async context manager.

**Example:**

```python
fanout = FanOut("fanout").session("...")
```

(method-FanOut-step)=
#### `.step(value: BaseAgent) -> Self` {bdg-primary}`Control Flow & Execution`

Alias for .branch() — consistent API across workflow builders.

**Example:**

```python
fanout = FanOut("fanout").step("...")
```

(method-FanOut-stream)=
#### `.stream(prompt: str) -> AsyncIterator[str]` {bdg-primary}`Control Flow & Execution`

ASYNC streaming execution. Yields response text chunks as they arrive.

**Example:**

```python
fanout = FanOut("fanout").stream("...")
```

(method-FanOut-test)=
#### `.test(prompt: str, *, contains: str | None = None, matches: str | None = None, equals: str | None = None) -> Self` {bdg-primary}`Control Flow & Execution`

Run a smoke test. Calls .ask() internally, asserts output matches condition.

**Example:**

```python
fanout = FanOut("fanout").test("...")
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
#### `.sub_agent(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
pipeline = Pipeline("pipeline").sub_agent("...")
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

(method-Pipeline-ask)=
#### `.ask(prompt: str) -> str` {bdg-primary}`Control Flow & Execution`

One-shot SYNC execution (blocking). Builds pipeline, sends prompt, returns response text.

**Example:**

```python
pipeline = Pipeline("pipeline").ask("...")
```

(method-Pipeline-ask_async)=
#### `.ask_async(prompt: str) -> str` {bdg-primary}`Control Flow & Execution`

One-shot ASYNC execution (non-blocking, use with await).

**Example:**

```python
pipeline = Pipeline("pipeline").ask_async("...")
```

(method-Pipeline-build)=
#### `.build() -> SequentialAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SequentialAgent.

**Example:**

```python
pipeline = Pipeline("pipeline").build("...")
```

(method-Pipeline-events)=
#### `.events(prompt: str) -> AsyncIterator[Any]` {bdg-primary}`Control Flow & Execution`

Stream raw ADK Event objects. Yields every event including state deltas and function calls.

**Example:**

```python
pipeline = Pipeline("pipeline").events("...")
```

(method-Pipeline-map)=
#### `.map(prompts: list[str], *, concurrency: int = 5) -> list[str]` {bdg-primary}`Control Flow & Execution`

Batch SYNC execution (blocking). Run pipeline against multiple prompts with bounded concurrency.

**Example:**

```python
pipeline = Pipeline("pipeline").map("...")
```

(method-Pipeline-map_async)=
#### `.map_async(prompts: list[str], *, concurrency: int = 5) -> list[str]` {bdg-primary}`Control Flow & Execution`

Batch ASYNC execution (non-blocking, use with await).

**Example:**

```python
pipeline = Pipeline("pipeline").map_async("...")
```

(method-Pipeline-session)=
#### `.session() -> Any` {bdg-primary}`Control Flow & Execution`

Create an interactive multi-turn chat session. Returns an async context manager.

**Example:**

```python
pipeline = Pipeline("pipeline").session("...")
```

(method-Pipeline-step)=
#### `.step(value: BaseAgent) -> Self` {bdg-primary}`Control Flow & Execution`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
pipeline = Pipeline("pipeline").step("...")
```

(method-Pipeline-stream)=
#### `.stream(prompt: str) -> AsyncIterator[str]` {bdg-primary}`Control Flow & Execution`

ASYNC streaming execution. Yields response text chunks as they arrive.

**Example:**

```python
pipeline = Pipeline("pipeline").stream("...")
```

(method-Pipeline-test)=
#### `.test(prompt: str, *, contains: str | None = None, matches: str | None = None, equals: str | None = None) -> Self` {bdg-primary}`Control Flow & Execution`

Run a smoke test. Calls .ask() internally, asserts output matches condition.

**Example:**

```python
pipeline = Pipeline("pipeline").test("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
