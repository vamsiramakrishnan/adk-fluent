# Middleware: Production Middleware Stack for a Healthcare API Agent

*How to configure agents for production runtime.*

_Source: `45_middleware.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent

# Native ADK requires implementing BasePlugin with many callbacks.
# For production healthcare APIs, you need retry logic for external
# service calls, structured logging for HIPAA audit trails, and
# rate limiting -- each requiring separate plugin implementations.
agent_native = LlmAgent(
    name="patient_lookup",
    model="gemini-2.5-flash",
    instruction="Look up patient records from the EHR system.",
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, RetryMiddleware, StructuredLogMiddleware

# Scenario: A healthcare agent that queries electronic health records.
# Production requirements mandate:
#   1. Retry with exponential backoff for transient EHR API failures
#   2. Structured audit logging for HIPAA compliance

agent_fluent = (
    Agent("patient_lookup")
    .model("gemini-2.5-flash")
    .instruct("Look up patient records from the EHR system.")
    .middleware(RetryMiddleware(max_attempts=3))
    .middleware(StructuredLogMiddleware())
)
```
:::
::::

## Equivalence

```python
# Middleware is stored on the builder
assert hasattr(agent_fluent, "_middlewares")
assert len(agent_fluent._middlewares) == 2
assert isinstance(agent_fluent._middlewares[0], RetryMiddleware)
assert isinstance(agent_fluent._middlewares[1], StructuredLogMiddleware)

# .middleware() is available on any builder -- pipelines too
from adk_fluent import Pipeline

p = Pipeline("patient_workflow").middleware(RetryMiddleware())
assert len(p._middlewares) == 1
```
