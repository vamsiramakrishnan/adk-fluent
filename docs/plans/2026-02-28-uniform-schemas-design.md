# Uniform Declarative Schemas

**Date**: 2026-02-28
**Status**: Approved
**Approach**: Bottom-up refactor (Approach A)

## Problem

`StateSchema` provides a metaclass-based declarative pattern for typed state
declarations with `Annotated` hints, scope annotations, and contract checking.
But tools, callbacks, and predicates remain opaque callables — the contract
checker can't see what state keys they read/write, `.explain()` can't show
their dependencies, and developers get no IDE autocomplete for their
declarations.

## Goals

1. **Contract checking** — checker validates tool/callback/predicate state
   dependencies (missing keys, type mismatches) at build time
1. **Developer ergonomics** — IDE autocomplete, typed declarations, Pydantic-
   style field introspection
1. **Explainability** — `.explain()` shows read/write dependencies for every
   component in the pipeline

## Design

### Shared Base (`_schema_base.py`)

A `DeclarativeMetaclass` that generalizes `StateSchemaMetaclass`:

- Introspects `get_type_hints(cls, include_extras=True)`
- Extracts `Annotated` metadata into `_DeclarativeField` objects
- Stores `_fields: dict[str, Field]` and `_field_list: tuple[Field, ...]`
- Provides `__dir__` override for REPL autocomplete

Each schema metaclass subclasses `DeclarativeMetaclass` and registers its own
annotation types.

#### Shared Annotations

```python
@dataclass(frozen=True)
class Reads:
    scope: str = "session"

@dataclass(frozen=True)
class Writes:
    scope: str = "session"

@dataclass(frozen=True)
class Param:
    required: bool = True

@dataclass(frozen=True)
class Confirms:
    message: str = ""

@dataclass(frozen=True)
class Timeout:
    seconds: float = 30.0
```

`Scoped` and `CapturedBy` stay in `_state_schema.py` (state-specific).

### ToolSchema (`_tool_schema.py`)

```python
class SearchTools(ToolSchema):
    query: Annotated[str, Reads()]
    user_tier: Annotated[str, Reads(scope="user")]
    results: Annotated[list[dict], Writes()]
    max_results: Annotated[int, Param()] = 10
```

Query methods: `reads_keys()`, `writes_keys()`, `param_names()`,
`requires_confirmation()`, `timeout_seconds()`.

Builder: `Agent("search").tools(SearchTools)`.

### CallbackSchema (`_callback_schema.py`)

```python
class AuditCallbacks(CallbackSchema):
    user_tier: Annotated[str, Reads(scope="user")]
    call_count: Annotated[int, Writes(scope="temp")]
```

Query methods: `reads_keys()`, `writes_keys()`.

Builder: `Agent("processor").callbacks(AuditCallbacks)`.

The schema declares what callbacks collectively read/write. Actual callback
functions are still registered via `.before_agent()` etc.

### PredicateSchema (`_predicate_schema.py`)

```python
class QualityGate(PredicateSchema):
    score: Annotated[float, Reads()]
    threshold: Annotated[float, Reads()]

    @staticmethod
    def evaluate(score: float, threshold: float) -> bool:
        return score >= threshold
```

The metaclass wires `evaluate()` to read declared keys from state, pass them
as keyword args, and return the bool. The callable stored in IR is no longer
an opaque lambda.

Builder: `Route("intent").when(QualityGate, agent)` and
`S.guard(QualityGate, message="...")`.

### StateSchema Refactor

`StateSchemaMetaclass` is refactored to extend `DeclarativeMetaclass`. All
existing behavior preserved — `_fields`, `_field_list`, `model_fields()`,
`keys()`, `required_keys()`, `scoped_keys()`, etc. No breaking changes.

### Contract Checker Extensions

Three new passes in `testing/contracts.py`:

| Pass                   | Validates                                                                             |
| ---------------------- | ------------------------------------------------------------------------------------- |
| Tool dependencies      | `ToolSchema.reads_keys()` produced upstream; registers `writes_keys()` downstream     |
| Callback dependencies  | `CallbackSchema.reads_keys()` produced upstream; registers `writes_keys()` downstream |
| Predicate dependencies | `PredicateSchema.reads_keys()` produced upstream                                      |

### IR Node Extensions

`AgentNode` gains optional `tool_schema` and `callback_schema` attributes.
`RouteNode` and `GateNode` gain predicate metadata when predicates are
`PredicateSchema` instances.

### Backward Compatibility

- `.tool(fn)` still accepts raw callables
- `.before_agent(fn)` still accepts raw async functions
- `Route.when(lambda ...)` still accepts raw lambdas
- Schemas are opt-in — existing code continues to work unchanged

## File Layout

```
src/adk_fluent/
  _schema_base.py          # NEW
  _state_schema.py         # REFACTORED (uses DeclarativeMetaclass)
  _tool_schema.py          # NEW
  _callback_schema.py      # NEW
  _predicate_schema.py     # NEW
  testing/contracts.py     # EXTENDED (3 new passes)
```

All new types exported from `__init__.py`.
