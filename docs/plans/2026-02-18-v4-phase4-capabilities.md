# Phase 4: New Capabilities Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add produces/consumes contracts, ToolConfirmation, Resource DI, mock testing, and graph visualization to adk-fluent.

**Architecture:** Phase 4 builds on the IR + Backend foundation from Phase 2-3. Each feature is independent: contract checking reads IR nodes, DI wraps tool callables, mock backend replaces ADKBackend, visualization walks the IR tree. All features are additive — no existing behavior changes.

**Tech Stack:** Python 3.10+, dataclasses, Pydantic (for schema introspection), google-adk 1.25.0

______________________________________________________________________

### Task 1: `.produces()` / `.consumes()` on builders + IR wiring

**Files:**

- Modify: `src/adk_fluent/_base.py` (add `produces()` and `consumes()` methods to BuilderBase)
- Modify: `src/adk_fluent/agent.py` (wire through `to_ir()`)
- Modify: `src/adk_fluent/workflow.py` (wire through `to_ir()` on Pipeline/FanOut/Loop)
- Test: `tests/manual/test_contracts.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_contracts.py
"""Tests for produces/consumes inter-agent contracts."""
import pytest
from pydantic import BaseModel


class Intent(BaseModel):
    category: str
    confidence: float


class Resolution(BaseModel):
    ticket_id: str
    status: str


def test_produces_sets_writes_keys():
    """Agent.produces(Schema) populates writes_keys from schema fields."""
    from adk_fluent import Agent
    a = Agent("classifier").produces(Intent)
    ir = a.to_ir()
    assert ir.writes_keys == frozenset({"category", "confidence"})
    assert ir.produces_type is Intent


def test_consumes_sets_reads_keys():
    """Agent.consumes(Schema) populates reads_keys from schema fields."""
    from adk_fluent import Agent
    a = Agent("resolver").consumes(Intent)
    ir = a.to_ir()
    assert ir.reads_keys == frozenset({"category", "confidence"})
    assert ir.consumes_type is Intent


def test_produces_and_consumes_together():
    """An agent can both produce and consume."""
    from adk_fluent import Agent
    a = Agent("resolver").consumes(Intent).produces(Resolution)
    ir = a.to_ir()
    assert ir.reads_keys == frozenset({"category", "confidence"})
    assert ir.writes_keys == frozenset({"ticket_id", "status"})


def test_produces_returns_self():
    """Produces is chainable."""
    from adk_fluent import Agent
    a = Agent("a")
    result = a.produces(Intent)
    assert result is a


def test_consumes_returns_self():
    """Consumes is chainable."""
    from adk_fluent import Agent
    a = Agent("a")
    result = a.consumes(Intent)
    assert result is a


def test_pipeline_to_ir_propagates_contracts():
    """Pipeline children preserve their contract annotations."""
    from adk_fluent import Agent
    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    ir = pipeline.to_ir()
    child_a = ir.children[0]
    child_b = ir.children[1]
    assert child_a.writes_keys == frozenset({"category", "confidence"})
    assert child_b.reads_keys == frozenset({"category", "confidence"})


def test_produces_with_non_pydantic_raises():
    """produces() rejects non-Pydantic types."""
    from adk_fluent import Agent
    with pytest.raises(TypeError, match="Pydantic"):
        Agent("a").produces(dict)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/manual/test_contracts.py -v`
Expected: FAIL — `produces` attribute not found

**Step 3: Implement produces/consumes on BuilderBase**

In `src/adk_fluent/_base.py`, add to `BuilderBase` class (after the `middleware` method):

```python
def produces(self, schema: type) -> Self:
    """Declare the Pydantic schema this agent writes to state.

    Populates writes_keys on the IR node from the schema's fields.
    Used by check_contracts() to verify pipeline data flow.
    """
    from pydantic import BaseModel
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        raise TypeError(
            f"produces() requires a Pydantic BaseModel subclass, got {schema!r}"
        )
    self._config["_produces"] = schema
    return self

def consumes(self, schema: type) -> Self:
    """Declare the Pydantic schema this agent reads from state.

    Populates reads_keys on the IR node from the schema's fields.
    Used by check_contracts() to verify pipeline data flow.
    """
    from pydantic import BaseModel
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        raise TypeError(
            f"consumes() requires a Pydantic BaseModel subclass, got {schema!r}"
        )
    self._config["_consumes"] = schema
    return self
```

In `src/adk_fluent/agent.py`, update `to_ir()` to extract `_produces` and `_consumes`:

```python
# At end of to_ir(), before the return:
produces = self._config.get("_produces")
consumes = self._config.get("_consumes")
writes_keys = frozenset(produces.model_fields.keys()) if produces else frozenset()
reads_keys = frozenset(consumes.model_fields.keys()) if consumes else frozenset()

return AgentNode(
    ...,
    writes_keys=writes_keys,
    reads_keys=reads_keys,
    produces_type=produces,
    consumes_type=consumes,
)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/manual/test_contracts.py -v`
Expected: PASS (7 tests)

**Step 5: Run full suite**

Run: `python -m pytest tests/ --tb=short -q`
Expected: 1020+ passed

**Step 6: Commit**

```bash
git add tests/manual/test_contracts.py src/adk_fluent/_base.py src/adk_fluent/agent.py src/adk_fluent/workflow.py
git commit -m "feat: add produces/consumes contract annotations on builders"
```

______________________________________________________________________

### Task 2: `check_contracts()` utility

**Files:**

- Create: `src/adk_fluent/testing/__init__.py`
- Create: `src/adk_fluent/testing/contracts.py`
- Test: `tests/manual/test_check_contracts.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_check_contracts.py
"""Tests for check_contracts() contract verification."""
import pytest
from pydantic import BaseModel


class Intent(BaseModel):
    category: str
    confidence: float


class Resolution(BaseModel):
    ticket_id: str
    status: str


def test_valid_contract_no_issues():
    """A properly wired pipeline passes contract checking."""
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    issues = check_contracts(pipeline.to_ir())
    assert issues == []


def test_missing_producer_reports_issue():
    """If consumer expects keys that no prior step produces, report it."""
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    pipeline = Agent("a") >> Agent("b").consumes(Intent)
    issues = check_contracts(pipeline.to_ir())
    assert len(issues) >= 1
    assert "category" in issues[0] or "confidence" in issues[0]


def test_untyped_agents_no_issues():
    """Agents without contracts produce no issues."""
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    pipeline = Agent("a") >> Agent("b")
    issues = check_contracts(pipeline.to_ir())
    assert issues == []


def test_multi_step_contract_chain():
    """Chain: a.produces(Intent) >> b.consumes(Intent).produces(Resolution) >> c.consumes(Resolution)."""
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    pipeline = (
        Agent("a").produces(Intent)
        >> Agent("b").consumes(Intent).produces(Resolution)
        >> Agent("c").consumes(Resolution)
    )
    issues = check_contracts(pipeline.to_ir())
    assert issues == []


def test_partial_overlap_reports_missing():
    """If consumer needs keys only partially provided, report the missing ones."""
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts

    class Partial(BaseModel):
        category: str

    pipeline = Agent("a").produces(Partial) >> Agent("b").consumes(Intent)
    issues = check_contracts(pipeline.to_ir())
    # confidence is missing
    assert len(issues) == 1
    assert "confidence" in issues[0]


def test_check_contracts_on_non_sequence():
    """check_contracts on a single agent returns empty list."""
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    issues = check_contracts(Agent("solo").to_ir())
    assert issues == []
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/manual/test_check_contracts.py -v`
Expected: FAIL — `from adk_fluent.testing import check_contracts` fails

**Step 3: Implement check_contracts**

Create `src/adk_fluent/testing/__init__.py`:

```python
"""Testing utilities for adk-fluent."""
from adk_fluent.testing.contracts import check_contracts

__all__ = ["check_contracts"]
```

Create `src/adk_fluent/testing/contracts.py`:

```python
"""Inter-agent contract verification."""
from __future__ import annotations
from typing import Any


def check_contracts(ir_node: Any) -> list[str]:
    """Verify that sequential steps satisfy each other's read/write contracts.

    Only checks SequenceNode children. Untyped agents are ignored.
    Returns a list of human-readable issue strings (empty = pass).
    """
    from adk_fluent._ir_generated import SequenceNode

    if not isinstance(ir_node, SequenceNode):
        return []

    issues = []
    available_keys: set[str] = set()

    for child in ir_node.children:
        reads = getattr(child, "reads_keys", frozenset())
        writes = getattr(child, "writes_keys", frozenset())
        child_name = getattr(child, "name", "?")

        if reads:
            missing = reads - available_keys
            for key in sorted(missing):
                issues.append(
                    f"Agent '{child_name}' consumes key '{key}' "
                    f"but no prior step produces it"
                )

        available_keys |= writes

    return issues
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/manual/test_check_contracts.py -v`
Expected: PASS (6 tests)

**Step 5: Run full suite**

Run: `python -m pytest tests/ --tb=short -q`
Expected: 1026+ passed

**Step 6: Commit**

```bash
git add src/adk_fluent/testing/ tests/manual/test_check_contracts.py
git commit -m "feat: add check_contracts() for inter-agent data flow verification"
```

______________________________________________________________________

### Task 3: ToolConfirmation + ExecutionConfig compaction wiring

**Files:**

- Modify: `src/adk_fluent/agent.py` (update `.tool()` to accept `require_confirmation`)
- Modify: `src/adk_fluent/backends/adk.py` (wire compaction config to App)
- Test: `tests/manual/test_tool_confirmation.py`
- Test: `tests/manual/test_compaction_wiring.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_tool_confirmation.py
"""Tests for ToolConfirmation pass-through."""


def greet(name: str) -> str:
    return f"Hello, {name}!"


def test_tool_with_require_confirmation():
    """Agent.tool(fn, require_confirmation=True) wraps in FunctionTool with flag."""
    from adk_fluent import Agent
    a = Agent("a").tool(greet, require_confirmation=True)
    built = a.build()
    # The tool should be a FunctionTool with require_confirmation=True
    from google.adk.tools.function_tool import FunctionTool
    tool = built.tools[0]
    assert isinstance(tool, FunctionTool)
    assert tool.require_confirmation is True


def test_tool_without_confirmation_unchanged():
    """Agent.tool(fn) without flag still works as before."""
    from adk_fluent import Agent
    a = Agent("a").tool(greet)
    built = a.build()
    tools = built.tools
    assert len(tools) == 1


def test_tool_confirmation_chainable():
    """tool() with require_confirmation returns self."""
    from adk_fluent import Agent
    a = Agent("a")
    result = a.tool(greet, require_confirmation=True)
    assert result is a


def test_tool_confirmation_in_ir():
    """FunctionTool with confirmation is preserved through IR."""
    from adk_fluent import Agent
    from google.adk.tools.function_tool import FunctionTool
    a = Agent("a").tool(greet, require_confirmation=True)
    ir = a.to_ir()
    # IR stores the tool objects directly
    assert len(ir.tools) == 1
    assert isinstance(ir.tools[0], FunctionTool)
    assert ir.tools[0].require_confirmation is True
```

```python
# tests/manual/test_compaction_wiring.py
"""Tests for ExecutionConfig compaction wiring to ADK App."""


def test_compaction_wired_to_app():
    """ExecutionConfig.compaction produces App with events_compaction_config."""
    from adk_fluent import Agent, ExecutionConfig, CompactionConfig
    config = ExecutionConfig(
        compaction=CompactionConfig(interval=5, overlap=1)
    )
    a = Agent("a").instruct("hi")
    app = a.to_app(config=config)
    # App should have events_compaction_config set
    assert app.events_compaction_config is not None


def test_no_compaction_by_default():
    """Without compaction config, App has no events_compaction_config."""
    from adk_fluent import Agent
    a = Agent("a").instruct("hi")
    app = a.to_app()
    assert app.events_compaction_config is None


def test_compaction_interval_maps_correctly():
    """CompactionConfig fields map to ADK EventsCompactionConfig fields."""
    from adk_fluent import Agent, ExecutionConfig, CompactionConfig
    config = ExecutionConfig(
        compaction=CompactionConfig(interval=20, overlap=3)
    )
    app = Agent("a").instruct("hi").to_app(config=config)
    ecc = app.events_compaction_config
    assert ecc.compaction_interval == 20
    assert ecc.overlap_size == 3
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/manual/test_tool_confirmation.py tests/manual/test_compaction_wiring.py -v`
Expected: FAIL

**Step 3: Implement**

In `src/adk_fluent/agent.py`, update the `.tool()` method signature:

```python
def tool(self, fn_or_tool: Callable | BaseTool, *, require_confirmation: bool = False) -> Self:
    """Add a single tool (appends). Multiple .tool() calls accumulate."""
    if require_confirmation and callable(fn_or_tool) and not isinstance(fn_or_tool, BaseTool):
        from google.adk.tools.function_tool import FunctionTool
        fn_or_tool = FunctionTool(func=fn_or_tool, require_confirmation=True)
    self._lists["tools"].append(fn_or_tool)
    return self
```

In `src/adk_fluent/backends/adk.py`, update `compile()` to wire compaction:

```python
# After resumability section
if cfg.compaction:
    from google.adk.agents.run_config import EventsCompactionConfig
    app_kwargs["events_compaction_config"] = EventsCompactionConfig(
        compaction_interval=cfg.compaction.interval,
        overlap_size=cfg.compaction.overlap,
    )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/manual/test_tool_confirmation.py tests/manual/test_compaction_wiring.py -v`
Expected: PASS (7 tests)

**Step 5: Run full suite**

Run: `python -m pytest tests/ --tb=short -q`
Expected: 1033+ passed

**Step 6: Commit**

```bash
git add src/adk_fluent/agent.py src/adk_fluent/backends/adk.py tests/manual/test_tool_confirmation.py tests/manual/test_compaction_wiring.py
git commit -m "feat: add ToolConfirmation pass-through and wire compaction to App"
```

______________________________________________________________________

### Task 4: Resource DI with `_inject_resources()`

**Files:**

- Create: `src/adk_fluent/di.py`
- Modify: `src/adk_fluent/_base.py` (add `.inject()` method)
- Modify: `src/adk_fluent/__init__.py` (export)
- Test: `tests/manual/test_di.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_di.py
"""Tests for Resource DI (dependency injection)."""
import inspect
import pytest


def test_inject_resources_hides_params():
    """_inject_resources removes resource params from __signature__."""
    from adk_fluent.di import inject_resources

    def greet(name: str, db: object) -> str:
        return f"Hello {name}, db={db}"

    wrapped = inject_resources(greet, {"db": "fake_db"})
    sig = inspect.signature(wrapped)
    assert "name" in sig.parameters
    assert "db" not in sig.parameters


def test_inject_resources_provides_values():
    """Injected resources are provided at call time."""
    from adk_fluent.di import inject_resources
    import asyncio

    def greet(name: str, db: object) -> str:
        return f"Hello {name}, db={db}"

    wrapped = inject_resources(greet, {"db": "fake_db"})
    result = asyncio.get_event_loop().run_until_complete(wrapped(name="World"))
    assert result == "Hello World, db=fake_db"


def test_inject_resources_async_fn():
    """Works with async functions."""
    from adk_fluent.di import inject_resources
    import asyncio

    async def greet(name: str, db: object) -> str:
        return f"Hello {name}, db={db}"

    wrapped = inject_resources(greet, {"db": "fake_db"})
    result = asyncio.get_event_loop().run_until_complete(wrapped(name="World"))
    assert result == "Hello World, db=fake_db"


def test_inject_preserves_tool_context():
    """tool_context param is never injected even if in resources."""
    from adk_fluent.di import inject_resources

    def tool_fn(query: str, tool_context: object) -> str:
        return "ok"

    wrapped = inject_resources(tool_fn, {"tool_context": "bad"})
    sig = inspect.signature(wrapped)
    assert "tool_context" in sig.parameters


def test_inject_no_overlap_passthrough():
    """If no params match resources, return unchanged."""
    from adk_fluent.di import inject_resources

    def greet(name: str) -> str:
        return f"Hello {name}"

    wrapped = inject_resources(greet, {"db": "fake"})
    sig = inspect.signature(wrapped)
    assert "name" in sig.parameters


def test_builder_inject_method():
    """Agent.inject(key=value) stores resources for DI."""
    from adk_fluent import Agent

    a = Agent("a").inject(db="fake_db")
    assert a._config["_resources"] == {"db": "fake_db"}


def test_builder_inject_chainable():
    """inject() returns self."""
    from adk_fluent import Agent
    a = Agent("a")
    result = a.inject(db="fake")
    assert result is a


def test_builder_inject_accumulates():
    """Multiple inject() calls merge resources."""
    from adk_fluent import Agent
    a = Agent("a").inject(db="fake").inject(cache="mem")
    assert a._config["_resources"] == {"db": "fake", "cache": "mem"}
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/manual/test_di.py -v`
Expected: FAIL — `from adk_fluent.di import inject_resources` fails

**Step 3: Implement**

Create `src/adk_fluent/di.py`:

```python
"""Resource dependency injection for tool functions."""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable


def inject_resources(fn: Callable, resources: dict[str, Any]) -> Callable:
    """Wrap a tool function with resource injection.

    Resource parameters are removed from __signature__ so ADK's
    FunctionTool excludes them from the LLM schema. At call time,
    the resources are injected as keyword arguments.
    """
    sig = inspect.signature(fn)
    resource_params = {
        name for name in sig.parameters
        if name in resources and name != "tool_context"
    }

    if not resource_params:
        return fn

    is_async = inspect.iscoroutinefunction(fn)

    @functools.wraps(fn)
    async def wrapped(**kwargs):
        kwargs.update({k: resources[k] for k in resource_params if k not in kwargs})
        if is_async:
            return await fn(**kwargs)
        return fn(**kwargs)

    new_params = [p for name, p in sig.parameters.items() if name not in resource_params]
    wrapped.__signature__ = sig.replace(parameters=new_params)
    return wrapped
```

In `src/adk_fluent/_base.py`, add to BuilderBase (after `consumes()`):

```python
def inject(self, **resources: Any) -> Self:
    """Register resources for dependency injection into tool functions.

    At build time, tools with matching parameter names will have
    those parameters injected and hidden from the LLM schema.
    """
    existing = self._config.setdefault("_resources", {})
    existing.update(resources)
    return self
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/manual/test_di.py -v`
Expected: PASS (8 tests)

**Step 5: Run full suite**

Run: `python -m pytest tests/ --tb=short -q`
Expected: 1041+ passed

**Step 6: Commit**

```bash
git add src/adk_fluent/di.py src/adk_fluent/_base.py tests/manual/test_di.py
git commit -m "feat: add resource DI with inject_resources and .inject() builder method"
```

______________________________________________________________________

### Task 5: Mock backend + AgentHarness for testing

**Files:**

- Create: `src/adk_fluent/testing/mock_backend.py`
- Create: `src/adk_fluent/testing/harness.py`
- Modify: `src/adk_fluent/testing/__init__.py` (add exports)
- Test: `tests/manual/test_mock_backend.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_mock_backend.py
"""Tests for mock_backend and AgentHarness."""
import pytest


def test_mock_backend_satisfies_protocol():
    """MockBackend satisfies the Backend protocol."""
    from adk_fluent.testing import mock_backend
    from adk_fluent.backends import Backend
    mb = mock_backend({"agent_a": "Hello!"})
    assert isinstance(mb, Backend)


def test_mock_backend_compile():
    """MockBackend.compile returns a passable compiled object."""
    from adk_fluent.testing import mock_backend
    from adk_fluent import Agent
    mb = mock_backend({"agent_a": "Hello!"})
    ir = Agent("agent_a").to_ir()
    compiled = mb.compile(ir)
    assert compiled is not None


@pytest.mark.asyncio
async def test_mock_backend_run():
    """MockBackend.run returns events with canned responses."""
    from adk_fluent.testing import mock_backend
    from adk_fluent import Agent
    mb = mock_backend({"agent_a": "Hello from mock!"})
    ir = Agent("agent_a").to_ir()
    compiled = mb.compile(ir)
    events = await mb.run(compiled, "test prompt")
    assert any(e.content == "Hello from mock!" for e in events)


@pytest.mark.asyncio
async def test_mock_backend_run_state_delta():
    """MockBackend supports dict responses for state_delta."""
    from adk_fluent.testing import mock_backend
    from adk_fluent import Agent
    mb = mock_backend({"agent_a": {"intent": "billing"}})
    ir = Agent("agent_a").to_ir()
    compiled = mb.compile(ir)
    events = await mb.run(compiled, "test")
    assert any(e.state_delta.get("intent") == "billing" for e in events)


@pytest.mark.asyncio
async def test_mock_backend_unknown_agent():
    """Unknown agents return a generic event."""
    from adk_fluent.testing import mock_backend
    from adk_fluent import Agent
    mb = mock_backend({"other": "response"})
    ir = Agent("unknown_agent").to_ir()
    compiled = mb.compile(ir)
    events = await mb.run(compiled, "test")
    assert len(events) >= 1


def test_harness_creation():
    """AgentHarness wraps a builder with a mock backend."""
    from adk_fluent.testing import AgentHarness, mock_backend
    from adk_fluent import Agent
    harness = AgentHarness(
        Agent("a").instruct("test"),
        backend=mock_backend({"a": "response"})
    )
    assert harness is not None


@pytest.mark.asyncio
async def test_harness_send():
    """AgentHarness.send() returns a response object."""
    from adk_fluent.testing import AgentHarness, mock_backend
    from adk_fluent import Agent
    harness = AgentHarness(
        Agent("a").instruct("test"),
        backend=mock_backend({"a": "Hello!"})
    )
    response = await harness.send("Hi")
    assert response.final_text == "Hello!"
    assert not response.errors
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/manual/test_mock_backend.py -v`
Expected: FAIL — import fails

**Step 3: Implement**

Create `src/adk_fluent/testing/mock_backend.py`:

```python
"""Mock backend for deterministic testing without LLM calls."""
from __future__ import annotations

from typing import Any, AsyncIterator

from adk_fluent._ir import AgentEvent, ExecutionConfig
from adk_fluent._ir_generated import SequenceNode


class MockBackend:
    """A backend that returns canned responses for each agent name."""

    def __init__(self, responses: dict[str, Any]):
        self._responses = responses

    def compile(self, node: Any, config: ExecutionConfig | None = None) -> Any:
        return node  # Pass-through; we walk the IR directly in run()

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]:
        events = []
        self._walk(compiled, events)
        return events

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        events = await self.run(compiled, prompt, **kwargs)
        for event in events:
            yield event

    def _walk(self, node: Any, events: list[AgentEvent]):
        """Walk the IR tree and generate events from canned responses."""
        name = getattr(node, "name", "")
        children = getattr(node, "children", ())

        if children:
            for child in children:
                self._walk(child, events)
        else:
            response = self._responses.get(name)
            if response is None:
                events.append(AgentEvent(
                    author=name,
                    content=f"[no mock for '{name}']",
                    is_final=True,
                ))
            elif isinstance(response, dict):
                events.append(AgentEvent(
                    author=name,
                    state_delta=response,
                    is_final=True,
                ))
            else:
                events.append(AgentEvent(
                    author=name,
                    content=str(response),
                    is_final=True,
                ))


def mock_backend(responses: dict[str, Any]) -> MockBackend:
    """Create a mock backend with canned responses.

    Args:
        responses: Mapping of agent name -> response.
            str values become content, dict values become state_delta.
    """
    return MockBackend(responses)
```

Create `src/adk_fluent/testing/harness.py`:

```python
"""Test harness for agent builders."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adk_fluent._ir import AgentEvent


@dataclass
class HarnessResponse:
    """Result from a harness send() call."""
    events: list[AgentEvent]
    final_text: str = ""
    errors: list[str] = field(default_factory=list)


class AgentHarness:
    """Wraps a builder + mock backend for ergonomic testing."""

    def __init__(self, builder: Any, *, backend: Any):
        self._builder = builder
        self._backend = backend

    async def send(self, prompt: str) -> HarnessResponse:
        ir = self._builder.to_ir()
        compiled = self._backend.compile(ir)
        events = await self._backend.run(compiled, prompt)
        final = ""
        for event in reversed(events):
            if event.is_final and event.content:
                final = event.content
                break
        return HarnessResponse(events=events, final_text=final)
```

Update `src/adk_fluent/testing/__init__.py`:

```python
"""Testing utilities for adk-fluent."""
from adk_fluent.testing.contracts import check_contracts
from adk_fluent.testing.mock_backend import mock_backend, MockBackend
from adk_fluent.testing.harness import AgentHarness, HarnessResponse

__all__ = ["check_contracts", "mock_backend", "MockBackend", "AgentHarness", "HarnessResponse"]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/manual/test_mock_backend.py -v`
Expected: PASS (7 tests)

**Step 5: Run full suite**

Run: `python -m pytest tests/ --tb=short -q`
Expected: 1048+ passed

**Step 6: Commit**

```bash
git add src/adk_fluent/testing/ tests/manual/test_mock_backend.py
git commit -m "feat: add mock_backend and AgentHarness for deterministic testing"
```

______________________________________________________________________

### Task 6: Graph visualization + exports

**Files:**

- Create: `src/adk_fluent/viz.py`
- Modify: `src/adk_fluent/_base.py` (add `.to_mermaid()`)
- Modify: `src/adk_fluent/__init__.py` (add all Phase 4 exports)
- Test: `tests/manual/test_viz.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_viz.py
"""Tests for graph visualization."""


def test_single_agent_mermaid():
    """Single agent produces minimal mermaid graph."""
    from adk_fluent import Agent
    a = Agent("greeter")
    result = a.to_mermaid()
    assert "greeter" in result
    assert "graph" in result


def test_pipeline_mermaid():
    """Pipeline shows sequential edges."""
    from adk_fluent import Agent
    pipeline = Agent("a") >> Agent("b") >> Agent("c")
    result = pipeline.to_mermaid()
    assert "a" in result
    assert "b" in result
    assert "c" in result
    assert "-->" in result


def test_fanout_mermaid():
    """FanOut shows parallel branches."""
    from adk_fluent import Agent
    fanout = Agent("a") | Agent("b")
    result = fanout.to_mermaid()
    assert "a" in result
    assert "b" in result


def test_loop_mermaid():
    """Loop shows iteration marker."""
    from adk_fluent import Agent
    loop = Agent("a") * 3
    result = loop.to_mermaid()
    assert "a" in result


def test_contract_edges_in_mermaid():
    """Mermaid includes data-flow edges for produces/consumes."""
    from pydantic import BaseModel
    from adk_fluent import Agent

    class Intent(BaseModel):
        category: str

    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    result = pipeline.to_mermaid()
    assert "category" in result or "Intent" in result


def test_to_mermaid_on_builder():
    """to_mermaid() is available on BuilderBase."""
    from adk_fluent import Agent
    a = Agent("test")
    assert hasattr(a, "to_mermaid")


def test_exports_phase4():
    """Phase 4 exports are available from top-level."""
    from adk_fluent.testing import check_contracts, mock_backend, AgentHarness
    from adk_fluent.di import inject_resources
    assert callable(check_contracts)
    assert callable(mock_backend)
    assert callable(inject_resources)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/manual/test_viz.py -v`
Expected: FAIL — `to_mermaid` not found

**Step 3: Implement**

Create `src/adk_fluent/viz.py`:

```python
"""Graph visualization for IR node trees."""
from __future__ import annotations

from typing import Any


def ir_to_mermaid(node: Any, *, show_contracts: bool = True) -> str:
    """Convert an IR node tree to a Mermaid graph definition.

    Args:
        node: Root IR node.
        show_contracts: Include data-flow edges from produces/consumes.

    Returns:
        Mermaid graph source text.
    """
    lines = ["graph TD"]
    edges = []
    contract_edges = []
    _counter = [0]

    def _id():
        _counter[0] += 1
        return f"n{_counter[0]}"

    def _walk(n: Any, parent_id: str | None = None) -> str:
        from adk_fluent._ir_generated import SequenceNode, ParallelNode, LoopNode, AgentNode
        from adk_fluent._ir import (
            TransformNode, TapNode, FallbackNode, RaceNode,
            GateNode, MapOverNode, TimeoutNode, RouteNode, TransferNode,
        )

        nid = _id()
        name = getattr(n, "name", "?")
        children = getattr(n, "children", ())

        # Node shape based on type
        if isinstance(n, AgentNode):
            lines.append(f"    {nid}[{name}]")
        elif isinstance(n, SequenceNode):
            lines.append(f"    {nid}[[\"{name} (sequence)\"]]")
        elif isinstance(n, ParallelNode):
            lines.append(f"    {nid}{{\"{name} (parallel)\"}}")
        elif isinstance(n, LoopNode):
            max_iter = getattr(n, "max_iterations", None)
            label = f"{name} (loop x{max_iter})" if max_iter else f"{name} (loop)"
            lines.append(f"    {nid}((\"{label}\"))")
        elif isinstance(n, TransformNode):
            lines.append(f"    {nid}>{name} transform]")
        elif isinstance(n, TapNode):
            lines.append(f"    {nid}>{name} tap]")
        elif isinstance(n, RouteNode):
            lines.append(f"    {nid}{{\"{name} (route)\"}}")
        else:
            lines.append(f"    {nid}[{name}]")

        # Contract annotations
        if show_contracts:
            writes = getattr(n, "writes_keys", frozenset())
            reads = getattr(n, "reads_keys", frozenset())
            produces = getattr(n, "produces_type", None)
            consumes = getattr(n, "consumes_type", None)
            if produces:
                pname = produces.__name__
                contract_edges.append(f"    {nid} -. \"produces {pname}\" .-> {nid}")
            if consumes:
                cname = consumes.__name__
                contract_edges.append(f"    {nid} -. \"consumes {cname}\" .-> {nid}")

        # Children
        if isinstance(n, SequenceNode) and children:
            child_ids = []
            for child in children:
                cid = _walk(child, nid)
                child_ids.append(cid)
            # Sequential edges between children
            for i in range(len(child_ids) - 1):
                edges.append(f"    {child_ids[i]} --> {child_ids[i+1]}")
        elif children:
            for child in children:
                cid = _walk(child, nid)
                edges.append(f"    {nid} --> {cid}")

        # Body (MapOverNode, TimeoutNode)
        body = getattr(n, "body", None)
        if body is not None:
            bid = _walk(body, nid)
            edges.append(f"    {nid} --> {bid}")

        return nid

    _walk(node)
    return "\n".join(lines + edges + contract_edges)
```

In `src/adk_fluent/_base.py`, add to BuilderBase (after `consumes()`):

```python
def to_mermaid(self) -> str:
    """Generate a Mermaid graph visualization of this builder's IR tree."""
    from adk_fluent.viz import ir_to_mermaid
    return ir_to_mermaid(self.to_ir())
```

Update `src/adk_fluent/__init__.py` to add Phase 4 exports to `__all__`:

```python
# Add to __all__:
"check_contracts",
"mock_backend",
"MockBackend",
"AgentHarness",
"HarnessResponse",
"inject_resources",
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/manual/test_viz.py -v`
Expected: PASS (7 tests)

**Step 5: Run full suite**

Run: `python -m pytest tests/ --tb=short -q`
Expected: 1055+ passed

**Step 6: Commit**

```bash
git add src/adk_fluent/viz.py src/adk_fluent/_base.py src/adk_fluent/__init__.py tests/manual/test_viz.py
git commit -m "feat: add Mermaid graph visualization and Phase 4 exports"
```
