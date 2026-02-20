# Analytics Data Quality: State Contract Assertions with expect()

*How to work with state keys and state transforms.*

_Source: `36_expect_assertions.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires a custom BaseAgent to assert state contracts.
# In a data analytics pipeline, every quality gate is a full class:
from google.adk.agents.base_agent import BaseAgent as NativeBaseAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent


class AssertMetricsExist(NativeBaseAgent):
    """Custom agent that raises if 'metrics' is missing from state."""

    async def _run_async_impl(self, ctx):
        if "metrics" not in ctx.session.state:
            raise ValueError("Metrics must be computed before dashboard generation")
        # yield nothing


collector = LlmAgent(name="collector", model="gemini-2.5-flash", instruction="Collect raw analytics data.")
checker = AssertMetricsExist(name="checker")
dashboard = LlmAgent(name="dashboard", model="gemini-2.5-flash", instruction="Generate the dashboard.")

pipeline_native = SequentialAgent(name="pipeline", sub_agents=[collector, checker, dashboard])
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline, expect

# expect(): assert a state contract at a pipeline step.
# In analytics, data quality gates prevent garbage-in-garbage-out.
analytics_pipeline = (
    Agent("metric_calculator")
    .model("gemini-2.5-flash")
    .instruct("Compute key business metrics: revenue, churn rate, and LTV from raw data.")
    .outputs("metrics")
    >> expect(lambda s: "metrics" in s, "Metrics must be computed before dashboard generation")
    >> Agent("dashboard_generator")
    .model("gemini-2.5-flash")
    .instruct("Generate an executive dashboard with charts and insights from the metrics.")
)

# Multiple quality gates in a data pipeline — catch issues at each stage
validated_pipeline = (
    Agent("data_ingester")
    .model("gemini-2.5-flash")
    .instruct("Ingest raw event data from the warehouse and extract user behavior events.")
    >> expect(lambda s: "events" in s, "Ingestion must produce events data")
    >> Agent("aggregator")
    .model("gemini-2.5-flash")
    .instruct("Aggregate events into daily/weekly/monthly cohort metrics.")
    >> expect(lambda s: len(s.get("events", "")) > 0, "Events data must not be empty after aggregation")
    >> Agent("report_builder")
    .model("gemini-2.5-flash")
    .instruct("Build the final analytics report with trend analysis and recommendations.")
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
assert isinstance(analytics_pipeline, Pipeline)
built = analytics_pipeline.build()
assert len(built.sub_agents) == 3

# The internal function raises ValueError on failure
e_fail = expect(lambda s: False, "Data quality check failed: missing required fields")
with pytest.raises(ValueError, match="Data quality check failed"):
    e_fail._fn({})

# The internal function passes silently on success
e_pass = expect(lambda s: "revenue" in s)
result = e_pass._fn({"revenue": 42000})
assert result == {}

# Default message
e_default = expect(lambda s: False)
with pytest.raises(ValueError, match="State assertion failed"):
    e_default._fn({})
```
