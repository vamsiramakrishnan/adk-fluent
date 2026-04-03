"""Tests for the Manifold — unified runtime capability discovery.

Tests cover:
    - CapabilityRegistry (add, search, list, import from registries)
    - ManifoldToolset (two-phase: discovery meta-tools → frozen execution)
    - H.manifold() factory
    - Event types (CapabilityLoaded, ManifoldFinalized)
    - Composition with existing ToolRegistry and SkillRegistry
"""

import asyncio
import json
import tempfile
from unittest.mock import MagicMock

import pytest

from adk_fluent import H
from adk_fluent._harness import (
    CapabilityLoaded,
    ManifoldFinalized,
)
from adk_fluent._harness._manifold import (
    CapabilityEntry,
    CapabilityRegistry,
    CapabilityType,
    ManifoldToolset,
)
from adk_fluent._tool_registry import ToolRegistry

# ======================================================================
# Helpers
# ======================================================================


def _make_tool(name: str, doc: str = ""):
    """Create a simple callable tool."""

    def tool_fn(x: str) -> str:
        return f"{name}: {x}"

    tool_fn.__name__ = name
    tool_fn.__doc__ = doc or f"A tool named {name}."
    return tool_fn


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# ======================================================================
# CapabilityEntry
# ======================================================================


class TestCapabilityEntry:
    def test_frozen(self):
        entry = CapabilityEntry(name="test", description="desc", cap_type=CapabilityType.TOOL)
        with pytest.raises(AttributeError):
            entry.name = "changed"  # type: ignore[misc]

    def test_tags(self):
        entry = CapabilityEntry(
            name="skill1",
            description="desc",
            cap_type=CapabilityType.SKILL,
            tags=("research", "code"),
        )
        assert entry.tags == ("research", "code")

    def test_types(self):
        assert CapabilityType.TOOL.value == "tool"
        assert CapabilityType.SKILL.value == "skill"
        assert CapabilityType.MCP_SERVER.value == "mcp_server"


# ======================================================================
# CapabilityRegistry
# ======================================================================


class TestCapabilityRegistry:
    def test_add_and_get(self):
        reg = CapabilityRegistry()
        entry = CapabilityEntry(name="my_tool", description="Does stuff", cap_type=CapabilityType.TOOL)
        reg.add(entry)
        assert reg.get("my_tool") is entry
        assert reg.size == 1

    def test_get_missing(self):
        reg = CapabilityRegistry()
        assert reg.get("nonexistent") is None

    def test_search_substring_fallback(self):
        reg = CapabilityRegistry()
        reg.add(CapabilityEntry(name="web_search", description="Search the web", cap_type=CapabilityType.TOOL))
        reg.add(CapabilityEntry(name="file_read", description="Read files", cap_type=CapabilityType.TOOL))
        reg.add(CapabilityEntry(name="code_review", description="Review code quality", cap_type=CapabilityType.SKILL))

        results = reg.search("web")
        assert len(results) >= 1
        assert results[0].name == "web_search"

    def test_search_empty_registry(self):
        reg = CapabilityRegistry()
        assert reg.search("anything") == []

    def test_search_by_type(self):
        reg = CapabilityRegistry()
        reg.add(CapabilityEntry(name="tool1", description="A tool", cap_type=CapabilityType.TOOL))
        reg.add(CapabilityEntry(name="skill1", description="A skill about tools", cap_type=CapabilityType.SKILL))

        results = reg.search_by_type("tool", CapabilityType.TOOL)
        assert all(e.cap_type == CapabilityType.TOOL for e in results)

    def test_list_by_type(self):
        reg = CapabilityRegistry()
        reg.add(CapabilityEntry(name="t1", description="", cap_type=CapabilityType.TOOL))
        reg.add(CapabilityEntry(name="s1", description="", cap_type=CapabilityType.SKILL))
        reg.add(CapabilityEntry(name="t2", description="", cap_type=CapabilityType.TOOL))

        tools = reg.list_by_type(CapabilityType.TOOL)
        assert len(tools) == 2

    def test_add_from_tool_registry(self):
        tool_reg = ToolRegistry()
        tool_reg.register(_make_tool("grep_search", "Search files with grep"))
        tool_reg.register(_make_tool("bash", "Execute shell commands"))

        reg = CapabilityRegistry()
        reg.add_from_tool_registry(tool_reg)

        assert reg.size == 2
        assert reg.get("grep_search") is not None
        assert reg.get("grep_search").cap_type == CapabilityType.TOOL

    def test_add_mcp_servers(self):
        reg = CapabilityRegistry()
        reg.add_mcp_servers(
            [
                {"name": "filesystem", "url": "http://localhost:3000/mcp", "description": "File system access"},
                {"name": "github", "command": "npx", "args": ["-y", "@github/mcp-server"]},
            ]
        )

        assert reg.size == 2
        fs = reg.get("mcp:filesystem")
        assert fs is not None
        assert fs.cap_type == CapabilityType.MCP_SERVER

    def test_add_mcp_config_from_file(self):
        config = {
            "mcpServers": {
                "filesystem": {"url": "http://localhost:3000/mcp"},
                "github": {"command": "npx", "args": ["-y", "@github/mcp"]},
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()

            reg = CapabilityRegistry()
            reg.add_mcp_config(f.name)

        assert reg.size == 2
        assert reg.get("mcp:filesystem") is not None
        assert reg.get("mcp:github") is not None

    def test_add_mcp_config_missing_file(self):
        reg = CapabilityRegistry()
        reg.add_mcp_config("/nonexistent/path.json")
        assert reg.size == 0  # no crash

    def test_search_tags(self):
        reg = CapabilityRegistry()
        reg.add(
            CapabilityEntry(
                name="research",
                description="Research methodology",
                cap_type=CapabilityType.SKILL,
                tags=("research", "methodology"),
            )
        )
        reg.add(
            CapabilityEntry(
                name="coding",
                description="Coding standards",
                cap_type=CapabilityType.SKILL,
                tags=("coding",),
            )
        )

        results = reg.search("methodology")
        assert len(results) >= 1
        assert any(e.name == "research" for e in results)


# ======================================================================
# ManifoldToolset — Two-phase discovery
# ======================================================================


class TestManifoldToolset:
    def _make_manifold(self):
        """Create a manifold with some tools registered."""
        tool_reg = ToolRegistry()
        tool_reg.register(_make_tool("web_fetch", "Fetch a URL"))
        tool_reg.register(_make_tool("bash", "Execute shell commands"))
        tool_reg.register(_make_tool("read_file", "Read a file"))

        cap_reg = CapabilityRegistry()
        cap_reg.add_from_tool_registry(tool_reg)

        return ManifoldToolset(cap_reg, tool_reg, max_tools=20)

    def test_discovery_phase_returns_meta_tools(self):
        manifold = self._make_manifold()
        # Mock readonly_context with discovery phase
        ctx = MagicMock()
        ctx.state = {"manifold_phase": "discovery"}

        tools = _run(manifold.get_tools(ctx))
        assert len(tools) == 3  # search, load, finalize

    def test_search_finds_tools(self):
        manifold = self._make_manifold()
        result = manifold.search("fetch URL")
        assert "web_fetch" in result

    def test_search_with_type_filter(self):
        manifold = self._make_manifold()
        result = manifold.search("fetch", cap_type="tool")
        assert "web_fetch" in result

    def test_search_invalid_type(self):
        manifold = self._make_manifold()
        result = manifold.search("fetch", cap_type="invalid")
        assert "Unknown type" in result

    def test_load_capability(self):
        manifold = self._make_manifold()
        result = manifold.load("web_fetch")
        assert "Loaded" in result
        assert "web_fetch" in result

    def test_load_nonexistent(self):
        manifold = self._make_manifold()
        result = manifold.load("nonexistent")
        assert "not found" in result

    def test_load_after_finalize_rejected(self):
        manifold = self._make_manifold()
        manifold.load("web_fetch")
        manifold.finalize()
        result = manifold.load("bash")
        assert "finalized" in result

    def test_finalize_freezes(self):
        manifold = self._make_manifold()
        manifold.load("web_fetch")
        manifold.load("bash")
        result = manifold.finalize()
        assert manifold.is_frozen
        assert "2 capabilities" in result

    def test_execution_phase_returns_loaded_tools(self):
        manifold = self._make_manifold()
        manifold.load("web_fetch")
        manifold.load("bash")
        manifold.finalize()

        ctx = MagicMock()
        ctx.state = {"manifold_phase": "execution"}

        tools = _run(manifold.get_tools(ctx))
        assert len(tools) == 2

    def test_always_loaded(self):
        tool_reg = ToolRegistry()
        tool_reg.register(_make_tool("read_file", "Read files"))
        tool_reg.register(_make_tool("bash", "Shell"))

        cap_reg = CapabilityRegistry()
        cap_reg.add_from_tool_registry(tool_reg)

        manifold = ManifoldToolset(cap_reg, tool_reg, always_loaded=["read_file"])
        manifold.finalize()

        ctx = MagicMock()
        ctx.state = {"manifold_phase": "execution"}
        tools = _run(manifold.get_tools(ctx))
        assert len(tools) == 1  # read_file always loaded

    def test_max_tools_limit(self):
        tool_reg = ToolRegistry()
        for i in range(10):
            tool_reg.register(_make_tool(f"tool_{i}", f"Tool {i}"))

        cap_reg = CapabilityRegistry()
        cap_reg.add_from_tool_registry(tool_reg)

        manifold = ManifoldToolset(cap_reg, tool_reg, max_tools=3)

        # Load 3 tools
        for i in range(3):
            manifold.load(f"tool_{i}")

        # 4th should be rejected
        result = manifold.load("tool_3")
        assert "maximum" in result.lower()

    def test_compiled_skills_empty_before_finalize(self):
        manifold = self._make_manifold()
        assert manifold.compiled_skills == ""

    def test_no_context_defaults_to_discovery(self):
        manifold = self._make_manifold()
        tools = _run(manifold.get_tools(None))
        assert len(tools) == 3  # meta-tools

    def test_frozen_returns_execution_tools(self):
        manifold = self._make_manifold()
        manifold.load("web_fetch")
        manifold.finalize()

        # Even with discovery phase in state, frozen manifold returns execution tools
        ctx = MagicMock()
        ctx.state = {"manifold_phase": "discovery"}
        tools = _run(manifold.get_tools(ctx))
        # After freeze, get_tools returns active tools regardless
        # Actually, the code checks `not self._frozen` first
        assert len(tools) == 1  # web_fetch


# ======================================================================
# ManifoldToolset with MCP entries
# ======================================================================


class TestManifoldMCP:
    def test_mcp_entries_registered(self):
        cap_reg = CapabilityRegistry()
        cap_reg.add_mcp_servers(
            [
                {"name": "fs", "url": "http://localhost:3000/mcp", "description": "Filesystem"},
            ]
        )

        manifold = ManifoldToolset(cap_reg)
        result = manifold.search("filesystem")
        assert "mcp:fs" in result

    def test_mcp_load(self):
        cap_reg = CapabilityRegistry()
        cap_reg.add_mcp_servers(
            [
                {"name": "fs", "url": "http://localhost:3000/mcp"},
            ]
        )

        manifold = ManifoldToolset(cap_reg)
        result = manifold.load("mcp:fs")
        assert "Loaded" in result
        assert "mcp_server" in result


# ======================================================================
# H.manifold() factory
# ======================================================================


class TestHManifold:
    def test_factory_with_tool_registry(self):
        tool_reg = ToolRegistry()
        tool_reg.register(_make_tool("fetch", "Fetch URL"))

        manifold = H.manifold(tools=tool_reg)
        assert isinstance(manifold, ManifoldToolset)

        result = manifold.search("fetch")
        assert "fetch" in result

    def test_factory_with_mcp(self):
        manifold = H.manifold(
            mcp=[
                {"name": "test-server", "url": "http://localhost:3000/mcp"},
            ]
        )
        result = manifold.search("test-server")
        assert "mcp:test-server" in result

    def test_factory_with_mcp_config(self):
        config = {"mcpServers": {"myserver": {"url": "http://localhost:3000/mcp"}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()

            manifold = H.manifold(mcp_config=f.name)
        result = manifold.search("myserver")
        assert "mcp:myserver" in result

    def test_factory_with_always_loaded(self):
        tool_reg = ToolRegistry()
        tool_reg.register(_make_tool("core_tool", "Always needed"))

        manifold = H.manifold(tools=tool_reg, always_loaded=["core_tool"])
        manifold.finalize()

        ctx = MagicMock()
        ctx.state = {"manifold_phase": "execution"}
        tools = _run(manifold.get_tools(ctx))
        assert len(tools) == 1

    def test_factory_empty(self):
        manifold = H.manifold()
        assert isinstance(manifold, ManifoldToolset)
        result = manifold.search("anything")
        assert "No capabilities" in result


# ======================================================================
# Event types
# ======================================================================


class TestManifoldEvents:
    def test_capability_loaded_event(self):
        event = CapabilityLoaded(
            capability_name="web_fetch",
            cap_type="tool",
        )
        assert event.kind == "capability_loaded"
        assert event.capability_name == "web_fetch"
        assert event.cap_type == "tool"

    def test_manifold_finalized_event(self):
        event = ManifoldFinalized(
            tool_count=5,
            skill_count=2,
            mcp_count=1,
        )
        assert event.kind == "manifold_finalized"
        assert event.tool_count == 5
        assert event.skill_count == 2
        assert event.mcp_count == 1

    def test_events_are_frozen(self):
        event = CapabilityLoaded(capability_name="test", cap_type="tool")
        with pytest.raises(AttributeError):
            event.capability_name = "changed"  # type: ignore[misc]


# ======================================================================
# Integration: full discovery → execution flow
# ======================================================================


class TestManifoldIntegration:
    def test_full_discovery_flow(self):
        """Test the complete two-phase discovery flow."""
        # Setup: register tools
        tool_reg = ToolRegistry()
        tool_reg.register(_make_tool("web_fetch", "Fetch web pages"))
        tool_reg.register(_make_tool("bash", "Execute shell commands"))
        tool_reg.register(_make_tool("read_file", "Read a file"))
        tool_reg.register(_make_tool("edit_file", "Edit a file"))
        tool_reg.register(_make_tool("grep_search", "Search file contents"))

        # Create manifold via H.manifold()
        manifold = H.manifold(tools=tool_reg, max_tools=10)

        # Phase 1: Discovery — get meta-tools
        ctx = MagicMock()
        ctx.state = {"manifold_phase": "discovery"}
        meta_tools = _run(manifold.get_tools(ctx))
        assert len(meta_tools) == 3

        # LLM searches for capabilities
        search_result = manifold.search("file operations")
        assert "read_file" in search_result or "edit_file" in search_result

        # LLM loads what it needs
        assert "Loaded" in manifold.load("read_file")
        assert "Loaded" in manifold.load("edit_file")
        assert "Loaded" in manifold.load("bash")

        # LLM finalizes
        finalize_result = manifold.finalize()
        assert "3 capabilities" in finalize_result
        assert manifold.is_frozen

        # Phase 2: Execution — get active tools
        ctx.state = {"manifold_phase": "execution"}
        active_tools = _run(manifold.get_tools(ctx))
        assert len(active_tools) == 3

    def test_mixed_capabilities(self):
        """Test manifold with tools and MCP servers."""
        tool_reg = ToolRegistry()
        tool_reg.register(_make_tool("local_search", "Search local files"))

        cap_reg = CapabilityRegistry()
        cap_reg.add_from_tool_registry(tool_reg)
        cap_reg.add_mcp_servers(
            [
                {"name": "remote-search", "url": "http://search:3000/mcp", "description": "Remote search API"},
            ]
        )

        manifold = ManifoldToolset(cap_reg, tool_reg)

        # Unified search finds both types
        result = manifold.search("search")
        assert "local_search" in result
        assert "mcp:remote-search" in result

    def test_discovery_phase_state_key_fallback(self):
        """Test that manifold_phase falls back to toolset_phase."""
        manifold = ManifoldToolset(CapabilityRegistry())

        ctx = MagicMock()
        ctx.state = {"toolset_phase": "discovery"}
        tools = _run(manifold.get_tools(ctx))
        assert len(tools) == 3  # meta-tools (search, load, finalize)
