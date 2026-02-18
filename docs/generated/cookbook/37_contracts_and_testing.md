# Contracts and Testing

*How to verify pipeline data flow and test without LLM calls.*

_Source: n/a (v4 feature)_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in contract verification or mock testing.
# Pipeline data flow errors are discovered at runtime.
```
:::
:::{tab-item} adk-fluent
```python
from pydantic import BaseModel
from adk_fluent import Agent
from adk_fluent.testing import check_contracts, mock_backend, AgentHarness

class Intent(BaseModel):
    category: str
    confidence: float

# 1. Declare data contracts
pipeline = (
    Agent("classifier").produces(Intent)
    >> Agent("resolver").consumes(Intent)
)

# 2. Verify at build time (no LLM calls)
issues = check_contracts(pipeline.to_ir())

# 3. Test with mock responses
harness = AgentHarness(
    pipeline,
    backend=mock_backend({
        "classifier": {"category": "billing", "confidence": 0.95},
        "resolver": "Ticket #42 created.",
    })
)
# response = await harness.send("My bill is wrong")
```
:::
::::

## Equivalence

```python
# Contract verification passes
assert issues == []

# Mock backend works with the pipeline
from adk_fluent.testing import MockBackend
from adk_fluent.backends import Backend
mb = mock_backend({"a": "response"})
assert isinstance(mb, Backend)
```

## Catching Contract Violations

```python
from adk_fluent import Agent
from adk_fluent.testing import check_contracts

# Missing producer: resolver consumes Intent but nothing produces it
bad_pipeline = Agent("a") >> Agent("resolver").consumes(Intent)
issues = check_contracts(bad_pipeline.to_ir())
assert len(issues) == 2  # category and confidence missing
assert "category" in issues[0]
```

:::{seealso}
User guide: [Testing](../user-guide/testing.md)
:::
