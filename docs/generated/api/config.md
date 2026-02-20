# Module: `config`

## Builders in this module

| Builder                                                            | Description                                                                |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| [AgentConfig](builder-AgentConfig)                                 | The config for the YAML schema to create an agent.                         |
| [BaseAgentConfig](builder-BaseAgentConfig)                         | The config for the YAML schema of a BaseAgent.                             |
| [AgentRefConfig](builder-AgentRefConfig)                           | The config for the reference to another agent.                             |
| [ArgumentConfig](builder-ArgumentConfig)                           | An argument passed to a function or a class's constructor.                 |
| [CodeConfig](builder-CodeConfig)                                   | Code reference config for a variable, a function, or a class.              |
| [ContextCacheConfig](builder-ContextCacheConfig)                   | Configuration for context caching across all agents in an app.             |
| [LlmAgentConfig](builder-LlmAgentConfig)                           | The config for the YAML schema of a LlmAgent.                              |
| [LoopAgentConfig](builder-LoopAgentConfig)                         | The config for the YAML schema of a LoopAgent.                             |
| [ParallelAgentConfig](builder-ParallelAgentConfig)                 | The config for the YAML schema of a ParallelAgent.                         |
| [RunConfig](builder-RunConfig)                                     | Configs for runtime behavior of agents.                                    |
| [ToolThreadPoolConfig](builder-ToolThreadPoolConfig)               | Configuration for the tool thread pool executor.                           |
| [SequentialAgentConfig](builder-SequentialAgentConfig)             | The config for the YAML schema of a SequentialAgent.                       |
| [EventsCompactionConfig](builder-EventsCompactionConfig)           | The config of event compaction for an application.                         |
| [ResumabilityConfig](builder-ResumabilityConfig)                   | The config of the resumability for an application.                         |
| [FeatureConfig](builder-FeatureConfig)                             | Feature configuration.                                                     |
| [AudioCacheConfig](builder-AudioCacheConfig)                       | Configuration for audio caching behavior.                                  |
| [SimplePromptOptimizerConfig](builder-SimplePromptOptimizerConfig) | Configuration for the IterativePromptOptimizer.                            |
| [BigQueryLoggerConfig](builder-BigQueryLoggerConfig)               | Configuration for the BigQueryAgentAnalyticsPlugin.                        |
| [RetryConfig](builder-RetryConfig)                                 | Configuration for retrying failed BigQuery write operations.               |
| [GetSessionConfig](builder-GetSessionConfig)                       | The configuration of getting a session.                                    |
| [BaseGoogleCredentialsConfig](builder-BaseGoogleCredentialsConfig) | Base Google Credentials Configuration for Google API tools (Experimental). |
| [AgentSimulatorConfig](builder-AgentSimulatorConfig)               | Configuration for AgentSimulator.                                          |
| [InjectionConfig](builder-InjectionConfig)                         | Injection configuration for a tool.                                        |
| [ToolSimulationConfig](builder-ToolSimulationConfig)               | Simulation configuration for a single tool.                                |
| [AgentToolConfig](builder-AgentToolConfig)                         | The config for the AgentTool.                                              |
| [BigQueryCredentialsConfig](builder-BigQueryCredentialsConfig)     | BigQuery Credentials Configuration for Google API tools (Experimental).    |
| [BigQueryToolConfig](builder-BigQueryToolConfig)                   | Configuration for BigQuery tools.                                          |
| [BigtableCredentialsConfig](builder-BigtableCredentialsConfig)     | Bigtable Credentials Configuration for Google API tools (Experimental).    |
| [DataAgentToolConfig](builder-DataAgentToolConfig)                 | Configuration for Data Agent tools.                                        |
| [DataAgentCredentialsConfig](builder-DataAgentCredentialsConfig)   | Data Agent Credentials Configuration for Google API tools.                 |
| [ExampleToolConfig](builder-ExampleToolConfig)                     | Fluent builder for ExampleToolConfig.                                      |
| [McpToolsetConfig](builder-McpToolsetConfig)                       | The config for McpToolset.                                                 |
| [PubSubToolConfig](builder-PubSubToolConfig)                       | Configuration for Pub/Sub tools.                                           |
| [PubSubCredentialsConfig](builder-PubSubCredentialsConfig)         | Pub/Sub Credentials Configuration for Google API tools (Experimental).     |
| [SpannerCredentialsConfig](builder-SpannerCredentialsConfig)       | Spanner Credentials Configuration for Google API tools (Experimental).     |
| [BaseToolConfig](builder-BaseToolConfig)                           | The base class for all tool configs.                                       |
| [ToolArgsConfig](builder-ToolArgsConfig)                           | Config to host free key-value pairs for the args in ToolConfig.            |
| [ToolConfig](builder-ToolConfig)                                   | The configuration for a tool.                                              |

(builder-AgentConfig)=

## AgentConfig

> Fluent builder for `google.adk.agents.agent_config.AgentConfig`

The config for the YAML schema to create an agent.

**Quick start:**

```python
from adk_fluent import AgentConfig

result = (
    AgentConfig("root_value")
    .build()
)
```

### Constructor

```python
AgentConfig(root: RootModelRootType)
```

| Argument | Type                |
| -------- | ------------------- |
| `root`   | `RootModelRootType` |

### Control Flow & Execution

#### `.build() -> AgentConfig`

Resolve into a native ADK AgentConfig.

______________________________________________________________________

(builder-BaseAgentConfig)=

## BaseAgentConfig

> Fluent builder for `google.adk.agents.base_agent_config.BaseAgentConfig`

The config for the YAML schema of a BaseAgent.

**Quick start:**

```python
from adk_fluent import BaseAgentConfig

result = (
    BaseAgentConfig("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
BaseAgentConfig(name: str)
```

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.sub_agent(value: AgentRefConfig) -> Self`

Append to `sub_agents` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self`

Append to `after_agent_callbacks` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self`

Append to `before_agent_callbacks` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> BaseAgentConfig`

Resolve into a native ADK BaseAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                            | Type                                    |
| -------------------------------- | --------------------------------------- |
| `.agent_class(value)`            | `Union[Literal[BaseAgent], str]`        |
| `.sub_agents(value)`             | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]`     |
| `.after_agent_callbacks(value)`  | `Union[list[CodeConfig], NoneType]`     |

______________________________________________________________________

(builder-AgentRefConfig)=

## AgentRefConfig

> Fluent builder for `google.adk.agents.common_configs.AgentRefConfig`

The config for the reference to another agent.

**Quick start:**

```python
from adk_fluent import AgentRefConfig

result = (
    AgentRefConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> AgentRefConfig`

Resolve into a native ADK AgentRefConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                 | Type                   |
| --------------------- | ---------------------- |
| `.config_path(value)` | `Union[str, NoneType]` |
| `.code(value)`        | `Union[str, NoneType]` |

______________________________________________________________________

(builder-ArgumentConfig)=

## ArgumentConfig

> Fluent builder for `google.adk.agents.common_configs.ArgumentConfig`

An argument passed to a function or a class's constructor.

**Quick start:**

```python
from adk_fluent import ArgumentConfig

result = (
    ArgumentConfig("value_value")
    .build()
)
```

### Constructor

```python
ArgumentConfig(value: Any)
```

| Argument | Type  |
| -------- | ----- |
| `value`  | `Any` |

### Control Flow & Execution

#### `.build() -> ArgumentConfig`

Resolve into a native ADK ArgumentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field          | Type                   |
| -------------- | ---------------------- |
| `.name(value)` | `Union[str, NoneType]` |

______________________________________________________________________

(builder-CodeConfig)=

## CodeConfig

> Fluent builder for `google.adk.agents.common_configs.CodeConfig`

Code reference config for a variable, a function, or a class.

**Quick start:**

```python
from adk_fluent import CodeConfig

result = (
    CodeConfig("name_value")
    .arg(...)
    .build()
)
```

### Constructor

```python
CodeConfig(name: str)
```

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Configuration

#### `.arg(value: ArgumentConfig) -> Self`

Append to `args` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> CodeConfig`

Resolve into a native ADK CodeConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field          | Type                                    |
| -------------- | --------------------------------------- |
| `.args(value)` | `Union[list[ArgumentConfig], NoneType]` |

______________________________________________________________________

(builder-ContextCacheConfig)=

## ContextCacheConfig

> Fluent builder for `google.adk.agents.context_cache_config.ContextCacheConfig`

Configuration for context caching across all agents in an app.

**Quick start:**

```python
from adk_fluent import ContextCacheConfig

result = (
    ContextCacheConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> ContextCacheConfig`

Resolve into a native ADK ContextCacheConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                     | Type  |
| ------------------------- | ----- |
| `.cache_intervals(value)` | `int` |
| `.ttl_seconds(value)`     | `int` |
| `.min_tokens(value)`      | `int` |

______________________________________________________________________

(builder-LlmAgentConfig)=

## LlmAgentConfig

> Fluent builder for `google.adk.agents.llm_agent_config.LlmAgentConfig`

The config for the YAML schema of a LlmAgent.

**Quick start:**

```python
from adk_fluent import LlmAgentConfig

result = (
    LlmAgentConfig("name_value", "instruction_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
LlmAgentConfig(name: str, instruction: str)
```

| Argument      | Type  |
| ------------- | ----- |
| `name`        | `str` |
| `instruction` | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.history(value: Literal[default, none]) -> Self`

- **Maps to:** `include_contents`
- Optional. LlmAgent.include_contents.

#### `.instruct(value: str) -> Self`

- **Maps to:** `instruction`
- Required. LlmAgent.instruction. Dynamic instructions with placeholder support. Behavior: if static_instruction is None, goes to system_instruction; if static_instruction is set, goes to user content after static content.

#### `.outputs(value: Union[str, NoneType]) -> Self`

- **Maps to:** `output_key`
- Session state key where the agent's response text is stored. Downstream agents and state transforms can read this key. Alias: `.outputs(key)`.

#### `.static(value: Union[Content, str, File, Part, list[Union[str, File, Part]], NoneType]) -> Self`

- **Maps to:** `static_instruction`
- Optional. LlmAgent.static_instruction. Static content sent literally at position 0 without placeholder processing. When set, changes instruction behavior to go to user content instead of system_instruction. Supports context caching. Accepts types.ContentUnion (str, types.Content, types.Part, PIL.Image.Image, types.File, or list[PartUnion]).

#### `.sub_agent(value: AgentRefConfig) -> Self`

Append to `sub_agents` (lazy — built at .build() time).

#### `.tool(value: ToolConfig) -> Self`

Append to `tools` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self`

Append to `after_agent_callbacks` (lazy — built at .build() time).

#### `.after_model_callback(value: CodeConfig) -> Self`

Append to `after_model_callbacks` (lazy — built at .build() time).

#### `.after_tool_callback(value: CodeConfig) -> Self`

Append to `after_tool_callbacks` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self`

Append to `before_agent_callbacks` (lazy — built at .build() time).

#### `.before_model_callback(value: CodeConfig) -> Self`

Append to `before_model_callbacks` (lazy — built at .build() time).

#### `.before_tool_callback(value: CodeConfig) -> Self`

Append to `before_tool_callbacks` (lazy — built at .build() time).

#### `.include_history(value: Literal[default, none]) -> Self`

- **Maps to:** `include_contents`
- Optional. LlmAgent.include_contents.

#### `.static_instruct(value: Union[Content, str, File, Part, list[Union[str, File, Part]], NoneType]) -> Self`

- **Maps to:** `static_instruction`
- Optional. LlmAgent.static_instruction. Static content sent literally at position 0 without placeholder processing. When set, changes instruction behavior to go to user content instead of system_instruction. Supports context caching. Accepts types.ContentUnion (str, types.Content, types.Part, PIL.Image.Image, types.File, or list[PartUnion]).

### Control Flow & Execution

#### `.build() -> LlmAgentConfig`

Resolve into a native ADK LlmAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                 | Type                                     |
| ------------------------------------- | ---------------------------------------- |
| `.agent_class(value)`                 | `str`                                    |
| `.sub_agents(value)`                  | `Union[list[AgentRefConfig], NoneType]`  |
| `.before_agent_callbacks(value)`      | `Union[list[CodeConfig], NoneType]`      |
| `.after_agent_callbacks(value)`       | `Union[list[CodeConfig], NoneType]`      |
| `.model(value)`                       | `Union[str, NoneType]`                   |
| `.model_code(value)`                  | `Union[CodeConfig, NoneType]`            |
| `.disallow_transfer_to_parent(value)` | `Union[bool, NoneType]`                  |
| `.disallow_transfer_to_peers(value)`  | `Union[bool, NoneType]`                  |
| `.input_schema(value)`                | `Union[CodeConfig, NoneType]`            |
| `.output_schema(value)`               | `Union[CodeConfig, NoneType]`            |
| `.tools(value)`                       | `Union[list[ToolConfig], NoneType]`      |
| `.before_model_callbacks(value)`      | `Union[list[CodeConfig], NoneType]`      |
| `.after_model_callbacks(value)`       | `Union[list[CodeConfig], NoneType]`      |
| `.before_tool_callbacks(value)`       | `Union[list[CodeConfig], NoneType]`      |
| `.after_tool_callbacks(value)`        | `Union[list[CodeConfig], NoneType]`      |
| `.generate_content_config(value)`     | `Union[GenerateContentConfig, NoneType]` |

______________________________________________________________________

(builder-LoopAgentConfig)=

## LoopAgentConfig

> Fluent builder for `google.adk.agents.loop_agent_config.LoopAgentConfig`

The config for the YAML schema of a LoopAgent.

**Quick start:**

```python
from adk_fluent import LoopAgentConfig

result = (
    LoopAgentConfig("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
LoopAgentConfig(name: str)
```

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.sub_agent(value: AgentRefConfig) -> Self`

Append to `sub_agents` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self`

Append to `after_agent_callbacks` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self`

Append to `before_agent_callbacks` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> LoopAgentConfig`

Resolve into a native ADK LoopAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                            | Type                                    |
| -------------------------------- | --------------------------------------- |
| `.agent_class(value)`            | `str`                                   |
| `.sub_agents(value)`             | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]`     |
| `.after_agent_callbacks(value)`  | `Union[list[CodeConfig], NoneType]`     |
| `.max_iterations(value)`         | `Union[int, NoneType]`                  |

______________________________________________________________________

(builder-ParallelAgentConfig)=

## ParallelAgentConfig

> Fluent builder for `google.adk.agents.parallel_agent_config.ParallelAgentConfig`

The config for the YAML schema of a ParallelAgent.

**Quick start:**

```python
from adk_fluent import ParallelAgentConfig

result = (
    ParallelAgentConfig("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
ParallelAgentConfig(name: str)
```

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.sub_agent(value: AgentRefConfig) -> Self`

Append to `sub_agents` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self`

Append to `after_agent_callbacks` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self`

Append to `before_agent_callbacks` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> ParallelAgentConfig`

Resolve into a native ADK ParallelAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                            | Type                                    |
| -------------------------------- | --------------------------------------- |
| `.agent_class(value)`            | `str`                                   |
| `.sub_agents(value)`             | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]`     |
| `.after_agent_callbacks(value)`  | `Union[list[CodeConfig], NoneType]`     |

______________________________________________________________________

(builder-RunConfig)=

## RunConfig

> Fluent builder for `google.adk.agents.run_config.RunConfig`

Configs for runtime behavior of agents.

**Quick start:**

```python
from adk_fluent import RunConfig

result = (
    RunConfig()
    .input_audio_transcribe("...")
    .build()
)
```

### Configuration

#### `.input_audio_transcribe(value: Union[AudioTranscriptionConfig, NoneType]) -> Self`

- **Maps to:** `input_audio_transcription`
- Set the `input_audio_transcription` field.

#### `.output_audio_transcribe(value: Union[AudioTranscriptionConfig, NoneType]) -> Self`

- **Maps to:** `output_audio_transcription`
- Set the `output_audio_transcription` field.

### Control Flow & Execution

#### `.build() -> RunConfig`

Resolve into a native ADK RunConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                   | Type                                              |
| --------------------------------------- | ------------------------------------------------- |
| `.speech_config(value)`                 | `Union[SpeechConfig, NoneType]`                   |
| `.response_modalities(value)`           | `Union[list[str], NoneType]`                      |
| `.save_input_blobs_as_artifacts(value)` | `bool`                                            |
| `.support_cfc(value)`                   | `bool`                                            |
| `.streaming_mode(value)`                | `StreamingMode`                                   |
| `.realtime_input_config(value)`         | `Union[RealtimeInputConfig, NoneType]`            |
| `.enable_affective_dialog(value)`       | `Union[bool, NoneType]`                           |
| `.proactivity(value)`                   | `Union[ProactivityConfig, NoneType]`              |
| `.session_resumption(value)`            | `Union[SessionResumptionConfig, NoneType]`        |
| `.context_window_compression(value)`    | `Union[ContextWindowCompressionConfig, NoneType]` |
| `.save_live_blob(value)`                | `bool`                                            |
| `.tool_thread_pool_config(value)`       | `Union[ToolThreadPoolConfig, NoneType]`           |
| `.save_live_audio(value)`               | `bool`                                            |
| `.max_llm_calls(value)`                 | `int`                                             |
| `.custom_metadata(value)`               | `Union[dict[str, Any], NoneType]`                 |

______________________________________________________________________

(builder-ToolThreadPoolConfig)=

## ToolThreadPoolConfig

> Fluent builder for `google.adk.agents.run_config.ToolThreadPoolConfig`

Configuration for the tool thread pool executor.

**Quick start:**

```python
from adk_fluent import ToolThreadPoolConfig

result = (
    ToolThreadPoolConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> ToolThreadPoolConfig`

Resolve into a native ADK ToolThreadPoolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                 | Type  |
| --------------------- | ----- |
| `.max_workers(value)` | `int` |

______________________________________________________________________

(builder-SequentialAgentConfig)=

## SequentialAgentConfig

> Fluent builder for `google.adk.agents.sequential_agent_config.SequentialAgentConfig`

The config for the YAML schema of a SequentialAgent.

**Quick start:**

```python
from adk_fluent import SequentialAgentConfig

result = (
    SequentialAgentConfig("name_value")
    .describe("...")
    .build()
)
```

### Constructor

```python
SequentialAgentConfig(name: str)
```

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Core Configuration

#### `.describe(value: str) -> Self`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.sub_agent(value: AgentRefConfig) -> Self`

Append to `sub_agents` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self`

Append to `after_agent_callbacks` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self`

Append to `before_agent_callbacks` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> SequentialAgentConfig`

Resolve into a native ADK SequentialAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                            | Type                                    |
| -------------------------------- | --------------------------------------- |
| `.agent_class(value)`            | `str`                                   |
| `.sub_agents(value)`             | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]`     |
| `.after_agent_callbacks(value)`  | `Union[list[CodeConfig], NoneType]`     |

______________________________________________________________________

(builder-EventsCompactionConfig)=

## EventsCompactionConfig

> Fluent builder for `google.adk.apps.app.EventsCompactionConfig`

The config of event compaction for an application.

**Quick start:**

```python
from adk_fluent import EventsCompactionConfig

result = (
    EventsCompactionConfig("compaction_interval_value", "overlap_size_value")
    .build()
)
```

### Constructor

```python
EventsCompactionConfig(compaction_interval: int, overlap_size: int)
```

| Argument              | Type  |
| --------------------- | ----- |
| `compaction_interval` | `int` |
| `overlap_size`        | `int` |

### Control Flow & Execution

#### `.build() -> EventsCompactionConfig`

Resolve into a native ADK EventsCompactionConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type                                    |
| ------------------------------ | --------------------------------------- |
| `.summarizer(value)`           | `Union[BaseEventsSummarizer, NoneType]` |
| `.token_threshold(value)`      | `Union[int, NoneType]`                  |
| `.event_retention_size(value)` | `Union[int, NoneType]`                  |

______________________________________________________________________

(builder-ResumabilityConfig)=

## ResumabilityConfig

> Fluent builder for `google.adk.apps.app.ResumabilityConfig`

The config of the resumability for an application.

**Quick start:**

```python
from adk_fluent import ResumabilityConfig

result = (
    ResumabilityConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> ResumabilityConfig`

Resolve into a native ADK ResumabilityConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                  | Type   |
| ---------------------- | ------ |
| `.is_resumable(value)` | `bool` |

______________________________________________________________________

(builder-FeatureConfig)=

## FeatureConfig

> Fluent builder for `google.adk.features._feature_registry.FeatureConfig`

Feature configuration.

**Quick start:**

```python
from adk_fluent import FeatureConfig

result = (
    FeatureConfig("stage_value")
    .build()
)
```

### Constructor

```python
FeatureConfig(stage: FeatureStage)
```

| Argument | Type           |
| -------- | -------------- |
| `stage`  | `FeatureStage` |

### Control Flow & Execution

#### `.build() -> FeatureConfig`

Resolve into a native ADK FeatureConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                | Type   |
| -------------------- | ------ |
| `.default_on(value)` | `bool` |

______________________________________________________________________

(builder-AudioCacheConfig)=

## AudioCacheConfig

> Fluent builder for `google.adk.flows.llm_flows.audio_cache_manager.AudioCacheConfig`

Configuration for audio caching behavior.

**Quick start:**

```python
from adk_fluent import AudioCacheConfig

result = (
    AudioCacheConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> AudioCacheConfig`

Resolve into a native ADK AudioCacheConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                | Type    |
| ------------------------------------ | ------- |
| `.max_cache_size_bytes(value)`       | `int`   |
| `.max_cache_duration_seconds(value)` | `float` |
| `.auto_flush_threshold(value)`       | `int`   |

______________________________________________________________________

(builder-SimplePromptOptimizerConfig)=

## SimplePromptOptimizerConfig

> Fluent builder for `google.adk.optimization.simple_prompt_optimizer.SimplePromptOptimizerConfig`

Configuration for the IterativePromptOptimizer.

**Quick start:**

```python
from adk_fluent import SimplePromptOptimizerConfig

result = (
    SimplePromptOptimizerConfig()
    .model_configure("...")
    .build()
)
```

### Configuration

#### `.model_configure(value: GenerateContentConfig) -> Self`

- **Maps to:** `model_configuration`
- The configuration for the optimizer model.

### Control Flow & Execution

#### `.build() -> SimplePromptOptimizerConfig`

Resolve into a native ADK SimplePromptOptimizerConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                     | Type  |
| ------------------------- | ----- |
| `.optimizer_model(value)` | `str` |
| `.num_iterations(value)`  | `int` |
| `.batch_size(value)`      | `int` |

______________________________________________________________________

(builder-BigQueryLoggerConfig)=

## BigQueryLoggerConfig

> Fluent builder for `google.adk.plugins.bigquery_agent_analytics_plugin.BigQueryLoggerConfig`

Configuration for the BigQueryAgentAnalyticsPlugin.

**Quick start:**

```python
from adk_fluent import BigQueryLoggerConfig

result = (
    BigQueryLoggerConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> BigQueryLoggerConfig`

Resolve into a native ADK BigQueryLoggerConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                             | Type                                  |
| --------------------------------- | ------------------------------------- |
| `.enabled(value)`                 | `bool`                                |
| `.event_allowlist(value)`         | \`list[str]                           |
| `.event_denylist(value)`          | \`list[str]                           |
| `.max_content_length(value)`      | `int`                                 |
| `.table_id(value)`                | `str`                                 |
| `.clustering_fields(value)`       | `list[str]`                           |
| `.log_multi_modal_content(value)` | `bool`                                |
| `.retry_config(value)`            | `RetryConfig`                         |
| `.batch_size(value)`              | `int`                                 |
| `.batch_flush_interval(value)`    | `float`                               |
| `.shutdown_timeout(value)`        | `float`                               |
| `.queue_max_size(value)`          | `int`                                 |
| `.content_formatter(value)`       | `Optional[Callable[[Any, str], Any]]` |
| `.gcs_bucket_name(value)`         | `Optional[str]`                       |
| `.connection_id(value)`           | `Optional[str]`                       |
| `.log_session_metadata(value)`    | `bool`                                |
| `.custom_tags(value)`             | `dict[str, Any]`                      |

______________________________________________________________________

(builder-RetryConfig)=

## RetryConfig

> Fluent builder for `google.adk.plugins.bigquery_agent_analytics_plugin.RetryConfig`

Configuration for retrying failed BigQuery write operations.

**Quick start:**

```python
from adk_fluent import RetryConfig

result = (
    RetryConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> RetryConfig`

Resolve into a native ADK RetryConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                   | Type    |
| ----------------------- | ------- |
| `.max_retries(value)`   | `int`   |
| `.initial_delay(value)` | `float` |
| `.multiplier(value)`    | `float` |
| `.max_delay(value)`     | `float` |

______________________________________________________________________

(builder-GetSessionConfig)=

## GetSessionConfig

> Fluent builder for `google.adk.sessions.base_session_service.GetSessionConfig`

The configuration of getting a session.

**Quick start:**

```python
from adk_fluent import GetSessionConfig

result = (
    GetSessionConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> GetSessionConfig`

Resolve into a native ADK GetSessionConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                       | Type                     |
| --------------------------- | ------------------------ |
| `.num_recent_events(value)` | `Union[int, NoneType]`   |
| `.after_timestamp(value)`   | `Union[float, NoneType]` |

______________________________________________________________________

(builder-BaseGoogleCredentialsConfig)=

## BaseGoogleCredentialsConfig

> Fluent builder for `google.adk.tools._google_credentials.BaseGoogleCredentialsConfig`

Base Google Credentials Configuration for Google API tools (Experimental).

**Quick start:**

```python
from adk_fluent import BaseGoogleCredentialsConfig

result = (
    BaseGoogleCredentialsConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> BaseGoogleCredentialsConfig`

Resolve into a native ADK BaseGoogleCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                               | Type                           |
| ----------------------------------- | ------------------------------ |
| `.credentials(value)`               | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]`         |
| `.client_id(value)`                 | `Union[str, NoneType]`         |
| `.client_secret(value)`             | `Union[str, NoneType]`         |
| `.scopes(value)`                    | `Union[list[str], NoneType]`   |

______________________________________________________________________

(builder-AgentSimulatorConfig)=

## AgentSimulatorConfig

> Fluent builder for `google.adk.tools.agent_simulator.agent_simulator_config.AgentSimulatorConfig`

Configuration for AgentSimulator.

**Quick start:**

```python
from adk_fluent import AgentSimulatorConfig

result = (
    AgentSimulatorConfig()
    .simulation_model_configure("...")
    .build()
)
```

### Configuration

#### `.simulation_model_configure(value: GenerateContentConfig) -> Self`

- **Maps to:** `simulation_model_configuration`
- Set the `simulation_model_configuration` field.

#### `.tool_simulation_config(value: ToolSimulationConfig) -> Self`

Append to `tool_simulation_configs` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> AgentSimulatorConfig`

Resolve into a native ADK AgentSimulatorConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                             | Type                         |
| --------------------------------- | ---------------------------- |
| `.tool_simulation_configs(value)` | `list[ToolSimulationConfig]` |
| `.simulation_model(value)`        | `str`                        |
| `.tracing_path(value)`            | `Union[str, NoneType]`       |
| `.environment_data(value)`        | `Union[str, NoneType]`       |

______________________________________________________________________

(builder-InjectionConfig)=

## InjectionConfig

> Fluent builder for `google.adk.tools.agent_simulator.agent_simulator_config.InjectionConfig`

Injection configuration for a tool.

**Quick start:**

```python
from adk_fluent import InjectionConfig

result = (
    InjectionConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> InjectionConfig`

Resolve into a native ADK InjectionConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                              | Type                              |
| ---------------------------------- | --------------------------------- |
| `.injection_probability(value)`    | `float`                           |
| `.match_args(value)`               | `Union[dict[str, Any], NoneType]` |
| `.injected_latency_seconds(value)` | `float`                           |
| `.random_seed(value)`              | `Union[int, NoneType]`            |
| `.injected_error(value)`           | `Union[InjectedError, NoneType]`  |
| `.injected_response(value)`        | `Union[dict[str, Any], NoneType]` |

______________________________________________________________________

(builder-ToolSimulationConfig)=

## ToolSimulationConfig

> Fluent builder for `google.adk.tools.agent_simulator.agent_simulator_config.ToolSimulationConfig`

Simulation configuration for a single tool.

**Quick start:**

```python
from adk_fluent import ToolSimulationConfig

result = (
    ToolSimulationConfig("tool_name_value")
    .injection_config(...)
    .build()
)
```

### Constructor

```python
ToolSimulationConfig(tool_name: str)
```

| Argument    | Type  |
| ----------- | ----- |
| `tool_name` | `str` |

### Configuration

#### `.injection_config(value: InjectionConfig) -> Self`

Append to `injection_configs` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> ToolSimulationConfig`

Resolve into a native ADK ToolSimulationConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                        | Type                    |
| ---------------------------- | ----------------------- |
| `.injection_configs(value)`  | `list[InjectionConfig]` |
| `.mock_strategy_type(value)` | `MockStrategy`          |

______________________________________________________________________

(builder-AgentToolConfig)=

## AgentToolConfig

> Fluent builder for `google.adk.tools.agent_tool.AgentToolConfig`

The config for the AgentTool.

**Quick start:**

```python
from adk_fluent import AgentToolConfig

result = (
    AgentToolConfig("agent_value")
    .skip_summarizate("...")
    .build()
)
```

### Constructor

```python
AgentToolConfig(agent: AgentRefConfig)
```

| Argument | Type             |
| -------- | ---------------- |
| `agent`  | `AgentRefConfig` |

### Configuration

#### `.skip_summarizate(value: bool) -> Self`

- **Maps to:** `skip_summarization`
- Set the `skip_summarization` field.

### Control Flow & Execution

#### `.build() -> AgentToolConfig`

Resolve into a native ADK AgentToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                     | Type   |
| ------------------------- | ------ |
| `.include_plugins(value)` | `bool` |

______________________________________________________________________

(builder-BigQueryCredentialsConfig)=

## BigQueryCredentialsConfig

> Fluent builder for `google.adk.tools.bigquery.bigquery_credentials.BigQueryCredentialsConfig`

BigQuery Credentials Configuration for Google API tools (Experimental).

**Quick start:**

```python
from adk_fluent import BigQueryCredentialsConfig

result = (
    BigQueryCredentialsConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> BigQueryCredentialsConfig`

Resolve into a native ADK BigQueryCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                               | Type                           |
| ----------------------------------- | ------------------------------ |
| `.credentials(value)`               | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]`         |
| `.client_id(value)`                 | `Union[str, NoneType]`         |
| `.client_secret(value)`             | `Union[str, NoneType]`         |
| `.scopes(value)`                    | `Union[list[str], NoneType]`   |

______________________________________________________________________

(builder-BigQueryToolConfig)=

## BigQueryToolConfig

> Fluent builder for `google.adk.tools.bigquery.config.BigQueryToolConfig`

Configuration for BigQuery tools.

**Quick start:**

```python
from adk_fluent import BigQueryToolConfig

result = (
    BigQueryToolConfig()
    .locate("...")
    .build()
)
```

### Configuration

#### `.locate(value: Union[str, NoneType]) -> Self`

- **Maps to:** `location`
- Set the `location` field.

### Control Flow & Execution

#### `.build() -> BigQueryToolConfig`

Resolve into a native ADK BigQueryToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                           | Type                              |
| ------------------------------- | --------------------------------- |
| `.write_mode(value)`            | `WriteMode`                       |
| `.maximum_bytes_billed(value)`  | `Union[int, NoneType]`            |
| `.max_query_result_rows(value)` | `int`                             |
| `.application_name(value)`      | `Union[str, NoneType]`            |
| `.compute_project_id(value)`    | `Union[str, NoneType]`            |
| `.job_labels(value)`            | `Union[dict[str, str], NoneType]` |

______________________________________________________________________

(builder-BigtableCredentialsConfig)=

## BigtableCredentialsConfig

> Fluent builder for `google.adk.tools.bigtable.bigtable_credentials.BigtableCredentialsConfig`

Bigtable Credentials Configuration for Google API tools (Experimental).

**Quick start:**

```python
from adk_fluent import BigtableCredentialsConfig

result = (
    BigtableCredentialsConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> BigtableCredentialsConfig`

Resolve into a native ADK BigtableCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                               | Type                           |
| ----------------------------------- | ------------------------------ |
| `.credentials(value)`               | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]`         |
| `.client_id(value)`                 | `Union[str, NoneType]`         |
| `.client_secret(value)`             | `Union[str, NoneType]`         |
| `.scopes(value)`                    | `Union[list[str], NoneType]`   |

______________________________________________________________________

(builder-DataAgentToolConfig)=

## DataAgentToolConfig

> Fluent builder for `google.adk.tools.data_agent.config.DataAgentToolConfig`

Configuration for Data Agent tools.

**Quick start:**

```python
from adk_fluent import DataAgentToolConfig

result = (
    DataAgentToolConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> DataAgentToolConfig`

Resolve into a native ADK DataAgentToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                           | Type  |
| ------------------------------- | ----- |
| `.max_query_result_rows(value)` | `int` |

______________________________________________________________________

(builder-DataAgentCredentialsConfig)=

## DataAgentCredentialsConfig

> Fluent builder for `google.adk.tools.data_agent.credentials.DataAgentCredentialsConfig`

Data Agent Credentials Configuration for Google API tools.

**Quick start:**

```python
from adk_fluent import DataAgentCredentialsConfig

result = (
    DataAgentCredentialsConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> DataAgentCredentialsConfig`

Resolve into a native ADK DataAgentCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                               | Type                           |
| ----------------------------------- | ------------------------------ |
| `.credentials(value)`               | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]`         |
| `.client_id(value)`                 | `Union[str, NoneType]`         |
| `.client_secret(value)`             | `Union[str, NoneType]`         |
| `.scopes(value)`                    | `Union[list[str], NoneType]`   |

______________________________________________________________________

(builder-ExampleToolConfig)=

## ExampleToolConfig

> Fluent builder for `google.adk.tools.example_tool.ExampleToolConfig`

Fluent builder for ExampleToolConfig.

**Quick start:**

```python
from adk_fluent import ExampleToolConfig

result = (
    ExampleToolConfig("examples_value")
    .build()
)
```

### Constructor

```python
ExampleToolConfig(examples: Union[list[Example], str])
```

| Argument   | Type                        |
| ---------- | --------------------------- |
| `examples` | `Union[list[Example], str]` |

### Control Flow & Execution

#### `.build() -> ExampleToolConfig`

Resolve into a native ADK ExampleToolConfig.

______________________________________________________________________

(builder-McpToolsetConfig)=

## McpToolsetConfig

> Fluent builder for `google.adk.tools.mcp_tool.mcp_toolset.McpToolsetConfig`

The config for McpToolset.

**Quick start:**

```python
from adk_fluent import McpToolsetConfig

result = (
    McpToolsetConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> McpToolsetConfig`

Resolve into a native ADK McpToolsetConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                       | Type                                                                                            |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `.stdio_server_params(value)`               | `Union[StdioServerParameters, NoneType]`                                                        |
| `.stdio_connection_params(value)`           | `Union[StdioConnectionParams, NoneType]`                                                        |
| `.sse_connection_params(value)`             | `Union[SseConnectionParams, NoneType]`                                                          |
| `.streamable_http_connection_params(value)` | `Union[StreamableHTTPConnectionParams, NoneType]`                                               |
| `.tool_filter(value)`                       | `Union[list[str], NoneType]`                                                                    |
| `.tool_name_prefix(value)`                  | `Union[str, NoneType]`                                                                          |
| `.auth_scheme(value)`                       | `Union[APIKey, HTTPBase, OAuth2, OpenIdConnect, HTTPBearer, OpenIdConnectWithConfig, NoneType]` |
| `.auth_credential(value)`                   | `Union[AuthCredential, NoneType]`                                                               |
| `.use_mcp_resources(value)`                 | `bool`                                                                                          |

______________________________________________________________________

(builder-PubSubToolConfig)=

## PubSubToolConfig

> Fluent builder for `google.adk.tools.pubsub.config.PubSubToolConfig`

Configuration for Pub/Sub tools.

**Quick start:**

```python
from adk_fluent import PubSubToolConfig

result = (
    PubSubToolConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> PubSubToolConfig`

Resolve into a native ADK PubSubToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                | Type  |
| -------------------- | ----- |
| `.project_id(value)` | \`str |

______________________________________________________________________

(builder-PubSubCredentialsConfig)=

## PubSubCredentialsConfig

> Fluent builder for `google.adk.tools.pubsub.pubsub_credentials.PubSubCredentialsConfig`

Pub/Sub Credentials Configuration for Google API tools (Experimental).

**Quick start:**

```python
from adk_fluent import PubSubCredentialsConfig

result = (
    PubSubCredentialsConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> PubSubCredentialsConfig`

Resolve into a native ADK PubSubCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                               | Type                           |
| ----------------------------------- | ------------------------------ |
| `.credentials(value)`               | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]`         |
| `.client_id(value)`                 | `Union[str, NoneType]`         |
| `.client_secret(value)`             | `Union[str, NoneType]`         |
| `.scopes(value)`                    | `Union[list[str], NoneType]`   |

______________________________________________________________________

(builder-SpannerCredentialsConfig)=

## SpannerCredentialsConfig

> Fluent builder for `google.adk.tools.spanner.spanner_credentials.SpannerCredentialsConfig`

Spanner Credentials Configuration for Google API tools (Experimental).

**Quick start:**

```python
from adk_fluent import SpannerCredentialsConfig

result = (
    SpannerCredentialsConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> SpannerCredentialsConfig`

Resolve into a native ADK SpannerCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                               | Type                           |
| ----------------------------------- | ------------------------------ |
| `.credentials(value)`               | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]`         |
| `.client_id(value)`                 | `Union[str, NoneType]`         |
| `.client_secret(value)`             | `Union[str, NoneType]`         |
| `.scopes(value)`                    | `Union[list[str], NoneType]`   |

______________________________________________________________________

(builder-BaseToolConfig)=

## BaseToolConfig

> Fluent builder for `google.adk.tools.tool_configs.BaseToolConfig`

The base class for all tool configs.

**Quick start:**

```python
from adk_fluent import BaseToolConfig

result = (
    BaseToolConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> BaseToolConfig`

Resolve into a native ADK BaseToolConfig.

______________________________________________________________________

(builder-ToolArgsConfig)=

## ToolArgsConfig

> Fluent builder for `google.adk.tools.tool_configs.ToolArgsConfig`

Config to host free key-value pairs for the args in ToolConfig.

**Quick start:**

```python
from adk_fluent import ToolArgsConfig

result = (
    ToolArgsConfig()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> ToolArgsConfig`

Resolve into a native ADK ToolArgsConfig.

______________________________________________________________________

(builder-ToolConfig)=

## ToolConfig

> Fluent builder for `google.adk.tools.tool_configs.ToolConfig`

The configuration for a tool.

**Quick start:**

```python
from adk_fluent import ToolConfig

result = (
    ToolConfig("name_value")
    .build()
)
```

### Constructor

```python
ToolConfig(name: str)
```

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Control Flow & Execution

#### `.build() -> ToolConfig`

Resolve into a native ADK ToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field          | Type                              |
| -------------- | --------------------------------- |
| `.args(value)` | `Union[ToolArgsConfig, NoneType]` |
