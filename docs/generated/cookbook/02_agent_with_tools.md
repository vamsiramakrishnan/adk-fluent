# Agent with Tools

*How to attach tools to an agent using the fluent API.*

_Source: `02_agent_with_tools.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent


def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}"


def get_time(timezone: str) -> str:
    """Get current time."""
    return f"3:00 PM in {timezone}"


agent_native = LlmAgent(
    name="assistant",
    model="gemini-2.5-flash",
    instruction="You help with weather and time.",
    tools=[get_weather, get_time],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

agent_fluent = (
    Agent("assistant")
    .model("gemini-2.5-flash")
    .instruct("You help with weather and time.")
    .tool(get_weather)
    .tool(get_time)
    .build()
)
```
:::
::::

## Equivalence

```python
assert type(agent_native) == type(agent_fluent)
assert agent_native.name == agent_fluent.name
assert len(agent_fluent.tools) == 2
```

:::{seealso}
API reference: [FunctionTool](../api/tool.md#builder-FunctionTool)
:::
