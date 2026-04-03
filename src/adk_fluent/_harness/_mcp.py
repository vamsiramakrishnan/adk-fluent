"""MCP server auto-discovery — bulk MCP tool wiring at harness level.

Claude Code natively discovers and connects to MCP servers defined in
config. This module delegates to the existing ``T.mcp()`` and
``McpToolset`` builder — the affordance is bulk-loading from a config
file and making it as easy to wire as ``H.workspace()``::

    # Direct specs
    tools = H.mcp([
        {"url": "http://localhost:3000/mcp"},
        {"command": "npx", "args": ["-y", "some-mcp-server"]},
    ])

    # From config file (Claude Code / VS Code format)
    tools = H.mcp_from_config("/project/.agent/mcp.json")

Reuses: ``adk_fluent.tool.McpToolset`` builder and ``T.mcp()`` factory.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

__all__ = ["load_mcp_tools", "load_mcp_config"]


def _load_single_server(
    spec: dict[str, Any],
    *,
    tool_filter: Callable[[str], bool] | list[str] | None = None,
    prefix: str | None = None,
) -> list[Any]:
    """Load tools from a single MCP server spec using adk-fluent's McpToolset builder."""
    try:
        from adk_fluent.tool import McpToolset
    except ImportError:
        return []

    # Build connection_params from spec
    if "url" in spec:
        connection_params = spec["url"]
    elif "command" in spec:
        connection_params = {
            "command": spec["command"],
            "args": spec.get("args", []),
        }
        # Include env if provided
        if "env" in spec:
            connection_params["env"] = spec["env"]
    else:
        # Pass through as-is (user knows the McpToolset format)
        connection_params = spec

    try:
        builder = McpToolset(connection_params)
        if tool_filter is not None:
            builder = builder.tool_filter(tool_filter)
        if prefix is not None:
            builder = builder.tool_name_prefix(prefix)
        return [builder.build()]
    except Exception:
        return []


def load_mcp_tools(
    servers: list[dict[str, Any]],
    *,
    tool_filter: Callable[[str], bool] | list[str] | None = None,
    prefix: str | None = None,
) -> list[Any]:
    """Load tools from a list of MCP server specifications.

    Each server spec is a dict with either:
    - ``{"url": "http://..."}`` for SSE/streamable-HTTP servers
    - ``{"command": "npx", "args": [...]}`` for stdio-based servers

    Delegates to ``adk_fluent.tool.McpToolset`` builder for each server.

    Args:
        servers: List of server specification dicts.
        tool_filter: Optional filter — callable or list of tool names.
        prefix: Optional prefix for tool names (avoids collisions).

    Returns:
        List of built McpToolset objects for ``.tools()``.
    """
    all_tools: list[Any] = []
    for spec in servers:
        tools = _load_single_server(spec, tool_filter=tool_filter, prefix=prefix)
        all_tools.extend(tools)
    return all_tools


def load_mcp_config(
    config_path: str | Path,
    *,
    tool_filter: Callable[[str], bool] | list[str] | None = None,
    prefix: str | None = None,
) -> list[Any]:
    """Load MCP tools from a JSON config file.

    Supports two formats:

    **Array format**::

        {"mcpServers": [
            {"url": "http://localhost:3000/mcp"},
            {"command": "npx", "args": ["-y", "server"]}
        ]}

    **Named dict format** (Claude Code / VS Code style)::

        {"mcpServers": {
            "filesystem": {"command": "npx", "args": ["-y", "@mcp/fs"]},
            "github": {"url": "http://localhost:3001/mcp"}
        }}

    Args:
        config_path: Path to the JSON config file.
        tool_filter: Optional filter — callable or list of tool names.
        prefix: Optional prefix for tool names.

    Returns:
        List of built McpToolset objects.
    """
    path = Path(config_path)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    servers_data = data.get("mcpServers", data.get("servers", []))

    # Handle dict format (Claude Code style: {"name": {spec}})
    if isinstance(servers_data, dict):
        servers = []
        for name, spec in servers_data.items():
            if isinstance(spec, dict):
                spec_copy = dict(spec)
                spec_copy.setdefault("name", name)
                servers.append(spec_copy)
    elif isinstance(servers_data, list):
        servers = servers_data
    else:
        return []

    return load_mcp_tools(servers, tool_filter=tool_filter, prefix=prefix)
