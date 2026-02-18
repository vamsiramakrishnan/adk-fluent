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

## Tool Confirmation

For tools that require human approval before execution:

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.function_tool import FunctionTool

deploy_tool = FunctionTool(func=deploy_fn, require_confirmation=True)

agent = LlmAgent(
    name="ops",
    model="gemini-2.5-flash",
    instruction="Deploy services.",
    tools=[deploy_tool],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# require_confirmation wraps the function in FunctionTool automatically
agent = (
    Agent("ops")
    .model("gemini-2.5-flash")
    .instruct("Deploy services.")
    .tool(deploy_fn, require_confirmation=True)
    .build()
)
```
:::
::::

```python
from google.adk.tools.function_tool import FunctionTool
assert isinstance(agent.tools[0], FunctionTool)
```
