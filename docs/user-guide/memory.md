# Memory

:::{admonition} At a Glance
:class: tip

- `.memory()` attaches memory tools for persistent state across sessions
- Three modes: preload (inject at start), tool-based (agent decides), auto-save (save after execution)
- Use for agents that need to remember previous conversations
:::

`.memory()` adds ADK memory tools to an agent for long-term recall across sessions. Without memory, each session starts fresh -- the agent has no knowledge of past interactions. With memory, the agent can retrieve relevant past conversations automatically.

## When to Use Memory

| Situation | Use memory? | Why |
|---|---|---|
| Customer support agent | Yes (`preload`) | Recognize returning customers, recall past issues |
| Classifier / router | No | Stateless utility agents should be fast and context-free |
| Research agent | Maybe (`on_demand`) | Only load when the agent decides past research is relevant |
| Conversational assistant | Yes (`both`) | Preload for immediate context, on-demand for deep recall |

:::{admonition} Rule of thumb
:class: tip
Use memory for agents that interact with users over multiple sessions. Don't use memory for intermediate pipeline agents (classifiers, transformers, validators) -- they should be stateless and fast.
:::

## Quick Start

```python
from adk_fluent import Agent

agent = Agent("assistant", "gemini-2.5-flash").memory("preload").build()
```

## Modes Reference

| Mode | Behavior | Use case |
|---|---|---|
| `preload` | Load relevant memories before each turn (`PreloadMemoryTool`) | Most common -- agent always has context |
| `on_demand` | Agent can invoke memory tool when needed (`LoadMemoryTool`) | Expensive memory backends; agent decides when to look |
| `both` | Both preload and on-demand tools added | Full flexibility |

## `preload`

Retrieves relevant memories at the start of each turn automatically. The agent does not need to decide when to load -- context is injected before the LLM call:

```python
agent = Agent("assistant", "gemini-2.5-flash").memory("preload").build()
```

## `on_demand`

Gives the agent a `LoadMemoryTool` it can invoke when it decides past context is needed. Useful when memory lookups are expensive and not always required:

```python
agent = Agent("assistant", "gemini-2.5-flash").memory("on_demand").build()
```

## `both`

Combines preload and on-demand. The agent gets pre-loaded context and can still query for more:

```python
agent = Agent("assistant", "gemini-2.5-flash").memory("both").build()
```

## Using `.memory()` in Pipelines

Memory can be added to individual agents within a pipeline. Not every agent needs memory -- be selective:

```python
from adk_fluent import Agent

pipeline = (
    Agent("researcher")
        .model("gemini-2.5-flash")
        .instruct("Research the topic.")
        .memory("preload")  # Researcher loads past research
    >> Agent("writer")
        .model("gemini-2.5-flash")
        .instruct("Write a report.")
        # Writer doesn't need memory -- it receives input from researcher
)
```

## Auto-Save

`.memory_auto_save()` saves the session to memory after each agent run via an `after_agent_callback`. This ensures future sessions can recall what happened:

```python
agent = (
    Agent("assistant", "gemini-2.5-flash")
    .memory("preload")
    .memory_auto_save()
    .build()
)
```

Auto-save requires a `memory_service` to be configured on the Runner or App.

## Interplay with Other Modules

### Memory + Context Engineering

Memory and context engineering solve different time scales:

- **Context engineering** (`C.*`) controls what the LLM sees from the *current session* -- conversation history, state keys, agent outputs
- **Memory** controls what the LLM sees from *past sessions* -- previous conversations, accumulated knowledge

They compose naturally:

```python
from adk_fluent import Agent, C

agent = (
    Agent("advisor")
    .model("gemini-2.5-flash")
    .instruct("Advise based on history and memories.")
    .memory("preload")        # Past sessions
    .context(C.window(n=5))   # Last 5 turns of current session
    .build()
)
```

The agent sees the last 5 conversation turns *plus* any relevant memories from previous sessions.

:::{admonition} Common mistake
:class: warning
Don't use `C.none()` with `.memory("preload")`. `C.none()` hides all conversation history, but preloaded memories arrive *as part of the conversation* -- they'll be hidden too. If you need context isolation with memory, use `C.from_state()` to select specific keys instead.
:::

### Memory + State Transforms

Use `S.*` to capture and structure data before it's saved to memory:

```python
from adk_fluent import Agent, S

pipeline = (
    S.capture("user_query")
    >> Agent("support")
       .model("gemini-2.5-flash")
       .instruct("Help the customer with: {user_query}")
       .memory("preload")
       .memory_auto_save()
       .writes("resolution")
    >> S.log("resolution")  # Debug: log what gets saved
)
```

### Memory + Presets

Share memory configuration across agents with Presets:

```python
from adk_fluent import Agent
from adk_fluent.presets import Preset

# All customer-facing agents share memory config
customer_preset = Preset(model="gemini-2.5-flash")

support = Agent("support").instruct("Help.").use(customer_preset).memory("preload").memory_auto_save()
advisor = Agent("advisor").instruct("Advise.").use(customer_preset).memory("preload").memory_auto_save()
```

### Memory + Testing

Mock backends don't include memory services. For testing agents with memory, either:

1. **Skip memory in unit tests** -- test the agent logic with `mock_backend()`, test memory integration separately
2. **Use `InMemoryMemoryService`** -- lightweight in-memory service for integration tests

```python
from adk_fluent import Agent
from adk_fluent.testing import AgentHarness, mock_backend

# Unit test: mock backend ignores memory, tests logic only
harness = AgentHarness(
    Agent("support").instruct("Help."),  # No .memory() for unit test
    backend=mock_backend({"support": "Issue resolved."})
)
```

See [Testing](testing.md) for the full testing guide.

## Complete Example

```python
from adk_fluent import Agent, C

# A support agent that remembers past interactions
support = (
    Agent("support")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a customer support agent. Use memories of past "
        "interactions to provide personalized assistance."
    )
    .memory("both")
    .memory_auto_save()
    .context(C.window(n=10))
    .build()
)
```

## Best Practices

1. **Be selective about which agents get memory.** Only user-facing agents that benefit from cross-session context should use memory. Pipeline intermediaries (classifiers, transformers) should be stateless
2. **Prefer `preload` for most cases.** It's simpler and ensures the agent always has context. Use `on_demand` only when memory lookups are expensive
3. **Always pair `.memory()` with `.memory_auto_save()`** if you want bidirectional memory (read and write). Without auto-save, the agent reads memories but never creates new ones
4. **Don't put memory on `C.none()` agents.** Context isolation hides preloaded memories. Use `C.from_state()` instead if you need selective context
5. **Test memory-dependent logic separately.** Mock backends test agent logic; integration tests with `InMemoryMemoryService` test memory behavior

:::{seealso}
- [Context Engineering](context-engineering.md) -- `C.window()`, `C.from_state()`, and controlling what the LLM sees from the current session
- [Presets](presets.md) -- share memory configuration across agents
- [Testing](testing.md) -- testing agents with and without memory
- [State Transforms](state-transforms.md) -- `S.capture()`, `S.log()` for structuring data around memory
:::
