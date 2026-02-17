# Parallel FanOut

*How to run agents in parallel using FanOut.*

_Source: `05_parallel_fanout.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.parallel_agent import ParallelAgent

fanout_native = ParallelAgent(
    name="parallel_search",
    sub_agents=[
        LlmAgent(name="web", model="gemini-2.5-flash", instruction="Search web."),
        LlmAgent(name="db", model="gemini-2.5-flash", instruction="Search database."),
    ],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, FanOut

fanout_fluent = (
    FanOut("parallel_search")
    .branch(Agent("web").model("gemini-2.5-flash").instruct("Search web."))
    .branch(Agent("db").model("gemini-2.5-flash").instruct("Search database."))
    .build()
)
```
:::
::::

## Equivalence

```python
assert type(fanout_native) == type(fanout_fluent)
assert len(fanout_fluent.sub_agents) == 2
```

:::{seealso}
API reference: [FanOut](../api/workflow.md#builder-FanOut)
:::
