# Module: tools

> `from adk_fluent import T`

Fluent tool composition. Consistent with P, C, S, M modules.

## Quick Reference

| Method                                                              | Returns      | Description                                                  |
| ------------------------------------------------------------------- | ------------ | ------------------------------------------------------------ |
| `T.fn(func_or_tool, confirm=False)`                                 | `TComposite` | Wrap a callable as a tool                                    |
| `T.agent(agent_or_builder)`                                         | `TComposite` | Wrap an agent (or builder) as an AgentTool                   |
| `T.toolset(ts)`                                                     | `TComposite` | Wrap any ADK toolset (MCPToolset, etc.)                      |
| `T.google_search()`                                                 | `TComposite` | Google Search tool                                           |
| `T.search(registry, always_loaded=None, max_tools=20)`              | `TComposite` | BM25-indexed dynamic tool loading (two-phase pattern)        |
| `T.schema(schema_cls)`                                              | `TComposite` | Attach a ToolSchema for contract checking                    |
| `T.mock(name, returns=None, side_effect=None)`                      | `TComposite` | Create a mock tool that returns a fixed value or side-effect |
| `T.confirm(tool_or_composite, message=None)`                        | `TComposite` | Wrap tool(s) with a confirmation requirement                 |
| `T.timeout(tool_or_composite, seconds=30)`                          | `TComposite` | Wrap tool(s) with a per-invocation timeout                   |
| `T.cache(tool_or_composite, ttl=300, key_fn=None)`                  | `TComposite` | Wrap tool(s) with a TTL-based result cache                   |
| `T.mcp(url_or_params, tool_filter=None, prefix=None)`               | `TComposite` | Thin factory over :class:`McpToolset` builder                |
| `T.a2a(agent_card_url, name=None, description=None, timeout=600.0)` | `TComposite` | Wrap a remote A2A agent as an AgentTool                      |
| `T.openapi(spec, tool_filter=None, auth=None)`                      | `TComposite` | Thin factory over :class:`OpenAPIToolset` builder            |
| `T.a2ui(catalog='basic', schema=None)`                              | `TComposite` | A2UI toolset for LLM-guided UI generation                    |
| `T.transform(tool_or_composite, pre=None, post=None)`               | `TComposite` | Wrap tool(s) with pre/post argument/result transforms        |

## Wrapping

### `T.fn(func_or_tool: Any, *, confirm: bool = False) -> TComposite`

Wrap a callable as a tool.

If `func_or_tool` is already a `BaseTool`, it is used as-is.
Plain callables are wrapped in `FunctionTool`.
Set `confirm=True` to require user confirmation before execution.

**Parameters:**

- `func_or_tool` (*Any*)
- `confirm` (*bool*) — default: `False`

### `T.agent(agent_or_builder: Any) -> TComposite`

Wrap an agent (or builder) as an AgentTool.

**Parameters:**

- `agent_or_builder` (*Any*)

### `T.toolset(ts: Any) -> TComposite`

Wrap any ADK toolset (MCPToolset, etc.).

**Parameters:**

- `ts` (*Any*)

## Built-in tool groups

### `T.google_search() -> TComposite`

Google Search tool.

## Dynamic loading

### `T.search(registry: Any, *, always_loaded: list[str] | None = None, max_tools: int = 20) -> TComposite`

BM25-indexed dynamic tool loading (two-phase pattern).

Wraps a `ToolRegistry` in a `SearchToolset` that implements
discovery -> loading -> freezing lifecycle.

**Parameters:**

- `registry` (*Any*)
- `always_loaded` (*list\[str\] | None*) — default: `None`
- `max_tools` (*int*) — default: `20`

## Contract checking

### `T.schema(schema_cls: type) -> TComposite`

Attach a ToolSchema for contract checking.

When piped into a tool chain, this marker is extracted during
IR conversion and wired to `AgentNode.tool_schema`.

**Parameters:**

- `schema_cls` (*type*)

## Mock

### `T.mock(name: str, *, returns: Any = None, side_effect: Any = None) -> TComposite`

Create a mock tool that returns a fixed value or side-effect.

**Args:**

- **`name`**: Name for the mock tool.
- **`returns`**: Value to return (ignored if *side_effect* is set).
- **`side_effect`**: Callable or static value used instead of *returns*.

**Parameters:**

- `name` (*str*)
- `returns` (*Any*) — default: `None`
- `side_effect` (*Any*) — default: `None`

## Confirm

### `T.confirm(tool_or_composite: TComposite | Any, message: str | None = None) -> TComposite`

Wrap tool(s) with a confirmation requirement.

Each tool in the composite is individually wrapped so that
`require_confirmation` is set.

**Parameters:**

- `tool_or_composite` (*TComposite | Any*)
- `message` (*str | None*) — default: `None`

## Timeout

### `T.timeout(tool_or_composite: TComposite | Any, seconds: float = 30) -> TComposite`

Wrap tool(s) with a per-invocation timeout.

**Parameters:**

- `tool_or_composite` (*TComposite | Any*)
- `seconds` (*float*) — default: `30`

## Cache

### `T.cache(tool_or_composite: TComposite | Any, ttl: float = 300, key_fn: Any = None) -> TComposite`

Wrap tool(s) with a TTL-based result cache.

**Parameters:**

- `tool_or_composite` (*TComposite | Any*)
- `ttl` (*float*) — default: `300`
- `key_fn` (*Any*) — default: `None`

## MCP

### `T.mcp(url_or_params: Any, *, tool_filter: Any = None, prefix: str | None = None) -> TComposite`

Thin factory over :class:`McpToolset` builder.

**Parameters:**

- `url_or_params` (*Any*)
- `tool_filter` (*Any*) — default: `None`
- `prefix` (*str | None*) — default: `None`

## A2A

### `T.a2a(agent_card_url: str, *, name: str | None = None, description: str | None = None, timeout: float = 600.0) -> TComposite`

Wrap a remote A2A agent as an AgentTool.

This is useful when you want the LLM to invoke a remote agent
as a tool (structured I/O) rather than delegating to it as a
sub-agent (opaque autonomous task).

**Args:**

- **`agent_card_url`**: Base URL or full card URL of the remote agent.
- **`name`**: Override the agent name (defaults to remote agent's name).
- **`description`**: Override the agent description.
- **`timeout`**: HTTP timeout in seconds.

**Parameters:**

- `agent_card_url` (*str*)
- `name` (*str | None*) — default: `None`
- `description` (*str | None*) — default: `None`
- `timeout` (*float*) — default: `600.0`

## OpenAPI

### `T.openapi(spec: Any, *, tool_filter: Any = None, auth: Any = None) -> TComposite`

Thin factory over :class:`OpenAPIToolset` builder.

**Parameters:**

- `spec` (*Any*)
- `tool_filter` (*Any*) — default: `None`
- `auth` (*Any*) — default: `None`

## A2UI

### `T.a2ui(*, catalog: str = basic, schema: Any = None) -> TComposite`

A2UI toolset for LLM-guided UI generation.

If `a2ui-agent` is installed, wraps `SendA2uiToClientToolset`.
Otherwise returns a no-op marker composite.

**Args:**

- **`catalog`**: Catalog identifier (default `"basic"`).
- **`schema`**: Optional catalog schema dict for validation.

**Parameters:**

- `catalog` (*str*) — default: `'basic'`
- `schema` (*Any*) — default: `None`

## Transform

### `T.transform(tool_or_composite: TComposite | Any, *, pre: Any = None, post: Any = None) -> TComposite`

Wrap tool(s) with pre/post argument/result transforms.

**Parameters:**

- `tool_or_composite` (*TComposite | Any*)
- `pre` (*Any*) — default: `None`
- `post` (*Any*) — default: `None`

## Composition Operators

### `|` (compose (TComposite))

Combine tools into a collection

## Types

| Type         | Description            |
| ------------ | ---------------------- |
| `TComposite` | Composable tool chain. |
