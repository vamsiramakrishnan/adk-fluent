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
| `name` | {py:class}`str` |

### Core Configuration

#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set the `description` field.

**Example:**

```python
agent = BaseAgent("agent").describe("...")
```

#### `.sub_agent(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
agent = BaseAgent("agent").sub_agent("...")
```

### Callbacks

#### `.after_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = BaseAgent("agent").after_agent(my_callback_fn)
```

#### `.after_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_agent_callback` only if `condition` is `True`.

**Example:**

```python
agent = BaseAgent("agent").after_agent_if(condition, my_callback_fn)
```

#### `.before_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = BaseAgent("agent").before_agent(my_callback_fn)
```

#### `.before_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_agent_callback` only if `condition` is `True`.

**Example:**

```python
agent = BaseAgent("agent").before_agent_if(condition, my_callback_fn)
```

### Control Flow & Execution

#### `.build() -> BaseAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseAgent.

**Example:**

```python
agent = BaseAgent("agent").build("...")
```

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
| `name` | {py:class}`str` |

### Core Configuration

#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set the `description` field.

**Example:**

```python
agent = Agent("agent").describe("...")
```

#### `.global_instruct(value: str | Callable[[ReadonlyContext], str | Awaitable[str]]) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `global_instruction`
- Set the `global_instruction` field.

**Example:**

```python
agent = Agent("agent").global_instruct("...")
```

#### `.instruct(value: str | Callable[[ReadonlyContext], str | Awaitable[str]]) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `instruction`
- Set the `instruction` field.

**Example:**

```python
agent = Agent("agent").instruct("You are a helpful assistant.")
```

#### `.static(value: Content | str | File | Part | list[str | File | Part] | None) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `static_instruction`
- Set the `static_instruction` field.

**Example:**

```python
agent = Agent("agent").static("You are a helpful assistant.")
```

#### `.sub_agent(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
agent = Agent("agent").sub_agent("...")
```

#### `.tool(fn_or_tool: Any, *, require_confirmation: bool = False) -> Self` {bdg-success}`Core Configuration`

Add a single tool (appends). Wraps plain callables in FunctionTool when require_confirmation=True.

**See also:** `FunctionTool`, `Agent.guard`

**Example:**

```python
def search(query: str) -> str:
    """Search the web."""
    return f"Results for {query}"

agent = Agent("helper").tool(search).build()
```

### Configuration

#### `.agent_tool(agent: Any) -> Self` {bdg-info}`Configuration`

Wrap an agent as a callable tool (AgentTool) and add it to this agent's tools. The LLM can invoke the wrapped agent by name.

**See also:** `Agent.tool`, `Agent.isolate`

**Example:**

```python
specialist = Agent("invoice_parser", "gemini-2.5-flash").instruct("Parse invoices.")
coordinator = (
    Agent("router", "gemini-2.5-flash")
    .instruct("Route tasks to specialists.")
    .agent_tool(specialist)
    .build()
)
```

#### `.artifact_schema(schema: type) -> Self` {bdg-info}`Configuration`

Attach an ArtifactSchema declaring artifact dependencies.

**See also:** `ArtifactSchema`, `Produces`, `Consumes`

**Example:**

```python
Agent("researcher").artifact_schema(ResearchArtifacts)
```

#### `.artifacts(*transforms: Any) -> Self` {bdg-info}`Configuration`

Attach artifact operations (A.publish, A.snapshot, etc.) that fire after this agent completes.

**See also:** `A`, `ATransform`

**Example:**

```python
Agent("writer").artifacts(A.publish("report.md", from_key="output"))
```

#### `.callback_schema(schema: type) -> Self` {bdg-info}`Configuration`

Attach a CallbackSchema declaring callback state dependencies.

**Example:**

```python
agent = Agent("agent").callback_schema(my_callback_fn)
```

#### `.context(spec: Any) -> Self` {bdg-info}`Configuration`

Declare what conversation context this agent should see. Accepts a C module transform (C.none(), C.user_only(), C.from_state(), etc.).

**See also:** `C`, `Agent.memory`

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

#### `.guard(fn: Callable[..., Any]) -> Self` {bdg-info}`Configuration`

Attach a guard function as both before_model and after_model callback. Runs before the LLM call and after the LLM response.

**See also:** `Agent.before_model`, `Agent.after_model`

**Example:**

```python
def safety_check(callback_context, llm_request, llm_response, agent):
    if "unsafe" in str(llm_response):
        return None  # Block response
    return llm_response

agent = Agent("safe", "gemini-2.5-flash").guard(safety_check).build()
```

#### `.hide() -> Self` {bdg-info}`Configuration`

Force this agent's events to be internal (override topology inference).

**See also:** `Agent.show`

**Example:**

```python
# Suppress terminal agent output from user view
agent = Agent("cleanup").model("m").instruct("Clean up.").hide()
```

#### `.memory(mode: str = 'preload') -> Self` {bdg-info}`Configuration`

Add memory tools to this agent. Modes: 'preload', 'on_demand', 'both'.

**See also:** `Agent.memory_auto_save`, `Agent.context`

**Example:**

```python
agent = Agent("assistant", "gemini-2.5-flash").memory("preload").build()
```

#### `.memory_auto_save() -> Self` {bdg-info}`Configuration`

Auto-save session to memory after each agent run.

**Example:**

```python
agent = Agent("agent").memory_auto_save("...")
```

#### `.no_peers() -> Self` {bdg-info}`Configuration`

Prevent this agent from transferring to sibling agents. The agent can still return to its parent.

**See also:** `Agent.isolate`, `Agent.stay`

**Example:**

```python
focused = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic thoroughly.")
    .no_peers()  # Don't hand off to sibling agents
    .build()
)
```

#### `.prompt_schema(schema: type) -> Self` {bdg-info}`Configuration`

Attach a PromptSchema declaring prompt state dependencies.

**Example:**

```python
agent = Agent("agent").prompt_schema("...")
```

#### `.show() -> Self` {bdg-info}`Configuration`

Force this agent's events to be user-facing (override topology inference).

**See also:** `Agent.hide`

**Example:**

```python
# Force intermediate agent output to be visible to users
agent = Agent("logger").model("m").instruct("Log progress.").show()
```

#### `.stay() -> Self` {bdg-info}`Configuration`

Prevent this agent from transferring back to its parent. Use for agents that should complete their work before returning.

**See also:** `Agent.isolate`, `Agent.no_peers`

**Example:**

```python
specialist = (
    Agent("invoice_parser", "gemini-2.5-flash")
    .instruct("Parse the invoice.")
    .stay()  # Must finish before returning to coordinator
    .build()
)
```

#### `.to_ir() -> Any` {bdg-info}`Configuration`

Convert this Agent builder to an AgentNode IR node.

**Example:**

```python
agent = Agent("agent").to_ir("...")
```

#### `.tool_schema(schema: type) -> Self` {bdg-info}`Configuration`

Attach a ToolSchema declaring tool state dependencies.

**Example:**

```python
agent = Agent("agent").tool_schema("...")
```

#### `.tools(value: Any) -> Self` {bdg-info}`Configuration`

Set tools. Accepts a list, a TComposite chain (T.fn(x) | T.fn(y)), or a single tool/toolset.

**Example:**

```python
agent = Agent("agent").tools("...")
```

### Callbacks

#### `.after_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").after_agent(my_callback_fn)
```

#### `.after_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_agent_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").after_agent_if(condition, my_callback_fn)
```

#### `.after_model(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_model_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").after_model(my_callback_fn)
```

#### `.after_model_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_model_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").after_model_if(condition, my_callback_fn)
```

#### `.after_tool(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_tool_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").after_tool(my_callback_fn)
```

#### `.after_tool_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_tool_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").after_tool_if(condition, my_callback_fn)
```

#### `.before_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").before_agent(my_callback_fn)
```

#### `.before_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_agent_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").before_agent_if(condition, my_callback_fn)
```

#### `.before_model(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_model_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").before_model(my_callback_fn)
```

#### `.before_model_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_model_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").before_model_if(condition, my_callback_fn)
```

#### `.before_tool(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_tool_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").before_tool(my_callback_fn)
```

#### `.before_tool_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_tool_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").before_tool_if(condition, my_callback_fn)
```

#### `.on_model_error(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `on_model_error_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").on_model_error(my_callback_fn)
```

#### `.on_model_error_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `on_model_error_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").on_model_error_if(condition, my_callback_fn)
```

#### `.on_tool_error(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `on_tool_error_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").on_tool_error(my_callback_fn)
```

#### `.on_tool_error_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `on_tool_error_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").on_tool_error_if(condition, my_callback_fn)
```

### Control Flow & Execution

#### `.ask(prompt: str) -> str` {bdg-primary}`Control Flow & Execution`

One-shot execution. Build agent, send prompt, return response text.

**See also:** `Agent.ask_async`, `Agent.stream`

**Example:**

```python
reply = Agent("qa", "gemini-2.5-flash").instruct("Answer questions.").ask("What is Python?")
print(reply)
```

#### `.ask_async(prompt: str) -> str` {bdg-primary}`Control Flow & Execution`

Async one-shot execution.

**Example:**

```python
agent = Agent("agent").ask_async("...")
```

#### `.build() -> LlmAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LlmAgent.

**Example:**

```python
agent = Agent("agent").build("...")
```

#### `.events(prompt: str) -> AsyncIterator[Any]` {bdg-primary}`Control Flow & Execution`

Stream raw ADK Event objects. Yields every event including state deltas and function calls.

**Example:**

```python
agent = Agent("agent").events("...")
```

#### `.isolate() -> Self` {bdg-primary}`Control Flow & Execution`

Prevent this agent from transferring to parent or peers. Sets both disallow_transfer_to_parent and disallow_transfer_to_peers to True. Use for specialist agents that should complete their task and return.

**See also:** `Agent.disallow_transfer_to_parent`, `Agent.disallow_transfer_to_peers`

**Example:**

```python
# Specialist agent that completes its task without transferring
specialist = (
    Agent("invoice_parser", "gemini-2.5-flash")
    .instruct("Parse the invoice and extract line items.")
    .isolate()
    .returns(Invoice)
    .build()
)
```

#### `.map(prompts: list[str], *, concurrency: int = 5) -> list[str]` {bdg-primary}`Control Flow & Execution`

Run agent against multiple prompts with bounded concurrency.

**Example:**

```python
agent = Agent("agent").map("...")
```

#### `.map_async(prompts: list[str], *, concurrency: int = 5) -> list[str]` {bdg-primary}`Control Flow & Execution`

Async batch execution against multiple prompts.

**Example:**

```python
agent = Agent("agent").map_async("...")
```

#### `.session() -> Any` {bdg-primary}`Control Flow & Execution`

Create an interactive session context manager. Use with 'async with'.

**Example:**

```python
agent = Agent("agent").session("...")
```

#### `.stream(prompt: str) -> AsyncIterator[str]` {bdg-primary}`Control Flow & Execution`

Streaming execution. Yields response text chunks.

**See also:** `Agent.ask`, `Agent.events`

**Example:**

```python
async for chunk in Agent("writer", "gemini-2.5-flash").instruct("Write a poem.").stream("About the sea"):
    print(chunk, end="")
```

#### `.test(prompt: str, *, contains: str | None = None, matches: str | None = None, equals: str | None = None) -> Self` {bdg-primary}`Control Flow & Execution`

Run a smoke test. Calls .ask() internally, asserts output matches condition.

**Example:**

```python
agent = Agent("agent").test("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
| `.model(value)` | `str | BaseLlm` |
| `.generate_content_config(value)` | `GenerateContentConfig | None` |
| `.disallow_transfer_to_parent(value)` | {py:class}`bool` |
| `.disallow_transfer_to_peers(value)` | {py:class}`bool` |
| `.include_contents(value)` | `Literal['default', 'none']` |
| `.input_schema(value)` | `type[BaseModel] | None` |
| `.output_schema(value)` | `type[BaseModel] | None` |
| `.output_key(value)` | `str | None` |
| `.planner(value)` | `BasePlanner | None` |
| `.code_executor(value)` | `BaseCodeExecutor | None` |
