# Conditional Loop Exit with loop_until

*How to create looping agent workflows.*

_Source: `20_loop_until.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in conditional loop exit. You'd need to:
#   1. Create a custom BaseAgent that evaluates a predicate
#   2. Yield Event(actions=EventActions(escalate=True)) to exit
#   3. Manually wire it into the LoopAgent's sub_agents
# This is ~30 lines of boilerplate per loop condition.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Loop

# loop_until: wraps in a loop that exits when predicate is satisfied
writer = Agent("writer").model("gemini-2.5-flash").instruct("Write a draft.").outputs("quality")
reviewer = Agent("reviewer").model("gemini-2.5-flash").instruct("Review the draft.")

refinement = (writer >> reviewer).loop_until(lambda s: s.get("quality") == "good", max_iterations=5)

# .until() on a Loop — alternative syntax
manual_loop = (
    Loop("polish")
    .step(Agent("drafter").model("gemini-2.5-flash").instruct("Draft."))
    .step(Agent("checker").model("gemini-2.5-flash").instruct("Check.").outputs("done"))
    .until(lambda s: s.get("done") == "yes")
    .max_iterations(10)
)
```
:::
::::

## Equivalence

```python
from adk_fluent.workflow import Loop as LoopBuilder

# loop_until creates a Loop builder
assert isinstance(refinement, LoopBuilder)

# The loop has _until_predicate stored for checkpoint injection at build time
assert refinement._config.get("_until_predicate") is not None
assert refinement._config.get("max_iterations") == 5

# .until() on Loop sets the predicate
assert manual_loop._config.get("_until_predicate") is not None
assert manual_loop._config.get("max_iterations") == 10

# Build verifies the checkpoint agent is injected
built = refinement.build()
# Last sub_agent should be the checkpoint
checkpoint = built.sub_agents[-1]
assert checkpoint.name == "_until_check"
```

:::{seealso}
API reference: [Loop](../api/workflow.md#builder-Loop)
:::
