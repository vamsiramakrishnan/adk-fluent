# Memory

`.memory()` adds ADK memory tools to an agent for long-term recall across sessions. The agent can retrieve past interactions without manual session management.

## Quick Start

```python
from adk_fluent import Agent

agent = Agent("assistant", "gemini-2.5-flash").memory("preload").build()
```

## Modes Reference

| Mode | Behavior |
|------|----------|
| `preload` | Load relevant memories before each turn (`PreloadMemoryTool`) |
| `on_demand` | Agent can invoke memory tool when needed (`LoadMemoryTool`) |
| `both` | Both preload and on-demand tools added |

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

Memory can be added to individual agents within a pipeline:

```python
from adk_fluent import Agent

pipeline = (
    Agent("researcher")
        .model("gemini-2.5-flash")
        .instruct("Research the topic.")
        .memory("preload")
    >> Agent("writer")
        .model("gemini-2.5-flash")
        .instruct("Write a report.")
)
```

Only the researcher loads memories here. The writer receives the researcher's output through the pipeline without needing its own memory.

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

## Combining Memory with Context

Memory and context engineering compose naturally. Use `.memory()` for long-term recall and `.context()` for controlling the conversation window:

```python
from adk_fluent import Agent, C

agent = (
    Agent("advisor")
    .model("gemini-2.5-flash")
    .instruct("Advise based on history and memories.")
    .memory("preload")
    .context(C.window(n=5))
    .build()
)
```

The agent sees the last 5 conversation turns plus any relevant memories from previous sessions.

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
