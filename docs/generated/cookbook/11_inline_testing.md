# Inline Testing with .test()

*How to run inline smoke tests on agents.*

_Source: `11_inline_testing.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no inline testing. You must write separate test files
# with full Runner/Session setup for each agent test.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# Chain tests directly into agent definition:
# agent = (
#     Agent("qa").model("gemini-2.5-flash")
#     .instruct("Answer math questions.")
#     .test("What is 2+2?", contains="4")
#     .test("What is 10*10?", contains="100")
#     .build()
# )

builder = Agent("qa").model("gemini-2.5-flash").instruct("Answer math.")
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

## Deterministic Testing with Mock Backend

For comprehensive testing without LLM calls, use `mock_backend` and `AgentHarness`:

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires full Runner/Session setup and actual LLM calls
# for testing, or complex mocking of the LLM client.
```
:::
:::{tab-item} adk-fluent
```python
import asyncio
from adk_fluent import Agent
from adk_fluent.testing import mock_backend, AgentHarness

pipeline = Agent("classifier").instruct("Classify.") >> Agent("resolver").instruct("Resolve.")

# Mock backend returns canned responses per agent name
harness = AgentHarness(
    pipeline,
    backend=mock_backend({
        "classifier": {"intent": "billing"},
        "resolver": "Ticket created.",
    })
)

# async def test_pipeline():
#     response = await harness.send("My bill is wrong")
#     assert response.final_text == "Ticket created."
#     assert not response.errors
```
:::
::::

```python
from adk_fluent.testing import mock_backend, AgentHarness, check_contracts
assert callable(mock_backend)
assert AgentHarness is not None
assert callable(check_contracts)
```
