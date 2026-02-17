# Migration Guide: Native ADK to adk-fluent

This guide maps every ADK class to its adk-fluent builder equivalent,
and lists field name mappings for builders that define aliases.

## Class Mapping

| Native ADK Class | adk-fluent Builder | Import |
|------------------|-------------------|--------|
| `APIHubToolset` | `APIHubToolset` | `from adk_fluent import APIHubToolset` |
| `ActiveStreamingTool` | `ActiveStreamingTool` | `from adk_fluent import ActiveStreamingTool` |
| `LlmAgent` | `Agent` | `from adk_fluent import Agent` |
| `AgentConfig` | `AgentConfig` | `from adk_fluent import AgentConfig` |
| `AgentEngineSandboxCodeExecutor` | `AgentEngineSandboxCodeExecutor` | `from adk_fluent import AgentEngineSandboxCodeExecutor` |
| `AgentRefConfig` | `AgentRefConfig` | `from adk_fluent import AgentRefConfig` |
| `AgentSimulatorConfig` | `AgentSimulatorConfig` | `from adk_fluent import AgentSimulatorConfig` |
| `AgentSimulatorPlugin` | `AgentSimulatorPlugin` | `from adk_fluent import AgentSimulatorPlugin` |
| `AgentTool` | `AgentTool` | `from adk_fluent import AgentTool` |
| `AgentToolConfig` | `AgentToolConfig` | `from adk_fluent import AgentToolConfig` |
| `App` | `App` | `from adk_fluent import App` |
| `ApplicationIntegrationToolset` | `ApplicationIntegrationToolset` | `from adk_fluent import ApplicationIntegrationToolset` |
| `ArgumentConfig` | `ArgumentConfig` | `from adk_fluent import ArgumentConfig` |
| `AudioCacheConfig` | `AudioCacheConfig` | `from adk_fluent import AudioCacheConfig` |
| `BaseAgent` | `BaseAgent` | `from adk_fluent import BaseAgent` |
| `BaseAgentConfig` | `BaseAgentConfig` | `from adk_fluent import BaseAgentConfig` |
| `BaseArtifactService` | `BaseArtifactService` | `from adk_fluent import BaseArtifactService` |
| `BaseAuthenticatedTool` | `BaseAuthenticatedTool` | `from adk_fluent import BaseAuthenticatedTool` |
| `BaseCodeExecutor` | `BaseCodeExecutor` | `from adk_fluent import BaseCodeExecutor` |
| `BaseGoogleCredentialsConfig` | `BaseGoogleCredentialsConfig` | `from adk_fluent import BaseGoogleCredentialsConfig` |
| `BaseMemoryService` | `BaseMemoryService` | `from adk_fluent import BaseMemoryService` |
| `BasePlanner` | `BasePlanner` | `from adk_fluent import BasePlanner` |
| `BasePlugin` | `BasePlugin` | `from adk_fluent import BasePlugin` |
| `BaseRetrievalTool` | `BaseRetrievalTool` | `from adk_fluent import BaseRetrievalTool` |
| `BaseSessionService` | `BaseSessionService` | `from adk_fluent import BaseSessionService` |
| `BaseTool` | `BaseTool` | `from adk_fluent import BaseTool` |
| `BaseToolConfig` | `BaseToolConfig` | `from adk_fluent import BaseToolConfig` |
| `BaseToolset` | `BaseToolset` | `from adk_fluent import BaseToolset` |
| `BigQueryAgentAnalyticsPlugin` | `BigQueryAgentAnalyticsPlugin` | `from adk_fluent import BigQueryAgentAnalyticsPlugin` |
| `BigQueryCredentialsConfig` | `BigQueryCredentialsConfig` | `from adk_fluent import BigQueryCredentialsConfig` |
| `BigQueryLoggerConfig` | `BigQueryLoggerConfig` | `from adk_fluent import BigQueryLoggerConfig` |
| `BigQueryToolConfig` | `BigQueryToolConfig` | `from adk_fluent import BigQueryToolConfig` |
| `BigQueryToolset` | `BigQueryToolset` | `from adk_fluent import BigQueryToolset` |
| `BigtableCredentialsConfig` | `BigtableCredentialsConfig` | `from adk_fluent import BigtableCredentialsConfig` |
| `BigtableToolset` | `BigtableToolset` | `from adk_fluent import BigtableToolset` |
| `BuiltInCodeExecutor` | `BuiltInCodeExecutor` | `from adk_fluent import BuiltInCodeExecutor` |
| `BuiltInPlanner` | `BuiltInPlanner` | `from adk_fluent import BuiltInPlanner` |
| `CalendarToolset` | `CalendarToolset` | `from adk_fluent import CalendarToolset` |
| `CodeConfig` | `CodeConfig` | `from adk_fluent import CodeConfig` |
| `ComputerUseTool` | `ComputerUseTool` | `from adk_fluent import ComputerUseTool` |
| `ComputerUseToolset` | `ComputerUseToolset` | `from adk_fluent import ComputerUseToolset` |
| `ContextCacheConfig` | `ContextCacheConfig` | `from adk_fluent import ContextCacheConfig` |
| `ContextFilterPlugin` | `ContextFilterPlugin` | `from adk_fluent import ContextFilterPlugin` |
| `DataAgentCredentialsConfig` | `DataAgentCredentialsConfig` | `from adk_fluent import DataAgentCredentialsConfig` |
| `DataAgentToolConfig` | `DataAgentToolConfig` | `from adk_fluent import DataAgentToolConfig` |
| `DataAgentToolset` | `DataAgentToolset` | `from adk_fluent import DataAgentToolset` |
| `DatabaseSessionService` | `DatabaseSessionService` | `from adk_fluent import DatabaseSessionService` |
| `DebugLoggingPlugin` | `DebugLoggingPlugin` | `from adk_fluent import DebugLoggingPlugin` |
| `DiscoveryEngineSearchTool` | `DiscoveryEngineSearchTool` | `from adk_fluent import DiscoveryEngineSearchTool` |
| `DocsToolset` | `DocsToolset` | `from adk_fluent import DocsToolset` |
| `EnterpriseWebSearchTool` | `EnterpriseWebSearchTool` | `from adk_fluent import EnterpriseWebSearchTool` |
| `EventsCompactionConfig` | `EventsCompactionConfig` | `from adk_fluent import EventsCompactionConfig` |
| `ExampleTool` | `ExampleTool` | `from adk_fluent import ExampleTool` |
| `ExampleToolConfig` | `ExampleToolConfig` | `from adk_fluent import ExampleToolConfig` |
| `ParallelAgent` | `FanOut` | `from adk_fluent import FanOut` |
| `FeatureConfig` | `FeatureConfig` | `from adk_fluent import FeatureConfig` |
| `FileArtifactService` | `FileArtifactService` | `from adk_fluent import FileArtifactService` |
| `ForwardingArtifactService` | `ForwardingArtifactService` | `from adk_fluent import ForwardingArtifactService` |
| `FunctionTool` | `FunctionTool` | `from adk_fluent import FunctionTool` |
| `GcsArtifactService` | `GcsArtifactService` | `from adk_fluent import GcsArtifactService` |
| `GetSessionConfig` | `GetSessionConfig` | `from adk_fluent import GetSessionConfig` |
| `GlobalInstructionPlugin` | `GlobalInstructionPlugin` | `from adk_fluent import GlobalInstructionPlugin` |
| `GmailToolset` | `GmailToolset` | `from adk_fluent import GmailToolset` |
| `GoogleApiTool` | `GoogleApiTool` | `from adk_fluent import GoogleApiTool` |
| `GoogleApiToolset` | `GoogleApiToolset` | `from adk_fluent import GoogleApiToolset` |
| `GoogleMapsGroundingTool` | `GoogleMapsGroundingTool` | `from adk_fluent import GoogleMapsGroundingTool` |
| `GoogleSearchAgentTool` | `GoogleSearchAgentTool` | `from adk_fluent import GoogleSearchAgentTool` |
| `GoogleSearchTool` | `GoogleSearchTool` | `from adk_fluent import GoogleSearchTool` |
| `GoogleTool` | `GoogleTool` | `from adk_fluent import GoogleTool` |
| `InMemoryArtifactService` | `InMemoryArtifactService` | `from adk_fluent import InMemoryArtifactService` |
| `InMemoryMemoryService` | `InMemoryMemoryService` | `from adk_fluent import InMemoryMemoryService` |
| `InMemoryRunner` | `InMemoryRunner` | `from adk_fluent import InMemoryRunner` |
| `InMemorySessionService` | `InMemorySessionService` | `from adk_fluent import InMemorySessionService` |
| `InjectionConfig` | `InjectionConfig` | `from adk_fluent import InjectionConfig` |
| `IntegrationConnectorTool` | `IntegrationConnectorTool` | `from adk_fluent import IntegrationConnectorTool` |
| `LlmAgentConfig` | `LlmAgentConfig` | `from adk_fluent import LlmAgentConfig` |
| `LoadArtifactsTool` | `LoadArtifactsTool` | `from adk_fluent import LoadArtifactsTool` |
| `LoadMcpResourceTool` | `LoadMcpResourceTool` | `from adk_fluent import LoadMcpResourceTool` |
| `LoadMemoryTool` | `LoadMemoryTool` | `from adk_fluent import LoadMemoryTool` |
| `LoadSkillResourceTool` | `LoadSkillResourceTool` | `from adk_fluent import LoadSkillResourceTool` |
| `LoadSkillTool` | `LoadSkillTool` | `from adk_fluent import LoadSkillTool` |
| `LoggingPlugin` | `LoggingPlugin` | `from adk_fluent import LoggingPlugin` |
| `LongRunningFunctionTool` | `LongRunningFunctionTool` | `from adk_fluent import LongRunningFunctionTool` |
| `LoopAgent` | `Loop` | `from adk_fluent import Loop` |
| `LoopAgentConfig` | `LoopAgentConfig` | `from adk_fluent import LoopAgentConfig` |
| `MCPTool` | `MCPTool` | `from adk_fluent import MCPTool` |
| `MCPToolset` | `MCPToolset` | `from adk_fluent import MCPToolset` |
| `McpTool` | `McpTool` | `from adk_fluent import McpTool` |
| `McpToolset` | `McpToolset` | `from adk_fluent import McpToolset` |
| `McpToolsetConfig` | `McpToolsetConfig` | `from adk_fluent import McpToolsetConfig` |
| `MultimodalToolResultsPlugin` | `MultimodalToolResultsPlugin` | `from adk_fluent import MultimodalToolResultsPlugin` |
| `OpenAPIToolset` | `OpenAPIToolset` | `from adk_fluent import OpenAPIToolset` |
| `ParallelAgentConfig` | `ParallelAgentConfig` | `from adk_fluent import ParallelAgentConfig` |
| `PerAgentDatabaseSessionService` | `PerAgentDatabaseSessionService` | `from adk_fluent import PerAgentDatabaseSessionService` |
| `SequentialAgent` | `Pipeline` | `from adk_fluent import Pipeline` |
| `PlanReActPlanner` | `PlanReActPlanner` | `from adk_fluent import PlanReActPlanner` |
| `PreloadMemoryTool` | `PreloadMemoryTool` | `from adk_fluent import PreloadMemoryTool` |
| `PubSubCredentialsConfig` | `PubSubCredentialsConfig` | `from adk_fluent import PubSubCredentialsConfig` |
| `PubSubToolConfig` | `PubSubToolConfig` | `from adk_fluent import PubSubToolConfig` |
| `PubSubToolset` | `PubSubToolset` | `from adk_fluent import PubSubToolset` |
| `RecordingsPlugin` | `RecordingsPlugin` | `from adk_fluent import RecordingsPlugin` |
| `ReflectAndRetryToolPlugin` | `ReflectAndRetryToolPlugin` | `from adk_fluent import ReflectAndRetryToolPlugin` |
| `ReplayPlugin` | `ReplayPlugin` | `from adk_fluent import ReplayPlugin` |
| `RestApiTool` | `RestApiTool` | `from adk_fluent import RestApiTool` |
| `ResumabilityConfig` | `ResumabilityConfig` | `from adk_fluent import ResumabilityConfig` |
| `RetryConfig` | `RetryConfig` | `from adk_fluent import RetryConfig` |
| `RunConfig` | `RunConfig` | `from adk_fluent import RunConfig` |
| `Runner` | `Runner` | `from adk_fluent import Runner` |
| `SaveFilesAsArtifactsPlugin` | `SaveFilesAsArtifactsPlugin` | `from adk_fluent import SaveFilesAsArtifactsPlugin` |
| `SequentialAgentConfig` | `SequentialAgentConfig` | `from adk_fluent import SequentialAgentConfig` |
| `SetModelResponseTool` | `SetModelResponseTool` | `from adk_fluent import SetModelResponseTool` |
| `SheetsToolset` | `SheetsToolset` | `from adk_fluent import SheetsToolset` |
| `SimplePromptOptimizerConfig` | `SimplePromptOptimizerConfig` | `from adk_fluent import SimplePromptOptimizerConfig` |
| `SkillToolset` | `SkillToolset` | `from adk_fluent import SkillToolset` |
| `SlidesToolset` | `SlidesToolset` | `from adk_fluent import SlidesToolset` |
| `SpannerCredentialsConfig` | `SpannerCredentialsConfig` | `from adk_fluent import SpannerCredentialsConfig` |
| `SpannerToolset` | `SpannerToolset` | `from adk_fluent import SpannerToolset` |
| `SqliteSessionService` | `SqliteSessionService` | `from adk_fluent import SqliteSessionService` |
| `ToolArgsConfig` | `ToolArgsConfig` | `from adk_fluent import ToolArgsConfig` |
| `ToolConfig` | `ToolConfig` | `from adk_fluent import ToolConfig` |
| `ToolSimulationConfig` | `ToolSimulationConfig` | `from adk_fluent import ToolSimulationConfig` |
| `ToolThreadPoolConfig` | `ToolThreadPoolConfig` | `from adk_fluent import ToolThreadPoolConfig` |
| `ToolboxToolset` | `ToolboxToolset` | `from adk_fluent import ToolboxToolset` |
| `TransferToAgentTool` | `TransferToAgentTool` | `from adk_fluent import TransferToAgentTool` |
| `UnsafeLocalCodeExecutor` | `UnsafeLocalCodeExecutor` | `from adk_fluent import UnsafeLocalCodeExecutor` |
| `UrlContextTool` | `UrlContextTool` | `from adk_fluent import UrlContextTool` |
| `VertexAiCodeExecutor` | `VertexAiCodeExecutor` | `from adk_fluent import VertexAiCodeExecutor` |
| `VertexAiMemoryBankService` | `VertexAiMemoryBankService` | `from adk_fluent import VertexAiMemoryBankService` |
| `VertexAiRagMemoryService` | `VertexAiRagMemoryService` | `from adk_fluent import VertexAiRagMemoryService` |
| `VertexAiSearchTool` | `VertexAiSearchTool` | `from adk_fluent import VertexAiSearchTool` |
| `VertexAiSessionService` | `VertexAiSessionService` | `from adk_fluent import VertexAiSessionService` |
| `YoutubeToolset` | `YoutubeToolset` | `from adk_fluent import YoutubeToolset` |

## Field Mappings

The tables below show fluent method names that differ from the native field names.

### Agent

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `global_instruction` | `.global_instruct()` | alias |
| `include_contents` | `.history()` | alias |
| `instruction` | `.instruct()` | alias |
| `output_key` | `.outputs()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `after_model_callback` | `.after_model()` | callback, additive |
| `after_tool_callback` | `.after_tool()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |
| `before_model_callback` | `.before_model()` | callback, additive |
| `before_tool_callback` | `.before_tool()` | callback, additive |
| `on_model_error_callback` | `.on_model_error()` | callback, additive |
| `on_tool_error_callback` | `.on_tool_error()` | callback, additive |

### BaseAgent

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |

### BaseAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |

### FanOut

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |

### LlmAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `include_contents` | `.history()` | alias |
| `instruction` | `.instruct()` | alias |
| `output_key` | `.outputs()` | alias |

### Loop

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |

### LoopAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |

### ParallelAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |

### Pipeline

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |

### SequentialAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
