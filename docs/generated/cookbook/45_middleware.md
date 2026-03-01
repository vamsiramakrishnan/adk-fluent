# Middleware: Production Middleware Stack for a Healthcare API Agent

:::{admonition} Why this matters
:class: important
Production agents need cross-cutting concerns: retry with exponential backoff for transient failures, structured audit logging for HIPAA compliance, cost tracking for budget management. These concerns apply to every agent in the pipeline but have nothing to do with the agent's core logic. Middleware separates operational concerns from business logic, applying them uniformly without modifying individual agents.
:::

:::{warning} Without this
Without middleware, retry logic, logging, and compliance hooks are scattered across individual agent callbacks. Adding audit logging to a 10-agent pipeline means modifying 10 agents. Miss one and you have a compliance gap. Middleware applies the concern once and it covers the entire pipeline automatically.
:::

:::{tip} What you'll learn
How to build production middleware stacks for retry, logging, and compliance.
:::

_Source: `45_middleware.py`_

::::{tab-set}
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
