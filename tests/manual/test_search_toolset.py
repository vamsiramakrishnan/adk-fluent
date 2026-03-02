"""Tests for SearchToolset -- two-phase dynamic tool loading."""

from __future__ import annotations

import pytest

try:
    import pytest_asyncio  # noqa: F401

    _has_pytest_asyncio = True
except ImportError:
    _has_pytest_asyncio = False

_needs_asyncio = pytest.mark.skipif(not _has_pytest_asyncio, reason="pytest-asyncio not installed")


def _make_fn(name: str, doc: str):
    def fn(**kwargs):
        pass

    fn.__name__ = name
    fn.__doc__ = doc
    return fn


@_needs_asyncio
class TestSearchToolsetPhases:
    @pytest.mark.asyncio
    async def test_discovery_phase_returns_meta_tools(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fn1 = _make_fn("search", "Search the web.")
        fn2 = _make_fn("email", "Send email.")
        registry = ToolRegistry.from_tools(fn1, fn2)
        toolset = SearchToolset(registry)

        from types import SimpleNamespace

        ctx = SimpleNamespace(state={})
        tools = await toolset.get_tools(readonly_context=ctx)
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
        names = [getattr(t, "name", None) for t in tools]
        assert "search" in names

    @pytest.mark.asyncio
    async def test_max_tools_limit(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fns = [_make_fn(f"tool_{i}", f"Tool {i}") for i in range(30)]
        registry = ToolRegistry.from_tools(*fns)
        toolset = SearchToolset(registry, max_tools=5)
        for i in range(10):
            toolset._loaded_names.add(f"tool_{i}")
        toolset._frozen = True

        from types import SimpleNamespace

        ctx = SimpleNamespace(state={"toolset_phase": "execution"})
        tools = await toolset.get_tools(readonly_context=ctx)
        assert len(tools) <= 5


class TestSearchToolsetMetaTools:
    def test_search_tools_returns_results(self):
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

    def test_load_after_frozen_rejected(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry

        fn = _make_fn("search", "Search the web.")
        registry = ToolRegistry.from_tools(fn)
        toolset = SearchToolset(registry)
        toolset._finalize_fn()
        result = toolset._load_fn("search")
        assert "frozen" in result.lower()
