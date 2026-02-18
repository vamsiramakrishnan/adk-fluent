# Capture and Route: S.capture >> Agent >> Route

*How to implement conditional routing and branching.*

_Source: `50_capture_and_route.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires a custom BaseAgent subclass to capture user input
# into session state, and manual routing logic.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, S
from adk_fluent._routing import Route
from adk_fluent._base import CaptureAgent

MODEL = "gemini-2.5-flash"

# S.capture() bridges user message into session state
pipeline = (
    S.capture("user_message")
    >> Agent("classifier")
        .model(MODEL)
        .instruct("Classify the user's intent.")
        .outputs("intent")
    >> Route("intent")
        .eq("booking",
            Agent("booker").model(MODEL).instruct("Help book: {user_message}"))
        .eq("info",
            Agent("info").model(MODEL).instruct("Provide info: {user_message}"))
)

built = pipeline.build()
```
:::
::::

## Equivalence

```python
# First sub-agent is a CaptureAgent
assert isinstance(built.sub_agents[0], CaptureAgent)
assert built.sub_agents[0].name == "capture_user_message"

# Classifier is the second agent
assert built.sub_agents[1].name == "classifier"

# Pipeline builds without errors
assert built is not None
assert len(built.sub_agents) >= 3
```
