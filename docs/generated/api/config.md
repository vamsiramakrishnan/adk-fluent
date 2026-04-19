# Module: `config`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [A2aAgentExecutorConfig](builder-A2aAgentExecutorConfig) | Configuration for the A2aAgentExecutor. |
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

(builder-A2aAgentExecutorConfig)=
## A2aAgentExecutorConfig

> Fluent builder for `google.adk.a2a.executor.a2a_agent_executor.A2aAgentExecutorConfig`

Configuration for the A2aAgentExecutor.

**Quick start:**

```python
from adk_fluent import A2aAgentExecutorConfig

result = (
    A2aAgentExecutorConfig()
    .build()
)
```

### Control Flow & Execution

(method-A2aAgentExecutorConfig-build)=
#### `.build() -> A2aAgentExecutorConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK A2aAgentExecutorConfig.

**Example:**

```python
config = A2aAgentExecutorConfig("config").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.a2a_part_converter(value)` | `Callable[[Part], Part | None | list[Part]]` |
| `.gen_ai_part_converter(value)` | `Callable[[Part], Part | None | list[Part]]` |
| `.request_converter(value)` | `Callable[[RequestContext, Callable[[Part], Part | None | list[Part]]], AgentRunRequest]` |
| `.event_converter(value)` | `Callable[[Event, InvocationContext, str | None, str | None, Callable[[Part], Part | None | list[Part]]], list[a2a.types.Message | a2a.types.Task | a2a.types.TaskStatusUpdateEvent | a2a.types.TaskArtifactUpdateEvent]]` |

---

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

(method-AgentConfig-build)=
#### `.build() -> AgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentConfig.

**Example:**

```python
config = AgentConfig("config").build("...")
```

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

(method-BaseAgentConfig-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
config = BaseAgentConfig("config").describe("...")
```

(method-BaseAgentConfig-sub_agent)=
#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
config = BaseAgentConfig("config").sub_agent("...")
```

### Configuration

(method-BaseAgentConfig-after_agent_callback)=
#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `after_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = BaseAgentConfig("config").after_agent_callback(my_callback_fn)
```

(method-BaseAgentConfig-before_agent_callback)=
#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `before_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = BaseAgentConfig("config").before_agent_callback(my_callback_fn)
```

### Control Flow & Execution

(method-BaseAgentConfig-build)=
#### `.build() -> BaseAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseAgentConfig.

**Example:**

```python
config = BaseAgentConfig("config").build("...")
```

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

(method-AgentRefConfig-build)=
#### `.build() -> AgentRefConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentRefConfig.

**Example:**

```python
config = AgentRefConfig("config").build("...")
```

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

(method-ArgumentConfig-build)=
#### `.build() -> ArgumentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ArgumentConfig.

**Example:**

```python
config = ArgumentConfig("config").build("...")
```

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

(method-CodeConfig-arg)=
#### `.arg(value: ArgumentConfig) -> Self` {bdg-info}`Configuration`

Append to `args` (lazy — built at .build() time).

**Example:**

```python
config = CodeConfig("config").arg("...")
```

### Control Flow & Execution

(method-CodeConfig-build)=
#### `.build() -> CodeConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK CodeConfig.

**Example:**

```python
config = CodeConfig("config").build("...")
```

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

(method-ContextCacheConfig-build)=
#### `.build() -> ContextCacheConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ContextCacheConfig.

**Example:**

```python
config = ContextCacheConfig("config").build("...")
```

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

(method-LlmAgentConfig-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
config = LlmAgentConfig("config").describe("...")
```

(method-LlmAgentConfig-history)=
#### `.history(value: Literal['default', 'none']) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `include_contents`
- Optional. LlmAgent.include_contents.

**Example:**

```python
config = LlmAgentConfig("config").history("none")
```

(method-LlmAgentConfig-instruct)=
#### `.instruct(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `instruction`
- Required. LlmAgent.instruction. Dynamic instructions with placeholder support. Behavior: if static_instruction is None, goes to system_instruction; if static_instruction is set, goes to user content after static content.

**Example:**

```python
config = LlmAgentConfig("config").instruct("You are a helpful assistant.")
```

(method-LlmAgentConfig-outputs)=
#### `.outputs(value: str | None) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `output_key`
- Deprecated: use `.writes(key)` instead. Session state key where the agent's response text is stored.

**Example:**

```python
config = LlmAgentConfig("config").outputs("result_key")
```

(method-LlmAgentConfig-static)=
#### `.static(value: Content | str | File | Part | list[str | File | Part] | None) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `static_instruction`
- Set cached instruction. When set, `.instruct()` text moves from system to user content, enabling context caching. Use for large, stable prompt sections that rarely change.

**Example:**

```python
config = LlmAgentConfig("config").static("You are a helpful assistant.")
```

(method-LlmAgentConfig-sub_agent)=
#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
config = LlmAgentConfig("config").sub_agent("...")
```

(method-LlmAgentConfig-tool)=
#### `.tool(value: ToolConfig) -> Self` {bdg-success}`Core Configuration`

Append to `tools` (lazy — built at .build() time).

**Example:**

```python
config = LlmAgentConfig("config").tool(my_function)
```

### Configuration

(method-LlmAgentConfig-after_agent_callback)=
#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `after_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = LlmAgentConfig("config").after_agent_callback(my_callback_fn)
```

(method-LlmAgentConfig-after_model_callback)=
#### `.after_model_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `after_model_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = LlmAgentConfig("config").after_model_callback(my_callback_fn)
```

(method-LlmAgentConfig-after_tool_callback)=
#### `.after_tool_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `after_tool_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = LlmAgentConfig("config").after_tool_callback(my_callback_fn)
```

(method-LlmAgentConfig-before_agent_callback)=
#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `before_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = LlmAgentConfig("config").before_agent_callback(my_callback_fn)
```

(method-LlmAgentConfig-before_model_callback)=
#### `.before_model_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `before_model_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = LlmAgentConfig("config").before_model_callback(my_callback_fn)
```

(method-LlmAgentConfig-before_tool_callback)=
#### `.before_tool_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `before_tool_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = LlmAgentConfig("config").before_tool_callback(my_callback_fn)
```

(method-LlmAgentConfig-include_history)=
#### `.include_history(value: Literal['default', 'none']) -> Self` {bdg-info}`Configuration`

- **Maps to:** `include_contents`
- Optional. LlmAgent.include_contents.

**Example:**

```python
config = LlmAgentConfig("config").include_history("none")
```

(method-LlmAgentConfig-static_instruct)=
#### `.static_instruct(value: Content | str | File | Part | list[str | File | Part] | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `static_instruction`
- Set cached instruction. When set, `.instruct()` text moves from system to user content, enabling context caching. Use for large, stable prompt sections that rarely change.

**Example:**

```python
config = LlmAgentConfig("config").static_instruct("...")
```

### Control Flow & Execution

(method-LlmAgentConfig-build)=
#### `.build() -> LlmAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LlmAgentConfig.

**Example:**

```python
config = LlmAgentConfig("config").build("...")
```

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

(method-LoopAgentConfig-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
config = LoopAgentConfig("config").describe("...")
```

(method-LoopAgentConfig-sub_agent)=
#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
config = LoopAgentConfig("config").sub_agent("...")
```

### Configuration

(method-LoopAgentConfig-after_agent_callback)=
#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `after_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = LoopAgentConfig("config").after_agent_callback(my_callback_fn)
```

(method-LoopAgentConfig-before_agent_callback)=
#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `before_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = LoopAgentConfig("config").before_agent_callback(my_callback_fn)
```

### Control Flow & Execution

(method-LoopAgentConfig-build)=
#### `.build() -> LoopAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LoopAgentConfig.

**Example:**

```python
config = LoopAgentConfig("config").build("...")
```

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

(method-ParallelAgentConfig-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
config = ParallelAgentConfig("config").describe("...")
```

(method-ParallelAgentConfig-sub_agent)=
#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
config = ParallelAgentConfig("config").sub_agent("...")
```

### Configuration

(method-ParallelAgentConfig-after_agent_callback)=
#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `after_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = ParallelAgentConfig("config").after_agent_callback(my_callback_fn)
```

(method-ParallelAgentConfig-before_agent_callback)=
#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `before_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = ParallelAgentConfig("config").before_agent_callback(my_callback_fn)
```

### Control Flow & Execution

(method-ParallelAgentConfig-build)=
#### `.build() -> ParallelAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ParallelAgentConfig.

**Example:**

```python
config = ParallelAgentConfig("config").build("...")
```

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

(method-RunConfig-input_audio_transcribe)=
#### `.input_audio_transcribe(value: AudioTranscriptionConfig | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `input_audio_transcription`
- Set the `input_audio_transcription` field.

**Example:**

```python
config = RunConfig("config").input_audio_transcribe("...")
```

(method-RunConfig-output_audio_transcribe)=
#### `.output_audio_transcribe(value: AudioTranscriptionConfig | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `output_audio_transcription`
- Set the `output_audio_transcription` field.

**Example:**

```python
config = RunConfig("config").output_audio_transcribe("...")
```

### Control Flow & Execution

(method-RunConfig-build)=
#### `.build() -> RunConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK RunConfig.

**Example:**

```python
config = RunConfig("config").build("...")
```

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

(method-ToolThreadPoolConfig-build)=
#### `.build() -> ToolThreadPoolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ToolThreadPoolConfig.

**Example:**

```python
config = ToolThreadPoolConfig("config").build("...")
```

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

(method-SequentialAgentConfig-describe)=
#### `.describe(value: str) -> Self` {bdg-success}`Core Configuration`

- **Maps to:** `description`
- Set agent description (metadata for transfer routing and topology display — NOT sent to the LLM as instruction). Always set this on sub-agents so the coordinator LLM can pick the right specialist.

**Example:**

```python
config = SequentialAgentConfig("config").describe("...")
```

(method-SequentialAgentConfig-sub_agent)=
#### `.sub_agent(value: AgentRefConfig) -> Self` {bdg-success}`Core Configuration`

Append to `sub_agents` (lazy — built at .build() time).

**Example:**

```python
config = SequentialAgentConfig("config").sub_agent("...")
```

### Configuration

(method-SequentialAgentConfig-after_agent_callback)=
#### `.after_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `after_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = SequentialAgentConfig("config").after_agent_callback(my_callback_fn)
```

(method-SequentialAgentConfig-before_agent_callback)=
#### `.before_agent_callback(value: CodeConfig) -> Self` {bdg-info}`Configuration`

Append to `before_agent_callbacks` (lazy — built at .build() time).

**Example:**

```python
config = SequentialAgentConfig("config").before_agent_callback(my_callback_fn)
```

### Control Flow & Execution

(method-SequentialAgentConfig-build)=
#### `.build() -> SequentialAgentConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SequentialAgentConfig.

**Example:**

```python
config = SequentialAgentConfig("config").build("...")
```

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

(method-EventsCompactionConfig-build)=
#### `.build() -> EventsCompactionConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK EventsCompactionConfig.

**Example:**

```python
config = EventsCompactionConfig("config").build("...")
```

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

(method-ResumabilityConfig-build)=
#### `.build() -> ResumabilityConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ResumabilityConfig.

**Example:**

```python
config = ResumabilityConfig("config").build("...")
```

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

(method-FeatureConfig-build)=
#### `.build() -> FeatureConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK FeatureConfig.

**Example:**

```python
config = FeatureConfig("config").build("...")
```

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

(method-AudioCacheConfig-build)=
#### `.build() -> AudioCacheConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AudioCacheConfig.

**Example:**

```python
config = AudioCacheConfig("config").build("...")
```

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

(method-SimplePromptOptimizerConfig-model_configure)=
#### `.model_configure(value: GenerateContentConfig) -> Self` {bdg-info}`Configuration`

- **Maps to:** `model_configuration`
- The configuration for the optimizer model.

**Example:**

```python
config = SimplePromptOptimizerConfig("config").model_configure("...")
```

### Control Flow & Execution

(method-SimplePromptOptimizerConfig-build)=
#### `.build() -> SimplePromptOptimizerConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SimplePromptOptimizerConfig.

**Example:**

```python
config = SimplePromptOptimizerConfig("config").build("...")
```

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

(method-BigQueryLoggerConfig-build)=
#### `.build() -> BigQueryLoggerConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigQueryLoggerConfig.

**Example:**

```python
config = BigQueryLoggerConfig("config").build("...")
```

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

(method-RetryConfig-build)=
#### `.build() -> RetryConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK RetryConfig.

**Example:**

```python
config = RetryConfig("config").build("...")
```

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

(method-GetSessionConfig-build)=
#### `.build() -> GetSessionConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK GetSessionConfig.

**Example:**

```python
config = GetSessionConfig("config").build("...")
```

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

(method-BaseGoogleCredentialsConfig-build)=
#### `.build() -> BaseGoogleCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseGoogleCredentialsConfig.

**Example:**

```python
config = BaseGoogleCredentialsConfig("config").build("...")
```

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

(method-AgentSimulatorConfig-simulation_model_configure)=
#### `.simulation_model_configure(value: GenerateContentConfig) -> Self` {bdg-info}`Configuration`

- **Maps to:** `simulation_model_configuration`
- Set the `simulation_model_configuration` field.

**Example:**

```python
config = AgentSimulatorConfig("config").simulation_model_configure("...")
```

(method-AgentSimulatorConfig-tool_simulation_config)=
#### `.tool_simulation_config(value: ToolSimulationConfig) -> Self` {bdg-info}`Configuration`

Append to `tool_simulation_configs` (lazy — built at .build() time).

**Example:**

```python
config = AgentSimulatorConfig("config").tool_simulation_config("...")
```

### Control Flow & Execution

(method-AgentSimulatorConfig-build)=
#### `.build() -> AgentSimulatorConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentSimulatorConfig.

**Example:**

```python
config = AgentSimulatorConfig("config").build("...")
```

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

(method-InjectionConfig-build)=
#### `.build() -> InjectionConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK InjectionConfig.

**Example:**

```python
config = InjectionConfig("config").build("...")
```

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

(method-ToolSimulationConfig-injection_config)=
#### `.injection_config(value: InjectionConfig) -> Self` {bdg-info}`Configuration`

Append to `injection_configs` (lazy — built at .build() time).

**Example:**

```python
config = ToolSimulationConfig("config").injection_config("...")
```

### Control Flow & Execution

(method-ToolSimulationConfig-build)=
#### `.build() -> ToolSimulationConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ToolSimulationConfig.

**Example:**

```python
config = ToolSimulationConfig("config").build("...")
```

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

(method-AgentToolConfig-skip_summarizate)=
#### `.skip_summarizate(value: bool) -> Self` {bdg-info}`Configuration`

- **Maps to:** `skip_summarization`
- Set the `skip_summarization` field.

**Example:**

```python
config = AgentToolConfig("config").skip_summarizate("...")
```

### Control Flow & Execution

(method-AgentToolConfig-build)=
#### `.build() -> AgentToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentToolConfig.

**Example:**

```python
config = AgentToolConfig("config").build("...")
```

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

(method-BigQueryCredentialsConfig-build)=
#### `.build() -> BigQueryCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigQueryCredentialsConfig.

**Example:**

```python
config = BigQueryCredentialsConfig("config").build("...")
```

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

(method-BigQueryToolConfig-locate)=
#### `.locate(value: str | None) -> Self` {bdg-info}`Configuration`

- **Maps to:** `location`
- Set the `location` field.

**Example:**

```python
config = BigQueryToolConfig("config").locate("...")
```

### Control Flow & Execution

(method-BigQueryToolConfig-build)=
#### `.build() -> BigQueryToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigQueryToolConfig.

**Example:**

```python
config = BigQueryToolConfig("config").build("...")
```

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

(method-BigtableCredentialsConfig-build)=
#### `.build() -> BigtableCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigtableCredentialsConfig.

**Example:**

```python
config = BigtableCredentialsConfig("config").build("...")
```

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

(method-DataAgentToolConfig-build)=
#### `.build() -> DataAgentToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK DataAgentToolConfig.

**Example:**

```python
config = DataAgentToolConfig("config").build("...")
```

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

(method-DataAgentCredentialsConfig-build)=
#### `.build() -> DataAgentCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK DataAgentCredentialsConfig.

**Example:**

```python
config = DataAgentCredentialsConfig("config").build("...")
```

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

(method-ExampleToolConfig-build)=
#### `.build() -> ExampleToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ExampleToolConfig.

**Example:**

```python
config = ExampleToolConfig("config").build("...")
```

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

(method-McpToolsetConfig-build)=
#### `.build() -> McpToolsetConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK McpToolsetConfig.

**Example:**

```python
config = McpToolsetConfig("config").build("...")
```

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

(method-PubSubToolConfig-build)=
#### `.build() -> PubSubToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK PubSubToolConfig.

**Example:**

```python
config = PubSubToolConfig("config").build("...")
```

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

(method-PubSubCredentialsConfig-build)=
#### `.build() -> PubSubCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK PubSubCredentialsConfig.

**Example:**

```python
config = PubSubCredentialsConfig("config").build("...")
```

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

(method-SpannerCredentialsConfig-build)=
#### `.build() -> SpannerCredentialsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SpannerCredentialsConfig.

**Example:**

```python
config = SpannerCredentialsConfig("config").build("...")
```

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

(method-BaseToolConfig-build)=
#### `.build() -> BaseToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseToolConfig.

**Example:**

```python
config = BaseToolConfig("config").build("...")
```

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

(method-ToolArgsConfig-build)=
#### `.build() -> ToolArgsConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ToolArgsConfig.

**Example:**

```python
config = ToolArgsConfig("config").build("...")
```

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

(method-ToolConfig-build)=
#### `.build() -> ToolConfig` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ToolConfig.

**Example:**

```python
config = ToolConfig("config").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.args(value)` | `ToolArgsConfig | None` |
