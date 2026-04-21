# Module: `agent`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [BaseAgent](builder-BaseAgent) | Base class for all agents in Agent Development Kit. |
| [Agent](builder-Agent) | LLM-based Agent. |
| [RemoteA2aAgent](builder-RemoteA2aAgent) | Agent that communicates with a remote A2A agent via A2A client. |

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

(method-BaseAgent-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
agent = BaseAgent("agent").describe("...")
```

(method-BaseAgent-sub_agent)=
#### `.transfer_to(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
agent = BaseAgent("agent").transfer_to("...")
```

### Callbacks

(method-BaseAgent-after_agent)=
#### `.after_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = BaseAgent("agent").after_agent(my_callback_fn)
```

(method-BaseAgent-after_agent_if)=
#### `.after_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_agent_callback` only if `condition` is `True`.

**Example:**

```python
agent = BaseAgent("agent").after_agent_if(condition, my_callback_fn)
```

(method-BaseAgent-before_agent)=
#### `.before_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = BaseAgent("agent").before_agent(my_callback_fn)
```

(method-BaseAgent-before_agent_if)=
#### `.before_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_agent_callback` only if `condition` is `True`.

**Example:**

```python
agent = BaseAgent("agent").before_agent_if(condition, my_callback_fn)
```

### Control Flow & Execution

(method-BaseAgent-build)=
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

(method-Agent-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
agent = Agent("agent").describe("...")
```

(method-Agent-global_instruct)=
#### `.global_instruct(value: str | Callable[[ReadonlyContext], str | Awaitable[str]]) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `global_instruction`
- Set instruction shared by ALL agents in a workflow. Only meaningful on the root agent. Prepended to every agent's system prompt.

**Example:**

```python
agent = Agent("agent").global_instruct("...")
```

(method-Agent-instruct)=
#### `.instruct(value: str | Callable[[ReadonlyContext], str | Awaitable[str]]) -> Self` {bdg-success}`Core Configuration`

Set the main instruction / system prompt — what the LLM is told to do. Accepts plain text, a callable, or a P module composition (P.role() | P.task()). Raises TypeError if passed a CTransform (use .context() instead).

**Example:**

```python
agent = Agent("agent").instruct("You are a helpful assistant.")
```

(method-Agent-static)=
#### `.static(value: Content | str | File | Part | list[str | File | Part] | None) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `static_instruction`
- Set cached instruction. When set, `.instruct()` text moves from system to user content, enabling context caching. Use for large, stable prompt sections that rarely change.

**Example:**

```python
agent = Agent("agent").static("You are a helpful assistant.")
```

(method-Agent-sub_agent)=
#### `.transfer_to(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
agent = Agent("agent").transfer_to("...")
```

(method-Agent-tool)=
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

(method-Agent-agent_tool)=
#### `.delegate_to(agent: Any) -> Self` {bdg-info}`Configuration`

Wrap another agent as a callable AgentTool and add it to this agent's tools. The parent LLM invokes the child like any other tool, stays in control, and receives the response. Compare with .transfer_to() which fully transfers control to the child.

**See also:** `Agent.tool`, `Agent.isolate`

**Example:**

```python
specialist = Agent("invoice_parser", "gemini-2.5-flash").instruct("Parse invoices.")
coordinator = (
    Agent("router", "gemini-2.5-flash")
    .instruct("Route tasks to specialists.")
    .delegate_to(specialist)
    .build()
)
```

(method-Agent-artifact_schema)=
#### `.artifact_schema(schema: type) -> Self` {bdg-info}`Configuration`

Attach an ArtifactSchema declaring artifact dependencies.

**See also:** `ArtifactSchema`, `Produces`, `Consumes`

**Example:**

```python
Agent("researcher").artifact_schema(ResearchArtifacts)
```

(method-Agent-artifacts)=
#### `.artifacts(*transforms: Any) -> Self` {bdg-info}`Configuration`

Attach artifact operations (A.publish, A.snapshot, etc.) that fire after this agent completes.

**See also:** `A`, `ATransform`

**Example:**

```python
Agent("writer").artifacts(A.publish("report.md", from_key="output"))
```

(method-Agent-callback_schema)=
#### `.callback_schema(schema: type) -> Self` {bdg-info}`Configuration`

Attach a CallbackSchema declaring callback state dependencies.

**Example:**

```python
agent = Agent("agent").callback_schema(my_callback_fn)
```

(method-Agent-context)=
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

(method-Agent-eval)=
#### `.eval(prompt: str, *, expect: str | None = None, criteria: Any | None = None) -> Any` {bdg-info}`Configuration`

Inline evaluation. Run a single eval case against this agent. Returns an EvalSuite ready to .run().

**See also:** `E`, `Agent.eval_suite`, `Agent.test`

**Example:**

```python
from adk_fluent import E

report = await agent.eval("What is 2+2?", expect="4").run()
assert report.ok

# With custom criteria
report = await agent.eval("query", criteria=E.semantic_match()).run()
```

(method-Agent-eval_suite)=
#### `.eval_suite() -> Any` {bdg-info}`Configuration`

Create an evaluation suite builder for this agent. Returns an EvalSuite bound to this agent.

**See also:** `E`, `Agent.eval`, `EvalSuite`

**Example:**

```python
from adk_fluent import E

report = await (
    agent.eval_suite()
    .case("What is 2+2?", expect="4")
    .criteria(E.trajectory() | E.response_match())
    .run()
)
```

(method-Agent-guard)=
#### `.guard(value: Any) -> Self` {bdg-info}`Configuration`

Add an output validation guard. Accepts a G composite (G.pii() | G.length(max=500)) or a plain callable. Guards run as after_model callbacks and validate/transform the LLM response before it is returned.

**See also:** `Agent.before_model`, `Agent.after_model`

**Example:**

```python
from adk_fluent import G

# Declarative guards
agent = Agent("safe", "gemini-2.5-flash").guard(G.pii("redact") | G.budget(5000))

# Legacy callable guard (still works)
agent = Agent("safe", "gemini-2.5-flash").guard(my_guard_fn)
```

(method-Agent-hide)=
#### `.hide() -> Self` {bdg-info}`Configuration`

Force this agent's events to be internal (override topology inference). Pair with .reveal() for the inverse.

**See also:** `Agent.reveal`

**Example:**

```python
# Suppress terminal agent output from user view
agent = Agent("cleanup").model("m").instruct("Clean up.").hide()
```

(method-Agent-memory)=
#### `.memory(mode: str = 'preload') -> Self` {bdg-info}`Configuration`

Add memory tools to this agent. Modes: 'preload', 'on_demand', 'both'.

**See also:** `Agent.memory_auto_save`, `Agent.context`

**Example:**

```python
agent = Agent("assistant", "gemini-2.5-flash").memory("preload").build()
```

(method-Agent-memory_auto_save)=
#### `.memory_auto_save() -> Self` {bdg-info}`Configuration`

Auto-save session to memory after each agent run.

**Example:**

```python
agent = Agent("agent").memory_auto_save("...")
```

(method-Agent-no_peers)=
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

(method-Agent-prompt_schema)=
#### `.prompt_schema(schema: type) -> Self` {bdg-info}`Configuration`

Attach a PromptSchema declaring prompt state dependencies.

**Example:**

```python
agent = Agent("agent").prompt_schema("...")
```

(method-Agent-publish)=
#### `.publish(*, port: int = 8000, host: str = '0.0.0.0') -> Any` {bdg-info}`Configuration`

Publish this agent as an A2A server (returns Starlette app). Shorthand for `A2AServer(self).port(port).host(host).build()`.

**Example:**

```python
agent = Agent("agent").publish("...")
```

(method-Agent-reveal)=
#### `.reveal() -> Self` {bdg-info}`Configuration`

Force this agent's events to be user-facing (override topology inference). Pair with .hide() for the inverse.

**See also:** `Agent.hide`

**Example:**

```python
# Force intermediate agent output to be visible to users
agent = Agent("logger").model("m").instruct("Log progress.").reveal()
```

(method-Agent-skill)=
#### `.skill(skill_id: str, name: str, *, description: str = '', tags: list[str] | None = None, examples: list[str] | None = None, input_modes: list[str] | None = None, output_modes: list[str] | None = None) -> Self` {bdg-info}`Configuration`

Declare an A2A skill for this agent's AgentCard. Skills are metadata consumed by `A2AServer` during card generation. They have no effect on local agent execution. If no skills are declared, `A2AServer` auto-infers them from the agent's tools and sub-agents.

**Example:**

```python
agent = Agent("agent").skill("...")
```

(method-Agent-static_instruct)=
#### `.static_instruct(value: Content | str | File | Part | list[str | File | Part] | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `static_instruction`
- Set cached instruction. When set, `.instruct()` text moves from system to user content, enabling context caching. Use for large, stable prompt sections that rarely change.

**Example:**

```python
agent = Agent("agent").static_instruct("...")
```

(method-Agent-stay)=
#### `.stay() -> Self` {bdg-info}`Configuration`

Prevent transfer to parent only (can still transfer to sibling peers). Equivalent to .disallow_transfer_to_parent(True). Use for agents in peer-to-peer handoff chains where the coordinator should not regain control mid-sequence.

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

(method-Agent-to_ir)=
#### `.to_ir() -> Any` {bdg-info}`Configuration`

Convert this Agent builder to an AgentNode IR node.

**Example:**

```python
agent = Agent("agent").to_ir("...")
```

(method-Agent-tool_schema)=
#### `.tool_schema(schema: type) -> Self` {bdg-info}`Configuration`

Attach a ToolSchema declaring tool state dependencies.

**Example:**

```python
agent = Agent("agent").tool_schema("...")
```

(method-Agent-tools)=
#### `.tools(value: Any) -> Self` {bdg-info}`Configuration`

Set tools. Accepts a list, a TComposite chain (T.fn(x) | T.fn(y)), or a single tool/toolset.

**Example:**

```python
agent = Agent("agent").tools("...")
```

(method-Agent-ui)=
#### `.ui(spec: Any = None, *, llm_guided: bool = False, validate: bool = True, log: bool = False) -> Self` {bdg-info}`Configuration`

Attach A2UI surface for rich UI output. Modes: Declarative (.ui(UI.form(...)) / .ui(UI.surface(...))); LLM-guided (.ui(UI.auto()) or .ui(llm_guided=True)); Component tree (.ui(UI.column(UI.text('Hi'), UI.button('Go', action='go')))). Flags: llm_guided auto-wires T.a2ui()+G.a2ui(); validate runs surface.validate() at build-time; log auto-wires M.a2ui_log().

**See also:** `UI.surface`, `UI.form`, `UI.auto`, `UI.paths`, `T.a2ui`, `G.a2ui`

**Example:**

```python
from adk_fluent import Agent, UI

# Declarative form
agent = Agent("support", "gemini-2.5-flash").ui(
    UI.form("Contact", fields={"name": "text", "email": "email"})
).build()

# LLM-guided mode (shorthand)
agent = Agent("creative", "gemini-2.5-flash").ui(llm_guided=True).build()

# LLM-guided mode (explicit)
agent = Agent("designer", "gemini-2.5-flash").ui(UI.auto(), llm_guided=True).build()
```

### Callbacks

(method-Agent-after_agent)=
#### `.after_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").after_agent(my_callback_fn)
```

(method-Agent-after_agent_if)=
#### `.after_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_agent_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").after_agent_if(condition, my_callback_fn)
```

(method-Agent-after_model)=
#### `.after_model(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_model_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").after_model(my_callback_fn)
```

(method-Agent-after_model_if)=
#### `.after_model_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_model_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").after_model_if(condition, my_callback_fn)
```

(method-Agent-after_tool)=
#### `.after_tool(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_tool_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").after_tool(my_callback_fn)
```

(method-Agent-after_tool_if)=
#### `.after_tool_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_tool_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").after_tool_if(condition, my_callback_fn)
```

(method-Agent-before_agent)=
#### `.before_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").before_agent(my_callback_fn)
```

(method-Agent-before_agent_if)=
#### `.before_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_agent_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").before_agent_if(condition, my_callback_fn)
```

(method-Agent-before_model)=
#### `.before_model(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_model_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").before_model(my_callback_fn)
```

(method-Agent-before_model_if)=
#### `.before_model_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_model_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").before_model_if(condition, my_callback_fn)
```

(method-Agent-before_tool)=
#### `.before_tool(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_tool_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").before_tool(my_callback_fn)
```

(method-Agent-before_tool_if)=
#### `.before_tool_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_tool_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").before_tool_if(condition, my_callback_fn)
```

(method-Agent-on_model_error)=
#### `.on_model_error(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `on_model_error_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").on_model_error(my_callback_fn)
```

(method-Agent-on_model_error_if)=
#### `.on_model_error_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `on_model_error_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").on_model_error_if(condition, my_callback_fn)
```

(method-Agent-on_tool_error)=
#### `.on_tool_error(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `on_tool_error_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
agent = Agent("agent").on_tool_error(my_callback_fn)
```

(method-Agent-on_tool_error_if)=
#### `.on_tool_error_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `on_tool_error_callback` only if `condition` is `True`.

**Example:**

```python
agent = Agent("agent").on_tool_error_if(condition, my_callback_fn)
```

### Control Flow & Execution

(method-Agent-build)=
#### `.build() -> LlmAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LlmAgent.

**Example:**

```python
agent = Agent("agent").build("...")
```

(method-Agent-isolate)=
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

---

(builder-RemoteA2aAgent)=
## RemoteA2aAgent

> Fluent builder for `google.adk.agents.remote_a2a_agent.RemoteA2aAgent`

Agent that communicates with a remote A2A agent via A2A client.

**Quick start:**

```python
from adk_fluent import RemoteA2aAgent

result = (
    RemoteA2aAgent("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
RemoteA2aAgent(name: str)
```

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |

### Core Configuration

(method-RemoteA2aAgent-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
remotea2aagent = RemoteA2aAgent("remotea2aagent").describe("...")
```

(method-RemoteA2aAgent-sub_agent)=
#### `.transfer_to(value: BaseAgent) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
remotea2aagent = RemoteA2aAgent("remotea2aagent").transfer_to("...")
```

### Callbacks

(method-RemoteA2aAgent-after_agent)=
#### `.after_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `after_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
remotea2aagent = RemoteA2aAgent("remotea2aagent").after_agent(my_callback_fn)
```

(method-RemoteA2aAgent-after_agent_if)=
#### `.after_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `after_agent_callback` only if `condition` is `True`.

**Example:**

```python
remotea2aagent = RemoteA2aAgent("remotea2aagent").after_agent_if(condition, my_callback_fn)
```

(method-RemoteA2aAgent-before_agent)=
#### `.before_agent(*fns: Callable) -> Self` {bdg-info}`Callbacks`

Append callback(s) to `before_agent_callback`.

:::{note}
Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks.
:::

**Example:**

```python
remotea2aagent = RemoteA2aAgent("remotea2aagent").before_agent(my_callback_fn)
```

(method-RemoteA2aAgent-before_agent_if)=
#### `.before_agent_if(condition: bool, fn: Callable) -> Self` {bdg-info}`Callbacks`

Append callback to `before_agent_callback` only if `condition` is `True`.

**Example:**

```python
remotea2aagent = RemoteA2aAgent("remotea2aagent").before_agent_if(condition, my_callback_fn)
```

### Control Flow & Execution

(method-RemoteA2aAgent-build)=
#### `.build() -> RemoteA2aAgent` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK RemoteA2aAgent.

**Example:**

```python
remotea2aagent = RemoteA2aAgent("remotea2aagent").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.sub_agents(value)` | `list[BaseAgent]` |
