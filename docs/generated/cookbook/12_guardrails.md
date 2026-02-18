# Guardrails with .guardrail()

*How to attach guardrails to agent model calls.*

_Source: `12_guardrails.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent


def pii_filter(callback_context, llm_request):
    """Filter PII from requests."""
    return None


# In native ADK, you must register the same function twice:
agent_native = LlmAgent(
    name="secure",
    model="gemini-2.5-flash",
    instruction="Be secure.",
    before_model_callback=pii_filter,
    after_model_callback=pii_filter,
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# One call registers both before and after:
builder = Agent("secure").model("gemini-2.5-flash").instruct("Be secure.").guardrail(pii_filter)
```
:::
::::

## Equivalence

```python
assert pii_filter in builder._callbacks["before_model_callback"]
assert pii_filter in builder._callbacks["after_model_callback"]
```
