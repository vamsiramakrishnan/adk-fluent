# Module: `agent`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [BaseAgent](builder-BaseAgent) | Base class for all agents in Agent Development Kit. |
| [Agent](builder-Agent) | LLM-based Agent. |

(builder-BaseAgent)=
## BaseAgent

> Fluent builder for `google.adk.agents.base_agent.BaseAgent`

Base class for all agents in Agent Development Kit.

**Quick start:**

```python
from adk_fluent import BaseAgent

result = (
    BaseAgent("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
BaseAgent(name: str)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

### Methods

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Set the `description` field.

### Callbacks

#### `.after_agent(*fns: Callable) -> Self`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.after_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_agent_callback` only if `condition` is `True`.

#### `.before_agent(*fns: Callable) -> Self`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.before_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_agent_callback` only if `condition` is `True`.

### Terminal Methods

#### `.build() -> BaseAgent`

Resolve into a native ADK BaseAgent.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |

---

(builder-Agent)=
## Agent

> Fluent builder for `google.adk.agents.llm_agent.LlmAgent`

LLM-based Agent.

**Quick start:**

```python
from adk_fluent import Agent

result = (
    Agent("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
Agent(name: str)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

### Methods

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Set the `description` field.

#### `.global_instruct(value: Union[str, Callable[ReadonlyContext, Union[str, Awaitable[str]]]]) -> Self`

- **Maps to:** `global_instruction`
- Set the `global_instruction` field.

#### `.history(value: Literal[default, none]) -> Self`

- **Maps to:** `include_contents`
- Set the `include_contents` field.

#### `.instruct(value: Union[str, Callable[ReadonlyContext, Union[str, Awaitable[str]]]]) -> Self`

- **Maps to:** `instruction`
- Set the `instruction` field.

#### `.outputs(value: Union[str, NoneType]) -> Self`

- **Maps to:** `output_key`
- Set the `output_key` field.

#### `.static(value: Union[Content, str, File, Part, list[Union[str, File, Part]], NoneType]) -> Self`

- **Maps to:** `static_instruction`
- Set the `static_instruction` field.

### Callbacks

#### `.after_agent(*fns: Callable) -> Self`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.after_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_agent_callback` only if `condition` is `True`.

#### `.after_model(*fns: Callable) -> Self`

Append callback(s) to `after_model_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.after_model_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_model_callback` only if `condition` is `True`.

#### `.after_tool(*fns: Callable) -> Self`

Append callback(s) to `after_tool_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.after_tool_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_tool_callback` only if `condition` is `True`.

#### `.before_agent(*fns: Callable) -> Self`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.before_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_agent_callback` only if `condition` is `True`.

#### `.before_model(*fns: Callable) -> Self`

Append callback(s) to `before_model_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.before_model_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_model_callback` only if `condition` is `True`.

#### `.before_tool(*fns: Callable) -> Self`

Append callback(s) to `before_tool_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.before_tool_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_tool_callback` only if `condition` is `True`.

#### `.on_model_error(*fns: Callable) -> Self`

Append callback(s) to `on_model_error_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.on_model_error_if(condition: bool, fn: Callable) -> Self`

Append callback to `on_model_error_callback` only if `condition` is `True`.

#### `.on_tool_error(*fns: Callable) -> Self`

Append callback(s) to `on_tool_error_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list
rather than replacing previous callbacks.
:::

#### `.on_tool_error_if(condition: bool, fn: Callable) -> Self`

Append callback to `on_tool_error_callback` only if `condition` is `True`.

### Extra Methods

#### `.tool(fn_or_tool: Callable | BaseTool) -> Self`

Add a single tool. Alias for .tools() with append semantics.

#### `.apply(stack: MiddlewareStack) -> Self`

Apply a reusable middleware stack (bulk callback registration).

#### `.member(agent: BaseAgent | AgentBuilder) -> Self`

Add a member agent for coordinator pattern.

#### `.delegate(agent) -> Self`

Add an agent as a delegatable tool (wraps in AgentTool). The coordinator LLM can route to this agent.

#### `.guardrail(fn: Callable) -> Self`

Attach a guardrail function as both before_model and after_model callback.

#### `.ask(prompt: str) -> str`

One-shot execution. Build agent, send prompt, return response text.

#### `.ask_async(prompt: str) -> str`

Async one-shot execution.

#### `.stream(prompt: str) -> AsyncIterator[str]`

Streaming execution. Yields response text chunks.

#### `.test(prompt: str, *, contains: str | None = None, matches: str | None = None, equals: str | None = None) -> Self`

Run a smoke test. Calls .ask() internally, asserts output matches condition.

#### `.session()`

Create an interactive session context manager. Use with 'async with'.

#### `.map(prompts: list[str], *, concurrency: int = 5) -> list[str]`

Run agent against multiple prompts with bounded concurrency.

#### `.map_async(prompts: list[str], *, concurrency: int = 5) -> list[str]`

Async batch execution against multiple prompts.

#### `.events(prompt: str) -> AsyncIterator`

Stream raw ADK Event objects. Yields every event including state deltas and function calls.

### Terminal Methods

#### `.build() -> LlmAgent`

Resolve into a native ADK LlmAgent.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
| `.model(value)` | `Union[str, BaseLlm]` |
| `.tools(value)` | `list[Union[Callable, BaseTool, BaseToolset]]` |
| `.generate_content_config(value)` | `Union[GenerateContentConfig, NoneType]` |
| `.disallow_transfer_to_parent(value)` | `bool` |
| `.disallow_transfer_to_peers(value)` | `bool` |
| `.input_schema(value)` | `Union[type[BaseModel], NoneType]` |
| `.output_schema(value)` | `Union[type[BaseModel], NoneType]` |
| `.planner(value)` | `Union[BasePlanner, NoneType]` |
| `.code_executor(value)` | `Union[BaseCodeExecutor, NoneType]` |
