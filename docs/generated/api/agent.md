# Module: `agent`

# BaseAgent

> Fluent builder for `google.adk.agents.base_agent.BaseAgent`

Base class for all agents in Agent Development Kit.

## Constructor

```python
BaseAgent(name)
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

## Terminal Methods

### `.build() -> BaseAgent`

Resolve into a native ADK BaseAgent.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |

---

# Agent

> Fluent builder for `google.adk.agents.llm_agent.LlmAgent`

LLM-based Agent.

## Constructor

```python
Agent(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Set the `description` field.

### `.global_instruct(value)`

- **Type:** `Union[str, Callable[ReadonlyContext, Union[str, Awaitable[str]]]]`
- **Maps to:** `global_instruction`
- Set the `global_instruction` field.

### `.instruct(value)`

- **Type:** `Union[str, Callable[ReadonlyContext, Union[str, Awaitable[str]]]]`
- **Maps to:** `instruction`
- Set the `instruction` field.

## Callbacks

### `.after_agent(*fns)`

Append callback(s) to `after_agent_callback`. Multiple calls accumulate.

### `.after_agent_if(condition, fn)`

Append callback to `after_agent_callback` only if `condition` is `True`.

### `.after_model(*fns)`

Append callback(s) to `after_model_callback`. Multiple calls accumulate.

### `.after_model_if(condition, fn)`

Append callback to `after_model_callback` only if `condition` is `True`.

### `.after_tool(*fns)`

Append callback(s) to `after_tool_callback`. Multiple calls accumulate.

### `.after_tool_if(condition, fn)`

Append callback to `after_tool_callback` only if `condition` is `True`.

### `.before_agent(*fns)`

Append callback(s) to `before_agent_callback`. Multiple calls accumulate.

### `.before_agent_if(condition, fn)`

Append callback to `before_agent_callback` only if `condition` is `True`.

### `.before_model(*fns)`

Append callback(s) to `before_model_callback`. Multiple calls accumulate.

### `.before_model_if(condition, fn)`

Append callback to `before_model_callback` only if `condition` is `True`.

### `.before_tool(*fns)`

Append callback(s) to `before_tool_callback`. Multiple calls accumulate.

### `.before_tool_if(condition, fn)`

Append callback to `before_tool_callback` only if `condition` is `True`.

### `.on_model_error(*fns)`

Append callback(s) to `on_model_error_callback`. Multiple calls accumulate.

### `.on_model_error_if(condition, fn)`

Append callback to `on_model_error_callback` only if `condition` is `True`.

### `.on_tool_error(*fns)`

Append callback(s) to `on_tool_error_callback`. Multiple calls accumulate.

### `.on_tool_error_if(condition, fn)`

Append callback to `on_tool_error_callback` only if `condition` is `True`.

## Extra Methods

### `.tool(fn_or_tool: Callable | BaseTool) -> Self`

Add a single tool. Alias for .tools() with append semantics.

### `.apply(stack: MiddlewareStack) -> Self`

Apply a reusable middleware stack (bulk callback registration).

### `.member(agent: BaseAgent | AgentBuilder) -> Self`

Add a member agent for coordinator pattern.

### `.guardrail(fn: Callable) -> Self`

Attach a guardrail function as both before_model and after_model callback.

### `.clone(new_name: str) -> Self`

Deep-copy this builder with a new name. Independent config/callbacks/lists.

### `.ask(prompt: str) -> str`

One-shot execution. Build agent, send prompt, return response text.

### `.ask_async(prompt: str) -> str`

Async one-shot execution.

### `.stream(prompt: str) -> AsyncIterator[str]`

Streaming execution. Yields response text chunks.

### `.test(prompt: str, *, contains: str | None = None, matches: str | None = None, equals: str | None = None) -> Self`

Run a smoke test. Calls .ask() internally, asserts output matches condition.

### `.session()`

Create an interactive session context manager. Use with 'async with'.

## Terminal Methods

### `.build() -> LlmAgent`

Resolve into a native ADK LlmAgent.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
| `.model(value)` | `Union[str, BaseLlm]` |
| `.static_instruction(value)` | `Union[Content, str, File, Part, list[Union[str, File, Part]], NoneType]` |
| `.tools(value)` | `list[Union[Callable, BaseTool, BaseToolset]]` |
| `.generate_content_config(value)` | `Union[GenerateContentConfig, NoneType]` |
| `.disallow_transfer_to_parent(value)` | `bool` |
| `.disallow_transfer_to_peers(value)` | `bool` |
| `.include_contents(value)` | `Literal[default, none]` |
| `.input_schema(value)` | `Union[type[BaseModel], NoneType]` |
| `.output_schema(value)` | `Union[type[BaseModel], NoneType]` |
| `.output_key(value)` | `Union[str, NoneType]` |
| `.planner(value)` | `Union[BasePlanner, NoneType]` |
| `.code_executor(value)` | `Union[BaseCodeExecutor, NoneType]` |
