# Fallback Chains: // Operator

*How to use operator syntax for composing agents.*

_Source: `32_fallback_operator.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in fallback mechanism. You'd need:
#   1. Custom BaseAgent subclass with try/except logic
#   2. Sub-agents list for each fallback tier
#   3. Manual error handling and re-delegation
# This is ~30 lines per fallback chain.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline
from adk_fluent._base import _FallbackBuilder

# // creates a fallback chain — first success wins
fast = Agent("fast").model("gemini-2.0-flash").instruct("Quick answer.")
slow = Agent("slow").model("gemini-2.5-pro").instruct("Thorough answer.")

answer = fast // slow  # Try fast first, fall back to slow

# Three-way fallback
tier1 = Agent("cache").model("gemini-2.0-flash").instruct("Check cache.")
tier2 = Agent("search").model("gemini-2.5-flash").instruct("Search for answer.")
tier3 = Agent("expert").model("gemini-2.5-pro").instruct("Deep analysis.")

resilient = tier1 // tier2 // tier3

# Composes with >> in pipelines
pipeline = (
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify request.")
    >> (fast // slow)
    >> Agent("formatter").model("gemini-2.5-flash").instruct("Format output.")
)

# Composes with | in parallel
branch_a = Agent("a1").model("gemini-2.0-flash") // Agent("a2").model("gemini-2.5-pro")
branch_b = Agent("b1").model("gemini-2.0-flash") // Agent("b2").model("gemini-2.5-pro")
parallel_fallbacks = branch_a | branch_b

# // works with functions too
fallback_with_fn = Agent("primary").model("gemini-2.5-flash").instruct("Try this.") // (
    lambda s: {"result": "static fallback"}
)
```
:::
::::

## Equivalence

```python
# // creates a _FallbackBuilder
assert isinstance(answer, _FallbackBuilder)
assert len(answer._children) == 2

# Three-way fallback has 3 children
assert len(resilient._children) == 3

# Builds to a BaseAgent with sub_agents
from google.adk.agents.base_agent import BaseAgent

built = Agent("a").model("gemini-2.5-flash").instruct("A") // Agent("b").model("gemini-2.5-pro").instruct("B")
built_agent = built.build()
assert isinstance(built_agent, BaseAgent)
assert len(built_agent.sub_agents) == 2

# Composes with >>
assert isinstance(pipeline, Pipeline)
built_pipeline = pipeline.build()
assert len(built_pipeline.sub_agents) == 3

# // with function
assert isinstance(fallback_with_fn, _FallbackBuilder)
assert len(fallback_with_fn._children) == 2
```
