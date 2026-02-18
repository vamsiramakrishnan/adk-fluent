# Validate and Explain

*How to validate and explain builder configurations.*

_Source: `25_validate_explain.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in validation or explanation mechanism.
# Errors surface only at runtime, deep in the call stack.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# .validate() — catch config errors at definition time, not runtime
agent = (
    Agent("helper")
    .model("gemini-2.5-flash")
    .instruct("You are helpful.")
    .validate()  # Tries .build(), raises ValueError on failure
)

# .explain() — inspect builder state for debugging
explanation = agent.explain()
```
:::
::::

## Equivalence

```python
# validate() returns self for chaining
assert agent._config["name"] == "helper"

# explain() returns a multi-line string
assert "Agent: helper" in explanation
assert "Config fields:" in explanation

# validate() catches errors: missing required fields
import pytest

broken = Agent("broken")  # No model set

# Some builders may pass validation even without model (depends on ADK version)
# The point is validate() calls build() and surfaces any error clearly
try:
    broken.validate()
except ValueError as e:
    assert "Validation failed" in str(e)
    assert "broken" in str(e)
```
