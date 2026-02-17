# Function Steps: Plain Functions as Workflow Nodes (>> fn)

*How to use plain functions as pipeline steps.*

_Source: `29_function_steps.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires subclassing BaseAgent for any custom logic node:
from google.adk.agents.base_agent import BaseAgent as NativeBaseAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent


class MergeResearch(NativeBaseAgent):
    """Custom agent just to merge two state keys."""
    async def _run_async_impl(self, ctx):
        web = ctx.session.state.get("web_results", "")
        papers = ctx.session.state.get("paper_results", "")
        ctx.session.state["research"] = web + "\n" + papers
        # yield nothing


researcher = LlmAgent(name="researcher", model="gemini-2.5-flash", instruction="Research.")
merger = MergeResearch(name="merge")
writer = LlmAgent(name="writer", model="gemini-2.5-flash", instruction="Write.")

pipeline_native = SequentialAgent(
    name="pipeline", sub_agents=[researcher, merger, writer]
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline

# Plain function — receives state dict, returns dict of updates
def merge_research(state):
    return {"research": state.get("web_results", "") + "\n" + state.get("paper_results", "")}

# >> fn: function becomes a zero-cost workflow node (no LLM call)
pipeline_fluent = (
    Agent("researcher").model("gemini-2.5-flash").instruct("Research.")
    >> merge_research
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write.")
)

# Named functions keep their name as the agent name
def trim_to_500(state):
    return {"summary": state.get("text", "")[:500]}

trimmed = Agent("a").model("gemini-2.5-flash") >> trim_to_500

# Lambdas get auto-generated names (fn_step_N)
pipeline_with_lambda = (
    Agent("a").model("gemini-2.5-flash")
    >> (lambda s: {"upper": s.get("text", "").upper()})
    >> Agent("b").model("gemini-2.5-flash")
)

# fn >> agent also works (via __rrshift__)
preprocess = lambda s: {"cleaned": s.get("raw", "").strip()}
reversed_pipeline = preprocess >> Agent("processor").model("gemini-2.5-flash")
```
:::
::::

## Equivalence

```python
# >> fn creates a Pipeline
assert isinstance(pipeline_fluent, Pipeline)
built = pipeline_fluent.build()
assert len(built.sub_agents) == 3

# Named functions use their name
built_trimmed = trimmed.build()
assert built_trimmed.sub_agents[1].name == "trim_to_500"

# Lambda gets a valid identifier name
built_lambda = pipeline_with_lambda.build()
name = built_lambda.sub_agents[1].name
assert name.isidentifier()  # Not "<lambda>"

# fn >> agent works
assert isinstance(reversed_pipeline, Pipeline)
built_rev = reversed_pipeline.build()
assert len(built_rev.sub_agents) == 2
```
