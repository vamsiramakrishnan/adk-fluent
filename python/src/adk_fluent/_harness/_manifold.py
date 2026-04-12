"""Manifold — unified runtime capability discovery.

Claude Code and Gemini CLI dynamically discover and load capabilities
at runtime: tools via search, skills via SKILL.md scanning, MCP servers
via config files. The manifold unifies these into a single two-phase
discovery surface that the LLM navigates through meta-tools.

The pattern extends ``SearchToolset``'s proven two-phase approach:

**Phase 1 (Discovery):** The LLM gets meta-tools to search and load
capabilities across all types — tools, skills, and MCP servers —
through one unified search interface.

**Phase 2 (Execution):** Loaded capabilities are frozen into a stable
tool list. Skills become ``static_instruction``. MCP tools join the
active set. KV-cache stable.

Composes with existing building blocks:
    - ``ToolRegistry`` for BM25-indexed tool search
    - ``SkillRegistry`` for SKILL.md scanning
    - ``SkillSpec`` / ``compile_skills_to_static`` for skill compilation
    - ``McpToolset`` builder for MCP server wiring
    - ``SearchToolset`` two-phase pattern (extended, not replaced)

Usage::

    manifold = H.manifold(
        tools=ToolRegistry.from_tools(fn1, fn2, fn3),
        skills="skills/",
        mcp_config="/project/.agent/mcp.json",
    )

    agent = (
        Agent("coder", "gemini-2.5-pro")
        .tools(manifold)
        .instruct("You are a coding assistant.")
    )
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = [
    "CapabilityType",
    "CapabilityEntry",
    "CapabilityRegistry",
    "ManifoldToolset",
]


class CapabilityType(Enum):
    """Type of discoverable capability."""

    TOOL = "tool"
    SKILL = "skill"
    MCP_SERVER = "mcp_server"


@dataclass(frozen=True, slots=True)
class CapabilityEntry:
    """A discoverable capability in the manifold.

    Uniform representation across tools, skills, and MCP servers.
    The manifold indexes these for unified BM25 search.
    """

    name: str
    description: str
    cap_type: CapabilityType
    tags: tuple[str, ...] = ()
    # Opaque reference for the loader (tool name, skill path, mcp spec)
    _ref: Any = None


class CapabilityRegistry:
    """Unified catalog of tools, skills, and MCP servers.

    Indexes all capability types into a single BM25-searchable catalog.
    Composes with existing ``ToolRegistry`` and ``SkillRegistry`` —
    does not replace them, but wraps their discovery APIs.
    """

    def __init__(self) -> None:
        self._entries: dict[str, CapabilityEntry] = {}
        self._bm25: Any = None
        self._corpus_names: list[str] = []

    def add(self, entry: CapabilityEntry) -> None:
        """Register a capability entry."""
        self._entries[entry.name] = entry
        self._bm25 = None  # invalidate

    def add_from_tool_registry(self, registry: Any) -> None:
        """Import all tools from an existing ``ToolRegistry``.

        Reuses the registry's descriptions. Each tool becomes a
        ``CapabilityEntry`` with ``cap_type=TOOL``.
        """
        for name in list(registry._tools.keys()):
            desc = registry._descriptions.get(name, "")
            self.add(
                CapabilityEntry(
                    name=name,
                    description=desc,
                    cap_type=CapabilityType.TOOL,
                    _ref=name,
                )
            )

    def add_from_skill_registry(self, registry: Any) -> None:
        """Import all skills from an existing ``SkillRegistry``.

        Each skill becomes a ``CapabilityEntry`` with ``cap_type=SKILL``.
        """
        for info in registry.list():
            self.add(
                CapabilityEntry(
                    name=info["name"],
                    description=info.get("description", ""),
                    cap_type=CapabilityType.SKILL,
                    tags=tuple(info.get("tags", [])),
                    _ref=info.get("path"),
                )
            )

    def add_mcp_servers(self, servers: list[dict[str, Any]]) -> None:
        """Register MCP server specs for runtime discovery.

        Each server spec becomes a ``CapabilityEntry`` with
        ``cap_type=MCP_SERVER``. The LLM can load them on demand.
        """
        for spec in servers:
            name = spec.get("name", spec.get("url", spec.get("command", "mcp")))
            desc = spec.get("description", f"MCP server: {name}")
            self.add(
                CapabilityEntry(
                    name=f"mcp:{name}",
                    description=desc,
                    cap_type=CapabilityType.MCP_SERVER,
                    _ref=spec,
                )
            )

    def add_mcp_config(self, config_path: str | Path) -> None:
        """Register MCP servers from a JSON config file.

        Supports Claude Code format (``mcpServers`` dict) and
        array format. Delegates parsing to ``_mcp.load_mcp_config``
        logic but only registers entries — does not build tools yet.
        """
        import json

        path = Path(config_path)
        if not path.exists():
            return

        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        # Extract server specs (same logic as _mcp.load_mcp_config)
        raw = data.get("mcpServers", data.get("servers", data))
        if isinstance(raw, dict):
            servers = []
            for name, spec in raw.items():
                spec_copy = dict(spec)
                spec_copy.setdefault("name", name)
                servers.append(spec_copy)
        elif isinstance(raw, list):
            servers = raw
        else:
            return

        self.add_mcp_servers(servers)

    def _ensure_index(self) -> None:
        """Build BM25 index over all entries."""
        if self._bm25 is not None:
            return

        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]
        except ImportError:
            return

        self._corpus_names = list(self._entries.keys())
        corpus = []
        for name in self._corpus_names:
            entry = self._entries[name]
            text = f"{name} {entry.description} {' '.join(entry.tags)}"
            corpus.append(text.lower().split())

        if corpus:
            self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 10) -> list[CapabilityEntry]:
        """Search across all capability types.

        Uses BM25 when available, falls back to substring matching.
        """
        if not self._entries:
            return []

        self._ensure_index()

        if self._bm25 is not None:
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
                    results.append(self._entries[name])
            if results:
                return results

        # Substring fallback
        query_lower = query.lower()
        matches = []
        for name, entry in self._entries.items():
            text = f"{name} {entry.description} {' '.join(entry.tags)}".lower()
            if any(word in text for word in query_lower.split()):
                matches.append(entry)
        return matches[:top_k]

    def search_by_type(
        self,
        query: str,
        cap_type: CapabilityType,
        top_k: int = 10,
    ) -> list[CapabilityEntry]:
        """Search within a specific capability type."""
        return [e for e in self.search(query, top_k=top_k * 2) if e.cap_type == cap_type][:top_k]

    def get(self, name: str) -> CapabilityEntry | None:
        """Get a capability entry by name."""
        return self._entries.get(name)

    def list_by_type(self, cap_type: CapabilityType) -> list[CapabilityEntry]:
        """List all entries of a given type."""
        return [e for e in self._entries.values() if e.cap_type == cap_type]

    @property
    def size(self) -> int:
        """Total number of registered capabilities."""
        return len(self._entries)


class ManifoldToolset:
    """Two-phase runtime capability discovery across tools, skills, and MCP.

    Extends the ``SearchToolset`` pattern to a unified discovery surface.
    In discovery phase, the LLM gets meta-tools to search across all
    capability types, load specific capabilities, and finalize the active
    set.

    On finalization:
    - Loaded tools → added to the active tool list
    - Loaded skills → compiled to ``static_instruction`` (available via
      ``.compiled_skills``)
    - Loaded MCP servers → resolved via ``McpToolset`` builder, tools
      added to the active set

    Args:
        registry: Unified capability registry.
        tool_registry: Existing ToolRegistry for resolving tool refs.
        always_loaded: Capabilities to always include.
        max_tools: Maximum tools in the active set.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        tool_registry: Any | None = None,
        *,
        always_loaded: list[str] | None = None,
        max_tools: int = 30,
    ) -> None:
        self._registry = registry
        self._tool_registry = tool_registry
        self._always_loaded = set(always_loaded or [])
        self._max_tools = max_tools
        self._loaded_names: set[str] = set()
        self._frozen = False
        self._meta_tools: list[Any] | None = None
        # Outputs populated on finalize
        self._compiled_skills: str = ""
        self._active_tools: list[Any] = []

    @property
    def compiled_skills(self) -> str:
        """Compiled skill XML for ``static_instruction``, available after finalize."""
        return self._compiled_skills

    @property
    def is_frozen(self) -> bool:
        """Whether the manifold has been finalized."""
        return self._frozen

    def unfreeze(self) -> None:
        """Unfreeze the manifold for another discovery cycle.

        Resets to discovery phase while keeping previously loaded
        capabilities. New capabilities can be searched and loaded,
        then ``finalize()`` freezes again. Enables hot-reload::

            manifold.unfreeze()
            manifold.load("new_mcp:server")
            manifold.finalize()
        """
        self._frozen = False
        self._meta_tools = None  # rebuild meta-tools on next get_tools
        self._active_tools = []
        self._compiled_skills = ""

    def add_capability(self, entry: CapabilityEntry) -> None:
        """Add a capability to the registry at runtime.

        Can be called between unfreeze/finalize cycles to register
        new capabilities discovered mid-session.

        Args:
            entry: New capability entry to register.
        """
        self._registry.add(entry)

    def _build_meta_tools(self) -> list[Any]:
        """Build the discovery meta-tools."""
        from google.adk.tools.function_tool import FunctionTool

        return [
            FunctionTool(func=self._make_search_fn()),
            FunctionTool(func=self._make_load_fn()),
            FunctionTool(func=self._make_finalize_fn()),
        ]

    def _make_search_fn(self) -> Callable:
        """Create the unified search meta-tool."""
        registry = self._registry

        def search_capabilities(query: str, cap_type: str = "") -> str:
            """Search available capabilities (tools, skills, MCP servers).

            Returns matching capabilities across all types. Optionally
            filter by type: "tool", "skill", or "mcp_server".

            Args:
                query: Natural language search query.
                cap_type: Optional filter: "tool", "skill", "mcp_server", or "" for all.
            """
            if cap_type:
                try:
                    ct = CapabilityType(cap_type)
                    results = registry.search_by_type(query, ct)
                except ValueError:
                    return f"Unknown type '{cap_type}'. Use: tool, skill, mcp_server"
            else:
                results = registry.search(query)

            if not results:
                return "No capabilities found matching your query."

            lines = []
            for entry in results:
                tags_str = f" [{', '.join(entry.tags)}]" if entry.tags else ""
                lines.append(f"- [{entry.cap_type.value}] {entry.name}: {entry.description}{tags_str}")
            return "\n".join(lines)

        return search_capabilities

    def _make_load_fn(self) -> Callable:
        """Create the load meta-tool."""
        manifold = self

        def load_capability(name: str) -> str:
            """Load a capability by name into the active set.

            Load tools, skills, or MCP servers discovered via
            ``search_capabilities``. Use the exact name from search results.

            Args:
                name: Exact capability name from search results.
            """
            if manifold._frozen:
                return "Error: manifold is finalized. Cannot load more capabilities."

            entry = manifold._registry.get(name)
            if entry is None:
                return f"Error: capability '{name}' not found."

            if len(manifold._loaded_names) >= manifold._max_tools:
                return f"Error: maximum capabilities ({manifold._max_tools}) reached."

            manifold._loaded_names.add(name)
            return f"Loaded [{entry.cap_type.value}] '{name}'. Call finalize_capabilities() when done loading."

        return load_capability

    def _make_finalize_fn(self) -> Callable:
        """Create the finalize meta-tool."""
        manifold = self

        def finalize_capabilities() -> str:
            """Finalize the capability set. No more capabilities can be loaded after this.

            Compiles loaded skills into static instruction, resolves MCP
            servers, and freezes the active tool list.
            """
            manifold._frozen = True
            all_names = manifold._loaded_names | manifold._always_loaded
            manifold._resolve_capabilities(all_names)

            # Summary
            tools = [
                n for n in all_names if (entry := manifold._registry.get(n)) and entry.cap_type == CapabilityType.TOOL
            ]
            skills = [
                n for n in all_names if (entry := manifold._registry.get(n)) and entry.cap_type == CapabilityType.SKILL
            ]
            mcps = [
                n
                for n in all_names
                if (entry := manifold._registry.get(n)) and entry.cap_type == CapabilityType.MCP_SERVER
            ]

            parts = [f"Manifold finalized with {len(all_names)} capabilities:"]
            if tools:
                parts.append(f"  Tools ({len(tools)}): {', '.join(sorted(tools))}")
            if skills:
                parts.append(f"  Skills ({len(skills)}): {', '.join(sorted(skills))}")
            if mcps:
                parts.append(f"  MCP servers ({len(mcps)}): {', '.join(sorted(mcps))}")
            return "\n".join(parts)

        return finalize_capabilities

    def _resolve_capabilities(self, names: set[str]) -> None:
        """Resolve loaded capabilities into active tools and compiled skills."""
        from adk_fluent._harness._skills import SkillSpec, compile_skills_to_static

        skill_specs: list[SkillSpec] = []
        tools: list[Any] = []

        for name in sorted(names):
            entry = self._registry.get(name)
            if entry is None:
                continue

            if entry.cap_type == CapabilityType.TOOL:
                tool = self._resolve_tool(entry)
                if tool is not None:
                    tools.append(tool)

            elif entry.cap_type == CapabilityType.SKILL:
                spec = self._resolve_skill(entry)
                if spec is not None:
                    skill_specs.append(spec)

            elif entry.cap_type == CapabilityType.MCP_SERVER:
                mcp_tools = self._resolve_mcp(entry)
                tools.extend(mcp_tools)

        self._active_tools = tools[: self._max_tools]
        self._compiled_skills = compile_skills_to_static(skill_specs)

    def _resolve_tool(self, entry: CapabilityEntry) -> Any | None:
        """Resolve a tool entry to an actual tool object."""
        if self._tool_registry is not None:
            return self._tool_registry.get_tool(entry._ref or entry.name)
        return None

    def _resolve_skill(self, entry: CapabilityEntry) -> Any | None:
        """Resolve a skill entry to a SkillSpec."""
        from adk_fluent._harness._skills import SkillSpec

        ref = entry._ref
        if ref and Path(str(ref)).exists():
            try:
                return SkillSpec.from_path(ref)
            except Exception:
                return None
        return None

    def _resolve_mcp(self, entry: CapabilityEntry) -> list[Any]:
        """Resolve an MCP server entry to tool objects."""
        from adk_fluent._harness._mcp import load_mcp_tools

        spec = entry._ref
        if isinstance(spec, dict):
            return load_mcp_tools([spec])
        return []

    async def get_tools(self, readonly_context: Any = None) -> list[Any]:
        """Return tools based on current phase.

        Discovery phase: returns meta-tools (search, load, finalize).
        Execution phase: returns frozen active tool list.

        Compatible with ADK's ``BaseToolset.get_tools()`` protocol.
        """
        state = getattr(readonly_context, "state", {})
        phase = state.get("manifold_phase", state.get("toolset_phase", "discovery"))

        if phase == "discovery" and not self._frozen:
            if self._meta_tools is None:
                self._meta_tools = self._build_meta_tools()
            return self._meta_tools

        return list(self._active_tools)

    # -- Direct access for testing / programmatic use --

    def search(self, query: str, cap_type: str = "") -> str:
        """Direct search (bypasses FunctionTool wrapper)."""
        return self._make_search_fn()(query, cap_type)

    def load(self, name: str) -> str:
        """Direct load (bypasses FunctionTool wrapper)."""
        return self._make_load_fn()(name)

    def finalize(self) -> str:
        """Direct finalize (bypasses FunctionTool wrapper)."""
        return self._make_finalize_fn()()
