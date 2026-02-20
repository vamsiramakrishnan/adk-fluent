# Travel Planner with Weather and Flight Lookup -- Agent with Tools

Demonstrates attaching function tools to an agent. The scenario:
a travel planning assistant that can look up weather forecasts and
search for flights to help users plan trips.

*How to attach tools to an agent using the fluent API.*

_Source: `02_agent_with_tools.py`_

::::\{tab-set}
:::\{tab-item} Native ADK

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
:::\{tab-item} adk-fluent

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
::::

## Equivalence

```python
assert type(agent_native) == type(agent_fluent)
assert agent_native.name == agent_fluent.name
assert len(agent_fluent.tools) == 2
```

:::\{seealso}
API reference: [FunctionTool](../api/tool.md#builder-FunctionTool)
:::
