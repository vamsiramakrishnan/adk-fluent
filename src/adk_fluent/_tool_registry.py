"""ToolRegistry -- BM25-indexed catalog for tool discovery.

``rank_bm25`` is an optional dependency (``pip install adk-fluent[search]``).
Falls back to substring matching if not installed.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.function_tool import FunctionTool

__all__ = [
    "ToolRegistry",
    "SearchToolset",
    "search_aware_after_tool",
    "compress_large_result",
]

try:
    from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

    _HAS_BM25 = True
except ImportError:
    BM25Okapi = None  # type: ignore[assignment,misc]
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
        if corpus and BM25Okapi is not None:
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
                    results.append({"name": name, "description": self._descriptions.get(name, "")})
            if results:
                return results
            # BM25 returned nothing (e.g. single-doc corpus → IDF=0); fall through

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
        search_tool = FunctionTool(func=self._make_search_fn())
        load_tool = FunctionTool(func=self._make_load_fn())
        finalize_tool = FunctionTool(func=self._make_finalize_fn())
        return [search_tool, load_tool, finalize_tool]

    def _make_search_fn(self):
        """Create the search_tools meta-tool function."""
        registry = self._registry

        def search_tools(query: str) -> str:
            """Search available tools by description. Returns summaries of matching tools."""
            results = registry.search(query)
            if not results:
                return "No tools found matching your query."
            lines = []
            for r in results:
                lines.append(f"- {r['name']}: {r['description']}")
            return "\n".join(lines)

        return search_tools

    def _make_load_fn(self):
        """Create the load_tool meta-tool function."""
        toolset = self

        def load_tool(tool_name: str) -> str:
            """Load a tool by name into the active toolset."""
            tool = toolset._registry.get_tool(tool_name)
            if tool is None:
                return f"Tool '{tool_name}' not found in registry."
            if toolset._frozen:
                return "Toolset is frozen. Cannot load more tools."
            if len(toolset._loaded_names) >= toolset._max_tools:
                return f"Maximum tools ({toolset._max_tools}) already loaded."
            toolset._loaded_names.add(tool_name)
            return f"Tool '{tool_name}' loaded successfully."

        return load_tool

    def _make_finalize_fn(self):
        """Create the finalize_tools meta-tool function."""
        toolset = self

        def finalize_tools() -> str:
            """Finalize the toolset. No more tools can be added after this."""
            toolset._frozen = True
            loaded = sorted(toolset._loaded_names | toolset._always_loaded)
            return f"Toolset finalized with {len(loaded)} tools: {', '.join(loaded)}"

        return finalize_tools

    # Convenience methods for direct testing (not via FunctionTool)
    def _search_fn(self, query: str) -> str:
        """Direct search -- for testing."""
        return self._make_search_fn()(query)

    def _load_fn(self, tool_name: str) -> str:
        """Direct load -- for testing."""
        return self._make_load_fn()(tool_name)

    def _finalize_fn(self) -> str:
        """Direct finalize -- for testing."""
        return self._make_finalize_fn()()

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
    1. Large result compression (results > threshold -> temp file)
    2. Error preservation (failed calls annotated, NOT silently retried)
    3. Result variation (subtle formatting per call index)
    """
    if tool_response is None:
        return tool_response

    result_str = str(tool_response)

    # Compress large results
    result_str = compress_large_result(result_str, threshold=compress_threshold)

    return result_str
