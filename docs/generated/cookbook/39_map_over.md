# Map Over: Iterate an Agent Over List Items

*How to use map over: iterate an agent over list items with the fluent API.*

_Source: `39_map_over.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires a custom BaseAgent to iterate over list items:
from google.adk.agents.base_agent import BaseAgent as NativeBaseAgent
from google.adk.agents.llm_agent import LlmAgent


class MapOverAgent(NativeBaseAgent):
    """Custom agent that iterates a sub-agent over each item in a state list."""

    async def _run_async_impl(self, ctx):
        items = ctx.session.state.get("documents", [])
        results = []
        for item in items:
            ctx.session.state["_item"] = item
            async for event in self.sub_agents[0].run_async(ctx):
                yield event
            results.append(ctx.session.state.get("_item", None))
        ctx.session.state["summaries"] = results


summarizer = LlmAgent(
    name="summarizer",
    model="gemini-2.5-flash",
    instruction="Summarize the document in _item.",
)
native_mapper = MapOverAgent(name="mapper", sub_agents=[summarizer])
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline, map_over

# map_over(): iterate an agent over each item in a state list
# For each item in state["documents"], runs the summarizer agent
mapper = map_over(
    "documents",
    Agent("summarizer").model("gemini-2.5-flash").instruct("Summarize the document in _item."),
    output_key="summaries",
)

# Custom item_key and output_key
custom_mapper = map_over(
    "emails",
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify the email in _current."),
    item_key="_current",
    output_key="classifications",
)

# map_over in a pipeline
pipeline = (
    Agent("fetcher").model("gemini-2.5-flash").instruct("Fetch documents.").outputs("documents")
    >> map_over("documents", Agent("summarizer").model("gemini-2.5-flash").instruct("Summarize."))
    >> Agent("compiler").model("gemini-2.5-flash").instruct("Compile summaries.")
)
```
:::
::::

## Equivalence

```python
from adk_fluent._base import _MapOverBuilder, BuilderBase

# map_over returns a _MapOverBuilder
assert isinstance(mapper, _MapOverBuilder)
assert isinstance(mapper, BuilderBase)

# Stores configuration
assert mapper._list_key == "documents"
assert mapper._item_key == "_item"
assert mapper._output_key == "summaries"

# Custom keys
assert custom_mapper._list_key == "emails"
assert custom_mapper._item_key == "_current"
assert custom_mapper._output_key == "classifications"

# Builds with sub-agent
built = mapper.build()
assert len(built.sub_agents) == 1
assert built.sub_agents[0].name == "summarizer"

# Composable in pipeline
assert isinstance(pipeline, Pipeline)
built_pipeline = pipeline.build()
assert len(built_pipeline.sub_agents) == 3

# Name includes the key
assert "documents" in mapper._config["name"]
```
