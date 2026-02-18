# Testing

adk-fluent provides testing utilities for verifying agent pipelines without making LLM calls.

## Mock Backend

`mock_backend()` creates a backend that returns canned responses:

```python
from adk_fluent import Agent
from adk_fluent.testing import mock_backend

mb = mock_backend({
    "classifier": {"intent": "billing"},      # dict -> state_delta
    "resolver": "Ticket #1234 created.",       # str -> content
})

ir = (Agent("classifier") >> Agent("resolver")).to_ir()
compiled = mb.compile(ir)
events = await mb.run(compiled, "My bill is wrong")

# Events contain the canned responses
assert events[0].state_delta == {"intent": "billing"}
assert events[1].content == "Ticket #1234 created."
```

## AgentHarness

`AgentHarness` wraps a builder and mock backend for ergonomic testing:

```python
from adk_fluent import Agent
from adk_fluent.testing import AgentHarness, mock_backend

harness = AgentHarness(
    Agent("helper").instruct("Help."),
    backend=mock_backend({"helper": "I can help!"})
)

response = await harness.send("Hi")
assert response.final_text == "I can help!"
assert not response.errors
```

## Contract Verification

`check_contracts()` verifies that sequential agents satisfy each other's data contracts:

```python
from pydantic import BaseModel
from adk_fluent import Agent
from adk_fluent.testing import check_contracts

class Intent(BaseModel):
    category: str
    confidence: float

# Valid: classifier produces what resolver consumes
pipeline = Agent("classifier").produces(Intent) >> Agent("resolver").consumes(Intent)
issues = check_contracts(pipeline.to_ir())
assert issues == []  # All good

# Invalid: resolver consumes Intent but nothing produces it
bad_pipeline = Agent("a") >> Agent("resolver").consumes(Intent)
issues = check_contracts(bad_pipeline.to_ir())
# ["Agent 'resolver' consumes key 'category' but no prior step produces it",
#  "Agent 'resolver' consumes key 'confidence' but no prior step produces it"]
```

Contract verification is static -- it inspects the IR tree without executing anything.

## pytest Integration

Use these tools in standard pytest tests:

```python
import pytest
from adk_fluent import Agent
from adk_fluent.testing import check_contracts, mock_backend, AgentHarness

def test_contracts_satisfied():
    pipeline = build_my_pipeline()
    issues = check_contracts(pipeline.to_ir())
    assert not issues, f"Contract violations: {issues}"

@pytest.mark.asyncio
async def test_pipeline_response():
    harness = AgentHarness(
        build_my_pipeline(),
        backend=mock_backend({"step1": "data", "step2": "result"})
    )
    response = await harness.send("test input")
    assert "result" in response.final_text
```
