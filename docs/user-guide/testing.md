# Testing

adk-fluent provides testing utilities for verifying agent pipelines without making LLM calls. Testing agents is fundamentally different from testing regular code -- you're testing *topology*, *data flow*, and *contracts*, not just input/output.

## Why Test Agents?

Without testing, you only discover broken pipelines in production:

- A `.writes("intent")` typo becomes `.writes("intnt")` and the downstream agent reads `None`
- A context strategy change (`C.none()` removed) causes a classifier to hallucinate based on conversation history
- A new agent added to a pipeline doesn't satisfy the next step's data contract

adk-fluent's testing tools catch these at build time, not runtime.

## Testing Layers

| Layer | Tool | What it catches | LLM calls? |
|---|---|---|---|
| **Contracts** | `check_contracts()` | Data flow mismatches between agents | No |
| **Topology** | `.to_ir()` + assertions | Missing agents, wrong wiring | No |
| **Behavior** | `AgentHarness` + `mock_backend` | Wrong responses, missing state | No |
| **Smoke** | `.test()` | Basic end-to-end correctness | Yes |
| **Evaluation** | `.eval()` / `EvalSuite` | Quality, consistency, regression | Yes |

Start from the top and work down. Each layer catches cheaper errors before you burn API tokens.

## Contract Verification

`check_contracts()` is the cheapest test you can write. It inspects the IR tree -- no execution, no API calls -- and verifies that sequential agents satisfy each other's data contracts:

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

:::{tip} Best Practice
Add contract checks to every pipeline test. They cost nothing and catch the most common production bugs -- renamed state keys and missing data flow.
:::

## Mock Backend

`mock_backend()` creates a backend that returns canned responses, letting you test pipeline behavior deterministically:

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

### Response Types

| Mock value | Behavior | Use case |
|---|---|---|
| `str` | Agent returns this text as content | Simple response assertions |
| `dict` | Agent writes these keys to state | Data flow testing |
| `callable` | Called with `(prompt, state)`, returns `str` or `dict` | Dynamic/conditional responses |

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

### Testing Multi-Agent Pipelines

```python
from adk_fluent import Agent, C
from adk_fluent.testing import AgentHarness, mock_backend

pipeline = (
    Agent("classifier").instruct("Classify.").context(C.none()).writes("intent")
    >> Agent("resolver").instruct("Resolve {intent}.")
)

harness = AgentHarness(
    pipeline,
    backend=mock_backend({
        "classifier": {"intent": "billing"},
        "resolver": "Your billing issue has been resolved.",
    })
)

response = await harness.send("My bill is wrong")
assert response.final_text == "Your billing issue has been resolved."
```

## pytest Integration

Use these tools in standard pytest tests:

```python
import pytest
from adk_fluent import Agent, C
from adk_fluent.testing import check_contracts, mock_backend, AgentHarness


def test_contracts_satisfied():
    """Contract checks are cheap -- run on every pipeline."""
    pipeline = build_my_pipeline()
    issues = check_contracts(pipeline.to_ir())
    assert not issues, f"Contract violations: {issues}"


def test_topology():
    """Verify the pipeline has the right shape."""
    ir = build_my_pipeline().to_ir()
    agent_names = [node.name for node in ir.walk()]
    assert "classifier" in agent_names
    assert "resolver" in agent_names


@pytest.mark.asyncio
async def test_pipeline_response():
    """Behavior test with mock backend."""
    harness = AgentHarness(
        build_my_pipeline(),
        backend=mock_backend({"step1": "data", "step2": "result"})
    )
    response = await harness.send("test input")
    assert "result" in response.final_text


@pytest.mark.asyncio
async def test_state_propagation():
    """Verify data flows correctly through state keys."""
    harness = AgentHarness(
        build_my_pipeline(),
        backend=mock_backend({
            "classifier": {"intent": "billing"},
            "resolver": "Resolved.",
        })
    )
    response = await harness.send("test")
    assert response.state.get("intent") == "billing"
```

### Test Organization

```
tests/
    test_contracts.py       # Contract checks for all pipelines (fast, no API)
    test_topology.py        # IR shape assertions (fast, no API)
    test_behavior.py        # Mock backend tests (fast, no API)
    test_smoke.py           # .test() with real LLM (slow, requires API key)
    test_eval.py            # .eval() quality checks (slow, requires API key)
```

## Interplay with Other Modules

### Testing + Contracts (`.produces()` / `.consumes()`)

Contract annotations power `check_contracts()`. Without them, you're relying on runtime failures:

```python
from pydantic import BaseModel
from adk_fluent import Agent
from adk_fluent.testing import check_contracts

class AnalysisResult(BaseModel):
    summary: str
    confidence: float

# Annotate your agents with contracts
pipeline = (
    Agent("analyzer").produces(AnalysisResult).writes("analysis")
    >> Agent("writer").consumes(AnalysisResult)
)

# check_contracts() uses the annotations to verify data flow
issues = check_contracts(pipeline.to_ir())
assert not issues
```

See [Structured Data](structured-data.md) for contract details.

### Testing + Context Engineering

Context strategy bugs are invisible without testing. A classifier with `C.none()` removed will still "work" but produce worse results because it hallucinates based on conversation history:

```python
def test_classifier_context_isolation():
    """Verify the classifier doesn't see conversation history."""
    ir = build_my_pipeline().to_ir()
    classifier_node = next(n for n in ir.walk() if n.name == "classifier")
    # The classifier should have context isolation
    assert classifier_node.include_contents == "none"
```

See [Context Engineering](context-engineering.md).

### Testing + Guards

Guards compile to callbacks. Test that they're attached:

```python
from adk_fluent import Agent, G

agent = Agent("safe").instruct("Help.").guard(G.pii("redact") | G.length(max=500))
ir = agent.to_ir()
assert ir.guard_specs  # Guards are attached
```

See [Guards](guards.md).

### Testing + Middleware

Middleware applies at the app level. Test it via `.to_app()`:

```python
from adk_fluent import Agent
from adk_fluent._middleware import M

pipeline = (Agent("a") >> Agent("b")).middleware(M.retry(3) | M.log())
app = pipeline.to_app()
# Verify middleware is compiled into the app
assert app.plugins  # Middleware plugin is attached
```

See [Middleware](middleware.md).

## Best Practices

1. **Always test contracts first.** `check_contracts()` is free and catches the most common bugs
2. **Mock everything in CI.** Never call real LLMs in CI -- use `mock_backend()` for deterministic tests
3. **Test topology, not just behavior.** Assert that agents exist, are wired correctly, and have the right context strategy
4. **Separate fast and slow tests.** Contract/topology/mock tests run in milliseconds. `.test()` and `.eval()` require API calls -- gate these behind a marker or env var
5. **Test state propagation explicitly.** Assert that `.writes()` keys appear in downstream state, not just that the final response looks right

:::{seealso}
- [Structured Data](structured-data.md) -- `.produces()`, `.consumes()`, and contract annotations
- [Context Engineering](context-engineering.md) -- `C.none()`, `C.from_state()`, and why context isolation matters for testing
- [Guards](guards.md) -- `G.pii()`, `G.length()`, and safety validation
- [Middleware](middleware.md) -- `M.retry()`, `M.log()`, and app-level middleware
- [Evaluation](evaluation.md) -- `E.case()`, `EvalSuite`, and quality assessment
- [Error Reference](error-reference.md) -- every error with fix-it examples
:::
