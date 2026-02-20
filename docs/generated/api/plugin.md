# Module: `plugin`

## Builders in this module

| Builder                                                              | Description                                                                                 |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| [RecordingsPlugin](builder-RecordingsPlugin)                         | Plugin for recording ADK agent interactions.                                                |
| [ReplayPlugin](builder-ReplayPlugin)                                 | Plugin for replaying ADK agent interactions from recordings.                                |
| [BasePlugin](builder-BasePlugin)                                     | Base class for creating plugins.                                                            |
| [BigQueryAgentAnalyticsPlugin](builder-BigQueryAgentAnalyticsPlugin) | BigQuery Agent Analytics Plugin (v2.                                                        |
| [ContextFilterPlugin](builder-ContextFilterPlugin)                   | A plugin that filters the LLM context to reduce its size.                                   |
| [DebugLoggingPlugin](builder-DebugLoggingPlugin)                     | A plugin that captures complete debug information to a file.                                |
| [GlobalInstructionPlugin](builder-GlobalInstructionPlugin)           | Plugin that provides global instructions functionality at the App level.                    |
| [LoggingPlugin](builder-LoggingPlugin)                               | A plugin that logs important information at each callback point.                            |
| [MultimodalToolResultsPlugin](builder-MultimodalToolResultsPlugin)   | A plugin that modifies function tool responses to support returning list of parts directly. |
| [ReflectAndRetryToolPlugin](builder-ReflectAndRetryToolPlugin)       | Provides self-healing, concurrent-safe error recovery for tool failures.                    |
| [SaveFilesAsArtifactsPlugin](builder-SaveFilesAsArtifactsPlugin)     | A plugin that saves files embedded in user messages as artifacts.                           |
| [AgentSimulatorPlugin](builder-AgentSimulatorPlugin)                 | ADK Plugin for AgentSimulator.                                                              |

(builder-RecordingsPlugin)=

## RecordingsPlugin

> Fluent builder for `google.adk.cli.plugins.recordings_plugin.RecordingsPlugin`

Plugin for recording ADK agent interactions.

**Quick start:**

```python
from adk_fluent import RecordingsPlugin

result = (
    RecordingsPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> RecordingsPlugin`

Resolve into a native ADK RecordingsPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field          | Type  |
| -------------- | ----- |
| `.name(value)` | `str` |

______________________________________________________________________

(builder-ReplayPlugin)=

## ReplayPlugin

> Fluent builder for `google.adk.cli.plugins.replay_plugin.ReplayPlugin`

Plugin for replaying ADK agent interactions from recordings.

**Quick start:**

```python
from adk_fluent import ReplayPlugin

result = (
    ReplayPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> ReplayPlugin`

Resolve into a native ADK ReplayPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field          | Type  |
| -------------- | ----- |
| `.name(value)` | `str` |

______________________________________________________________________

(builder-BasePlugin)=

## BasePlugin

> Fluent builder for `google.adk.plugins.base_plugin.BasePlugin`

Base class for creating plugins.

**Quick start:**

```python
from adk_fluent import BasePlugin

result = (
    BasePlugin("name_value")
    .build()
)
```

### Constructor

```python
BasePlugin(name: str)
```

| Argument | Type  |
| -------- | ----- |
| `name`   | `str` |

### Control Flow & Execution

#### `.build() -> BasePlugin`

Resolve into a native ADK BasePlugin.

______________________________________________________________________

(builder-BigQueryAgentAnalyticsPlugin)=

## BigQueryAgentAnalyticsPlugin

> Fluent builder for `google.adk.plugins.bigquery_agent_analytics_plugin.BigQueryAgentAnalyticsPlugin`

BigQuery Agent Analytics Plugin (v2.0 using Write API).

**Quick start:**

```python
from adk_fluent import BigQueryAgentAnalyticsPlugin

result = (
    BigQueryAgentAnalyticsPlugin("project_id_value", "dataset_id_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
BigQueryAgentAnalyticsPlugin(project_id: str, dataset_id: str, kwargs: Any)
```

| Argument     | Type  |
| ------------ | ----- |
| `project_id` | `str` |
| `dataset_id` | `str` |
| `kwargs`     | `Any` |

### Control Flow & Execution

#### `.build() -> BigQueryAgentAnalyticsPlugin`

Resolve into a native ADK BigQueryAgentAnalyticsPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field              | Type                             |
| ------------------ | -------------------------------- |
| `.table_id(value)` | `Optional[str]`                  |
| `.config(value)`   | `Optional[BigQueryLoggerConfig]` |
| `.location(value)` | `str`                            |

______________________________________________________________________

(builder-ContextFilterPlugin)=

## ContextFilterPlugin

> Fluent builder for `google.adk.plugins.context_filter_plugin.ContextFilterPlugin`

A plugin that filters the LLM context to reduce its size.

**Quick start:**

```python
from adk_fluent import ContextFilterPlugin

result = (
    ContextFilterPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> ContextFilterPlugin`

Resolve into a native ADK ContextFilterPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                             | Type                                                             |
| --------------------------------- | ---------------------------------------------------------------- |
| `.num_invocations_to_keep(value)` | `Optional[int]`                                                  |
| `.custom_filter(value)`           | `Optional[Callable[[list[types.Content]], list[types.Content]]]` |
| `.name(value)`                    | `str`                                                            |

______________________________________________________________________

(builder-DebugLoggingPlugin)=

## DebugLoggingPlugin

> Fluent builder for `google.adk.plugins.debug_logging_plugin.DebugLoggingPlugin`

A plugin that captures complete debug information to a file.

**Quick start:**

```python
from adk_fluent import DebugLoggingPlugin

result = (
    DebugLoggingPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> DebugLoggingPlugin`

Resolve into a native ADK DebugLoggingPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                | Type   |
| ------------------------------------ | ------ |
| `.name(value)`                       | `str`  |
| `.output_path(value)`                | `str`  |
| `.include_session_state(value)`      | `bool` |
| `.include_system_instruction(value)` | `bool` |

______________________________________________________________________

(builder-GlobalInstructionPlugin)=

## GlobalInstructionPlugin

> Fluent builder for `google.adk.plugins.global_instruction_plugin.GlobalInstructionPlugin`

Plugin that provides global instructions functionality at the App level.

**Quick start:**

```python
from adk_fluent import GlobalInstructionPlugin

result = (
    GlobalInstructionPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> GlobalInstructionPlugin`

Resolve into a native ADK GlobalInstructionPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                        | Type                              |
| ---------------------------- | --------------------------------- |
| `.global_instruction(value)` | `Union[str, InstructionProvider]` |
| `.name(value)`               | `str`                             |

______________________________________________________________________

(builder-LoggingPlugin)=

## LoggingPlugin

> Fluent builder for `google.adk.plugins.logging_plugin.LoggingPlugin`

A plugin that logs important information at each callback point.

**Quick start:**

```python
from adk_fluent import LoggingPlugin

result = (
    LoggingPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> LoggingPlugin`

Resolve into a native ADK LoggingPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field          | Type  |
| -------------- | ----- |
| `.name(value)` | `str` |

______________________________________________________________________

(builder-MultimodalToolResultsPlugin)=

## MultimodalToolResultsPlugin

> Fluent builder for `google.adk.plugins.multimodal_tool_results_plugin.MultimodalToolResultsPlugin`

A plugin that modifies function tool responses to support returning list of parts directly.

**Quick start:**

```python
from adk_fluent import MultimodalToolResultsPlugin

result = (
    MultimodalToolResultsPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> MultimodalToolResultsPlugin`

Resolve into a native ADK MultimodalToolResultsPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field          | Type  |
| -------------- | ----- |
| `.name(value)` | `str` |

______________________________________________________________________

(builder-ReflectAndRetryToolPlugin)=

## ReflectAndRetryToolPlugin

> Fluent builder for `google.adk.plugins.reflect_retry_tool_plugin.ReflectAndRetryToolPlugin`

Provides self-healing, concurrent-safe error recovery for tool failures.

**Quick start:**

```python
from adk_fluent import ReflectAndRetryToolPlugin

result = (
    ReflectAndRetryToolPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> ReflectAndRetryToolPlugin`

Resolve into a native ADK ReflectAndRetryToolPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                                       | Type            |
| ------------------------------------------- | --------------- |
| `.name(value)`                              | `str`           |
| `.max_retries(value)`                       | `int`           |
| `.throw_exception_if_retry_exceeded(value)` | `bool`          |
| `.tracking_scope(value)`                    | `TrackingScope` |

______________________________________________________________________

(builder-SaveFilesAsArtifactsPlugin)=

## SaveFilesAsArtifactsPlugin

> Fluent builder for `google.adk.plugins.save_files_as_artifacts_plugin.SaveFilesAsArtifactsPlugin`

A plugin that saves files embedded in user messages as artifacts.

**Quick start:**

```python
from adk_fluent import SaveFilesAsArtifactsPlugin

result = (
    SaveFilesAsArtifactsPlugin()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> SaveFilesAsArtifactsPlugin`

Resolve into a native ADK SaveFilesAsArtifactsPlugin.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field          | Type  |
| -------------- | ----- |
| `.name(value)` | `str` |

______________________________________________________________________

(builder-AgentSimulatorPlugin)=

## AgentSimulatorPlugin

> Fluent builder for `google.adk.tools.agent_simulator.agent_simulator_plugin.AgentSimulatorPlugin`

ADK Plugin for AgentSimulator.

**Quick start:**

```python
from adk_fluent import AgentSimulatorPlugin

result = (
    AgentSimulatorPlugin("simulator_engine_value")
    .build()
)
```

### Constructor

```python
AgentSimulatorPlugin(simulator_engine: AgentSimulatorEngine)
```

| Argument           | Type                   |
| ------------------ | ---------------------- |
| `simulator_engine` | `AgentSimulatorEngine` |

### Control Flow & Execution

#### `.build() -> AgentSimulatorPlugin`

Resolve into a native ADK AgentSimulatorPlugin.
