# Conditional Gating with proceed_if

_Source: `19_conditional_gating.py`_

## Native ADK

```python
# Native ADK requires manually implementing before_agent_callback
# that returns Content to skip an agent:
#
#   from google.genai import types
#
#   def gate(callback_context):
#       if callback_context.state.get("valid") != "yes":
#           return types.Content(role="model", parts=[])
#       return None
#
#   agent = LlmAgent(
#       name="enricher", model="gemini-2.5-flash",
#       instruction="Enrich the data.",
#       before_agent_callback=gate,
#   )
```

## adk-fluent

```python
from adk_fluent import Agent

# proceed_if: only runs if predicate(state) is truthy
enricher = (
    Agent("enricher")
    .model("gemini-2.5-flash")
    .instruct("Enrich the validated data.")
    .proceed_if(lambda s: s.get("valid") == "yes")
)

# Chain proceed_if in a pipeline: skip steps based on state
validator = Agent("validator").model("gemini-2.5-flash").instruct("Validate input.").outputs("valid")
formatter = (
    Agent("formatter")
    .model("gemini-2.5-flash")
    .instruct("Format the output.")
    .proceed_if(lambda s: s.get("valid") == "yes")
)

pipeline = validator >> enricher >> formatter
```

## Equivalence

```python
# proceed_if registers a before_agent_callback
assert len(enricher._callbacks["before_agent_callback"]) == 1
assert len(formatter._callbacks["before_agent_callback"]) == 1

# The callback is a closure that checks state
cb = enricher._callbacks["before_agent_callback"][0]

# Simulate: callback returns None (proceed) when state matches
class FakeCtx:
    def __init__(self, state_dict):
        self.state = state_dict

result = cb(FakeCtx({"valid": "yes"}))
assert result is None  # Proceed

# Simulate: callback returns Content (skip) when state doesn't match
result = cb(FakeCtx({"valid": "no"}))
assert result is not None  # Skip
```
