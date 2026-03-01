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


class _SchemaMarker:
    """Internal marker for T.schema() -- carries schema class through composition."""

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
    def google_search() -> TComposite:
        """Google Search tool."""
        from google.adk.tools.google_search_tool import google_search

        return TComposite([google_search])

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
        discovery -> loading -> freezing lifecycle.
        """
        from adk_fluent._tool_registry import SearchToolset

        toolset = SearchToolset(registry, always_loaded=always_loaded, max_tools=max_tools)
        return TComposite([toolset])

    # --- Contract checking ---

    @staticmethod
    def schema(schema_cls: type) -> TComposite:
        """Attach a ToolSchema for contract checking.

        When piped into a tool chain, this marker is extracted during
        IR conversion and wired to ``AgentNode.tool_schema``.
        """
        return TComposite([_SchemaMarker(schema_cls)])
