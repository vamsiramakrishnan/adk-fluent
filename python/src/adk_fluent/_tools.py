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

from cachetools import TTLCache as _TTLCache

from adk_fluent._composite import Composite

__all__ = [
    "T",
    "TComposite",
    "_ConfirmWrapper",
    "_TimeoutWrapper",
    "_CachedWrapper",
    "_EffectfulWrapper",
    "_TransformWrapper",
]


class TComposite(Composite, kind="tool_chain"):
    """Composable tool chain. The result of any ``T.xxx()`` call.

    Supports ``|`` for composition, and ``>>`` to attach to a builder::

        agent = T.fn(search) | T.fn(email) >> Agent("x", "gemini-2.5-flash")
        # equivalent to: Agent(...).tools(T.fn(search) | T.fn(email))
    """

    _builder_attach_method = "tools"

    def to_tools(self) -> list[Any]:
        """Flatten to ADK-compatible tool/toolset list.

        Auto-wraps plain callables in FunctionTool.
        """
        return list(self._items)


class _SchemaMarker:
    """Internal marker for T.schema() -- carries schema class through composition."""

    def __init__(self, schema_cls: type):
        self._schema_cls = schema_cls

    def __repr__(self) -> str:
        return f"_SchemaMarker({self._schema_cls.__name__})"


class _FluxA2UIToolset:
    """Minimal toolset marker returned by ``T.a2ui(catalog="flux")``.

    Carries flux component factory metadata (description, examples,
    antiPatterns) loaded from ``catalog/flux/catalog.json`` so the LLM-facing
    schema advertises the full flux surface without requiring the external
    ``a2ui-agent`` dependency.

    This is a data-bearing marker, not an ADK Toolset — the ADK-facing
    integration (mapping each flux factory to a runtime tool) will land
    alongside the public ``a2ui-agent[flux]`` package. Today the marker is
    enough for ``T.a2ui(catalog="flux")`` to be discoverable and testable.
    """

    __slots__ = ("catalog", "components", "llm_metadata", "_schema")

    def __init__(self, *, schema: Any = None) -> None:
        import json
        from pathlib import Path

        self.catalog = "flux"
        self._schema = schema

        catalog_path = Path(__file__).resolve().parent.parent.parent.parent / "catalog/flux/catalog.json"
        if catalog_path.is_file():
            try:
                catalog_data = json.loads(catalog_path.read_text())
            except (OSError, ValueError):
                catalog_data = {"components": {}}
        else:
            catalog_data = {"components": {}}

        components = catalog_data.get("components", {}) or {}
        self.components = tuple(sorted(components.keys()))
        self.llm_metadata = {name: block.get("llm", {}) for name, block in components.items()}

    @property
    def description(self) -> str:
        """LLM-facing description enumerating the flux component surface."""
        parts = [
            "Flux catalog toolset. Emit A2UI nodes for the following components:",
        ]
        for name in self.components:
            meta = self.llm_metadata.get(name, {})
            desc = (meta.get("description") or "").strip().splitlines()[0:1]
            desc_line = desc[0] if desc else ""
            parts.append(f"- {name}: {desc_line}")
        return "\n".join(parts)

    def __repr__(self) -> str:
        return f"_FluxA2UIToolset(components={len(self.components)})"


def _build_flux_a2ui_toolset(*, schema: Any = None) -> TComposite:
    """Build a TComposite wrapping the flux toolset marker.

    Exposed for T.a2ui(catalog="flux"). Does not require the ``a2ui-agent``
    package because flux factories live in-tree under ``adk_fluent._flux_gen``.
    """
    return TComposite([_FluxA2UIToolset(schema=schema)], kind="a2ui_flux")


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

    # --- A2A ---

    @staticmethod
    def a2a(
        agent_card_url: str,
        *,
        name: str | None = None,
        description: str | None = None,
        timeout: float = 600.0,
    ) -> TComposite:
        """Wrap a remote A2A agent as an AgentTool.

        This is useful when you want the LLM to invoke a remote agent
        as a tool (structured I/O) rather than delegating to it as a
        sub-agent (opaque autonomous task).

        Args:
            agent_card_url: Base URL or full card URL of the remote agent.
            name: Override the agent name (defaults to remote agent's name).
            description: Override the agent description.
            timeout: HTTP timeout in seconds.
        """
        from google.adk.tools.agent_tool import AgentTool

        from adk_fluent.a2a import RemoteAgent

        builder = RemoteAgent(name or "remote_a2a", agent_card_url).timeout(timeout)
        if description:
            builder = builder.describe(description)
        built = builder.build()
        return TComposite([AgentTool(agent=built)], kind="a2a")

    # --- Skills ---

    @staticmethod
    def skill(
        path: Any,
    ) -> TComposite:
        """Wrap ADK ``SkillToolset`` for progressive disclosure.

        Parses SKILL.md files from directory path(s) and creates a
        ``SkillToolset``.  The toolset provides L1/L2/L3 progressive
        disclosure — skill metadata is always in the system prompt,
        instructions loaded on demand by the LLM.

        Args:
            path: Directory path, list of paths, or list of
                ``google.adk.skills.Skill`` objects.
        """
        from pathlib import Path as _Path

        from google.adk.skills.models import Frontmatter
        from google.adk.skills.models import Skill as _ADKSkill
        from google.adk.tools.skill_toolset import SkillToolset

        from adk_fluent._skill_parser import parse_skill_file

        if isinstance(path, (str, _Path)):
            path = [path]
        skills: list[_ADKSkill] = []
        for p in path:
            if isinstance(p, _ADKSkill):
                skills.append(p)
            else:
                sd = parse_skill_file(p)
                skills.append(
                    _ADKSkill(
                        frontmatter=Frontmatter(
                            name=sd.name,
                            description=sd.description,
                        ),
                        instructions=sd.body,
                    )
                )
        toolset = SkillToolset(skills=skills)
        return TComposite([toolset], kind="skill_toolset")

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

    # --- A2UI ---

    @staticmethod
    def a2ui(*, catalog: str = "basic", schema: Any = None) -> TComposite:
        """A2UI toolset for LLM-guided UI generation.

        Default (``catalog="basic"``): wraps ``SendA2uiToClientToolset`` from
        the optional ``a2ui-agent`` package. Raises :class:`A2UINotInstalled`
        when the package is not importable — install with
        ``pip install a2ui-agent``.

        Flux (``catalog="flux"``): returns a toolset that exposes the flux
        component factories and injects per-component ``llm`` metadata
        (description, examples, antiPatterns) loaded from
        ``catalog/flux/catalog.json`` into the tool schema. The flux path
        does *not* require ``a2ui-agent``.

        Args:
            catalog: Catalog identifier (``"basic"`` or ``"flux"``).
            schema: Optional catalog schema dict for validation.

        Raises:
            ValueError: If ``catalog`` is not a known identifier.
        """
        from adk_fluent._exceptions import A2UINotInstalled
        from adk_fluent._ui import KNOWN_CATALOGS

        if catalog not in KNOWN_CATALOGS:
            raise ValueError(f"Unknown catalog {catalog!r}. Known catalogs: {sorted(KNOWN_CATALOGS)}")

        if catalog == "flux":
            return _build_flux_a2ui_toolset(schema=schema)

        try:
            from a2ui.agent import SendA2uiToClientToolset  # type: ignore[import-not-found]
        except ImportError as exc:
            raise A2UINotInstalled(
                "T.a2ui() requires the 'a2ui-agent' package. Install with: pip install a2ui-agent"
            ) from exc
        return TComposite([SendA2uiToClientToolset()], kind="a2ui")

    # --- Effectful (idempotent) ---

    @staticmethod
    def effectful(
        tool_or_composite: TComposite | Any,
        *,
        key: str | Any,
        scope: str = "session",
        ttl: float = 0.0,
    ) -> TComposite:
        """Wrap tool(s) as idempotent side-effects with a user-supplied key.

        First call with a given key runs the tool and records the result in
        the ambient :class:`EffectCache`; subsequent calls with the same key
        return the cached value without invoking the tool.

        An :class:`EffectRecorded` event is emitted on the ambient
        :class:`EventBus` with ``source="fresh"`` or ``source="cache"``.

        Args:
            tool_or_composite: The tool to wrap.
            key: Either a format string rendered against ``args`` (e.g.
                ``"user:{user_id}"``) or a callable ``(args) -> str``.
            scope: Cache partition bucket (``"session"`` by default).
            ttl: Lifetime in seconds. ``0`` means "no expiry".
        """
        items = tool_or_composite._items if isinstance(tool_or_composite, TComposite) else [tool_or_composite]
        wrapped = [_EffectfulWrapper(item, key=key, scope=scope, ttl=ttl) for item in items]
        return TComposite(wrapped, kind="effectful")

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
    """Wraps a tool with a TTL-based in-memory cache.

    Backed by ``cachetools.TTLCache`` which handles expiry eviction and
    max-size bounds. Replaces the hand-rolled dict + timestamp pattern,
    which grew unbounded in long-running agents.
    """

    def __init__(self, inner: Any, ttl: float, key_fn: Any = None, *, max_size: int = 1024):
        self._inner = inner
        self._ttl = ttl
        self._key_fn = key_fn or (lambda args: str(sorted(args.items())))
        self._cache: _TTLCache[str, Any] = _TTLCache(maxsize=max_size, ttl=ttl)
        self.name = getattr(inner, "name", getattr(inner, "__name__", "tool"))
        self.description = getattr(inner, "description", getattr(inner, "__doc__", "") or "")

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:  # noqa: ANN401
        """Return cached result if fresh, otherwise invoke and cache."""
        key = self._key_fn(args)
        if key in self._cache:
            return self._cache[key]
        if hasattr(self._inner, "run_async"):
            result = await self._inner.run_async(args=args, tool_context=tool_context)
        else:
            result = self._inner(**args)
        self._cache[key] = result
        return result


class _EffectfulWrapper:
    """Wraps a tool as an idempotent side-effect (Phase E).

    Looks up the ambient :class:`EffectCache` before invoking the inner
    tool. On hit the cached value is returned and an
    :class:`EffectRecorded` event with ``source="cache"`` is emitted.
    On miss the tool runs, its return value is cached, and an
    :class:`EffectRecorded` event with ``source="fresh"`` is emitted.

    When no ambient cache is active the wrapper is a pass-through.
    """

    def __init__(self, inner: Any, *, key: str | Any, scope: str = "session", ttl: float = 0.0):
        self._inner = inner
        self._key_spec = key
        self._scope = scope
        self._ttl = ttl
        self.name = getattr(inner, "name", getattr(inner, "__name__", "tool"))
        self.description = getattr(inner, "description", getattr(inner, "__doc__", "") or "")

    def _render_key(self, args: dict) -> str:
        spec = self._key_spec
        if callable(spec):
            try:
                return str(spec(args))
            except Exception:
                return repr(sorted(args.items()))
        if isinstance(spec, str):
            try:
                return spec.format(**args, args=args)
            except Exception:
                return spec
        return str(spec)

    async def run_async(self, *, args: dict, tool_context: Any) -> Any:  # noqa: ANN401
        """Consult ambient cache, invoke inner tool on miss, record outcome."""
        import time as _time

        from adk_fluent._session._effect_cache import active_cache

        cache = active_cache()
        rendered_key = self._render_key(args)

        if cache is not None:
            entry = cache.get(self.name, rendered_key, scope=self._scope)
            if entry is not None:
                self._emit_effect(rendered_key, source="cache", duration_ms=0.0)
                return entry.value

        start = _time.monotonic()
        if hasattr(self._inner, "run_async"):
            result = await self._inner.run_async(args=args, tool_context=tool_context)
        else:
            result = self._inner(**args)
        duration_ms = (_time.monotonic() - start) * 1000.0

        if cache is not None:
            cache.put(
                self.name,
                rendered_key,
                result,
                scope=self._scope,
                ttl_seconds=self._ttl,
            )
        self._emit_effect(rendered_key, source="fresh", duration_ms=duration_ms)
        return result

    def _emit_effect(self, rendered_key: str, *, source: str, duration_ms: float) -> None:
        try:
            from adk_fluent._harness._event_bus import active_bus
            from adk_fluent._harness._events import EffectRecorded

            bus = active_bus()
            if bus is None:
                return
            bus.emit(
                EffectRecorded(
                    tool_name=self.name,
                    key=rendered_key,
                    source=source,
                    duration_ms=duration_ms,
                )
            )
        except Exception:  # noqa: BLE001
            return


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
