# Medical Diagnosis Agent: Validate Config and Explain Builder State

*How to work with state keys and state transforms.*

_Source: `25_validate_explain.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in validation or explanation mechanism.
# A misconfigured medical AI agent would only surface errors at runtime,
# deep in the call stack — unacceptable for healthcare applications.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# In a hospital system, we build a diagnosis assistant that must be
# validated before deployment. .validate() catches config errors at
# definition time, not when a patient is waiting for results.
diagnosis_agent = (
    Agent("diagnosis_assistant")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a medical diagnosis assistant. Given patient symptoms, "
        "lab results, and medical history, provide a differential diagnosis "
        "ranked by likelihood. Always include severity assessment."
    )
    .outputs("diagnosis")
    .validate()  # Tries .build(), raises ValueError on failure
)

# .explain() — before deploying to production, the DevOps team inspects
# the builder state to verify the agent is configured correctly.
explanation = diagnosis_agent.explain()
```
:::
::::

## Equivalence

```python
# validate() returns self for chaining
assert diagnosis_agent._config["name"] == "diagnosis_assistant"

# explain() returns a multi-line string with builder internals
assert "Agent: diagnosis_assistant" in explanation
assert "Config fields:" in explanation

# validate() catches errors: missing required fields
import pytest

broken = Agent("broken_triage")  # No model set

# Some builders may pass validation even without model (depends on ADK version)
# The point is validate() calls build() and surfaces any error clearly
try:
    broken.validate()
except ValueError as e:
    assert "Validation failed" in str(e)
    assert "broken_triage" in str(e)
```
