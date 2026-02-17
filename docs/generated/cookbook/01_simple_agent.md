# Simple Agent Creation

_Source: `01_simple_agent.py`_

## Native ADK

```python
from google.adk.agents.llm_agent import LlmAgent

agent_native = LlmAgent(
    name="helper",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    description="A simple helper agent",
)
```

## adk-fluent

```python
from adk_fluent import Agent

agent_fluent = (
    Agent("helper")
    .model("gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("A simple helper agent")
    .build()
)
```

## Equivalence

```python
assert type(agent_native) == type(agent_fluent)
assert agent_native.name == agent_fluent.name
assert agent_native.model == agent_fluent.model
assert agent_native.instruction == agent_fluent.instruction
```
