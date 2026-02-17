# Migration Guide: Native ADK to adk-fluent

This guide helps you migrate from the native Google ADK API to the
adk-fluent builder pattern. The fluent API wraps every ADK class with a
chainable builder that produces identical runtime objects. You can migrate
incrementally -- fluent builders and native objects interoperate freely.

## Common Patterns: Before and After

### Agent

::::{tab-set}
:::{tab-item} Before (Native)
```python
from google.adk.agents.llm_agent import LlmAgent

agent = LlmAgent(
    name="helper",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    description="A helper agent",
)
```
:::
:::{tab-item} After (Fluent)
```python
from adk_fluent import Agent

agent = (
    Agent("helper")
    .model("gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("A helper agent")
    .build()
)
```
:::
::::

### Pipeline (SequentialAgent)

::::{tab-set}
:::{tab-item} Before (Native)
```python
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.llm_agent import LlmAgent

pipeline = SequentialAgent(
    name="my_pipeline",
    sub_agents=[
        LlmAgent(name="step1", model="gemini-2.5-flash", instruction="Do step 1."),
        LlmAgent(name="step2", model="gemini-2.5-flash", instruction="Do step 2."),
    ],
)
```
:::
:::{tab-item} After (Fluent)
```python
from adk_fluent import Agent, Pipeline

pipeline = (
    Pipeline("my_pipeline")
    .step(Agent("step1").model("gemini-2.5-flash").instruct("Do step 1."))
    .step(Agent("step2").model("gemini-2.5-flash").instruct("Do step 2."))
    .build()
)
```
:::
::::

### FanOut (ParallelAgent)

::::{tab-set}
:::{tab-item} Before (Native)
```python
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.llm_agent import LlmAgent

fanout = ParallelAgent(
    name="parallel_search",
    sub_agents=[
        LlmAgent(name="web", model="gemini-2.5-flash", instruction="Search web."),
        LlmAgent(name="db", model="gemini-2.5-flash", instruction="Search DB."),
    ],
)
```
:::
:::{tab-item} After (Fluent)
```python
from adk_fluent import Agent, FanOut

fanout = (
    FanOut("parallel_search")
    .branch(Agent("web").model("gemini-2.5-flash").instruct("Search web."))
    .branch(Agent("db").model("gemini-2.5-flash").instruct("Search DB."))
    .build()
)
```
:::
::::

## Class Mapping

| Native ADK Class | adk-fluent Builder | Import |
|------------------|-------------------|--------|
| `APIHubToolset` | [APIHubToolset](../api/tool.md#builder-APIHubToolset) | `from adk_fluent import APIHubToolset` |
| `ActiveStreamingTool` | [ActiveStreamingTool](../api/tool.md#builder-ActiveStreamingTool) | `from adk_fluent import ActiveStreamingTool` |
| `LlmAgent` | [Agent](../api/agent.md#builder-Agent) | `from adk_fluent import Agent` |
| `AgentConfig` | [AgentConfig](../api/config.md#builder-AgentConfig) | `from adk_fluent import AgentConfig` |
| `AgentEngineSandboxCodeExecutor` | [AgentEngineSandboxCodeExecutor](../api/executor.md#builder-AgentEngineSandboxCodeExecutor) | `from adk_fluent import AgentEngineSandboxCodeExecutor` |
| `AgentRefConfig` | [AgentRefConfig](../api/config.md#builder-AgentRefConfig) | `from adk_fluent import AgentRefConfig` |
| `AgentSimulatorConfig` | [AgentSimulatorConfig](../api/config.md#builder-AgentSimulatorConfig) | `from adk_fluent import AgentSimulatorConfig` |
| `AgentSimulatorPlugin` | [AgentSimulatorPlugin](../api/plugin.md#builder-AgentSimulatorPlugin) | `from adk_fluent import AgentSimulatorPlugin` |
| `AgentTool` | [AgentTool](../api/tool.md#builder-AgentTool) | `from adk_fluent import AgentTool` |
| `AgentToolConfig` | [AgentToolConfig](../api/config.md#builder-AgentToolConfig) | `from adk_fluent import AgentToolConfig` |
| `App` | [App](../api/runtime.md#builder-App) | `from adk_fluent import App` |
| `ApplicationIntegrationToolset` | [ApplicationIntegrationToolset](../api/tool.md#builder-ApplicationIntegrationToolset) | `from adk_fluent import ApplicationIntegrationToolset` |
| `ArgumentConfig` | [ArgumentConfig](../api/config.md#builder-ArgumentConfig) | `from adk_fluent import ArgumentConfig` |
| `AudioCacheConfig` | [AudioCacheConfig](../api/config.md#builder-AudioCacheConfig) | `from adk_fluent import AudioCacheConfig` |
| `BaseAgent` | [BaseAgent](../api/agent.md#builder-BaseAgent) | `from adk_fluent import BaseAgent` |
| `BaseAgentConfig` | [BaseAgentConfig](../api/config.md#builder-BaseAgentConfig) | `from adk_fluent import BaseAgentConfig` |
| `BaseArtifactService` | [BaseArtifactService](../api/service.md#builder-BaseArtifactService) | `from adk_fluent import BaseArtifactService` |
| `BaseAuthenticatedTool` | [BaseAuthenticatedTool](../api/tool.md#builder-BaseAuthenticatedTool) | `from adk_fluent import BaseAuthenticatedTool` |
| `BaseCodeExecutor` | [BaseCodeExecutor](../api/executor.md#builder-BaseCodeExecutor) | `from adk_fluent import BaseCodeExecutor` |
| `BaseGoogleCredentialsConfig` | [BaseGoogleCredentialsConfig](../api/config.md#builder-BaseGoogleCredentialsConfig) | `from adk_fluent import BaseGoogleCredentialsConfig` |
| `BaseMemoryService` | [BaseMemoryService](../api/service.md#builder-BaseMemoryService) | `from adk_fluent import BaseMemoryService` |
| `BasePlanner` | [BasePlanner](../api/planner.md#builder-BasePlanner) | `from adk_fluent import BasePlanner` |
| `BasePlugin` | [BasePlugin](../api/plugin.md#builder-BasePlugin) | `from adk_fluent import BasePlugin` |
| `BaseRetrievalTool` | [BaseRetrievalTool](../api/tool.md#builder-BaseRetrievalTool) | `from adk_fluent import BaseRetrievalTool` |
| `BaseSessionService` | [BaseSessionService](../api/service.md#builder-BaseSessionService) | `from adk_fluent import BaseSessionService` |
| `BaseTool` | [BaseTool](../api/tool.md#builder-BaseTool) | `from adk_fluent import BaseTool` |
| `BaseToolConfig` | [BaseToolConfig](../api/config.md#builder-BaseToolConfig) | `from adk_fluent import BaseToolConfig` |
| `BaseToolset` | [BaseToolset](../api/tool.md#builder-BaseToolset) | `from adk_fluent import BaseToolset` |
| `BigQueryAgentAnalyticsPlugin` | [BigQueryAgentAnalyticsPlugin](../api/plugin.md#builder-BigQueryAgentAnalyticsPlugin) | `from adk_fluent import BigQueryAgentAnalyticsPlugin` |
| `BigQueryCredentialsConfig` | [BigQueryCredentialsConfig](../api/config.md#builder-BigQueryCredentialsConfig) | `from adk_fluent import BigQueryCredentialsConfig` |
| `BigQueryLoggerConfig` | [BigQueryLoggerConfig](../api/config.md#builder-BigQueryLoggerConfig) | `from adk_fluent import BigQueryLoggerConfig` |
| `BigQueryToolConfig` | [BigQueryToolConfig](../api/config.md#builder-BigQueryToolConfig) | `from adk_fluent import BigQueryToolConfig` |
| `BigQueryToolset` | [BigQueryToolset](../api/tool.md#builder-BigQueryToolset) | `from adk_fluent import BigQueryToolset` |
| `BigtableCredentialsConfig` | [BigtableCredentialsConfig](../api/config.md#builder-BigtableCredentialsConfig) | `from adk_fluent import BigtableCredentialsConfig` |
| `BigtableToolset` | [BigtableToolset](../api/tool.md#builder-BigtableToolset) | `from adk_fluent import BigtableToolset` |
| `BuiltInCodeExecutor` | [BuiltInCodeExecutor](../api/executor.md#builder-BuiltInCodeExecutor) | `from adk_fluent import BuiltInCodeExecutor` |
| `BuiltInPlanner` | [BuiltInPlanner](../api/planner.md#builder-BuiltInPlanner) | `from adk_fluent import BuiltInPlanner` |
| `CalendarToolset` | [CalendarToolset](../api/tool.md#builder-CalendarToolset) | `from adk_fluent import CalendarToolset` |
| `CodeConfig` | [CodeConfig](../api/config.md#builder-CodeConfig) | `from adk_fluent import CodeConfig` |
| `ComputerUseTool` | [ComputerUseTool](../api/tool.md#builder-ComputerUseTool) | `from adk_fluent import ComputerUseTool` |
| `ComputerUseToolset` | [ComputerUseToolset](../api/tool.md#builder-ComputerUseToolset) | `from adk_fluent import ComputerUseToolset` |
| `ContextCacheConfig` | [ContextCacheConfig](../api/config.md#builder-ContextCacheConfig) | `from adk_fluent import ContextCacheConfig` |
| `ContextFilterPlugin` | [ContextFilterPlugin](../api/plugin.md#builder-ContextFilterPlugin) | `from adk_fluent import ContextFilterPlugin` |
| `DataAgentCredentialsConfig` | [DataAgentCredentialsConfig](../api/config.md#builder-DataAgentCredentialsConfig) | `from adk_fluent import DataAgentCredentialsConfig` |
| `DataAgentToolConfig` | [DataAgentToolConfig](../api/config.md#builder-DataAgentToolConfig) | `from adk_fluent import DataAgentToolConfig` |
| `DataAgentToolset` | [DataAgentToolset](../api/tool.md#builder-DataAgentToolset) | `from adk_fluent import DataAgentToolset` |
| `DatabaseSessionService` | [DatabaseSessionService](../api/service.md#builder-DatabaseSessionService) | `from adk_fluent import DatabaseSessionService` |
| `DebugLoggingPlugin` | [DebugLoggingPlugin](../api/plugin.md#builder-DebugLoggingPlugin) | `from adk_fluent import DebugLoggingPlugin` |
| `DiscoveryEngineSearchTool` | [DiscoveryEngineSearchTool](../api/tool.md#builder-DiscoveryEngineSearchTool) | `from adk_fluent import DiscoveryEngineSearchTool` |
| `DocsToolset` | [DocsToolset](../api/tool.md#builder-DocsToolset) | `from adk_fluent import DocsToolset` |
| `EnterpriseWebSearchTool` | [EnterpriseWebSearchTool](../api/tool.md#builder-EnterpriseWebSearchTool) | `from adk_fluent import EnterpriseWebSearchTool` |
| `EventsCompactionConfig` | [EventsCompactionConfig](../api/config.md#builder-EventsCompactionConfig) | `from adk_fluent import EventsCompactionConfig` |
| `ExampleTool` | [ExampleTool](../api/tool.md#builder-ExampleTool) | `from adk_fluent import ExampleTool` |
| `ExampleToolConfig` | [ExampleToolConfig](../api/config.md#builder-ExampleToolConfig) | `from adk_fluent import ExampleToolConfig` |
| `ParallelAgent` | [FanOut](../api/workflow.md#builder-FanOut) | `from adk_fluent import FanOut` |
| `FeatureConfig` | [FeatureConfig](../api/config.md#builder-FeatureConfig) | `from adk_fluent import FeatureConfig` |
| `FileArtifactService` | [FileArtifactService](../api/service.md#builder-FileArtifactService) | `from adk_fluent import FileArtifactService` |
| `ForwardingArtifactService` | [ForwardingArtifactService](../api/service.md#builder-ForwardingArtifactService) | `from adk_fluent import ForwardingArtifactService` |
| `FunctionTool` | [FunctionTool](../api/tool.md#builder-FunctionTool) | `from adk_fluent import FunctionTool` |
| `GcsArtifactService` | [GcsArtifactService](../api/service.md#builder-GcsArtifactService) | `from adk_fluent import GcsArtifactService` |
| `GetSessionConfig` | [GetSessionConfig](../api/config.md#builder-GetSessionConfig) | `from adk_fluent import GetSessionConfig` |
| `GlobalInstructionPlugin` | [GlobalInstructionPlugin](../api/plugin.md#builder-GlobalInstructionPlugin) | `from adk_fluent import GlobalInstructionPlugin` |
| `GmailToolset` | [GmailToolset](../api/tool.md#builder-GmailToolset) | `from adk_fluent import GmailToolset` |
| `GoogleApiTool` | [GoogleApiTool](../api/tool.md#builder-GoogleApiTool) | `from adk_fluent import GoogleApiTool` |
| `GoogleApiToolset` | [GoogleApiToolset](../api/tool.md#builder-GoogleApiToolset) | `from adk_fluent import GoogleApiToolset` |
| `GoogleMapsGroundingTool` | [GoogleMapsGroundingTool](../api/tool.md#builder-GoogleMapsGroundingTool) | `from adk_fluent import GoogleMapsGroundingTool` |
| `GoogleSearchAgentTool` | [GoogleSearchAgentTool](../api/tool.md#builder-GoogleSearchAgentTool) | `from adk_fluent import GoogleSearchAgentTool` |
| `GoogleSearchTool` | [GoogleSearchTool](../api/tool.md#builder-GoogleSearchTool) | `from adk_fluent import GoogleSearchTool` |
| `GoogleTool` | [GoogleTool](../api/tool.md#builder-GoogleTool) | `from adk_fluent import GoogleTool` |
| `InMemoryArtifactService` | [InMemoryArtifactService](../api/service.md#builder-InMemoryArtifactService) | `from adk_fluent import InMemoryArtifactService` |
| `InMemoryMemoryService` | [InMemoryMemoryService](../api/service.md#builder-InMemoryMemoryService) | `from adk_fluent import InMemoryMemoryService` |
| `InMemoryRunner` | [InMemoryRunner](../api/runtime.md#builder-InMemoryRunner) | `from adk_fluent import InMemoryRunner` |
| `InMemorySessionService` | [InMemorySessionService](../api/service.md#builder-InMemorySessionService) | `from adk_fluent import InMemorySessionService` |
| `InjectionConfig` | [InjectionConfig](../api/config.md#builder-InjectionConfig) | `from adk_fluent import InjectionConfig` |
| `IntegrationConnectorTool` | [IntegrationConnectorTool](../api/tool.md#builder-IntegrationConnectorTool) | `from adk_fluent import IntegrationConnectorTool` |
| `LlmAgentConfig` | [LlmAgentConfig](../api/config.md#builder-LlmAgentConfig) | `from adk_fluent import LlmAgentConfig` |
| `LoadArtifactsTool` | [LoadArtifactsTool](../api/tool.md#builder-LoadArtifactsTool) | `from adk_fluent import LoadArtifactsTool` |
| `LoadMcpResourceTool` | [LoadMcpResourceTool](../api/tool.md#builder-LoadMcpResourceTool) | `from adk_fluent import LoadMcpResourceTool` |
| `LoadMemoryTool` | [LoadMemoryTool](../api/tool.md#builder-LoadMemoryTool) | `from adk_fluent import LoadMemoryTool` |
| `LoadSkillResourceTool` | [LoadSkillResourceTool](../api/tool.md#builder-LoadSkillResourceTool) | `from adk_fluent import LoadSkillResourceTool` |
| `LoadSkillTool` | [LoadSkillTool](../api/tool.md#builder-LoadSkillTool) | `from adk_fluent import LoadSkillTool` |
| `LoggingPlugin` | [LoggingPlugin](../api/plugin.md#builder-LoggingPlugin) | `from adk_fluent import LoggingPlugin` |
| `LongRunningFunctionTool` | [LongRunningFunctionTool](../api/tool.md#builder-LongRunningFunctionTool) | `from adk_fluent import LongRunningFunctionTool` |
| `LoopAgent` | [Loop](../api/workflow.md#builder-Loop) | `from adk_fluent import Loop` |
| `LoopAgentConfig` | [LoopAgentConfig](../api/config.md#builder-LoopAgentConfig) | `from adk_fluent import LoopAgentConfig` |
| `MCPTool` | [MCPTool](../api/tool.md#builder-MCPTool) | `from adk_fluent import MCPTool` |
| `MCPToolset` | [MCPToolset](../api/tool.md#builder-MCPToolset) | `from adk_fluent import MCPToolset` |
| `McpTool` | [McpTool](../api/tool.md#builder-McpTool) | `from adk_fluent import McpTool` |
| `McpToolset` | [McpToolset](../api/tool.md#builder-McpToolset) | `from adk_fluent import McpToolset` |
| `McpToolsetConfig` | [McpToolsetConfig](../api/config.md#builder-McpToolsetConfig) | `from adk_fluent import McpToolsetConfig` |
| `MultimodalToolResultsPlugin` | [MultimodalToolResultsPlugin](../api/plugin.md#builder-MultimodalToolResultsPlugin) | `from adk_fluent import MultimodalToolResultsPlugin` |
| `OpenAPIToolset` | [OpenAPIToolset](../api/tool.md#builder-OpenAPIToolset) | `from adk_fluent import OpenAPIToolset` |
| `ParallelAgentConfig` | [ParallelAgentConfig](../api/config.md#builder-ParallelAgentConfig) | `from adk_fluent import ParallelAgentConfig` |
| `PerAgentDatabaseSessionService` | [PerAgentDatabaseSessionService](../api/service.md#builder-PerAgentDatabaseSessionService) | `from adk_fluent import PerAgentDatabaseSessionService` |
| `SequentialAgent` | [Pipeline](../api/workflow.md#builder-Pipeline) | `from adk_fluent import Pipeline` |
| `PlanReActPlanner` | [PlanReActPlanner](../api/planner.md#builder-PlanReActPlanner) | `from adk_fluent import PlanReActPlanner` |
| `PreloadMemoryTool` | [PreloadMemoryTool](../api/tool.md#builder-PreloadMemoryTool) | `from adk_fluent import PreloadMemoryTool` |
| `PubSubCredentialsConfig` | [PubSubCredentialsConfig](../api/config.md#builder-PubSubCredentialsConfig) | `from adk_fluent import PubSubCredentialsConfig` |
| `PubSubToolConfig` | [PubSubToolConfig](../api/config.md#builder-PubSubToolConfig) | `from adk_fluent import PubSubToolConfig` |
| `PubSubToolset` | [PubSubToolset](../api/tool.md#builder-PubSubToolset) | `from adk_fluent import PubSubToolset` |
| `RecordingsPlugin` | [RecordingsPlugin](../api/plugin.md#builder-RecordingsPlugin) | `from adk_fluent import RecordingsPlugin` |
| `ReflectAndRetryToolPlugin` | [ReflectAndRetryToolPlugin](../api/plugin.md#builder-ReflectAndRetryToolPlugin) | `from adk_fluent import ReflectAndRetryToolPlugin` |
| `ReplayPlugin` | [ReplayPlugin](../api/plugin.md#builder-ReplayPlugin) | `from adk_fluent import ReplayPlugin` |
| `RestApiTool` | [RestApiTool](../api/tool.md#builder-RestApiTool) | `from adk_fluent import RestApiTool` |
| `ResumabilityConfig` | [ResumabilityConfig](../api/config.md#builder-ResumabilityConfig) | `from adk_fluent import ResumabilityConfig` |
| `RetryConfig` | [RetryConfig](../api/config.md#builder-RetryConfig) | `from adk_fluent import RetryConfig` |
| `RunConfig` | [RunConfig](../api/config.md#builder-RunConfig) | `from adk_fluent import RunConfig` |
| `Runner` | [Runner](../api/runtime.md#builder-Runner) | `from adk_fluent import Runner` |
| `SaveFilesAsArtifactsPlugin` | [SaveFilesAsArtifactsPlugin](../api/plugin.md#builder-SaveFilesAsArtifactsPlugin) | `from adk_fluent import SaveFilesAsArtifactsPlugin` |
| `SequentialAgentConfig` | [SequentialAgentConfig](../api/config.md#builder-SequentialAgentConfig) | `from adk_fluent import SequentialAgentConfig` |
| `SetModelResponseTool` | [SetModelResponseTool](../api/tool.md#builder-SetModelResponseTool) | `from adk_fluent import SetModelResponseTool` |
| `SheetsToolset` | [SheetsToolset](../api/tool.md#builder-SheetsToolset) | `from adk_fluent import SheetsToolset` |
| `SimplePromptOptimizerConfig` | [SimplePromptOptimizerConfig](../api/config.md#builder-SimplePromptOptimizerConfig) | `from adk_fluent import SimplePromptOptimizerConfig` |
| `SkillToolset` | [SkillToolset](../api/tool.md#builder-SkillToolset) | `from adk_fluent import SkillToolset` |
| `SlidesToolset` | [SlidesToolset](../api/tool.md#builder-SlidesToolset) | `from adk_fluent import SlidesToolset` |
| `SpannerCredentialsConfig` | [SpannerCredentialsConfig](../api/config.md#builder-SpannerCredentialsConfig) | `from adk_fluent import SpannerCredentialsConfig` |
| `SpannerToolset` | [SpannerToolset](../api/tool.md#builder-SpannerToolset) | `from adk_fluent import SpannerToolset` |
| `SqliteSessionService` | [SqliteSessionService](../api/service.md#builder-SqliteSessionService) | `from adk_fluent import SqliteSessionService` |
| `ToolArgsConfig` | [ToolArgsConfig](../api/config.md#builder-ToolArgsConfig) | `from adk_fluent import ToolArgsConfig` |
| `ToolConfig` | [ToolConfig](../api/config.md#builder-ToolConfig) | `from adk_fluent import ToolConfig` |
| `ToolSimulationConfig` | [ToolSimulationConfig](../api/config.md#builder-ToolSimulationConfig) | `from adk_fluent import ToolSimulationConfig` |
| `ToolThreadPoolConfig` | [ToolThreadPoolConfig](../api/config.md#builder-ToolThreadPoolConfig) | `from adk_fluent import ToolThreadPoolConfig` |
| `ToolboxToolset` | [ToolboxToolset](../api/tool.md#builder-ToolboxToolset) | `from adk_fluent import ToolboxToolset` |
| `TransferToAgentTool` | [TransferToAgentTool](../api/tool.md#builder-TransferToAgentTool) | `from adk_fluent import TransferToAgentTool` |
| `UnsafeLocalCodeExecutor` | [UnsafeLocalCodeExecutor](../api/executor.md#builder-UnsafeLocalCodeExecutor) | `from adk_fluent import UnsafeLocalCodeExecutor` |
| `UrlContextTool` | [UrlContextTool](../api/tool.md#builder-UrlContextTool) | `from adk_fluent import UrlContextTool` |
| `VertexAiCodeExecutor` | [VertexAiCodeExecutor](../api/executor.md#builder-VertexAiCodeExecutor) | `from adk_fluent import VertexAiCodeExecutor` |
| `VertexAiMemoryBankService` | [VertexAiMemoryBankService](../api/service.md#builder-VertexAiMemoryBankService) | `from adk_fluent import VertexAiMemoryBankService` |
| `VertexAiRagMemoryService` | [VertexAiRagMemoryService](../api/service.md#builder-VertexAiRagMemoryService) | `from adk_fluent import VertexAiRagMemoryService` |
| `VertexAiSearchTool` | [VertexAiSearchTool](../api/tool.md#builder-VertexAiSearchTool) | `from adk_fluent import VertexAiSearchTool` |
| `VertexAiSessionService` | [VertexAiSessionService](../api/service.md#builder-VertexAiSessionService) | `from adk_fluent import VertexAiSessionService` |
| `YoutubeToolset` | [YoutubeToolset](../api/tool.md#builder-YoutubeToolset) | `from adk_fluent import YoutubeToolset` |

## Field Mappings

The tables below show fluent method names that differ from the native field names.

(migration-agent)=
### Agent

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `global_instruction` | `.global_instruct()` | alias |
| `include_contents` | `.history()` | alias |
| `instruction` | `.instruct()` | alias |
| `output_key` | `.outputs()` | alias |
| `static_instruction` | `.static()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `after_model_callback` | `.after_model()` | callback, additive |
| `after_tool_callback` | `.after_tool()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |
| `before_model_callback` | `.before_model()` | callback, additive |
| `before_tool_callback` | `.before_tool()` | callback, additive |
| `on_model_error_callback` | `.on_model_error()` | callback, additive |
| `on_tool_error_callback` | `.on_tool_error()` | callback, additive |

(migration-baseagent)=
### BaseAgent

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |

(migration-baseagentconfig)=
### BaseAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |

(migration-fanout)=
### FanOut

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |

(migration-llmagentconfig)=
### LlmAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `include_contents` | `.history()` | alias |
| `instruction` | `.instruct()` | alias |
| `output_key` | `.outputs()` | alias |
| `static_instruction` | `.static()` | alias |

(migration-loop)=
### Loop

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |

(migration-loopagentconfig)=
### LoopAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |

(migration-parallelagentconfig)=
### ParallelAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |

(migration-pipeline)=
### Pipeline

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
| `after_agent_callback` | `.after_agent()` | callback, additive |
| `before_agent_callback` | `.before_agent()` | callback, additive |

(migration-sequentialagentconfig)=
### SequentialAgentConfig

| Native Field | Fluent Method | Notes |
|-------------|---------------|-------|
| `description` | `.describe()` | alias |
