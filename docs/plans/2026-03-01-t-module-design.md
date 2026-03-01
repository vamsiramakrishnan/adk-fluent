# T Module: Fluent Tool Composition and Dynamic Loading

## Context

adk-fluent has four composition namespaces: `P` (prompts), `C` (context), `S` (state transforms), `M` (middleware). Each owns a mechanism. Tools currently lack a composition surface: `.tool(fn)` appends one tool, `.tools([list])` sets all, but there's no composable chain, no dynamic discovery, and no lifecycle management.

Enterprise deployments face a scaling problem: 100+ tools in a catalog, but stuffing them all into an agent's tool list bloats context and degrades LLM performance. Research (context engineering best practices) shows a two-phase approach works: discover and load tools first, then freeze the tool list for stable KV-cache performance during execution.

`T` earns its place alongside `P`/`C`/`S`/`M` because it manages a lifecycle (discovery, loading, freezing) — not just grouping syntax.

## Design

### 1. Core Types

#### `TComposite`

Composable tool chain, analogous to `MComposite`:

```python
class TComposite:
    """Composable tool chain. The result of any T.xxx() call."""

    def __init__(self, items: list | None = None):
        self._items = list(items or [])

    def __or__(self, other):
        """T.fn(search) | T.fn(email) | T.google_search()"""
        if isinstance(other, TComposite):
            return TComposite(self._items + other._items)
        return TComposite(self._items + [other])

    def __ror__(self, other):
        """my_fn | T.google_search()"""
        return TComposite([other] + self._items)

    def to_tools(self) -> list:
        """Flatten to ADK-compatible tool/toolset list.
        Auto-wraps plain callables in FunctionTool."""
```

#### `T` Factory Class

```python
class T:
    """Fluent tool composition. Consistent with P, C, S, M modules."""

    # --- Wrapping ---
    @staticmethod
    def fn(func: Callable, *, confirm: bool = False) -> TComposite:
        """Wrap a callable as a tool."""

    @staticmethod
    def agent(agent_or_builder) -> TComposite:
        """Wrap an agent as an AgentTool."""

    @staticmethod
    def toolset(ts: BaseToolset) -> TComposite:
        """Wrap any ADK toolset (MCPToolset, BigQueryToolset, etc.)."""

    # --- Built-in tool groups ---
    @staticmethod
    def google_search(**kwargs) -> TComposite:
        """Google Search tool."""

    # --- Dynamic loading ---
    @staticmethod
    def search(registry: ToolRegistry, **kwargs) -> TComposite:
        """BM25-indexed dynamic tool loading (two-phase pattern)."""

    # --- Composition ---
    @staticmethod
    def schema(schema_cls: type) -> TComposite:
        """Attach a ToolSchema for contract checking."""
```

### 2. ToolRegistry

BM25-indexed catalog for tool discovery. `rank_bm25` is an optional dependency (`pip install adk-fluent[search]`). Falls back to substring matching if not installed.

```python
class ToolRegistry:
    """BM25-indexed registry for tool discovery."""

    def register(self, tool: BaseTool | Callable) -> None: ...
    def register_all(self, *tools) -> None: ...
    def search(self, query: str, top_k: int = 5) -> list[dict]: ...
    def get_tool(self, name: str) -> BaseTool | None: ...

    @classmethod
    def from_tools(cls, *tools) -> ToolRegistry:
        """Factory: build registry from a list of tools."""
```

Import-guarded BM25:

```python
try:
    from rank_bm25 import BM25Okapi
    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False
```

### 3. SearchToolset (two-phase dynamic loading)

Native `BaseToolset` subclass implementing the two-phase pattern:

```python
class SearchToolset(BaseToolset):
    """Two-phase dynamic tool loading.

    Phase 1 (Discovery): get_tools() returns meta-tools:
        [search_tools, load_tool, finalize_tools]
        Agent discovers and loads tools via BM25 search.
        KV-cache invalidation is acceptable (short prefix).

    Phase 2 (Execution): get_tools() returns loaded tools. FROZEN.
        Identical tool list on every turn. Stable KV-cache.
        No more tools can be added.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        always_loaded: list[str] | None = None,
        max_tools: int = 20,
    ): ...

    async def get_tools(self, readonly_context=None) -> list[BaseTool]:
        phase = readonly_context.state.get("toolset_phase", "discovery")
        if phase == "discovery":
            return [self._search_tool, self._load_tool, self._finalize_tool]
        else:
            return self._build_frozen_list(readonly_context)
```

**Meta-tools** (generated internally by SearchToolset):

- `search_tools(query: str)` — BM25 search over registry, returns summaries
- `load_tool(tool_name: str, tool_context)` — activates a tool into the session
- `finalize_tools(tool_context)` — locks the toolset, transitions to Phase 2

**Design principles baked in**:

1. **KV-cache aware**: Tool list frozen after finalization — identical on every subsequent turn
1. **Append-only**: Once loaded, tools never disappear
1. **File-as-context**: `compress_large_result()` helper writes large outputs to temp files
1. **Error preservation**: Failed tool calls kept in context, not silently retried

### 4. Integration with Existing Systems

#### ToolSchema

```python
# ToolSchema works exactly as before
class SearchTools(ToolSchema):
    query: Annotated[str, Reads()]
    results: Annotated[list, Writes()]

# T.schema() attaches ToolSchema for contract checking
agent = Agent("searcher").tools(
    T.fn(search) | T.schema(SearchTools)
)
```

- `T.fn(fn)` — no schema, wraps the function
- `T.schema(MyToolSchema)` — attaches schema metadata, wired to `AgentNode.tool_schema` during IR conversion
- `T.search(registry)` — schema is opaque at build time (tools discovered at runtime), contract checker skips validation for dynamic toolsets

#### After-Tool Callbacks

Fluent API already has `.after_tool(fn)` as a clean alias for `.after_tool_callback(fn)`. The search-aware callback is a pre-built helper:

```python
from adk_fluent import T, ToolRegistry, search_aware_after_tool

registry = ToolRegistry.from_tools(fn1, fn2, fn3)
agent = (
    Agent("assistant")
    .tools(T.search(registry))
    .after_tool(search_aware_after_tool)
)
```

`search_aware_after_tool` handles:

1. **Large result compression**: Results > threshold written to temp file, path kept in context
1. **Error preservation**: Failed calls annotated but NOT silently retried
1. **Result variation**: Subtle formatting variation per call index to prevent repetitive patterns

These are opt-in — not baked into `SearchToolset`.

#### Backward Compatibility

| Existing API                           | Interaction with T                                                 |
| -------------------------------------- | ------------------------------------------------------------------ |
| `.tool(fn)`                            | Unchanged. Appends individual tools.                               |
| `.tool(fn, require_confirmation=True)` | Unchanged. `T.fn(fn, confirm=True)` is the T equivalent.           |
| `.delegate(agent)`                     | Unchanged. `T.agent(agent)` is the T equivalent.                   |
| `.tools([list])`                       | Extended to also accept `TComposite`.                              |
| `.tool_schema(MySchema)`               | Unchanged. `T.schema(MySchema)` pipes the same value.              |
| `.after_tool(fn)`                      | Unchanged. `search_aware_after_tool` is just a pre-built function. |

#### Builder Integration

```python
def tools(self, t):
    if isinstance(t, TComposite):
        for item in t.to_tools():
            self._lists["tools"].append(item)
    elif isinstance(t, list):
        self._config["tools"] = t
    else:
        self._lists["tools"].append(t)
    return self
```

**IR wiring**: No changes needed. `_agent_to_ir()` already collects from `_lists["tools"]` and `_config["tools"]`. `TComposite.to_tools()` returns standard ADK types.

### 5. Files Modified

| File                               | Changes                                                                                                          |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `src/adk_fluent/_tools.py`         | **NEW** — `T`, `TComposite`                                                                                      |
| `src/adk_fluent/_tool_registry.py` | **NEW** — `ToolRegistry`, `SearchToolset`, `search_aware_after_tool`, `compress_large_result`, `_ResultVariator` |
| `src/adk_fluent/_helpers.py`       | `_add_tools()` helper for `TComposite` support                                                                   |
| `seeds/seed.manual.toml`           | `.tools()` extra updated for `TComposite`                                                                        |
| `src/adk_fluent/prelude.py`        | Export `T`, `TComposite`, `ToolRegistry`, `SearchToolset`, `search_aware_after_tool`                             |
| `src/adk_fluent/__init__.py`       | Regenerated                                                                                                      |
| `pyproject.toml`                   | `[project.optional-dependencies] search = ["rank-bm25>=0.2.2"]`                                                  |

### 6. Testing Strategy

1. Unit: `TComposite` composition (`|` operator, `to_tools()` normalization)
1. Unit: `T.fn()`, `T.agent()`, `T.toolset()`, `T.google_search()` factories
1. Unit: `ToolRegistry` registration and search (with and without BM25)
1. Unit: `SearchToolset.get_tools()` two-phase behavior (mock state)
1. Unit: Meta-tools state transitions (search → load → finalize)
1. Unit: `search_aware_after_tool` compression, error preservation, variation
1. Integration: `Agent("x").tools(T.search(registry))` builds successfully
1. Integration: `T.fn(fn) | T.google_search()` produces correct ADK types
1. Cookbook: End-to-end dynamic loading example
