# v4 Phase 2: Seed-Based IR + Backend Protocol Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce an Intermediate Representation (IR) layer between fluent builders and ADK objects, enabling backend-agnostic compilation, testing, and visualization.

**Architecture:** Builders gain a `to_ir()` method that produces a frozen dataclass tree. A `Backend` protocol defines `compile(ir) → runnable` and `run(compiled, prompt) → events`. The ADK backend compiles IR → native ADK objects (App/Runner). The existing `.build()` method is unchanged for backward compatibility — new entry points (`to_app()`, `run()`, `stream()`) use the IR path.

**Tech Stack:** Python 3.11+, google-adk ≥1.25.0, dataclasses (frozen), typing.Protocol

**Reference Specs:**

- `docs/other_specs/adk_fluent_v4_spec.md` — §3 (IR), §4 (Backend Protocol)
- `docs/other_specs/adk_fluent_v3_spec.docx` — event-stream fidelity, delta-based state

**Key Design Decisions:**

- `build()` is **unchanged** — returns ADK objects directly (backward compat)
- `to_ir()` is **new** — returns IR tree (the expression graph)
- IR nodes are **frozen dataclasses** — immutable, hashable, serializable
- IR nodes for ADK agent types are **generated** from manifest.json (seed-based)
- IR nodes for adk-fluent primitives are **hand-written** (no ADK counterpart)
- `Backend` is a `Protocol` with `compile()`, `run()`, `stream()` methods
- `AgentEvent` is a **backend-agnostic event** type (not ADK's `Event`)

______________________________________________________________________

## Context: Key Files

| File                            | Role                                               |
| ------------------------------- | -------------------------------------------------- |
| `src/adk_fluent/_base.py`       | BuilderBase mixin, operators, 7 primitive builders |
| `src/adk_fluent/_routing.py`    | Route builder + \_RouteAgent + \_CheckpointAgent   |
| `src/adk_fluent/_transforms.py` | S transform factories, StateDelta/StateReplacement |
| `src/adk_fluent/_helpers.py`    | Execution helpers (run_one_shot, run_stream, etc.) |
| `scripts/scanner.py`            | Introspects ADK, produces manifest.json            |
| `scripts/generator.py`          | Generates builder classes from manifest + seed     |
| `manifest.json`                 | Machine truth about ADK classes                    |

## Codegen Pipeline (Extended)

```
python scripts/scanner.py -o manifest.json
python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py   # NEW
```

______________________________________________________________________

### Task 1: Hand-Written IR Nodes for adk-fluent Primitives

**Problem:** adk-fluent has 8 primitive concepts (fn_step, tap, fallback, race, gate, map_over, timeout, route) with no ADK counterpart. These need hand-written IR node types.

**Files:**

- Create: `src/adk_fluent/_ir.py`
- Create: `tests/manual/test_ir_nodes.py`

**Step 1: Write tests for IR node types**

Create `tests/manual/test_ir_nodes.py`:

```python
"""Tests for hand-written IR node types."""
import pytest
from adk_fluent._ir import (
    TransformNode, TapNode, FallbackNode, RaceNode, GateNode,
    MapOverNode, TimeoutNode, RouteNode, TransferNode,
    ExecutionConfig, CompactionConfig, AgentEvent,
    Node,
)


# --- Frozen immutability ---

def test_transform_node_is_frozen():
    node = TransformNode(name="t1", fn=lambda s: s)
    with pytest.raises(AttributeError):
        node.name = "changed"


def test_tap_node_is_frozen():
    node = TapNode(name="tap1", fn=lambda s: None)
    with pytest.raises(AttributeError):
        node.name = "changed"


# --- Field defaults ---

def test_transform_node_defaults():
    fn = lambda s: {"x": 1}
    node = TransformNode(name="t1", fn=fn)
    assert node.semantics == "merge"
    assert node.scope == "session"
    assert node.affected_keys is None


def test_map_over_node_defaults():
    from adk_fluent._ir import TapNode
    body = TapNode(name="inner", fn=lambda s: None)
    node = MapOverNode(name="m1", list_key="items", body=body)
    assert node.item_key == "_item"
    assert node.output_key == "results"


def test_gate_node_defaults():
    node = GateNode(name="g1", predicate=lambda s: True)
    assert node.message == "Approval required"


def test_route_node_defaults():
    node = RouteNode(name="r1")
    assert node.rules == ()
    assert node.default is None
    assert node.key is None


# --- ExecutionConfig ---

def test_execution_config_defaults():
    cfg = ExecutionConfig()
    assert cfg.app_name == "adk_fluent_app"
    assert cfg.max_llm_calls == 500
    assert cfg.resumable is False
    assert cfg.compaction is None


def test_compaction_config():
    cc = CompactionConfig(interval=5, overlap=2)
    assert cc.interval == 5
    assert cc.overlap == 2
    assert cc.token_threshold is None


# --- AgentEvent ---

def test_agent_event_defaults():
    evt = AgentEvent(author="test")
    assert evt.content is None
    assert evt.state_delta == {}
    assert evt.is_final is False
    assert evt.is_partial is False
    assert evt.transfer_to is None


def test_agent_event_with_content():
    evt = AgentEvent(author="agent1", content="Hello", is_final=True)
    assert evt.content == "Hello"
    assert evt.is_final is True


# --- Node type union ---

def test_node_union_includes_primitive_types():
    """The Node type should accept all primitive IR types."""
    fn = lambda s: s
    nodes = [
        TransformNode(name="t", fn=fn),
        TapNode(name="t", fn=fn),
        GateNode(name="g", predicate=fn),
        RouteNode(name="r"),
        FallbackNode(name="f"),
        RaceNode(name="r"),
    ]
    for n in nodes:
        assert hasattr(n, "name")
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_ir_nodes.py -v
```

Expected: FAIL — `_ir` module doesn't exist

**Step 3: Implement `_ir.py`**

Create `src/adk_fluent/_ir.py`:

```python
"""Hand-written IR node types for adk-fluent primitives.

These represent concepts that have no ADK counterpart — they are
adk-fluent inventions compiled to custom BaseAgent subclasses by the
ADK backend.

For ADK-native agent types (AgentNode, SequenceNode, etc.), see
_ir_generated.py which is produced by scripts/ir_generator.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Union

__all__ = [
    # Primitive nodes
    "TransformNode", "TapNode", "FallbackNode", "RaceNode",
    "GateNode", "MapOverNode", "TimeoutNode", "RouteNode",
    "TransferNode",
    # Config
    "ExecutionConfig", "CompactionConfig",
    # Events
    "AgentEvent", "ToolCallInfo", "ToolResponseInfo",
    # Type union
    "Node",
]


# ======================================================================
# Primitive IR nodes (hand-written — no ADK counterpart)
# ======================================================================

@dataclass(frozen=True)
class TransformNode:
    """Zero-cost state transform. No LLM call."""
    name: str
    fn: Callable
    semantics: Literal["merge", "replace_session", "delete_keys"] = "merge"
    scope: Literal["session", "all"] = "session"
    affected_keys: frozenset[str] | None = None


@dataclass(frozen=True)
class TapNode:
    """Zero-cost observation. No LLM call, no state mutation."""
    name: str
    fn: Callable


@dataclass(frozen=True)
class FallbackNode:
    """Try children in order. First success wins."""
    name: str
    children: tuple[Node, ...] = ()


@dataclass(frozen=True)
class RaceNode:
    """Run children concurrently. First to finish wins."""
    name: str
    children: tuple[Node, ...] = ()


@dataclass(frozen=True)
class GateNode:
    """Human-in-the-loop approval gate."""
    name: str
    predicate: Callable
    message: str = "Approval required"
    gate_key: str = "_gate_approved"


@dataclass(frozen=True)
class MapOverNode:
    """Iterate a sub-agent over each item in a state list."""
    name: str
    list_key: str
    body: Node
    item_key: str = "_item"
    output_key: str = "results"


@dataclass(frozen=True)
class TimeoutNode:
    """Wrap a sub-agent with a time limit."""
    name: str
    body: Node
    seconds: float


@dataclass(frozen=True)
class RouteNode:
    """Deterministic state-based routing. No LLM call."""
    name: str
    key: str | None = None
    rules: tuple[tuple[Callable, Node], ...] = ()
    default: Node | None = None


@dataclass(frozen=True)
class TransferNode:
    """Hard agent transfer (ADK's transfer_to_agent)."""
    name: str
    target: str
    condition: Callable | None = None


# ======================================================================
# Execution configuration
# ======================================================================

@dataclass(frozen=True)
class CompactionConfig:
    """Event compaction settings (maps to ADK EventsCompactionConfig)."""
    interval: int = 10
    overlap: int = 2
    token_threshold: int | None = None
    event_retention_size: int | None = None


@dataclass(frozen=True)
class ExecutionConfig:
    """Top-level execution configuration."""
    app_name: str = "adk_fluent_app"
    max_llm_calls: int = 500
    timeout_seconds: float | None = None
    streaming_mode: Literal["none", "sse", "bidi"] = "none"
    resumable: bool = False
    compaction: CompactionConfig | None = None
    custom_metadata: dict[str, Any] | None = None


# ======================================================================
# Backend-agnostic event types
# ======================================================================

@dataclass
class ToolCallInfo:
    """A tool invocation within an event."""
    tool_name: str
    args: dict[str, Any]
    call_id: str


@dataclass
class ToolResponseInfo:
    """A tool response within an event."""
    tool_name: str
    result: Any
    call_id: str


@dataclass
class AgentEvent:
    """Backend-agnostic representation of an execution event."""
    author: str
    content: str | None = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    artifact_delta: dict[str, int] = field(default_factory=dict)
    transfer_to: str | None = None
    escalate: bool = False
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    tool_responses: list[ToolResponseInfo] = field(default_factory=list)
    is_final: bool = False
    is_partial: bool = False
    end_of_agent: bool = False
    agent_state: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


# ======================================================================
# Node type union (extended by _ir_generated.py)
# ======================================================================

# This is the base union of hand-written node types.
# _ir_generated.py extends this with generated ADK node types.
Node = Union[
    TransformNode, TapNode, FallbackNode, RaceNode,
    GateNode, MapOverNode, TimeoutNode, RouteNode,
    TransferNode,
]
```

**Step 4: Run tests**

```bash
pytest tests/manual/test_ir_nodes.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_ir.py tests/manual/test_ir_nodes.py
git commit -m "feat: add hand-written IR node types for adk-fluent primitives"
```

______________________________________________________________________

### Task 2: IR Generator Script + Generated IR Nodes

**Problem:** ADK agent types (LlmAgent, SequentialAgent, ParallelAgent, LoopAgent) need IR node types that mirror their Pydantic fields. These should be auto-generated from `manifest.json` so they evolve with ADK.

**Files:**

- Create: `scripts/ir_generator.py`
- Create: `src/adk_fluent/_ir_generated.py` (generated output)
- Modify: `.github/workflows/ci.yml` (add ir_generator to pipeline)
- Create: `tests/manual/test_ir_generated.py`

**Step 1: Write tests for generated IR nodes**

Create `tests/manual/test_ir_generated.py`:

```python
"""Tests for generated IR node types."""
import pytest


def test_agent_node_exists():
    from adk_fluent._ir_generated import AgentNode
    assert AgentNode is not None


def test_sequence_node_exists():
    from adk_fluent._ir_generated import SequenceNode
    assert SequenceNode is not None


def test_parallel_node_exists():
    from adk_fluent._ir_generated import ParallelNode
    assert ParallelNode is not None


def test_loop_node_exists():
    from adk_fluent._ir_generated import LoopNode
    assert LoopNode is not None


def test_agent_node_is_frozen():
    from adk_fluent._ir_generated import AgentNode
    node = AgentNode(name="test")
    with pytest.raises(AttributeError):
        node.name = "changed"


def test_agent_node_has_model_field():
    from adk_fluent._ir_generated import AgentNode
    node = AgentNode(name="test", model="gemini-2.5-flash")
    assert node.model == "gemini-2.5-flash"


def test_agent_node_has_instruction_field():
    from adk_fluent._ir_generated import AgentNode
    node = AgentNode(name="test", instruction="Help the user")
    assert node.instruction == "Help the user"


def test_agent_node_has_children():
    from adk_fluent._ir_generated import AgentNode
    child = AgentNode(name="child")
    parent = AgentNode(name="parent", children=(child,))
    assert len(parent.children) == 1
    assert parent.children[0].name == "child"


def test_agent_node_has_callbacks():
    from adk_fluent._ir_generated import AgentNode
    fn = lambda ctx: None
    node = AgentNode(name="test", callbacks={"before_model": (fn,)})
    assert "before_model" in node.callbacks


def test_agent_node_has_adk_fluent_extensions():
    from adk_fluent._ir_generated import AgentNode
    node = AgentNode(name="test", writes_keys=frozenset({"intent"}))
    assert "intent" in node.writes_keys


def test_sequence_node_has_children():
    from adk_fluent._ir_generated import AgentNode, SequenceNode
    c1 = AgentNode(name="a")
    c2 = AgentNode(name="b")
    seq = SequenceNode(name="pipe", children=(c1, c2))
    assert len(seq.children) == 2


def test_loop_node_has_max_iterations():
    from adk_fluent._ir_generated import AgentNode, LoopNode
    body = AgentNode(name="step")
    loop = LoopNode(name="loop", children=(body,), max_iterations=5)
    assert loop.max_iterations == 5


def test_all_node_type_union():
    """The full Node union should include both generated and hand-written types."""
    from adk_fluent._ir_generated import FullNode, AgentNode
    from adk_fluent._ir import TransformNode
    # Both should be valid Node types
    assert AgentNode is not None
    assert TransformNode is not None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_ir_generated.py -v
```

Expected: FAIL — `_ir_generated` module doesn't exist

**Step 3: Create the IR generator script**

Create `scripts/ir_generator.py`:

```python
#!/usr/bin/env python3
"""Generate frozen dataclass IR nodes from ADK manifest.

Reads manifest.json (produced by scanner.py) and generates _ir_generated.py
containing IR node types that mirror ADK agent Pydantic models.

Usage:
    python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ADK agent classes that map to IR node types
AGENT_CLASS_MAP = {
    "LlmAgent": "AgentNode",
    "SequentialAgent": "SequenceNode",
    "ParallelAgent": "ParallelNode",
    "LoopAgent": "LoopNode",
}

# Fields to skip (internal ADK machinery, not part of the expression)
SKIP_FIELDS = {
    "parent_agent",  # Set internally by ADK
    "canonical_model",  # Derived field
    "model_config",  # Pydantic internals
}

# Fields to rename for IR clarity
RENAMES = {
    "sub_agents": "children",
}

# Fields that are callbacks (stored as tuples in IR)
CALLBACK_SUFFIX = "_callback"

# adk-fluent extension fields (appended to every node)
EXTENSION_FIELDS = [
    ("writes_keys", "frozenset[str]", "frozenset()"),
    ("reads_keys", "frozenset[str]", "frozenset()"),
    ("produces_type", "type | None", "None"),
    ("consumes_type", "type | None", "None"),
]


def load_manifest(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def find_class_info(manifest: dict, class_name: str) -> dict | None:
    for cls in manifest["classes"]:
        if cls["name"] == class_name:
            return cls
    return None


def ir_field_type(field_info: dict, ir_name: str) -> str:
    """Map a manifest field type to an IR dataclass type."""
    type_str = field_info.get("type_str", "Any")
    name = ir_name

    # Callbacks become tuple[Callable, ...]
    if name.endswith(CALLBACK_SUFFIX) or field_info.get("is_callback"):
        return "tuple[Callable, ...]"

    # Lists become tuples (frozen)
    if field_info.get("is_list"):
        return "tuple[Any, ...]"

    # Children (sub_agents → children) become tuple of Nodes
    if name == "children":
        return "tuple[Any, ...]"  # Will be Node once union is defined

    # Simplify complex generics to Any
    if "Union" in type_str or "|" in type_str:
        return "Any"

    # Map common types
    type_map = {
        "str": "str | None",
        "int": "int",
        "float": "float",
        "bool": "bool",
        "dict": "dict[str, Any]",
        "list": "list[Any]",
    }
    for key, val in type_map.items():
        if type_str.startswith(key):
            return val

    return "Any"


def ir_field_default(field_info: dict, ir_type: str) -> str:
    """Determine the default value for an IR field."""
    if ir_type.startswith("tuple"):
        return "()"
    if ir_type.endswith("| None"):
        return "None"
    if ir_type == "bool":
        default = field_info.get("default", "False")
        return str(default) if default not in (None, "PydanticUndefined") else "False"
    if ir_type == "int":
        default = field_info.get("default")
        return str(default) if default not in (None, "PydanticUndefined") else "0"
    if ir_type == "float":
        default = field_info.get("default")
        return str(default) if default not in (None, "PydanticUndefined") else "0.0"
    if ir_type.startswith("dict"):
        return "field(default_factory=dict)"
    if ir_type.startswith("list"):
        return "field(default_factory=list)"
    return "None"


def generate_node_class(node_name: str, class_info: dict) -> str:
    """Generate a frozen dataclass IR node from manifest class info."""
    lines = []
    lines.append(f"@dataclass(frozen=True)")
    lines.append(f"class {node_name}:")
    lines.append(f'    """IR node generated from ADK {class_info["name"]}."""')

    # Always have name as first required field
    lines.append(f"    name: str")

    # Process ADK fields
    has_field_factory = False
    regular_fields = []
    callback_fields = []

    for f in class_info.get("fields", []):
        fname = f["name"]
        if fname in SKIP_FIELDS or fname == "name":
            continue
        ir_name = RENAMES.get(fname, fname)

        # Separate callbacks from regular fields
        if fname.endswith(CALLBACK_SUFFIX) or f.get("is_callback"):
            callback_fields.append((ir_name, f))
        else:
            regular_fields.append((ir_name, f))

    # Emit regular fields (with defaults)
    for ir_name, f in regular_fields:
        ir_type = ir_field_type(f, ir_name)
        ir_default = ir_field_default(f, ir_type)
        if "field(" in ir_default:
            has_field_factory = True
        lines.append(f"    {ir_name}: {ir_type} = {ir_default}")

    # Emit callbacks as a single dict
    lines.append(f"    callbacks: dict[str, tuple[Callable, ...]] = field(default_factory=dict)")
    has_field_factory = True

    # Emit adk-fluent extensions
    for ext_name, ext_type, ext_default in EXTENSION_FIELDS:
        lines.append(f"    {ext_name}: {ext_type} = {ext_default}")

    lines.append("")
    return "\n".join(lines)


def generate_ir_module(manifest: dict) -> str:
    """Generate the complete _ir_generated.py module."""
    timestamp = datetime.now(timezone.utc).isoformat()
    adk_version = manifest.get("adk_version", "unknown")

    header = f'''"""Auto-generated IR nodes from ADK model introspection.

DO NOT EDIT — regenerate with:
    python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py

ADK version: {adk_version}
Generated: {timestamp}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Union

from adk_fluent._ir import (
    TransformNode, TapNode, FallbackNode, RaceNode,
    GateNode, MapOverNode, TimeoutNode, RouteNode,
    TransferNode,
)

'''

    body_parts = []
    node_names = []

    for adk_class_name, ir_node_name in AGENT_CLASS_MAP.items():
        class_info = find_class_info(manifest, adk_class_name)
        if class_info is None:
            print(f"WARNING: {adk_class_name} not found in manifest, skipping",
                  file=sys.stderr)
            continue
        body_parts.append(generate_node_class(ir_node_name, class_info))
        node_names.append(ir_node_name)

    # Generate full Node union (generated + hand-written)
    all_generated = ", ".join(node_names)
    hand_written = (
        "TransformNode, TapNode, FallbackNode, RaceNode, "
        "GateNode, MapOverNode, TimeoutNode, RouteNode, TransferNode"
    )

    footer = f'''
# Complete Node type union (generated + hand-written primitives)
FullNode = Union[{all_generated}, {hand_written}]

__all__ = [{", ".join(f'"{n}"' for n in node_names)}, "FullNode"]
'''

    return header + "\n".join(body_parts) + footer


def main():
    parser = argparse.ArgumentParser(description="Generate IR nodes from ADK manifest")
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("--output", "-o", default="src/adk_fluent/_ir_generated.py",
                        help="Output file path")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    code = generate_ir_module(manifest)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code)

    print(f"  IR nodes generated: {len(AGENT_CLASS_MAP)}")
    print(f"  Output: {args.output}")


if __name__ == "__main__":
    main()
```

**Step 4: Run the generator**

```bash
python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
```

**Step 5: Run tests**

```bash
pytest tests/manual/test_ir_generated.py -v
```

Expected: All PASS

**Step 6: Update CI pipeline**

In `.github/workflows/ci.yml`, add `ir_generator.py` to the codegen step in both `test` and `build` jobs:

```yaml
      - name: Run codegen pipeline
        run: |
          python scripts/scanner.py -o manifest.json
          python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
          python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
          python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
```

**Step 7: Commit**

```bash
git add scripts/ir_generator.py src/adk_fluent/_ir_generated.py tests/manual/test_ir_generated.py .github/workflows/ci.yml
git commit -m "feat: add seed-based IR generator that produces IR nodes from ADK manifest"
```

______________________________________________________________________

### Task 3: Add `to_ir()` to Primitive Builders

**Problem:** The 8 primitive builders (\_FnStepBuilder, \_TapBuilder, \_FallbackBuilder, \_GateBuilder, \_RaceBuilder, \_MapOverBuilder, \_TimeoutBuilder) and Route need `to_ir()` methods that return the corresponding IR node types.

**Files:**

- Modify: `src/adk_fluent/_base.py`
- Modify: `src/adk_fluent/_routing.py`
- Create: `tests/manual/test_to_ir_primitives.py`

**Step 1: Write tests**

Create `tests/manual/test_to_ir_primitives.py`:

```python
"""Tests for to_ir() on primitive builders."""
import pytest
from adk_fluent._ir import (
    TransformNode, TapNode, FallbackNode, RaceNode,
    GateNode, MapOverNode, TimeoutNode, RouteNode,
)


def test_fn_step_to_ir():
    from adk_fluent._base import _fn_step
    fn = lambda s: {"x": 1}
    ir = _fn_step(fn).to_ir()
    assert isinstance(ir, TransformNode)
    assert ir.fn is fn
    assert ir.semantics == "merge"


def test_fn_step_with_state_replacement_to_ir():
    from adk_fluent._base import _fn_step
    from adk_fluent._transforms import S
    fn = S.pick("a", "b")
    ir = _fn_step(fn).to_ir()
    assert isinstance(ir, TransformNode)
    assert ir.semantics == "replace_session"


def test_tap_to_ir():
    from adk_fluent import tap
    fn = lambda s: print(s)
    ir = tap(fn).to_ir()
    assert isinstance(ir, TapNode)
    assert ir.fn is fn


def test_fallback_to_ir():
    from adk_fluent import Agent
    from adk_fluent._base import _FallbackBuilder
    a = Agent("a")
    b = Agent("b")
    ir = _FallbackBuilder("fb", [a, b]).to_ir()
    assert isinstance(ir, FallbackNode)
    assert len(ir.children) == 2


def test_gate_to_ir():
    from adk_fluent import gate
    ir = gate(lambda s: s.get("approved")).to_ir()
    assert isinstance(ir, GateNode)
    assert ir.message == "Approval required"


def test_race_to_ir():
    from adk_fluent import Agent, race
    ir = race(Agent("a"), Agent("b")).to_ir()
    assert isinstance(ir, RaceNode)
    assert len(ir.children) == 2


def test_map_over_to_ir():
    from adk_fluent import Agent, map_over
    ir = map_over("items", Agent("processor")).to_ir()
    assert isinstance(ir, MapOverNode)
    assert ir.list_key == "items"
    assert ir.item_key == "_item"


def test_timeout_to_ir():
    from adk_fluent import Agent
    from adk_fluent._base import _TimeoutBuilder
    ir = _TimeoutBuilder("to", Agent("a"), 30.0).to_ir()
    assert isinstance(ir, TimeoutNode)
    assert ir.seconds == 30.0


def test_route_to_ir():
    from adk_fluent import Agent
    from adk_fluent._routing import Route
    ir = Route("intent").eq("billing", Agent("b")).otherwise(Agent("d")).to_ir()
    assert isinstance(ir, RouteNode)
    assert ir.key == "intent"
    assert len(ir.rules) == 1
    assert ir.default is not None


def test_nested_to_ir_recursion():
    """to_ir() should recursively convert child builders."""
    from adk_fluent import Agent
    from adk_fluent._base import _FallbackBuilder
    a = Agent("a")
    b = Agent("b")
    ir = _FallbackBuilder("fb", [a, b]).to_ir()
    # Children should be IR nodes, not builders
    from adk_fluent._ir_generated import AgentNode
    for child in ir.children:
        assert isinstance(child, AgentNode)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_to_ir_primitives.py -v
```

Expected: FAIL — `to_ir()` doesn't exist

**Step 3: Add `to_ir()` to BuilderBase**

In `src/adk_fluent/_base.py`, add a base `to_ir()` method to `BuilderBase`:

```python
def to_ir(self):
    """Convert this builder to an IR node tree.

    Subclasses with custom build() methods must override this.
    Generated builders get to_ir() from the generator.
    """
    raise NotImplementedError(
        f"{self.__class__.__name__}.to_ir() is not implemented. "
        f"Use .build() for direct ADK object construction."
    )
```

**Step 4: Add `to_ir()` to each primitive builder**

In `_base.py`, add `to_ir()` methods:

```python
# _FnStepBuilder
def to_ir(self):
    from adk_fluent._ir import TransformNode
    from adk_fluent._transforms import StateDelta, StateReplacement
    # Detect semantics by running fn with empty state
    try:
        sample = self._fn({})
        if isinstance(sample, StateReplacement):
            semantics = "replace_session"
        elif isinstance(sample, StateDelta):
            semantics = "merge"
        else:
            semantics = "merge"
    except Exception:
        semantics = "merge"
    return TransformNode(name=self._config["name"], fn=self._fn, semantics=semantics)

# _TapBuilder
def to_ir(self):
    from adk_fluent._ir import TapNode
    return TapNode(name=self._config["name"], fn=self._fn)

# _FallbackBuilder
def to_ir(self):
    from adk_fluent._ir import FallbackNode
    children = tuple(
        c.to_ir() if isinstance(c, BuilderBase) else c
        for c in self._children
    )
    return FallbackNode(name=self._config["name"], children=children)

# _GateBuilder
def to_ir(self):
    from adk_fluent._ir import GateNode
    return GateNode(
        name=self._config["name"],
        predicate=self._predicate,
        message=self._message,
        gate_key=self._gate_key,
    )

# _RaceBuilder
def to_ir(self):
    from adk_fluent._ir import RaceNode
    children = tuple(
        a.to_ir() if isinstance(a, BuilderBase) else a
        for a in self._agents
    )
    return RaceNode(name=self._config["name"], children=children)

# _MapOverBuilder
def to_ir(self):
    from adk_fluent._ir import MapOverNode
    body = self._agent.to_ir() if isinstance(self._agent, BuilderBase) else self._agent
    return MapOverNode(
        name=self._config["name"],
        list_key=self._list_key,
        body=body,
        item_key=self._item_key,
        output_key=self._output_key,
    )

# _TimeoutBuilder
def to_ir(self):
    from adk_fluent._ir import TimeoutNode
    body = self._agent.to_ir() if isinstance(self._agent, BuilderBase) else self._agent
    return TimeoutNode(
        name=self._config["name"],
        body=body,
        seconds=self._seconds,
    )
```

**Step 5: Add `to_ir()` to Route**

In `src/adk_fluent/_routing.py`:

```python
def to_ir(self):
    """Convert this Route to an IR RouteNode."""
    from adk_fluent._base import BuilderBase
    from adk_fluent._ir import RouteNode

    ir_rules = []
    for pred, agent_or_builder in self._rules:
        if isinstance(agent_or_builder, BuilderBase):
            ir_agent = agent_or_builder.to_ir()
        else:
            ir_agent = agent_or_builder
        ir_rules.append((pred, ir_agent))

    ir_default = None
    if self._default is not None:
        if isinstance(self._default, BuilderBase):
            ir_default = self._default.to_ir()
        else:
            ir_default = self._default

    name = f"route_{self._key}" if self._key else "route"
    return RouteNode(
        name=name,
        key=self._key,
        rules=tuple(ir_rules),
        default=ir_default,
    )
```

**Step 6: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: All PASS

**Step 7: Commit**

```bash
git add src/adk_fluent/_base.py src/adk_fluent/_routing.py tests/manual/test_to_ir_primitives.py
git commit -m "feat: add to_ir() to all primitive builders and Route"
```

______________________________________________________________________

### Task 4: Add `to_ir()` to Generated Builders

**Problem:** Generated builders (Agent, Pipeline, FanOut, Loop, and all config/tool/service builders) need `to_ir()` methods. The generator must emit these alongside `build()`.

**Files:**

- Modify: `scripts/generator.py` (add `gen_to_ir_method()`)
- Regenerate: All generated files
- Create: `tests/manual/test_to_ir_generated.py`

**Step 1: Write tests**

Create `tests/manual/test_to_ir_generated.py`:

```python
"""Tests for to_ir() on generated builders."""
from adk_fluent._ir_generated import AgentNode, SequenceNode, ParallelNode, LoopNode


def test_agent_to_ir():
    from adk_fluent import Agent
    ir = Agent("test", "gemini-2.5-flash").instruct("Help").to_ir()
    assert isinstance(ir, AgentNode)
    assert ir.name == "test"
    assert ir.model == "gemini-2.5-flash"
    assert ir.instruction == "Help"


def test_agent_with_tools_to_ir():
    from adk_fluent import Agent
    fn = lambda x: x
    ir = Agent("test").tool(fn).to_ir()
    assert isinstance(ir, AgentNode)
    assert fn in ir.tools


def test_agent_with_callbacks_to_ir():
    from adk_fluent import Agent
    fn = lambda ctx: None
    ir = Agent("test").before_model(fn).to_ir()
    assert isinstance(ir, AgentNode)
    assert "before_model_callback" in ir.callbacks
    assert fn in ir.callbacks["before_model_callback"]


def test_agent_with_output_key_writes_keys():
    from adk_fluent import Agent
    ir = Agent("test").outputs("intent").to_ir()
    assert isinstance(ir, AgentNode)
    assert "intent" in ir.writes_keys


def test_agent_with_instruction_reads_keys():
    from adk_fluent import Agent
    ir = Agent("test").instruct("Process {user_query} for {user_id}").to_ir()
    assert isinstance(ir, AgentNode)
    assert "user_query" in ir.reads_keys
    assert "user_id" in ir.reads_keys


def test_pipeline_to_ir():
    from adk_fluent import Agent
    pipeline = Agent("a") >> Agent("b") >> Agent("c")
    ir = pipeline.to_ir()
    assert isinstance(ir, SequenceNode)
    assert len(ir.children) == 3
    assert all(isinstance(c, AgentNode) for c in ir.children)


def test_pipeline_with_fn_step():
    from adk_fluent import Agent
    from adk_fluent._ir import TransformNode
    pipeline = Agent("a") >> (lambda s: {"x": 1}) >> Agent("b")
    ir = pipeline.to_ir()
    assert isinstance(ir, SequenceNode)
    assert isinstance(ir.children[1], TransformNode)


def test_fanout_to_ir():
    from adk_fluent import Agent
    fanout = Agent("a") | Agent("b")
    ir = fanout.to_ir()
    assert isinstance(ir, ParallelNode)
    assert len(ir.children) == 2


def test_loop_to_ir():
    from adk_fluent import Agent
    loop = Agent("step") * 5
    ir = loop.to_ir()
    assert isinstance(ir, LoopNode)
    assert ir.max_iterations == 5


def test_nested_pipeline_to_ir():
    """Nested structures should recursively convert."""
    from adk_fluent import Agent
    pipeline = Agent("a") >> (Agent("b") | Agent("c")) >> Agent("d")
    ir = pipeline.to_ir()
    assert isinstance(ir, SequenceNode)
    assert isinstance(ir.children[1], ParallelNode)
```

**Step 2: Implement `gen_to_ir_method()` in generator.py**

Add a new function to `scripts/generator.py`:

```python
def gen_to_ir_method(spec: BuilderSpec) -> str:
    """Generate the to_ir() method that produces an IR node."""
    if spec.is_composite or spec.is_standalone:
        return ""  # Hand-written composites (Pipeline, FanOut, Loop) have custom to_ir()

    class_name = spec.name  # e.g., "Agent"
    source_class = spec.source_class  # e.g., "LlmAgent"

    # Map source class to IR node name
    ir_class_map = {
        "LlmAgent": "AgentNode",
        "SequentialAgent": "SequenceNode",
        "ParallelAgent": "ParallelNode",
        "LoopAgent": "LoopNode",
    }
    ir_node_name = ir_class_map.get(source_class)
    if ir_node_name is None:
        return ""  # No IR mapping for this builder (configs, tools, etc.)

    return f'''
    def to_ir(self):
        """Convert to IR {ir_node_name}."""
        from adk_fluent._ir_generated import {ir_node_name}
        from adk_fluent._base import BuilderBase
        import re

        config = {{k: v for k, v in self._config.items() if not k.startswith("_")}}

        # Collect tools
        tools = tuple(self._lists.get("tools", []))

        # Collect callbacks
        callbacks = {{}}
        for field, fns in self._callbacks.items():
            if fns:
                callbacks[field] = tuple(fns)

        # Recursively convert sub-builders in lists
        children = []
        for item in self._lists.get("sub_agents", []):
            if isinstance(item, BuilderBase):
                children.append(item.to_ir())
            else:
                children.append(item)

        # Data-flow analysis
        instruction = config.get("instruction", "")
        reads_keys = frozenset()
        if isinstance(instruction, str):
            reads_keys = frozenset(re.findall(r"\\{{(\\w+)\\}}", instruction))

        output_key = config.get("output_key")
        writes_keys = frozenset({{output_key}}) if output_key else frozenset()

        return {ir_node_name}(
            name=config.get("name", "unnamed"),
            model=config.get("model"),
            instruction=config.get("instruction"),
            tools=tools,
            children=tuple(children),
            callbacks=callbacks,
            output_key=output_key,
            writes_keys=writes_keys,
            reads_keys=reads_keys,
            **{{k: v for k, v in config.items()
               if k not in ("name", "model", "instruction", "output_key", "sub_agents")
               and hasattr({ir_node_name}, k)}},
        )
'''
```

Then add `gen_to_ir_method(spec)` to `gen_runtime_class()` after the build method.

**Important:** For composite builders (Pipeline, FanOut, Loop), add hand-written `to_ir()` methods in `_base.py` or the corresponding generated files. The generator should emit `to_ir()` only for non-composite, non-standalone specs that have IR mappings.

For Pipeline (SequentialAgent), FanOut (ParallelAgent), and Loop (LoopAgent), add hand-written `to_ir()` methods. These are already generated builders but are tagged `is_composite=True` in the seed, so the generator skips them. Add `to_ir()` as extras in `seeds/seed.manual.toml` or hand-write them in the generated output post-processing.

The simplest approach: add `to_ir()` directly in the composite builder classes. Since Pipeline, FanOut, and Loop are generated from seed extras, add `to_ir` as a `runtime_helper` extra that calls a helper in `_helpers.py`, or add it directly via template injection in the generator.

Given the complexity, the recommended approach is to add `to_ir()` methods as seed extras with behavior type `custom_code` or simply add them to the generated files and update the generator to preserve them on regeneration.

**Step 3: Regenerate all builders**

```bash
python scripts/scanner.py -o manifest.json
python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
```

**Step 4: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: All PASS

**Step 5: Commit**

```bash
git add scripts/generator.py seeds/seed.manual.toml src/adk_fluent/*.py tests/manual/test_to_ir_generated.py
git commit -m "feat: add to_ir() to generated builders with data-flow analysis"
```

______________________________________________________________________

### Task 5: Backend Protocol + AgentEvent Convenience

**Problem:** Need a formal protocol for backends that can compile IR and execute it. The `AgentEvent` type is already defined in `_ir.py` (Task 1); this task adds the protocol and convenience functions.

**Files:**

- Create: `src/adk_fluent/backends/__init__.py`
- Create: `src/adk_fluent/backends/_protocol.py`
- Create: `tests/manual/test_backend_protocol.py`

**Step 1: Write tests**

Create `tests/manual/test_backend_protocol.py`:

```python
"""Tests for the backend protocol."""
import pytest
from adk_fluent.backends._protocol import Backend, final_text
from adk_fluent._ir import AgentEvent


def test_backend_is_runtime_checkable():
    """Backend should be a runtime-checkable Protocol."""
    assert hasattr(Backend, '__protocol_attrs__') or hasattr(Backend, '__abstractmethods__')


def test_final_text_extracts_last_final_content():
    events = [
        AgentEvent(author="a", content="Step 1"),
        AgentEvent(author="a", content="Step 2"),
        AgentEvent(author="a", content="Final answer", is_final=True),
    ]
    assert final_text(events) == "Final answer"


def test_final_text_returns_empty_on_no_final():
    events = [
        AgentEvent(author="a", content="Step 1"),
    ]
    assert final_text(events) == ""


def test_final_text_handles_empty_events():
    assert final_text([]) == ""


def test_final_text_skips_partial_events():
    events = [
        AgentEvent(author="a", content="Partial", is_partial=True),
        AgentEvent(author="a", content="Done", is_final=True),
    ]
    assert final_text(events) == "Done"
```

**Step 2: Implement backend protocol**

Create `src/adk_fluent/backends/__init__.py`:

```python
"""Backend protocol and implementations for adk-fluent IR compilation."""
from adk_fluent.backends._protocol import Backend, final_text

__all__ = ["Backend", "final_text"]
```

Create `src/adk_fluent/backends/_protocol.py`:

```python
"""Backend protocol — the contract between IR and execution engines."""
from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable

from adk_fluent._ir import AgentEvent, ExecutionConfig


@runtime_checkable
class Backend(Protocol):
    """A backend compiles IR node trees into runnable objects and executes them."""

    def compile(self, node: Any, config: ExecutionConfig | None = None) -> Any:
        """Transform an IR node tree into a backend-specific runnable."""
        ...

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute the compiled runnable and return all events."""
        ...

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Stream events as they occur."""
        ...


def final_text(events: list[AgentEvent]) -> str:
    """Extract the final response text from an event list."""
    for event in reversed(events):
        if event.is_final and event.content:
            return event.content
    return ""
```

**Step 3: Run tests**

```bash
pytest tests/manual/test_backend_protocol.py -v
```

Expected: All PASS

**Step 4: Commit**

```bash
git add src/adk_fluent/backends/ tests/manual/test_backend_protocol.py
git commit -m "feat: add Backend protocol and AgentEvent convenience functions"
```

______________________________________________________________________

### Task 6: ADK Backend — Compile IR to Native ADK Objects

**Problem:** Need a concrete backend that compiles IR nodes into native ADK objects (LlmAgent, SequentialAgent, etc.) and executes them via Runner.

**Files:**

- Create: `src/adk_fluent/backends/adk.py`
- Create: `tests/manual/test_adk_backend.py`

**Step 1: Write tests**

Create `tests/manual/test_adk_backend.py`:

```python
"""Tests for the ADK backend compiler."""
import pytest
from adk_fluent.backends.adk import ADKBackend
from adk_fluent._ir import TransformNode, TapNode, FallbackNode, RouteNode
from adk_fluent._ir_generated import AgentNode, SequenceNode, ParallelNode, LoopNode


@pytest.fixture
def backend():
    return ADKBackend()


def test_compile_agent_node(backend):
    from google.adk.agents.llm_agent import LlmAgent
    node = AgentNode(name="test", model="gemini-2.5-flash", instruction="Help")
    result = backend.compile(node)
    # Returns an App wrapping the agent
    assert hasattr(result, 'root_agent')
    agent = result.root_agent
    assert isinstance(agent, LlmAgent)
    assert agent.name == "test"
    assert agent.model == "gemini-2.5-flash"


def test_compile_sequence_node(backend):
    from google.adk.agents.sequential_agent import SequentialAgent
    children = (AgentNode(name="a"), AgentNode(name="b"))
    node = SequenceNode(name="pipe", children=children)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, SequentialAgent)
    assert len(agent.sub_agents) == 2


def test_compile_parallel_node(backend):
    from google.adk.agents.parallel_agent import ParallelAgent
    children = (AgentNode(name="a"), AgentNode(name="b"))
    node = ParallelNode(name="fan", children=children)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, ParallelAgent)


def test_compile_loop_node(backend):
    from google.adk.agents.loop_agent import LoopAgent
    body = AgentNode(name="step")
    node = LoopNode(name="loop", children=(body,), max_iterations=3)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, LoopAgent)


def test_compile_transform_node(backend):
    from adk_fluent._base import FnAgent
    fn = lambda s: {"x": 1}
    node = TransformNode(name="t", fn=fn)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, FnAgent)


def test_compile_tap_node(backend):
    from adk_fluent._base import TapAgent
    fn = lambda s: None
    node = TapNode(name="tap", fn=fn)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, TapAgent)


def test_compile_nested_ir(backend):
    """Nested IR trees should compile recursively."""
    from google.adk.agents.sequential_agent import SequentialAgent
    from google.adk.agents.llm_agent import LlmAgent

    inner = SequenceNode(name="inner", children=(
        AgentNode(name="a"), AgentNode(name="b")
    ))
    outer = SequenceNode(name="outer", children=(
        AgentNode(name="pre"), inner, AgentNode(name="post")
    ))
    result = backend.compile(outer)
    agent = result.root_agent
    assert isinstance(agent, SequentialAgent)
    assert isinstance(agent.sub_agents[1], SequentialAgent)


def test_compile_with_execution_config(backend):
    from adk_fluent._ir import ExecutionConfig
    node = AgentNode(name="test")
    config = ExecutionConfig(app_name="myapp", resumable=True)
    result = backend.compile(node, config=config)
    assert result.name == "myapp"


def test_round_trip_builder_to_ir_to_adk(backend):
    """Full round-trip: builder → IR → ADK object."""
    from adk_fluent import Agent
    from google.adk.agents.llm_agent import LlmAgent

    builder = Agent("classifier", "gemini-2.5-flash").instruct("Classify intent")
    ir = builder.to_ir()
    compiled = backend.compile(ir)
    agent = compiled.root_agent
    assert isinstance(agent, LlmAgent)
    assert agent.name == "classifier"
```

**Step 2: Implement ADK backend**

Create `src/adk_fluent/backends/adk.py`:

```python
"""ADK backend — compiles IR nodes into native ADK objects."""
from __future__ import annotations

from typing import Any, AsyncIterator

from adk_fluent._ir import (
    AgentEvent, ExecutionConfig, CompactionConfig,
    TransformNode, TapNode, FallbackNode, RaceNode,
    GateNode, MapOverNode, TimeoutNode, RouteNode,
    TransferNode,
)


class ADKBackend:
    """Compiles IR node trees into native ADK App objects and executes them."""

    def __init__(
        self,
        session_service=None,
        artifact_service=None,
        memory_service=None,
        credential_service=None,
    ):
        self._session_service = session_service
        self._artifact_service = artifact_service
        self._memory_service = memory_service
        self._credential_service = credential_service

    def compile(self, node, config: ExecutionConfig | None = None):
        """Compile an IR node tree into a native ADK App."""
        from google.adk.apps.app import App

        config = config or ExecutionConfig()
        root_agent = self._compile_node(node)

        app_kwargs = {
            "name": config.app_name,
            "root_agent": root_agent,
        }

        if config.resumable:
            from google.adk.apps.app import ResumabilityConfig
            app_kwargs["resumability_config"] = ResumabilityConfig(is_resumable=True)

        if config.compaction:
            from google.adk.apps.app import EventsCompactionConfig
            app_kwargs["events_compaction_config"] = EventsCompactionConfig(
                compaction_interval=config.compaction.interval,
                overlap_size=config.compaction.overlap,
            )

        return App(**app_kwargs)

    def _compile_node(self, node) -> Any:
        """Recursively compile a single IR node to an ADK agent."""
        # Import generated node types
        from adk_fluent._ir_generated import (
            AgentNode, SequenceNode, ParallelNode, LoopNode,
        )

        if isinstance(node, AgentNode):
            return self._compile_agent_node(node)
        elif isinstance(node, SequenceNode):
            return self._compile_sequence_node(node)
        elif isinstance(node, ParallelNode):
            return self._compile_parallel_node(node)
        elif isinstance(node, LoopNode):
            return self._compile_loop_node(node)
        elif isinstance(node, TransformNode):
            return self._compile_transform_node(node)
        elif isinstance(node, TapNode):
            return self._compile_tap_node(node)
        elif isinstance(node, FallbackNode):
            return self._compile_fallback_node(node)
        elif isinstance(node, RaceNode):
            return self._compile_race_node(node)
        elif isinstance(node, GateNode):
            return self._compile_gate_node(node)
        elif isinstance(node, MapOverNode):
            return self._compile_map_over_node(node)
        elif isinstance(node, TimeoutNode):
            return self._compile_timeout_node(node)
        elif isinstance(node, RouteNode):
            return self._compile_route_node(node)
        else:
            raise TypeError(f"Unknown IR node type: {type(node).__name__}")

    def _compile_agent_node(self, node):
        from google.adk.agents.llm_agent import LlmAgent
        from adk_fluent._base import _compose_callbacks

        kwargs = {"name": node.name}
        if node.model is not None:
            kwargs["model"] = node.model
        if node.instruction is not None:
            kwargs["instruction"] = node.instruction
        if node.tools:
            kwargs["tools"] = list(node.tools)
        if node.output_key is not None:
            kwargs["output_key"] = node.output_key

        # Compile children
        if node.children:
            kwargs["sub_agents"] = [self._compile_node(c) for c in node.children]

        # Compose callbacks
        for cb_field, fns in node.callbacks.items():
            if fns:
                kwargs[cb_field] = _compose_callbacks(list(fns))

        # Pass through remaining fields that LlmAgent accepts
        for attr in ("output_schema", "input_schema", "include_contents",
                      "generate_content_config", "planner", "code_executor",
                      "disallow_transfer_to_parent", "disallow_transfer_to_peers"):
            val = getattr(node, attr, None)
            if val is not None and val is not False:
                kwargs[attr] = val

        return LlmAgent(**kwargs)

    def _compile_sequence_node(self, node):
        from google.adk.agents.sequential_agent import SequentialAgent
        children = [self._compile_node(c) for c in node.children]
        return SequentialAgent(name=node.name, sub_agents=children)

    def _compile_parallel_node(self, node):
        from google.adk.agents.parallel_agent import ParallelAgent
        children = [self._compile_node(c) for c in node.children]
        return ParallelAgent(name=node.name, sub_agents=children)

    def _compile_loop_node(self, node):
        from google.adk.agents.loop_agent import LoopAgent
        children = [self._compile_node(c) for c in node.children]
        kwargs = {"name": node.name, "sub_agents": children}
        if hasattr(node, "max_iterations") and node.max_iterations:
            kwargs["max_iterations"] = node.max_iterations
        return LoopAgent(**kwargs)

    def _compile_transform_node(self, node):
        from adk_fluent._base import FnAgent
        return FnAgent(name=node.name, fn=node.fn)

    def _compile_tap_node(self, node):
        from adk_fluent._base import TapAgent
        return TapAgent(name=node.name, fn=node.fn)

    def _compile_fallback_node(self, node):
        from adk_fluent._base import FallbackAgent
        children = [self._compile_node(c) for c in node.children]
        return FallbackAgent(name=node.name, sub_agents=children)

    def _compile_race_node(self, node):
        from adk_fluent._base import RaceAgent
        children = [self._compile_node(c) for c in node.children]
        return RaceAgent(name=node.name, sub_agents=children)

    def _compile_gate_node(self, node):
        from adk_fluent._base import GateAgent
        return GateAgent(
            name=node.name,
            predicate=node.predicate,
            message=node.message,
            gate_key=node.gate_key,
        )

    def _compile_map_over_node(self, node):
        from adk_fluent._base import MapOverAgent
        body = self._compile_node(node.body)
        return MapOverAgent(
            name=node.name,
            list_key=node.list_key,
            sub_agent=body,
            item_key=node.item_key,
            output_key=node.output_key,
        )

    def _compile_timeout_node(self, node):
        from adk_fluent._base import TimeoutAgent
        body = self._compile_node(node.body)
        return TimeoutAgent(
            name=node.name,
            sub_agent=body,
            seconds=node.seconds,
        )

    def _compile_route_node(self, node):
        from adk_fluent._routing import _make_route_agent
        compiled_rules = []
        sub_agents = []
        for pred, child_node in node.rules:
            compiled = self._compile_node(child_node)
            compiled_rules.append((pred, compiled))
            sub_agents.append(compiled)
        compiled_default = None
        if node.default is not None:
            compiled_default = self._compile_node(node.default)
            sub_agents.append(compiled_default)
        return _make_route_agent(node.name, compiled_rules, compiled_default, sub_agents)

    async def run(self, compiled, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute compiled App and return all events."""
        from google.adk.runners import Runner
        from google.adk.sessions.in_memory_session_service import InMemorySessionService
        from google.genai import types

        session_service = self._session_service or InMemorySessionService()
        runner = Runner(
            app=compiled,
            session_service=session_service,
            artifact_service=self._artifact_service,
            memory_service=self._memory_service,
            credential_service=self._credential_service,
        )

        user_id = kwargs.get("user_id", "default_user")
        session_id = kwargs.get("session_id", None)

        if session_id is None:
            session = await session_service.create_session(
                app_name=compiled.name, user_id=user_id
            )
            session_id = session.id

        content = types.Content(
            role="user", parts=[types.Part.from_text(prompt)]
        )

        events = []
        async for adk_event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            events.append(self._to_agent_event(adk_event))
        return events

    async def stream(self, compiled, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Stream events from compiled App."""
        from google.adk.runners import Runner
        from google.adk.sessions.in_memory_session_service import InMemorySessionService
        from google.genai import types

        session_service = self._session_service or InMemorySessionService()
        runner = Runner(
            app=compiled,
            session_service=session_service,
        )

        user_id = kwargs.get("user_id", "default_user")
        session = await session_service.create_session(
            app_name=compiled.name, user_id=user_id
        )

        content = types.Content(
            role="user", parts=[types.Part.from_text(prompt)]
        )

        async for adk_event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            yield self._to_agent_event(adk_event)

    def _to_agent_event(self, event) -> AgentEvent:
        """Convert an ADK Event to a backend-agnostic AgentEvent."""
        content = None
        if event.content and event.content.parts:
            texts = [p.text for p in event.content.parts if p.text]
            content = "\n".join(texts) if texts else None

        return AgentEvent(
            author=event.author or "",
            content=content,
            state_delta=dict(event.actions.state_delta) if event.actions and event.actions.state_delta else {},
            artifact_delta=dict(event.actions.artifact_delta) if event.actions and event.actions.artifact_delta else {},
            transfer_to=event.actions.transfer_to_agent if event.actions else None,
            escalate=bool(event.actions.escalate) if event.actions else False,
            is_final=event.is_final_response() if hasattr(event, 'is_final_response') else False,
            is_partial=bool(getattr(event, 'partial', False)),
            end_of_agent=bool(event.actions.end_of_agent) if event.actions else False,
            timestamp=getattr(event, 'timestamp', 0.0) or 0.0,
        )
```

**Step 3: Run tests**

```bash
pytest tests/manual/test_adk_backend.py -v --tb=short
```

Expected: All PASS (the compile tests don't need API keys — they just construct ADK objects)

**Step 4: Commit**

```bash
git add src/adk_fluent/backends/adk.py tests/manual/test_adk_backend.py
git commit -m "feat: add ADK backend that compiles IR to native ADK objects"
```

______________________________________________________________________

### Task 7: Wire Builder Convenience Methods Through IR

**Problem:** Users need high-level methods (`to_app()`, `run()`, `stream()`) that go through the IR → backend path, while keeping `build()` backward compatible.

**Files:**

- Modify: `src/adk_fluent/_base.py` (add `to_app`, `run`, `stream` to BuilderBase)
- Modify: `src/adk_fluent/__init__.py` (export new types)
- Create: `tests/manual/test_ir_convenience.py`

**Step 1: Write tests**

Create `tests/manual/test_ir_convenience.py`:

```python
"""Tests for IR convenience methods on builders."""
import pytest
from adk_fluent import Agent


def test_to_app_returns_adk_app():
    from google.adk.apps.app import App
    pipeline = Agent("a") >> Agent("b")
    app = pipeline.to_app()
    assert isinstance(app, App)
    assert app.name == "adk_fluent_app"


def test_to_app_with_custom_name():
    from google.adk.apps.app import App
    from adk_fluent._ir import ExecutionConfig
    pipeline = Agent("a")
    app = pipeline.to_app(ExecutionConfig(app_name="my_app"))
    assert app.name == "my_app"


def test_to_app_with_resumability():
    from adk_fluent._ir import ExecutionConfig
    pipeline = Agent("a")
    app = pipeline.to_app(ExecutionConfig(resumable=True))
    assert app.resumability_config is not None


def test_build_still_returns_adk_object():
    """build() must remain unchanged for backward compat."""
    from google.adk.agents.llm_agent import LlmAgent
    agent = Agent("test", "gemini-2.5-flash")
    built = agent.build()
    assert isinstance(built, LlmAgent)


def test_to_ir_on_agent():
    from adk_fluent._ir_generated import AgentNode
    ir = Agent("test").to_ir()
    assert isinstance(ir, AgentNode)


def test_explain_ir():
    """explain() should include IR information."""
    agent = Agent("test", "gemini-2.5-flash").instruct("Help")
    info = agent.explain()
    assert "test" in str(info)
```

**Step 2: Add convenience methods to BuilderBase**

In `src/adk_fluent/_base.py`, add to `BuilderBase`:

```python
def to_app(self, config=None):
    """Compile this builder through IR to a native ADK App.

    Args:
        config: ExecutionConfig with app_name, resumability, etc.
    Returns:
        A native google.adk App object.
    """
    from adk_fluent.backends.adk import ADKBackend
    backend = ADKBackend()
    ir = self.to_ir()
    return backend.compile(ir, config=config)
```

**Step 3: Update `__init__.py` exports**

Add to `src/adk_fluent/__init__.py`:

```python
from ._ir import ExecutionConfig, CompactionConfig, AgentEvent
from .backends import Backend, final_text
from .backends.adk import ADKBackend
```

**Step 4: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_base.py src/adk_fluent/__init__.py tests/manual/test_ir_convenience.py
git commit -m "feat: wire to_app() convenience method through IR + backend"
```

______________________________________________________________________

## Post-Implementation Verification

After all 7 tasks are complete:

1. **Full test suite:**

   ```bash
   pytest tests/ -v --tb=short
   ```

   Expected: All 909+ tests PASS (plus ~60 new IR tests)

1. **Codegen pipeline (extended):**

   ```bash
   python scripts/scanner.py -o manifest.json
   python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
   python scripts/generator.py seeds/seed.toml manifest.json --output-dir /tmp/regen-check --test-dir /tmp/regen-tests
   python scripts/ir_generator.py manifest.json --output /tmp/regen-check/_ir_generated.py
   diff -r src/adk_fluent /tmp/regen-check
   ```

   Expected: No meaningful diff

1. **Round-trip verification:**

   ```python
   python -c "
   from adk_fluent import Agent
   from adk_fluent.backends.adk import ADKBackend

   pipeline = Agent('a') >> Agent('b') >> Agent('c')
   ir = pipeline.to_ir()
   print('IR:', type(ir).__name__, '- children:', len(ir.children))

   app = pipeline.to_app()
   print('App:', app.name, '- root:', type(app.root_agent).__name__)
   "
   ```

   Expected: No errors

1. **Imports:**

   ```bash
   python -c "from adk_fluent import Agent, S, tap, ExecutionConfig, ADKBackend, AgentEvent, final_text"
   ```

   Expected: No import errors

______________________________________________________________________

## Summary

| Task | What                        | Impact                                                                |
| ---- | --------------------------- | --------------------------------------------------------------------- |
| 1    | Hand-written IR nodes       | TransformNode, TapNode, GateNode, etc. + ExecutionConfig + AgentEvent |
| 2    | IR generator script         | Auto-generate AgentNode, SequenceNode, etc. from ADK manifest         |
| 3    | Primitive builder `to_ir()` | 8 primitives + Route produce IR trees                                 |
| 4    | Generated builder `to_ir()` | Agent, Pipeline, FanOut, Loop produce IR trees with data-flow         |
| 5    | Backend protocol            | Formal `Backend` protocol + `final_text()` utility                    |
| 6    | ADK backend                 | Compile IR → ADK objects + run/stream execution                       |
| 7    | Builder convenience         | `to_app()` wired through IR, backward-compat `build()` preserved      |
