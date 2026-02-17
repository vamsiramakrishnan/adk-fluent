# Module: `tool`

# ActiveStreamingTool

> Fluent builder for `google.adk.agents.active_streaming_tool.ActiveStreamingTool`

Manages streaming tool related resources during invocation.

## Terminal Methods

### `.build() -> ActiveStreamingTool`

Resolve into a native ADK ActiveStreamingTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.task(value)` | `Union[Task, NoneType]` |
| `.stream(value)` | `Union[LiveRequestQueue, NoneType]` |

---

# AgentTool

> Fluent builder for `google.adk.tools.agent_tool.AgentTool`

A tool that wraps an agent.

## Constructor

```python
AgentTool(agent)
```

| Argument | Type |
|----------|------|
| `agent` | `BaseAgent` |

## Terminal Methods

### `.build() -> AgentTool`

Resolve into a native ADK AgentTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.skip_summarization(value)` | `bool` |
| `.include_plugins(value)` | `bool` |

---

# APIHubToolset

> Fluent builder for `google.adk.tools.apihub_tool.apihub_toolset.APIHubToolset`

APIHubTool generates tools from a given API Hub resource.

## Constructor

```python
APIHubToolset(apihub_resource_name)
```

| Argument | Type |
|----------|------|
| `apihub_resource_name` | `str` |

## Terminal Methods

### `.build() -> APIHubToolset`

Resolve into a native ADK APIHubToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.access_token(value)` | `Optional[str]` |
| `.service_account_json(value)` | `Optional[str]` |
| `.name(value)` | `str` |
| `.description(value)` | `str` |
| `.lazy_load_spec(value)` | `Any` |
| `.auth_scheme(value)` | `Optional[AuthScheme]` |
| `.auth_credential(value)` | `Optional[AuthCredential]` |
| `.apihub_client(value)` | `Optional[APIHubClient]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |

---

# ApplicationIntegrationToolset

> Fluent builder for `google.adk.tools.application_integration_tool.application_integration_toolset.ApplicationIntegrationToolset`

ApplicationIntegrationToolset generates tools from a given Application.

## Constructor

```python
ApplicationIntegrationToolset(project, location)
```

| Argument | Type |
|----------|------|
| `project` | `str` |
| `location` | `str` |

## Terminal Methods

### `.build() -> ApplicationIntegrationToolset`

Resolve into a native ADK ApplicationIntegrationToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.connection_template_override(value)` | `Optional[str]` |
| `.integration(value)` | `Optional[str]` |
| `.triggers(value)` | `Optional[List[str]]` |
| `.connection(value)` | `Optional[str]` |
| `.entity_operations(value)` | `Optional[str]` |
| `.actions(value)` | `Optional[list[str]]` |
| `.tool_name_prefix(value)` | `Optional[str]` |
| `.tool_instructions(value)` | `Optional[str]` |
| `.service_account_json(value)` | `Optional[str]` |
| `.auth_scheme(value)` | `Optional[AuthScheme]` |
| `.auth_credential(value)` | `Optional[AuthCredential]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |

---

# IntegrationConnectorTool

> Fluent builder for `google.adk.tools.application_integration_tool.integration_connector_tool.IntegrationConnectorTool`

A tool that wraps a RestApiTool to interact with a specific Application Integration endpoint.

## Constructor

```python
IntegrationConnectorTool(name, description, connection_name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |
| `description` | `str` |
| `connection_name` | `str` |

## Terminal Methods

### `.build() -> IntegrationConnectorTool`

Resolve into a native ADK IntegrationConnectorTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.connection_host(value)` | `str` |
| `.connection_service_name(value)` | `str` |
| `.entity(value)` | `str` |
| `.operation(value)` | `str` |
| `.action(value)` | `str` |
| `.rest_api_tool(value)` | `RestApiTool` |
| `.auth_scheme(value)` | `Optional[Union[AuthScheme, str]]` |
| `.auth_credential(value)` | `Optional[Union[AuthCredential, str]]` |

---

# BaseAuthenticatedTool

> Fluent builder for `google.adk.tools.base_authenticated_tool.BaseAuthenticatedTool`

A base tool class that handles authentication before the actual tool logic.

## Constructor

```python
BaseAuthenticatedTool(name, description)
```

| Argument | Type |
|----------|------|
| `name` | `Any` |
| `description` | `Any` |

## Terminal Methods

### `.build() -> BaseAuthenticatedTool`

Resolve into a native ADK BaseAuthenticatedTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.auth_config(value)` | `AuthConfig` |
| `.response_for_auth_required(value)` | `Optional[Union[dict[str, Any], str]]` |

---

# BaseTool

> Fluent builder for `google.adk.tools.base_tool.BaseTool`

The base class for all tools.

## Constructor

```python
BaseTool(name, description)
```

| Argument | Type |
|----------|------|
| `name` | `Any` |
| `description` | `Any` |

## Terminal Methods

### `.build() -> BaseTool`

Resolve into a native ADK BaseTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.is_long_running(value)` | `bool` |
| `.custom_metadata(value)` | `Optional[dict[str, Any]]` |

---

# BaseToolset

> Fluent builder for `google.adk.tools.base_toolset.BaseToolset`

Base class for toolset.

## Terminal Methods

### `.build() -> BaseToolset`

Resolve into a native ADK BaseToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.tool_name_prefix(value)` | `Optional[str]` |

---

# BigQueryToolset

> Fluent builder for `google.adk.tools.bigquery.bigquery_toolset.BigQueryToolset`

BigQuery Toolset contains tools for interacting with BigQuery data and metadata.

## Terminal Methods

### `.build() -> BigQueryToolset`

Resolve into a native ADK BigQueryToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.credentials_config(value)` | `Optional[BigQueryCredentialsConfig]` |
| `.bigquery_tool_config(value)` | `Optional[BigQueryToolConfig]` |

---

# BigtableToolset

> Fluent builder for `google.adk.tools.bigtable.bigtable_toolset.BigtableToolset`

Bigtable Toolset contains tools for interacting with Bigtable data and metadata.

## Terminal Methods

### `.build() -> BigtableToolset`

Resolve into a native ADK BigtableToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.credentials_config(value)` | `Optional[BigtableCredentialsConfig]` |
| `.bigtable_tool_settings(value)` | `Optional[BigtableToolSettings]` |

---

# ComputerUseTool

> Fluent builder for `google.adk.tools.computer_use.computer_use_tool.ComputerUseTool`

A tool that wraps computer control functions for use with LLMs.

## Constructor

```python
ComputerUseTool(func, screen_size)
```

| Argument | Type |
|----------|------|
| `func` | `Callable[..., Any]` |
| `screen_size` | `tuple[int, int]` |

## Terminal Methods

### `.build() -> ComputerUseTool`

Resolve into a native ADK ComputerUseTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.virtual_screen_size(value)` | `tuple[int, int]` |

---

# ComputerUseToolset

> Fluent builder for `google.adk.tools.computer_use.computer_use_toolset.ComputerUseToolset`

Fluent builder for ComputerUseToolset.

## Constructor

```python
ComputerUseToolset(computer)
```

| Argument | Type |
|----------|------|
| `computer` | `BaseComputer` |

## Terminal Methods

### `.build() -> ComputerUseToolset`

Resolve into a native ADK ComputerUseToolset.

---

# DataAgentToolset

> Fluent builder for `google.adk.tools.data_agent.data_agent_toolset.DataAgentToolset`

Data Agent Toolset contains tools for interacting with data agents.

## Terminal Methods

### `.build() -> DataAgentToolset`

Resolve into a native ADK DataAgentToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.credentials_config(value)` | `Optional[DataAgentCredentialsConfig]` |
| `.data_agent_tool_config(value)` | `Optional[DataAgentToolConfig]` |

---

# DiscoveryEngineSearchTool

> Fluent builder for `google.adk.tools.discovery_engine_search_tool.DiscoveryEngineSearchTool`

Tool for searching the discovery engine.

## Terminal Methods

### `.build() -> DiscoveryEngineSearchTool`

Resolve into a native ADK DiscoveryEngineSearchTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.data_store_id(value)` | `Optional[str]` |
| `.data_store_specs(value)` | `Optional[list[types.VertexAISearchDataStoreSpec]]` |
| `.search_engine_id(value)` | `Optional[str]` |
| `.filter(value)` | `Optional[str]` |
| `.max_results(value)` | `Optional[int]` |

---

# EnterpriseWebSearchTool

> Fluent builder for `google.adk.tools.enterprise_search_tool.EnterpriseWebSearchTool`

A Gemini 2+ built-in tool using web grounding for Enterprise compliance.

## Terminal Methods

### `.build() -> EnterpriseWebSearchTool`

Resolve into a native ADK EnterpriseWebSearchTool.

---

# ExampleTool

> Fluent builder for `google.adk.tools.example_tool.ExampleTool`

A tool that adds (few-shot) examples to the LLM request.

## Constructor

```python
ExampleTool(examples)
```

| Argument | Type |
|----------|------|
| `examples` | `Union[list[Example], BaseExampleProvider]` |

## Terminal Methods

### `.build() -> ExampleTool`

Resolve into a native ADK ExampleTool.

---

# FunctionTool

> Fluent builder for `google.adk.tools.function_tool.FunctionTool`

A tool that wraps a user-defined Python function.

## Constructor

```python
FunctionTool(func)
```

| Argument | Type |
|----------|------|
| `func` | `Callable[..., Any]` |

## Terminal Methods

### `.build() -> FunctionTool`

Resolve into a native ADK FunctionTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.require_confirmation(value)` | `Union[bool, Callable[..., bool]]` |

---

# GoogleApiTool

> Fluent builder for `google.adk.tools.google_api_tool.google_api_tool.GoogleApiTool`

Fluent builder for GoogleApiTool.

## Constructor

```python
GoogleApiTool(rest_api_tool)
```

| Argument | Type |
|----------|------|
| `rest_api_tool` | `RestApiTool` |

## Terminal Methods

### `.build() -> GoogleApiTool`

Resolve into a native ADK GoogleApiTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.client_id(value)` | `Optional[str]` |
| `.client_secret(value)` | `Optional[str]` |
| `.service_account(value)` | `Optional[ServiceAccount]` |
| `.additional_headers(value)` | `Optional[Dict[str, str]]` |

---

# GoogleApiToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolset.GoogleApiToolset`

Google API Toolset contains tools for interacting with Google APIs.

## Constructor

```python
GoogleApiToolset(api_name, api_version)
```

| Argument | Type |
|----------|------|
| `api_name` | `str` |
| `api_version` | `str` |

## Terminal Methods

### `.build() -> GoogleApiToolset`

Resolve into a native ADK GoogleApiToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.client_id(value)` | `Optional[str]` |
| `.client_secret(value)` | `Optional[str]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)` | `Optional[ServiceAccount]` |
| `.tool_name_prefix(value)` | `Optional[str]` |
| `.additional_headers(value)` | `Optional[Dict[str, str]]` |

---

# CalendarToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.CalendarToolset`

Auto-generated Calendar toolset based on Google Calendar API v3 spec exposed by Google API discovery API.

## Terminal Methods

### `.build() -> CalendarToolset`

Resolve into a native ADK CalendarToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.client_id(value)` | `Optional[str]` |
| `.client_secret(value)` | `Optional[str]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)` | `Optional[ServiceAccount]` |
| `.tool_name_prefix(value)` | `Optional[str]` |

---

# DocsToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.DocsToolset`

Auto-generated Docs toolset based on Google Docs API v1 spec exposed by Google API discovery API.

## Terminal Methods

### `.build() -> DocsToolset`

Resolve into a native ADK DocsToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.client_id(value)` | `Optional[str]` |
| `.client_secret(value)` | `Optional[str]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)` | `Optional[ServiceAccount]` |
| `.tool_name_prefix(value)` | `Optional[str]` |

---

# GmailToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.GmailToolset`

Auto-generated Gmail toolset based on Google Gmail API v1 spec exposed by Google API discovery API.

## Terminal Methods

### `.build() -> GmailToolset`

Resolve into a native ADK GmailToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.client_id(value)` | `Optional[str]` |
| `.client_secret(value)` | `Optional[str]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)` | `Optional[ServiceAccount]` |
| `.tool_name_prefix(value)` | `Optional[str]` |

---

# SheetsToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.SheetsToolset`

Auto-generated Sheets toolset based on Google Sheets API v4 spec exposed by Google API discovery API.

## Terminal Methods

### `.build() -> SheetsToolset`

Resolve into a native ADK SheetsToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.client_id(value)` | `Optional[str]` |
| `.client_secret(value)` | `Optional[str]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)` | `Optional[ServiceAccount]` |
| `.tool_name_prefix(value)` | `Optional[str]` |

---

# SlidesToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.SlidesToolset`

Auto-generated Slides toolset based on Google Slides API v1 spec exposed by Google API discovery API.

## Terminal Methods

### `.build() -> SlidesToolset`

Resolve into a native ADK SlidesToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.client_id(value)` | `Optional[str]` |
| `.client_secret(value)` | `Optional[str]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)` | `Optional[ServiceAccount]` |
| `.tool_name_prefix(value)` | `Optional[str]` |

---

# YoutubeToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.YoutubeToolset`

Auto-generated YouTube toolset based on YouTube API v3 spec exposed by Google API discovery API.

## Terminal Methods

### `.build() -> YoutubeToolset`

Resolve into a native ADK YoutubeToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.client_id(value)` | `Optional[str]` |
| `.client_secret(value)` | `Optional[str]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)` | `Optional[ServiceAccount]` |
| `.tool_name_prefix(value)` | `Optional[str]` |

---

# GoogleMapsGroundingTool

> Fluent builder for `google.adk.tools.google_maps_grounding_tool.GoogleMapsGroundingTool`

A built-in tool that is automatically invoked by Gemini 2 models to ground query results with Google Maps.

## Terminal Methods

### `.build() -> GoogleMapsGroundingTool`

Resolve into a native ADK GoogleMapsGroundingTool.

---

# GoogleSearchAgentTool

> Fluent builder for `google.adk.tools.google_search_agent_tool.GoogleSearchAgentTool`

A tool that wraps a sub-agent that only uses google_search tool.

## Constructor

```python
GoogleSearchAgentTool(agent)
```

| Argument | Type |
|----------|------|
| `agent` | `LlmAgent` |

## Terminal Methods

### `.build() -> GoogleSearchAgentTool`

Resolve into a native ADK GoogleSearchAgentTool.

---

# GoogleSearchTool

> Fluent builder for `google.adk.tools.google_search_tool.GoogleSearchTool`

A built-in tool that is automatically invoked by Gemini 2 models to retrieve search results from Google Search.

## Terminal Methods

### `.build() -> GoogleSearchTool`

Resolve into a native ADK GoogleSearchTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.bypass_multi_tools_limit(value)` | `bool` |
| `.model(value)` | `str | None` |

---

# GoogleTool

> Fluent builder for `google.adk.tools.google_tool.GoogleTool`

GoogleTool class for tools that call Google APIs.

## Constructor

```python
GoogleTool(func)
```

| Argument | Type |
|----------|------|
| `func` | `Callable[..., Any]` |

## Terminal Methods

### `.build() -> GoogleTool`

Resolve into a native ADK GoogleTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials_config(value)` | `Optional[BaseGoogleCredentialsConfig]` |
| `.tool_settings(value)` | `Optional[BaseModel]` |

---

# LoadArtifactsTool

> Fluent builder for `google.adk.tools.load_artifacts_tool.LoadArtifactsTool`

A tool that loads the artifacts and adds them to the session.

## Terminal Methods

### `.build() -> LoadArtifactsTool`

Resolve into a native ADK LoadArtifactsTool.

---

# LoadMcpResourceTool

> Fluent builder for `google.adk.tools.load_mcp_resource_tool.LoadMcpResourceTool`

A tool that loads the MCP resources and adds them to the session.

## Constructor

```python
LoadMcpResourceTool(mcp_toolset)
```

| Argument | Type |
|----------|------|
| `mcp_toolset` | `McpToolset` |

## Terminal Methods

### `.build() -> LoadMcpResourceTool`

Resolve into a native ADK LoadMcpResourceTool.

---

# LoadMemoryTool

> Fluent builder for `google.adk.tools.load_memory_tool.LoadMemoryTool`

A tool that loads the memory for the current user.

## Terminal Methods

### `.build() -> LoadMemoryTool`

Resolve into a native ADK LoadMemoryTool.

---

# LongRunningFunctionTool

> Fluent builder for `google.adk.tools.long_running_tool.LongRunningFunctionTool`

A function tool that returns the result asynchronously.

## Constructor

```python
LongRunningFunctionTool(func)
```

| Argument | Type |
|----------|------|
| `func` | `Callable` |

## Terminal Methods

### `.build() -> LongRunningFunctionTool`

Resolve into a native ADK LongRunningFunctionTool.

---

# MCPTool

> Fluent builder for `google.adk.tools.mcp_tool.mcp_tool.MCPTool`

Deprecated name, use `McpTool` instead.

## Constructor

```python
MCPTool(args, kwargs)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> MCPTool`

Resolve into a native ADK MCPTool.

---

# McpTool

> Fluent builder for `google.adk.tools.mcp_tool.mcp_tool.McpTool`

Turns an MCP Tool into an ADK Tool.

## Constructor

```python
McpTool(mcp_tool, mcp_session_manager)
```

| Argument | Type |
|----------|------|
| `mcp_tool` | `McpBaseTool` |
| `mcp_session_manager` | `MCPSessionManager` |

## Terminal Methods

### `.build() -> McpTool`

Resolve into a native ADK McpTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.auth_scheme(value)` | `Optional[AuthScheme]` |
| `.auth_credential(value)` | `Optional[AuthCredential]` |
| `.require_confirmation(value)` | `Union[bool, Callable[..., bool]]` |
| `.header_provider(value)` | `Optional[Callable[[ReadonlyContext], Dict[str, str]]]` |
| `.progress_callback(value)` | `Optional[Union[ProgressFnT, ProgressCallbackFactory]]` |

---

# MCPToolset

> Fluent builder for `google.adk.tools.mcp_tool.mcp_toolset.MCPToolset`

Deprecated name, use `McpToolset` instead.

## Constructor

```python
MCPToolset(args, kwargs)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> MCPToolset`

Resolve into a native ADK MCPToolset.

---

# McpToolset

> Fluent builder for `google.adk.tools.mcp_tool.mcp_toolset.McpToolset`

Connects to a MCP Server, and retrieves MCP Tools into ADK Tools.

## Constructor

```python
McpToolset(connection_params)
```

| Argument | Type |
|----------|------|
| `connection_params` | `Union[StdioServerParameters, StdioConnectionParams, SseConnectionParams, StreamableHTTPConnectionParams]` |

## Terminal Methods

### `.build() -> McpToolset`

Resolve into a native ADK McpToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.tool_name_prefix(value)` | `Optional[str]` |
| `.errlog(value)` | `TextIO` |
| `.auth_scheme(value)` | `Optional[AuthScheme]` |
| `.auth_credential(value)` | `Optional[AuthCredential]` |
| `.require_confirmation(value)` | `Union[bool, Callable[..., bool]]` |
| `.header_provider(value)` | `Optional[Callable[[ReadonlyContext], Dict[str, str]]]` |
| `.progress_callback(value)` | `Optional[Union[ProgressFnT, ProgressCallbackFactory]]` |
| `.use_mcp_resources(value)` | `Optional[bool]` |

---

# OpenAPIToolset

> Fluent builder for `google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset`

Class for parsing OpenAPI spec into a list of RestApiTool.

## Terminal Methods

### `.build() -> OpenAPIToolset`

Resolve into a native ADK OpenAPIToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.spec_dict(value)` | `Optional[Dict[str, Any]]` |
| `.spec_str(value)` | `Optional[str]` |
| `.spec_str_type(value)` | `Literal['json', 'yaml']` |
| `.auth_scheme(value)` | `Optional[AuthScheme]` |
| `.auth_credential(value)` | `Optional[AuthCredential]` |
| `.credential_key(value)` | `Optional[str]` |
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.tool_name_prefix(value)` | `Optional[str]` |
| `.ssl_verify(value)` | `Optional[Union[bool, str, ssl.SSLContext]]` |
| `.header_provider(value)` | `Optional[Callable[[ReadonlyContext], Dict[str, str]]]` |

---

# RestApiTool

> Fluent builder for `google.adk.tools.openapi_tool.openapi_spec_parser.rest_api_tool.RestApiTool`

A generic tool that interacts with a REST API.

## Constructor

```python
RestApiTool(name, description, endpoint)
```

| Argument | Type |
|----------|------|
| `name` | `str` |
| `description` | `str` |
| `endpoint` | `Union[OperationEndpoint, str]` |

## Terminal Methods

### `.build() -> RestApiTool`

Resolve into a native ADK RestApiTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.operation(value)` | `Union[Operation, str]` |
| `.auth_scheme(value)` | `Optional[Union[AuthScheme, str]]` |
| `.auth_credential(value)` | `Optional[Union[AuthCredential, str]]` |
| `.should_parse_operation(value)` | `Any` |
| `.ssl_verify(value)` | `Optional[Union[bool, str, ssl.SSLContext]]` |
| `.header_provider(value)` | `Optional[Callable[[ReadonlyContext], Dict[str, str]]]` |
| `.credential_key(value)` | `Optional[str]` |

---

# PreloadMemoryTool

> Fluent builder for `google.adk.tools.preload_memory_tool.PreloadMemoryTool`

A tool that preloads the memory for the current user.

## Terminal Methods

### `.build() -> PreloadMemoryTool`

Resolve into a native ADK PreloadMemoryTool.

---

# PubSubToolset

> Fluent builder for `google.adk.tools.pubsub.pubsub_toolset.PubSubToolset`

Pub/Sub Toolset contains tools for interacting with Pub/Sub topics and subscriptions.

## Terminal Methods

### `.build() -> PubSubToolset`

Resolve into a native ADK PubSubToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_filter(value)` | `ToolPredicate | list[str] | None` |
| `.credentials_config(value)` | `PubSubCredentialsConfig | None` |
| `.pubsub_tool_config(value)` | `PubSubToolConfig | None` |

---

# BaseRetrievalTool

> Fluent builder for `google.adk.tools.retrieval.base_retrieval_tool.BaseRetrievalTool`

Fluent builder for BaseRetrievalTool.

## Constructor

```python
BaseRetrievalTool(name, description)
```

| Argument | Type |
|----------|------|
| `name` | `Any` |
| `description` | `Any` |

## Terminal Methods

### `.build() -> BaseRetrievalTool`

Resolve into a native ADK BaseRetrievalTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.is_long_running(value)` | `bool` |
| `.custom_metadata(value)` | `Optional[dict[str, Any]]` |

---

# SetModelResponseTool

> Fluent builder for `google.adk.tools.set_model_response_tool.SetModelResponseTool`

Internal tool used for output schema workaround.

## Constructor

```python
SetModelResponseTool(output_schema)
```

| Argument | Type |
|----------|------|
| `output_schema` | `type[BaseModel]` |

## Terminal Methods

### `.build() -> SetModelResponseTool`

Resolve into a native ADK SetModelResponseTool.

---

# LoadSkillResourceTool

> Fluent builder for `google.adk.tools.skill_toolset.LoadSkillResourceTool`

Tool to load resources (references or assets) from a skill.

## Constructor

```python
LoadSkillResourceTool(toolset)
```

| Argument | Type |
|----------|------|
| `toolset` | `'SkillToolset'` |

## Terminal Methods

### `.build() -> LoadSkillResourceTool`

Resolve into a native ADK LoadSkillResourceTool.

---

# LoadSkillTool

> Fluent builder for `google.adk.tools.skill_toolset.LoadSkillTool`

Tool to load a skill's instructions.

## Constructor

```python
LoadSkillTool(toolset)
```

| Argument | Type |
|----------|------|
| `toolset` | `'SkillToolset'` |

## Terminal Methods

### `.build() -> LoadSkillTool`

Resolve into a native ADK LoadSkillTool.

---

# SkillToolset

> Fluent builder for `google.adk.tools.skill_toolset.SkillToolset`

A toolset for managing and interacting with agent skills.

## Constructor

```python
SkillToolset(skills)
```

| Argument | Type |
|----------|------|
| `skills` | `list[models.Skill]` |

## Terminal Methods

### `.build() -> SkillToolset`

Resolve into a native ADK SkillToolset.

---

# SpannerToolset

> Fluent builder for `google.adk.tools.spanner.spanner_toolset.SpannerToolset`

Spanner Toolset contains tools for interacting with Spanner data, database and table information.

## Terminal Methods

### `.build() -> SpannerToolset`

Resolve into a native ADK SpannerToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_filter(value)` | `Optional[Union[ToolPredicate, List[str]]]` |
| `.credentials_config(value)` | `Optional[SpannerCredentialsConfig]` |
| `.spanner_tool_settings(value)` | `Optional[SpannerToolSettings]` |

---

# ToolboxToolset

> Fluent builder for `google.adk.tools.toolbox_toolset.ToolboxToolset`

A class that provides access to toolbox toolsets.

## Constructor

```python
ToolboxToolset(server_url, kwargs)
```

| Argument | Type |
|----------|------|
| `server_url` | `str` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> ToolboxToolset`

Resolve into a native ADK ToolboxToolset.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.toolset_name(value)` | `Optional[str]` |
| `.tool_names(value)` | `Optional[List[str]]` |
| `.auth_token_getters(value)` | `Optional[Mapping[str, Callable[[], str]]]` |
| `.bound_params(value)` | `Optional[Mapping[str, Union[Callable[[], Any], Any]]]` |
| `.credentials(value)` | `Optional[CredentialConfig]` |
| `.additional_headers(value)` | `Optional[Mapping[str, str]]` |

---

# TransferToAgentTool

> Fluent builder for `google.adk.tools.transfer_to_agent_tool.TransferToAgentTool`

A specialized FunctionTool for agent transfer with enum constraints.

## Constructor

```python
TransferToAgentTool(agent_names)
```

| Argument | Type |
|----------|------|
| `agent_names` | `list[str]` |

## Terminal Methods

### `.build() -> TransferToAgentTool`

Resolve into a native ADK TransferToAgentTool.

---

# UrlContextTool

> Fluent builder for `google.adk.tools.url_context_tool.UrlContextTool`

A built-in tool that is automatically invoked by Gemini 2 models to retrieve content from the URLs and use that content to inform and shape its response.

## Terminal Methods

### `.build() -> UrlContextTool`

Resolve into a native ADK UrlContextTool.

---

# VertexAiSearchTool

> Fluent builder for `google.adk.tools.vertex_ai_search_tool.VertexAiSearchTool`

A built-in tool using Vertex AI Search.

## Terminal Methods

### `.build() -> VertexAiSearchTool`

Resolve into a native ADK VertexAiSearchTool.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.data_store_id(value)` | `Optional[str]` |
| `.data_store_specs(value)` | `Optional[list[types.VertexAISearchDataStoreSpec]]` |
| `.search_engine_id(value)` | `Optional[str]` |
| `.filter(value)` | `Optional[str]` |
| `.max_results(value)` | `Optional[int]` |
| `.bypass_multi_tools_limit(value)` | `bool` |
