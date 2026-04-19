# Module: `plugin`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [RecordingsPlugin](builder-RecordingsPlugin) | Plugin for recording ADK agent interactions. |
| [ReplayPlugin](builder-ReplayPlugin) | Plugin for replaying ADK agent interactions from recordings. |
| [BasePlugin](builder-BasePlugin) | Base class for creating plugins. |
| [BigQueryAgentAnalyticsPlugin](builder-BigQueryAgentAnalyticsPlugin) | BigQuery Agent Analytics Plugin (v2. |
| [ContextFilterPlugin](builder-ContextFilterPlugin) | A plugin that filters the LLM context to reduce its size. |
| [DebugLoggingPlugin](builder-DebugLoggingPlugin) | A plugin that captures complete debug information to a file. |
| [GlobalInstructionPlugin](builder-GlobalInstructionPlugin) | Plugin that provides global instructions functionality at the App level. |
| [LoggingPlugin](builder-LoggingPlugin) | A plugin that logs important information at each callback point. |
| [MultimodalToolResultsPlugin](builder-MultimodalToolResultsPlugin) | A plugin that modifies function tool responses to support returning list of parts directly. |
| [ReflectAndRetryToolPlugin](builder-ReflectAndRetryToolPlugin) | Provides self-healing, concurrent-safe error recovery for tool failures. |
| [SaveFilesAsArtifactsPlugin](builder-SaveFilesAsArtifactsPlugin) | A plugin that saves files embedded in user messages as artifacts. |
| [AgentSimulatorPlugin](builder-AgentSimulatorPlugin) | ADK Plugin for AgentSimulator. |

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

(method-RecordingsPlugin-build)=
#### `.build() -> RecordingsPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK RecordingsPlugin.

**Example:**

```python
recordingsplugin = RecordingsPlugin("recordingsplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | {py:class}`str` |

---

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

(method-ReplayPlugin-build)=
#### `.build() -> ReplayPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ReplayPlugin.

**Example:**

```python
replayplugin = ReplayPlugin("replayplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | {py:class}`str` |

---

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

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |

### Control Flow & Execution

(method-BasePlugin-build)=
#### `.build() -> BasePlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BasePlugin.

**Example:**

```python
baseplugin = BasePlugin("baseplugin").build("...")
```

---

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

| Argument | Type |
|----------|------|
| `project_id` | {py:class}`str` |
| `dataset_id` | {py:class}`str` |
| `kwargs` | `Any` |

### Control Flow & Execution

(method-BigQueryAgentAnalyticsPlugin-build)=
#### `.build() -> BigQueryAgentAnalyticsPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BigQueryAgentAnalyticsPlugin.

**Example:**

```python
bigqueryagentanalyticsplugin = BigQueryAgentAnalyticsPlugin("bigqueryagentanalyticsplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.table_id(value)` | `str | None` |
| `.config(value)` | `BigQueryLoggerConfig | None` |
| `.location(value)` | {py:class}`str` |

---

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

(method-ContextFilterPlugin-build)=
#### `.build() -> ContextFilterPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ContextFilterPlugin.

**Example:**

```python
contextfilterplugin = ContextFilterPlugin("contextfilterplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.num_invocations_to_keep(value)` | `int | None` |
| `.custom_filter(value)` | `Callable[[list[types.Content]], list[types.Content]] | None` |
| `.name(value)` | {py:class}`str` |

---

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

(method-DebugLoggingPlugin-build)=
#### `.build() -> DebugLoggingPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK DebugLoggingPlugin.

**Example:**

```python
debugloggingplugin = DebugLoggingPlugin("debugloggingplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | {py:class}`str` |
| `.output_path(value)` | {py:class}`str` |
| `.include_session_state(value)` | {py:class}`bool` |
| `.include_system_instruction(value)` | {py:class}`bool` |

---

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

(method-GlobalInstructionPlugin-build)=
#### `.build() -> GlobalInstructionPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK GlobalInstructionPlugin.

**Example:**

```python
globalinstructionplugin = GlobalInstructionPlugin("globalinstructionplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.global_instruction(value)` | `str | InstructionProvider` |
| `.name(value)` | {py:class}`str` |

---

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

(method-LoggingPlugin-build)=
#### `.build() -> LoggingPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK LoggingPlugin.

**Example:**

```python
loggingplugin = LoggingPlugin("loggingplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | {py:class}`str` |

---

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

(method-MultimodalToolResultsPlugin-build)=
#### `.build() -> MultimodalToolResultsPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK MultimodalToolResultsPlugin.

**Example:**

```python
multimodaltoolresultsplugin = MultimodalToolResultsPlugin("multimodaltoolresultsplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | {py:class}`str` |

---

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

(method-ReflectAndRetryToolPlugin-build)=
#### `.build() -> ReflectAndRetryToolPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ReflectAndRetryToolPlugin.

**Example:**

```python
reflectandretrytoolplugin = ReflectAndRetryToolPlugin("reflectandretrytoolplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | {py:class}`str` |
| `.max_retries(value)` | {py:class}`int` |
| `.throw_exception_if_retry_exceeded(value)` | {py:class}`bool` |
| `.tracking_scope(value)` | `TrackingScope` |

---

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

(method-SaveFilesAsArtifactsPlugin-build)=
#### `.build() -> SaveFilesAsArtifactsPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SaveFilesAsArtifactsPlugin.

**Example:**

```python
savefilesasartifactsplugin = SaveFilesAsArtifactsPlugin("savefilesasartifactsplugin").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | {py:class}`str` |

---

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

| Argument | Type |
|----------|------|
| `simulator_engine` | `AgentSimulatorEngine` |

### Control Flow & Execution

(method-AgentSimulatorPlugin-build)=
#### `.build() -> AgentSimulatorPlugin` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentSimulatorPlugin.

**Example:**

```python
agentsimulatorplugin = AgentSimulatorPlugin("agentsimulatorplugin").build("...")
```
