# Module: tools

> `from adk_fluent import T`

Fluent tool composition. Consistent with P, C, S, M modules.

## Quick Reference

| Method                                                 | Returns      | Description                                           |
| ------------------------------------------------------ | ------------ | ----------------------------------------------------- |
| `T.fn(func_or_tool, confirm=False)`                    | `TComposite` | Wrap a callable as a tool                             |
| `T.agent(agent_or_builder)`                            | `TComposite` | Wrap an agent (or builder) as an AgentTool            |
| `T.toolset(ts)`                                        | `TComposite` | Wrap any ADK toolset (MCPToolset, etc.)               |
| `T.google_search()`                                    | `TComposite` | Google Search tool                                    |
| `T.search(registry, always_loaded=None, max_tools=20)` | `TComposite` | BM25-indexed dynamic tool loading (two-phase pattern) |
| `T.schema(schema_cls)`                                 | `TComposite` | Attach a ToolSchema for contract checking             |

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
- `always_loaded` (*list[str] | None*) — default: `None`
- `max_tools` (*int*) — default: `20`

## Contract checking

### `T.schema(schema_cls: type) -> TComposite`

Attach a ToolSchema for contract checking.

When piped into a tool chain, this marker is extracted during
IR conversion and wired to `AgentNode.tool_schema`.

**Parameters:**

- `schema_cls` (*type*)

## Composition Operators

### `|` (compose (TComposite))

Combine tools into a collection

## Types

| Type         | Description            |
| ------------ | ---------------------- |
| `TComposite` | Composable tool chain. |
