# Uniform Declarative Schemas Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract a shared `DeclarativeMetaclass` from `StateSchemaMetaclass`, then build `ToolSchema`, `CallbackSchema`, and `PredicateSchema` on top — giving every component introspectable state dependencies for contract checking, IDE autocomplete, and `.explain()` output.

**Architecture:** Bottom-up refactor. First extract the shared metaclass and refactor `StateSchema` to use it (zero behavior change). Then build new schema types one at a time, each wired into the builder API, IR nodes, and contract checker. Each task is independently testable and shippable.

**Tech Stack:** Python 3.12+, `typing.Annotated`, metaclasses, frozen dataclasses, pytest.

---

### Task 1: Shared Base — `_schema_base.py`

**Files:**
- Create: `src/adk_fluent/_schema_base.py`
- Test: `tests/manual/test_schema_base.py`

**Step 1: Write the failing test**

```python
# tests/manual/test_schema_base.py
"""Tests for the shared DeclarativeMetaclass and annotation types."""

from __future__ import annotations

from typing import Annotated

import pytest

from adk_fluent._schema_base import (
    DeclarativeField,
    DeclarativeMetaclass,
    DeclarativeSchema,
    Reads,
    Writes,
    Param,
    Confirms,
    Timeout,
)


# ── Annotation tests ──────────────────────────────────────────────


class TestAnnotations:
    def test_reads_defaults(self):
        r = Reads()
        assert r.scope == "session"

    def test_reads_custom_scope(self):
        r = Reads(scope="user")
        assert r.scope == "user"

    def test_writes_defaults(self):
        w = Writes()
        assert w.scope == "session"

    def test_param_defaults(self):
        p = Param()
        assert p.required is True

    def test_confirms_defaults(self):
        c = Confirms()
        assert c.message == ""

    def test_timeout_defaults(self):
        t = Timeout()
        assert t.seconds == 30.0

    def test_annotations_are_frozen(self):
        r = Reads()
        with pytest.raises(AttributeError):
            r.scope = "app"  # type: ignore[misc]


# ── DeclarativeSchema tests ───────────────────────────────────────


class TestDeclarativeSchema:
    def test_empty_schema(self):
        class Empty(DeclarativeSchema):
            pass

        assert Empty._fields == {}
        assert Empty._field_list == ()

    def test_plain_fields(self):
        class Plain(DeclarativeSchema):
            name: str
            age: int

        assert len(Plain._fields) == 2
        assert "name" in Plain._fields
        assert Plain._fields["name"].type is str

    def test_annotated_reads(self):
        class S(DeclarativeSchema):
            query: Annotated[str, Reads()]

        f = S._fields["query"]
        assert f.type is str
        assert f.get_annotation(Reads) == Reads()
        assert f.get_annotation(Writes) is None

    def test_annotated_writes_with_scope(self):
        class S(DeclarativeSchema):
            count: Annotated[int, Writes(scope="temp")]

        f = S._fields["count"]
        w = f.get_annotation(Writes)
        assert w is not None
        assert w.scope == "temp"

    def test_multiple_annotations(self):
        class S(DeclarativeSchema):
            x: Annotated[str, Reads(), Timeout(10)]

        f = S._fields["x"]
        assert f.get_annotation(Reads) is not None
        assert f.get_annotation(Timeout) == Timeout(10)

    def test_default_values(self):
        class S(DeclarativeSchema):
            required: str
            optional: str = "fallback"

        assert S._fields["required"].required is True
        assert S._fields["optional"].required is False
        assert S._fields["optional"].default == "fallback"

    def test_private_fields_skipped(self):
        class S(DeclarativeSchema):
            _internal: str = "hidden"
            public: str

        assert "_internal" not in S._fields
        assert "public" in S._fields

    def test_dir_includes_field_names(self):
        class S(DeclarativeSchema):
            alpha: str
            beta: int

        d = dir(S)
        assert "alpha" in d
        assert "beta" in d

    def test_inheritance(self):
        class Base(DeclarativeSchema):
            a: str

        class Child(Base):
            b: int

        assert "a" in Child._fields
        assert "b" in Child._fields
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_schema_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'adk_fluent._schema_base'`

**Step 3: Write minimal implementation**

```python
# src/adk_fluent/_schema_base.py
"""Shared declarative metaclass and annotation types for adk-fluent schemas.

DeclarativeMetaclass introspects Annotated type hints at class definition
time, extracting annotation instances into structured field metadata. This
is the shared base for StateSchema, ToolSchema, CallbackSchema, and
PredicateSchema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, get_args, get_origin, get_type_hints

__all__ = [
    "DeclarativeField",
    "DeclarativeMetaclass",
    "DeclarativeSchema",
    "Reads",
    "Writes",
    "Param",
    "Confirms",
    "Timeout",
]


# ======================================================================
# Shared annotations
# ======================================================================

_VALID_SCOPES = frozenset({"session", "app", "user", "temp"})


@dataclass(frozen=True)
class Reads:
    """Field is read from state before execution."""

    scope: str = "session"

    def __post_init__(self) -> None:
        if self.scope not in _VALID_SCOPES:
            raise ValueError(f"Invalid scope '{self.scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")


@dataclass(frozen=True)
class Writes:
    """Field is written to state after execution."""

    scope: str = "session"

    def __post_init__(self) -> None:
        if self.scope not in _VALID_SCOPES:
            raise ValueError(f"Invalid scope '{self.scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")


@dataclass(frozen=True)
class Param:
    """Field is a tool/function parameter (not from state)."""

    required: bool = True


@dataclass(frozen=True)
class Confirms:
    """Tool requires user confirmation before execution."""

    message: str = ""


@dataclass(frozen=True)
class Timeout:
    """Execution timeout constraint."""

    seconds: float = 30.0


# ======================================================================
# Field descriptor
# ======================================================================

_MISSING = object()


class DeclarativeField:
    """Metadata about a single field in a DeclarativeSchema."""

    __slots__ = ("name", "type", "default", "_annotations")

    MISSING = _MISSING

    def __init__(
        self,
        name: str,
        type_: Any,
        default: Any = _MISSING,
        annotations: dict[type, Any] | None = None,
    ) -> None:
        self.name = name
        self.type = type_
        self.default = default
        self._annotations: dict[type, Any] = annotations or {}

    @property
    def required(self) -> bool:
        """True if this field has no default value."""
        return self.default is _MISSING

    def get_annotation(self, cls: type) -> Any | None:
        """Return the annotation instance for the given type, or None."""
        return self._annotations.get(cls)

    def has_annotation(self, cls: type) -> bool:
        """True if this field has an annotation of the given type."""
        return cls in self._annotations

    def __repr__(self) -> str:
        parts = [f"name={self.name!r}", f"type={self.type}"]
        if self._annotations:
            parts.append(f"annotations={list(self._annotations.values())}")
        return f"DeclarativeField({', '.join(parts)})"


# ======================================================================
# Metaclass
# ======================================================================


class DeclarativeMetaclass(type):
    """Metaclass that introspects Annotated type hints into field metadata.

    Subclass this metaclass and set ``_schema_base_name`` to the name of your
    schema base class (e.g. "ToolSchema") so the metaclass skips introspection
    for the base class itself.
    """

    _schema_base_name: str = "DeclarativeSchema"

    def __dir__(cls) -> list[str]:
        """Include field names in dir() for IDE/REPL autocomplete."""
        base = list(super().__dir__())
        field_list = getattr(cls, "_field_list", ())
        base.extend(f.name for f in field_list)
        return base

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        # Skip introspection for the base class itself
        base_names = {mcs._schema_base_name, "DeclarativeSchema"}
        if name in base_names:
            cls._fields = {}  # type: ignore[attr-defined]
            cls._field_list = ()  # type: ignore[attr-defined]
            return cls

        # Collect fields from type hints
        fields: dict[str, DeclarativeField] = {}
        try:
            hints = get_type_hints(cls, include_extras=True)
        except Exception:
            hints = getattr(cls, "__annotations__", {})

        for field_name, hint in hints.items():
            if field_name.startswith("_"):
                continue

            field_type = hint
            annotations: dict[type, Any] = {}

            # Extract metadata from Annotated
            if get_origin(hint) is Annotated:
                args = get_args(hint)
                if args:
                    field_type = args[0]
                    for meta in args[1:]:
                        annotations[type(meta)] = meta

            # Check for default value
            default = namespace.get(field_name, _MISSING)

            fields[field_name] = DeclarativeField(
                name=field_name,
                type_=field_type,
                default=default,
                annotations=annotations,
            )

        cls._fields = fields  # type: ignore[attr-defined]
        cls._field_list = tuple(fields.values())  # type: ignore[attr-defined]
        return cls


class DeclarativeSchema(metaclass=DeclarativeMetaclass):
    """Base class for all declarative schemas.

    Subclass to create typed declarations with Annotated hints::

        class MySchema(DeclarativeSchema):
            field: Annotated[str, Reads()]
            optional: str = "default"
    """

    _fields: ClassVar[dict[str, DeclarativeField]]
    _field_list: ClassVar[tuple[DeclarativeField, ...]]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/manual/test_schema_base.py -v`
Expected: All PASS

**Step 5: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_schema_base.py tests/manual/test_schema_base.py && ruff format src/adk_fluent/_schema_base.py tests/manual/test_schema_base.py
git add src/adk_fluent/_schema_base.py tests/manual/test_schema_base.py
git commit -m "feat: add DeclarativeMetaclass and shared annotation types"
```

---

### Task 2: Refactor StateSchema to use DeclarativeMetaclass

**Files:**
- Modify: `src/adk_fluent/_state_schema.py` (lines 92-196)
- Modify: `tests/manual/test_state_schema.py` (existing tests — must all still pass)

**Step 1: Run existing StateSchema tests to establish baseline**

Run: `source .venv/bin/activate && pytest tests/manual/test_state_schema.py -v`
Expected: All PASS (baseline)

**Step 2: Refactor StateSchemaMetaclass to extend DeclarativeMetaclass**

In `src/adk_fluent/_state_schema.py`:

1. Import `DeclarativeMetaclass`, `DeclarativeField` from `_schema_base`
2. Make `StateSchemaMetaclass` extend `DeclarativeMetaclass`
3. Override `__new__` to call `super().__new__()` first (gets `_fields`, `_field_list` with `DeclarativeField` objects), then build the state-specific `_StateSchemaField` objects from them
4. Keep `_StateSchemaField` and all `StateSchema` class methods unchanged — they still use `_StateSchemaField` internally
5. Set `_schema_base_name = "StateSchema"` on the metaclass

The key constraint: `StateSchema._fields` must remain `dict[str, _StateSchemaField]` (not `DeclarativeField`) because existing code (contract checker, `.model_fields()`) depends on `.scope`, `.captured_by`, `.full_key` attributes.

Strategy: `StateSchemaMetaclass.__new__` calls super to get generic `DeclarativeField` objects, then converts them to `_StateSchemaField` objects using the `Scoped`/`CapturedBy` annotations.

```python
class StateSchemaMetaclass(DeclarativeMetaclass):
    _schema_base_name = "StateSchema"

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        if name == "StateSchema":
            return cls

        # Convert DeclarativeFields to StateSchemaFields
        state_fields: dict[str, _StateSchemaField] = {}
        for f in cls._field_list:
            scoped = f.get_annotation(Scoped)
            captured = f.get_annotation(CapturedBy)
            scope = scoped.scope if scoped else "session"
            captured_by = captured.source if captured else None

            state_fields[f.name] = _StateSchemaField(
                name=f.name,
                type_=f.type,
                scope=scope,
                captured_by=captured_by,
                default=f.default,
            )

        cls._fields = state_fields  # type: ignore[attr-defined]
        cls._field_list = tuple(state_fields.values())  # type: ignore[attr-defined]
        return cls
```

**Step 3: Run existing tests to verify zero behavior change**

Run: `source .venv/bin/activate && pytest tests/manual/test_state_schema.py -v`
Expected: All PASS (no regressions)

**Step 4: Run the full test suite**

Run: `source .venv/bin/activate && pytest tests/ -x -q`
Expected: All PASS

**Step 5: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_state_schema.py && ruff format src/adk_fluent/_state_schema.py
git add src/adk_fluent/_state_schema.py
git commit -m "refactor: StateSchemaMetaclass extends DeclarativeMetaclass"
```

---

### Task 3: ToolSchema

**Files:**
- Create: `src/adk_fluent/_tool_schema.py`
- Modify: `src/adk_fluent/_helpers.py` (lines 80-131, `_agent_to_ir`)
- Modify: `src/adk_fluent/_ir_generated.py` (line 63-69, add `tool_schema` field to `AgentNode`)
- Modify: `src/adk_fluent/agent.py` (add `.tool_schema()` method near line 341)
- Modify: `src/adk_fluent/__init__.py` (add exports)
- Test: `tests/manual/test_tool_schema.py`

**Step 1: Write the failing test**

```python
# tests/manual/test_tool_schema.py
"""Tests for ToolSchema — typed tool declarations."""

from __future__ import annotations

from typing import Annotated

import pytest

from adk_fluent._schema_base import Confirms, Param, Reads, Timeout, Writes
from adk_fluent._tool_schema import ToolSchema


class SearchTools(ToolSchema):
    query: Annotated[str, Reads()]
    user_tier: Annotated[str, Reads(scope="user")]
    results: Annotated[list, Writes()]
    search_count: Annotated[int, Writes(scope="temp")]
    max_results: Annotated[int, Param()] = 10


class ConfirmableTool(ToolSchema):
    action: Annotated[str, Reads()]
    confirm: Annotated[bool, Confirms("Are you sure?")] = False
    limit: Annotated[float, Timeout(60)] = 60.0


class EmptyToolSchema(ToolSchema):
    pass


class TestToolSchemaFields:
    def test_reads_keys(self):
        assert SearchTools.reads_keys() == frozenset({"query", "user:user_tier"})

    def test_writes_keys(self):
        assert SearchTools.writes_keys() == frozenset({"results", "temp:search_count"})

    def test_param_names(self):
        assert SearchTools.param_names() == frozenset({"max_results"})

    def test_requires_confirmation(self):
        assert ConfirmableTool.requires_confirmation() is True
        assert SearchTools.requires_confirmation() is False

    def test_timeout_seconds(self):
        assert ConfirmableTool.timeout_seconds() == 60.0
        assert SearchTools.timeout_seconds() is None

    def test_empty_schema(self):
        assert EmptyToolSchema.reads_keys() == frozenset()
        assert EmptyToolSchema.writes_keys() == frozenset()
        assert EmptyToolSchema.param_names() == frozenset()

    def test_field_introspection(self):
        assert len(SearchTools._fields) == 5
        assert "query" in SearchTools._fields

    def test_dir_includes_fields(self):
        d = dir(SearchTools)
        assert "query" in d
        assert "results" in d


class TestToolSchemaBuilderIntegration:
    def test_tool_schema_on_agent(self):
        from adk_fluent import Agent

        a = Agent("search").tool_schema(SearchTools).instruct("Search")
        ir = a.to_ir()
        assert ir.tool_schema is SearchTools

    def test_tool_schema_adds_to_reads_keys(self):
        from adk_fluent import Agent

        a = Agent("search").tool_schema(SearchTools).instruct("Search")
        ir = a.to_ir()
        assert "query" in ir.reads_keys
        assert "user:user_tier" in ir.reads_keys

    def test_tool_schema_adds_to_writes_keys(self):
        from adk_fluent import Agent

        a = Agent("search").tool_schema(SearchTools).instruct("Search")
        ir = a.to_ir()
        assert "results" in ir.writes_keys
        assert "temp:search_count" in ir.writes_keys
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_tool_schema.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement ToolSchema**

Create `src/adk_fluent/_tool_schema.py`:

```python
"""Typed tool declarations for adk-fluent agents.

ToolSchema provides typed declarations of what state keys a tool reads
and writes, along with parameter, confirmation, and timeout metadata.

Usage::

    from adk_fluent import ToolSchema, Reads, Writes, Param

    class SearchTools(ToolSchema):
        query: Annotated[str, Reads()]
        user_tier: Annotated[str, Reads(scope="user")]
        results: Annotated[list, Writes()]
        max_results: Annotated[int, Param()] = 10

    Agent("search").tool_schema(SearchTools).instruct("Search")
"""

from __future__ import annotations

from typing import Any, ClassVar

from adk_fluent._schema_base import (
    Confirms,
    DeclarativeField,
    DeclarativeMetaclass,
    Param,
    Reads,
    Timeout,
    Writes,
)

__all__ = ["ToolSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class ToolSchemaMetaclass(DeclarativeMetaclass):
    """Metaclass for ToolSchema — adds reads/writes/param query methods."""

    _schema_base_name = "ToolSchema"


class ToolSchema(metaclass=ToolSchemaMetaclass):
    """Base class for typed tool declarations."""

    _fields: ClassVar[dict[str, DeclarativeField]]
    _field_list: ClassVar[tuple[DeclarativeField, ...]]

    @classmethod
    def reads_keys(cls) -> frozenset[str]:
        """State keys this tool reads (with scope prefixes)."""
        keys: list[str] = []
        for f in cls._field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                keys.append(_scoped_key(f.name, r.scope))
        return frozenset(keys)

    @classmethod
    def writes_keys(cls) -> frozenset[str]:
        """State keys this tool writes (with scope prefixes)."""
        keys: list[str] = []
        for f in cls._field_list:
            w = f.get_annotation(Writes)
            if w is not None:
                keys.append(_scoped_key(f.name, w.scope))
        return frozenset(keys)

    @classmethod
    def param_names(cls) -> frozenset[str]:
        """Tool parameter names (not from state)."""
        return frozenset(f.name for f in cls._field_list if f.has_annotation(Param))

    @classmethod
    def requires_confirmation(cls) -> bool:
        """True if any field has a Confirms annotation."""
        return any(f.has_annotation(Confirms) for f in cls._field_list)

    @classmethod
    def timeout_seconds(cls) -> float | None:
        """Return the timeout in seconds, or None if not set."""
        for f in cls._field_list:
            t = f.get_annotation(Timeout)
            if t is not None:
                return t.seconds
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
```

**Step 4: Wire into builder and IR**

Add `tool_schema` field to `AgentNode` in `src/adk_fluent/_ir_generated.py` (after line 69):

```python
    tool_schema: type | None = None  # ToolSchema class, preserved for diagnostics
```

Add `.tool_schema()` method to `src/adk_fluent/agent.py` (after `.tool()` method, ~line 399):

```python
    def tool_schema(self, schema: type) -> Self:
        """Attach a ToolSchema declaring tool state dependencies."""
        self = self._maybe_fork_for_mutation()
        self._config["_tool_schema"] = schema
        return self
```

Update `_agent_to_ir` in `src/adk_fluent/_helpers.py` (after line 94):

```python
    tool_schema = builder._config.get("_tool_schema")
```

And merge tool_schema keys into writes_keys/reads_keys (modify lines 103-104):

```python
    writes_keys = frozenset(produces_schema.model_fields.keys()) if produces_schema else frozenset()
    reads_keys = frozenset(consumes_schema.model_fields.keys()) if consumes_schema else frozenset()
    if tool_schema is not None and hasattr(tool_schema, "reads_keys"):
        reads_keys = reads_keys | tool_schema.reads_keys()
    if tool_schema is not None and hasattr(tool_schema, "writes_keys"):
        writes_keys = writes_keys | tool_schema.writes_keys()
```

And pass `tool_schema=tool_schema` in the `AgentNode(...)` constructor (after line 130).

Add exports to `src/adk_fluent/__init__.py`:

In `__all__` list (after `"Scoped",` line 416):
```python
    "ToolSchema",
```

In imports (after line 625):
```python
from ._tool_schema import ToolSchema
```

**Step 5: Run tests**

Run: `source .venv/bin/activate && pytest tests/manual/test_tool_schema.py tests/manual/test_state_schema.py -v`
Expected: All PASS

**Step 6: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_tool_schema.py src/adk_fluent/_helpers.py src/adk_fluent/_ir_generated.py src/adk_fluent/agent.py tests/manual/test_tool_schema.py && ruff format src/adk_fluent/_tool_schema.py src/adk_fluent/_helpers.py src/adk_fluent/_ir_generated.py src/adk_fluent/agent.py tests/manual/test_tool_schema.py
git add src/adk_fluent/_tool_schema.py src/adk_fluent/_helpers.py src/adk_fluent/_ir_generated.py src/adk_fluent/agent.py src/adk_fluent/__init__.py tests/manual/test_tool_schema.py
git commit -m "feat: add ToolSchema with reads/writes/param introspection"
```

---

### Task 4: CallbackSchema

**Files:**
- Create: `src/adk_fluent/_callback_schema.py`
- Modify: `src/adk_fluent/_helpers.py` (`_agent_to_ir`)
- Modify: `src/adk_fluent/_ir_generated.py` (add `callback_schema` field)
- Modify: `src/adk_fluent/agent.py` (add `.callback_schema()` method)
- Modify: `src/adk_fluent/__init__.py` (add exports)
- Test: `tests/manual/test_callback_schema.py`

**Step 1: Write the failing test**

```python
# tests/manual/test_callback_schema.py
"""Tests for CallbackSchema — typed callback declarations."""

from __future__ import annotations

from typing import Annotated

from adk_fluent._schema_base import Reads, Writes
from adk_fluent._callback_schema import CallbackSchema


class AuditCallbacks(CallbackSchema):
    user_tier: Annotated[str, Reads(scope="user")]
    intent: Annotated[str, Reads()]
    call_count: Annotated[int, Writes(scope="temp")]
    audit_log: Annotated[list, Writes()]


class EmptyCallbacks(CallbackSchema):
    pass


class TestCallbackSchemaFields:
    def test_reads_keys(self):
        assert AuditCallbacks.reads_keys() == frozenset({"user:user_tier", "intent"})

    def test_writes_keys(self):
        assert AuditCallbacks.writes_keys() == frozenset({"temp:call_count", "audit_log"})

    def test_empty_schema(self):
        assert EmptyCallbacks.reads_keys() == frozenset()
        assert EmptyCallbacks.writes_keys() == frozenset()

    def test_dir_includes_fields(self):
        d = dir(AuditCallbacks)
        assert "user_tier" in d
        assert "call_count" in d


class TestCallbackSchemaBuilderIntegration:
    def test_callback_schema_on_agent(self):
        from adk_fluent import Agent

        a = Agent("proc").callback_schema(AuditCallbacks).instruct("Process")
        ir = a.to_ir()
        assert ir.callback_schema is AuditCallbacks

    def test_callback_schema_adds_to_reads_keys(self):
        from adk_fluent import Agent

        a = Agent("proc").callback_schema(AuditCallbacks).instruct("Process")
        ir = a.to_ir()
        assert "intent" in ir.reads_keys
        assert "user:user_tier" in ir.reads_keys

    def test_callback_schema_adds_to_writes_keys(self):
        from adk_fluent import Agent

        a = Agent("proc").callback_schema(AuditCallbacks).instruct("Process")
        ir = a.to_ir()
        assert "audit_log" in ir.writes_keys
        assert "temp:call_count" in ir.writes_keys
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_callback_schema.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement CallbackSchema**

Create `src/adk_fluent/_callback_schema.py`:

```python
"""Typed callback declarations for adk-fluent agents.

CallbackSchema declares what state keys the agent's callbacks collectively
read and write, making them visible to the contract checker and .explain().

Usage::

    from adk_fluent import CallbackSchema, Reads, Writes

    class AuditCallbacks(CallbackSchema):
        user_tier: Annotated[str, Reads(scope="user")]
        call_count: Annotated[int, Writes(scope="temp")]

    Agent("proc").callback_schema(AuditCallbacks).before_agent(audit_fn)
"""

from __future__ import annotations

from typing import Any, ClassVar

from adk_fluent._schema_base import (
    DeclarativeField,
    DeclarativeMetaclass,
    Reads,
    Writes,
)

__all__ = ["CallbackSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class CallbackSchemaMetaclass(DeclarativeMetaclass):
    _schema_base_name = "CallbackSchema"


class CallbackSchema(metaclass=CallbackSchemaMetaclass):
    """Base class for typed callback declarations."""

    _fields: ClassVar[dict[str, DeclarativeField]]
    _field_list: ClassVar[tuple[DeclarativeField, ...]]

    @classmethod
    def reads_keys(cls) -> frozenset[str]:
        keys: list[str] = []
        for f in cls._field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                keys.append(_scoped_key(f.name, r.scope))
        return frozenset(keys)

    @classmethod
    def writes_keys(cls) -> frozenset[str]:
        keys: list[str] = []
        for f in cls._field_list:
            w = f.get_annotation(Writes)
            if w is not None:
                keys.append(_scoped_key(f.name, w.scope))
        return frozenset(keys)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
```

**Step 4: Wire into builder and IR**

Same pattern as Task 3:

Add to `AgentNode` in `_ir_generated.py` (after `tool_schema`):
```python
    callback_schema: type | None = None
```

Add `.callback_schema()` to `agent.py` (after `.tool_schema()`):
```python
    def callback_schema(self, schema: type) -> Self:
        """Attach a CallbackSchema declaring callback state dependencies."""
        self = self._maybe_fork_for_mutation()
        self._config["_callback_schema"] = schema
        return self
```

Update `_agent_to_ir` in `_helpers.py`:
```python
    callback_schema = builder._config.get("_callback_schema")
    if callback_schema is not None and hasattr(callback_schema, "reads_keys"):
        reads_keys = reads_keys | callback_schema.reads_keys()
    if callback_schema is not None and hasattr(callback_schema, "writes_keys"):
        writes_keys = writes_keys | callback_schema.writes_keys()
```

Pass `callback_schema=callback_schema` in the `AgentNode(...)` call.

Add exports to `__init__.py` (same pattern as ToolSchema).

**Step 5: Run tests**

Run: `source .venv/bin/activate && pytest tests/manual/test_callback_schema.py tests/manual/test_tool_schema.py tests/manual/test_state_schema.py -v`
Expected: All PASS

**Step 6: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_callback_schema.py tests/manual/test_callback_schema.py && ruff format src/adk_fluent/_callback_schema.py tests/manual/test_callback_schema.py
git add src/adk_fluent/_callback_schema.py src/adk_fluent/_helpers.py src/adk_fluent/_ir_generated.py src/adk_fluent/agent.py src/adk_fluent/__init__.py tests/manual/test_callback_schema.py
git commit -m "feat: add CallbackSchema with reads/writes introspection"
```

---

### Task 5: PredicateSchema

**Files:**
- Create: `src/adk_fluent/_predicate_schema.py`
- Modify: `src/adk_fluent/_routing.py` (lines 73-76, `.when()` method)
- Modify: `src/adk_fluent/_ir.py` (lines 85-91, `GateNode`; lines 114-121, `RouteNode`)
- Modify: `src/adk_fluent/__init__.py` (add exports)
- Test: `tests/manual/test_predicate_schema.py`

**Step 1: Write the failing test**

```python
# tests/manual/test_predicate_schema.py
"""Tests for PredicateSchema — typed predicate declarations."""

from __future__ import annotations

from typing import Annotated

import pytest

from adk_fluent._schema_base import Reads
from adk_fluent._predicate_schema import PredicateSchema


class QualityGate(PredicateSchema):
    score: Annotated[float, Reads()]
    threshold: Annotated[float, Reads()]

    @staticmethod
    def evaluate(score: float, threshold: float) -> bool:
        return score >= threshold


class SimpleCheck(PredicateSchema):
    active: Annotated[bool, Reads()]

    @staticmethod
    def evaluate(active: bool) -> bool:
        return active


class NoEvaluate(PredicateSchema):
    x: Annotated[str, Reads()]


class TestPredicateSchemaFields:
    def test_reads_keys(self):
        assert QualityGate.reads_keys() == frozenset({"score", "threshold"})

    def test_reads_keys_simple(self):
        assert SimpleCheck.reads_keys() == frozenset({"active"})


class TestPredicateSchemaCallable:
    def test_call_passes_state_keys(self):
        state = {"score": 0.9, "threshold": 0.7}
        assert QualityGate(state) is True

    def test_call_fails_state_keys(self):
        state = {"score": 0.3, "threshold": 0.7}
        assert QualityGate(state) is False

    def test_simple_check(self):
        assert SimpleCheck({"active": True}) is True
        assert SimpleCheck({"active": False}) is False

    def test_scoped_key_reads(self):
        class ScopedPred(PredicateSchema):
            tier: Annotated[str, Reads(scope="user")]

            @staticmethod
            def evaluate(tier: str) -> bool:
                return tier == "premium"

        assert ScopedPred.reads_keys() == frozenset({"user:tier"})
        assert ScopedPred({"user:tier": "premium"}) is True

    def test_missing_evaluate_raises(self):
        with pytest.raises(TypeError, match="evaluate"):
            NoEvaluate({"x": "hello"})


class TestPredicateSchemaRouting:
    def test_route_when_accepts_predicate_schema(self):
        from adk_fluent import Agent, Route

        a = Agent("hi").instruct("Hi")
        b = Agent("lo").instruct("Lo")

        route = Route("score").when(QualityGate, a).otherwise(b)
        ir = route.to_ir()
        # The predicate stored in IR should be callable
        pred, _ = ir.rules[0]
        assert pred({"score": 0.9, "threshold": 0.5}) is True
        assert pred({"score": 0.2, "threshold": 0.5}) is False
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_predicate_schema.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement PredicateSchema**

Create `src/adk_fluent/_predicate_schema.py`:

```python
"""Typed predicate declarations for adk-fluent routing and gates.

PredicateSchema declares what state keys a predicate reads and provides
a structured evaluate() method that receives those keys as arguments.

Usage::

    from adk_fluent import PredicateSchema, Reads

    class QualityGate(PredicateSchema):
        score: Annotated[float, Reads()]
        threshold: Annotated[float, Reads()]

        @staticmethod
        def evaluate(score, threshold) -> bool:
            return score >= threshold

    Route("intent").when(QualityGate, high_agent).otherwise(low_agent)
"""

from __future__ import annotations

from typing import Any, ClassVar

from adk_fluent._schema_base import (
    DeclarativeField,
    DeclarativeMetaclass,
    Reads,
)

__all__ = ["PredicateSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class PredicateSchemaMetaclass(DeclarativeMetaclass):
    _schema_base_name = "PredicateSchema"

    def __call__(cls, state: dict[str, Any]) -> bool:
        """Make the schema class itself callable: QualityGate(state) -> bool."""
        evaluate = getattr(cls, "evaluate", None)
        if evaluate is None:
            raise TypeError(
                f"{cls.__name__} must define a static evaluate() method"
            )

        # Extract declared reads keys from state
        kwargs: dict[str, Any] = {}
        for f in cls._field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                full_key = _scoped_key(f.name, r.scope)
                kwargs[f.name] = state.get(full_key)

        return bool(evaluate(**kwargs))


class PredicateSchema(metaclass=PredicateSchemaMetaclass):
    """Base class for typed predicate declarations."""

    _fields: ClassVar[dict[str, DeclarativeField]]
    _field_list: ClassVar[tuple[DeclarativeField, ...]]

    @classmethod
    def reads_keys(cls) -> frozenset[str]:
        keys: list[str] = []
        for f in cls._field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                keys.append(_scoped_key(f.name, r.scope))
        return frozenset(keys)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
```

**Step 4: Update Route.when() to accept PredicateSchema**

In `src/adk_fluent/_routing.py`, modify `.when()` (line 73-76):

```python
    def when(self, predicate: Callable | type, agent) -> Route:
        """Branch to agent when predicate(state) is truthy.

        Accepts a callable or a PredicateSchema class.
        """
        from adk_fluent._predicate_schema import PredicateSchema as _PS

        if isinstance(predicate, type) and issubclass(predicate, _PS):
            # PredicateSchema — it's already callable via its metaclass
            self._rules.append((predicate, agent))
        else:
            self._rules.append((predicate, agent))
        return self
```

Add exports to `__init__.py` (same pattern).

**Step 5: Run tests**

Run: `source .venv/bin/activate && pytest tests/manual/test_predicate_schema.py tests/manual/test_state_schema.py -v`
Expected: All PASS

**Step 6: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_predicate_schema.py src/adk_fluent/_routing.py tests/manual/test_predicate_schema.py && ruff format src/adk_fluent/_predicate_schema.py src/adk_fluent/_routing.py tests/manual/test_predicate_schema.py
git add src/adk_fluent/_predicate_schema.py src/adk_fluent/_routing.py src/adk_fluent/__init__.py tests/manual/test_predicate_schema.py
git commit -m "feat: add PredicateSchema with callable evaluate() and Route integration"
```

---

### Task 6: Contract Checker Extensions

**Files:**
- Modify: `src/adk_fluent/testing/contracts.py` (add 3 new passes after Pass 12, ~line 578)
- Test: `tests/manual/test_contracts_schemas.py`

**Step 1: Write the failing test**

```python
# tests/manual/test_contracts_schemas.py
"""Tests for contract checker passes on ToolSchema/CallbackSchema/PredicateSchema."""

from __future__ import annotations

from typing import Annotated

from adk_fluent import Agent, S, Route
from adk_fluent._schema_base import Reads, Writes
from adk_fluent._tool_schema import ToolSchema
from adk_fluent._callback_schema import CallbackSchema
from adk_fluent._predicate_schema import PredicateSchema
from adk_fluent.testing.contracts import check_contracts


class ProducerTools(ToolSchema):
    query: Annotated[str, Reads()]
    results: Annotated[list, Writes()]


class ConsumerCallbacks(CallbackSchema):
    results: Annotated[list, Reads()]
    log_entry: Annotated[str, Writes()]


class MissingKeyTools(ToolSchema):
    nonexistent: Annotated[str, Reads()]


class GatePred(PredicateSchema):
    score: Annotated[float, Reads()]

    @staticmethod
    def evaluate(score: float) -> bool:
        return score > 0.5


class TestToolSchemaContracts:
    def test_tool_reads_satisfied(self):
        pipeline = (
            Agent("a").instruct("produce query").outputs("query")
            >> Agent("b").instruct("search").tool_schema(ProducerTools)
        )
        issues = check_contracts(pipeline.to_ir())
        tool_issues = [i for i in issues if isinstance(i, dict) and "nonexistent" in i.get("message", "")]
        assert len(tool_issues) == 0

    def test_tool_reads_missing(self):
        pipeline = (
            Agent("a").instruct("do nothing")
            >> Agent("b").instruct("search").tool_schema(MissingKeyTools)
        )
        issues = check_contracts(pipeline.to_ir())
        missing = [i for i in issues if isinstance(i, dict) and "nonexistent" in i.get("message", "")]
        assert len(missing) >= 1


class TestCallbackSchemaContracts:
    def test_callback_reads_satisfied(self):
        pipeline = (
            Agent("a").instruct("produce").tool_schema(ProducerTools)
            >> Agent("b").instruct("consume").callback_schema(ConsumerCallbacks)
        )
        issues = check_contracts(pipeline.to_ir())
        cb_issues = [i for i in issues if isinstance(i, dict) and "results" in i.get("message", "") and "not produced" in i.get("message", "")]
        assert len(cb_issues) == 0


class TestPredicateSchemaContracts:
    def test_predicate_reads_missing(self):
        a = Agent("hi").instruct("Hi")
        b = Agent("lo").instruct("Lo")
        pipeline = (
            Agent("start").instruct("start")
            >> Route().when(GatePred, a).otherwise(b)
        )
        issues = check_contracts(pipeline.to_ir())
        pred_issues = [i for i in issues if isinstance(i, dict) and "score" in i.get("message", "")]
        assert len(pred_issues) >= 1
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/manual/test_contracts_schemas.py -v`
Expected: FAIL (the checker doesn't know about tool_schema/callback_schema yet)

**Step 3: Add contract checker passes**

In `src/adk_fluent/testing/contracts.py`, after Pass 12 (line ~578), add:

```python
    # =================================================================
    # Pass 13: ToolSchema / CallbackSchema dependency validation
    # =================================================================
    for idx, child in enumerate(children):
        child_name = getattr(child, "name", "?")

        for schema_attr, label in [("tool_schema", "ToolSchema"), ("callback_schema", "CallbackSchema")]:
            schema = getattr(child, schema_attr, None)
            if schema is None or not hasattr(schema, "reads_keys"):
                continue

            schema_reads = schema.reads_keys()
            if schema_reads:
                missing = schema_reads - available_keys
                for key in sorted(missing):
                    issues.append(
                        {
                            "level": "warning",
                            "agent": _scoped(child_name),
                            "message": (
                                f"{label} reads key '{key}' but it is not "
                                f"produced by any upstream agent"
                            ),
                            "hint": (
                                f"Add .outputs('{key}') to an upstream agent "
                                f"or use S.set() / S.capture() to provide this key."
                            ),
                        }
                    )

            # Register writes from schema as available downstream
            if hasattr(schema, "writes_keys"):
                available_keys |= schema.writes_keys()

    # =================================================================
    # Pass 14: PredicateSchema dependency validation (Route/Gate)
    # =================================================================
    for child in children:
        child_name = getattr(child, "name", "?")

        # Check RouteNode predicates
        rules = getattr(child, "rules", ())
        for pred, _agent in rules:
            if hasattr(pred, "reads_keys"):
                pred_reads = pred.reads_keys()
                missing = pred_reads - available_keys
                for key in sorted(missing):
                    issues.append(
                        {
                            "level": "warning",
                            "agent": _scoped(child_name),
                            "message": (
                                f"Predicate reads key '{key}' but it is not "
                                f"produced by any upstream agent"
                            ),
                            "hint": (
                                f"Add .outputs('{key}') to an upstream agent "
                                f"or use S.set() to provide this key."
                            ),
                        }
                    )

        # Check GateNode predicate
        gate_pred = getattr(child, "predicate", None)
        if gate_pred is not None and hasattr(gate_pred, "reads_keys"):
            pred_reads = gate_pred.reads_keys()
            missing = pred_reads - available_keys
            for key in sorted(missing):
                issues.append(
                    {
                        "level": "warning",
                        "agent": _scoped(child_name),
                        "message": (
                            f"Gate predicate reads key '{key}' but it is not "
                            f"produced by any upstream agent"
                        ),
                        "hint": (
                            f"Add .outputs('{key}') to an upstream agent "
                            f"or use S.set() to provide this key."
                        ),
                    }
                )
```

**Important**: The `available_keys` set is already maintained by Pass 1-2. Passes 13-14 extend it by adding `writes_keys` from schemas.

**Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/manual/test_contracts_schemas.py tests/manual/test_contracts.py tests/manual/test_contracts_v2.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest tests/ -x -q`
Expected: All PASS

**Step 6: Lint and commit**

```bash
ruff check --fix src/adk_fluent/testing/contracts.py tests/manual/test_contracts_schemas.py && ruff format src/adk_fluent/testing/contracts.py tests/manual/test_contracts_schemas.py
git add src/adk_fluent/testing/contracts.py tests/manual/test_contracts_schemas.py
git commit -m "feat: contract checker passes for ToolSchema, CallbackSchema, PredicateSchema"
```

---

### Task 7: Cookbook Example

**Files:**
- Create: `examples/structured_schemas/structured_schemas.py`

**Step 1: Write the example**

```python
"""Uniform Declarative Schemas — ToolSchema, CallbackSchema, PredicateSchema.

Demonstrates how to declare typed state dependencies for tools, callbacks,
and predicates using the same Annotated-hint pattern as StateSchema.
"""

from __future__ import annotations

from typing import Annotated

from adk_fluent import (
    Agent,
    Route,
    S,
    StateSchema,
    Scoped,
)
from adk_fluent._schema_base import Reads, Writes, Param
from adk_fluent._tool_schema import ToolSchema
from adk_fluent._callback_schema import CallbackSchema
from adk_fluent._predicate_schema import PredicateSchema
from adk_fluent.testing.contracts import check_contracts


# ── State Schema (existing pattern) ──────────────────────────────

class TriageState(StateSchema):
    intent: str
    confidence: float
    user_tier: Annotated[str, Scoped("user")]
    ticket_id: str | None = None


# ── Tool Schema (NEW) ────────────────────────────────────────────

class SearchTools(ToolSchema):
    query: Annotated[str, Reads()]
    user_tier: Annotated[str, Reads(scope="user")]
    results: Annotated[list, Writes()]
    max_results: Annotated[int, Param()] = 10


# ── Callback Schema (NEW) ────────────────────────────────────────

class AuditCallbacks(CallbackSchema):
    intent: Annotated[str, Reads()]
    audit_log: Annotated[list, Writes()]


# ── Predicate Schema (NEW) ───────────────────────────────────────

class HighConfidence(PredicateSchema):
    confidence: Annotated[float, Reads()]

    @staticmethod
    def evaluate(confidence: float) -> bool:
        return confidence >= 0.8


# ── Pipeline ─────────────────────────────────────────────────────

classifier = (
    Agent("classifier")
    .produces(TriageState)
    .instruct("Classify the user's intent and confidence.")
)

searcher = (
    Agent("searcher")
    .tool_schema(SearchTools)
    .instruct("Search for relevant documents.")
)

processor = (
    Agent("processor")
    .callback_schema(AuditCallbacks)
    .instruct("Process and respond.")
)

pipeline = (
    classifier
    >> Route("confidence")
        .when(HighConfidence, searcher >> processor)
        .otherwise(Agent("fallback").instruct("Ask for clarification."))
)

# ── Contract check ───────────────────────────────────────────────

issues = check_contracts(pipeline.to_ir())
for issue in issues:
    if isinstance(issue, dict):
        print(f"[{issue['level']}] {issue['agent']}: {issue['message']}")
    else:
        print(issue)

if not issues:
    print("All contracts satisfied.")

# ── Introspection ────────────────────────────────────────────────

print(f"\nSearchTools reads:  {SearchTools.reads_keys()}")
print(f"SearchTools writes: {SearchTools.writes_keys()}")
print(f"SearchTools params: {SearchTools.param_names()}")
print(f"AuditCallbacks reads:  {AuditCallbacks.reads_keys()}")
print(f"AuditCallbacks writes: {AuditCallbacks.writes_keys()}")
print(f"HighConfidence reads:  {HighConfidence.reads_keys()}")
print(f"HighConfidence(score=0.9): {HighConfidence({'confidence': 0.9})}")
```

**Step 2: Run the example**

Run: `source .venv/bin/activate && python examples/structured_schemas/structured_schemas.py`
Expected: Prints introspection output without errors

**Step 3: Commit**

```bash
git add examples/structured_schemas/
git commit -m "docs: add uniform schemas cookbook example"
```

---

### Task 8: Final Integration — Full Test Suite + Cleanup

**Files:**
- All files from previous tasks
- Verify: `src/adk_fluent/__init__.py` has all exports

**Step 1: Run the full test suite**

Run: `source .venv/bin/activate && pytest tests/ -x -q`
Expected: All PASS

**Step 2: Run lint**

Run: `source .venv/bin/activate && ruff check --fix . && ruff format .`
Expected: Clean

**Step 3: Verify exports**

```python
source .venv/bin/activate && python -c "
from adk_fluent import ToolSchema, CallbackSchema, PredicateSchema, Reads, Writes, Param, Confirms, Timeout
print('All exports working')
print(f'ToolSchema: {ToolSchema}')
print(f'CallbackSchema: {CallbackSchema}')
print(f'PredicateSchema: {PredicateSchema}')
"
```

Expected: Prints without errors

**Step 4: Commit if any final cleanup needed**

```bash
git add -A && git commit -m "chore: final cleanup for uniform schemas"
```
