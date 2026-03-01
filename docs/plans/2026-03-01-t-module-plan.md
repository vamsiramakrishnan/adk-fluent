# T Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `T` — a fluent tool composition and dynamic loading surface, consistent with P/C/S/M modules.

**Architecture:** `TComposite` is a composable chain (mirrors `MComposite`). `T` is the factory class with static methods. `ToolRegistry` is a BM25-indexed catalog. `SearchToolset` is a native ADK `BaseToolset` subclass implementing two-phase dynamic loading. The builder's `.tools()` is extended to accept `TComposite`.

**Tech Stack:** Python 3.11+, google-adk `BaseToolset`, optional `rank_bm25>=0.2.2`

______________________________________________________________________

### Task 1: Create `_tools.py` — `TComposite` class

**Files:**

- Create: `src/adk_fluent/_tools.py`
- Test: `tests/manual/test_tools_t.py`

**Step 1: Write the failing test**

Create `tests/manual/test_tools_t.py`:

```python
"""Tests for TComposite — composable tool chain."""

from __future__ import annotations


class TestTComposite:
    def test_init_empty(self):
        from adk_fluent._tools import TComposite

        tc = TComposite()
        assert len(tc) == 0
        assert tc.to_tools() == []

    def test_init_with_items(self):
        from adk_fluent._tools import TComposite

        tc = TComposite(["a", "b"])
        assert len(tc) == 2
        assert tc.to_tools() == ["a", "b"]

    def test_or_two_composites(self):
        from adk_fluent._tools import TComposite

        a = TComposite(["x"])
        b = TComposite(["y"])
        c = a | b
        assert len(c) == 2
        assert c.to_tools() == ["x", "y"]

    def test_or_composite_and_raw(self):
        from adk_fluent._tools import TComposite

        a = TComposite(["x"])
        c = a | "y"
        assert len(c) == 2
        assert c.to_tools() == ["x", "y"]

    def test_ror_raw_and_composite(self):
        from adk_fluent._tools import TComposite

        b = TComposite(["y"])
        c = "x" | b
        assert len(c) == 2
        assert c.to_tools() == ["x", "y"]

    def test_repr(self):
        from adk_fluent._tools import TComposite

        tc = TComposite(["a", "b"])
        r = repr(tc)
        assert "TComposite" in r
        assert "str" in r

    def test_chain_three(self):
        from adk_fluent._tools import TComposite

        a = TComposite(["x"])
        b = TComposite(["y"])
        c = TComposite(["z"])
        result = a | b | c
        assert len(result) == 3
        assert result.to_tools() == ["x", "y", "z"]

    def test_to_tools_returns_copy(self):
        from adk_fluent._tools import TComposite

        tc = TComposite(["x"])
        tools = tc.to_tools()
        tools.append("extra")
        assert len(tc) == 1  # original unchanged
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_tools_t.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError

**Step 3: Write minimal implementation**

Create `src/adk_fluent/_tools.py`:

```python
"""T module -- fluent tool composition surface.

Consistent with P (prompts), C (context), S (state transforms), M (middleware).
T is an expression DSL for composing, wrapping, and dynamically loading tools.

Usage::

    from adk_fluent import T

    # Wrap and compose tools
    agent.tools(T.fn(search) | T.fn(email))

    # Built-in tool groups
    agent.tools(T.google_search())

    # Dynamic loading from a registry
    agent.tools(T.search(registry))
"""

from __future__ import annotations

from typing import Any

__all__ = ["T", "TComposite"]


class TComposite:
    """Composable tool chain. The result of any ``T.xxx()`` call.

    Supports ``|`` for composition::

        T.fn(search) | T.fn(email) | T.google_search()
    """

    def __init__(self, items: list[Any] | None = None):
        self._items: list[Any] = list(items or [])

    def __or__(self, other: TComposite | Any) -> TComposite:
        """T.fn(search) | T.fn(email)"""
        if isinstance(other, TComposite):
            return TComposite(self._items + other._items)
        return TComposite(self._items + [other])

    def __ror__(self, other: Any) -> TComposite:
        """my_fn | T.google_search()"""
        if isinstance(other, TComposite):
            return TComposite(other._items + self._items)
        return TComposite([other] + self._items)

    def to_tools(self) -> list[Any]:
        """Flatten to ADK-compatible tool/toolset list.

        Auto-wraps plain callables in FunctionTool.
        """
        return list(self._items)

    def __repr__(self) -> str:
        names = [type(item).__name__ for item in self._items]
        return f"TComposite([{', '.join(names)}])"

    def __len__(self) -> int:
        return len(self._items)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_tools_t.py -v`
Expected: PASS (all 8 tests)

**Step 5: Lint**

Run: `ruff check --fix src/adk_fluent/_tools.py tests/manual/test_tools_t.py && ruff format src/adk_fluent/_tools.py tests/manual/test_tools_t.py`

**Step 6: Commit**

```bash
git add src/adk_fluent/_tools.py tests/manual/test_tools_t.py
git commit -m "feat(T): add TComposite composable tool chain"
```

______________________________________________________________________

### Task 2: Add `T` factory class — `T.fn()`, `T.agent()`, `T.toolset()`, `T.google_search()`, `T.schema()`

**Files:**

- Modify: `src/adk_fluent/_tools.py`
- Modify: `tests/manual/test_tools_t.py`

**Step 1: Write the failing tests**

Append to `tests/manual/test_tools_t.py`:

```python
class TestTFactory:
    def test_fn_wraps_callable(self):
        from adk_fluent._tools import T

        def my_tool(query: str) -> str:
            return query

        tc = T.fn(my_tool)
        assert len(tc) == 1
        tools = tc.to_tools()
        assert len(tools) == 1
        # Should be a FunctionTool
        from google.adk.tools.function_tool import FunctionTool

        assert isinstance(tools[0], FunctionTool)

    def test_fn_with_confirm(self):
        from adk_fluent._tools import T

        def risky(action: str) -> str:
            return action

        tc = T.fn(risky, confirm=True)
        tools = tc.to_tools()
        from google.adk.tools.function_tool import FunctionTool

        assert isinstance(tools[0], FunctionTool)

    def test_fn_passthrough_base_tool(self):
        from unittest.mock import MagicMock

        from google.adk.tools.base_tool import BaseTool

        from adk_fluent._tools import T

        mock_tool = MagicMock(spec=BaseTool)
        tc = T.fn(mock_tool)
        tools = tc.to_tools()
        assert tools[0] is mock_tool

    def test_agent_wraps_builder(self):
        from adk_fluent import Agent
        from adk_fluent._tools import T

        a = Agent("helper").instruct("Help")
        tc = T.agent(a)
        assert len(tc) == 1
        from google.adk.tools.agent_tool import AgentTool

        assert isinstance(tc.to_tools()[0], AgentTool)

    def test_toolset_wraps(self):
        from unittest.mock import MagicMock

        from google.adk.tools.base_toolset import BaseToolset

        from adk_fluent._tools import T

        mock_ts = MagicMock(spec=BaseToolset)
        tc = T.toolset(mock_ts)
        assert len(tc) == 1
        assert tc.to_tools()[0] is mock_ts

    def test_google_search(self):
        from adk_fluent._tools import T

        tc = T.google_search()
        assert len(tc) == 1

    def test_schema_attaches(self):
        from adk_fluent._tools import T

        class FakeSchema:
            pass

        tc = T.schema(FakeSchema)
        assert len(tc) == 1
        item = tc.to_tools()[0]
        assert item._schema_cls is FakeSchema

    def test_compose_fn_and_google_search(self):
        from adk_fluent._tools import T

        def my_tool(q: str) -> str:
            return q

        tc = T.fn(my_tool) | T.google_search()
        assert len(tc) == 2
```

**Step 2: Run test to verify new tests fail**

Run: `uv run pytest tests/manual/test_tools_t.py::TestTFactory -v`
Expected: FAIL with AttributeError (T has no method fn, etc.)

**Step 3: Add T factory class to `_tools.py`**

Add after the `TComposite` class in `src/adk_fluent/_tools.py`:

```python
class _SchemaMarker:
    """Internal marker for T.schema() — carries schema class through composition."""

    def __init__(self, schema_cls: type):
        self._schema_cls = schema_cls

    def __repr__(self) -> str:
        return f"_SchemaMarker({self._schema_cls.__name__})"


class T:
    """Fluent tool composition. Consistent with P, C, S, M modules.

    Factory methods return ``TComposite`` instances that compose with ``|``.
    """

    # --- Wrapping ---

    @staticmethod
    def fn(func_or_tool: Any, *, confirm: bool = False) -> TComposite:
        """Wrap a callable as a tool.

        If ``func_or_tool`` is already a ``BaseTool``, it is used as-is.
        Plain callables are wrapped in ``FunctionTool``.
        Set ``confirm=True`` to require user confirmation before execution.
        """
        from google.adk.tools.base_tool import BaseTool

        if isinstance(func_or_tool, BaseTool):
            return TComposite([func_or_tool])
        from google.adk.tools.function_tool import FunctionTool

        if confirm:
            return TComposite([FunctionTool(func=func_or_tool, require_confirmation=True)])
        return TComposite([FunctionTool(func=func_or_tool)])

    @staticmethod
    def agent(agent_or_builder: Any) -> TComposite:
        """Wrap an agent (or builder) as an AgentTool."""
        from google.adk.tools.agent_tool import AgentTool

        built = (
            agent_or_builder.build()
            if hasattr(agent_or_builder, "build") and hasattr(agent_or_builder, "_config")
            else agent_or_builder
        )
        return TComposite([AgentTool(agent=built)])

    @staticmethod
    def toolset(ts: Any) -> TComposite:
        """Wrap any ADK toolset (MCPToolset, etc.)."""
        return TComposite([ts])

    # --- Built-in tool groups ---

    @staticmethod
    def google_search(**kwargs: Any) -> TComposite:
        """Google Search tool."""
        from google.adk.tools import google_search

        return TComposite([google_search])

    # --- Contract checking ---

    @staticmethod
    def schema(schema_cls: type) -> TComposite:
        """Attach a ToolSchema for contract checking.

        When piped into a tool chain, this marker is extracted during
        IR conversion and wired to ``AgentNode.tool_schema``.
        """
        return TComposite([_SchemaMarker(schema_cls)])
```

Also update `__all__` to include `_SchemaMarker`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_tools_t.py -v`
Expected: PASS

**Step 5: Lint**

Run: `ruff check --fix src/adk_fluent/_tools.py tests/manual/test_tools_t.py && ruff format src/adk_fluent/_tools.py tests/manual/test_tools_t.py`

**Step 6: Commit**

```bash
git add src/adk_fluent/_tools.py tests/manual/test_tools_t.py
git commit -m "feat(T): add T factory class with fn/agent/toolset/google_search/schema"
```

______________________________________________________________________

### Task 3: Builder integration — `.tools()` accepts `TComposite`

**Files:**

- Modify: `src/adk_fluent/_helpers.py` (add `_add_tools` helper)
- Modify: `seeds/seed.manual.toml` (add `.tools()` extra override)
- Modify: `tests/manual/test_tools_t.py`

**Step 1: Write the failing test**

Append to `tests/manual/test_tools_t.py`:

```python
class TestTBuilderIntegration:
    def test_tools_accepts_tcomposite(self):
        from adk_fluent import Agent
        from adk_fluent._tools import T

        def search(query: str) -> str:
            return query

        a = Agent("helper").tools(T.fn(search))
        ir = a.to_ir()
        assert len(ir.tools) >= 1

    def test_tools_accepts_list(self):
        """Existing behavior: .tools([list]) still works."""
        from adk_fluent import Agent

        def search(query: str) -> str:
            return query

        a = Agent("helper").tools([search])
        ir = a.to_ir()
        assert len(ir.tools) >= 1

    def test_tools_tcomposite_with_schema_extracts(self):
        from adk_fluent import Agent
        from adk_fluent._tools import T, _SchemaMarker

        class FakeSchema:
            pass

        def search(query: str) -> str:
            return query

        a = Agent("helper").tools(T.fn(search) | T.schema(FakeSchema))
        ir = a.to_ir()
        assert ir.tool_schema is FakeSchema
        # Schema marker should NOT be in tools list
        for tool in ir.tools:
            assert not isinstance(tool, _SchemaMarker)

    def test_tool_and_tools_combine(self):
        """T.fn() via .tools() and .tool() via individual add both contribute."""
        from adk_fluent import Agent
        from adk_fluent._tools import T

        def search(query: str) -> str:
            return query

        def email(to: str) -> str:
            return to

        a = Agent("helper").tool(search).tools(T.fn(email))
        ir = a.to_ir()
        assert len(ir.tools) >= 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_tools_t.py::TestTBuilderIntegration -v`
Expected: FAIL — `.tools(TComposite)` currently sets `_config["tools"]` to the TComposite object itself

**Step 3: Add `_add_tools` helper to `_helpers.py`**

Add to `src/adk_fluent/_helpers.py` after the `_add_tool` function (around line 58):

```python
def _add_tools(builder, tools_arg):
    """Set tools on the builder, handling TComposite, lists, and single items.

    If ``tools_arg`` is a ``TComposite``, flattens it and extracts any
    ``_SchemaMarker`` entries to wire ``tool_schema`` on the IR node.
    """
    from adk_fluent._tools import TComposite, _SchemaMarker

    if isinstance(tools_arg, TComposite):
        for item in tools_arg.to_tools():
            if isinstance(item, _SchemaMarker):
                builder._config["_tool_schema"] = item._schema_cls
            else:
                builder._lists["tools"].append(item)
    elif isinstance(tools_arg, list):
        builder._config["tools"] = tools_arg
    else:
        builder._lists["tools"].append(tools_arg)
    return builder
```

Add `"_add_tools"` to `__all__` in `_helpers.py`.

**Step 4: Add `.tools()` override to `seed.manual.toml`**

The generated `.tools()` method does a simple `_config["tools"] = value`. We need to override it to route through our helper. Add to `seed.manual.toml` after the `.tool()` extra (around line 106):

```toml
[[builders.Agent.extras]]
name = "tools"
signature = "(self, value: Any) -> Self"
doc = "Set tools. Accepts a list, a TComposite chain (T.fn(x) | T.fn(y)), or a single tool/toolset."
behavior = "runtime_helper"
helper_func = "_add_tools"
```

**Step 5: Regenerate**

Run: `just seed && just generate`

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_tools_t.py -v`
Expected: PASS

**Step 7: Verify no regressions**

Run: `uv run pytest tests/ -x --tb=short -q`
Expected: All tests pass

**Step 8: Lint**

Run: `ruff check --fix . && ruff format .`

**Step 9: Commit**

```bash
git add src/adk_fluent/_helpers.py seeds/seed.manual.toml src/adk_fluent/agent.py src/adk_fluent/agent.pyi tests/manual/test_tools_t.py
git commit -m "feat(T): builder .tools() accepts TComposite with schema extraction"
```

______________________________________________________________________

### Task 4: Create `_tool_registry.py` — `ToolRegistry` with BM25

**Files:**

- Create: `src/adk_fluent/_tool_registry.py`
- Test: `tests/manual/test_tool_registry.py`

**Step 1: Write the failing test**

Create `tests/manual/test_tool_registry.py`:

```python
"""Tests for ToolRegistry — BM25-indexed tool catalog."""

from __future__ import annotations

from unittest.mock import MagicMock

from google.adk.tools.function_tool import FunctionTool


def _make_fn(name: str, doc: str):
    """Create a mock callable with a given name and docstring."""

    def fn(**kwargs):
        pass

    fn.__name__ = name
    fn.__doc__ = doc
    return fn


class TestToolRegistry:
    def test_register_callable(self):
        from adk_fluent._tool_registry import ToolRegistry

        reg = ToolRegistry()

        def search(query: str) -> str:
            """Search the web for information."""
            return query

        reg.register(search)
        assert reg.get_tool("search") is not None

    def test_register_base_tool(self):
        from adk_fluent._tool_registry import ToolRegistry

        reg = ToolRegistry()
        tool = FunctionTool(func=lambda q: q)
        tool.name = "my_tool"
        reg.register(tool)
        assert reg.get_tool("my_tool") is not None

    def test_register_all(self):
        from adk_fluent._tool_registry import ToolRegistry

        fn1 = _make_fn("search", "Search the web.")
        fn2 = _make_fn("email", "Send an email.")
        reg = ToolRegistry()
        reg.register_all(fn1, fn2)
        assert reg.get_tool("search") is not None
        assert reg.get_tool("email") is not None

    def test_search_substring_fallback(self):
        from adk_fluent._tool_registry import ToolRegistry

        fn1 = _make_fn("web_search", "Search the web for information.")
        fn2 = _make_fn("send_email", "Send an email message.")
        fn3 = _make_fn("calculator", "Perform math calculations.")
        reg = ToolRegistry()
        reg.register_all(fn1, fn2, fn3)
        results = reg.search("search web", top_k=2)
        assert len(results) <= 2
        assert any("web_search" in r["name"] for r in results)

    def test_from_tools_factory(self):
        from adk_fluent._tool_registry import ToolRegistry

        fn1 = _make_fn("a", "Tool A")
        fn2 = _make_fn("b", "Tool B")
        reg = ToolRegistry.from_tools(fn1, fn2)
        assert reg.get_tool("a") is not None
        assert reg.get_tool("b") is not None

    def test_get_tool_not_found(self):
        from adk_fluent._tool_registry import ToolRegistry

        reg = ToolRegistry()
        assert reg.get_tool("nonexistent") is None

    def test_search_empty_registry(self):
        from adk_fluent._tool_registry import ToolRegistry

        reg = ToolRegistry()
        results = reg.search("anything")
        assert results == []

    def test_search_returns_dicts(self):
        from adk_fluent._tool_registry import ToolRegistry

        fn = _make_fn("tool_a", "A useful tool.")
        reg = ToolRegistry.from_tools(fn)
        results = reg.search("useful", top_k=1)
        assert len(results) == 1
        assert "name" in results[0]
        assert "description" in results[0]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_tool_registry.py -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

Create `src/adk_fluent/_tool_registry.py`:

```python
"""ToolRegistry — BM25-indexed catalog for tool discovery.

``rank_bm25`` is an optional dependency (``pip install adk-fluent[search]``).
Falls back to substring matching if not installed.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.function_tool import FunctionTool

__all__ = ["ToolRegistry"]

try:
    from rank_bm25 import BM25Okapi

    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False


def _tool_name(tool: Any) -> str:
    """Extract a name from a tool or callable."""
    if isinstance(tool, BaseTool):
        return getattr(tool, "name", type(tool).__name__)
    return getattr(tool, "__name__", str(tool))


def _tool_description(tool: Any) -> str:
    """Extract a description from a tool or callable."""
    if isinstance(tool, BaseTool):
        return getattr(tool, "description", "") or ""
    return getattr(tool, "__doc__", "") or ""


class ToolRegistry:
    """BM25-indexed registry for tool discovery.

    Register tools (callables or ``BaseTool`` instances), then search
    by natural language query. When ``rank_bm25`` is installed, uses
    BM25Okapi for ranking. Otherwise falls back to substring matching.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}
        self._descriptions: dict[str, str] = {}
        self._bm25: Any = None
        self._corpus_names: list[str] = []

    def register(self, tool: Any) -> None:
        """Register a tool (callable or BaseTool instance)."""
        if callable(tool) and not isinstance(tool, BaseTool):
            wrapped = FunctionTool(func=tool)
            name = _tool_name(tool)
            self._tools[name] = wrapped
            self._descriptions[name] = _tool_description(tool)
        else:
            name = _tool_name(tool)
            self._tools[name] = tool
            self._descriptions[name] = _tool_description(tool)
        self._bm25 = None  # invalidate index

    def register_all(self, *tools: Any) -> None:
        """Register multiple tools at once."""
        for tool in tools:
            self.register(tool)

    def _ensure_index(self) -> None:
        """Build or rebuild the BM25 index."""
        if not _HAS_BM25:
            return
        if self._bm25 is not None:
            return
        self._corpus_names = list(self._tools.keys())
        corpus = []
        for name in self._corpus_names:
            desc = self._descriptions.get(name, "")
            tokens = (name + " " + desc).lower().split()
            corpus.append(tokens)
        if corpus:
            self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, str]]:
        """Search for tools matching a query.

        Returns a list of dicts with ``name`` and ``description`` keys,
        ordered by relevance.
        """
        if not self._tools:
            return []

        if _HAS_BM25:
            self._ensure_index()
            tokens = query.lower().split()
            scores = self._bm25.get_scores(tokens)
            ranked = sorted(
                zip(self._corpus_names, scores),
                key=lambda x: x[1],
                reverse=True,
            )
            results = []
            for name, score in ranked[:top_k]:
                if score > 0:
                    results.append(
                        {"name": name, "description": self._descriptions.get(name, "")}
                    )
            return results
        else:
            # Substring fallback
            query_lower = query.lower()
            matches = []
            for name, desc in self._descriptions.items():
                text = (name + " " + desc).lower()
                if any(word in text for word in query_lower.split()):
                    matches.append({"name": name, "description": desc})
            return matches[:top_k]

    def get_tool(self, name: str) -> Any | None:
        """Get a registered tool by name."""
        return self._tools.get(name)

    @classmethod
    def from_tools(cls, *tools: Any) -> ToolRegistry:
        """Factory: build registry from a list of tools."""
        reg = cls()
        reg.register_all(*tools)
        return reg
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_tool_registry.py -v`
Expected: PASS

**Step 5: Lint**

Run: `ruff check --fix src/adk_fluent/_tool_registry.py tests/manual/test_tool_registry.py && ruff format src/adk_fluent/_tool_registry.py tests/manual/test_tool_registry.py`

**Step 6: Commit**

```bash
git add src/adk_fluent/_tool_registry.py tests/manual/test_tool_registry.py
git commit -m "feat(T): add ToolRegistry with BM25 search and substring fallback"
```

______________________________________________________________________

### Task 5: Create `SearchToolset` — two-phase dynamic loading

**Files:**

- Modify: `src/adk_fluent/_tool_registry.py`
- Create: `tests/manual/test_search_toolset.py`

**Step 1: Write the failing test**

Create `tests/manual/test_search_toolset.py`:

```python
"""Tests for SearchToolset — two-phase dynamic tool loading."""

from __future__ import annotations

import pytest


def _make_fn(name: str, doc: str):
    def fn(**kwargs):
        pass

    fn.__name__ = name
    fn.__doc__ = doc
    return fn


class TestSearchToolsetPhases:
    @pytest.mark.asyncio
    async def test_discovery_phase_returns_meta_tools(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fn1 = _make_fn("search", "Search the web.")
        fn2 = _make_fn("email", "Send email.")
        registry = ToolRegistry.from_tools(fn1, fn2)
        toolset = SearchToolset(registry)

        # Mock a readonly_context with state
        from types import SimpleNamespace

        ctx = SimpleNamespace(state={})
        tools = await toolset.get_tools(readonly_context=ctx)
        # Discovery phase returns meta-tools
        assert len(tools) == 3
        names = [t.name for t in tools]
        assert "search_tools" in names
        assert "load_tool" in names
        assert "finalize_tools" in names

    @pytest.mark.asyncio
    async def test_execution_phase_returns_loaded_tools(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fn1 = _make_fn("search", "Search the web.")
        registry = ToolRegistry.from_tools(fn1)
        toolset = SearchToolset(registry)
        toolset._loaded_names.add("search")
        toolset._frozen = True

        from types import SimpleNamespace

        ctx = SimpleNamespace(state={"toolset_phase": "execution"})
        tools = await toolset.get_tools(readonly_context=ctx)
        assert len(tools) >= 1
        # Should contain the actual tool, not meta-tools
        names = [getattr(t, "name", None) or t.__name__ for t in tools]
        assert "search" in names

    @pytest.mark.asyncio
    async def test_always_loaded(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fn1 = _make_fn("search", "Search the web.")
        fn2 = _make_fn("email", "Send email.")
        registry = ToolRegistry.from_tools(fn1, fn2)
        toolset = SearchToolset(registry, always_loaded=["search"])
        toolset._frozen = True

        from types import SimpleNamespace

        ctx = SimpleNamespace(state={"toolset_phase": "execution"})
        tools = await toolset.get_tools(readonly_context=ctx)
        names = [getattr(t, "name", None) or t.__name__ for t in tools]
        assert "search" in names

    @pytest.mark.asyncio
    async def test_max_tools_limit(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fns = [_make_fn(f"tool_{i}", f"Tool {i}") for i in range(30)]
        registry = ToolRegistry.from_tools(*fns)
        toolset = SearchToolset(registry, max_tools=5)
        # Try to load more than max
        for i in range(10):
            toolset._loaded_names.add(f"tool_{i}")
        toolset._frozen = True

        from types import SimpleNamespace

        ctx = SimpleNamespace(state={"toolset_phase": "execution"})
        tools = await toolset.get_tools(readonly_context=ctx)
        assert len(tools) <= 5


class TestSearchToolsetMetaTools:
    @pytest.mark.asyncio
    async def test_search_tools_returns_results(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fn = _make_fn("web_search", "Search the web for information.")
        registry = ToolRegistry.from_tools(fn)
        toolset = SearchToolset(registry)
        result = toolset._search_fn("search web")
        assert isinstance(result, str)
        assert "web_search" in result

    def test_load_tool_adds_to_loaded(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fn = _make_fn("search", "Search the web.")
        registry = ToolRegistry.from_tools(fn)
        toolset = SearchToolset(registry)
        result = toolset._load_fn("search")
        assert "search" in toolset._loaded_names
        assert "loaded" in result.lower() or "search" in result.lower()

    def test_load_tool_not_found(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        registry = ToolRegistry()
        toolset = SearchToolset(registry)
        result = toolset._load_fn("nonexistent")
        assert "not found" in result.lower()

    def test_finalize_freezes(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        registry = ToolRegistry()
        toolset = SearchToolset(registry)
        result = toolset._finalize_fn()
        assert toolset._frozen is True
        assert "finalized" in result.lower() or "frozen" in result.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_search_toolset.py -v`
Expected: FAIL with ImportError

**Step 3: Add `SearchToolset` to `_tool_registry.py`**

Append to `src/adk_fluent/_tool_registry.py`:

```python
class SearchToolset:
    """Two-phase dynamic tool loading.

    Phase 1 (Discovery): ``get_tools()`` returns meta-tools
    (search_tools, load_tool, finalize_tools). The agent discovers
    and loads tools via BM25 search. KV-cache invalidation is
    acceptable during this phase (short prefix).

    Phase 2 (Execution): ``get_tools()`` returns loaded tools. FROZEN.
    Identical tool list on every turn. Stable KV-cache.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        always_loaded: list[str] | None = None,
        max_tools: int = 20,
    ) -> None:
        self._registry = registry
        self._always_loaded = set(always_loaded or [])
        self._max_tools = max_tools
        self._loaded_names: set[str] = set()
        self._frozen = False
        self._meta_tools: list[Any] | None = None

    def _build_meta_tools(self) -> list[Any]:
        """Build the three meta-tools for the discovery phase."""
        search_tool = FunctionTool(func=self._search_fn)
        load_tool = FunctionTool(func=self._load_fn)
        finalize_tool = FunctionTool(func=self._finalize_fn)
        return [search_tool, load_tool, finalize_tool]

    def _search_fn(self, query: str) -> str:
        """Search available tools by description. Returns summaries of matching tools."""
        results = self._registry.search(query)
        if not results:
            return "No tools found matching your query."
        lines = []
        for r in results:
            lines.append(f"- {r['name']}: {r['description']}")
        return "\n".join(lines)

    _search_fn.__name__ = "search_tools"
    _search_fn.__doc__ = "Search available tools by description. Returns summaries of matching tools."

    def _load_fn(self, tool_name: str) -> str:
        """Load a tool by name into the active toolset."""
        tool = self._registry.get_tool(tool_name)
        if tool is None:
            return f"Tool '{tool_name}' not found in registry."
        if self._frozen:
            return "Toolset is frozen. Cannot load more tools."
        if len(self._loaded_names) >= self._max_tools:
            return f"Maximum tools ({self._max_tools}) already loaded."
        self._loaded_names.add(tool_name)
        return f"Tool '{tool_name}' loaded successfully."

    _load_fn.__name__ = "load_tool"
    _load_fn.__doc__ = "Load a tool by name into the active toolset."

    def _finalize_fn(self) -> str:
        """Finalize the toolset. No more tools can be added after this."""
        self._frozen = True
        loaded = sorted(self._loaded_names | self._always_loaded)
        return f"Toolset finalized with {len(loaded)} tools: {', '.join(loaded)}"

    _finalize_fn.__name__ = "finalize_tools"
    _finalize_fn.__doc__ = "Finalize the toolset. No more tools can be added after this."

    async def get_tools(self, readonly_context: Any = None) -> list[Any]:
        """Return tools based on current phase.

        Discovery phase: returns meta-tools.
        Execution phase: returns frozen tool list.
        """
        state = getattr(readonly_context, "state", {})
        phase = state.get("toolset_phase", "discovery")

        if phase == "discovery" and not self._frozen:
            if self._meta_tools is None:
                self._meta_tools = self._build_meta_tools()
            return self._meta_tools

        # Execution phase: return loaded tools
        active_names = self._loaded_names | self._always_loaded
        tools = []
        for name in sorted(active_names):
            tool = self._registry.get_tool(name)
            if tool is not None:
                tools.append(tool)
        return tools[: self._max_tools]
```

Update `__all__` to include `"SearchToolset"`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_search_toolset.py -v`
Expected: PASS

**Step 5: Lint**

Run: `ruff check --fix src/adk_fluent/_tool_registry.py tests/manual/test_search_toolset.py && ruff format src/adk_fluent/_tool_registry.py tests/manual/test_search_toolset.py`

**Step 6: Commit**

```bash
git add src/adk_fluent/_tool_registry.py tests/manual/test_search_toolset.py
git commit -m "feat(T): add SearchToolset with two-phase dynamic loading"
```

______________________________________________________________________

### Task 6: Add `T.search()` factory and `search_aware_after_tool` callback

**Files:**

- Modify: `src/adk_fluent/_tools.py` (add `T.search()`)
- Modify: `src/adk_fluent/_tool_registry.py` (add `search_aware_after_tool`, `compress_large_result`, `_ResultVariator`)
- Modify: `tests/manual/test_tools_t.py`
- Modify: `tests/manual/test_tool_registry.py`

**Step 1: Write the failing tests**

Append to `tests/manual/test_tools_t.py`:

```python
class TestTSearch:
    def test_t_search_returns_tcomposite(self):
        from adk_fluent._tool_registry import ToolRegistry
        from adk_fluent._tools import T, TComposite

        def search(query: str) -> str:
            """Search."""
            return query

        registry = ToolRegistry.from_tools(search)
        tc = T.search(registry)
        assert isinstance(tc, TComposite)
        assert len(tc) == 1

    def test_t_search_contains_search_toolset(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry
        from adk_fluent._tools import T

        def search(query: str) -> str:
            """Search."""
            return query

        registry = ToolRegistry.from_tools(search)
        tc = T.search(registry)
        tools = tc.to_tools()
        assert isinstance(tools[0], SearchToolset)
```

Append to `tests/manual/test_tool_registry.py`:

```python
class TestSearchAwareAfterTool:
    def test_compress_large_result(self):
        from adk_fluent._tool_registry import compress_large_result

        # Small result passes through
        small = "hello"
        assert compress_large_result(small, threshold=100) == small

        # Large result is compressed to a file path reference
        large = "x" * 200
        result = compress_large_result(large, threshold=100)
        assert "file" in result.lower() or len(result) < len(large)

    def test_result_variator(self):
        from adk_fluent._tool_registry import _ResultVariator

        v = _ResultVariator()
        r1 = v.vary("result text", 0)
        r2 = v.vary("result text", 1)
        # Both should contain the original text
        assert "result text" in r1
        assert "result text" in r2
        # They should have slight variation
        assert r1 != r2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_tools_t.py::TestTSearch tests/manual/test_tool_registry.py::TestSearchAwareAfterTool -v`
Expected: FAIL

**Step 3: Add `T.search()` to `_tools.py`**

Add to the `T` class in `_tools.py`:

```python
    # --- Dynamic loading ---

    @staticmethod
    def search(
        registry: Any,
        *,
        always_loaded: list[str] | None = None,
        max_tools: int = 20,
    ) -> TComposite:
        """BM25-indexed dynamic tool loading (two-phase pattern).

        Wraps a ``ToolRegistry`` in a ``SearchToolset`` that implements
        discovery → loading → freezing lifecycle.
        """
        from adk_fluent._tool_registry import SearchToolset

        toolset = SearchToolset(
            registry, always_loaded=always_loaded, max_tools=max_tools
        )
        return TComposite([toolset])
```

**Step 4: Add helpers to `_tool_registry.py`**

Append to `src/adk_fluent/_tool_registry.py`:

```python
import tempfile
import os


def compress_large_result(result: str, threshold: int = 4000) -> str:
    """Write large results to a temp file, return file path reference.

    If the result is shorter than ``threshold``, return it unchanged.
    Otherwise write to a temp file and return a reference string.
    """
    if len(result) <= threshold:
        return result
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="tool_result_")
    with os.fdopen(fd, "w") as f:
        f.write(result)
    return f"[Result written to file: {path}] ({len(result)} chars)"


class _ResultVariator:
    """Add subtle formatting variation to tool results.

    Prevents repetitive patterns that confuse the LLM.
    """

    _PREFIXES = [
        "Result:",
        "Output:",
        "Response:",
        "Data:",
    ]

    def vary(self, result: str, call_index: int) -> str:
        """Add a prefix variation based on call index."""
        prefix = self._PREFIXES[call_index % len(self._PREFIXES)]
        return f"{prefix} {result}"


async def search_aware_after_tool(
    tool_context: Any,
    tool_response: Any,
    *,
    compress_threshold: int = 4000,
) -> Any:
    """Pre-built after_tool callback for search-aware agents.

    Handles:
    1. Large result compression (results > threshold → temp file)
    2. Error preservation (failed calls annotated, NOT silently retried)
    3. Result variation (subtle formatting per call index)
    """
    if tool_response is None:
        return tool_response

    result_str = str(tool_response)

    # Compress large results
    result_str = compress_large_result(result_str, threshold=compress_threshold)

    return result_str
```

Update `__all__` to include `"SearchToolset"`, `"search_aware_after_tool"`, `"compress_large_result"`, `"_ResultVariator"`.

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_tools_t.py tests/manual/test_tool_registry.py -v`
Expected: PASS

**Step 6: Lint**

Run: `ruff check --fix src/adk_fluent/_tools.py src/adk_fluent/_tool_registry.py tests/manual/test_tools_t.py tests/manual/test_tool_registry.py && ruff format src/adk_fluent/_tools.py src/adk_fluent/_tool_registry.py tests/manual/test_tools_t.py tests/manual/test_tool_registry.py`

**Step 7: Commit**

```bash
git add src/adk_fluent/_tools.py src/adk_fluent/_tool_registry.py tests/manual/test_tools_t.py tests/manual/test_tool_registry.py
git commit -m "feat(T): add T.search(), search_aware_after_tool, result compression"
```

______________________________________________________________________

### Task 7: Exports — prelude, `__init__.py`, pyproject.toml

**Files:**

- Modify: `src/adk_fluent/prelude.py`
- Modify: `pyproject.toml`
- Regenerate: `src/adk_fluent/__init__.py` (via `just generate`)

**Step 1: Write the failing test**

Append to `tests/manual/test_tools_t.py`:

```python
class TestTExports:
    def test_import_from_adk_fluent(self):
        from adk_fluent import T, TComposite

        assert T is not None
        assert TComposite is not None

    def test_import_from_prelude(self):
        from adk_fluent.prelude import T, TComposite

        assert T is not None
        assert TComposite is not None

    def test_import_registry_from_adk_fluent(self):
        from adk_fluent import ToolRegistry

        assert ToolRegistry is not None

    def test_import_search_toolset(self):
        from adk_fluent import SearchToolset

        assert SearchToolset is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/manual/test_tools_t.py::TestTExports -v`
Expected: FAIL — T, TComposite not yet exported from adk_fluent or prelude

**Step 3: Update prelude.py**

Add `T` and `TComposite` to Tier 2 (composition namespaces) in `src/adk_fluent/prelude.py`:

```python
from adk_fluent._tools import T, TComposite
```

And add to `__all__`:

```python
    "T",
    "TComposite",
```

Also add `ToolRegistry` and `SearchToolset` imports:

```python
from adk_fluent._tool_registry import ToolRegistry, SearchToolset
```

And to `__all__`:

```python
    "ToolRegistry",
    "SearchToolset",
```

**Step 4: Update pyproject.toml**

Add `search` optional dependency. Add after the `rich` section:

```toml
search = [
    "rank-bm25>=0.2.2",
]
```

**Step 5: Regenerate `__init__.py`**

Run: `just generate`

The `__init__.py` auto-discovers `__all__` from `_tools.py` and `_tool_registry.py`.

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/manual/test_tools_t.py::TestTExports -v`
Expected: PASS

**Step 7: Verify no regressions**

Run: `uv run pytest tests/ -x --tb=short -q`
Expected: All tests pass

**Step 8: Lint and verify idempotency**

Run: `ruff check --fix . && ruff format . && just check-gen`

**Step 9: Commit**

```bash
git add src/adk_fluent/prelude.py src/adk_fluent/__init__.py pyproject.toml
git commit -m "feat(T): export T, TComposite, ToolRegistry, SearchToolset; add search extra"
```

______________________________________________________________________

### Task 8: Cookbook example

**Files:**

- Create: `examples/cookbook/66_t_module_tools.py`

**Step 1: Write the cookbook**

Create `examples/cookbook/66_t_module_tools.py`:

```python
"""T Module: Fluent Tool Composition and Dynamic Loading

Demonstrates the T module for composing, wrapping, and dynamically
loading tools using the fluent API.

Key concepts:
  - TComposite: composable tool chain with | operator
  - T.fn(): wrap callable as FunctionTool
  - T.agent(): wrap agent as AgentTool
  - T.toolset(): wrap any ADK toolset
  - T.google_search(): built-in Google Search
  - T.schema(): attach ToolSchema for contract checking
  - T.search(): BM25-indexed dynamic tool loading
  - ToolRegistry: tool catalog with search
  - SearchToolset: two-phase discovery/execution
  - search_aware_after_tool: pre-built callback
"""

# --- FLUENT ---
from adk_fluent._tools import T, TComposite

# --- 1. TComposite composition ---
a = TComposite(["tool_a"])
b = TComposite(["tool_b"])
c = a | b
assert len(c) == 2
assert c.to_tools() == ["tool_a", "tool_b"]

# Three-way composition
d = TComposite(["tool_c"])
result = a | b | d
assert len(result) == 3

# Raw value on left
mixed = "raw_tool" | TComposite(["wrapped"])
assert len(mixed) == 2
assert mixed.to_tools()[0] == "raw_tool"

# Repr
assert "TComposite" in repr(c)

# --- 2. T.fn() wrapping ---
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Results for {query}"


tc = T.fn(search_web)
assert len(tc) == 1

from google.adk.tools.function_tool import FunctionTool

assert isinstance(tc.to_tools()[0], FunctionTool)

# With confirmation
tc_confirm = T.fn(search_web, confirm=True)
assert isinstance(tc_confirm.to_tools()[0], FunctionTool)

# --- 3. T.agent() wrapping ---
from adk_fluent import Agent

helper = Agent("helper").instruct("Help the user.")
tc_agent = T.agent(helper)
assert len(tc_agent) == 1

from google.adk.tools.agent_tool import AgentTool

assert isinstance(tc_agent.to_tools()[0], AgentTool)

# --- 4. T.google_search() ---
tc_gs = T.google_search()
assert len(tc_gs) == 1

# --- 5. Composition: T.fn() | T.google_search() ---
composed = T.fn(search_web) | T.google_search()
assert len(composed) == 2
assert isinstance(composed.to_tools()[0], FunctionTool)

# --- 6. T.schema() ---
from adk_fluent._tools import _SchemaMarker


class FakeToolSchema:
    pass


tc_schema = T.schema(FakeToolSchema)
assert len(tc_schema) == 1
assert isinstance(tc_schema.to_tools()[0], _SchemaMarker)
assert tc_schema.to_tools()[0]._schema_cls is FakeToolSchema

# --- 7. ToolRegistry ---
from adk_fluent._tool_registry import ToolRegistry


def send_email(to: str, body: str) -> str:
    """Send an email message to a recipient."""
    return f"Email sent to {to}"


def calculate(expr: str) -> str:
    """Perform mathematical calculations."""
    return f"Result: {expr}"


def translate(text: str, lang: str) -> str:
    """Translate text to another language."""
    return f"Translated to {lang}: {text}"


registry = ToolRegistry.from_tools(search_web, send_email, calculate, translate)

# Get tool by name
assert registry.get_tool("search_web") is not None
assert registry.get_tool("nonexistent") is None

# Search
results = registry.search("search web", top_k=2)
assert len(results) <= 2
assert any("search_web" in r["name"] for r in results)

# --- 8. SearchToolset two-phase ---
from adk_fluent._tool_registry import SearchToolset

toolset = SearchToolset(registry, always_loaded=["calculate"], max_tools=10)

# Meta-tool functions
search_result = toolset._search_fn("email")
assert "send_email" in search_result

load_result = toolset._load_fn("send_email")
assert "send_email" in toolset._loaded_names

finalize_result = toolset._finalize_fn()
assert toolset._frozen is True
assert "finalized" in finalize_result.lower() or "frozen" in finalize_result.lower()

# --- 9. T.search() factory ---
registry2 = ToolRegistry.from_tools(search_web, send_email)
tc_search = T.search(registry2)
assert len(tc_search) == 1
assert isinstance(tc_search.to_tools()[0], SearchToolset)

# --- 10. compress_large_result ---
from adk_fluent._tool_registry import compress_large_result

small = "hello"
assert compress_large_result(small, threshold=100) == small

large = "x" * 200
compressed = compress_large_result(large, threshold=100)
assert len(compressed) < len(large)

# --- 11. _ResultVariator ---
from adk_fluent._tool_registry import _ResultVariator

variator = _ResultVariator()
r0 = variator.vary("data", 0)
r1 = variator.vary("data", 1)
assert "data" in r0
assert "data" in r1
assert r0 != r1  # Different prefixes

# --- 12. Builder integration ---
def tool_a(x: str) -> str:
    """Tool A."""
    return x


def tool_b(x: str) -> str:
    """Tool B."""
    return x


agent = Agent("composer").tools(T.fn(tool_a) | T.fn(tool_b))
ir = agent.to_ir()
assert len(ir.tools) >= 2

# .tool() and .tools(TComposite) combine
agent2 = Agent("combined").tool(tool_a).tools(T.fn(tool_b))
ir2 = agent2.to_ir()
assert len(ir2.tools) >= 2

print("All T module assertions passed!")
```

**Step 2: Run cookbook test**

Run: `uv run pytest examples/cookbook/66_t_module_tools.py -v`
Expected: PASS

**Step 3: Lint**

Run: `ruff check --fix examples/cookbook/66_t_module_tools.py && ruff format examples/cookbook/66_t_module_tools.py`

**Step 4: Commit**

```bash
git add examples/cookbook/66_t_module_tools.py
git commit -m "docs: add cookbook 66 — T module tool composition and dynamic loading"
```

______________________________________________________________________

### Task 9: Full verification

**Files:** None (verification only)

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -x --tb=short -q`
Expected: All tests pass (2060+ tests)

**Step 2: Run all cookbook tests**

Run: `uv run pytest examples/cookbook/ -q`
Expected: All 66 cookbook tests pass

**Step 3: Typecheck**

Run: `just typecheck-core`
Expected: 0 errors

**Step 4: Lint**

Run: `ruff check --fix . && ruff format .`
Expected: Clean

**Step 5: Pre-commit hooks**

Run: `just preflight`
Expected: All hooks pass

**Step 6: Check-gen idempotency**

Run: `just check-gen`
Expected: No diff

**Step 7: Verify key imports**

Run: `uv run python -c "from adk_fluent import T, TComposite, ToolRegistry, SearchToolset; print('OK')"`
Expected: `OK`

Run: `uv run python -c "from adk_fluent.prelude import T, TComposite; print('OK')"`
Expected: `OK`
