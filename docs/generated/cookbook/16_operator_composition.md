# Operator Composition: >>, |, *

_Source: `16_operator_composition.py`_

## Native ADK

```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.loop_agent import LoopAgent

# Native: 15+ lines for a simple pipeline
researcher = LlmAgent(name="researcher", model="gemini-2.5-flash", instruction="Research.")
writer = LlmAgent(name="writer", model="gemini-2.5-flash", instruction="Write.")
editor = LlmAgent(name="editor", model="gemini-2.5-flash", instruction="Edit.")

pipeline_native = SequentialAgent(
    name="content_pipeline",
    sub_agents=[researcher, writer, editor],
)

# Native: parallel requires explicit wrapping
web = LlmAgent(name="web", model="gemini-2.5-flash", instruction="Search web.")
db = LlmAgent(name="db", model="gemini-2.5-flash", instruction="Search DB.")
parallel_native = ParallelAgent(name="dual_search", sub_agents=[web, db])

# Native: loop requires explicit wrapping
critic = LlmAgent(name="critic", model="gemini-2.5-flash", instruction="Critique.")
reviser = LlmAgent(name="reviser", model="gemini-2.5-flash", instruction="Revise.")
loop_native = LoopAgent(name="refine", max_iterations=3, sub_agents=[critic, reviser])
```

## adk-fluent

```python
from adk_fluent import Agent, Pipeline

r = Agent("researcher").model("gemini-2.5-flash").instruct("Research.")
w = Agent("writer").model("gemini-2.5-flash").instruct("Write.")
e = Agent("editor").model("gemini-2.5-flash").instruct("Edit.")

# >> creates Pipeline (SequentialAgent)
pipeline_fluent = r >> w >> e

# | creates FanOut (ParallelAgent)
web_f = Agent("web").model("gemini-2.5-flash").instruct("Search web.")
db_f = Agent("db").model("gemini-2.5-flash").instruct("Search DB.")
parallel_fluent = web_f | db_f

# * creates Loop (LoopAgent)
c = Agent("critic").model("gemini-2.5-flash").instruct("Critique.")
rv = Agent("reviser").model("gemini-2.5-flash").instruct("Revise.")
loop_fluent = (c >> rv) * 3
```

## Equivalence

```python
# Pipeline via >>
assert isinstance(pipeline_fluent, Pipeline)
built_pipeline = pipeline_fluent.build()
assert type(pipeline_native) == type(built_pipeline)
assert len(built_pipeline.sub_agents) == 3

# FanOut via |
built_parallel = parallel_fluent.build()
assert type(parallel_native) == type(built_parallel)
assert len(built_parallel.sub_agents) == 2

# Loop via *
built_loop = loop_fluent.build()
assert type(loop_native) == type(built_loop)
assert built_loop.max_iterations == 3
```
