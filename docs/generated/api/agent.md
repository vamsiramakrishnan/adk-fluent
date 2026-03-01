# Module: `agent`

## Builders in this module

| Builder                        | Description                                         |
| ------------------------------ | --------------------------------------------------- |
| [BaseAgent](builder-BaseAgent) | Base class for all agents in Agent Development Kit. |
| [Agent](builder-Agent)         | LLM-based Agent.                                    |

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

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Set the `description` field.

#### `.sub_agent(value: BaseAgent) -> Self`

Append to `sub_agents` (lazy — built at .build() time).

### Callbacks

#### `.after_agent(*fns: Callable) -> Self`

Append callback(s) to `after_agent_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.after_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_agent_callback` only if `condition` is `True`.

#### `.before_agent(*fns: Callable) -> Self`

Append callback(s) to `before_agent_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.before_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_agent_callback` only if `condition` is `True`.

### Control Flow & Execution

#### `.build() -> BaseAgent`

Resolve into a native ADK BaseAgent.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                | Type              |
| -------------------- | ----------------- |
| `.sub_agents(value)` | `list[BaseAgent]` |

______________________________________________________________________

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

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Set the `description` field.

#### `.global_instruct(value: str | Callable[[ReadonlyContext], str | Awaitable[str]]) -> Self`

- **Maps to:** `global_instruction`
- Set the `global_instruction` field.

#### `.instruct(value: str | Callable[[ReadonlyContext], str | Awaitable[str]]) -> Self`

- **Maps to:** `instruction`
- Set the `instruction` field.

#### `.static(value: Content | str | File | Part | list[str | File | Part] | None) -> Self`

- **Maps to:** `static_instruction`
- Set the `static_instruction` field.

#### `.sub_agent(value: BaseAgent) -> Self`

Append to `sub_agents` (lazy — built at .build() time).

#### `.tool(fn_or_tool: Any, *, require_confirmation: bool = False) -> Self`

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

#### `.agent_tool(agent: Any) -> Self`

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

#### `.artifact_schema(schema: type) -> Self`

Attach an ArtifactSchema declaring artifact dependencies.

**See also:** `ArtifactSchema`, `Produces`, `Consumes`

**Example:**

```python
Agent("researcher").artifact_schema(ResearchArtifacts)
```

#### `.artifacts(*transforms: Any) -> Self`

Attach artifact operations (A.publish, A.snapshot, etc.) that fire after this agent completes.

**See also:** `A`, `ATransform`

**Example:**

```python
Agent("writer").artifacts(A.publish("report.md", from_key="output"))
```

#### `.callback_schema(schema: type) -> Self`

Attach a CallbackSchema declaring callback state dependencies.

#### `.context(spec: Any) -> Self`

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

#### `.guard(fn: Callable[..., Any]) -> Self`

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

#### `.hide() -> Self`

Force this agent's events to be internal (override topology inference).

**See also:** `Agent.show`

**Example:**

```python
# Suppress terminal agent output from user view
agent = Agent("cleanup").model("m").instruct("Clean up.").hide()
```

#### `.memory(mode: str = 'preload') -> Self`

Add memory tools to this agent. Modes: 'preload', 'on_demand', 'both'.

**See also:** `Agent.memory_auto_save`, `Agent.context`

**Example:**

```python
agent = Agent("assistant", "gemini-2.5-flash").memory("preload").build()
```

#### `.memory_auto_save() -> Self`

Auto-save session to memory after each agent run.

#### `.no_peers() -> Self`

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

#### `.prompt_schema(schema: type) -> Self`

Attach a PromptSchema declaring prompt state dependencies.

#### `.show() -> Self`

Force this agent's events to be user-facing (override topology inference).

**See also:** `Agent.hide`

**Example:**

```python
# Force intermediate agent output to be visible to users
agent = Agent("logger").model("m").instruct("Log progress.").show()
```

#### `.stay() -> Self`

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

#### `.to_ir() -> Any`

Convert this Agent builder to an AgentNode IR node.

#### `.tool_schema(schema: type) -> Self`

Attach a ToolSchema declaring tool state dependencies.

#### `.tools(value: Any) -> Self`

Set tools. Accepts a list, a TComposite chain (T.fn(x) | T.fn(y)), or a single tool/toolset.

### Callbacks

#### `.after_agent(*fns: Callable) -> Self`

Append callback(s) to `after_agent_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.after_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_agent_callback` only if `condition` is `True`.

#### `.after_model(*fns: Callable) -> Self`

Append callback(s) to `after_model_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.after_model_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_model_callback` only if `condition` is `True`.

#### `.after_tool(*fns: Callable) -> Self`

Append callback(s) to `after_tool_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.after_tool_if(condition: bool, fn: Callable) -> Self`

Append callback to `after_tool_callback` only if `condition` is `True`.

#### `.before_agent(*fns: Callable) -> Self`

Append callback(s) to `before_agent_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.before_agent_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_agent_callback` only if `condition` is `True`.

#### `.before_model(*fns: Callable) -> Self`

Append callback(s) to `before_model_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.before_model_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_model_callback` only if `condition` is `True`.

#### `.before_tool(*fns: Callable) -> Self`

Append callback(s) to `before_tool_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.before_tool_if(condition: bool, fn: Callable) -> Self`

Append callback to `before_tool_callback` only if `condition` is `True`.

#### `.on_model_error(*fns: Callable) -> Self`

Append callback(s) to `on_model_error_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.on_model_error_if(condition: bool, fn: Callable) -> Self`

Append callback to `on_model_error_callback` only if `condition` is `True`.

#### `.on_tool_error(*fns: Callable) -> Self`

Append callback(s) to `on_tool_error_callback`.

:::\{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

#### `.on_tool_error_if(condition: bool, fn: Callable) -> Self`

Append callback to `on_tool_error_callback` only if `condition` is `True`.

### Control Flow & Execution

#### `.ask(prompt: str) -> str`

One-shot execution. Build agent, send prompt, return response text.

**See also:** `Agent.ask_async`, `Agent.stream`

**Example:**

```python
reply = Agent("qa", "gemini-2.5-flash").instruct("Answer questions.").ask("What is Python?")
print(reply)
```

#### `.ask_async(prompt: str) -> str`

Async one-shot execution.

#### `.build() -> LlmAgent`

Resolve into a native ADK LlmAgent.

#### `.events(prompt: str) -> AsyncIterator[Any]`

Stream raw ADK Event objects. Yields every event including state deltas and function calls.

#### `.isolate() -> Self`

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

#### `.map(prompts: list[str], *, concurrency: int = 5) -> list[str]`

Run agent against multiple prompts with bounded concurrency.

#### `.map_async(prompts: list[str], *, concurrency: int = 5) -> list[str]`

Async batch execution against multiple prompts.

#### `.session() -> Any`

Create an interactive session context manager. Use with 'async with'.

#### `.stream(prompt: str) -> AsyncIterator[str]`

Streaming execution. Yields response text chunks.

**See also:** `Agent.ask`, `Agent.events`

**Example:**

```python
async for chunk in Agent("writer", "gemini-2.5-flash").instruct("Write a poem.").stream("About the sea"):
    print(chunk, end="")
```

#### `.test(prompt: str, *, contains: str | None = None, matches: str | None = None, equals: str | None = None) -> Self`

Run a smoke test. Calls .ask() internally, asserts output matches condition.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                 | Type                         |
| ------------------------------------- | ---------------------------- |
| `.sub_agents(value)`                  | `list[BaseAgent]`            |
| `.model(value)`                       | \`str                        |
| `.generate_content_config(value)`     | \`GenerateContentConfig      |
| `.disallow_transfer_to_parent(value)` | `bool`                       |
| `.disallow_transfer_to_peers(value)`  | `bool`                       |
| `.include_contents(value)`            | `Literal['default', 'none']` |
| `.input_schema(value)`                | \`type\[BaseModel\]          |
| `.output_schema(value)`               | \`type\[BaseModel\]          |
| `.output_key(value)`                  | \`str                        |
| `.planner(value)`                     | \`BasePlanner                |
| `.code_executor(value)`               | \`BaseCodeExecutor           |
