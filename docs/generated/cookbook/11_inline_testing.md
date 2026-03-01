# Smoke-Testing a Customer Support Bot -- Inline Testing with .test()

Demonstrates the .test() method for validating agent behavior during
development.  The scenario: a customer support bot that is
smoke-tested inline before deployment to ensure it handles common
queries correctly.  No LLM calls are made here -- we verify that
the builder exposes the test API with the right signature.

:::{admonition} Why this matters
:class: important
Agent behavior is notoriously hard to test because outputs are non-deterministic. The `.test()` method lets you define smoke tests inline with the agent definition -- right next to the code that configures the agent. This catches regressions early: if a prompt change breaks expected behavior, the test fails immediately during development rather than in production.
:::

:::{warning} Without this
Without inline testing, agent validation requires separate test files with full runner setup, session management, and response parsing. This friction means most agents ship untested. When a prompt change causes the agent to stop handling billing queries, nobody notices until customers complain. Inline `.test()` makes testing a one-liner next to the agent definition.
:::

:::{tip} What you'll learn
How to run inline smoke tests on agents.
:::

_Source: `11_inline_testing.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# In production, you chain tests directly into the agent definition:
# agent = (
#     Agent("support_bot")
#     .model("gemini-2.5-flash")
#     .instruct("You are a customer support agent for an e-commerce platform.")
#     .test("How do I return an item?", contains="return")
#     .test("What is your refund policy?", contains="refund")
#     .test("Track my order #12345", contains="order")
#     .build()
# )

builder = (
    Agent("support_bot")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a customer support agent for an e-commerce platform. "
        "Handle returns, refunds, order tracking, and general inquiries. "
        "Always be polite and offer to escalate to a human if needed."
    )
)
```
:::
:::{tab-item} Native ADK
```python
# Native ADK has no inline testing. You must write separate test files
# with full Runner/Session setup for each agent test case.
```
:::
::::

## Equivalence

```python
assert hasattr(builder, "test")
assert callable(builder.test)
import inspect

sig = inspect.signature(builder.test)
assert "prompt" in sig.parameters
assert "contains" in sig.parameters
assert "matches" in sig.parameters
assert "equals" in sig.parameters
```
