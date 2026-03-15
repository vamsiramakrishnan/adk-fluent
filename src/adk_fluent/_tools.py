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

__all__ = [
    "T",
    "TComposite",
    "_ConfirmWrapper",
    "_TimeoutWrapper",
    "_CachedWrapper",
    "_TransformWrapper",
]


class TComposite:
    """Composable tool chain. The result of any ``T.xxx()`` call.

    Supports ``|`` for composition::

        T.fn(search) | T.fn(email) | T.google_search()
    """

    def __init__(self, items: list[Any] | None = None, *, kind: str = "tool_chain"):
        self._items: list[Any] = list(items or [])
        self.__kind = kind

    # ------------------------------------------------------------------
    # NamespaceSpec protocol
    # ------------------------------------------------------------------

    @property
    def _kind(self) -> str:
        """Discriminator tag for IR serialization."""
        return self.__kind

    def _as_list(self) -> tuple[Any, ...]:
        """Flatten for composite building."""
        return tuple(self._items)

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """Tools are opaque to state — always returns ``None``."""
        return None

    @property
    def _writes_keys(self) -> frozenset[str] | None:
        """Tools are opaque to state — always returns ``None``."""
        return None

    # ------------------------------------------------------------------
    # Composition: | (chain)
    # ------------------------------------------------------------------

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
            return TComposite([func_or_tool], kind="fn")
        from google.adk.tools.function_tool import FunctionTool

        if confirm:
            return TComposite([FunctionTool(func=func_or_tool, require_confirmation=True)], kind="fn")
        return TComposite([FunctionTool(func=func_or_tool)], kind="fn")

    @staticmethod
    def agent(agent_or_builder: Any) -> TComposite:
        """Wrap an agent (or builder) as an AgentTool."""
        from google.adk.tools.agent_tool import AgentTool

        built = (
            agent_or_builder.build()
            if hasattr(agent_or_builder, "build") and hasattr(agent_or_builder, "_config")
            else agent_or_builder
        )
        return TComposite([AgentTool(agent=built)], kind="agent")

    @staticmethod
    def toolset(ts: Any) -> TComposite:
        """Wrap any ADK toolset (MCPToolset, etc.)."""
        return TComposite([ts], kind="toolset")

    # --- Built-in tool groups ---

    @staticmethod
    def google_search() -> TComposite:
        """Google Search tool."""
        from google.adk.tools.google_search_tool import google_search

        return TComposite([google_search], kind="google_search")

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
        return TComposite([toolset], kind="search")

    # --- Contract checking ---

    @staticmethod
    def schema(schema_cls: type) -> TComposite:
        """Attach a ToolSchema for contract checking.

        When piped into a tool chain, this marker is extracted during
        IR conversion and wired to ``AgentNode.tool_schema``.
        """
        return TComposite([_SchemaMarker(schema_cls)], kind="schema")

    # --- Mock ---

    @staticmethod
    def mock(name: str, *, returns: Any = None, side_effect: Any = None) -> TComposite:
        """Create a mock tool that returns a fixed value or side-effect.

        Args:
            name: Name for the mock tool.
            returns: Value to return (ignored if *side_effect* is set).
            side_effect: Callable or static value used instead of *returns*.
        """
        return TComposite(
            [_MockWrapper(name, returns=returns, side_effect=side_effect)],
            kind="mock",
        )

    # --- Confirm ---

    @staticmethod
    def confirm(tool_or_composite: TComposite | Any, message: str | None = None) -> TComposite:
        """Wrap tool(s) with a confirmation requirement.

        Each tool in the composite is individually wrapped so that
        ``require_confirmation`` is set.
        """
        items = tool_or_composite._items if isinstance(tool_or_composite, TComposite) else [tool_or_composite]
        wrapped = [_ConfirmWrapper(item, message) for item in items]
        return TComposite(wrapped, kind="confirm")

    # --- Timeout ---

    @staticmethod
    def timeout(tool_or_composite: TComposite | Any, seconds: float = 30) -> TComposite:
        """Wrap tool(s) with a per-invocation timeout."""
        items = tool_or_composite._items if isinstance(tool_or_composite, TComposite) else [tool_or_composite]
        wrapped = [_TimeoutWrapper(item, seconds) for item in items]
        return TComposite(wrapped, kind="timeout")

    # --- Cache ---

    @staticmethod
    def cache(
        tool_or_composite: TComposite | Any,
        ttl: float = 300,
        key_fn: Any = None,
    ) -> TComposite:
        """Wrap tool(s) with a TTL-based result cache."""
        items = tool_or_composite._items if isinstance(tool_or_composite, TComposite) else [tool_or_composite]
        wrapped = [_CachedWrapper(item, ttl, key_fn) for item in items]
        return TComposite(wrapped, kind="cache")

    # --- MCP ---

    @staticmethod
    def mcp(
        url_or_params: Any,
        *,
        tool_filter: Any = None,
        prefix: str | None = None,
    ) -> TComposite:
        """Thin factory over :class:`McpToolset` builder."""
        from adk_fluent.tool import McpToolset

        builder = McpToolset().connection_params(url_or_params)  # type: ignore[reportAttributeAccessIssue]
        if tool_filter is not None:
            builder = builder.tool_filter(tool_filter)
        if prefix is not None:
            builder = builder.tool_name_prefix(prefix)
        return TComposite([builder.build()], kind="mcp")

    # --- OpenAPI ---

    @staticmethod
    def openapi(
        spec: Any,
        *,
        tool_filter: Any = None,
        auth: Any = None,
    ) -> TComposite:
        """Thin factory over :class:`OpenAPIToolset` builder."""
        from adk_fluent.tool import OpenAPIToolset

        builder = OpenAPIToolset().spec_dict(spec)
        if tool_filter is not None:
            builder = builder.tool_filter(tool_filter)
        if auth is not None:
            builder = builder.auth_credential(auth)
        return TComposite([builder.build()], kind="openapi")

    # --- A2A ---

    @staticmethod
    def a2a(
        agent_card: str | Any,
        *,
        name: str = "remote_agent",
        description: str = "",
        timeout: float = 600.0,
    ) -> TComposite:
        """Wrap a remote A2A agent as a tool (``AgentTool`` around ``RemoteA2aAgent``).

        Creates a ``RemoteAgent`` builder, builds it into a native
        ``RemoteA2aAgent``, wraps it in an ``AgentTool``, and returns
        a ``TComposite`` for composition with ``|``.

        Requires ``pip install adk-fluent[a2a]``.

        Args:
            agent_card: URL to ``/.well-known/agent.json``, file path, or
                ``AgentCard`` object.
            name: Agent name (used by the parent LLM for tool selection).
            description: Tool description shown to the LLM.
            timeout: HTTP timeout in seconds (default 600).

        Usage::

            agent.tools(T.a2a("http://research:8001", name="research"))
        """
        from adk_fluent.a2a import RemoteAgent

        remote = RemoteAgent(name, agent_card).describe(description).timeout(timeout)
        built = remote.build()

        from google.adk.tools.agent_tool import AgentTool

        return TComposite([AgentTool(agent=built)], kind="a2a")

    # --- Transform ---

    @staticmethod
    def transform(
        tool_or_composite: TComposite | Any,
        *,
        pre: Any = None,
        post: Any = None,
    ) -> TComposite:
        """Wrap tool(s) with pre/post argument/result transforms."""
        items = tool_or_composite._items if isinstance(tool_or_composite, TComposite) else [tool_or_composite]
        wrapped = [_TransformWrapper(item, pre, post) for item in items]
        return TComposite(wrapped, kind="transform")


# ---------------------------------------------------------------------------
# Wrapper classes (module-level, outside T)
# ---------------------------------------------------------------------------


class _MockWrapper:
    """A mock tool that returns a fixed value or calls a side-effect."""

    def __init__(self, name: str, *, returns: Any = None, side_effect: Any = None):
        self.name = name
        self.description = f"Mock tool: {name}"
        self._returns = returns
        self._side_effect = side_effect

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:  # noqa: ANN401
        """Return configured value or invoke side-effect."""
        if self._side_effect is not None:
            return self._side_effect(**args) if callable(self._side_effect) else self._side_effect
        return self._returns


class _ConfirmWrapper:
    """Wraps a tool to require user confirmation before execution."""

    def __init__(self, inner: Any, message: str | None = None):
        from google.adk.tools.base_tool import BaseTool

        self._inner = inner
        self._message = message
        if isinstance(inner, BaseTool):
            self.name = inner.name
            self.description = inner.description
        else:
            self.name = getattr(inner, "__name__", "tool")
            self.description = getattr(inner, "__doc__", "") or ""
        self.require_confirmation = True

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:  # noqa: ANN401
        """Delegate to inner tool."""
        if hasattr(self._inner, "run_async"):
            return await self._inner.run_async(args=args, tool_context=tool_context)
        return self._inner(**args)


class _TimeoutWrapper:
    """Wraps a tool with an asyncio timeout."""

    def __init__(self, inner: Any, seconds: float):
        self._inner = inner
        self._seconds = seconds
        self.name = getattr(inner, "name", getattr(inner, "__name__", "tool"))
        self.description = getattr(inner, "description", getattr(inner, "__doc__", "") or "")

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:  # noqa: ANN401
        """Delegate with timeout."""
        import asyncio

        if hasattr(self._inner, "run_async"):
            return await asyncio.wait_for(
                self._inner.run_async(args=args, tool_context=tool_context),
                timeout=self._seconds,
            )
        return self._inner(**args)


class _CachedWrapper:
    """Wraps a tool with a TTL-based in-memory cache."""

    def __init__(self, inner: Any, ttl: float, key_fn: Any = None):
        self._inner = inner
        self._ttl = ttl
        self._key_fn = key_fn or (lambda args: str(sorted(args.items())))
        self._cache: dict[str, tuple[Any, float]] = {}
        self.name = getattr(inner, "name", getattr(inner, "__name__", "tool"))
        self.description = getattr(inner, "description", getattr(inner, "__doc__", "") or "")

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:  # noqa: ANN401
        """Return cached result if fresh, otherwise invoke and cache."""
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


class _TransformWrapper:
    """Wraps a tool with pre/post argument/result transforms."""

    def __init__(self, inner: Any, pre: Any = None, post: Any = None):
        self._inner = inner
        self._pre = pre
        self._post = post
        self.name = getattr(inner, "name", getattr(inner, "__name__", "tool"))
        self.description = getattr(inner, "description", getattr(inner, "__doc__", "") or "")

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:  # noqa: ANN401
        """Apply pre-transform, invoke, apply post-transform."""
        if self._pre is not None:
            args = self._pre(args)
        if hasattr(self._inner, "run_async"):
            result = await self._inner.run_async(args=args, tool_context=tool_context)
        else:
            result = self._inner(**args)
        if self._post is not None:
            result = self._post(result)
        return result
