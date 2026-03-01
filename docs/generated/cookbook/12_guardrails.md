# Medical Advice Safety Guards -- Guards with .guard()

Demonstrates the .guard() method that registers a function as
both a before_model and after_model callback in one call. The
scenario: a medical information agent with safety guards that
screen requests and responses for dangerous self-diagnosis or
treatment recommendations.

:::{admonition} Why this matters
:class: important
In medical, legal, and financial domains, both the input to and output from the model must be screened for safety. A medical chatbot must block dangerous self-diagnosis prompts (before_model) AND flag treatment recommendations in responses (after_model). The `.guard()` method registers a single function as both a before and after hook, ensuring symmetric safety coverage with one call instead of two.
:::

:::{warning} Without this
Without guardrails, medical chatbots can recommend dosages, legal agents can give binding advice, and financial agents can make unauthorized trades. In native ADK, you must remember to set both `before_model_callback` AND `after_model_callback` separately -- forget one and your safety net has a hole. The `.guard()` method guarantees both sides are covered.
:::

*How to add safety guardrails with the unified .guard() method.*

_Source: `12_guardrails.py`_

::::\{tab-set}
:::\{tab-item} Native ADK

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
:::\{tab-item} adk-fluent

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
    .guard(medical_safety_screen)
)
```

:::
::::

## Equivalence

```python
assert medical_safety_screen in builder._callbacks["before_model_callback"]
assert medical_safety_screen in builder._callbacks["after_model_callback"]
```
