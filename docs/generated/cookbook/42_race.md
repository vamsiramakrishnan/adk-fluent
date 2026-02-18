# Race: First-to-Finish Wins

*How to use race: first-to-finish wins with the fluent API.*

_Source: `42_race.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK's ParallelAgent runs all branches and merges results.
# There is no built-in "first to finish" mechanism. You'd need to:
#   1. Subclass BaseAgent
#   2. Use asyncio.create_task for each sub-agent
#   3. asyncio.wait(FIRST_COMPLETED) to get the winner
#   4. Cancel remaining tasks
# This is ~40 lines of async boilerplate.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline, race

# race(): run agents concurrently, keep only the first to finish
# Perfect for: fastest model wins, parallel strategies, timeout fallbacks
fast = Agent("fast").model("gemini-2.0-flash").instruct("Quick answer.")
thorough = Agent("thorough").model("gemini-2.5-pro").instruct("Detailed answer.")

winner = race(fast, thorough)

# Three-way race
creative = Agent("creative").model("gemini-2.5-flash").instruct("Creative answer.")
precise = Agent("precise").model("gemini-2.5-flash").instruct("Precise answer.")
concise = Agent("concise").model("gemini-2.0-flash").instruct("Brief answer.")

best_first = race(creative, precise, concise)

# Race in a pipeline
pipeline = (
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify.")
    >> race(
        Agent("strategy_a").model("gemini-2.5-flash").instruct("Strategy A."),
        Agent("strategy_b").model("gemini-2.5-flash").instruct("Strategy B."),
    )
    >> Agent("formatter").model("gemini-2.5-flash").instruct("Format result.")
)
```
:::
::::

## Equivalence

```python
from adk_fluent._base import _RaceBuilder, BuilderBase

# race() creates a _RaceBuilder
assert isinstance(winner, _RaceBuilder)
assert isinstance(winner, BuilderBase)

# Builds with correct number of sub-agents
built = winner.build()
assert len(built.sub_agents) == 2
assert built.sub_agents[0].name == "fast"
assert built.sub_agents[1].name == "thorough"

# Three-way race
built3 = best_first.build()
assert len(built3.sub_agents) == 3

# Name includes agent names
assert "fast" in winner._config["name"]
assert "thorough" in winner._config["name"]

# Composable in pipeline
assert isinstance(pipeline, Pipeline)
built_pipeline = pipeline.build()
assert len(built_pipeline.sub_agents) == 3
```
