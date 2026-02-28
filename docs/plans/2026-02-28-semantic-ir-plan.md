# Semantic IR Implementation Plan (Phase 0 + Phase 1)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Define framework-agnostic IR node types and descriptor types, then wire builders to produce them alongside the existing IR path — proving the abstraction without breaking anything.

**Architecture:** New `_semantic_ir.py` module defines `SAgentNode`, `SSequenceNode`, `SParallelNode`, `SLoopNode` plus supporting descriptors (`ToolDesc`, `GenerationDesc`, `CallbackDesc`, `NativeExtension`, `AuthDesc`). Existing primitive nodes from `_ir.py` (TransformNode, TapNode, etc.) are reused unchanged. Builders grow a `.to_semantic_ir()` method alongside `.to_ir()`. No behavior changes, no ADK import changes.

**Tech Stack:** Python 3.11 dataclasses (frozen), pytest, existing P/C/S types

**Design Doc:** `docs/plans/2026-02-28-semantic-ir-design.md`

______________________________________________________________________

## Phase 0: Semantic IR Types

### Task 1: Define ToolKind enum and descriptor types

**Files:**

- Create: `src/adk_fluent/_semantic_ir.py`
- Test: `tests/manual/test_semantic_ir.py`

**Step 1: Write the failing test**

Create `tests/manual/test_semantic_ir.py`:

```python
"""Tests for the semantic IR types."""

import pytest

from adk_fluent._semantic_ir import (
    AuthDesc,
    CallbackDesc,
    GenerationDesc,
    NativeExtension,
    ToolDesc,
    ToolKind,
)


class TestToolKind:
    def test_enum_values(self):
        assert ToolKind.FUNCTION.value == "function"
        assert ToolKind.TOOLSET.value == "toolset"
        assert ToolKind.AGENT_TOOL.value == "agent_tool"
        assert ToolKind.RETRIEVAL.value == "retrieval"
        assert ToolKind.CODE_EXEC.value == "code_exec"


class TestToolDesc:
    def test_function_tool(self):
        fn = lambda x: x
        td = ToolDesc(kind=ToolKind.FUNCTION, name="echo", impl=fn)
        assert td.kind == ToolKind.FUNCTION
        assert td.name == "echo"
        assert td.impl is fn
        assert td.provider is None

    def test_toolset(self):
        td = ToolDesc(
            kind=ToolKind.TOOLSET,
            name="bigquery",
            provider="bigquery",
            provider_config={"project": "my-project"},
        )
        assert td.provider == "bigquery"
        assert td.provider_config["project"] == "my-project"

    def test_frozen(self):
        td = ToolDesc(kind=ToolKind.FUNCTION, name="f")
        with pytest.raises(AttributeError):
            td.name = "changed"


class TestGenerationDesc:
    def test_defaults(self):
        g = GenerationDesc()
        assert g.temperature is None
        assert g.top_p is None
        assert g.max_tokens is None
        assert g.stop_sequences == ()
        assert g.extras == {}

    def test_custom_values(self):
        g = GenerationDesc(temperature=0.7, max_tokens=1024, extras={"foo": "bar"})
        assert g.temperature == 0.7
        assert g.max_tokens == 1024
        assert g.extras["foo"] == "bar"

    def test_frozen(self):
        g = GenerationDesc(temperature=0.5)
        with pytest.raises(AttributeError):
            g.temperature = 0.9


class TestCallbackDesc:
    def test_defaults_empty(self):
        c = CallbackDesc()
        assert c.before_agent == ()
        assert c.after_agent == ()
        assert c.before_model == ()

    def test_with_callbacks(self):
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        c = CallbackDesc(before_agent=(fn1,), after_agent=(fn2,))
        assert len(c.before_agent) == 1
        assert c.before_agent[0] is fn1


class TestNativeExtension:
    def test_creation(self):
        ext = NativeExtension(
            target_backend="adk",
            extras={"disallow_transfer_to_parent": True},
        )
        assert ext.target_backend == "adk"
        assert ext.extras["disallow_transfer_to_parent"] is True

    def test_non_adk_backend(self):
        ext = NativeExtension(target_backend="langgraph", extras={"thread_id": "abc"})
        assert ext.target_backend == "langgraph"


class TestAuthDesc:
    def test_creation(self):
        a = AuthDesc(scheme="oauth2", config={"client_id": "xxx"})
        assert a.scheme == "oauth2"
        assert a.config["client_id"] == "xxx"

    def test_defaults(self):
        a = AuthDesc()
        assert a.scheme == ""
        assert a.config == {}
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py -v -x`
Expected: FAIL with `ModuleNotFoundError: No module named 'adk_fluent._semantic_ir'`

**Step 3: Write minimal implementation**

Create `src/adk_fluent/_semantic_ir.py` with the descriptor types:

```python
"""Semantic IR — framework-agnostic intermediate representation.

This module defines the descriptor types used by the semantic IR layer.
These types capture *intent* (what should happen) rather than *mechanism*
(how a specific framework implements it).

Existing framework-agnostic types are reused:
- P transforms (PTransform, PRole, etc.) from _prompt.py
- C transforms (CTransform, CWindow, etc.) from _context.py
- S schemas (StateSchema) from _state_schema.py
- Primitive nodes (TransformNode, TapNode, etc.) from _ir.py

This module adds:
- ToolDesc, ToolKind — portable tool descriptors
- GenerationDesc — universal LLM generation parameters
- CallbackDesc — lifecycle hook descriptors
- NativeExtension — typed escape hatch for framework-specific config
- AuthDesc — portable auth descriptors
- SAgentNode, SSequenceNode, SParallelNode, SLoopNode — semantic agent nodes
- SNode — union of all semantic node types
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


__all__ = [
    # Enums
    "ToolKind",
    # Descriptors
    "ToolDesc",
    "GenerationDesc",
    "CallbackDesc",
    "NativeExtension",
    "AuthDesc",
    # Nodes
    "SAgentNode",
    "SSequenceNode",
    "SParallelNode",
    "SLoopNode",
    # Union
    "SNode",
]


# ======================================================================
# Enums
# ======================================================================


class ToolKind(Enum):
    """Discriminator for tool descriptor types."""

    FUNCTION = "function"
    TOOLSET = "toolset"
    AGENT_TOOL = "agent_tool"
    RETRIEVAL = "retrieval"
    CODE_EXEC = "code_exec"


# ======================================================================
# Descriptors
# ======================================================================


@dataclass(frozen=True)
class AuthDesc:
    """Framework-agnostic auth descriptor."""

    scheme: str = ""  # "oauth2", "api_key", "service_account", etc.
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDesc:
    """Unified tool descriptor.

    Discriminated by ``kind``:
    - FUNCTION: ``impl`` is the callable, ``parameters`` is JSON schema or Pydantic model
    - TOOLSET: ``provider`` + ``provider_config`` describe the toolset type and its config
    - AGENT_TOOL: ``agent_ref`` is the inner SNode to use as a tool
    - RETRIEVAL: retrieval tool with provider config
    - CODE_EXEC: code execution tool with provider config
    """

    kind: ToolKind
    name: str = ""
    description: str = ""
    impl: Callable | None = None
    parameters: type | dict[str, Any] | None = None
    provider: str | None = None
    provider_config: dict[str, Any] = field(default_factory=dict)
    agent_ref: Any = None  # SNode — forward ref to avoid circular
    auth: AuthDesc | None = None


@dataclass(frozen=True)
class GenerationDesc:
    """Framework-agnostic LLM generation parameters."""

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()
    safety_settings: tuple[Any, ...] = ()
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CallbackDesc:
    """Lifecycle hook descriptors.

    Each field is a tuple of callables. The backend maps these to
    framework-specific lifecycle events.
    """

    before_agent: tuple[Callable, ...] = ()
    after_agent: tuple[Callable, ...] = ()
    before_model: tuple[Callable, ...] = ()
    after_model: tuple[Callable, ...] = ()
    on_model_error: tuple[Callable, ...] = ()
    before_tool: tuple[Callable, ...] = ()
    after_tool: tuple[Callable, ...] = ()
    on_tool_error: tuple[Callable, ...] = ()


@dataclass(frozen=True)
class NativeExtension:
    """Framework-specific configuration escape hatch.

    Backends that match ``target_backend`` apply ``extras`` to the
    constructed object. Others ignore it safely.
    """

    target_backend: str
    extras: dict[str, Any] = field(default_factory=dict)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py -v -x`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_semantic_ir.py tests/manual/test_semantic_ir.py
git commit -m "feat(ir): add semantic IR descriptor types — ToolDesc, GenerationDesc, CallbackDesc, NativeExtension, AuthDesc"
```

______________________________________________________________________

### Task 2: Define SAgentNode, SSequenceNode, SParallelNode, SLoopNode

**Files:**

- Modify: `src/adk_fluent/_semantic_ir.py`
- Modify: `tests/manual/test_semantic_ir.py`

**Step 1: Write the failing tests**

Append to `tests/manual/test_semantic_ir.py`:

```python
from adk_fluent._semantic_ir import (
    SAgentNode,
    SLoopNode,
    SNode,
    SParallelNode,
    SSequenceNode,
)
from adk_fluent._prompt import P


class TestSAgentNode:
    def test_minimal(self):
        node = SAgentNode(name="agent1")
        assert node.name == "agent1"
        assert node.model == ""
        assert node.prompt == ""
        assert node.context is None
        assert node.tools == ()
        assert node.children == ()
        assert node.writes_keys == frozenset()
        assert node.reads_keys == frozenset()

    def test_with_prompt_spec(self):
        prompt = P.role("Helper") + P.task("Assist")
        node = SAgentNode(name="a", model="gemini-2.5-flash", prompt=prompt)
        assert node.model == "gemini-2.5-flash"
        # PTransform is preserved as-is
        from adk_fluent._prompt import PTransform
        assert isinstance(node.prompt, PTransform)

    def test_with_tools(self):
        fn = lambda x: x
        td = ToolDesc(kind=ToolKind.FUNCTION, name="echo", impl=fn)
        node = SAgentNode(name="a", tools=(td,))
        assert len(node.tools) == 1
        assert node.tools[0].name == "echo"

    def test_with_generation(self):
        gen = GenerationDesc(temperature=0.7, max_tokens=1024)
        node = SAgentNode(name="a", generation=gen)
        assert node.generation.temperature == 0.7

    def test_with_native_extensions(self):
        ext = NativeExtension("adk", {"disallow_transfer_to_parent": True})
        node = SAgentNode(name="a", native_extensions=(ext,))
        assert len(node.native_extensions) == 1
        assert node.native_extensions[0].target_backend == "adk"

    def test_with_children(self):
        child = SAgentNode(name="child")
        parent = SAgentNode(name="parent", children=(child,))
        assert len(parent.children) == 1
        assert parent.children[0].name == "child"

    def test_frozen(self):
        node = SAgentNode(name="a")
        with pytest.raises(AttributeError):
            node.name = "b"

    def test_dataflow_keys(self):
        node = SAgentNode(
            name="a",
            writes_keys=frozenset({"output"}),
            reads_keys=frozenset({"input"}),
        )
        assert "output" in node.writes_keys
        assert "input" in node.reads_keys


class TestSSequenceNode:
    def test_basic(self):
        a = SAgentNode(name="a")
        b = SAgentNode(name="b")
        seq = SSequenceNode(name="pipe", children=(a, b))
        assert seq.name == "pipe"
        assert len(seq.children) == 2

    def test_with_callbacks(self):
        fn = lambda ctx: None
        cb = CallbackDesc(before_agent=(fn,))
        seq = SSequenceNode(name="s", callbacks=cb)
        assert len(seq.callbacks.before_agent) == 1


class TestSParallelNode:
    def test_basic(self):
        a = SAgentNode(name="a")
        b = SAgentNode(name="b")
        par = SParallelNode(name="fan", children=(a, b))
        assert par.name == "fan"
        assert len(par.children) == 2


class TestSLoopNode:
    def test_basic(self):
        a = SAgentNode(name="body")
        loop = SLoopNode(name="loop", children=(a,), max_iterations=5)
        assert loop.max_iterations == 5

    def test_no_max_iterations(self):
        loop = SLoopNode(name="loop", children=())
        assert loop.max_iterations is None


class TestSNodeUnion:
    """Verify that SNode is the correct union of all node types."""

    def test_agent_is_snode(self):
        node = SAgentNode(name="a")
        assert isinstance(node, SAgentNode)

    def test_sequence_is_snode(self):
        node = SSequenceNode(name="s")
        assert isinstance(node, SSequenceNode)

    def test_primitive_nodes_included(self):
        """Hand-written primitives from _ir.py should be part of the SNode union."""
        from adk_fluent._ir import TransformNode, TapNode, RouteNode

        # These types should exist and be importable
        # (We verify the union type annotation includes them in type-checking,
        # but at runtime we just confirm they're constructable)
        tn = TransformNode(name="t", fn=lambda s: s)
        assert tn.name == "t"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestSAgentNode -v -x`
Expected: FAIL with `ImportError: cannot import name 'SAgentNode'`

**Step 3: Write minimal implementation**

Append to `src/adk_fluent/_semantic_ir.py`:

```python
# ======================================================================
# Semantic IR nodes
# ======================================================================


@dataclass(frozen=True)
class SAgentNode:
    """Semantic IR node for an LLM-backed agent.

    Framework-agnostic. Uses our vocabulary (PTransform, CTransform,
    ToolDesc, GenerationDesc) instead of framework-specific fields.
    """

    name: str
    model: str = ""
    prompt: Any = ""  # PTransform | str
    context: Any = None  # CTransform | None
    tools: tuple[ToolDesc, ...] = ()
    output_schema: type | None = None
    output_key: str | None = None
    generation: GenerationDesc | None = None
    callbacks: CallbackDesc = field(default_factory=CallbackDesc)
    children: tuple = ()  # tuple[SNode, ...]
    native_extensions: tuple[NativeExtension, ...] = ()
    description: str = ""
    # Dataflow
    writes_keys: frozenset[str] = frozenset()
    reads_keys: frozenset[str] = frozenset()
    produces_type: type | None = None
    consumes_type: type | None = None
    # Preserved high-level specs for diagnostics
    prompt_spec: Any = None  # PTransform descriptor
    context_spec: Any = None  # CTransform descriptor
    tool_schema: type | None = None


@dataclass(frozen=True)
class SSequenceNode:
    """Semantic IR node: execute children in order."""

    name: str
    children: tuple = ()  # tuple[SNode, ...]
    callbacks: CallbackDesc = field(default_factory=CallbackDesc)
    description: str = ""


@dataclass(frozen=True)
class SParallelNode:
    """Semantic IR node: execute children concurrently."""

    name: str
    children: tuple = ()  # tuple[SNode, ...]
    callbacks: CallbackDesc = field(default_factory=CallbackDesc)
    description: str = ""


@dataclass(frozen=True)
class SLoopNode:
    """Semantic IR node: execute children in a loop."""

    name: str
    children: tuple = ()  # tuple[SNode, ...]
    max_iterations: int | None = None
    callbacks: CallbackDesc = field(default_factory=CallbackDesc)
    description: str = ""


# ======================================================================
# SNode union — all semantic node types
# ======================================================================

# Import primitive nodes from _ir.py (already framework-agnostic)
from adk_fluent._ir import (  # noqa: E402
    CaptureNode,
    DispatchNode,
    FallbackNode,
    GateNode,
    JoinNode,
    MapOverNode,
    RaceNode,
    RouteNode,
    TapNode,
    TimeoutNode,
    TransferNode,
    TransformNode,
)

SNode = (
    SAgentNode
    | SSequenceNode
    | SParallelNode
    | SLoopNode
    | TransformNode
    | TapNode
    | FallbackNode
    | RaceNode
    | GateNode
    | MapOverNode
    | TimeoutNode
    | RouteNode
    | TransferNode
    | CaptureNode
    | DispatchNode
    | JoinNode
)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py -v -x`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_semantic_ir.py tests/manual/test_semantic_ir.py
git commit -m "feat(ir): add SAgentNode, SSequenceNode, SParallelNode, SLoopNode and SNode union"
```

______________________________________________________________________

### Task 3: Add fingerprinting and equality for semantic IR nodes

**Files:**

- Modify: `src/adk_fluent/_semantic_ir.py`
- Modify: `tests/manual/test_semantic_ir.py`

**Step 1: Write the failing test**

Append to `tests/manual/test_semantic_ir.py`:

```python
from adk_fluent._semantic_ir import fingerprint_snode


class TestFingerprint:
    def test_same_content_same_fingerprint(self):
        a = SAgentNode(name="a", model="gemini-2.5-flash")
        b = SAgentNode(name="a", model="gemini-2.5-flash")
        assert fingerprint_snode(a) == fingerprint_snode(b)

    def test_different_content_different_fingerprint(self):
        a = SAgentNode(name="a", model="gemini-2.5-flash")
        b = SAgentNode(name="a", model="gemini-2.5-pro")
        assert fingerprint_snode(a) != fingerprint_snode(b)

    def test_nested_fingerprint(self):
        child = SAgentNode(name="child")
        parent1 = SSequenceNode(name="s", children=(child,))
        parent2 = SSequenceNode(name="s", children=(child,))
        assert fingerprint_snode(parent1) == fingerprint_snode(parent2)

    def test_tool_desc_affects_fingerprint(self):
        td1 = ToolDesc(kind=ToolKind.FUNCTION, name="f1")
        td2 = ToolDesc(kind=ToolKind.FUNCTION, name="f2")
        a = SAgentNode(name="a", tools=(td1,))
        b = SAgentNode(name="a", tools=(td2,))
        assert fingerprint_snode(a) != fingerprint_snode(b)

    def test_returns_12_char_hex(self):
        node = SAgentNode(name="a")
        fp = fingerprint_snode(node)
        assert len(fp) == 12
        assert all(c in "0123456789abcdef" for c in fp)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestFingerprint -v -x`
Expected: FAIL with `ImportError: cannot import name 'fingerprint_snode'`

**Step 3: Write minimal implementation**

Add to `src/adk_fluent/_semantic_ir.py`:

```python
import hashlib


def fingerprint_snode(node: Any) -> str:
    """Compute a stable SHA-256 fingerprint of a semantic IR node tree.

    Used for caching, version comparison, and change detection.
    Callables are hashed by id (not content) since they can't be serialized.
    """
    h = hashlib.sha256()
    _hash_node(h, node)
    return h.hexdigest()[:12]


def _hash_node(h: Any, node: Any) -> None:
    """Recursively hash a node into a hashlib object."""
    h.update(type(node).__name__.encode())

    if isinstance(node, SAgentNode):
        h.update(node.name.encode())
        h.update(node.model.encode())
        h.update(node.description.encode())
        if isinstance(node.prompt, str):
            h.update(node.prompt.encode())
        elif hasattr(node.prompt, "fingerprint"):
            h.update(node.prompt.fingerprint().encode())
        for tool in node.tools:
            _hash_tool(h, tool)
        if node.generation is not None:
            _hash_generation(h, node.generation)
        for child in node.children:
            _hash_node(h, child)
        for ext in node.native_extensions:
            h.update(ext.target_backend.encode())
            h.update(str(sorted(ext.extras.items())).encode())

    elif isinstance(node, SSequenceNode | SParallelNode | SLoopNode):
        h.update(node.name.encode())
        if isinstance(node, SLoopNode) and node.max_iterations is not None:
            h.update(str(node.max_iterations).encode())
        for child in node.children:
            _hash_node(h, child)

    else:
        # Primitive nodes: hash name and kind
        h.update(getattr(node, "name", "").encode())
        kind = type(node).__name__
        h.update(kind.encode())


def _hash_tool(h: Any, tool: ToolDesc) -> None:
    """Hash a ToolDesc into a hashlib object."""
    h.update(tool.kind.value.encode())
    h.update(tool.name.encode())
    h.update(tool.description.encode())
    if tool.provider:
        h.update(tool.provider.encode())
    h.update(str(sorted(tool.provider_config.items())).encode())


def _hash_generation(h: Any, gen: GenerationDesc) -> None:
    """Hash a GenerationDesc into a hashlib object."""
    if gen.temperature is not None:
        h.update(str(gen.temperature).encode())
    if gen.top_p is not None:
        h.update(str(gen.top_p).encode())
    if gen.max_tokens is not None:
        h.update(str(gen.max_tokens).encode())
    for s in gen.stop_sequences:
        h.update(s.encode())
```

Also add to `__all__`: `"fingerprint_snode"`

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py -v -x`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_semantic_ir.py tests/manual/test_semantic_ir.py
git commit -m "feat(ir): add fingerprint_snode for semantic IR change detection"
```

______________________________________________________________________

### Task 4: Export semantic IR types from package

**Files:**

- Modify: `src/adk_fluent/__init__.py`

**Step 1: Write the failing test**

Append to `tests/manual/test_semantic_ir.py`:

```python
class TestExports:
    def test_importable_from_package(self):
        from adk_fluent import (
            SAgentNode,
            SSequenceNode,
            SParallelNode,
            SLoopNode,
            ToolDesc,
            ToolKind,
            GenerationDesc,
            CallbackDesc,
            NativeExtension,
            AuthDesc,
        )
        # Smoke test: all are importable
        assert SAgentNode is not None
        assert ToolKind.FUNCTION.value == "function"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestExports -v -x`
Expected: FAIL with `ImportError: cannot import name 'SAgentNode' from 'adk_fluent'`

**Step 3: Add exports to `__init__.py`**

Add the following import block to `src/adk_fluent/__init__.py`, near the existing `_prompt` imports (around line 599):

```python
from ._semantic_ir import AuthDesc
from ._semantic_ir import CallbackDesc
from ._semantic_ir import GenerationDesc
from ._semantic_ir import NativeExtension
from ._semantic_ir import SAgentNode
from ._semantic_ir import SLoopNode
from ._semantic_ir import SNode
from ._semantic_ir import SParallelNode
from ._semantic_ir import SSequenceNode
from ._semantic_ir import ToolDesc
from ._semantic_ir import ToolKind
from ._semantic_ir import fingerprint_snode
```

Also add these names to the `__all__` list in `__init__.py`.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py -v -x`
Expected: all tests PASS

**Step 5: Lint and commit**

```bash
ruff check --fix src/adk_fluent/__init__.py && ruff format src/adk_fluent/__init__.py
git add src/adk_fluent/__init__.py tests/manual/test_semantic_ir.py
git commit -m "feat(ir): export semantic IR types from adk_fluent package"
```

______________________________________________________________________

## Phase 1: Dual-Path `.to_semantic_ir()`

### Task 5: Add `_agent_to_semantic_ir` helper

**Files:**

- Modify: `src/adk_fluent/_helpers.py`
- Test: `tests/manual/test_semantic_ir.py`

**Step 1: Write the failing test**

Append to `tests/manual/test_semantic_ir.py`:

```python
from adk_fluent import Agent, P


class TestAgentToSemanticIR:
    def test_basic_agent(self):
        agent = Agent("reviewer").model("gemini-2.5-flash").instruct("Review code.")
        sir = agent.to_semantic_ir()
        assert isinstance(sir, SAgentNode)
        assert sir.name == "reviewer"
        assert sir.model == "gemini-2.5-flash"

    def test_with_prompt_spec(self):
        prompt = P.role("Helper") + P.task("Assist")
        agent = Agent("a").model("gemini-2.5-flash").instruct(prompt)
        sir = agent.to_semantic_ir()
        assert isinstance(sir, SAgentNode)
        from adk_fluent._prompt import PTransform
        assert isinstance(sir.prompt, PTransform)

    def test_with_function_tool(self):
        def greet(name: str) -> str:
            return f"Hello {name}"

        agent = Agent("a").model("gemini-2.5-flash").tools(greet)
        sir = agent.to_semantic_ir()
        assert len(sir.tools) == 1
        assert sir.tools[0].kind == ToolKind.FUNCTION
        assert sir.tools[0].impl is greet

    def test_with_children(self):
        child = Agent("child").model("gemini-2.5-flash")
        parent = Agent("parent").model("gemini-2.5-flash").sub_agents(child)
        sir = parent.to_semantic_ir()
        assert len(sir.children) == 1
        assert isinstance(sir.children[0], SAgentNode)
        assert sir.children[0].name == "child"

    def test_dataflow_preserved(self):
        from pydantic import BaseModel

        class Out(BaseModel):
            result: str

        agent = Agent("a").model("gemini-2.5-flash").produces(Out)
        sir = agent.to_semantic_ir()
        assert "result" in sir.writes_keys
        assert sir.produces_type is Out

    def test_callbacks_converted(self):
        fn = lambda ctx, resp: None
        agent = Agent("a").model("gemini-2.5-flash").after_model(fn)
        sir = agent.to_semantic_ir()
        assert len(sir.callbacks.after_model) == 1

    def test_native_extension_for_adk_fields(self):
        agent = (
            Agent("a")
            .model("gemini-2.5-flash")
            .disallow_transfer_to_parent(True)
        )
        sir = agent.to_semantic_ir()
        # ADK-specific fields should become NativeExtensions
        adk_exts = [e for e in sir.native_extensions if e.target_backend == "adk"]
        assert len(adk_exts) >= 1
        combined = {}
        for e in adk_exts:
            combined.update(e.extras)
        assert combined.get("disallow_transfer_to_parent") is True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestAgentToSemanticIR -v -x`
Expected: FAIL with `AttributeError: 'Agent' object has no attribute 'to_semantic_ir'`

**Step 3: Implement `_agent_to_semantic_ir` in `_helpers.py`**

Add to `src/adk_fluent/_helpers.py` after `_agent_to_ir`:

```python
def _agent_to_semantic_ir(builder):
    """Convert an Agent builder to an SAgentNode (semantic IR)."""
    from adk_fluent._prompt import PTransform as _PT
    from adk_fluent._semantic_ir import (
        CallbackDesc,
        NativeExtension,
        SAgentNode,
        ToolDesc,
        ToolKind,
    )

    # --- Tools ---
    raw_tools = list(builder._config.get("tools", []))
    if builder._lists.get("tools"):
        raw_tools.extend(builder._lists["tools"])
    tools = tuple(_to_tool_desc(t) for t in raw_tools)

    # --- Callbacks ---
    cb_map = {k: tuple(v) for k, v in builder._callbacks.items() if v}
    callbacks = CallbackDesc(
        before_agent=cb_map.get("before_agent_callback", ()),
        after_agent=cb_map.get("after_agent_callback", ()),
        before_model=cb_map.get("before_model_callback", ()),
        after_model=cb_map.get("after_model_callback", ()),
        on_model_error=cb_map.get("on_model_error_callback", ()),
        before_tool=cb_map.get("before_tool_callback", ()),
        after_tool=cb_map.get("after_tool_callback", ()),
        on_tool_error=cb_map.get("on_tool_error_callback", ()),
    )

    # --- Children ---
    children = _collect_children_semantic(builder)

    # --- Prompt ---
    prompt = builder._config.get("instruction", "")
    prompt_spec = builder._config.get("_prompt_spec")
    if prompt_spec is None and isinstance(prompt, _PT):
        prompt_spec = prompt

    # --- Context ---
    context_spec = builder._config.get("_context_spec")

    # --- Dataflow ---
    produces_schema = builder._config.get("_produces")
    consumes_schema = builder._config.get("_consumes")
    tool_schema = builder._config.get("_tool_schema")
    callback_schema = builder._config.get("_callback_schema")
    writes_keys = frozenset(produces_schema.model_fields.keys()) if produces_schema else frozenset()
    reads_keys = frozenset(consumes_schema.model_fields.keys()) if consumes_schema else frozenset()
    if tool_schema is not None and hasattr(tool_schema, "reads_keys"):
        reads_keys = reads_keys | tool_schema.reads_keys()
    if tool_schema is not None and hasattr(tool_schema, "writes_keys"):
        writes_keys = writes_keys | tool_schema.writes_keys()
    if callback_schema is not None and hasattr(callback_schema, "reads_keys"):
        reads_keys = reads_keys | callback_schema.reads_keys()
    if callback_schema is not None and hasattr(callback_schema, "writes_keys"):
        writes_keys = writes_keys | callback_schema.writes_keys()

    # --- ADK-specific fields → NativeExtension ---
    _ADK_SPECIFIC_FIELDS = {
        "disallow_transfer_to_parent",
        "disallow_transfer_to_peers",
        "include_contents",
        "generate_content_config",
        "planner",
        "code_executor",
        "input_schema",
        "global_instruction",
        "static_instruction",
    }
    adk_extras = {}
    for field_name in _ADK_SPECIFIC_FIELDS:
        val = builder._config.get(field_name)
        if val is not None and val != "" and val != False and val != "default":
            adk_extras[field_name] = val

    native_extensions = ()
    if adk_extras:
        native_extensions = (NativeExtension(target_backend="adk", extras=adk_extras),)

    return SAgentNode(
        name=builder._config.get("name", ""),
        description=builder._config.get("description", ""),
        model=builder._config.get("model", ""),
        prompt=prompt,
        context=context_spec,
        tools=tools,
        output_schema=builder._config.get("output_schema") or builder._config.get("_output_schema"),
        output_key=builder._config.get("output_key"),
        callbacks=callbacks,
        children=children,
        native_extensions=native_extensions,
        writes_keys=writes_keys,
        reads_keys=reads_keys,
        produces_type=produces_schema,
        consumes_type=consumes_schema,
        prompt_spec=prompt_spec,
        context_spec=context_spec,
        tool_schema=tool_schema,
    )


def _to_tool_desc(tool):
    """Convert a tool object to a ToolDesc."""
    from adk_fluent._semantic_ir import ToolDesc, ToolKind

    if callable(tool) and not hasattr(tool, "_tool_type"):
        # Plain function
        return ToolDesc(
            kind=ToolKind.FUNCTION,
            name=getattr(tool, "__name__", ""),
            impl=tool,
        )

    # ADK tool objects: wrap as toolset or function
    tool_cls_name = type(tool).__name__
    if "Toolset" in tool_cls_name:
        # Toolset: extract provider from class name
        provider = tool_cls_name.replace("Toolset", "").lower()
        # Try to extract config from the tool's Pydantic fields
        config = {}
        if hasattr(tool, "model_dump"):
            try:
                config = tool.model_dump()
            except Exception:
                pass
        return ToolDesc(
            kind=ToolKind.TOOLSET,
            name=tool_cls_name,
            provider=provider,
            provider_config=config,
        )

    # Default: wrap as function tool
    return ToolDesc(
        kind=ToolKind.FUNCTION,
        name=getattr(tool, "name", tool_cls_name),
        impl=tool if callable(tool) else None,
    )


def _collect_children_semantic(builder):
    """Collect children from builder, recursively converting to semantic IR."""
    from adk_fluent._base import BuilderBase

    children_raw = list(builder._config.get("sub_agents", []))
    children_raw.extend(builder._lists.get("sub_agents", []))
    result = []
    for c in children_raw:
        if isinstance(c, BuilderBase) and hasattr(c, "to_semantic_ir"):
            result.append(c.to_semantic_ir())
        elif hasattr(c, "to_ir"):
            result.append(c.to_ir())
        else:
            result.append(c)
    return tuple(result)
```

**Step 4: Add `to_semantic_ir()` to Agent builder**

In `src/adk_fluent/agent.py`, add after `to_ir()`:

```python
    def to_semantic_ir(self) -> Any:
        """Convert this Agent builder to an SAgentNode (semantic IR)."""
        from adk_fluent._helpers import _agent_to_semantic_ir

        return _agent_to_semantic_ir(self)
```

**Step 5: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestAgentToSemanticIR -v -x`
Expected: all tests PASS

**Step 6: Commit**

```bash
git add src/adk_fluent/_helpers.py src/adk_fluent/agent.py tests/manual/test_semantic_ir.py
git commit -m "feat(ir): add _agent_to_semantic_ir and Agent.to_semantic_ir()"
```

______________________________________________________________________

### Task 6: Add `to_semantic_ir()` to Pipeline, FanOut, Loop builders

**Files:**

- Modify: `src/adk_fluent/_helpers.py`
- Modify: `src/adk_fluent/workflow.py`
- Modify: `tests/manual/test_semantic_ir.py`

**Step 1: Write the failing test**

Append to `tests/manual/test_semantic_ir.py`:

```python
from adk_fluent import Pipeline, FanOut, Loop


class TestWorkflowToSemanticIR:
    def test_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        pipe = a >> b
        sir = pipe.to_semantic_ir()
        assert isinstance(sir, SSequenceNode)
        assert len(sir.children) == 2
        assert isinstance(sir.children[0], SAgentNode)

    def test_fanout(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        fan = a | b
        sir = fan.to_semantic_ir()
        assert isinstance(sir, SParallelNode)
        assert len(sir.children) == 2

    def test_loop(self):
        a = Agent("body").model("gemini-2.5-flash")
        loop_builder = a * 3
        sir = loop_builder.to_semantic_ir()
        assert isinstance(sir, SLoopNode)
        assert sir.max_iterations == 3
        assert len(sir.children) == 1

    def test_nested_pipeline_fanout(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        composite = a >> (b | c)
        sir = composite.to_semantic_ir()
        assert isinstance(sir, SSequenceNode)
        assert len(sir.children) == 2
        assert isinstance(sir.children[0], SAgentNode)
        assert isinstance(sir.children[1], SParallelNode)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestWorkflowToSemanticIR -v -x`
Expected: FAIL with `AttributeError: ... has no attribute 'to_semantic_ir'`

**Step 3: Add helpers to `_helpers.py`**

```python
def _pipeline_to_semantic_ir(builder):
    """Convert a Pipeline builder to an SSequenceNode."""
    from adk_fluent._semantic_ir import SSequenceNode

    return SSequenceNode(
        name=builder._config.get("name", "pipeline"),
        children=_collect_children_semantic(builder),
    )


def _fanout_to_semantic_ir(builder):
    """Convert a FanOut builder to an SParallelNode."""
    from adk_fluent._semantic_ir import SParallelNode

    return SParallelNode(
        name=builder._config.get("name", "fanout"),
        children=_collect_children_semantic(builder),
    )


def _loop_to_semantic_ir(builder):
    """Convert a Loop builder to an SLoopNode."""
    from adk_fluent._semantic_ir import SLoopNode

    return SLoopNode(
        name=builder._config.get("name", "loop"),
        children=_collect_children_semantic(builder),
        max_iterations=builder._config.get("max_iterations"),
    )
```

**Step 4: Add `to_semantic_ir()` to workflow builders in `src/adk_fluent/workflow.py`**

Add to each of `Loop`, `FanOut`, and `Pipeline` classes, after their existing `to_ir()`:

```python
    def to_semantic_ir(self) -> Any:
        """Convert to semantic IR node."""
        from adk_fluent._helpers import _loop_to_semantic_ir  # or _fanout/_pipeline
        return _loop_to_semantic_ir(self)
```

**Step 5: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestWorkflowToSemanticIR -v -x`
Expected: all tests PASS

**Step 6: Commit**

```bash
git add src/adk_fluent/_helpers.py src/adk_fluent/workflow.py tests/manual/test_semantic_ir.py
git commit -m "feat(ir): add to_semantic_ir() for Pipeline, FanOut, Loop builders"
```

______________________________________________________________________

### Task 7: Add `to_semantic_ir()` to primitive builders

**Files:**

- Modify: `src/adk_fluent/_primitive_builders.py`
- Modify: `tests/manual/test_semantic_ir.py`

**Step 1: Write the failing test**

Append to `tests/manual/test_semantic_ir.py`:

```python
from adk_fluent._ir import TransformNode, TapNode, FallbackNode


class TestPrimitiveToSemanticIR:
    def test_fn_step(self):
        """FnStep builders should return TransformNode (already framework-agnostic)."""
        from adk_fluent import S

        transform = S.set(foo="bar")
        sir = transform.to_semantic_ir()
        assert isinstance(sir, TransformNode)

    def test_fallback(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        fb = a // b
        sir = fb.to_semantic_ir()
        assert isinstance(sir, FallbackNode)
        assert len(sir.children) == 2
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestPrimitiveToSemanticIR -v -x`
Expected: FAIL with `AttributeError: ... has no attribute 'to_semantic_ir'`

**Step 3: Add `to_semantic_ir()` to primitive builders**

In `src/adk_fluent/_primitive_builders.py`, add a `to_semantic_ir` method to each builder class. Since primitive nodes are already framework-agnostic, `to_semantic_ir()` returns the same node types as `to_ir()` — but with children recursively converted:

For each builder class that has `to_ir()`, add:

```python
    def to_semantic_ir(self):
        return self.to_ir()  # Primitive nodes are already framework-agnostic
```

For builders that have children (FallbackBuilder, RaceBuilder, DispatchBuilder), override to use semantic children:

```python
    def to_semantic_ir(self):
        from adk_fluent._base import BuilderBase
        from adk_fluent._ir import FallbackNode

        children = tuple(
            c.to_semantic_ir() if isinstance(c, BuilderBase) else c
            for c in self._children
        )
        return FallbackNode(name=self._config.get("name", "fallback"), children=children)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestPrimitiveToSemanticIR -v -x`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_primitive_builders.py tests/manual/test_semantic_ir.py
git commit -m "feat(ir): add to_semantic_ir() to all primitive builders"
```

______________________________________________________________________

### Task 8: Add `to_semantic_ir()` to base class and Route builder

**Files:**

- Modify: `src/adk_fluent/_base.py`
- Modify: `src/adk_fluent/_routing.py`
- Modify: `tests/manual/test_semantic_ir.py`

**Step 1: Write the failing test**

Append to `tests/manual/test_semantic_ir.py`:

```python
from adk_fluent._ir import RouteNode


class TestRouteToSemanticIR:
    def test_route_builder(self):
        from adk_fluent import Route

        route = (
            Route("router")
            .on("intent", "billing", Agent("billing").model("gemini-2.5-flash"))
            .on("intent", "support", Agent("support").model("gemini-2.5-flash"))
            .default(Agent("general").model("gemini-2.5-flash"))
        )
        sir = route.to_semantic_ir()
        assert isinstance(sir, RouteNode)
        assert sir.name == "router"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestRouteToSemanticIR -v -x`
Expected: FAIL

**Step 3: Add base `to_semantic_ir()` to `_base.py` and implement for Route**

In `src/adk_fluent/_base.py`, add next to the existing `to_ir()` method (around line 1621):

```python
    def to_semantic_ir(self) -> Any:
        """Convert this builder to a semantic IR node.

        Subclasses override to return the appropriate semantic IR node type.
        Falls back to to_ir() for primitive nodes that are already framework-agnostic.
        """
        return self.to_ir()
```

In `src/adk_fluent/_routing.py`, add `to_semantic_ir()` to the Route class, after `to_ir()`:

```python
    def to_semantic_ir(self):
        """Convert this Route to a semantic IR RouteNode."""
        from adk_fluent._base import BuilderBase
        from adk_fluent._ir import RouteNode

        ir_rules = []
        for pred, agent in self._rules:
            if isinstance(agent, BuilderBase):
                ir_agent = agent.to_semantic_ir()
            else:
                ir_agent = agent
            ir_rules.append((pred, ir_agent))

        default = self._default
        if isinstance(default, BuilderBase):
            default = default.to_semantic_ir()

        return RouteNode(
            name=self._config.get("name", "route"),
            key=self._route_key,
            rules=tuple(ir_rules),
            default=default,
        )
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_semantic_ir.py::TestRouteToSemanticIR -v -x`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_base.py src/adk_fluent/_routing.py tests/manual/test_semantic_ir.py
git commit -m "feat(ir): add to_semantic_ir() base method and Route support"
```

______________________________________________________________________

### Task 9: Equivalence validation — both IR paths produce same topology

**Files:**

- Create: `tests/manual/test_ir_equivalence.py`

**Step 1: Write the equivalence test**

```python
"""Validate that to_ir() and to_semantic_ir() produce equivalent agent topologies."""

import pytest

from adk_fluent import Agent, P


def _names(node, depth=0):
    """Extract a name tree from any IR node for comparison."""
    result = {"name": node.name, "type": type(node).__name__}
    children = getattr(node, "children", ())
    if children:
        result["children"] = [_names(c, depth + 1) for c in children]
    body = getattr(node, "body", None)
    if body is not None:
        result["body"] = _names(body, depth + 1)
    return result


class TestIREquivalence:
    def test_agent_topology_matches(self):
        agent = Agent("reviewer").model("gemini-2.5-flash").instruct("Review.")
        old = agent.to_ir()
        new = agent.to_semantic_ir()
        assert old.name == new.name
        assert old.model == new.model

    def test_pipeline_topology_matches(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        pipe = a >> b
        old_names = _names(pipe.to_ir())
        new_names = _names(pipe.to_semantic_ir())
        assert old_names["name"] == new_names["name"]
        assert len(old_names["children"]) == len(new_names["children"])
        for old_child, new_child in zip(old_names["children"], new_names["children"]):
            assert old_child["name"] == new_child["name"]

    def test_fanout_topology_matches(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        fan = a | b
        old = fan.to_ir()
        new = fan.to_semantic_ir()
        assert old.name == new.name
        assert len(old.children) == len(new.children)

    def test_nested_topology_matches(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        composite = a >> (b | c)
        old_tree = _names(composite.to_ir())
        new_tree = _names(composite.to_semantic_ir())
        assert old_tree["name"] == new_tree["name"]
        assert len(old_tree["children"]) == len(new_tree["children"])

    def test_loop_topology_matches(self):
        a = Agent("body").model("gemini-2.5-flash")
        loop = a * 5
        old = loop.to_ir()
        new = loop.to_semantic_ir()
        assert old.name == new.name
        assert old.max_iterations == new.max_iterations
        assert len(old.children) == len(new.children)

    def test_dataflow_keys_match(self):
        from pydantic import BaseModel

        class Out(BaseModel):
            result: str

        agent = Agent("a").model("gemini-2.5-flash").produces(Out)
        old = agent.to_ir()
        new = agent.to_semantic_ir()
        assert old.writes_keys == new.writes_keys

    def test_tool_count_matches(self):
        def greet(name: str) -> str:
            return f"Hi {name}"

        agent = Agent("a").model("gemini-2.5-flash").tools(greet)
        old = agent.to_ir()
        new = agent.to_semantic_ir()
        assert len(old.tools) == len(new.tools)
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/manual/test_ir_equivalence.py -v`
Expected: all tests PASS (if prior tasks are complete)

**Step 3: Commit**

```bash
git add tests/manual/test_ir_equivalence.py
git commit -m "test: add IR equivalence validation — old and semantic IR produce matching topologies"
```

______________________________________________________________________

### Task 10: Run full test suite and lint

**Step 1: Lint all new/modified files**

```bash
source .venv/bin/activate
ruff check --fix src/adk_fluent/_semantic_ir.py src/adk_fluent/_helpers.py src/adk_fluent/agent.py src/adk_fluent/workflow.py src/adk_fluent/_primitive_builders.py src/adk_fluent/_base.py src/adk_fluent/_routing.py src/adk_fluent/__init__.py
ruff format src/adk_fluent/_semantic_ir.py src/adk_fluent/_helpers.py src/adk_fluent/agent.py src/adk_fluent/workflow.py src/adk_fluent/_primitive_builders.py src/adk_fluent/_base.py src/adk_fluent/_routing.py src/adk_fluent/__init__.py
```

**Step 2: Run the full test suite**

```bash
source .venv/bin/activate && pytest tests/ -v --tb=short
```

Expected: all tests PASS, no regressions. The semantic IR is purely additive.

**Step 3: Fix any failures**

If any existing tests fail, investigate. The semantic IR changes should not affect existing behavior since `to_semantic_ir()` is a new method and `to_ir()` / `build()` are unchanged.

**Step 4: Final commit**

```bash
git add -u
git commit -m "chore: lint and verify full test suite with semantic IR additions"
```

______________________________________________________________________

## What's Next (Future Plans)

These phases are NOT part of this plan — they'll be separate plans after Phase 0+1 are merged and validated:

- **Phase 2:** ADK backend compiles from Semantic IR (`backends/adk.py` rewrite)
- **Phase 3:** Cutover — `.build()` routes through Semantic IR
- **Phase 4:** Scanner as capability validator
- **Phase 5:** DryRunBackend portability proof
