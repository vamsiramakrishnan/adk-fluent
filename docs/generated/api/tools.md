# Module: tools

> `from adk_fluent import T`

Fluent tool composition. Consistent with P, C, S, M modules.

## Quick Reference

| Method                                                              | Returns      | Description                                                      |
| ------------------------------------------------------------------- | ------------ | ---------------------------------------------------------------- |
| `T.fn(func_or_tool, confirm=False)`                                 | `TComposite` | Wrap a callable as a tool                                        |
| `T.agent(agent_or_builder)`                                         | `TComposite` | Wrap an agent (or builder) as an AgentTool                       |
| `T.toolset(ts)`                                                     | `TComposite` | Wrap any ADK toolset (MCPToolset, etc.)                          |
| `T.google_search()`                                                 | `TComposite` | Google Search tool                                               |
| `T.search(registry, always_loaded=None, max_tools=20)`              | `TComposite` | BM25-indexed dynamic tool loading (two-phase pattern)            |
| `T.schema(schema_cls)`                                              | `TComposite` | Attach a ToolSchema for contract checking                        |
| `T.mock(name, returns=None, side_effect=None)`                      | `TComposite` | Create a mock tool that returns a fixed value or side-effect     |
| `T.confirm(tool_or_composite, message=None)`                        | `TComposite` | Wrap tool(s) with a confirmation requirement                     |
| `T.timeout(tool_or_composite, seconds=30)`                          | `TComposite` | Wrap tool(s) with a per-invocation timeout                       |
| `T.cache(tool_or_composite, ttl=300, key_fn=None)`                  | `TComposite` | Wrap tool(s) with a TTL-based result cache                       |
| `T.mcp(url_or_params, tool_filter=None, prefix=None)`               | `TComposite` | Thin factory over :class:`McpToolset` builder                    |
| `T.a2a(agent_card_url, name=None, description=None, timeout=600.0)` | `TComposite` | Wrap a remote A2A agent as an AgentTool                          |
| `T.skill(path)`                                                     | `TComposite` | Wrap ADK `SkillToolset` for progressive disclosure               |
| `T.openapi(spec, tool_filter=None, auth=None)`                      | `TComposite` | Thin factory over :class:`OpenAPIToolset` builder                |
| `T.a2ui(catalog='basic', schema=None)`                              | `TComposite` | A2UI toolset for LLM-guided UI generation                        |
| `T.effectful(tool_or_composite, key, scope='session', ttl=0.0)`     | `TComposite` | Wrap tool(s) as idempotent side-effects with a user-supplied key |
| `T.transform(tool_or_composite, pre=None, post=None)`               | `TComposite` | Wrap tool(s) with pre/post argument/result transforms            |

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

## Skills

### `T.skill(path: Any) -> TComposite`

Wrap ADK `SkillToolset` for progressive disclosure.

Parses SKILL.md files from directory path(s) and creates a
`SkillToolset`.  The toolset provides L1/L2/L3 progressive
disclosure — skill metadata is always in the system prompt,
instructions loaded on demand by the LLM.

**Args:**

- **`path`**: Directory path, list of paths, or list of
  `google.adk.skills.Skill` objects.

**Parameters:**

- `path` (*Any*)

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

Default (`catalog="basic"`): wraps `SendA2uiToClientToolset` from
the optional `a2ui-agent` package. Raises :class:`A2UINotInstalled`
when the package is not importable — install with
`pip install a2ui-agent`.

Flux (`catalog="flux"`): returns a toolset that exposes the flux
component factories and injects per-component `llm` metadata
(description, examples, antiPatterns) loaded from
`catalog/flux/catalog.json` into the tool schema. The flux path
does *not* require `a2ui-agent`.

**Args:**

- **`catalog`**: Catalog identifier (`"basic"` or `"flux"`).
- **`schema`**: Optional catalog schema dict for validation.

**Raises:**

    ValueError: If `catalog` is not a known identifier.

**Parameters:**

- `catalog` (*str*) — default: `'basic'`
- `schema` (*Any*) — default: `None`

## Effectful (idempotent)

### `T.effectful(tool_or_composite: TComposite | Any, *, key: str | Any, scope: str = session, ttl: float = 0.0) -> TComposite`

Wrap tool(s) as idempotent side-effects with a user-supplied key.

First call with a given key runs the tool and records the result in
the ambient :class:`EffectCache`; subsequent calls with the same key
return the cached value without invoking the tool.

An :class:`EffectRecorded` event is emitted on the ambient
:class:`EventBus` with `source="fresh"` or `source="cache"`.

**Args:**

- **`tool_or_composite`**: The tool to wrap.
- **`key`**: Either a format string rendered against `args` (e.g.
  `"user:{user_id}"`) or a callable `(args) -> str`.
- **`scope`**: Cache partition bucket (`"session"` by default).
- **`ttl`**: Lifetime in seconds. `0` means "no expiry".

**Parameters:**

- `tool_or_composite` (*TComposite | Any*)
- `key` (*str | Any*)
- `scope` (*str*) — default: `'session'`
- `ttl` (*float*) — default: `0.0`

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
