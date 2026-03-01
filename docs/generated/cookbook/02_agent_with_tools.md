# Travel Planner with Weather and Flight Lookup -- Agent with Tools

Demonstrates attaching function tools to an agent.  The scenario:
a travel planning assistant that can look up weather forecasts and
search for flights to help users plan trips.

:::{admonition} Why this matters
:class: important
Tools are what make agents useful beyond text generation -- they connect agents to real-world data and actions. A travel planner without tools can only guess at weather and flight information. With tools, it queries live APIs and returns actionable results. The fluent `.tool()` method adds tools additively with chaining, making it easy to compose tool sets from reusable functions.
:::

:::{warning} Without this
Without tools, agents hallucinate factual data -- weather forecasts, flight prices, database records -- because they have no way to access real information. In native ADK, tools are passed as a flat list to the constructor, making it harder to compose tool sets from multiple sources or conditionally add tools based on configuration.
:::

:::{tip} What you'll learn
How to attach tools to an agent using the fluent API.
:::

_Source: `02_agent_with_tools.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

agent_fluent = (
    Agent("travel_planner")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a travel planning assistant. Help users plan trips by "
        "checking weather forecasts and searching for flights. Always "
        "check the weather at the destination before recommending flights."
    )
    .tool(check_weather)
    .tool(search_flights)
    .build()
)
```
:::
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent


def check_weather(city: str, date: str) -> str:
    """Check the weather forecast for a city on a given date."""
    return f"Forecast for {city} on {date}: 24C, partly cloudy"


def search_flights(origin: str, destination: str, date: str) -> str:
    """Search available flights between two cities on a date."""
    return f"Found 3 flights from {origin} to {destination} on {date}, starting at $299"


agent_native = LlmAgent(
    name="travel_planner",
    model="gemini-2.5-flash",
    instruction=(
        "You are a travel planning assistant. Help users plan trips by "
        "checking weather forecasts and searching for flights. Always "
        "check the weather at the destination before recommending flights."
    ),
    tools=[check_weather, search_flights],
)
```
:::
::::

## Equivalence

```python
assert type(agent_native) == type(agent_fluent)
assert agent_native.name == agent_fluent.name
assert len(agent_fluent.tools) == 2

# --- T Module equivalent ---
# T module provides composable tool chains as an alternative to individual .tool() calls
from adk_fluent._tools import T
from google.adk.tools.function_tool import FunctionTool

travel_t = (
    Agent("travel_planner_t")
    .model("gemini-2.5-flash")
    .instruct("Help users plan trips.")
    .tools(T.fn(check_weather) | T.fn(search_flights))
)
ir_t = travel_t.to_ir()
assert len(ir_t.tools) == 2
assert isinstance(ir_t.tools[0], FunctionTool)
assert isinstance(ir_t.tools[1], FunctionTool)
```

:::{seealso}
API reference: [FunctionTool](../api/tool.md#builder-FunctionTool)
:::
