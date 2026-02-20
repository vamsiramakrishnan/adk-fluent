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

#### `.include_history(value: Literal[default, none]) -> Self`

- **Maps to:** `include_contents`
- Set the `include_contents` field.

#### `.instruct(value: Union[str, Callable[ReadonlyContext, Union[str, Awaitable[str]]]]) -> Self`

- **Maps to:** `instruction`
- Set the `instruction` field.

#### `.outputs(value: Union[str, NoneType]) -> Self`

- **Maps to:** `output_key`
- Session state key where the agent's response text is stored. Downstream agents and state transforms can read this key. Alias: ``.outputs(key)``.

#### `.static(value: Union[Content, str, Image, File, Part, list[Union[str, Image, File, Part]], NoneType]) -> Self`

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

#### `.apply(stack: MiddlewareStack) -> Self`

Apply a reusable middleware stack (bulk callback registration).

#### `.sub_agent(agent: BaseAgent | AgentBuilder) -> Self`

Add a sub-agent (appends). Multiple .sub_agent() calls accumulate.

#### `.member(agent: BaseAgent | AgentBuilder) -> Self`

Deprecated: use .sub_agent() instead. Add a sub-agent for coordinator pattern.

#### `.delegate(agent) -> Self`

Add an agent as a delegatable tool (wraps in AgentTool). The coordinator LLM can route to this agent.

#### `.tool(fn_or_tool, *, require_confirmation: bool = False) -> Self`

Add a single tool (appends). Wraps plain callables in FunctionTool when require_confirmation=True.

**Example:**

```python
def search(query: str) -> str:
    """Search the web."""
    return f"Results for {query}"

agent = Agent("helper").tool(search).build()
```

**See also:** `FunctionTool`, `Agent.guardrail`

#### `.guardrail(fn: Callable) -> Self`

Attach a guardrail function as both before_model and after_model callback.

**Example:**

```python
def safety_check(callback_context, llm_request, llm_response, agent):
    if "unsafe" in str(llm_response):
        return None  # Block response
    return llm_response

agent = Agent("safe", "gemini-2.5-flash").guardrail(safety_check).build()
```

**See also:** `Agent.before_model`, `Agent.after_model`

#### `.ask(prompt: str) -> str`

One-shot execution. Build agent, send prompt, return response text.

**Example:**

```python
reply = Agent("qa", "gemini-2.5-flash").instruct("Answer questions.").ask("What is Python?")
print(reply)
```

**See also:** `Agent.ask_async`, `Agent.stream`

#### `.ask_async(prompt: str) -> str`

Async one-shot execution.

#### `.stream(prompt: str) -> AsyncIterator[str]`

Streaming execution. Yields response text chunks.

**Example:**

```python
async for chunk in Agent("writer", "gemini-2.5-flash").instruct("Write a poem.").stream("About the sea"):
    print(chunk, end="")
```

**See also:** `Agent.ask`, `Agent.events`

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

#### `.context(spec: Any) -> Self`

Declare what conversation context this agent should see. Accepts a C module transform (C.none(), C.user_only(), C.from_state(), etc.).

**Example:**

```python
from adk_fluent import C

agent = (
    Agent("writer")
    .model("gemini-2.5-flash")
    .instruct("Write about {topic}.")
    .context(C.from_state("topic"))
    .build()
)
```

**See also:** `C`, `Agent.memory`

#### `.show() -> Self`

Force this agent's events to be user-facing (override topology inference).

**Example:**

```python
# Force intermediate agent output to be visible to users
agent = Agent("logger").model("m").instruct("Log progress.").show()
```

**See also:** `Agent.hide`

#### `.hide() -> Self`

Force this agent's events to be internal (override topology inference).

**Example:**

```python
# Suppress terminal agent output from user view
agent = Agent("cleanup").model("m").instruct("Clean up.").hide()
```

**See also:** `Agent.show`

#### `.memory(mode: str = 'preload') -> Self`

Add memory tools to this agent. Modes: 'preload', 'on_demand', 'both'.

**Example:**

```python
agent = Agent("assistant", "gemini-2.5-flash").memory("preload").build()
```

**See also:** `Agent.memory_auto_save`, `Agent.context`

#### `.memory_auto_save() -> Self`

Auto-save session to memory after each agent run.

#### `.isolate() -> Self`

Prevent this agent from transferring to parent or peers. Sets both disallow_transfer_to_parent and disallow_transfer_to_peers to True. Use for specialist agents that should complete their task and return.

**Example:**

```python
# Specialist agent that completes its task without transferring
specialist = (
    Agent("invoice_parser", "gemini-2.5-flash")
    .instruct("Parse the invoice and extract line items.")
    .isolate()
    .output_schema(Invoice)
    .build()
)
```

**See also:** `Agent.disallow_transfer_to_parent`, `Agent.disallow_transfer_to_peers`

#### `.to_ir()`

Convert this Agent builder to an AgentNode IR node.

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
