# Team Coordinator Pattern

*How to build a team of agents with a coordinator.*

_Source: `07_team_coordinator.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent

coordinator_native = LlmAgent(
    name="team_lead",
    model="gemini-2.5-flash",
    instruction="Coordinate the team. Delegate to the right member.",
    sub_agents=[
        LlmAgent(name="frontend", model="gemini-2.5-flash", instruction="Build UI."),
        LlmAgent(name="backend", model="gemini-2.5-flash", instruction="Build APIs."),
    ],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

coordinator_fluent = (
    Agent("team_lead")
    .model("gemini-2.5-flash")
    .instruct("Coordinate the team. Delegate to the right member.")
    .member(Agent("frontend").model("gemini-2.5-flash").instruct("Build UI."))
    .member(Agent("backend").model("gemini-2.5-flash").instruct("Build APIs."))
    .build()
)
```
:::
::::

## Equivalence

```python
assert type(coordinator_native) == type(coordinator_fluent)
assert len(coordinator_fluent.sub_agents) == 2
assert coordinator_fluent.sub_agents[0].name == "frontend"
```
