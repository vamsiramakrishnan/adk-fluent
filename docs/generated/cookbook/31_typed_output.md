# Typed Output Contracts: @ Operator

*How to use operator syntax for composing agents.*

_Source: `31_typed_output.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from pydantic import BaseModel


class ReportSchema(BaseModel):
    title: str
    body: str
    confidence: float


# Native: pass output_schema directly
writer_native = LlmAgent(
    name="writer",
    model="gemini-2.5-flash",
    instruction="Write a report.",
    output_schema=ReportSchema,
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline

# @ binds a Pydantic model as the output schema
writer_fluent = (
    Agent("writer")
    .model("gemini-2.5-flash")
    .instruct("Write a report.")
    @ ReportSchema
)

# @ is immutable — original unchanged
base = Agent("base").model("gemini-2.5-flash").instruct("Analyze.")
typed = base @ ReportSchema
# base has no schema, typed does


class SummarySchema(BaseModel):
    summary: str
    key_points: list[str]


# Composes with >> — typed agent feeds into pipeline
pipeline = (
    Agent("researcher").model("gemini-2.5-flash").instruct("Research the topic.")
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write summary.") @ SummarySchema
    >> Agent("editor").model("gemini-2.5-flash").instruct("Polish the summary.")
)

# @ preserves all existing config
detailed = (
    Agent("analyst")
    .model("gemini-2.5-flash")
    .instruct("Analyze data thoroughly.")
    .outputs("analysis")
    @ ReportSchema
)
```
:::
::::

## Equivalence

```python
# @ wires into ADK's native output_schema
built = writer_fluent.build()
assert built.output_schema is ReportSchema
assert writer_native.output_schema is ReportSchema

# Original unchanged (immutable)
assert "_output_schema" not in base._config
assert typed._config["_output_schema"] is ReportSchema

# Composes with >>
assert isinstance(pipeline, Pipeline)

# Preserves config
assert detailed._config["instruction"] == "Analyze data thoroughly."
assert detailed._config["output_key"] == "analysis"
assert detailed._config["_output_schema"] is ReportSchema
```
