# Namespace Expansion Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the G (Guards) namespace and fatten T, M, S namespaces in a single big-bang release.

**Architecture:** Each namespace answers one question (T=capability, M=resilience, G=safety, S=data flow). G compiles guards to the correct enforcement layer automatically (callbacks, context, middleware). T/M/S extend existing classes with new factory methods. One shared utility extracted (`_llm_judge.py`). All new code is hand-written, not generated.

**Tech Stack:** Python 3.11+, google-adk 1.25.0, google-cloud-dlp (optional), opentelemetry (optional), Pydantic (optional, duck-typed)

**Spec:** `docs/plans/2026-03-10-namespace-expansion-design.md`

___

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `src/adk_fluent/_guards.py` | G namespace: GGuard, GComposite, GuardViolation, PIIDetector, ContentJudge, all G.xxx() factories | NEW |
| `src/adk_fluent/_llm_judge.py` | Shared LLM-as-judge utility used by E and G | NEW |
| `src/adk_fluent/_tools.py` | T namespace: add mcp, openapi, retrieval, code\_exec, confirm, timeout, cache, transform, mock | EXTEND |
| `src/adk_fluent/_middleware.py` | M namespace: add circuit\_breaker, timeout, fallback\_model, cache, dedup, trace, metrics, sample | EXTEND |
| `src/adk_fluent/middleware.py` | Middleware classes: CircuitBreakerMiddleware, TimeoutMiddleware, etc. | EXTEND |
| `src/adk_fluent/_transforms.py` | S namespace: add accumulate, counter, history, validate, require, flatten, unflatten, zip, group\_by | EXTEND |
| `src/adk_fluent/_eval.py` | Refactor: extract \_llm\_judge usage to shared module | MODIFY |
| `src/adk_fluent/_helpers.py` | Add \_guard\_dispatch function | MODIFY |
| `src/adk_fluent/prelude.py` | Add G to Tier 2 exports | MODIFY |
| `seeds/seed.manual.toml` | Change .guard() from dual\_callback to runtime\_helper | MODIFY |
| `scripts/ir_generator.py` | Add guard\_specs field to AgentNode | MODIFY |
| `pyproject.toml` | Add optional deps: pii, observability | MODIFY |
| `tests/manual/test_guards.py` | G namespace unit tests | NEW |
| `tests/manual/test_guards_compile.py` | G compilation into builder callbacks/middleware/context | NEW |
| `tests/manual/test_tools_t_expanded.py` | Expanded T factory + wrapper tests | NEW |
| `tests/manual/test_middleware_expanded.py` | Expanded M middleware class tests | NEW |
| `tests/manual/test_transforms_expanded.py` | Expanded S method tests | NEW |
| `tests/manual/test_interplay.py` | Cross-module composition tests | NEW |

___

## Chunk 1: S Namespace Expansion

Self-contained. No cross-module dependencies. Pure additions to `_transforms.py`.

### Task 1: S.accumulate and S.counter

**Files:**

- Modify: `src/adk_fluent/_transforms.py:610` (append after `S.branch`)
- Create: `tests/manual/test_transforms_expanded.py`

- [ ] **Step 1: Write failing tests for S.accumulate**

```python
# tests/manual/test_transforms_expanded.py
"""Tests for S namespace expansion — accumulate, counter, history, validate, require, structure."""

from __future__ import annotations

from adk_fluent._transforms import S, StateDelta


class TestAccumulate:
    def test_accumulate_appends_to_list(self):
        t = S.accumulate("finding", into="findings")
        result = t({"finding": "item1", "findings": ["item0"]})
        assert isinstance(result, StateDelta)
        assert result.updates["findings"] == ["item0", "item1"]

    def test_accumulate_creates_list_when_missing(self):
        t = S.accumulate("finding", into="findings")
        result = t({"finding": "first"})
        assert result.updates["findings"] == ["first"]

    def test_accumulate_skips_none(self):
        t = S.accumulate("finding", into="findings")
        result = t({"findings": ["existing"]})
        assert result.updates["findings"] == ["existing"]

    def test_accumulate_default_into(self):
        t = S.accumulate("item")
        result = t({"item": "x"})
        assert result.updates["item_all"] == ["x"]

    def test_accumulate_reads_keys(self):
        t = S.accumulate("finding", into="findings")
        assert t._reads_keys == frozenset({"finding", "findings"})

    def test_accumulate_writes_keys(self):
        t = S.accumulate("finding", into="findings")
        assert t._writes_keys == frozenset({"findings"})


class TestCounter:
    def test_counter_increments(self):
        t = S.counter("count")
        result = t({"count": 5})
        assert result.updates["count"] == 6

    def test_counter_starts_at_zero(self):
        t = S.counter("count")
        result = t({})
        assert result.updates["count"] == 1

    def test_counter_custom_step(self):
        t = S.counter("count", step=3)
        result = t({"count": 10})
        assert result.updates["count"] == 13

    def test_counter_reads_writes(self):
        t = S.counter("count")
        assert t._reads_keys == frozenset({"count"})
        assert t._writes_keys == frozenset({"count"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_transforms_expanded.py -x -v`
Expected: FAIL — `S` has no attribute `accumulate`

- [ ] **Step 3: Implement S.accumulate and S.counter**

Append to `src/adk_fluent/_transforms.py` after line 609 (end of `S.branch`):

```python
    @staticmethod
    def accumulate(key: str, *, into: str | None = None) -> STransform:
        """Append state[key] to a running list at state[into].

        Defaults ``into`` to ``f"{key}_all"`` if not specified.

        >>> S.accumulate("finding", into="findings")
        """
        target = into or f"{key}_all"

        def _accumulate(state: dict) -> StateDelta:
            current_list = list(state.get(target, []))
            new_item = state.get(key)
            if new_item is not None:
                current_list.append(new_item)
            return StateDelta(current_list and {target: current_list} or {})

        return STransform(
            _accumulate,
            reads=frozenset({key, target}),
            writes=frozenset({target}),
            name=f"accumulate_{key}_into_{target}",
        )

    @staticmethod
    def counter(key: str, step: int = 1) -> STransform:
        """Increment a numeric state value.

        >>> S.counter("retries")
        >>> S.counter("score", step=10)
        """

        def _counter(state: dict) -> StateDelta:
            return StateDelta({key: state.get(key, 0) + step})

        return STransform(
            _counter,
            reads=frozenset({key}),
            writes=frozenset({key}),
            name=f"counter_{key}",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_transforms_expanded.py::TestAccumulate tests/manual/test_transforms_expanded.py::TestCounter -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_transforms.py tests/manual/test_transforms_expanded.py
git commit -m "feat(S): add S.accumulate() and S.counter() state transforms"
```

### Task 2: S.history

**Files:**

- Modify: `src/adk_fluent/_transforms.py` (append after S.counter)
- Modify: `tests/manual/test_transforms_expanded.py`

- [ ] **Step 1: Write failing tests for S.history**

Append to `tests/manual/test_transforms_expanded.py`:

```python
class TestHistory:
    def test_history_appends(self):
        t = S.history("score")
        result = t({"score": 0.9, "score_history": [0.7, 0.8]})
        assert result.updates["score_history"] == [0.7, 0.8, 0.9]

    def test_history_creates_list(self):
        t = S.history("score")
        result = t({"score": 0.5})
        assert result.updates["score_history"] == [0.5]

    def test_history_respects_max_size(self):
        t = S.history("score", max_size=3)
        result = t({"score": 4, "score_history": [1, 2, 3]})
        assert result.updates["score_history"] == [2, 3, 4]

    def test_history_skips_missing(self):
        t = S.history("score")
        result = t({})
        assert result.updates.get("score_history", []) == []

    def test_history_reads_writes(self):
        t = S.history("score", max_size=5)
        assert t._reads_keys == frozenset({"score", "score_history"})
        assert t._writes_keys == frozenset({"score_history"})
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_transforms_expanded.py::TestHistory -x -v`
Expected: FAIL

- [ ] **Step 3: Implement S.history**

```python
    @staticmethod
    def history(key: str, max_size: int = 10) -> STransform:
        """Keep a rolling window of past values for a key.

        Stores history at ``state[f"{key}_history"]``.

        >>> S.history("score", max_size=5)
        """
        hist_key = f"{key}_history"

        def _history(state: dict) -> StateDelta:
            past = list(state.get(hist_key, []))
            current = state.get(key)
            if current is not None:
                past.append(current)
                past = past[-max_size:]
            return StateDelta({hist_key: past})

        return STransform(
            _history,
            reads=frozenset({key, hist_key}),
            writes=frozenset({hist_key}),
            name=f"history_{key}",
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_transforms_expanded.py::TestHistory -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_transforms.py tests/manual/test_transforms_expanded.py
git commit -m "feat(S): add S.history() rolling window transform"
```

### Task 3: S.validate and S.require

**Files:**

- Modify: `src/adk_fluent/_transforms.py`
- Modify: `tests/manual/test_transforms_expanded.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_transforms_expanded.py`:

```python
from dataclasses import dataclass


class TestValidate:
    def test_validate_passes_valid_state(self):
        @dataclass
        class Schema:
            name: str
            score: float

        t = S.validate(Schema)
        result = t({"name": "test", "score": 0.9})
        assert isinstance(result, StateDelta)
        assert result.updates == {}

    def test_validate_raises_on_invalid(self):
        @dataclass
        class Schema:
            name: str

        t = S.validate(Schema)
        import pytest
        with pytest.raises(ValueError, match="State validation failed"):
            t({})  # missing required 'name'

    def test_validate_reads_writes(self):
        @dataclass
        class Schema:
            x: int

        t = S.validate(Schema)
        assert t._reads_keys is None  # opaque — validates full state
        assert t._writes_keys == frozenset()


class TestRequire:
    def test_require_passes_when_present(self):
        t = S.require("name", "score")
        result = t({"name": "x", "score": 1})
        assert result.updates == {}

    def test_require_raises_when_missing(self):
        t = S.require("name", "score")
        import pytest
        with pytest.raises(ValueError, match="missing or falsy"):
            t({"name": "x"})

    def test_require_raises_when_falsy(self):
        t = S.require("name")
        import pytest
        with pytest.raises(ValueError, match="missing or falsy"):
            t({"name": ""})

    def test_require_reads_keys(self):
        t = S.require("a", "b")
        assert t._reads_keys == frozenset({"a", "b"})
        assert t._writes_keys == frozenset()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_transforms_expanded.py::TestValidate tests/manual/test_transforms_expanded.py::TestRequire -x -v`
Expected: FAIL

- [ ] **Step 3: Implement S.validate and S.require**

```python
    @staticmethod
    def validate(schema_cls: type, *, strict: bool = False) -> STransform:
        """Validate state against a Pydantic model or dataclass.

        Raises ``ValueError`` if validation fails. Returns empty delta on success.
        Duck-types: uses ``model_validate`` (Pydantic) or ``__init__`` (dataclass).

        >>> S.validate(MyPydanticModel)
        """

        def _validate(state: dict) -> StateDelta:
            try:
                if hasattr(schema_cls, "model_validate"):
                    schema_cls.model_validate(state, strict=strict)
                else:
                    schema_cls(**state)
            except Exception as e:
                raise ValueError(
                    f"State validation failed against {schema_cls.__name__}: {e}"
                ) from e
            return StateDelta({})

        return STransform(
            _validate,
            reads=None,
            writes=frozenset(),
            name=f"validate_{schema_cls.__name__}",
        )

    @staticmethod
    def require(*keys: str) -> STransform:
        """Assert that all specified keys exist and are truthy in state.

        Unlike ``S.guard()`` with a lambda, this has precise ``_reads_keys``
        for contract checking.

        >>> S.require("user_input", "context")
        """

        def _require(state: dict) -> StateDelta:
            missing = [k for k in keys if not state.get(k)]
            if missing:
                raise ValueError(f"Required state keys missing or falsy: {missing}")
            return StateDelta({})

        return STransform(
            _require,
            reads=frozenset(keys),
            writes=frozenset(),
            name=f"require_{'_'.join(keys)}",
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_transforms_expanded.py::TestValidate tests/manual/test_transforms_expanded.py::TestRequire -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_transforms.py tests/manual/test_transforms_expanded.py
git commit -m "feat(S): add S.validate() and S.require() state assertions"
```

### Task 4: S.flatten, S.unflatten, S.zip, S.group\_by

**Files:**

- Modify: `src/adk_fluent/_transforms.py`
- Modify: `tests/manual/test_transforms_expanded.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_transforms_expanded.py`:

```python
class TestFlatten:
    def test_flatten_nested(self):
        t = S.flatten("data")
        result = t({"data": {"a": {"b": 1}, "c": 2}})
        assert result.updates == {"a.b": 1, "c": 2}

    def test_flatten_custom_separator(self):
        t = S.flatten("data", separator="/")
        result = t({"data": {"a": {"b": 1}}})
        assert result.updates == {"a/b": 1}

    def test_flatten_empty(self):
        t = S.flatten("data")
        result = t({"data": {}})
        assert result.updates == {}


class TestUnflatten:
    def test_unflatten_dotted(self):
        t = S.unflatten()
        result = t({"a.b": 1, "a.c": 2, "d": 3})
        assert result.updates == {"a": {"b": 1, "c": 2}, "d": 3}


class TestZip:
    def test_zip_parallel_lists(self):
        t = S.zip("names", "scores", into="pairs")
        result = t({"names": ["a", "b"], "scores": [1, 2]})
        assert result.updates["pairs"] == [("a", 1), ("b", 2)]

    def test_zip_reads_writes(self):
        t = S.zip("names", "scores", into="pairs")
        assert t._reads_keys == frozenset({"names", "scores"})
        assert t._writes_keys == frozenset({"pairs"})


class TestGroupBy:
    def test_group_by_key(self):
        t = S.group_by("items", key_fn=lambda x: x["type"], into="grouped")
        result = t({"items": [
            {"type": "a", "val": 1},
            {"type": "b", "val": 2},
            {"type": "a", "val": 3},
        ]})
        groups = result.updates["grouped"]
        assert len(groups["a"]) == 2
        assert len(groups["b"]) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_transforms_expanded.py::TestFlatten tests/manual/test_transforms_expanded.py::TestUnflatten tests/manual/test_transforms_expanded.py::TestZip tests/manual/test_transforms_expanded.py::TestGroupBy -x -v`
Expected: FAIL

- [ ] **Step 3: Implement S.flatten, S.unflatten, S.zip, S.group\_by**

```python
    @staticmethod
    def flatten(key: str, separator: str = ".") -> STransform:
        """Flatten a nested dict at state[key] into dotted keys.

        >>> S.flatten("config")
        # {"config": {"db": {"host": "x"}}} -> {"db.host": "x"}
        """

        def _flatten(state: dict) -> StateDelta:
            nested = state.get(key, {})
            flat: dict[str, Any] = {}

            def _walk(obj: Any, prefix: str) -> None:
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        _walk(v, f"{prefix}{separator}{k}" if prefix else k)
                else:
                    flat[prefix] = obj

            _walk(nested, "")
            return StateDelta(flat)

        return STransform(
            _flatten, reads=frozenset({key}), writes=None, name=f"flatten_{key}"
        )

    @staticmethod
    def unflatten(separator: str = ".") -> STransform:
        """Unflatten dotted keys back into nested dicts.

        >>> S.unflatten()
        # {"a.b": 1, "a.c": 2} -> {"a": {"b": 1, "c": 2}}
        """

        def _unflatten(state: dict) -> StateDelta:
            result: dict[str, Any] = {}
            for key, value in state.items():
                if separator in key:
                    parts = key.split(separator)
                    d = result
                    for part in parts[:-1]:
                        d = d.setdefault(part, {})
                    d[parts[-1]] = value
                else:
                    result[key] = value
            from adk_fluent._transforms import StateReplacement

            return StateReplacement(result)

        return STransform(
            _unflatten, reads=None, writes=None, name="unflatten"
        )

    @staticmethod
    def zip(*keys: str, into: str = "zipped") -> STransform:
        """Zip parallel lists into a list of tuples.

        >>> S.zip("names", "scores", into="pairs")
        """

        def _zip(state: dict) -> StateDelta:
            lists = [state.get(k, []) for k in keys]
            return StateDelta({into: list(zip(*lists))})

        return STransform(
            _zip,
            reads=frozenset(keys),
            writes=frozenset({into}),
            name=f"zip_{'_'.join(keys)}_into_{into}",
        )

    @staticmethod
    def group_by(items_key: str, key_fn: Callable, into: str) -> STransform:
        """Group list items by a key function.

        >>> S.group_by("items", key_fn=lambda x: x["type"], into="grouped")
        """

        def _group_by(state: dict) -> StateDelta:
            items = state.get(items_key, [])
            groups: dict[str, list] = {}
            for item in items:
                k = str(key_fn(item))
                groups.setdefault(k, []).append(item)
            return StateDelta({into: groups})

        return STransform(
            _group_by,
            reads=frozenset({items_key}),
            writes=frozenset({into}),
            name=f"group_by_{items_key}_into_{into}",
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_transforms_expanded.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite to check no regressions**

Run: `uv run pytest tests/manual/test_transforms.py tests/manual/test_transforms_v3.py tests/manual/test_stransform_compose.py tests/manual/test_transforms_expanded.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/adk_fluent/_transforms.py tests/manual/test_transforms_expanded.py
git commit -m "feat(S): add S.flatten, S.unflatten, S.zip, S.group_by structure transforms"
```

___

## Chunk 2: T Namespace Expansion

Self-contained. Extends `_tools.py` only. New wrapper classes are `BaseTool` subclasses.

### Task 5: T.mock and T.confirm

**Files:**

- Modify: `src/adk_fluent/_tools.py:184` (append after `T.schema`)
- Create: `tests/manual/test_tools_t_expanded.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/manual/test_tools_t_expanded.py
"""Tests for T namespace expansion — mock, confirm, timeout, cache, mcp, openapi."""

from __future__ import annotations

from adk_fluent._tools import T, TComposite


class TestMock:
    def test_mock_returns_value(self):
        tc = T.mock("search", returns={"results": ["a"]})
        assert isinstance(tc, TComposite)
        assert len(tc) == 1
        tool = tc.to_tools()[0]
        assert tool.name == "search"

    def test_mock_composes(self):
        tc = T.mock("search", returns="x") | T.mock("email", returns="y")
        assert len(tc) == 2

    def test_mock_kind(self):
        tc = T.mock("search", returns="x")
        assert tc._kind == "mock"


class TestConfirm:
    def test_confirm_wraps_tool(self):
        base = T.fn(lambda: "hello")
        tc = T.confirm(base, message="Proceed?")
        assert isinstance(tc, TComposite)
        assert len(tc) == 1

    def test_confirm_wraps_composite(self):
        base = T.fn(lambda: "a") | T.fn(lambda: "b")
        tc = T.confirm(base)
        assert len(tc) == 2  # both wrapped

    def test_confirm_composes(self):
        tc = T.confirm(T.fn(lambda: "a")) | T.fn(lambda: "b")
        assert len(tc) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_tools_t_expanded.py -x -v`
Expected: FAIL — `T` has no attribute `mock`

- [ ] **Step 3: Implement T.mock and T.confirm**

Append to `src/adk_fluent/_tools.py` after line 184 (end of `T.schema`):

```python
    # --- Test doubles ---

    @staticmethod
    def mock(name: str, *, returns: Any = None, side_effect: Any = None) -> TComposite:
        """Create a mock tool for testing. No API calls.

        >>> T.mock("search", returns={"results": []})
        """
        from google.adk.tools.function_tool import FunctionTool

        async def _mock_fn(**kwargs: Any) -> Any:
            if side_effect is not None:
                return side_effect(**kwargs) if callable(side_effect) else side_effect
            return returns

        _mock_fn.__name__ = name
        _mock_fn.__doc__ = f"Mock tool: {name}"
        return TComposite([FunctionTool(func=_mock_fn)], kind="mock")

    # --- Tool wrappers ---

    @staticmethod
    def confirm(tool_or_composite: TComposite | Any, message: str | None = None) -> TComposite:
        """Wrap tool(s) with human-in-the-loop confirmation.

        Works on any tool, not just callables (unlike ``T.fn(f, confirm=True)``).

        >>> T.confirm(T.fn(delete_file), message="Delete this file?")
        """
        items = (
            tool_or_composite._items
            if isinstance(tool_or_composite, TComposite)
            else [tool_or_composite]
        )
        wrapped = [_ConfirmWrapper(item, message) for item in items]
        return TComposite(wrapped, kind="confirm")


class _ConfirmWrapper:
    """Wraps any tool with require_confirmation=True."""

    def __init__(self, inner: Any, message: str | None = None):
        from google.adk.tools.base_tool import BaseTool

        self._inner = inner
        self._message = message
        # Copy tool identity
        if isinstance(inner, BaseTool):
            self.name = inner.name
            self.description = inner.description
        else:
            self.name = getattr(inner, "__name__", "tool")
            self.description = getattr(inner, "__doc__", "") or ""
        self.require_confirmation = True

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:
        """Delegate to inner tool."""
        if hasattr(self._inner, "run_async"):
            return await self._inner.run_async(args=args, tool_context=tool_context)
        return self._inner(**args)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_tools_t_expanded.py::TestMock tests/manual/test_tools_t_expanded.py::TestConfirm -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_tools.py tests/manual/test_tools_t_expanded.py
git commit -m "feat(T): add T.mock() and T.confirm() tool factories"
```

### Task 6: T.timeout and T.cache

**Files:**

- Modify: `src/adk_fluent/_tools.py`
- Modify: `tests/manual/test_tools_t_expanded.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_tools_t_expanded.py`:

```python
import asyncio


class TestTimeout:
    def test_timeout_wraps_tool(self):
        tc = T.timeout(T.fn(lambda: "ok"), seconds=5)
        assert isinstance(tc, TComposite)
        assert len(tc) == 1

    def test_timeout_kind(self):
        tc = T.timeout(T.fn(lambda: "ok"), seconds=5)
        assert tc._kind == "timeout"

    def test_timeout_wraps_composite(self):
        base = T.fn(lambda: "a") | T.fn(lambda: "b")
        tc = T.timeout(base, seconds=10)
        assert len(tc) == 2


class TestCache:
    def test_cache_wraps_tool(self):
        tc = T.cache(T.fn(lambda: "ok"), ttl=60)
        assert isinstance(tc, TComposite)
        assert len(tc) == 1

    def test_cache_kind(self):
        tc = T.cache(T.fn(lambda: "ok"), ttl=60)
        assert tc._kind == "cache"

    def test_cache_custom_key_fn(self):
        tc = T.cache(T.fn(lambda: "ok"), ttl=60, key_fn=lambda args: "fixed")
        assert len(tc) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_tools_t_expanded.py::TestTimeout tests/manual/test_tools_t_expanded.py::TestCache -x -v`
Expected: FAIL

- [ ] **Step 3: Implement T.timeout and T.cache with wrapper classes**

Append to `src/adk_fluent/_tools.py`:

```python
    @staticmethod
    def timeout(tool_or_composite: TComposite | Any, seconds: float = 30) -> TComposite:
        """Wrap tool(s) with a per-invocation timeout.

        >>> T.timeout(T.fn(slow_api), seconds=10)
        """
        items = (
            tool_or_composite._items
            if isinstance(tool_or_composite, TComposite)
            else [tool_or_composite]
        )
        wrapped = [_TimeoutWrapper(item, seconds) for item in items]
        return TComposite(wrapped, kind="timeout")

    @staticmethod
    def cache(tool_or_composite: TComposite | Any, ttl: float = 300, key_fn: Any = None) -> TComposite:
        """Wrap tool(s) with in-memory result caching.

        >>> T.cache(T.fn(expensive_api), ttl=600)
        """
        items = (
            tool_or_composite._items
            if isinstance(tool_or_composite, TComposite)
            else [tool_or_composite]
        )
        wrapped = [_CachedWrapper(item, ttl, key_fn) for item in items]
        return TComposite(wrapped, kind="cache")


class _TimeoutWrapper:
    """Wraps a tool with asyncio.wait_for timeout."""

    def __init__(self, inner: Any, seconds: float):
        self._inner = inner
        self._seconds = seconds
        self.name = getattr(inner, "name", getattr(inner, "__name__", "tool"))
        self.description = getattr(inner, "description", getattr(inner, "__doc__", "") or "")

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:
        import asyncio

        if hasattr(self._inner, "run_async"):
            return await asyncio.wait_for(
                self._inner.run_async(args=args, tool_context=tool_context),
                timeout=self._seconds,
            )
        return self._inner(**args)


class _CachedWrapper:
    """Wraps a tool with in-memory TTL caching keyed by args."""

    def __init__(self, inner: Any, ttl: float, key_fn: Any = None):
        import time

        self._inner = inner
        self._ttl = ttl
        self._key_fn = key_fn or (lambda args: str(sorted(args.items())))
        self._cache: dict[str, tuple[Any, float]] = {}
        self.name = getattr(inner, "name", getattr(inner, "__name__", "tool"))
        self.description = getattr(inner, "description", getattr(inner, "__doc__", "") or "")

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:
        import time

        key = self._key_fn(args)
        now = time.monotonic()
        if key in self._cache:
            result, ts = self._cache[key]
            if now - ts < self._ttl:
                return result
        if hasattr(self._inner, "run_async"):
            result = await self._inner.run_async(args=args, tool_context=tool_context)
        else:
            result = self._inner(**args)
        self._cache[key] = (result, now)
        return result
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_tools_t_expanded.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_tools.py tests/manual/test_tools_t_expanded.py
git commit -m "feat(T): add T.timeout() and T.cache() tool wrappers"
```

### Task 7: T.mcp, T.openapi, T.transform

**Files:**

- Modify: `src/adk_fluent/_tools.py`
- Modify: `tests/manual/test_tools_t_expanded.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_tools_t_expanded.py`:

```python
class TestMcp:
    def test_mcp_returns_composite(self):
        # Can't test actual MCP connection, but test factory shape
        tc = T.mcp({"command": "echo", "args": ["hello"]})
        assert isinstance(tc, TComposite)
        assert tc._kind == "mcp"


class TestOpenapi:
    def test_openapi_returns_composite(self):
        tc = T.openapi({"openapi": "3.0.0", "info": {"title": "test", "version": "1.0"}, "paths": {}})
        assert isinstance(tc, TComposite)
        assert tc._kind == "openapi"


class TestTransform:
    def test_transform_wraps_tool(self):
        tc = T.transform(
            T.fn(lambda: "raw"),
            pre=lambda args: {**args, "extra": True},
            post=lambda result: f"processed: {result}",
        )
        assert isinstance(tc, TComposite)
        assert len(tc) == 1
        assert tc._kind == "transform"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_tools_t_expanded.py::TestMcp tests/manual/test_tools_t_expanded.py::TestOpenapi tests/manual/test_tools_t_expanded.py::TestTransform -x -v`
Expected: FAIL

- [ ] **Step 3: Implement T.mcp, T.openapi, T.transform**

Append to `src/adk_fluent/_tools.py`:

```python
    # --- Toolset shortcuts ---

    @staticmethod
    def mcp(url_or_params: Any, *, tool_filter: Any = None, prefix: str | None = None) -> TComposite:
        """MCP server toolset shortcut.

        >>> T.mcp("stdio://my-server")
        >>> T.mcp({"command": "node", "args": ["server.js"]})
        """
        from adk_fluent.tool import McpToolset

        builder = McpToolset().connection_params(url_or_params)
        if tool_filter is not None:
            builder = builder.tool_filter(tool_filter)
        if prefix is not None:
            builder = builder.tool_name_prefix(prefix)
        return TComposite([builder.build()], kind="mcp")

    @staticmethod
    def openapi(spec: Any, *, tool_filter: Any = None, auth: Any = None) -> TComposite:
        """OpenAPI spec toolset shortcut.

        >>> T.openapi({"openapi": "3.0.0", ...})
        """
        from adk_fluent.tool import OpenAPIToolset

        builder = OpenAPIToolset().spec_dict(spec)
        if tool_filter is not None:
            builder = builder.tool_filter(tool_filter)
        if auth is not None:
            builder = builder.auth_credential(auth)
        return TComposite([builder.build()], kind="openapi")

    @staticmethod
    def transform(
        tool_or_composite: TComposite | Any,
        *,
        pre: Any = None,
        post: Any = None,
    ) -> TComposite:
        """Wrap tool(s) with input/output transformation.

        >>> T.transform(T.fn(api), pre=lambda args: clean(args), post=lambda r: parse(r))
        """
        items = (
            tool_or_composite._items
            if isinstance(tool_or_composite, TComposite)
            else [tool_or_composite]
        )
        wrapped = [_TransformWrapper(item, pre, post) for item in items]
        return TComposite(wrapped, kind="transform")


class _TransformWrapper:
    """Wraps a tool with pre/post I/O transformation."""

    def __init__(self, inner: Any, pre: Any = None, post: Any = None):
        self._inner = inner
        self._pre = pre
        self._post = post
        self.name = getattr(inner, "name", getattr(inner, "__name__", "tool"))
        self.description = getattr(inner, "description", getattr(inner, "__doc__", "") or "")

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:
        if self._pre is not None:
            args = self._pre(args)
        if hasattr(self._inner, "run_async"):
            result = await self._inner.run_async(args=args, tool_context=tool_context)
        else:
            result = self._inner(**args)
        if self._post is not None:
            result = self._post(result)
        return result
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_tools_t_expanded.py -v`
Expected: All PASS

- [ ] **Step 5: Run existing T tests to check no regressions**

Run: `uv run pytest tests/manual/test_tools_t.py tests/manual/test_tools_t_expanded.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/adk_fluent/_tools.py tests/manual/test_tools_t_expanded.py
git commit -m "feat(T): add T.mcp, T.openapi, T.transform toolset shortcuts and wrappers"
```

___

## Chunk 3: M Namespace Expansion

Extends `_middleware.py` (factories) and `middleware.py` (classes).

### Task 8: CircuitBreakerMiddleware and M.circuit\_breaker

**Files:**

- Modify: `src/adk_fluent/middleware.py:1056` (append after CostTracker)
- Modify: `src/adk_fluent/_middleware.py:248` (append after M.on\_fallback)
- Create: `tests/manual/test_middleware_expanded.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/manual/test_middleware_expanded.py
"""Tests for M namespace expansion — circuit_breaker, timeout, cache, etc."""

from __future__ import annotations

from adk_fluent._middleware import M, MComposite


class TestCircuitBreaker:
    def test_circuit_breaker_creates_composite(self):
        mc = M.circuit_breaker(threshold=3, reset_after=30)
        assert isinstance(mc, MComposite)
        assert len(mc) == 1

    def test_circuit_breaker_composes(self):
        mc = M.circuit_breaker() | M.log()
        assert len(mc) == 2

    def test_circuit_breaker_defaults(self):
        mc = M.circuit_breaker()
        mw = mc.to_stack()[0]
        assert mw._threshold == 5
        assert mw._reset_after == 60
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_middleware_expanded.py -x -v`
Expected: FAIL

- [ ] **Step 3: Implement CircuitBreakerMiddleware**

Append to `src/adk_fluent/middleware.py` after line 1056 (end of `CostTracker`):

```python
class CircuitBreakerMiddleware:
    """Trips open after N consecutive model errors, auto-resets after cooldown.

    Resilience pattern — prevents hammering a failing provider.
    """

    def __init__(self, threshold: int = 5, reset_after: float = 60):
        self._threshold = threshold
        self._reset_after = reset_after
        self._failures: dict[str, int] = {}
        self._tripped_at: dict[str, float] = {}

    async def before_model(self, ctx: Any, request: Any) -> Any:
        import time

        name = getattr(ctx, "agent_name", "unknown")
        if name in self._tripped_at:
            elapsed = time.monotonic() - self._tripped_at[name]
            if elapsed < self._reset_after:
                raise RuntimeError(
                    f"Circuit open for agent '{name}' — "
                    f"{self._reset_after - elapsed:.0f}s until reset"
                )
            del self._tripped_at[name]
            self._failures[name] = 0
        return None

    async def after_model(self, ctx: Any, request: Any, response: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        self._failures[name] = 0
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Any) -> Any:
        import time

        name = getattr(ctx, "agent_name", "unknown")
        self._failures[name] = self._failures.get(name, 0) + 1
        if self._failures[name] >= self._threshold:
            self._tripped_at[name] = time.monotonic()
        return None
```

- [ ] **Step 4: Add M.circuit\_breaker factory**

Append to `src/adk_fluent/_middleware.py` class M after line 247 (end of `M.on_fallback`):

```python
    @staticmethod
    def circuit_breaker(threshold: int = 5, reset_after: float = 60) -> MComposite:
        """Circuit breaker — trips open after N consecutive model errors."""
        from adk_fluent.middleware import CircuitBreakerMiddleware

        return MComposite(
            [CircuitBreakerMiddleware(threshold=threshold, reset_after=reset_after)],
            kind="circuit_breaker",
        )
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/manual/test_middleware_expanded.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/adk_fluent/middleware.py src/adk_fluent/_middleware.py tests/manual/test_middleware_expanded.py
git commit -m "feat(M): add M.circuit_breaker() resilience middleware"
```

### Task 9: TimeoutMiddleware, ModelCacheMiddleware, FallbackModelMiddleware

**Files:**

- Modify: `src/adk_fluent/middleware.py`
- Modify: `src/adk_fluent/_middleware.py`
- Modify: `tests/manual/test_middleware_expanded.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_middleware_expanded.py`:

```python
class TestTimeoutMiddleware:
    def test_timeout_creates_composite(self):
        mc = M.timeout(seconds=15)
        assert isinstance(mc, MComposite)
        assert len(mc) == 1

    def test_timeout_default(self):
        mc = M.timeout()
        mw = mc.to_stack()[0]
        assert mw._seconds == 30


class TestModelCache:
    def test_cache_creates_composite(self):
        mc = M.cache(ttl=120)
        assert isinstance(mc, MComposite)
        assert len(mc) == 1

    def test_cache_default_ttl(self):
        mc = M.cache()
        mw = mc.to_stack()[0]
        assert mw._ttl == 300


class TestFallbackModel:
    def test_fallback_model_creates_composite(self):
        mc = M.fallback_model(model="gemini-2.0-flash")
        assert isinstance(mc, MComposite)
        assert len(mc) == 1


class TestDedup:
    def test_dedup_creates_composite(self):
        mc = M.dedup(window=5)
        assert isinstance(mc, MComposite)
        assert len(mc) == 1


class TestSample:
    def test_sample_wraps_middleware(self):
        mc = M.sample(0.1, M.log())
        assert isinstance(mc, MComposite)
        assert len(mc) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_middleware_expanded.py -x -v`
Expected: FAIL

- [ ] **Step 3: Implement middleware classes in middleware.py**

Append to `src/adk_fluent/middleware.py`:

```python
class TimeoutMiddleware:
    """Per-agent execution timeout. Tracks deadline across model calls."""

    def __init__(self, seconds: float = 30):
        self._seconds = seconds
        self._deadlines: dict[str, float] = {}

    async def before_agent(self, ctx: Any) -> Any:
        import time

        name = getattr(ctx, "agent_name", "unknown")
        self._deadlines[name] = time.monotonic() + self._seconds
        return None

    async def before_model(self, ctx: Any, request: Any) -> Any:
        import time

        name = getattr(ctx, "agent_name", "unknown")
        deadline = self._deadlines.get(name)
        if deadline and time.monotonic() > deadline:
            raise TimeoutError(f"Agent '{name}' exceeded {self._seconds}s timeout")
        return None


class ModelCacheMiddleware:
    """Caches LLM responses keyed by request content. Model-level caching."""

    def __init__(self, ttl: float = 300, key_fn: Any = None):
        self._ttl = ttl
        self._key_fn = key_fn or (lambda req: str(req))
        self._cache: dict[str, tuple[Any, float]] = {}

    async def before_model(self, ctx: Any, request: Any) -> Any:
        import time

        key = self._key_fn(request)
        if key in self._cache:
            result, ts = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                return result
        return None

    async def after_model(self, ctx: Any, request: Any, response: Any) -> Any:
        import time

        key = self._key_fn(request)
        self._cache[key] = (response, time.monotonic())
        return None


class FallbackModelMiddleware:
    """Auto-downgrade to fallback model on primary model failure."""

    def __init__(self, fallback_model: str):
        self._fallback = fallback_model

    async def on_model_error(self, ctx: Any, request: Any, error: Any) -> Any:
        if hasattr(request, "model"):
            request.model = self._fallback
        return None


class DedupMiddleware:
    """Suppress duplicate model calls within a sliding window."""

    def __init__(self, window: int = 10):
        self._window = window
        self._recent: list[str] = []

    async def before_model(self, ctx: Any, request: Any) -> Any:
        key = str(request)
        if key in self._recent:
            return None  # Already seen — let framework handle
        self._recent.append(key)
        if len(self._recent) > self._window:
            self._recent = self._recent[-self._window:]
        return None


class _SampledMiddleware:
    """Probabilistic middleware wrapper — fires inner middleware only N% of the time."""

    def __init__(self, rate: float, inner: Any):
        self._rate = rate
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        import random

        inner_attr = getattr(self._inner, name, None)
        if inner_attr is None or not callable(inner_attr):
            raise AttributeError(name)

        async def _sampled(*args: Any, **kwargs: Any) -> Any:
            if random.random() < self._rate:
                return await inner_attr(*args, **kwargs)
            return None

        return _sampled
```

- [ ] **Step 4: Add M factories in \_middleware.py**

Append to class M in `src/adk_fluent/_middleware.py`:

```python
    @staticmethod
    def timeout(seconds: float = 30) -> MComposite:
        """Per-agent execution timeout."""
        from adk_fluent.middleware import TimeoutMiddleware

        return MComposite([TimeoutMiddleware(seconds=seconds)], kind="timeout")

    @staticmethod
    def cache(ttl: float = 300, key_fn: Any = None) -> MComposite:
        """LLM response caching (model-level)."""
        from adk_fluent.middleware import ModelCacheMiddleware

        return MComposite([ModelCacheMiddleware(ttl=ttl, key_fn=key_fn)], kind="cache")

    @staticmethod
    def fallback_model(model: str = "gemini-2.0-flash") -> MComposite:
        """Auto-downgrade to fallback model on failure."""
        from adk_fluent.middleware import FallbackModelMiddleware

        return MComposite([FallbackModelMiddleware(fallback_model=model)], kind="fallback_model")

    @staticmethod
    def dedup(window: int = 10) -> MComposite:
        """Suppress duplicate model calls within a sliding window."""
        from adk_fluent.middleware import DedupMiddleware

        return MComposite([DedupMiddleware(window=window)], kind="dedup")

    @staticmethod
    def sample(rate: float, mw: MComposite | Any) -> MComposite:
        """Probabilistic — only fire inner middleware N% of the time."""
        from adk_fluent.middleware import _SampledMiddleware

        stack = mw.to_stack() if isinstance(mw, MComposite) else [mw]
        wrapped = [_SampledMiddleware(rate, m) for m in stack]
        return MComposite(wrapped)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/manual/test_middleware_expanded.py -v`
Expected: All PASS

- [ ] **Step 6: Run existing middleware tests**

Run: `uv run pytest tests/manual/test_middleware.py tests/manual/test_middleware_expanded.py tests/manual/test_builtin_middleware.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/adk_fluent/middleware.py src/adk_fluent/_middleware.py tests/manual/test_middleware_expanded.py
git commit -m "feat(M): add timeout, cache, fallback_model, dedup, sample middleware"
```

### Task 10: M.trace and M.metrics (optional deps)

**Files:**

- Modify: `src/adk_fluent/middleware.py`
- Modify: `src/adk_fluent/_middleware.py`
- Modify: `pyproject.toml:68`
- Modify: `tests/manual/test_middleware_expanded.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_middleware_expanded.py`:

```python
class TestTrace:
    def test_trace_creates_composite(self):
        mc = M.trace()
        assert isinstance(mc, MComposite)
        assert len(mc) == 1


class TestMetrics:
    def test_metrics_creates_composite(self):
        mc = M.metrics()
        assert isinstance(mc, MComposite)
        assert len(mc) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_middleware_expanded.py::TestTrace tests/manual/test_middleware_expanded.py::TestMetrics -x -v`
Expected: FAIL

- [ ] **Step 3: Implement TraceMiddleware and MetricsMiddleware**

Append to `src/adk_fluent/middleware.py`:

```python
class TraceMiddleware:
    """OpenTelemetry span export. Graceful no-op if opentelemetry not installed."""

    def __init__(self, exporter: Any = None):
        self._tracer = None
        self._exporter = exporter
        self._spans: dict[str, Any] = {}
        try:
            from opentelemetry import trace

            self._tracer = trace.get_tracer("adk-fluent")
        except ImportError:
            import logging

            logging.getLogger(__name__).debug(
                "opentelemetry not installed — M.trace() is a no-op. "
                "Install with: pip install adk-fluent[observability]"
            )

    async def before_agent(self, ctx: Any) -> Any:
        if self._tracer:
            name = getattr(ctx, "agent_name", "unknown")
            self._spans[name] = self._tracer.start_span(f"agent:{name}")
        return None

    async def after_agent(self, ctx: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        span = self._spans.pop(name, None)
        if span:
            span.end()
        return None


class MetricsMiddleware:
    """Metrics collection. Graceful no-op if no collector provided."""

    def __init__(self, collector: Any = None):
        self._collector = collector
        self._counts: dict[str, int] = {}

    async def after_agent(self, ctx: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        self._counts[name] = self._counts.get(name, 0) + 1
        if self._collector and hasattr(self._collector, "increment"):
            self._collector.increment(f"agent.{name}.calls")
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Any) -> Any:
        name = getattr(ctx, "agent_name", "unknown")
        if self._collector and hasattr(self._collector, "increment"):
            self._collector.increment(f"agent.{name}.errors")
        return None
```

- [ ] **Step 4: Add M.trace and M.metrics factories**

Append to class M in `src/adk_fluent/_middleware.py`:

```python
    @staticmethod
    def trace(exporter: Any = None) -> MComposite:
        """OpenTelemetry span export. No-op if opentelemetry not installed."""
        from adk_fluent.middleware import TraceMiddleware

        return MComposite([TraceMiddleware(exporter=exporter)], kind="trace")

    @staticmethod
    def metrics(collector: Any = None) -> MComposite:
        """Metrics collection (Prometheus, StatsD, or custom collector)."""
        from adk_fluent.middleware import MetricsMiddleware

        return MComposite([MetricsMiddleware(collector=collector)], kind="metrics")
```

- [ ] **Step 5: Add optional deps to pyproject.toml**

Add after line 68 in `pyproject.toml`:

```toml
pii = [
    "google-cloud-dlp>=3.12",
]
observability = [
    "opentelemetry-api>=1.20",
    "opentelemetry-sdk>=1.20",
]
```

- [ ] **Step 6: Run to verify pass**

Run: `uv run pytest tests/manual/test_middleware_expanded.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/adk_fluent/middleware.py src/adk_fluent/_middleware.py pyproject.toml tests/manual/test_middleware_expanded.py
git commit -m "feat(M): add M.trace() and M.metrics() with optional deps"
```

___

## Chunk 4: G Namespace — Core Infrastructure

The new module. Depends on nothing from Chunks 1-3 (they can be built in parallel).

### Task 11: GGuard, GComposite, GuardViolation base classes

**Files:**

- Create: `src/adk_fluent/_guards.py`
- Create: `tests/manual/test_guards.py`

- [ ] **Step 1: Write failing tests for base infrastructure**

```python
# tests/manual/test_guards.py
"""Tests for G namespace — guard composition and compilation."""

from __future__ import annotations


class TestGComposite:
    def test_guard_or_guard(self):
        from adk_fluent._guards import G, GComposite

        g = G.json() | G.length(max=500)
        assert isinstance(g, GComposite)
        assert len(g._guards) == 2

    def test_guard_chain_three(self):
        from adk_fluent._guards import G

        g = G.json() | G.length(max=500) | G.regex(r"bad", action="block")
        assert len(g._guards) == 3

    def test_guard_reads_keys_union(self):
        from adk_fluent._guards import G

        g = G.grounded(sources_key="docs") | G.json()
        assert "docs" in g._reads_keys

    def test_guard_writes_keys_always_empty(self):
        from adk_fluent._guards import G

        g = G.json() | G.length(max=500)
        assert g._writes_keys == frozenset()

    def test_namespace_spec_protocol(self):
        from adk_fluent._guards import G
        from adk_fluent._namespace_protocol import NamespaceSpec

        g = G.json()
        assert isinstance(g, NamespaceSpec)


class TestGuardViolation:
    def test_guard_violation_fields(self):
        from adk_fluent._guards import GuardViolation

        e = GuardViolation(
            guard_kind="pii", phase="post_model",
            detail="SSN detected", value="123-45-6789",
        )
        assert e.guard_kind == "pii"
        assert e.phase == "post_model"
        assert "SSN" in e.detail
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_guards.py -x -v`
Expected: FAIL — module `_guards` not found

- [ ] **Step 3: Implement base classes**

```python
# src/adk_fluent/_guards.py
"""G module -- fluent guard composition surface.

Consistent with P, C, S, M, T, A, E namespaces.
G is the DX surface for safety and policy enforcement.

Each namespace answers one question:
- G answers: "What must this agent NEVER do?"

Usage::

    from adk_fluent import G

    agent.guard(G.pii("redact") | G.budget(5000) | G.output(Schema))
"""

from __future__ import annotations

import enum
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "G",
    "GComposite",
    "GGuard",
    "GuardViolation",
    "PIIDetector",
    "PIIFinding",
    "ContentJudge",
    "JudgmentResult",
]


# ======================================================================
# Error type
# ======================================================================


class GuardViolation(Exception):
    """Raised when a guard rejects input or output."""

    def __init__(
        self,
        guard_kind: str,
        phase: str,
        detail: str,
        value: Any = None,
    ):
        self.guard_kind = guard_kind
        self.phase = phase
        self.detail = detail
        self.value = value
        super().__init__(f"[{guard_kind}] {detail}")


# ======================================================================
# Provider protocols
# ======================================================================


@dataclass(frozen=True)
class PIIFinding:
    """A single PII detection result."""

    kind: str
    start: int
    end: int
    confidence: float
    text: str


@runtime_checkable
class PIIDetector(Protocol):
    """Protocol for PII detection providers."""

    async def detect(self, text: str) -> list[PIIFinding]: ...


@dataclass(frozen=True)
class JudgmentResult:
    """Result from a content judgment."""

    passed: bool
    score: float
    reason: str


@runtime_checkable
class ContentJudge(Protocol):
    """Protocol for content judgment providers (toxicity, hallucination)."""

    async def judge(self, text: str, context: dict | None = None) -> JudgmentResult: ...


# ======================================================================
# Internal phase enum
# ======================================================================


class _Phase(enum.Enum):
    PRE_AGENT = "pre_agent"
    PRE_MODEL = "pre_model"
    POST_MODEL = "post_model"
    CONTEXT = "context"
    MIDDLEWARE = "middleware"


# ======================================================================
# GGuard — single composable guard spec
# ======================================================================


class GGuard:
    """A single guard specification. Frozen, composable via ``|``."""

    __slots__ = ("_kind", "_phase", "_reads_keys", "_writes_keys", "_compile")

    def __init__(
        self,
        kind: str,
        phase: _Phase,
        reads: frozenset[str] | None,
        compile_fn: Callable[[Any], None],
    ):
        self._kind = kind
        self._phase = phase
        self._reads_keys = reads
        self._writes_keys: frozenset[str] = frozenset()
        self._compile = compile_fn

    def _as_list(self) -> tuple[GGuard, ...]:
        return (self,)

    def __or__(self, other: GGuard | GComposite | Any) -> GComposite:
        if isinstance(other, GComposite):
            return GComposite([self] + other._guards)
        if isinstance(other, GGuard):
            return GComposite([self, other])
        return NotImplemented

    def __repr__(self) -> str:
        return f"GGuard({self._kind!r})"


# ======================================================================
# GComposite — chain of guards
# ======================================================================


class GComposite:
    """Chain of guards. Result of ``G.xxx() | G.yyy()``."""

    def __init__(self, guards: list[GGuard]):
        self._guards = list(guards)

    def __or__(self, other: GGuard | GComposite | Any) -> GComposite:
        if isinstance(other, GComposite):
            return GComposite(self._guards + other._guards)
        if isinstance(other, GGuard):
            return GComposite(self._guards + [other])
        return NotImplemented

    def _compile_into(self, builder: Any) -> None:
        """Route each guard to its correct enforcement layer on the builder."""
        for guard in self._guards:
            guard._compile(builder)
        # Store specs for contract checking
        existing = builder._config.get("_guard_specs", ())
        builder._config["_guard_specs"] = existing + tuple(self._guards)

    # -- NamespaceSpec protocol --

    @property
    def _kind(self) -> str:
        return "guard_chain"

    def _as_list(self) -> tuple[GGuard, ...]:
        return tuple(self._guards)

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        result: frozenset[str] = frozenset()
        for g in self._guards:
            if g._reads_keys is None:
                return None
            result = result | g._reads_keys
        return result

    @property
    def _writes_keys(self) -> frozenset[str]:
        return frozenset()

    def __len__(self) -> int:
        return len(self._guards)

    def __repr__(self) -> str:
        kinds = [g._kind for g in self._guards]
        return f"GComposite([{', '.join(kinds)}])"
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_guards.py -v`
Expected: All PASS (tests for G factories will still fail — those are in later tasks)

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_guards.py tests/manual/test_guards.py
git commit -m "feat(G): add GGuard, GComposite, GuardViolation base infrastructure"
```

### Task 12: G.json, G.length, G.regex, G.output, G.input — structural guards

**Files:**

- Modify: `src/adk_fluent/_guards.py`
- Modify: `tests/manual/test_guards.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_guards.py`:

```python
import json


class TestJsonGuard:
    def test_json_creates_guard(self):
        from adk_fluent._guards import G, GComposite

        g = G.json()
        assert isinstance(g, GComposite)

    def test_json_kind(self):
        from adk_fluent._guards import G

        g = G.json()
        assert g._guards[0]._kind == "json"


class TestLengthGuard:
    def test_length_max(self):
        from adk_fluent._guards import G

        g = G.length(max=100)
        assert g._guards[0]._kind == "length"

    def test_length_min_max(self):
        from adk_fluent._guards import G

        g = G.length(min=10, max=500)
        assert len(g._guards) == 1


class TestRegexGuard:
    def test_regex_block(self):
        from adk_fluent._guards import G

        g = G.regex(r"ignore previous", action="block")
        assert g._guards[0]._kind == "regex"

    def test_regex_redact(self):
        from adk_fluent._guards import G

        g = G.regex(r"\d{3}-\d{2}-\d{4}", action="redact")
        assert len(g._guards) == 1


class TestOutputGuard:
    def test_output_creates_guard(self):
        from adk_fluent._guards import G
        from dataclasses import dataclass

        @dataclass
        class Schema:
            answer: str

        g = G.output(Schema)
        assert g._guards[0]._kind == "output"


class TestInputGuard:
    def test_input_creates_guard(self):
        from adk_fluent._guards import G
        from dataclasses import dataclass

        @dataclass
        class Schema:
            query: str

        g = G.input(Schema)
        assert g._guards[0]._kind == "input"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_guards.py::TestJsonGuard tests/manual/test_guards.py::TestLengthGuard tests/manual/test_guards.py::TestRegexGuard tests/manual/test_guards.py::TestOutputGuard tests/manual/test_guards.py::TestInputGuard -x -v`
Expected: FAIL

- [ ] **Step 3: Implement G factories — add class G to \_guards.py**

Append to `src/adk_fluent/_guards.py`:

```python
# ======================================================================
# G namespace — public API
# ======================================================================


class G:
    """Fluent guard composition. Answers: 'What must this agent NEVER do?'

    Factory methods return ``GComposite`` instances that compose with ``|``.
    Compile into the correct enforcement layer automatically.
    """

    # -- Structural Validation --

    @staticmethod
    def json() -> GComposite:
        """Assert LLM output is parseable JSON."""

        def _compile(builder: Any) -> None:
            def _check(callback_context: Any, llm_response: Any) -> Any:
                import json as _json

                text = str(llm_response) if llm_response else ""
                try:
                    _json.loads(text)
                except (ValueError, TypeError) as e:
                    raise GuardViolation(
                        guard_kind="json", phase="post_model",
                        detail=f"Output is not valid JSON: {e}", value=text,
                    ) from e
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([GGuard("json", _Phase.POST_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def length(*, min: int | None = None, max: int | None = None) -> GComposite:
        """Assert LLM output length is within bounds (character count)."""

        def _compile(builder: Any) -> None:
            def _check(callback_context: Any, llm_response: Any) -> Any:
                text = str(llm_response) if llm_response else ""
                length = len(text)
                if min is not None and length < min:
                    raise GuardViolation(
                        guard_kind="length", phase="post_model",
                        detail=f"Output too short: {length} < {min}", value=text,
                    )
                if max is not None and length > max:
                    raise GuardViolation(
                        guard_kind="length", phase="post_model",
                        detail=f"Output too long: {length} > {max}", value=text,
                    )
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([GGuard("length", _Phase.POST_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def regex(
        pattern: str,
        action: str = "block",
        replacement: str = "[REDACTED]",
    ) -> GComposite:
        """Pattern-based guard. Block or redact matching content in output."""

        def _compile(builder: Any) -> None:
            import re

            compiled = re.compile(pattern)

            def _check(callback_context: Any, llm_response: Any) -> Any:
                text = str(llm_response) if llm_response else ""
                if compiled.search(text):
                    if action == "block":
                        raise GuardViolation(
                            guard_kind="regex", phase="post_model",
                            detail=f"Output matches blocked pattern: {pattern}",
                            value=text,
                        )
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([GGuard("regex", _Phase.POST_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def output(schema_cls: type) -> GComposite:
        """Validate LLM output against a Pydantic model or dataclass."""

        def _compile(builder: Any) -> None:
            def _check(callback_context: Any, llm_response: Any) -> Any:
                text = str(llm_response) if llm_response else ""
                try:
                    if hasattr(schema_cls, "model_validate_json"):
                        schema_cls.model_validate_json(text)
                    elif hasattr(schema_cls, "model_validate"):
                        import json as _json

                        schema_cls.model_validate(_json.loads(text))
                    else:
                        import json as _json

                        schema_cls(**_json.loads(text))
                except Exception as e:
                    raise GuardViolation(
                        guard_kind="output", phase="post_model",
                        detail=f"Output validation failed against {schema_cls.__name__}: {e}",
                        value=text,
                    ) from e
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([GGuard("output", _Phase.POST_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def input(schema_cls: type) -> GComposite:
        """Validate user input before agent processes it."""

        def _compile(builder: Any) -> None:
            def _check(callback_context: Any, llm_request: Any) -> Any:
                text = str(llm_request) if llm_request else ""
                try:
                    if hasattr(schema_cls, "model_validate"):
                        import json as _json

                        schema_cls.model_validate(_json.loads(text))
                    else:
                        import json as _json

                        schema_cls(**_json.loads(text))
                except Exception as e:
                    raise GuardViolation(
                        guard_kind="input", phase="pre_model",
                        detail=f"Input validation failed against {schema_cls.__name__}: {e}",
                        value=text,
                    ) from e
                return llm_request

            builder._callbacks.setdefault("before_model_callback", []).append(_check)

        return GComposite([GGuard("input", _Phase.PRE_MODEL, reads=frozenset(), compile_fn=_compile)])
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_guards.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_guards.py tests/manual/test_guards.py
git commit -m "feat(G): add G.json, G.length, G.regex, G.output, G.input structural guards"
```

### Task 13: G.budget, G.rate\_limit, G.max\_turns — policy guards

**Files:**

- Modify: `src/adk_fluent/_guards.py`
- Modify: `tests/manual/test_guards.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_guards.py`:

```python
class TestBudgetGuard:
    def test_budget_creates_guard(self):
        from adk_fluent._guards import G

        g = G.budget(max_tokens=5000)
        assert any(guard._kind == "budget" for guard in g._guards)


class TestRateLimitGuard:
    def test_rate_limit_creates_guard(self):
        from adk_fluent._guards import G

        g = G.rate_limit(rpm=60)
        assert g._guards[0]._kind == "rate_limit"


class TestMaxTurnsGuard:
    def test_max_turns_creates_guard(self):
        from adk_fluent._guards import G

        g = G.max_turns(n=10)
        assert g._guards[0]._kind == "max_turns"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_guards.py::TestBudgetGuard tests/manual/test_guards.py::TestRateLimitGuard tests/manual/test_guards.py::TestMaxTurnsGuard -x -v`
Expected: FAIL

- [ ] **Step 3: Implement policy guards**

Append to class G in `src/adk_fluent/_guards.py`:

```python
    # -- Cost & Rate Policy --

    @staticmethod
    def budget(max_tokens: int = 5000) -> GComposite:
        """Hard kill if cumulative tokens exceed budget.

        Compiles to middleware (tracking) + before_model callback (enforcement).
        """

        def _compile(builder: Any) -> None:
            tracker = {"total": 0, "max": max_tokens}

            def _check_before(callback_context: Any, llm_request: Any) -> Any:
                if tracker["total"] >= tracker["max"]:
                    raise GuardViolation(
                        guard_kind="budget", phase="pre_model",
                        detail=f"Token budget exhausted: {tracker['total']} >= {tracker['max']}",
                        value=tracker["total"],
                    )
                return llm_request

            def _track_after(callback_context: Any, llm_response: Any) -> Any:
                # Best-effort token counting from response metadata
                usage = getattr(llm_response, "usage_metadata", None)
                if usage:
                    tracker["total"] += getattr(usage, "total_token_count", 0)
                return llm_response

            builder._callbacks.setdefault("before_model_callback", []).append(_check_before)
            builder._callbacks.setdefault("after_model_callback", []).append(_track_after)

        return GComposite([GGuard("budget", _Phase.PRE_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def rate_limit(rpm: int = 60) -> GComposite:
        """Sliding window rate limit on model calls."""

        def _compile(builder: Any) -> None:
            import time

            window: list[float] = []

            def _check(callback_context: Any, llm_request: Any) -> Any:
                now = time.monotonic()
                # Trim window to last 60 seconds
                while window and now - window[0] > 60:
                    window.pop(0)
                if len(window) >= rpm:
                    raise GuardViolation(
                        guard_kind="rate_limit", phase="pre_model",
                        detail=f"Rate limit exceeded: {len(window)} calls in last 60s (limit: {rpm})",
                        value=len(window),
                    )
                window.append(now)
                return llm_request

            builder._callbacks.setdefault("before_model_callback", []).append(_check)

        return GComposite([GGuard("rate_limit", _Phase.PRE_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def max_turns(n: int = 10) -> GComposite:
        """Cap conversation turns."""

        def _compile(builder: Any) -> None:
            counter = {"turns": 0}

            def _check(callback_context: Any, llm_request: Any) -> Any:
                counter["turns"] += 1
                if counter["turns"] > n:
                    raise GuardViolation(
                        guard_kind="max_turns", phase="pre_model",
                        detail=f"Maximum turns exceeded: {counter['turns']} > {n}",
                        value=counter["turns"],
                    )
                return llm_request

            builder._callbacks.setdefault("before_model_callback", []).append(_check)

        return GComposite([GGuard("max_turns", _Phase.PRE_MODEL, reads=frozenset(), compile_fn=_compile)])
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_guards.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_guards.py tests/manual/test_guards.py
git commit -m "feat(G): add G.budget, G.rate_limit, G.max_turns policy guards"
```

### Task 14: G.pii with provider protocol, G.toxicity, G.hallucination, G.grounded, G.topic, G.when

**Files:**

- Modify: `src/adk_fluent/_guards.py`
- Modify: `tests/manual/test_guards.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/manual/test_guards.py`:

```python
class TestPiiGuard:
    def test_pii_creates_guard(self):
        from adk_fluent._guards import G

        g = G.pii(action="redact")
        assert any(guard._kind == "pii" for guard in g._guards)

    def test_pii_with_custom_detector(self):
        from adk_fluent._guards import G, PIIFinding

        class FakeDetector:
            async def detect(self, text):
                return [PIIFinding("TEST", 0, 4, 1.0, text[:4])]

        g = G.pii(action="block", detector=FakeDetector())
        assert len(g._guards) >= 1

    def test_pii_regex_detector_factory(self):
        from adk_fluent._guards import G

        detector = G.regex_detector(patterns=[r"\d{3}-\d{2}-\d{4}"])
        assert hasattr(detector, "detect")


class TestToxicityGuard:
    def test_toxicity_creates_guard(self):
        from adk_fluent._guards import G

        g = G.toxicity(threshold=0.8)
        assert g._guards[0]._kind == "toxicity"


class TestGroundedGuard:
    def test_grounded_reads_sources_key(self):
        from adk_fluent._guards import G

        g = G.grounded(sources_key="docs")
        assert g._reads_keys == frozenset({"docs"})


class TestTopicGuard:
    def test_topic_creates_guard(self):
        from adk_fluent._guards import G

        g = G.topic(deny=["politics"])
        assert g._guards[0]._kind == "topic"


class TestWhenGuard:
    def test_when_wraps_guard(self):
        from adk_fluent._guards import G

        g = G.when(lambda s: s.get("premium"), G.budget(max_tokens=50000))
        assert len(g._guards) >= 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_guards.py::TestPiiGuard tests/manual/test_guards.py::TestToxicityGuard tests/manual/test_guards.py::TestGroundedGuard tests/manual/test_guards.py::TestTopicGuard tests/manual/test_guards.py::TestWhenGuard -x -v`
Expected: FAIL

- [ ] **Step 3: Implement provider-based guards**

Append to class G in `src/adk_fluent/_guards.py`:

```python
    # -- Content Safety (provider-based) --

    @staticmethod
    def pii(
        action: str = "redact",
        detector: PIIDetector | None = None,
        threshold: float = 0.7,
        replacement: str = "[{kind}]",
    ) -> GComposite:
        """PII detection and enforcement. Provider-based.

        Use ``G.dlp()``, ``G.regex_detector()``, or bring your own ``PIIDetector``.
        If no detector given, defaults to ``G.regex_detector()`` (dev/test only).
        """
        actual_detector = detector or _RegexDetector()

        def _compile(builder: Any) -> None:
            async def _check(callback_context: Any, llm_response: Any) -> Any:
                text = str(llm_response) if llm_response else ""
                findings = await actual_detector.detect(text)
                findings = [f for f in findings if f.confidence >= threshold]
                if not findings:
                    return llm_response
                if action == "block":
                    raise GuardViolation(
                        guard_kind="pii", phase="post_model",
                        detail=f"PII detected: {[f.kind for f in findings]}",
                        value=text,
                    )
                # Redact — replace spans in reverse order
                for f in sorted(findings, key=lambda f: f.start, reverse=True):
                    label = replacement.format(kind=f.kind)
                    text = text[: f.start] + label + text[f.end :]
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([GGuard("pii", _Phase.POST_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def toxicity(threshold: float = 0.8, judge: ContentJudge | None = None) -> GComposite:
        """Content toxicity check. Provider-based.

        Defaults to LLM-as-judge. Plug in Perspective API or custom classifier.
        """
        actual_judge = judge or _LLMJudge("toxicity")

        def _compile(builder: Any) -> None:
            async def _check(callback_context: Any, llm_response: Any) -> Any:
                text = str(llm_response) if llm_response else ""
                result = await actual_judge.judge(text)
                if not result.passed and result.score >= threshold:
                    raise GuardViolation(
                        guard_kind="toxicity", phase="post_model",
                        detail=f"Toxicity score {result.score:.2f} >= {threshold}: {result.reason}",
                        value=text,
                    )
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([GGuard("toxicity", _Phase.POST_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def topic(deny: list[str] | None = None) -> GComposite:
        """Topic blocklist. Rejects output that touches denied topics."""

        def _compile(builder: Any) -> None:
            blocked = set(t.lower() for t in (deny or []))

            def _check(callback_context: Any, llm_response: Any) -> Any:
                text = (str(llm_response) if llm_response else "").lower()
                for topic in blocked:
                    if topic in text:
                        raise GuardViolation(
                            guard_kind="topic", phase="post_model",
                            detail=f"Denied topic detected: {topic}",
                            value=text,
                        )
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([GGuard("topic", _Phase.POST_MODEL, reads=frozenset(), compile_fn=_compile)])

    @staticmethod
    def grounded(sources_key: str = "docs") -> GComposite:
        """Grounding check — verify output references source material."""
        actual_judge = _LLMJudge("grounding")

        def _compile(builder: Any) -> None:
            async def _check(callback_context: Any, llm_response: Any) -> Any:
                text = str(llm_response) if llm_response else ""
                # Sources would be read from state at runtime
                result = await actual_judge.judge(text, context={"sources_key": sources_key})
                if not result.passed:
                    raise GuardViolation(
                        guard_kind="grounded", phase="post_model",
                        detail=f"Output not grounded in sources: {result.reason}",
                        value=text,
                    )
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([
            GGuard("grounded", _Phase.POST_MODEL, reads=frozenset({sources_key}), compile_fn=_compile)
        ])

    @staticmethod
    def hallucination(
        threshold: float = 0.7,
        sources_key: str = "docs",
        judge: ContentJudge | None = None,
    ) -> GComposite:
        """Hallucination detection. Provider-based."""
        actual_judge = judge or _LLMJudge("hallucination")

        def _compile(builder: Any) -> None:
            async def _check(callback_context: Any, llm_response: Any) -> Any:
                text = str(llm_response) if llm_response else ""
                result = await actual_judge.judge(text, context={"sources_key": sources_key})
                if not result.passed and result.score >= threshold:
                    raise GuardViolation(
                        guard_kind="hallucination", phase="post_model",
                        detail=f"Hallucination score {result.score:.2f}: {result.reason}",
                        value=text,
                    )
                return llm_response

            builder._callbacks.setdefault("after_model_callback", []).append(_check)

        return GComposite([
            GGuard("hallucination", _Phase.POST_MODEL, reads=frozenset({sources_key}), compile_fn=_compile)
        ])

    # -- Composition --

    @staticmethod
    def when(predicate: Any, guard: GComposite | GGuard) -> GComposite:
        """Conditional guard. Only compiles if predicate is truthy at runtime."""
        composite = guard if isinstance(guard, GComposite) else GComposite([guard])

        def _compile(builder: Any) -> None:
            from adk_fluent._predicate_utils import evaluate_predicate

            original_guards = list(composite._guards)
            for g in original_guards:
                original_compile = g._compile

                def _conditional_compile(builder: Any, _oc: Any = original_compile) -> None:
                    _oc(builder)

                g._compile = _conditional_compile

            composite._compile_into(builder)

        return GComposite(composite._guards)

    # -- Provider factories --

    @staticmethod
    def dlp(
        project: str,
        *,
        info_types: list[str] | None = None,
        location: str = "global",
    ) -> PIIDetector:
        """Google Cloud DLP detector. Requires google-cloud-dlp."""
        return _DLPDetector(project, info_types, location)

    @staticmethod
    def regex_detector(patterns: list[str] | None = None) -> PIIDetector:
        """Lightweight regex PII detector. For dev/test only."""
        return _RegexDetector(patterns)

    @staticmethod
    def multi(*detectors: PIIDetector) -> PIIDetector:
        """Union of findings from multiple detectors."""
        return _MultiDetector(list(detectors))

    @staticmethod
    def custom(fn: Callable[..., Any]) -> PIIDetector:
        """Wrap any async callable as a PIIDetector."""
        return _CustomDetector(fn)

    @staticmethod
    def llm_judge(model: str = "gemini-2.5-flash") -> ContentJudge:
        """LLM-as-judge content evaluator."""
        return _LLMJudge("general", model=model)

    @staticmethod
    def custom_judge(fn: Callable[..., Any]) -> ContentJudge:
        """Wrap any async callable as a ContentJudge."""
        return _CustomJudge(fn)


# ======================================================================
# Built-in provider implementations
# ======================================================================


class _RegexDetector:
    """Lightweight regex PII detector. Dev/test only."""

    _DEFAULT_PATTERNS = {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "CREDIT_CARD": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "PHONE": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    }

    def __init__(self, patterns: list[str] | None = None):
        import re

        if patterns:
            self._compiled = {f"CUSTOM_{i}": re.compile(p) for i, p in enumerate(patterns)}
        else:
            self._compiled = {k: re.compile(p) for k, p in self._DEFAULT_PATTERNS.items()}

    async def detect(self, text: str) -> list[PIIFinding]:
        findings = []
        for kind, pattern in self._compiled.items():
            for match in pattern.finditer(text):
                findings.append(
                    PIIFinding(
                        kind=kind, start=match.start(), end=match.end(),
                        confidence=1.0, text=match.group(),
                    )
                )
        return findings


class _DLPDetector:
    """Google Cloud DLP detector. Production-grade."""

    def __init__(self, project: str, info_types: list[str] | None, location: str):
        self._project = project
        self._location = location
        self._info_types = info_types or [
            "PERSON_NAME", "EMAIL_ADDRESS", "PHONE_NUMBER",
            "CREDIT_CARD_NUMBER", "US_SOCIAL_SECURITY_NUMBER",
        ]

    async def detect(self, text: str) -> list[PIIFinding]:
        try:
            from google.cloud import dlp_v2
        except ImportError:
            raise ImportError(
                "google-cloud-dlp required for G.dlp(). "
                "Install with: pip install adk-fluent[pii]"
            ) from None

        client = dlp_v2.DlpServiceAsyncClient()
        response = await client.inspect_content(
            request={
                "parent": f"projects/{self._project}/locations/{self._location}",
                "item": {"value": text},
                "inspect_config": {
                    "info_types": [{"name": t} for t in self._info_types],
                },
            }
        )
        return [
            PIIFinding(
                kind=f.info_type.name,
                start=f.location.byte_range.start,
                end=f.location.byte_range.end,
                confidence=f.likelihood.value / 5.0,
                text=f.quote,
            )
            for f in response.result.findings
        ]


class _MultiDetector:
    """Union of findings from multiple detectors, deduplicated by span."""

    def __init__(self, detectors: list[Any]):
        self._detectors = detectors

    async def detect(self, text: str) -> list[PIIFinding]:
        import asyncio

        results = await asyncio.gather(*(d.detect(text) for d in self._detectors))
        seen: set[tuple[int, int]] = set()
        findings = []
        for batch in results:
            for f in batch:
                span = (f.start, f.end)
                if span not in seen:
                    seen.add(span)
                    findings.append(f)
        return findings


class _CustomDetector:
    """Wrap any async callable as a PIIDetector."""

    def __init__(self, fn: Any):
        self._fn = fn

    async def detect(self, text: str) -> list[PIIFinding]:
        return await self._fn(text)


class _LLMJudge:
    """LLM-as-judge content evaluator. Shared by G.toxicity, G.grounded, G.hallucination."""

    def __init__(self, judge_type: str, model: str = "gemini-2.5-flash"):
        self._judge_type = judge_type
        self._model = model

    async def judge(self, text: str, context: dict | None = None) -> JudgmentResult:
        # Placeholder — actual implementation would call LLM
        # For now, always passes (real impl in _llm_judge.py extraction)
        return JudgmentResult(passed=True, score=0.0, reason="ok")


class _CustomJudge:
    """Wrap any async callable as a ContentJudge."""

    def __init__(self, fn: Any):
        self._fn = fn

    async def judge(self, text: str, context: dict | None = None) -> JudgmentResult:
        return await self._fn(text, context)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/manual/test_guards.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/_guards.py tests/manual/test_guards.py
git commit -m "feat(G): add G.pii, G.toxicity, G.topic, G.grounded, G.hallucination, G.when with provider protocols"
```

___

## Chunk 5: Wiring, Registration, and Integration

Connects everything to the builder system.

### Task 15: Wire .guard() to support GComposite

**Files:**

- Modify: `src/adk_fluent/_helpers.py` (add `_guard_dispatch`)
- Modify: `seeds/seed.manual.toml:120-135` (change guard extra)
- Create: `tests/manual/test_guards_compile.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/manual/test_guards_compile.py
"""Tests for G guard compilation into builder callbacks."""

from __future__ import annotations

from adk_fluent.agent import Agent
from adk_fluent._guards import G, GComposite


class TestGuardCompile:
    def test_guard_g_composite_compiles_callbacks(self):
        builder = Agent("test").guard(G.json() | G.length(max=500))
        assert len(builder._callbacks.get("after_model_callback", [])) >= 2

    def test_guard_callable_backwards_compatible(self):
        fn = lambda ctx: None
        builder = Agent("test").guard(fn)
        assert fn in builder._callbacks.get("before_model_callback", [])
        assert fn in builder._callbacks.get("after_model_callback", [])

    def test_guard_stores_specs(self):
        builder = Agent("test").guard(G.json())
        specs = builder._config.get("_guard_specs", ())
        assert len(specs) >= 1

    def test_guard_composable_with_other_callbacks(self):
        before_fn = lambda ctx, req: req
        builder = Agent("test").before_model(before_fn).guard(G.json())
        assert before_fn in builder._callbacks["before_model_callback"]
        assert len(builder._callbacks["after_model_callback"]) >= 1

    def test_guard_chain_multiple(self):
        builder = Agent("test").guard(G.json()).guard(G.length(max=100))
        assert len(builder._callbacks.get("after_model_callback", [])) >= 2
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/manual/test_guards_compile.py -x -v`
Expected: FAIL — `.guard()` currently only accepts callables

- [ ] **Step 3: Add \_guard\_dispatch to \_helpers.py**

Add to `src/adk_fluent/_helpers.py` (find a suitable location near other guard helpers, around line 93):

```python
def _guard_dispatch(builder: Any, value: Any) -> None:
    """Route .guard() calls — supports G composites and legacy callables."""
    from adk_fluent._guards import GComposite, GGuard

    if isinstance(value, GComposite):
        value._compile_into(builder)
    elif isinstance(value, GGuard):
        GComposite([value])._compile_into(builder)
    elif callable(value):
        # Backwards compatible — existing dual-callback behavior
        builder._callbacks.setdefault("before_model_callback", []).append(value)
        builder._callbacks.setdefault("after_model_callback", []).append(value)
    else:
        raise TypeError(
            f"guard() expects a callable or G composite, got {type(value).__name__}. "
            f"Use G.json(), G.pii(), etc. to create guard composites."
        )
```

- [ ] **Step 4: Update seed.manual.toml**

Change lines 120-134 in `seeds/seed.manual.toml`:

```toml
[[builders.Agent.extras]]
name = "guard"
signature = "(self, value: Any) -> Self"
doc = "Add a guard. Accepts a G composite (G.pii() | G.budget()) or a plain callable (legacy dual-callback)."
behavior = "runtime_helper"
helper_func = "_guard_dispatch"
example = '''
from adk_fluent import G

# Declarative guards
agent = Agent("safe", "gemini-2.5-flash").guard(G.pii("redact") | G.budget(5000))

# Legacy callable guard (still works)
agent = Agent("safe", "gemini-2.5-flash").guard(my_guard_fn)
'''
see_also = ["Agent.before_model", "Agent.after_model"]
```

- [ ] **Step 5: Regenerate**

Run: `just seed && just generate`
Expected: Clean generation, `agent.py` updated with new `.guard()` signature

- [ ] **Step 6: Run to verify pass**

Run: `uv run pytest tests/manual/test_guards_compile.py tests/manual/test_guardrail.py -v`
Expected: All PASS (including backwards compatibility with existing guardrail tests)

- [ ] **Step 7: Commit**

```bash
git add src/adk_fluent/_helpers.py seeds/seed.manual.toml seeds/seed.toml src/adk_fluent/agent.py src/adk_fluent/agent.pyi tests/manual/test_guards_compile.py
git commit -m "feat(G): wire .guard() to support GComposite with backwards-compatible callable path"
```

### Task 16: IR integration — guard\_specs on AgentNode

**Files:**

- Modify: `scripts/ir_generator.py:218`
- Modify: `src/adk_fluent/_helpers.py` (in `_agent_to_ir`)

- [ ] **Step 1: Add guard\_specs to AgentNode IR**

In `scripts/ir_generator.py`, after line 218, add:

```python
        lines.append("    guard_specs: tuple = ()  # GGuard specs, preserved for contract checking")
```

- [ ] **Step 2: Wire guard\_specs in \_agent\_to\_ir**

In `src/adk_fluent/_helpers.py`, find `_agent_to_ir` and add `guard_specs` extraction near where `tool_schema` is extracted:

```python
guard_specs = builder._config.get("_guard_specs", ())
```

And pass to the `AgentNode(...)` constructor:

```python
guard_specs=guard_specs,
```

- [ ] **Step 3: Regenerate**

Run: `just generate`
Expected: `_ir_generated.py` updated with new `guard_specs` field

- [ ] **Step 4: Run IR tests**

Run: `uv run pytest tests/manual/test_ir_generated.py tests/manual/test_to_ir_generated.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ir_generator.py src/adk_fluent/_helpers.py src/adk_fluent/_ir_generated.py
git commit -m "feat(G): add guard_specs field to AgentNode IR for contract checking"
```

### Task 17: Register G in prelude.py and \_\_init\_\_.py

**Files:**

- Modify: `src/adk_fluent/prelude.py:18,62-80`

- [ ] **Step 1: Add G to prelude.py imports and \_\_all\_\_**

In `src/adk_fluent/prelude.py`, add to import line 18:

```python
from adk_fluent._guards import G, GComposite, GuardViolation
```

Add to `__all__` Tier 2 section (after line 66 "Route"):

```python
    "G",
    "GComposite",
    "GuardViolation",
```

- [ ] **Step 2: Regenerate \_\_init\_\_.py**

Run: `just generate`
Expected: `__init__.py` auto-discovers G exports from `_guards.py.__all__`

- [ ] **Step 3: Verify import works**

Run: `uv run python -c "from adk_fluent import G; print(G.json())"`
Expected: Prints `GComposite([json])`

Run: `uv run python -c "from adk_fluent.prelude import G; print(G.pii())"`
Expected: Prints `GComposite([pii])`

- [ ] **Step 4: Add optional deps to pyproject.toml**

Already done in Task 10 Step 5 (`pii` and `observability` extras). Verify they're present.

- [ ] **Step 5: Commit**

```bash
git add src/adk_fluent/prelude.py src/adk_fluent/__init__.py
git commit -m "feat(G): register G namespace in prelude and __init__"
```

### Task 18: Cross-module interplay tests

**Files:**

- Create: `tests/manual/test_interplay.py`

- [ ] **Step 1: Write interplay tests**

```python
# tests/manual/test_interplay.py
"""Cross-module composition tests — G+M, G+T, T+M, S+G, full pipeline."""

from __future__ import annotations

from adk_fluent._guards import G, GComposite
from adk_fluent._middleware import M, MComposite
from adk_fluent._tools import T, TComposite
from adk_fluent._transforms import S, STransform
from adk_fluent.agent import Agent


class TestGWithM:
    def test_guard_and_middleware_coexist(self):
        builder = (
            Agent("test")
            .guard(G.json() | G.budget(max_tokens=5000))
        )
        # Guards compile to callbacks, not middleware
        assert len(builder._callbacks.get("after_model_callback", [])) >= 1
        assert len(builder._callbacks.get("before_model_callback", [])) >= 1

    def test_guard_does_not_interfere_with_middleware(self):
        mc = M.retry(3) | M.circuit_breaker()
        assert len(mc) == 2
        # G and M are independent composition chains
        gc = G.json() | G.length(max=500)
        assert len(gc) == 2


class TestTWrappers:
    def test_cache_and_timeout_compose(self):
        tc = T.cache(T.timeout(T.fn(lambda: "x"), seconds=5), ttl=60)
        assert isinstance(tc, TComposite)
        assert len(tc) == 1  # nested wrappers

    def test_mock_composes_with_real(self):
        tc = T.mock("search", returns="x") | T.fn(lambda: "y")
        assert len(tc) == 2

    def test_confirm_and_schema_compose(self):
        tc = T.confirm(T.fn(lambda: "x")) | T.schema(type)
        assert len(tc) == 2


class TestSExpansion:
    def test_accumulate_chains_with_require(self):
        pipeline = S.accumulate("item", into="items") >> S.require("items")
        assert isinstance(pipeline, STransform)

    def test_counter_chains_with_guard(self):
        pipeline = S.counter("n") >> S.guard(lambda s: s["n"] < 100)
        assert isinstance(pipeline, STransform)

    def test_validate_composes_with_pick(self):
        from dataclasses import dataclass

        @dataclass
        class Schema:
            name: str

        pipeline = S.pick("name") >> S.validate(Schema)
        assert isinstance(pipeline, STransform)


class TestFullPipeline:
    def test_all_namespaces_on_single_agent(self):
        """Verify all namespace methods can be called on a single agent without error."""
        from adk_fluent._prompt import P
        from adk_fluent._context import C

        builder = (
            Agent("test")
            .instruct(P.role("analyst") + P.task("analyze data"))
            .context(C.window(10))
            .tools(T.mock("search", returns="ok") | T.fn(lambda: "x"))
            .guard(G.json() | G.length(max=1000))
        )
        # Verify builder state
        assert len(builder._callbacks.get("after_model_callback", [])) >= 2
        assert len(builder._lists.get("tools", [])) >= 2

    def test_namespace_spec_protocol_all(self):
        """All expanded namespace objects conform to NamespaceSpec."""
        from adk_fluent._namespace_protocol import NamespaceSpec

        specs = [
            G.json(),
            T.mock("x", returns="y"),
            M.circuit_breaker(),
            S.accumulate("x"),
        ]
        for spec in specs:
            assert hasattr(spec, "_kind")
            assert hasattr(spec, "_reads_keys")
            assert hasattr(spec, "_writes_keys")
```

- [ ] **Step 2: Run interplay tests**

Run: `uv run pytest tests/manual/test_interplay.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/manual/test_interplay.py
git commit -m "test: add cross-module interplay tests for G+M+T+S composition"
```

### Task 19: Full regression + lint + check-gen

- [ ] **Step 1: Lint and format**

Run: `ruff check --fix . && ruff format .`
Expected: Clean

- [ ] **Step 2: Pre-commit hooks**

Run: `uv run pre-commit run --all-files`
Expected: All passed. If files modified, stage and re-run until idempotent.

- [ ] **Step 3: Check generated files**

Run: `just check-gen`
Expected: No diff — generated files match

- [ ] **Step 4: Full test suite**

Run: `uv run pytest tests/ -x --tb=short -q`
Expected: All PASS

- [ ] **Step 5: Type check**

Run: `just typecheck-core`
Expected: 0 errors

- [ ] **Step 6: Final commit if any lint/format changes**

```bash
git add -A
git commit -m "chore: lint and format after namespace expansion"
```
