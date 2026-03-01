# Module: `config`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [AgentConfig](builder-AgentConfig) | The config for the YAML schema to create an agent. |
| [BaseAgentConfig](builder-BaseAgentConfig) | The config for the YAML schema of a BaseAgent. |
| [AgentRefConfig](builder-AgentRefConfig) | The config for the reference to another agent. |
| [ArgumentConfig](builder-ArgumentConfig) | An argument passed to a function or a class's constructor. |
| [CodeConfig](builder-CodeConfig) | Code reference config for a variable, a function, or a class. |
| [ContextCacheConfig](builder-ContextCacheConfig) | Configuration for context caching across all agents in an app. |
| [LlmAgentConfig](builder-LlmAgentConfig) | The config for the YAML schema of a LlmAgent. |
| [LoopAgentConfig](builder-LoopAgentConfig) | The config for the YAML schema of a LoopAgent. |
| [ParallelAgentConfig](builder-ParallelAgentConfig) | The config for the YAML schema of a ParallelAgent. |
| [RunConfig](builder-RunConfig) | Configs for runtime behavior of agents. |
| [ToolThreadPoolConfig](builder-ToolThreadPoolConfig) | Configuration for the tool thread pool executor. |
| [SequentialAgentConfig](builder-SequentialAgentConfig) | The config for the YAML schema of a SequentialAgent. |
| [EventsCompactionConfig](builder-EventsCompactionConfig) | The config of event compaction for an application. |
| [ResumabilityConfig](builder-ResumabilityConfig) | The config of the resumability for an application. |
| [FeatureConfig](builder-FeatureConfig) | Feature configuration. |
| [AudioCacheConfig](builder-AudioCacheConfig) | Configuration for audio caching behavior. |
| [SimplePromptOptimizerConfig](builder-SimplePromptOptimizerConfig) | Configuration for the IterativePromptOptimizer. |
| [BigQueryLoggerConfig](builder-BigQueryLoggerConfig) | Configuration for the BigQueryAgentAnalyticsPlugin. |
| [RetryConfig](builder-RetryConfig) | Configuration for retrying failed BigQuery write operations. |
| [GetSessionConfig](builder-GetSessionConfig) | The configuration of getting a session. |
| [BaseGoogleCredentialsConfig](builder-BaseGoogleCredentialsConfig) | Base Google Credentials Configuration for Google API tools (Experimental). |
| [AgentSimulatorConfig](builder-AgentSimulatorConfig) | Configuration for AgentSimulator. |
| [InjectionConfig](builder-InjectionConfig) | Injection configuration for a tool. |
| [ToolSimulationConfig](builder-ToolSimulationConfig) | Simulation configuration for a single tool. |
| [AgentToolConfig](builder-AgentToolConfig) | The config for the AgentTool. |
| [BigQueryCredentialsConfig](builder-BigQueryCredentialsConfig) | BigQuery Credentials Configuration for Google API tools (Experimental). |
| [BigQueryToolConfig](builder-BigQueryToolConfig) | Configuration for BigQuery tools. |
| [BigtableCredentialsConfig](builder-BigtableCredentialsConfig) | Bigtable Credentials Configuration for Google API tools (Experimental). |
| [DataAgentToolConfig](builder-DataAgentToolConfig) | Configuration for Data Agent tools. |
| [DataAgentCredentialsConfig](builder-DataAgentCredentialsConfig) | Data Agent Credentials Configuration for Google API tools. |
| [ExampleToolConfig](builder-ExampleToolConfig) | Fluent builder for ExampleToolConfig. |
| [McpToolsetConfig](builder-McpToolsetConfig) | The config for McpToolset. |
| [PubSubToolConfig](builder-PubSubToolConfig) | Configuration for Pub/Sub tools. |
| [PubSubCredentialsConfig](builder-PubSubCredentialsConfig) | Pub/Sub Credentials Configuration for Google API tools (Experimental). |
| [SpannerCredentialsConfig](builder-SpannerCredentialsConfig) | Spanner Credentials Configuration for Google API tools (Experimental). |
| [BaseToolConfig](builder-BaseToolConfig) | The base class for all tool configs. |
| [ToolArgsConfig](builder-ToolArgsConfig) | Config to host free key-value pairs for the args in ToolConfig. |
| [ToolConfig](builder-ToolConfig) | The configuration for a tool. |

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

| Argument | Type |
|----------|------|
| `root` | `RootModelRootType` |

### Control Flow & Execution

#### `.build() -> AgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentConfig.

---

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

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |

### Core Configuration

#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to ``sub_agents`` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``after_agent_callbacks`` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``before_agent_callbacks`` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> BaseAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | `Literal['BaseAgent'] | str` |
| `.sub_agents(value)` | `list[AgentRefConfig] | None` |
| `.before_agent_callbacks(value)` | `list[CodeConfig] | None` |
| `.after_agent_callbacks(value)` | `list[CodeConfig] | None` |

---

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

#### `.build() -> AgentRefConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentRefConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.config_path(value)` | `str | None` |
| `.code(value)` | `str | None` |

---

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

| Argument | Type |
|----------|------|
| `value` | `Any` |

### Control Flow & Execution

#### `.build() -> ArgumentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ArgumentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `str | None` |

---

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

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |

### Configuration

#### `.arg(value: ArgumentConfig) -> Self` {bdg-info}`Configuration`

Append to ``args`` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> CodeConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK CodeConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.args(value)` | `list[ArgumentConfig] | None` |

---

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

#### `.build() -> ContextCacheConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ContextCacheConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.cache_intervals(value)` | {py:class}`int` |
| `.ttl_seconds(value)` | {py:class}`int` |
| `.min_tokens(value)` | {py:class}`int` |

---

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

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |
| `instruction` | {py:class}`str` |

### Core Configuration

#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.history(value: Literal['default', 'none']) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `include_contents`
- Optional. LlmAgent.include_contents.

#### `.instruct(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `instruction`
- Required. LlmAgent.instruction. Dynamic instructions with placeholder support. Behavior: if static_instruction is None, goes to system_instruction; if static_instruction is set, goes to user content after static content.

#### `.outputs(value: str | None) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `output_key`
- Deprecated: use ``.writes(key)`` instead. Session state key where the agent's response text is stored.

#### `.static(value: Content | str | File | Part | list[str | File | Part] | None) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `static_instruction`
- Optional. LlmAgent.static_instruction. Static content sent literally at position 0 without placeholder processing. When set, changes instruction behavior to go to user content instead of system_instruction. Supports context caching. Accepts types.ContentUnion (str, types.Content, types.Part, PIL.Image.Image, types.File, or list[PartUnion]).

#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to ``sub_agents`` (lazy — built at .build() time).

#### `.tool(value: ToolConfig) -> Self` {bdg-success}`Core Configuration`

Append to ``tools`` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``after_agent_callbacks`` (lazy — built at .build() time).

#### `.after_model_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``after_model_callbacks`` (lazy — built at .build() time).

#### `.after_tool_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``after_tool_callbacks`` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``before_agent_callbacks`` (lazy — built at .build() time).

#### `.before_model_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``before_model_callbacks`` (lazy — built at .build() time).

#### `.before_tool_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``before_tool_callbacks`` (lazy — built at .build() time).

#### `.include_history(value: Literal['default', 'none']) -> Self` {bdg-info}`Configuration`

- **Maps to:** `include_contents`
- Optional. LlmAgent.include_contents.

#### `.static_instruct(value: Content | str | File | Part | list[str | File | Part] | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `static_instruction`
- Optional. LlmAgent.static_instruction. Static content sent literally at position 0 without placeholder processing. When set, changes instruction behavior to go to user content instead of system_instruction. Supports context caching. Accepts types.ContentUnion (str, types.Content, types.Part, PIL.Image.Image, types.File, or list[PartUnion]).

### Control Flow & Execution

#### `.build() -> LlmAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LlmAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | {py:class}`str` |
| `.sub_agents(value)` | `list[AgentRefConfig] | None` |
| `.before_agent_callbacks(value)` | `list[CodeConfig] | None` |
| `.after_agent_callbacks(value)` | `list[CodeConfig] | None` |
| `.model(value)` | `str | None` |
| `.model_code(value)` | `CodeConfig | None` |
| `.disallow_transfer_to_parent(value)` | `bool | None` |
| `.disallow_transfer_to_peers(value)` | `bool | None` |
| `.input_schema(value)` | `CodeConfig | None` |
| `.output_schema(value)` | `CodeConfig | None` |
| `.tools(value)` | `list[ToolConfig] | None` |
| `.before_model_callbacks(value)` | `list[CodeConfig] | None` |
| `.after_model_callbacks(value)` | `list[CodeConfig] | None` |
| `.before_tool_callbacks(value)` | `list[CodeConfig] | None` |
| `.after_tool_callbacks(value)` | `list[CodeConfig] | None` |
| `.generate_content_config(value)` | `GenerateContentConfig | None` |

---

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

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |

### Core Configuration

#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to ``sub_agents`` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``after_agent_callbacks`` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``before_agent_callbacks`` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> LoopAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LoopAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | {py:class}`str` |
| `.sub_agents(value)` | `list[AgentRefConfig] | None` |
| `.before_agent_callbacks(value)` | `list[CodeConfig] | None` |
| `.after_agent_callbacks(value)` | `list[CodeConfig] | None` |
| `.max_iterations(value)` | `int | None` |

---

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

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |

### Core Configuration

#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to ``sub_agents`` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``after_agent_callbacks`` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``before_agent_callbacks`` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> ParallelAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ParallelAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | {py:class}`str` |
| `.sub_agents(value)` | `list[AgentRefConfig] | None` |
| `.before_agent_callbacks(value)` | `list[CodeConfig] | None` |
| `.after_agent_callbacks(value)` | `list[CodeConfig] | None` |

---

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

#### `.input_audio_transcribe(value: AudioTranscriptionConfig | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `input_audio_transcription`
- Set the `input_audio_transcription` field.

#### `.output_audio_transcribe(value: AudioTranscriptionConfig | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `output_audio_transcription`
- Set the `output_audio_transcription` field.

### Control Flow & Execution

#### `.build() -> RunConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK RunConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.speech_config(value)` | `SpeechConfig | None` |
| `.response_modalities(value)` | `list[str] | None` |
| `.save_input_blobs_as_artifacts(value)` | {py:class}`bool` |
| `.support_cfc(value)` | {py:class}`bool` |
| `.streaming_mode(value)` | `StreamingMode` |
| `.realtime_input_config(value)` | `RealtimeInputConfig | None` |
| `.enable_affective_dialog(value)` | `bool | None` |
| `.proactivity(value)` | `ProactivityConfig | None` |
| `.session_resumption(value)` | `SessionResumptionConfig | None` |
| `.context_window_compression(value)` | `ContextWindowCompressionConfig | None` |
| `.save_live_blob(value)` | {py:class}`bool` |
| `.tool_thread_pool_config(value)` | `ToolThreadPoolConfig | None` |
| `.save_live_audio(value)` | {py:class}`bool` |
| `.max_llm_calls(value)` | {py:class}`int` |
| `.custom_metadata(value)` | `dict[str, Any] | None` |

---

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

#### `.build() -> ToolThreadPoolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ToolThreadPoolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.max_workers(value)` | {py:class}`int` |

---

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

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |

### Core Configuration

#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Optional. The description of the agent.

#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to ``sub_agents`` (lazy — built at .build() time).

### Configuration

#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``after_agent_callbacks`` (lazy — built at .build() time).

#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to ``before_agent_callbacks`` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> SequentialAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SequentialAgentConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | {py:class}`str` |
| `.sub_agents(value)` | `list[AgentRefConfig] | None` |
| `.before_agent_callbacks(value)` | `list[CodeConfig] | None` |
| `.after_agent_callbacks(value)` | `list[CodeConfig] | None` |

---

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

| Argument | Type |
|----------|------|
| `compaction_interval` | {py:class}`int` |
| `overlap_size` | {py:class}`int` |

### Control Flow & Execution

#### `.build() -> EventsCompactionConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK EventsCompactionConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.summarizer(value)` | `BaseEventsSummarizer | None` |
| `.token_threshold(value)` | `int | None` |
| `.event_retention_size(value)` | `int | None` |

---

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

#### `.build() -> ResumabilityConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ResumabilityConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.is_resumable(value)` | {py:class}`bool` |

---

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

| Argument | Type |
|----------|------|
| `stage` | `FeatureStage` |

### Control Flow & Execution

#### `.build() -> FeatureConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK FeatureConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.default_on(value)` | {py:class}`bool` |

---

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

#### `.build() -> AudioCacheConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AudioCacheConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.max_cache_size_bytes(value)` | {py:class}`int` |
| `.max_cache_duration_seconds(value)` | {py:class}`float` |
| `.auto_flush_threshold(value)` | {py:class}`int` |

---

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

#### `.model_configure(value: GenerateContentConfig) -> Self` {bdg-info}`Configuration`

- **Maps to:** `model_configuration`
- The configuration for the optimizer model.

### Control Flow & Execution

#### `.build() -> SimplePromptOptimizerConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SimplePromptOptimizerConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimizer_model(value)` | {py:class}`str` |
| `.num_iterations(value)` | {py:class}`int` |
| `.batch_size(value)` | {py:class}`int` |

---

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

#### `.build() -> BigQueryLoggerConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigQueryLoggerConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.enabled(value)` | {py:class}`bool` |
| `.event_allowlist(value)` | `list[str] | None` |
| `.event_denylist(value)` | `list[str] | None` |
| `.max_content_length(value)` | {py:class}`int` |
| `.table_id(value)` | {py:class}`str` |
| `.clustering_fields(value)` | `list[str]` |
| `.log_multi_modal_content(value)` | {py:class}`bool` |
| `.retry_config(value)` | `RetryConfig` |
| `.batch_size(value)` | {py:class}`int` |
| `.batch_flush_interval(value)` | {py:class}`float` |
| `.shutdown_timeout(value)` | {py:class}`float` |
| `.queue_max_size(value)` | {py:class}`int` |
| `.content_formatter(value)` | `Callable[[Any, str], Any] | None` |
| `.gcs_bucket_name(value)` | `str | None` |
| `.connection_id(value)` | `str | None` |
| `.log_session_metadata(value)` | {py:class}`bool` |
| `.custom_tags(value)` | `dict[str, Any]` |

---

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

#### `.build() -> RetryConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK RetryConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.max_retries(value)` | {py:class}`int` |
| `.initial_delay(value)` | {py:class}`float` |
| `.multiplier(value)` | {py:class}`float` |
| `.max_delay(value)` | {py:class}`float` |

---

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

#### `.build() -> GetSessionConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK GetSessionConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.num_recent_events(value)` | `int | None` |
| `.after_timestamp(value)` | `float | None` |

---

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

#### `.build() -> BaseGoogleCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseGoogleCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Credentials | None` |
| `.external_access_token_key(value)` | `str | None` |
| `.client_id(value)` | `str | None` |
| `.client_secret(value)` | `str | None` |
| `.scopes(value)` | `list[str] | None` |

---

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

#### `.simulation_model_configure(value: GenerateContentConfig) -> Self` {bdg-info}`Configuration`

- **Maps to:** `simulation_model_configuration`
- Set the `simulation_model_configuration` field.

#### `.tool_simulation_config(value: ToolSimulationConfig) -> Self` {bdg-info}`Configuration`

Append to ``tool_simulation_configs`` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> AgentSimulatorConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentSimulatorConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_simulation_configs(value)` | `list[ToolSimulationConfig]` |
| `.simulation_model(value)` | {py:class}`str` |
| `.tracing_path(value)` | `str | None` |
| `.environment_data(value)` | `str | None` |

---

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

#### `.build() -> InjectionConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK InjectionConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.injection_probability(value)` | {py:class}`float` |
| `.match_args(value)` | `dict[str, Any] | None` |
| `.injected_latency_seconds(value)` | {py:class}`float` |
| `.random_seed(value)` | `int | None` |
| `.injected_error(value)` | `InjectedError | None` |
| `.injected_response(value)` | `dict[str, Any] | None` |

---

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

| Argument | Type |
|----------|------|
| `tool_name` | {py:class}`str` |

### Configuration

#### `.injection_config(value: InjectionConfig) -> Self` {bdg-info}`Configuration`

Append to ``injection_configs`` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> ToolSimulationConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ToolSimulationConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.injection_configs(value)` | `list[InjectionConfig]` |
| `.mock_strategy_type(value)` | `MockStrategy` |

---

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

| Argument | Type |
|----------|------|
| `agent` | `AgentRefConfig` |

### Configuration

#### `.skip_summarizate(value: bool) -> Self` {bdg-info}`Configuration`

- **Maps to:** `skip_summarization`
- Set the `skip_summarization` field.

### Control Flow & Execution

#### `.build() -> AgentToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.include_plugins(value)` | {py:class}`bool` |

---

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

#### `.build() -> BigQueryCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigQueryCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Credentials | None` |
| `.external_access_token_key(value)` | `str | None` |
| `.client_id(value)` | `str | None` |
| `.client_secret(value)` | `str | None` |
| `.scopes(value)` | `list[str] | None` |

---

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

#### `.locate(value: str | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `location`
- Set the `location` field.

### Control Flow & Execution

#### `.build() -> BigQueryToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigQueryToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.write_mode(value)` | `WriteMode` |
| `.maximum_bytes_billed(value)` | `int | None` |
| `.max_query_result_rows(value)` | {py:class}`int` |
| `.application_name(value)` | `str | None` |
| `.compute_project_id(value)` | `str | None` |
| `.job_labels(value)` | `dict[str, str] | None` |

---

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

#### `.build() -> BigtableCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigtableCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Credentials | None` |
| `.external_access_token_key(value)` | `str | None` |
| `.client_id(value)` | `str | None` |
| `.client_secret(value)` | `str | None` |
| `.scopes(value)` | `list[str] | None` |

---

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

#### `.build() -> DataAgentToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK DataAgentToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.max_query_result_rows(value)` | {py:class}`int` |

---

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

#### `.build() -> DataAgentCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK DataAgentCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Credentials | None` |
| `.external_access_token_key(value)` | `str | None` |
| `.client_id(value)` | `str | None` |
| `.client_secret(value)` | `str | None` |
| `.scopes(value)` | `list[str] | None` |

---

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
ExampleToolConfig(examples: list[Example] | str)
```

| Argument | Type |
|----------|------|
| `examples` | `list[Example] | str` |

### Control Flow & Execution

#### `.build() -> ExampleToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ExampleToolConfig.

---

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

#### `.build() -> McpToolsetConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK McpToolsetConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.stdio_server_params(value)` | `StdioServerParameters | None` |
| `.stdio_connection_params(value)` | `StdioConnectionParams | None` |
| `.sse_connection_params(value)` | `SseConnectionParams | None` |
| `.streamable_http_connection_params(value)` | `StreamableHTTPConnectionParams | None` |
| `.tool_filter(value)` | `list[str] | None` |
| `.tool_name_prefix(value)` | `str | None` |
| `.auth_scheme(value)` | `APIKey | HTTPBase | OAuth2 | OpenIdConnect | HTTPBearer | OpenIdConnectWithConfig | None` |
| `.auth_credential(value)` | `AuthCredential | None` |
| `.use_mcp_resources(value)` | {py:class}`bool` |

---

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

#### `.build() -> PubSubToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK PubSubToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.project_id(value)` | `str | None` |

---

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

#### `.build() -> PubSubCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK PubSubCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Credentials | None` |
| `.external_access_token_key(value)` | `str | None` |
| `.client_id(value)` | `str | None` |
| `.client_secret(value)` | `str | None` |
| `.scopes(value)` | `list[str] | None` |

---

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

#### `.build() -> SpannerCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SpannerCredentialsConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Credentials | None` |
| `.external_access_token_key(value)` | `str | None` |
| `.client_id(value)` | `str | None` |
| `.client_secret(value)` | `str | None` |
| `.scopes(value)` | `list[str] | None` |

---

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

#### `.build() -> BaseToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseToolConfig.

---

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

#### `.build() -> ToolArgsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ToolArgsConfig.

---

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

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |

### Control Flow & Execution

#### `.build() -> ToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ToolConfig.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.args(value)` | `ToolArgsConfig | None` |
