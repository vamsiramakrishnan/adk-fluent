# Module: `tool`

## Builders in this module

| Builder                                                                | Description                                                                                                                                               |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [ActiveStreamingTool](builder-ActiveStreamingTool)                     | Manages streaming tool related resources during invocation.                                                                                               |
| [AgentTool](builder-AgentTool)                                         | A tool that wraps an agent.                                                                                                                               |
| [APIHubToolset](builder-APIHubToolset)                                 | APIHubTool generates tools from a given API Hub resource.                                                                                                 |
| [ApplicationIntegrationToolset](builder-ApplicationIntegrationToolset) | ApplicationIntegrationToolset generates tools from a given Application.                                                                                   |
| [IntegrationConnectorTool](builder-IntegrationConnectorTool)           | A tool that wraps a RestApiTool to interact with a specific Application Integration endpoint.                                                             |
| [BaseAuthenticatedTool](builder-BaseAuthenticatedTool)                 | A base tool class that handles authentication before the actual tool logic.                                                                               |
| [BaseTool](builder-BaseTool)                                           | The base class for all tools.                                                                                                                             |
| [BaseToolset](builder-BaseToolset)                                     | Base class for toolset.                                                                                                                                   |
| [BigQueryToolset](builder-BigQueryToolset)                             | BigQuery Toolset contains tools for interacting with BigQuery data and metadata.                                                                          |
| [BigtableToolset](builder-BigtableToolset)                             | Bigtable Toolset contains tools for interacting with Bigtable data and metadata.                                                                          |
| [ComputerUseTool](builder-ComputerUseTool)                             | A tool that wraps computer control functions for use with LLMs.                                                                                           |
| [ComputerUseToolset](builder-ComputerUseToolset)                       | Fluent builder for ComputerUseToolset.                                                                                                                    |
| [DataAgentToolset](builder-DataAgentToolset)                           | Data Agent Toolset contains tools for interacting with data agents.                                                                                       |
| [DiscoveryEngineSearchTool](builder-DiscoveryEngineSearchTool)         | Tool for searching the discovery engine.                                                                                                                  |
| [EnterpriseWebSearchTool](builder-EnterpriseWebSearchTool)             | A Gemini 2+ built-in tool using web grounding for Enterprise compliance.                                                                                  |
| [ExampleTool](builder-ExampleTool)                                     | A tool that adds (few-shot) examples to the LLM request.                                                                                                  |
| [FunctionTool](builder-FunctionTool)                                   | A tool that wraps a user-defined Python function.                                                                                                         |
| [GoogleApiTool](builder-GoogleApiTool)                                 | Fluent builder for GoogleApiTool.                                                                                                                         |
| [GoogleApiToolset](builder-GoogleApiToolset)                           | Google API Toolset contains tools for interacting with Google APIs.                                                                                       |
| [CalendarToolset](builder-CalendarToolset)                             | Auto-generated Calendar toolset based on Google Calendar API v3 spec exposed by Google API discovery API.                                                 |
| [DocsToolset](builder-DocsToolset)                                     | Auto-generated Docs toolset based on Google Docs API v1 spec exposed by Google API discovery API.                                                         |
| [GmailToolset](builder-GmailToolset)                                   | Auto-generated Gmail toolset based on Google Gmail API v1 spec exposed by Google API discovery API.                                                       |
| [SheetsToolset](builder-SheetsToolset)                                 | Auto-generated Sheets toolset based on Google Sheets API v4 spec exposed by Google API discovery API.                                                     |
| [SlidesToolset](builder-SlidesToolset)                                 | Auto-generated Slides toolset based on Google Slides API v1 spec exposed by Google API discovery API.                                                     |
| [YoutubeToolset](builder-YoutubeToolset)                               | Auto-generated YouTube toolset based on YouTube API v3 spec exposed by Google API discovery API.                                                          |
| [GoogleMapsGroundingTool](builder-GoogleMapsGroundingTool)             | A built-in tool that is automatically invoked by Gemini 2 models to ground query results with Google Maps.                                                |
| [GoogleSearchAgentTool](builder-GoogleSearchAgentTool)                 | A tool that wraps a sub-agent that only uses google_search tool.                                                                                          |
| [GoogleSearchTool](builder-GoogleSearchTool)                           | A built-in tool that is automatically invoked by Gemini 2 models to retrieve search results from Google Search.                                           |
| [GoogleTool](builder-GoogleTool)                                       | GoogleTool class for tools that call Google APIs.                                                                                                         |
| [LoadArtifactsTool](builder-LoadArtifactsTool)                         | A tool that loads the artifacts and adds them to the session.                                                                                             |
| [LoadMcpResourceTool](builder-LoadMcpResourceTool)                     | A tool that loads the MCP resources and adds them to the session.                                                                                         |
| [LoadMemoryTool](builder-LoadMemoryTool)                               | A tool that loads the memory for the current user.                                                                                                        |
| [LongRunningFunctionTool](builder-LongRunningFunctionTool)             | A function tool that returns the result asynchronously.                                                                                                   |
| [MCPTool](builder-MCPTool)                                             | Deprecated name, use `McpTool` instead.                                                                                                                   |
| [McpTool](builder-McpTool)                                             | Turns an MCP Tool into an ADK Tool.                                                                                                                       |
| [MCPToolset](builder-MCPToolset)                                       | Deprecated name, use `McpToolset` instead.                                                                                                                |
| [McpToolset](builder-McpToolset)                                       | Connects to a MCP Server, and retrieves MCP Tools into ADK Tools.                                                                                         |
| [OpenAPIToolset](builder-OpenAPIToolset)                               | Class for parsing OpenAPI spec into a list of RestApiTool.                                                                                                |
| [RestApiTool](builder-RestApiTool)                                     | A generic tool that interacts with a REST API.                                                                                                            |
| [PreloadMemoryTool](builder-PreloadMemoryTool)                         | A tool that preloads the memory for the current user.                                                                                                     |
| [PubSubToolset](builder-PubSubToolset)                                 | Pub/Sub Toolset contains tools for interacting with Pub/Sub topics and subscriptions.                                                                     |
| [BaseRetrievalTool](builder-BaseRetrievalTool)                         | Fluent builder for BaseRetrievalTool.                                                                                                                     |
| [SetModelResponseTool](builder-SetModelResponseTool)                   | Internal tool used for output schema workaround.                                                                                                          |
| [LoadSkillResourceTool](builder-LoadSkillResourceTool)                 | Tool to load resources (references or assets) from a skill.                                                                                               |
| [LoadSkillTool](builder-LoadSkillTool)                                 | Tool to load a skill's instructions.                                                                                                                      |
| [SkillToolset](builder-SkillToolset)                                   | A toolset for managing and interacting with agent skills.                                                                                                 |
| [SpannerToolset](builder-SpannerToolset)                               | Spanner Toolset contains tools for interacting with Spanner data, database and table information.                                                         |
| [ToolboxToolset](builder-ToolboxToolset)                               | A class that provides access to toolbox toolsets.                                                                                                         |
| [TransferToAgentTool](builder-TransferToAgentTool)                     | A specialized FunctionTool for agent transfer with enum constraints.                                                                                      |
| [UrlContextTool](builder-UrlContextTool)                               | A built-in tool that is automatically invoked by Gemini 2 models to retrieve content from the URLs and use that content to inform and shape its response. |
| [VertexAiSearchTool](builder-VertexAiSearchTool)                       | A built-in tool using Vertex AI Search.                                                                                                                   |

(builder-ActiveStreamingTool)=

## ActiveStreamingTool

> Fluent builder for `google.adk.agents.active_streaming_tool.ActiveStreamingTool`

Manages streaming tool related resources during invocation.

**Quick start:**

```python
from adk_fluent import ActiveStreamingTool

result = (
    ActiveStreamingTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> ActiveStreamingTool`

Resolve into a native ADK ActiveStreamingTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field            | Type                                |
| ---------------- | ----------------------------------- |
| `.task(value)`   | `Union[Task, NoneType]`             |
| `.stream(value)` | `Union[LiveRequestQueue, NoneType]` |

______________________________________________________________________

(builder-AgentTool)=

## AgentTool

> Fluent builder for `google.adk.tools.agent_tool.AgentTool`

A tool that wraps an agent.

**Quick start:**

```python
from adk_fluent import AgentTool

result = (
    AgentTool("agent_value")
    .build()
)
```

### Constructor

```python
AgentTool(agent: BaseAgent)
```

| Argument | Type        |
| -------- | ----------- |
| `agent`  | `BaseAgent` |

### Control Flow & Execution

#### `.build() -> AgentTool`

Resolve into a native ADK AgentTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                        | Type   |
| ---------------------------- | ------ |
| `.skip_summarization(value)` | `bool` |
| `.include_plugins(value)`    | `bool` |

______________________________________________________________________

(builder-APIHubToolset)=

## APIHubToolset

> Fluent builder for `google.adk.tools.apihub_tool.apihub_toolset.APIHubToolset`

APIHubTool generates tools from a given API Hub resource.

**Quick start:**

```python
from adk_fluent import APIHubToolset

result = (
    APIHubToolset("apihub_resource_name_value")
    .build()
)
```

### Constructor

```python
APIHubToolset(apihub_resource_name: str)
```

| Argument               | Type  |
| ---------------------- | ----- |
| `apihub_resource_name` | `str` |

### Control Flow & Execution

#### `.build() -> APIHubToolset`

Resolve into a native ADK APIHubToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type                                        |
| ------------------------------ | ------------------------------------------- |
| `.access_token(value)`         | `Optional[str]`                             |
| `.service_account_json(value)` | `Optional[str]`                             |
| `.name(value)`                 | `str`                                       |
| `.description(value)`          | `str`                                       |
| `.lazy_load_spec(value)`       | `Any`                                       |
| `.auth_scheme(value)`          | `Optional[AuthScheme]`                      |
| `.auth_credential(value)`      | `Optional[AuthCredential]`                  |
| `.apihub_client(value)`        | `Optional[APIHubClient]`                    |
| `.tool_filter(value)`          | `Optional[Union[ToolPredicate, List[str]]]` |

______________________________________________________________________

(builder-ApplicationIntegrationToolset)=

## ApplicationIntegrationToolset

> Fluent builder for `google.adk.tools.application_integration_tool.application_integration_toolset.ApplicationIntegrationToolset`

ApplicationIntegrationToolset generates tools from a given Application.

**Quick start:**

```python
from adk_fluent import ApplicationIntegrationToolset

result = (
    ApplicationIntegrationToolset("project_value", "location_value")
    .build()
)
```

### Constructor

```python
ApplicationIntegrationToolset(project: str, location: str)
```

| Argument   | Type  |
| ---------- | ----- |
| `project`  | `str` |
| `location` | `str` |

### Control Flow & Execution

#### `.build() -> ApplicationIntegrationToolset`

Resolve into a native ADK ApplicationIntegrationToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                  | Type                                        |
| -------------------------------------- | ------------------------------------------- |
| `.connection_template_override(value)` | `Optional[str]`                             |
| `.integration(value)`                  | `Optional[str]`                             |
| `.triggers(value)`                     | `Optional[List[str]]`                       |
| `.connection(value)`                   | `Optional[str]`                             |
| `.entity_operations(value)`            | `Optional[str]`                             |
| `.actions(value)`                      | `Optional[list[str]]`                       |
| `.tool_name_prefix(value)`             | `Optional[str]`                             |
| `.tool_instructions(value)`            | `Optional[str]`                             |
| `.service_account_json(value)`         | `Optional[str]`                             |
| `.auth_scheme(value)`                  | `Optional[AuthScheme]`                      |
| `.auth_credential(value)`              | `Optional[AuthCredential]`                  |
| `.tool_filter(value)`                  | `Optional[Union[ToolPredicate, List[str]]]` |

______________________________________________________________________

(builder-IntegrationConnectorTool)=

## IntegrationConnectorTool

> Fluent builder for `google.adk.tools.application_integration_tool.integration_connector_tool.IntegrationConnectorTool`

A tool that wraps a RestApiTool to interact with a specific Application Integration endpoint.

**Quick start:**

```python
from adk_fluent import IntegrationConnectorTool

result = (
    IntegrationConnectorTool("name_value", "description_value", "connection_name_value")
    .build()
)
```

### Constructor

```python
IntegrationConnectorTool(name: str, description: str, connection_name: str)
```

| Argument          | Type  |
| ----------------- | ----- |
| `name`            | `str` |
| `description`     | `str` |
| `connection_name` | `str` |

### Control Flow & Execution

#### `.build() -> IntegrationConnectorTool`

Resolve into a native ADK IntegrationConnectorTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                             | Type                                   |
| --------------------------------- | -------------------------------------- |
| `.connection_host(value)`         | `str`                                  |
| `.connection_service_name(value)` | `str`                                  |
| `.entity(value)`                  | `str`                                  |
| `.operation(value)`               | `str`                                  |
| `.action(value)`                  | `str`                                  |
| `.rest_api_tool(value)`           | `RestApiTool`                          |
| `.auth_scheme(value)`             | `Optional[Union[AuthScheme, str]]`     |
| `.auth_credential(value)`         | `Optional[Union[AuthCredential, str]]` |

______________________________________________________________________

(builder-BaseAuthenticatedTool)=

## BaseAuthenticatedTool

> Fluent builder for `google.adk.tools.base_authenticated_tool.BaseAuthenticatedTool`

A base tool class that handles authentication before the actual tool logic.

**Quick start:**

```python
from adk_fluent import BaseAuthenticatedTool

result = (
    BaseAuthenticatedTool("name_value", "description_value")
    .build()
)
```

### Constructor

```python
BaseAuthenticatedTool(name: Any, description: Any)
```

| Argument      | Type  |
| ------------- | ----- |
| `name`        | `Any` |
| `description` | `Any` |

### Control Flow & Execution

#### `.build() -> BaseAuthenticatedTool`

Resolve into a native ADK BaseAuthenticatedTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                | Type                                   |
| ------------------------------------ | -------------------------------------- |
| `.auth_config(value)`                | `AuthConfig`                           |
| `.response_for_auth_required(value)` | `Optional[Union[dict[str, Any], str]]` |

______________________________________________________________________

(builder-BaseTool)=

## BaseTool

> Fluent builder for `google.adk.tools.base_tool.BaseTool`

The base class for all tools.

**Quick start:**

```python
from adk_fluent import BaseTool

result = (
    BaseTool("name_value", "description_value")
    .build()
)
```

### Constructor

```python
BaseTool(name: Any, description: Any)
```

| Argument      | Type  |
| ------------- | ----- |
| `name`        | `Any` |
| `description` | `Any` |

### Control Flow & Execution

#### `.build() -> BaseTool`

Resolve into a native ADK BaseTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                     | Type                       |
| ------------------------- | -------------------------- |
| `.is_long_running(value)` | `bool`                     |
| `.custom_metadata(value)` | `Optional[dict[str, Any]]` |

______________________________________________________________________

(builder-BaseToolset)=

## BaseToolset

> Fluent builder for `google.adk.tools.base_toolset.BaseToolset`

Base class for toolset.

**Quick start:**

```python
from adk_fluent import BaseToolset

result = (
    BaseToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> BaseToolset`

Resolve into a native ADK BaseToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                        |
| -------------------------- | ------------------------------------------- |
| `.tool_filter(value)`      | `Optional[Union[ToolPredicate, List[str]]]` |
| `.tool_name_prefix(value)` | `Optional[str]`                             |

______________________________________________________________________

(builder-BigQueryToolset)=

## BigQueryToolset

> Fluent builder for `google.adk.tools.bigquery.bigquery_toolset.BigQueryToolset`

BigQuery Toolset contains tools for interacting with BigQuery data and metadata.

**Quick start:**

```python
from adk_fluent import BigQueryToolset

result = (
    BigQueryToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> BigQueryToolset`

Resolve into a native ADK BigQueryToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type                                        |
| ------------------------------ | ------------------------------------------- |
| `.tool_filter(value)`          | `Optional[Union[ToolPredicate, List[str]]]` |
| `.credentials_config(value)`   | `Optional[BigQueryCredentialsConfig]`       |
| `.bigquery_tool_config(value)` | `Optional[BigQueryToolConfig]`              |

______________________________________________________________________

(builder-BigtableToolset)=

## BigtableToolset

> Fluent builder for `google.adk.tools.bigtable.bigtable_toolset.BigtableToolset`

Bigtable Toolset contains tools for interacting with Bigtable data and metadata.

**Quick start:**

```python
from adk_fluent import BigtableToolset

result = (
    BigtableToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> BigtableToolset`

Resolve into a native ADK BigtableToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                            | Type                                        |
| -------------------------------- | ------------------------------------------- |
| `.tool_filter(value)`            | `Optional[Union[ToolPredicate, List[str]]]` |
| `.credentials_config(value)`     | `Optional[BigtableCredentialsConfig]`       |
| `.bigtable_tool_settings(value)` | `Optional[BigtableToolSettings]`            |

______________________________________________________________________

(builder-ComputerUseTool)=

## ComputerUseTool

> Fluent builder for `google.adk.tools.computer_use.computer_use_tool.ComputerUseTool`

A tool that wraps computer control functions for use with LLMs.

**Quick start:**

```python
from adk_fluent import ComputerUseTool

result = (
    ComputerUseTool("func_value", "screen_size_value")
    .build()
)
```

### Constructor

```python
ComputerUseTool(func: Callable[..., Any], screen_size: tuple[int, int])
```

| Argument      | Type                 |
| ------------- | -------------------- |
| `func`        | `Callable[..., Any]` |
| `screen_size` | `tuple[int, int]`    |

### Control Flow & Execution

#### `.build() -> ComputerUseTool`

Resolve into a native ADK ComputerUseTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                         | Type              |
| ----------------------------- | ----------------- |
| `.virtual_screen_size(value)` | `tuple[int, int]` |

______________________________________________________________________

(builder-ComputerUseToolset)=

## ComputerUseToolset

> Fluent builder for `google.adk.tools.computer_use.computer_use_toolset.ComputerUseToolset`

Fluent builder for ComputerUseToolset.

**Quick start:**

```python
from adk_fluent import ComputerUseToolset

result = (
    ComputerUseToolset("computer_value")
    .build()
)
```

### Constructor

```python
ComputerUseToolset(computer: BaseComputer)
```

| Argument   | Type           |
| ---------- | -------------- |
| `computer` | `BaseComputer` |

### Control Flow & Execution

#### `.build() -> ComputerUseToolset`

Resolve into a native ADK ComputerUseToolset.

______________________________________________________________________

(builder-DataAgentToolset)=

## DataAgentToolset

> Fluent builder for `google.adk.tools.data_agent.data_agent_toolset.DataAgentToolset`

Data Agent Toolset contains tools for interacting with data agents.

**Quick start:**

```python
from adk_fluent import DataAgentToolset

result = (
    DataAgentToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> DataAgentToolset`

Resolve into a native ADK DataAgentToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                            | Type                                        |
| -------------------------------- | ------------------------------------------- |
| `.tool_filter(value)`            | `Optional[Union[ToolPredicate, List[str]]]` |
| `.credentials_config(value)`     | `Optional[DataAgentCredentialsConfig]`      |
| `.data_agent_tool_config(value)` | `Optional[DataAgentToolConfig]`             |

______________________________________________________________________

(builder-DiscoveryEngineSearchTool)=

## DiscoveryEngineSearchTool

> Fluent builder for `google.adk.tools.discovery_engine_search_tool.DiscoveryEngineSearchTool`

Tool for searching the discovery engine.

**Quick start:**

```python
from adk_fluent import DiscoveryEngineSearchTool

result = (
    DiscoveryEngineSearchTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> DiscoveryEngineSearchTool`

Resolve into a native ADK DiscoveryEngineSearchTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                                |
| -------------------------- | --------------------------------------------------- |
| `.data_store_id(value)`    | `Optional[str]`                                     |
| `.data_store_specs(value)` | `Optional[list[types.VertexAISearchDataStoreSpec]]` |
| `.search_engine_id(value)` | `Optional[str]`                                     |
| `.filter(value)`           | `Optional[str]`                                     |
| `.max_results(value)`      | `Optional[int]`                                     |

______________________________________________________________________

(builder-EnterpriseWebSearchTool)=

## EnterpriseWebSearchTool

> Fluent builder for `google.adk.tools.enterprise_search_tool.EnterpriseWebSearchTool`

A Gemini 2+ built-in tool using web grounding for Enterprise compliance.

**Quick start:**

```python
from adk_fluent import EnterpriseWebSearchTool

result = (
    EnterpriseWebSearchTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> EnterpriseWebSearchTool`

Resolve into a native ADK EnterpriseWebSearchTool.

______________________________________________________________________

(builder-ExampleTool)=

## ExampleTool

> Fluent builder for `google.adk.tools.example_tool.ExampleTool`

A tool that adds (few-shot) examples to the LLM request.

**Quick start:**

```python
from adk_fluent import ExampleTool

result = (
    ExampleTool("examples_value")
    .build()
)
```

### Constructor

```python
ExampleTool(examples: Union[list[Example], BaseExampleProvider])
```

| Argument   | Type                                        |
| ---------- | ------------------------------------------- |
| `examples` | `Union[list[Example], BaseExampleProvider]` |

### Control Flow & Execution

#### `.build() -> ExampleTool`

Resolve into a native ADK ExampleTool.

______________________________________________________________________

(builder-FunctionTool)=

## FunctionTool

> Fluent builder for `google.adk.tools.function_tool.FunctionTool`

A tool that wraps a user-defined Python function.

**Quick start:**

```python
from adk_fluent import FunctionTool

result = (
    FunctionTool("func_value")
    .build()
)
```

### Constructor

```python
FunctionTool(func: Callable[..., Any])
```

| Argument | Type                 |
| -------- | -------------------- |
| `func`   | `Callable[..., Any]` |

### Control Flow & Execution

#### `.build() -> FunctionTool`

Resolve into a native ADK FunctionTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type                               |
| ------------------------------ | ---------------------------------- |
| `.require_confirmation(value)` | `Union[bool, Callable[..., bool]]` |

______________________________________________________________________

(builder-GoogleApiTool)=

## GoogleApiTool

> Fluent builder for `google.adk.tools.google_api_tool.google_api_tool.GoogleApiTool`

Fluent builder for GoogleApiTool.

**Quick start:**

```python
from adk_fluent import GoogleApiTool

result = (
    GoogleApiTool("rest_api_tool_value")
    .build()
)
```

### Constructor

```python
GoogleApiTool(rest_api_tool: RestApiTool)
```

| Argument        | Type          |
| --------------- | ------------- |
| `rest_api_tool` | `RestApiTool` |

### Control Flow & Execution

#### `.build() -> GoogleApiTool`

Resolve into a native ADK GoogleApiTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                        | Type                       |
| ---------------------------- | -------------------------- |
| `.client_id(value)`          | `Optional[str]`            |
| `.client_secret(value)`      | `Optional[str]`            |
| `.service_account(value)`    | `Optional[ServiceAccount]` |
| `.additional_headers(value)` | `Optional[Dict[str, str]]` |

______________________________________________________________________

(builder-GoogleApiToolset)=

## GoogleApiToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolset.GoogleApiToolset`

Google API Toolset contains tools for interacting with Google APIs.

**Quick start:**

```python
from adk_fluent import GoogleApiToolset

result = (
    GoogleApiToolset("api_name_value", "api_version_value")
    .build()
)
```

### Constructor

```python
GoogleApiToolset(api_name: str, api_version: str)
```

| Argument      | Type  |
| ------------- | ----- |
| `api_name`    | `str` |
| `api_version` | `str` |

### Control Flow & Execution

#### `.build() -> GoogleApiToolset`

Resolve into a native ADK GoogleApiToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                        | Type                                        |
| ---------------------------- | ------------------------------------------- |
| `.client_id(value)`          | `Optional[str]`                             |
| `.client_secret(value)`      | `Optional[str]`                             |
| `.tool_filter(value)`        | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)`    | `Optional[ServiceAccount]`                  |
| `.tool_name_prefix(value)`   | `Optional[str]`                             |
| `.additional_headers(value)` | `Optional[Dict[str, str]]`                  |

______________________________________________________________________

(builder-CalendarToolset)=

## CalendarToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.CalendarToolset`

Auto-generated Calendar toolset based on Google Calendar API v3 spec exposed by Google API discovery API.

**Quick start:**

```python
from adk_fluent import CalendarToolset

result = (
    CalendarToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> CalendarToolset`

Resolve into a native ADK CalendarToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                        |
| -------------------------- | ------------------------------------------- |
| `.client_id(value)`        | `Optional[str]`                             |
| `.client_secret(value)`    | `Optional[str]`                             |
| `.tool_filter(value)`      | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)`  | `Optional[ServiceAccount]`                  |
| `.tool_name_prefix(value)` | `Optional[str]`                             |

______________________________________________________________________

(builder-DocsToolset)=

## DocsToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.DocsToolset`

Auto-generated Docs toolset based on Google Docs API v1 spec exposed by Google API discovery API.

**Quick start:**

```python
from adk_fluent import DocsToolset

result = (
    DocsToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> DocsToolset`

Resolve into a native ADK DocsToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                        |
| -------------------------- | ------------------------------------------- |
| `.client_id(value)`        | `Optional[str]`                             |
| `.client_secret(value)`    | `Optional[str]`                             |
| `.tool_filter(value)`      | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)`  | `Optional[ServiceAccount]`                  |
| `.tool_name_prefix(value)` | `Optional[str]`                             |

______________________________________________________________________

(builder-GmailToolset)=

## GmailToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.GmailToolset`

Auto-generated Gmail toolset based on Google Gmail API v1 spec exposed by Google API discovery API.

**Quick start:**

```python
from adk_fluent import GmailToolset

result = (
    GmailToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> GmailToolset`

Resolve into a native ADK GmailToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                        |
| -------------------------- | ------------------------------------------- |
| `.client_id(value)`        | `Optional[str]`                             |
| `.client_secret(value)`    | `Optional[str]`                             |
| `.tool_filter(value)`      | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)`  | `Optional[ServiceAccount]`                  |
| `.tool_name_prefix(value)` | `Optional[str]`                             |

______________________________________________________________________

(builder-SheetsToolset)=

## SheetsToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.SheetsToolset`

Auto-generated Sheets toolset based on Google Sheets API v4 spec exposed by Google API discovery API.

**Quick start:**

```python
from adk_fluent import SheetsToolset

result = (
    SheetsToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> SheetsToolset`

Resolve into a native ADK SheetsToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                        |
| -------------------------- | ------------------------------------------- |
| `.client_id(value)`        | `Optional[str]`                             |
| `.client_secret(value)`    | `Optional[str]`                             |
| `.tool_filter(value)`      | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)`  | `Optional[ServiceAccount]`                  |
| `.tool_name_prefix(value)` | `Optional[str]`                             |

______________________________________________________________________

(builder-SlidesToolset)=

## SlidesToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.SlidesToolset`

Auto-generated Slides toolset based on Google Slides API v1 spec exposed by Google API discovery API.

**Quick start:**

```python
from adk_fluent import SlidesToolset

result = (
    SlidesToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> SlidesToolset`

Resolve into a native ADK SlidesToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                        |
| -------------------------- | ------------------------------------------- |
| `.client_id(value)`        | `Optional[str]`                             |
| `.client_secret(value)`    | `Optional[str]`                             |
| `.tool_filter(value)`      | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)`  | `Optional[ServiceAccount]`                  |
| `.tool_name_prefix(value)` | `Optional[str]`                             |

______________________________________________________________________

(builder-YoutubeToolset)=

## YoutubeToolset

> Fluent builder for `google.adk.tools.google_api_tool.google_api_toolsets.YoutubeToolset`

Auto-generated YouTube toolset based on YouTube API v3 spec exposed by Google API discovery API.

**Quick start:**

```python
from adk_fluent import YoutubeToolset

result = (
    YoutubeToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> YoutubeToolset`

Resolve into a native ADK YoutubeToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                        |
| -------------------------- | ------------------------------------------- |
| `.client_id(value)`        | `Optional[str]`                             |
| `.client_secret(value)`    | `Optional[str]`                             |
| `.tool_filter(value)`      | `Optional[Union[ToolPredicate, List[str]]]` |
| `.service_account(value)`  | `Optional[ServiceAccount]`                  |
| `.tool_name_prefix(value)` | `Optional[str]`                             |

______________________________________________________________________

(builder-GoogleMapsGroundingTool)=

## GoogleMapsGroundingTool

> Fluent builder for `google.adk.tools.google_maps_grounding_tool.GoogleMapsGroundingTool`

A built-in tool that is automatically invoked by Gemini 2 models to ground query results with Google Maps.

**Quick start:**

```python
from adk_fluent import GoogleMapsGroundingTool

result = (
    GoogleMapsGroundingTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> GoogleMapsGroundingTool`

Resolve into a native ADK GoogleMapsGroundingTool.

______________________________________________________________________

(builder-GoogleSearchAgentTool)=

## GoogleSearchAgentTool

> Fluent builder for `google.adk.tools.google_search_agent_tool.GoogleSearchAgentTool`

A tool that wraps a sub-agent that only uses google_search tool.

**Quick start:**

```python
from adk_fluent import GoogleSearchAgentTool

result = (
    GoogleSearchAgentTool("agent_value")
    .build()
)
```

### Constructor

```python
GoogleSearchAgentTool(agent: LlmAgent)
```

| Argument | Type       |
| -------- | ---------- |
| `agent`  | `LlmAgent` |

### Control Flow & Execution

#### `.build() -> GoogleSearchAgentTool`

Resolve into a native ADK GoogleSearchAgentTool.

______________________________________________________________________

(builder-GoogleSearchTool)=

## GoogleSearchTool

> Fluent builder for `google.adk.tools.google_search_tool.GoogleSearchTool`

A built-in tool that is automatically invoked by Gemini 2 models to retrieve search results from Google Search.

**Quick start:**

```python
from adk_fluent import GoogleSearchTool

result = (
    GoogleSearchTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> GoogleSearchTool`

Resolve into a native ADK GoogleSearchTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                              | Type   |
| ---------------------------------- | ------ |
| `.bypass_multi_tools_limit(value)` | `bool` |
| `.model(value)`                    | \`str  |

______________________________________________________________________

(builder-GoogleTool)=

## GoogleTool

> Fluent builder for `google.adk.tools.google_tool.GoogleTool`

GoogleTool class for tools that call Google APIs.

**Quick start:**

```python
from adk_fluent import GoogleTool

result = (
    GoogleTool("func_value")
    .build()
)
```

### Constructor

```python
GoogleTool(func: Callable[..., Any])
```

| Argument | Type                 |
| -------- | -------------------- |
| `func`   | `Callable[..., Any]` |

### Control Flow & Execution

#### `.build() -> GoogleTool`

Resolve into a native ADK GoogleTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                        | Type                                    |
| ---------------------------- | --------------------------------------- |
| `.credentials_config(value)` | `Optional[BaseGoogleCredentialsConfig]` |
| `.tool_settings(value)`      | `Optional[BaseModel]`                   |

______________________________________________________________________

(builder-LoadArtifactsTool)=

## LoadArtifactsTool

> Fluent builder for `google.adk.tools.load_artifacts_tool.LoadArtifactsTool`

A tool that loads the artifacts and adds them to the session.

**Quick start:**

```python
from adk_fluent import LoadArtifactsTool

result = (
    LoadArtifactsTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> LoadArtifactsTool`

Resolve into a native ADK LoadArtifactsTool.

______________________________________________________________________

(builder-LoadMcpResourceTool)=

## LoadMcpResourceTool

> Fluent builder for `google.adk.tools.load_mcp_resource_tool.LoadMcpResourceTool`

A tool that loads the MCP resources and adds them to the session.

**Quick start:**

```python
from adk_fluent import LoadMcpResourceTool

result = (
    LoadMcpResourceTool("mcp_toolset_value")
    .build()
)
```

### Constructor

```python
LoadMcpResourceTool(mcp_toolset: McpToolset)
```

| Argument      | Type         |
| ------------- | ------------ |
| `mcp_toolset` | `McpToolset` |

### Control Flow & Execution

#### `.build() -> LoadMcpResourceTool`

Resolve into a native ADK LoadMcpResourceTool.

______________________________________________________________________

(builder-LoadMemoryTool)=

## LoadMemoryTool

> Fluent builder for `google.adk.tools.load_memory_tool.LoadMemoryTool`

A tool that loads the memory for the current user.

**Quick start:**

```python
from adk_fluent import LoadMemoryTool

result = (
    LoadMemoryTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> LoadMemoryTool`

Resolve into a native ADK LoadMemoryTool.

______________________________________________________________________

(builder-LongRunningFunctionTool)=

## LongRunningFunctionTool

> Fluent builder for `google.adk.tools.long_running_tool.LongRunningFunctionTool`

A function tool that returns the result asynchronously.

**Quick start:**

```python
from adk_fluent import LongRunningFunctionTool

result = (
    LongRunningFunctionTool("func_value")
    .build()
)
```

### Constructor

```python
LongRunningFunctionTool(func: Callable)
```

| Argument | Type       |
| -------- | ---------- |
| `func`   | `Callable` |

### Control Flow & Execution

#### `.build() -> LongRunningFunctionTool`

Resolve into a native ADK LongRunningFunctionTool.

______________________________________________________________________

(builder-MCPTool)=

## MCPTool

> Fluent builder for `google.adk.tools.mcp_tool.mcp_tool.MCPTool`

Deprecated name, use `McpTool` instead.

**Quick start:**

```python
from adk_fluent import MCPTool

result = (
    MCPTool("args_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
MCPTool(args: Any, kwargs: Any)
```

| Argument | Type  |
| -------- | ----- |
| `args`   | `Any` |
| `kwargs` | `Any` |

### Control Flow & Execution

#### `.build() -> MCPTool`

Resolve into a native ADK MCPTool.

______________________________________________________________________

(builder-McpTool)=

## McpTool

> Fluent builder for `google.adk.tools.mcp_tool.mcp_tool.McpTool`

Turns an MCP Tool into an ADK Tool.

**Quick start:**

```python
from adk_fluent import McpTool

result = (
    McpTool("mcp_tool_value", "mcp_session_manager_value")
    .build()
)
```

### Constructor

```python
McpTool(mcp_tool: McpBaseTool, mcp_session_manager: MCPSessionManager)
```

| Argument              | Type                |
| --------------------- | ------------------- |
| `mcp_tool`            | `McpBaseTool`       |
| `mcp_session_manager` | `MCPSessionManager` |

### Control Flow & Execution

#### `.build() -> McpTool`

Resolve into a native ADK McpTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type                                                    |
| ------------------------------ | ------------------------------------------------------- |
| `.auth_scheme(value)`          | `Optional[AuthScheme]`                                  |
| `.auth_credential(value)`      | `Optional[AuthCredential]`                              |
| `.require_confirmation(value)` | `Union[bool, Callable[..., bool]]`                      |
| `.header_provider(value)`      | `Optional[Callable[[ReadonlyContext], Dict[str, str]]]` |
| `.progress_callback(value)`    | `Optional[Union[ProgressFnT, ProgressCallbackFactory]]` |

______________________________________________________________________

(builder-MCPToolset)=

## MCPToolset

> Fluent builder for `google.adk.tools.mcp_tool.mcp_toolset.MCPToolset`

Deprecated name, use `McpToolset` instead.

**Quick start:**

```python
from adk_fluent import MCPToolset

result = (
    MCPToolset("args_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
MCPToolset(args: Any, kwargs: Any)
```

| Argument | Type  |
| -------- | ----- |
| `args`   | `Any` |
| `kwargs` | `Any` |

### Control Flow & Execution

#### `.build() -> MCPToolset`

Resolve into a native ADK MCPToolset.

______________________________________________________________________

(builder-McpToolset)=

## McpToolset

> Fluent builder for `google.adk.tools.mcp_tool.mcp_toolset.McpToolset`

Connects to a MCP Server, and retrieves MCP Tools into ADK Tools.

**Quick start:**

```python
from adk_fluent import McpToolset

result = (
    McpToolset("connection_params_value")
    .build()
)
```

### Constructor

```python
McpToolset(connection_params: Union[StdioServerParameters, StdioConnectionParams, SseConnectionParams, StreamableHTTPConnectionParams])
```

| Argument            | Type                                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `connection_params` | `Union[StdioServerParameters, StdioConnectionParams, SseConnectionParams, StreamableHTTPConnectionParams]` |

### Control Flow & Execution

#### `.build() -> McpToolset`

Resolve into a native ADK McpToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type                                                    |
| ------------------------------ | ------------------------------------------------------- |
| `.tool_filter(value)`          | `Optional[Union[ToolPredicate, List[str]]]`             |
| `.tool_name_prefix(value)`     | `Optional[str]`                                         |
| `.errlog(value)`               | `TextIO`                                                |
| `.auth_scheme(value)`          | `Optional[AuthScheme]`                                  |
| `.auth_credential(value)`      | `Optional[AuthCredential]`                              |
| `.require_confirmation(value)` | `Union[bool, Callable[..., bool]]`                      |
| `.header_provider(value)`      | `Optional[Callable[[ReadonlyContext], Dict[str, str]]]` |
| `.progress_callback(value)`    | `Optional[Union[ProgressFnT, ProgressCallbackFactory]]` |
| `.use_mcp_resources(value)`    | `Optional[bool]`                                        |

______________________________________________________________________

(builder-OpenAPIToolset)=

## OpenAPIToolset

> Fluent builder for `google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset`

Class for parsing OpenAPI spec into a list of RestApiTool.

**Quick start:**

```python
from adk_fluent import OpenAPIToolset

result = (
    OpenAPIToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> OpenAPIToolset`

Resolve into a native ADK OpenAPIToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                      | Type                                                    |
| -------------------------- | ------------------------------------------------------- |
| `.spec_dict(value)`        | `Optional[Dict[str, Any]]`                              |
| `.spec_str(value)`         | `Optional[str]`                                         |
| `.spec_str_type(value)`    | `Literal['json', 'yaml']`                               |
| `.auth_scheme(value)`      | `Optional[AuthScheme]`                                  |
| `.auth_credential(value)`  | `Optional[AuthCredential]`                              |
| `.credential_key(value)`   | `Optional[str]`                                         |
| `.tool_filter(value)`      | `Optional[Union[ToolPredicate, List[str]]]`             |
| `.tool_name_prefix(value)` | `Optional[str]`                                         |
| `.ssl_verify(value)`       | `Optional[Union[bool, str, ssl.SSLContext]]`            |
| `.header_provider(value)`  | `Optional[Callable[[ReadonlyContext], Dict[str, str]]]` |

______________________________________________________________________

(builder-RestApiTool)=

## RestApiTool

> Fluent builder for `google.adk.tools.openapi_tool.openapi_spec_parser.rest_api_tool.RestApiTool`

A generic tool that interacts with a REST API.

**Quick start:**

```python
from adk_fluent import RestApiTool

result = (
    RestApiTool("name_value", "description_value", "endpoint_value")
    .build()
)
```

### Constructor

```python
RestApiTool(name: str, description: str, endpoint: Union[OperationEndpoint, str])
```

| Argument      | Type                            |
| ------------- | ------------------------------- |
| `name`        | `str`                           |
| `description` | `str`                           |
| `endpoint`    | `Union[OperationEndpoint, str]` |

### Control Flow & Execution

#### `.build() -> RestApiTool`

Resolve into a native ADK RestApiTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                            | Type                                                    |
| -------------------------------- | ------------------------------------------------------- |
| `.operation(value)`              | `Union[Operation, str]`                                 |
| `.auth_scheme(value)`            | `Optional[Union[AuthScheme, str]]`                      |
| `.auth_credential(value)`        | `Optional[Union[AuthCredential, str]]`                  |
| `.should_parse_operation(value)` | `Any`                                                   |
| `.ssl_verify(value)`             | `Optional[Union[bool, str, ssl.SSLContext]]`            |
| `.header_provider(value)`        | `Optional[Callable[[ReadonlyContext], Dict[str, str]]]` |
| `.credential_key(value)`         | `Optional[str]`                                         |

______________________________________________________________________

(builder-PreloadMemoryTool)=

## PreloadMemoryTool

> Fluent builder for `google.adk.tools.preload_memory_tool.PreloadMemoryTool`

A tool that preloads the memory for the current user.

**Quick start:**

```python
from adk_fluent import PreloadMemoryTool

result = (
    PreloadMemoryTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> PreloadMemoryTool`

Resolve into a native ADK PreloadMemoryTool.

______________________________________________________________________

(builder-PubSubToolset)=

## PubSubToolset

> Fluent builder for `google.adk.tools.pubsub.pubsub_toolset.PubSubToolset`

Pub/Sub Toolset contains tools for interacting with Pub/Sub topics and subscriptions.

**Quick start:**

```python
from adk_fluent import PubSubToolset

result = (
    PubSubToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> PubSubToolset`

Resolve into a native ADK PubSubToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                        | Type                      |
| ---------------------------- | ------------------------- |
| `.tool_filter(value)`        | \`ToolPredicate           |
| `.credentials_config(value)` | \`PubSubCredentialsConfig |
| `.pubsub_tool_config(value)` | \`PubSubToolConfig        |

______________________________________________________________________

(builder-BaseRetrievalTool)=

## BaseRetrievalTool

> Fluent builder for `google.adk.tools.retrieval.base_retrieval_tool.BaseRetrievalTool`

Fluent builder for BaseRetrievalTool.

**Quick start:**

```python
from adk_fluent import BaseRetrievalTool

result = (
    BaseRetrievalTool("name_value", "description_value")
    .build()
)
```

### Constructor

```python
BaseRetrievalTool(name: Any, description: Any)
```

| Argument      | Type  |
| ------------- | ----- |
| `name`        | `Any` |
| `description` | `Any` |

### Control Flow & Execution

#### `.build() -> BaseRetrievalTool`

Resolve into a native ADK BaseRetrievalTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                     | Type                       |
| ------------------------- | -------------------------- |
| `.is_long_running(value)` | `bool`                     |
| `.custom_metadata(value)` | `Optional[dict[str, Any]]` |

______________________________________________________________________

(builder-SetModelResponseTool)=

## SetModelResponseTool

> Fluent builder for `google.adk.tools.set_model_response_tool.SetModelResponseTool`

Internal tool used for output schema workaround.

**Quick start:**

```python
from adk_fluent import SetModelResponseTool

result = (
    SetModelResponseTool("output_schema_value")
    .build()
)
```

### Constructor

```python
SetModelResponseTool(output_schema: type[BaseModel])
```

| Argument        | Type              |
| --------------- | ----------------- |
| `output_schema` | `type[BaseModel]` |

### Control Flow & Execution

#### `.build() -> SetModelResponseTool`

Resolve into a native ADK SetModelResponseTool.

______________________________________________________________________

(builder-LoadSkillResourceTool)=

## LoadSkillResourceTool

> Fluent builder for `google.adk.tools.skill_toolset.LoadSkillResourceTool`

Tool to load resources (references or assets) from a skill.

**Quick start:**

```python
from adk_fluent import LoadSkillResourceTool

result = (
    LoadSkillResourceTool("toolset_value")
    .build()
)
```

### Constructor

```python
LoadSkillResourceTool(toolset: 'SkillToolset')
```

| Argument  | Type             |
| --------- | ---------------- |
| `toolset` | `'SkillToolset'` |

### Control Flow & Execution

#### `.build() -> LoadSkillResourceTool`

Resolve into a native ADK LoadSkillResourceTool.

______________________________________________________________________

(builder-LoadSkillTool)=

## LoadSkillTool

> Fluent builder for `google.adk.tools.skill_toolset.LoadSkillTool`

Tool to load a skill's instructions.

**Quick start:**

```python
from adk_fluent import LoadSkillTool

result = (
    LoadSkillTool("toolset_value")
    .build()
)
```

### Constructor

```python
LoadSkillTool(toolset: 'SkillToolset')
```

| Argument  | Type             |
| --------- | ---------------- |
| `toolset` | `'SkillToolset'` |

### Control Flow & Execution

#### `.build() -> LoadSkillTool`

Resolve into a native ADK LoadSkillTool.

______________________________________________________________________

(builder-SkillToolset)=

## SkillToolset

> Fluent builder for `google.adk.tools.skill_toolset.SkillToolset`

A toolset for managing and interacting with agent skills.

**Quick start:**

```python
from adk_fluent import SkillToolset

result = (
    SkillToolset("skills_value")
    .build()
)
```

### Constructor

```python
SkillToolset(skills: list[models.Skill])
```

| Argument | Type                 |
| -------- | -------------------- |
| `skills` | `list[models.Skill]` |

### Control Flow & Execution

#### `.build() -> SkillToolset`

Resolve into a native ADK SkillToolset.

______________________________________________________________________

(builder-SpannerToolset)=

## SpannerToolset

> Fluent builder for `google.adk.tools.spanner.spanner_toolset.SpannerToolset`

Spanner Toolset contains tools for interacting with Spanner data, database and table information.

**Quick start:**

```python
from adk_fluent import SpannerToolset

result = (
    SpannerToolset()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> SpannerToolset`

Resolve into a native ADK SpannerToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                           | Type                                        |
| ------------------------------- | ------------------------------------------- |
| `.tool_filter(value)`           | `Optional[Union[ToolPredicate, List[str]]]` |
| `.credentials_config(value)`    | `Optional[SpannerCredentialsConfig]`        |
| `.spanner_tool_settings(value)` | `Optional[SpannerToolSettings]`             |

______________________________________________________________________

(builder-ToolboxToolset)=

## ToolboxToolset

> Fluent builder for `google.adk.tools.toolbox_toolset.ToolboxToolset`

A class that provides access to toolbox toolsets.

**Quick start:**

```python
from adk_fluent import ToolboxToolset

result = (
    ToolboxToolset("server_url_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
ToolboxToolset(server_url: str, kwargs: Any)
```

| Argument     | Type  |
| ------------ | ----- |
| `server_url` | `str` |
| `kwargs`     | `Any` |

### Control Flow & Execution

#### `.build() -> ToolboxToolset`

Resolve into a native ADK ToolboxToolset.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                        | Type                                                    |
| ---------------------------- | ------------------------------------------------------- |
| `.toolset_name(value)`       | `Optional[str]`                                         |
| `.tool_names(value)`         | `Optional[List[str]]`                                   |
| `.auth_token_getters(value)` | `Optional[Mapping[str, Callable[[], str]]]`             |
| `.bound_params(value)`       | `Optional[Mapping[str, Union[Callable[[], Any], Any]]]` |
| `.credentials(value)`        | `Optional[CredentialConfig]`                            |
| `.additional_headers(value)` | `Optional[Mapping[str, str]]`                           |

______________________________________________________________________

(builder-TransferToAgentTool)=

## TransferToAgentTool

> Fluent builder for `google.adk.tools.transfer_to_agent_tool.TransferToAgentTool`

A specialized FunctionTool for agent transfer with enum constraints.

**Quick start:**

```python
from adk_fluent import TransferToAgentTool

result = (
    TransferToAgentTool("agent_names_value")
    .build()
)
```

### Constructor

```python
TransferToAgentTool(agent_names: list[str])
```

| Argument      | Type        |
| ------------- | ----------- |
| `agent_names` | `list[str]` |

### Control Flow & Execution

#### `.build() -> TransferToAgentTool`

Resolve into a native ADK TransferToAgentTool.

______________________________________________________________________

(builder-UrlContextTool)=

## UrlContextTool

> Fluent builder for `google.adk.tools.url_context_tool.UrlContextTool`

A built-in tool that is automatically invoked by Gemini 2 models to retrieve content from the URLs and use that content to inform and shape its response.

**Quick start:**

```python
from adk_fluent import UrlContextTool

result = (
    UrlContextTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> UrlContextTool`

Resolve into a native ADK UrlContextTool.

______________________________________________________________________

(builder-VertexAiSearchTool)=

## VertexAiSearchTool

> Fluent builder for `google.adk.tools.vertex_ai_search_tool.VertexAiSearchTool`

A built-in tool using Vertex AI Search.

**Quick start:**

```python
from adk_fluent import VertexAiSearchTool

result = (
    VertexAiSearchTool()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> VertexAiSearchTool`

Resolve into a native ADK VertexAiSearchTool.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                              | Type                                                |
| ---------------------------------- | --------------------------------------------------- |
| `.data_store_id(value)`            | `Optional[str]`                                     |
| `.data_store_specs(value)`         | `Optional[list[types.VertexAISearchDataStoreSpec]]` |
| `.search_engine_id(value)`         | `Optional[str]`                                     |
| `.filter(value)`                   | `Optional[str]`                                     |
| `.max_results(value)`              | `Optional[int]`                                     |
| `.bypass_multi_tools_limit(value)` | `bool`                                              |
