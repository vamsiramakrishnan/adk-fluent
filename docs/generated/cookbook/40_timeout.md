# Timeout: Time-Bound Agent Execution

*How to use timeout: time-bound agent execution with the fluent API.*

_Source: `40_timeout.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in timeout mechanism. You'd need to:
#   1. Subclass BaseAgent
#   2. Run the sub-agent in an asyncio.create_task
#   3. Use asyncio.Queue to forward events with deadline tracking
#   4. Cancel the task on timeout
# This is ~40 lines of async boilerplate per timeout.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline

# .timeout(seconds): wrap any agent with a time limit
# Raises asyncio.TimeoutError if the agent exceeds the limit
fast_agent = Agent("fast_responder").model("gemini-2.5-flash").instruct("Answer quickly.").timeout(30)

# Timeout in a pipeline -- only the slow step is time-bounded
pipeline = (
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify.")
    >> Agent("researcher").model("gemini-2.5-pro").instruct("Deep research.").timeout(60)
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write summary.")
)

# Timeout on a whole pipeline
bounded_pipeline = (
    Agent("a").model("gemini-2.5-flash").instruct("Step A.") >> Agent("b").model("gemini-2.5-flash").instruct("Step B.")
).timeout(120)
```
:::
::::

## Equivalence

```python
from adk_fluent._base import _TimeoutBuilder, BuilderBase

# .timeout() returns a _TimeoutBuilder
assert isinstance(fast_agent, _TimeoutBuilder)
assert isinstance(fast_agent, BuilderBase)

# Stores the timeout duration
assert fast_agent._seconds == 30

# Builds with sub-agent
built = fast_agent.build()
assert len(built.sub_agents) == 1
assert built.sub_agents[0].name == "fast_responder"

# Name includes original agent name
assert "fast_responder" in fast_agent._config["name"]

# Composable in pipeline
assert isinstance(pipeline, Pipeline)
built_pipeline = pipeline.build()
assert len(built_pipeline.sub_agents) == 3

# Pipeline timeout
assert isinstance(bounded_pipeline, _TimeoutBuilder)
assert bounded_pipeline._seconds == 120
```
