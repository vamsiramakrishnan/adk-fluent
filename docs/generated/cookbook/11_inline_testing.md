# Smoke-Testing a Customer Support Bot -- Inline Testing with .test() and .eval()

Demonstrates the `.test()` method for validating agent behavior during
development, and the `.eval()` / `.eval_suite()` methods for structured
evaluation using Google ADK's evaluation framework.  The scenario: a
customer support bot that is smoke-tested inline before deployment to
ensure it handles common queries correctly.

:::{admonition} Why this matters
:class: important
Agent behavior is notoriously hard to test because outputs are non-deterministic. The `.test()` method lets you define smoke tests inline with the agent definition -- right next to the code that configures the agent. For deeper evaluation, `.eval()` and `.eval_suite()` connect to ADK's evaluation framework with criteria like trajectory matching, semantic similarity, hallucination detection, and safety scoring. This catches regressions early: if a prompt change breaks expected behavior, the test fails immediately during development rather than in production.
:::

:::{warning} Without this
Without inline testing, agent validation requires separate test files with full runner setup, session management, and response parsing. This friction means most agents ship untested. When a prompt change causes the agent to stop handling billing queries, nobody notices until customers complain. Inline `.test()` makes testing a one-liner, and `.eval()` provides structured evaluation with composable criteria -- no boilerplate needed.
:::

:::{tip} What you'll learn
How to run inline smoke tests and structured evaluations on agents.
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
:::{tab-item} adk-fluent (E module eval)
```python
from adk_fluent import Agent, E

# .eval() — inline evaluation with ADK's evaluation framework.
# Returns an EvalSuite ready to .run().
# Composes with E.trajectory(), E.response_match(), E.semantic_match(),
# E.hallucination(), E.safety(), E.rubric(), E.tool_rubric(), E.custom().

builder = (
    Agent("support_bot")
    .model("gemini-2.5-flash")
    .instruct("You are a customer support agent for an e-commerce platform.")
)

# Quick inline eval — auto-selects response_match when expect= is given
suite = builder.eval("How do I return an item?", expect="return")

# Full eval suite with composable criteria
suite = (
    builder.eval_suite()
    .case("How do I return an item?", expect="return policy")
    .case("What is your refund policy?", expect="refund within 30 days")
    .case("Track my order #12345", expect="order status")
    .criteria(E.response_match(0.7) | E.safety())
    .rubric("Response must be polite and offer escalation to a human")
    .num_runs(2)
)

# Run: report = await suite.run()
# Assert: assert report.ok

# Serialize for CI: suite.to_file("support_bot.test.json")
```
:::
:::{tab-item} Native ADK
```python
# Native ADK has no inline testing. You must write separate test files
# with full Runner/Session setup for each agent test case.
# For evaluation, you manually construct EvalCase, EvalSet, EvalConfig,
# and call AgentEvaluator.evaluate_eval_set() — ~30 lines of setup.
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

# E module eval integration
assert hasattr(builder, "eval")
assert hasattr(builder, "eval_suite")

from adk_fluent._eval import EvalSuite

suite = builder.eval("What is your return policy?", expect="return")
assert isinstance(suite, EvalSuite)
assert len(suite._cases) == 1

suite2 = builder.eval_suite()
assert isinstance(suite2, EvalSuite)
```
