# Medical Advice Safety Guardrails -- Guardrails with .guardrail()

Demonstrates the .guardrail() method that registers a function as
both a before_model and after_model callback in one call.  The
scenario: a medical information agent with safety guardrails that
screen requests and responses for dangerous self-diagnosis or
treatment recommendations.

*How to register lifecycle callbacks with accumulation semantics.*

_Source: `12_guardrails.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent


def medical_safety_screen(callback_context, llm_request):
    """Screen for dangerous medical advice in both requests and responses.

    Checks for self-medication dosage instructions, diagnostic claims
    without disclaimers, and emergency situations that need 911.
    """
    return None


# In native ADK, you must register the same function twice:
agent_native = LlmAgent(
    name="medical_info",
    model="gemini-2.5-flash",
    instruction=(
        "You provide general health and wellness information. "
        "Always include a disclaimer that you are not a doctor. "
        "Never prescribe medication or provide specific dosages. "
        "For emergencies, direct users to call emergency services."
    ),
    before_model_callback=medical_safety_screen,
    after_model_callback=medical_safety_screen,
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# One call registers both before and after:
builder = (
    Agent("medical_info")
    .model("gemini-2.5-flash")
    .instruct(
        "You provide general health and wellness information. "
        "Always include a disclaimer that you are not a doctor. "
        "Never prescribe medication or provide specific dosages. "
        "For emergencies, direct users to call emergency services."
    )
    .guardrail(medical_safety_screen)
)
```
:::
::::

## Equivalence

```python
assert medical_safety_screen in builder._callbacks["before_model_callback"]
assert medical_safety_screen in builder._callbacks["after_model_callback"]
```
