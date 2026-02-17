# Sequential Pipeline

*How to compose agents into a sequential pipeline.*

_Source: `04_sequential_pipeline.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent

researcher = LlmAgent(
    name="researcher",
    model="gemini-2.5-flash",
    instruction="Research the topic.",
)
writer = LlmAgent(
    name="writer",
    model="gemini-2.5-flash",
    instruction="Write a summary.",
)
pipeline_native = SequentialAgent(
    name="blog_pipeline",
    description="Research then write",
    sub_agents=[researcher, writer],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline

pipeline_fluent = (
    Pipeline("blog_pipeline")
    .describe("Research then write")
    .step(Agent("researcher").model("gemini-2.5-flash").instruct("Research the topic."))
    .step(Agent("writer").model("gemini-2.5-flash").instruct("Write a summary."))
    .build()
)
```
:::
::::

## Equivalence

```python
assert type(pipeline_native) == type(pipeline_fluent)
assert len(pipeline_fluent.sub_agents) == 2
assert pipeline_fluent.sub_agents[0].name == "researcher"
assert pipeline_fluent.sub_agents[1].name == "writer"
```

:::{seealso}
API reference: [Pipeline](../api/workflow.md#builder-Pipeline)
:::
