# Expect: State Contract Assertions in Pipelines

*How to compose agents into a sequential pipeline.*

_Source: `36_expect_assertions.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires a custom BaseAgent to assert state contracts:
from google.adk.agents.base_agent import BaseAgent as NativeBaseAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent


class AssertDraftExists(NativeBaseAgent):
    """Custom agent that raises if 'draft' is missing from state."""

    async def _run_async_impl(self, ctx):
        if "draft" not in ctx.session.state:
            raise ValueError("Draft must exist before review")
        # yield nothing


writer = LlmAgent(name="writer", model="gemini-2.5-flash", instruction="Write a draft.")
checker = AssertDraftExists(name="checker")
reviewer = LlmAgent(name="reviewer", model="gemini-2.5-flash", instruction="Review the draft.")

pipeline_native = SequentialAgent(name="pipeline", sub_agents=[writer, checker, reviewer])
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline, expect

# expect(): assert a state contract at a pipeline step
# Raises ValueError with your message if predicate fails
pipeline_fluent = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write a draft.").outputs("draft")
    >> expect(lambda s: "draft" in s, "Draft must exist before review")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review the draft.")
)

# Multiple expectations in a pipeline
validated_pipeline = (
    Agent("extractor").model("gemini-2.5-flash").instruct("Extract entities.")
    >> expect(lambda s: "entities" in s, "Extraction must produce entities")
    >> Agent("enricher").model("gemini-2.5-flash").instruct("Enrich entities.")
    >> expect(lambda s: len(s.get("entities", "")) > 0, "Entities must not be empty")
    >> Agent("formatter").model("gemini-2.5-flash").instruct("Format output.")
)
```
:::
::::

## Equivalence

```python
import pytest

# expect() creates a builder
e = expect(lambda s: True, "test msg")
assert hasattr(e, "build")

# >> expect() creates a Pipeline
assert isinstance(pipeline_fluent, Pipeline)
built = pipeline_fluent.build()
assert len(built.sub_agents) == 3

# The internal function raises ValueError on failure
e_fail = expect(lambda s: False, "Custom error message")
with pytest.raises(ValueError, match="Custom error message"):
    e_fail._fn({})

# The internal function passes silently on success
e_pass = expect(lambda s: "key" in s)
result = e_pass._fn({"key": "value"})
assert result == {}

# Default message
e_default = expect(lambda s: False)
with pytest.raises(ValueError, match="State assertion failed"):
    e_default._fn({})
```
