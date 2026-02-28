# MiddlewareSchema Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `MiddlewareSchema` — typed state declarations for middleware — completing the uniform schema family and enabling contract checking for scoped middleware.

**Architecture:** `MiddlewareSchema` follows the exact same `DeclarativeMetaclass` pattern as `CallbackSchema`. Middleware classes declare `schema = SomeMiddlewareSchema` as a class attribute (parallel to the existing `agents` attribute). The contract checker adds Pass 14 to validate scoped middleware reads at the target agent's position. `_ConditionalMiddleware` is rewritten to support `PredicateSchema` conditions via deferred hook evaluation.

**Tech Stack:** Python, `DeclarativeMetaclass` from `_schema_base.py`, `testing/contracts.py` contract checker, `middleware.py` wrappers, `_middleware.py` M module.

______________________________________________________________________

### Task 1: Create `MiddlewareSchema` class

**Files:**

- Create: `src/adk_fluent/_middleware_schema.py`
- Test: `tests/manual/test_middleware_schema.py`

**Step 1: Write the failing test**

Create the test file:

```python
"""Tests for MiddlewareSchema declarative type."""

from __future__ import annotations

from typing import Annotated

from adk_fluent._schema_base import Reads, Writes


class TestMiddlewareSchemaMetaclass:
    """MiddlewareSchema introspects Annotated hints via DeclarativeMetaclass."""

    def test_reads_keys(self):
        from adk_fluent._middleware_schema import MiddlewareSchema

        class BudgetState(MiddlewareSchema):
            token_budget: Annotated[int, Reads(scope="app")]
            user_tier: Annotated[str, Reads(scope="user")]

        assert BudgetState.reads_keys() == frozenset({"app:token_budget", "user:user_tier"})

    def test_writes_keys(self):
        from adk_fluent._middleware_schema import MiddlewareSchema

        class Tracking(MiddlewareSchema):
            tokens_used: Annotated[int, Writes(scope="temp")]
            result_key: Annotated[str, Writes()]

        assert Tracking.writes_keys() == frozenset({"temp:tokens_used", "result_key"})

    def test_mixed_reads_writes(self):
        from adk_fluent._middleware_schema import MiddlewareSchema

        class Mixed(MiddlewareSchema):
            budget: Annotated[int, Reads(scope="app")]
            spent: Annotated[int, Writes(scope="temp")]

        assert Mixed.reads_keys() == frozenset({"app:budget"})
        assert Mixed.writes_keys() == frozenset({"temp:spent"})

    def test_empty_schema(self):
        from adk_fluent._middleware_schema import MiddlewareSchema

        class Empty(MiddlewareSchema):
            pass

        assert Empty.reads_keys() == frozenset()
        assert Empty.writes_keys() == frozenset()

    def test_repr(self):
        from adk_fluent._middleware_schema import MiddlewareSchema

        class Budget(MiddlewareSchema):
            tokens: Annotated[int, Reads()]

        assert "Budget" in repr(Budget())
        assert "tokens" in repr(Budget())
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_middleware_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adk_fluent._middleware_schema'`

**Step 3: Write minimal implementation**

Create `src/adk_fluent/_middleware_schema.py`:

```python
"""Typed middleware state declarations for adk-fluent.

MiddlewareSchema declares what state keys middleware hooks read and write,
making them visible to the contract checker and .explain().

Usage::

    from adk_fluent import MiddlewareSchema, Reads, Writes

    class BudgetState(MiddlewareSchema):
        token_budget: Annotated[int, Reads(scope="app")]
        tokens_used: Annotated[int, Writes(scope="temp")]

    class BudgetEnforcer:
        agents = "writer"
        schema = BudgetState
        async def before_agent(self, ctx, agent_name): ...
"""

from __future__ import annotations

from typing import ClassVar

from adk_fluent._schema_base import (
    DeclarativeField,
    DeclarativeMetaclass,
    Reads,
    Writes,
)

__all__ = ["MiddlewareSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class MiddlewareSchemaMetaclass(DeclarativeMetaclass):
    _schema_base_name = "MiddlewareSchema"


class MiddlewareSchema(metaclass=MiddlewareSchemaMetaclass):
    """Base class for typed middleware state declarations."""

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

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_middleware_schema.py -v`
Expected: PASS — all 5 tests green

**Step 5: Commit**

```bash
git add src/adk_fluent/_middleware_schema.py tests/manual/test_middleware_schema.py
git commit -m "feat: add MiddlewareSchema declarative type"
```

______________________________________________________________________

### Task 2: Rewrite `_ConditionalMiddleware` for deferred evaluation

**Files:**

- Modify: `src/adk_fluent/middleware.py` (lines 420–453, `_ConditionalMiddleware`)
- Test: `tests/manual/test_middleware_schema.py` (append)

**Step 1: Write the failing tests**

Append to `tests/manual/test_middleware_schema.py`:

```python
import asyncio


class TestConditionalMiddlewareDeferred:
    """_ConditionalMiddleware returns guarded wrappers, not None."""

    def test_guarded_wrapper_is_callable(self):
        """__getattr__ returns a callable wrapper even when condition is false."""
        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            async def before_agent(self, ctx, name):
                return "fired"

        cond = _ConditionalMiddleware(lambda: False, Inner())
        # Old behavior: returned None. New behavior: returns async callable.
        hook = cond.before_agent
        assert callable(hook)

    def test_guarded_wrapper_skips_when_false(self):
        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            async def before_agent(self, ctx, name):
                return "fired"

        cond = _ConditionalMiddleware(lambda: False, Inner())
        result = asyncio.get_event_loop().run_until_complete(cond.before_agent(None, "x"))
        assert result is None

    def test_guarded_wrapper_fires_when_true(self):
        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            async def before_agent(self, ctx, name):
                return "fired"

        cond = _ConditionalMiddleware(lambda: True, Inner())
        result = asyncio.get_event_loop().run_until_complete(cond.before_agent(None, "x"))
        assert result == "fired"

    def test_schema_forwarded(self):
        """schema attribute is forwarded from inner middleware."""
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent.middleware import _ConditionalMiddleware

        class MySchema(MiddlewareSchema):
            pass

        class Inner:
            schema = MySchema

        cond = _ConditionalMiddleware(lambda: True, Inner())
        assert cond.schema is MySchema

    def test_predicate_schema_condition(self):
        """PredicateSchema condition is deferred to invocation time."""
        from adk_fluent._predicate_schema import PredicateSchema
        from adk_fluent.middleware import _ConditionalMiddleware

        class AlwaysTrue(PredicateSchema):
            pass

            @staticmethod
            def evaluate():
                return True

        fired = []

        class Inner:
            async def before_agent(self, ctx, name):
                fired.append(name)

        cond = _ConditionalMiddleware(AlwaysTrue, Inner())
        # Should return a callable wrapper
        assert callable(cond.before_agent)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_middleware_schema.py::TestConditionalMiddlewareDeferred -v`
Expected: FAIL — `test_guarded_wrapper_is_callable` fails because current `__getattr__` returns `None` when condition is false

**Step 3: Rewrite `_ConditionalMiddleware` in `middleware.py`**

Replace the `_ConditionalMiddleware` class (lines 420–453) with:

```python
class _ConditionalMiddleware:
    """Wraps a middleware to only fire when a condition is met.

    ``condition`` can be:
        - A callable returning bool.
        - A string shortcut: ``"stream"``, ``"dispatched"``, ``"pipeline"``
          matching ``ExecutionMode``.
        - A ``PredicateSchema`` subclass — evaluated against session state
          from ``TraceContext.invocation_context`` at invocation time.
    """

    def __init__(self, condition: str | Callable[[], bool] | type, inner: Any) -> None:
        self._condition = condition
        self._inner = inner
        # Forward agents and schema from inner for static introspection
        agents = getattr(inner, "agents", None)
        if agents is not None:
            self.agents = agents
        schema = getattr(inner, "schema", None)
        if schema is not None:
            self.schema = schema

    def _check(self) -> bool:
        cond = self._condition
        if isinstance(cond, str):
            return self._check_mode(cond)
        if isinstance(cond, type):
            return self._check_predicate(cond)
        if callable(cond):
            return bool(cond())
        return True

    @staticmethod
    def _check_mode(mode_str: str) -> bool:
        from adk_fluent._primitives import get_execution_mode

        return bool(get_execution_mode().value == mode_str)

    @staticmethod
    def _check_predicate(schema_cls: type) -> bool:
        """Evaluate a PredicateSchema against current session state."""
        trace = _trace_context.get()
        if trace is None:
            return True  # no trace context = can't evaluate, allow
        inv_ctx = trace.invocation_context
        if inv_ctx is None:
            return True
        session = getattr(inv_ctx, "session", None)
        if session is None:
            return True
        state = getattr(session, "state", {})
        evaluate = getattr(schema_cls, "evaluate", None)
        if evaluate is None:
            return True
        # Extract field values from state using schema introspection
        from adk_fluent._schema_base import Reads

        field_list = getattr(schema_cls, "_field_list", ())
        kwargs: dict[str, Any] = {}
        for f in field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                full_key = f.name if r.scope == "session" else f"{r.scope}:{f.name}"
                kwargs[f.name] = state.get(full_key)
        return bool(evaluate(**kwargs))

    def __getattr__(self, name: str) -> Any:
        val = getattr(self._inner, name, None)
        if val is None or not callable(val):
            if val is None:
                raise AttributeError(name)
            return val  # non-callable attributes forwarded directly
        # Return a guarded wrapper that defers condition check to invocation time
        async def _guarded(*args: Any, **kwargs: Any) -> Any:
            if not self._check():
                return None
            return await val(*args, **kwargs)

        return _guarded

    def __repr__(self) -> str:
        return f"_ConditionalMiddleware(inner={self._inner!r})"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_middleware_schema.py -v`
Expected: PASS — all tests green (both Task 1 and Task 2)

**Step 5: Run existing middleware tests to check for regressions**

Run: `uv run pytest tests/ -k "middleware" -v --tb=short`
Expected: PASS — no regressions

**Step 6: Commit**

```bash
git add src/adk_fluent/middleware.py tests/manual/test_middleware_schema.py
git commit -m "refactor: rewrite _ConditionalMiddleware for deferred evaluation"
```

______________________________________________________________________

### Task 3: Extend `M.when()` for PredicateSchema

**Files:**

- Modify: `src/adk_fluent/_middleware.py` (line 141, `M.when()`)
- Test: `tests/manual/test_middleware_schema.py` (append)

**Step 1: Write the failing test**

Append to `tests/manual/test_middleware_schema.py`:

```python
class TestMWhenPredicateSchema:
    """M.when() accepts PredicateSchema subclasses."""

    def test_m_when_predicate_creates_conditional(self):
        from adk_fluent._middleware import M
        from adk_fluent._predicate_schema import PredicateSchema

        class IsPremium(PredicateSchema):
            @staticmethod
            def evaluate():
                return True

        class Inner:
            async def before_agent(self, ctx, name):
                pass

        result = M.when(IsPremium, Inner())
        assert len(result) == 1
        # Inner middleware should be wrapped in _ConditionalMiddleware
        wrapped = result.to_stack()[0]
        assert callable(getattr(wrapped, "before_agent", None))

    def test_m_when_string_still_works(self):
        from adk_fluent._middleware import M

        class Inner:
            async def before_agent(self, ctx, name):
                pass

        result = M.when("stream", Inner())
        assert len(result) == 1

    def test_m_when_callable_still_works(self):
        from adk_fluent._middleware import M

        class Inner:
            async def before_agent(self, ctx, name):
                pass

        result = M.when(lambda: True, Inner())
        assert len(result) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_middleware_schema.py::TestMWhenPredicateSchema -v`
Expected: FAIL — `M.when()` type annotation rejects `type` argument (or it passes because `type` is callable — either way, verify the test infrastructure works)

**Step 3: Update `M.when()` signature and docstring**

In `src/adk_fluent/_middleware.py`, update the `when` method (line 141):

```python
    @staticmethod
    def when(condition: str | Callable[[], bool] | type, mw: MComposite | Any) -> MComposite:
        """Conditionally apply middleware.

        ``condition`` can be:
            - String shortcut: ``"stream"``, ``"dispatched"``, ``"pipeline"``
              matching ExecutionMode.
            - Callable returning bool, evaluated at hook invocation time.
            - ``PredicateSchema`` subclass, evaluated against session state
              at hook invocation time.

        Usage::

            M.when("stream", M.latency())
            M.when(lambda: is_debug(), M.log())
            M.when(PremiumOnly, M.scope("writer", M.cost()))
        """
        from adk_fluent.middleware import _ConditionalMiddleware

        stack = mw.to_stack() if isinstance(mw, MComposite) else [mw]
        wrapped = [_ConditionalMiddleware(condition, m) for m in stack]
        return MComposite(wrapped)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_middleware_schema.py -v`
Expected: PASS — all tests green

**Step 5: Commit**

```bash
git add src/adk_fluent/_middleware.py tests/manual/test_middleware_schema.py
git commit -m "feat: extend M.when() to accept PredicateSchema conditions"
```

______________________________________________________________________

### Task 4: Forward `schema` in `_ScopedMiddleware`

**Files:**

- Modify: `src/adk_fluent/middleware.py` (lines 406–417, `_ScopedMiddleware`)
- Test: `tests/manual/test_middleware_schema.py` (append)

**Step 1: Write the failing test**

Append to `tests/manual/test_middleware_schema.py`:

```python
class TestScopedMiddlewareSchema:
    """_ScopedMiddleware forwards schema from inner middleware."""

    def test_schema_accessible_via_getattr(self):
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent.middleware import _ScopedMiddleware

        class MySchema(MiddlewareSchema):
            pass

        class Inner:
            schema = MySchema
            async def before_agent(self, ctx, name):
                pass

        scoped = _ScopedMiddleware("writer", Inner())
        # __getattr__ should forward schema
        assert scoped.schema is MySchema

    def test_agents_overrides_inner(self):
        from adk_fluent.middleware import _ScopedMiddleware

        class Inner:
            agents = "original"

        scoped = _ScopedMiddleware("overridden", Inner())
        assert scoped.agents == "overridden"
```

**Step 2: Run test to verify it passes (or fails)**

Run: `uv run pytest tests/manual/test_middleware_schema.py::TestScopedMiddlewareSchema -v`
Expected: PASS — `_ScopedMiddleware.__getattr__` already forwards all attributes from inner. If it fails, proceed to Step 3.

**Step 3: If test fails, update `_ScopedMiddleware`**

Only needed if `__getattr__` doesn't fire for `schema` (e.g., if Python checks `__dict__` first). If so, explicitly forward in `__init__`:

```python
class _ScopedMiddleware:
    def __init__(self, agents, inner):
        self.agents = agents
        self._inner = inner
        schema = getattr(inner, "schema", None)
        if schema is not None:
            self.schema = schema
```

**Step 4: Commit**

```bash
git add src/adk_fluent/middleware.py tests/manual/test_middleware_schema.py
git commit -m "test: verify _ScopedMiddleware forwards schema attribute"
```

______________________________________________________________________

### Task 5: Add Pass 14 to contract checker

**Files:**

- Modify: `src/adk_fluent/testing/contracts.py` (after Pass 13, ~line 661)
- Test: `tests/manual/test_middleware_schema.py` (append)

**Step 1: Write the failing tests**

Append to `tests/manual/test_middleware_schema.py`:

```python
class TestContractCheckerPass14:
    """Pass 14: Middleware schema validation in contract checker."""

    def _make_agent_node(self, name, output_key=None, tool_schema=None):
        """Create a minimal AgentNode-like object."""
        from types import SimpleNamespace
        return SimpleNamespace(
            name=name,
            output_key=output_key,
            tool_schema=tool_schema,
            callback_schema=None,
            prompt_schema=None,
            writes_keys=frozenset(),
            reads_keys=frozenset(),
            include_contents="default",
            instruction="",
            context_spec=None,
            produces_type=None,
            consumes_type=None,
            rules=(),
            predicate=None,
        )

    def _make_sequence(self, children, middlewares=()):
        from types import SimpleNamespace
        return SimpleNamespace(
            name="test_seq",
            children=tuple(children),
            middlewares=middlewares,
        )

    def test_scoped_middleware_reads_satisfied(self):
        """Scoped middleware whose reads are produced upstream: no warnings."""
        from typing import Annotated
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent._schema_base import Reads
        from adk_fluent.testing.contracts import check_contracts

        class NeedsResult(MiddlewareSchema):
            result: Annotated[str, Reads()]

        class MyMW:
            agents = "reviewer"
            schema = NeedsResult

        producer = self._make_agent_node("writer", output_key="result")
        consumer = self._make_agent_node("reviewer")
        seq = self._make_sequence([producer, consumer], middlewares=[MyMW()])

        issues = check_contracts(seq)
        mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
        assert len(mw_issues) == 0

    def test_scoped_middleware_reads_unsatisfied(self):
        """Scoped middleware whose reads are NOT produced upstream: warning."""
        from typing import Annotated
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent._schema_base import Reads
        from adk_fluent.testing.contracts import check_contracts

        class NeedsMissing(MiddlewareSchema):
            missing_key: Annotated[str, Reads()]

        class MyMW:
            agents = "reviewer"
            schema = NeedsMissing

        producer = self._make_agent_node("writer", output_key="result")
        consumer = self._make_agent_node("reviewer")
        seq = self._make_sequence([producer, consumer], middlewares=[MyMW()])

        issues = check_contracts(seq)
        mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
        assert len(mw_issues) == 1
        assert "missing_key" in mw_issues[0]["message"]

    def test_unscoped_middleware_skipped(self):
        """Middleware without agents scope: no validation."""
        from typing import Annotated
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent._schema_base import Reads
        from adk_fluent.testing.contracts import check_contracts

        class NeedsMissing(MiddlewareSchema):
            missing_key: Annotated[str, Reads()]

        class GlobalMW:
            # No agents attribute — unscoped
            schema = NeedsMissing

        agent = self._make_agent_node("writer")
        seq = self._make_sequence([agent], middlewares=[GlobalMW()])

        issues = check_contracts(seq)
        mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
        assert len(mw_issues) == 0

    def test_middleware_writes_promoted(self):
        """Scoped middleware writes become available to downstream agents."""
        from typing import Annotated
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent._schema_base import Reads, Writes
        from adk_fluent.testing.contracts import check_contracts

        class WriterSchema(MiddlewareSchema):
            enriched: Annotated[str, Writes()]

        class WriterMW:
            agents = "enricher"
            schema = WriterSchema

        class ReaderSchema(MiddlewareSchema):
            enriched: Annotated[str, Reads()]

        class ReaderMW:
            agents = "consumer"
            schema = ReaderSchema

        enricher = self._make_agent_node("enricher")
        consumer = self._make_agent_node("consumer")
        seq = self._make_sequence([enricher, consumer], middlewares=[WriterMW(), ReaderMW()])

        issues = check_contracts(seq)
        mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
        assert len(mw_issues) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_middleware_schema.py::TestContractCheckerPass14 -v`
Expected: FAIL — `check_contracts` doesn't accept/use `middlewares` and doesn't validate middleware schemas

**Step 3: Update contract checker**

In `src/adk_fluent/testing/contracts.py`:

**3a.** Update `check_contracts()` (line 777) to extract middlewares from the IR node and pass them to `_check_sequence_contracts`:

```python
def check_contracts(ir_node: Any) -> list[dict[str, str] | str]:
    # ... existing imports and dispatching ...
    if isinstance(ir_node, SequenceNode):
        if not ir_node.children:
            return []
        middlewares = getattr(ir_node, "middlewares", ())
        return _check_sequence_contracts(ir_node.children, middlewares=middlewares)
    # ... rest unchanged ...
```

**3b.** Update `_check_sequence_contracts` signature (line 141) to accept `middlewares`:

```python
def _check_sequence_contracts(
    children: tuple, scope: str = "", middlewares: tuple | list = ()
) -> list[dict[str, str] | str]:
```

**3c.** Add Pass 14 after Pass 13 (after line 661, before `return issues`):

```python
    # =================================================================
    # Pass 14: MiddlewareSchema dependency validation
    # =================================================================
    if middlewares:
        # Rebuild available keys at each agent position for middleware checking
        mw_available: dict[str, set[str]] = {}  # agent_name -> keys available at position
        mw_cumulative: set[str] = set()

        for child in children:
            child_name = getattr(child, "name", "?")
            mw_available[child_name] = set(mw_cumulative)
            # Accumulate keys from this child
            ok = getattr(child, "output_key", None)
            if ok:
                mw_cumulative.add(ok)
            writes = getattr(child, "writes_keys", frozenset())
            if writes:
                mw_cumulative |= writes
            for sa in ("tool_schema", "callback_schema"):
                s = getattr(child, sa, None)
                if s is not None and hasattr(s, "writes_keys"):
                    mw_cumulative |= s.writes_keys()

        # Check each scoped middleware
        for mw in middlewares:
            agents_scope = getattr(mw, "agents", None)
            schema_cls = getattr(mw, "schema", None)
            if agents_scope is None or schema_cls is None:
                continue
            if not hasattr(schema_cls, "reads_keys"):
                continue

            # Normalize target agents
            if isinstance(agents_scope, str):
                target_names = (agents_scope,)
            elif isinstance(agents_scope, tuple):
                target_names = agents_scope
            else:
                continue  # regex/callable scopes can't be statically resolved

            schema_reads = schema_cls.reads_keys()
            schema_writes = schema_cls.writes_keys() if hasattr(schema_cls, "writes_keys") else frozenset()

            for target in target_names:
                if target not in mw_available:
                    continue  # agent not in this pipeline
                available = mw_available[target]
                missing = schema_reads - available
                for key in sorted(missing):
                    issues.append(
                        {
                            "level": "warning",
                            "agent": _scoped(target),
                            "message": (
                                f"MiddlewareSchema reads key '{key}' but it is "
                                f"not produced by any upstream agent"
                            ),
                            "hint": (
                                f"Add .save_as('{key}') to an upstream agent "
                                f"or use S.set() / S.capture() to provide this key."
                            ),
                        }
                    )

                # Promote middleware writes at this agent's position
                if schema_writes and target in mw_available:
                    # Add writes to all agents AFTER this target
                    found = False
                    for child in children:
                        cn = getattr(child, "name", "?")
                        if cn == target:
                            found = True
                            continue
                        if found and cn in mw_available:
                            mw_available[cn] |= schema_writes
```

**3d.** Update the module docstring to mention Pass 14.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_middleware_schema.py -v`
Expected: PASS — all tests green

**Step 5: Run full contract checker test suite**

Run: `uv run pytest tests/ -k "contract" -v --tb=short`
Expected: PASS — no regressions

**Step 6: Commit**

```bash
git add src/adk_fluent/testing/contracts.py tests/manual/test_middleware_schema.py
git commit -m "feat: add Pass 14 — MiddlewareSchema contract validation"
```

______________________________________________________________________

### Task 6: Exports and integration

**Files:**

- Modify: `src/adk_fluent/__init__.py` (regenerate via `just generate`)
- Modify: `src/adk_fluent/prelude.py` (add `MiddlewareSchema`)
- Test: `tests/manual/test_api_surface_v2.py` (update prelude assertions)

**Step 1: Add `MiddlewareSchema` to prelude**

In `src/adk_fluent/prelude.py`, add import and `__all__` entry:

```python
from adk_fluent._middleware_schema import MiddlewareSchema
```

Add `"MiddlewareSchema"` to the `__all__` list under a suitable tier comment.

**Step 2: Regenerate `__init__.py`**

Run: `just generate`

This auto-discovers `__all__` from `_middleware_schema.py` and adds the export.

**Step 3: Update prelude test**

In `tests/manual/test_api_surface_v2.py`, add `"MiddlewareSchema"` to the expected set and update the count.

**Step 4: Run prelude test**

Run: `uv run pytest tests/manual/test_api_surface_v2.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -x --tb=short`
Expected: PASS — all tests green

**Step 6: Lint and typecheck**

Run: `ruff check --fix . && ruff format .`
Run: `just typecheck-core`
Expected: Clean

**Step 7: Commit**

```bash
git add src/adk_fluent/prelude.py src/adk_fluent/__init__.py tests/manual/test_api_surface_v2.py
git commit -m "feat: export MiddlewareSchema from prelude and __init__"
```

______________________________________________________________________

### Task 7: Final verification

**Step 1: Run full test suite**

Run: `just test`
Expected: All tests pass

**Step 2: Run lint + typecheck**

Run: `just preflight`
Expected: Clean

**Step 3: Run cookbook tests**

Run: `uv run pytest examples/cookbook/ -q`
Expected: All pass

**Step 4: Verify backward compatibility**

Run: `uv run python -c "from adk_fluent import M; print(M.when('stream', M.log()))"`
Expected: Prints `MComposite([_ConditionalMiddleware])` — string shortcuts still work

Run: `uv run python -c "from adk_fluent import MiddlewareSchema; print(MiddlewareSchema)"`
Expected: Prints `<class 'adk_fluent._middleware_schema.MiddlewareSchema'>`
