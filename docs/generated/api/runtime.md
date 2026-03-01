# Module: `runtime`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [App](builder-App) | Represents an LLM-backed agentic application. |
| [InMemoryRunner](builder-InMemoryRunner) | An in-memory Runner for testing and development. |
| [Runner](builder-Runner) | The Runner class is used to run agents. |

(builder-App)=
## App

> Fluent builder for `google.adk.apps.app.App`

Represents an LLM-backed agentic application.

**Quick start:**

```python
from adk_fluent import App

result = (
    App("name_value", "root_agent_value")
    .plugin(...)
    .build()
)
```

### Constructor

```python
App(name: str, root_agent: BaseAgent)
```

| Argument | Type |
|----------|------|
| `name` | {py:class}`str` |
| `root_agent` | `BaseAgent` |

### Configuration

#### `.plugin(value: BasePlugin) -> Self` {bdg-info}`Configuration`

Append to `plugins` (lazy — built at .build() time).

**Example:**

```python
app = App("app").plugin("...")
```

### Control Flow & Execution

#### `.build() -> App` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK App.

**Example:**

```python
app = App("app").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.plugins(value)` | `list[BasePlugin]` |
| `.events_compaction_config(value)` | `EventsCompactionConfig | None` |
| `.context_cache_config(value)` | `ContextCacheConfig | None` |
| `.resumability_config(value)` | `ResumabilityConfig | None` |

---

(builder-InMemoryRunner)=
## InMemoryRunner

> Fluent builder for `google.adk.runners.InMemoryRunner`

An in-memory Runner for testing and development.

**Quick start:**

```python
from adk_fluent import InMemoryRunner

result = (
    InMemoryRunner()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> InMemoryRunner` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK InMemoryRunner.

**Example:**

```python
inmemoryrunner = InMemoryRunner("inmemoryrunner").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent(value)` | `BaseAgent | None` |
| `.app_name(value)` | `str | None` |
| `.plugins(value)` | `list[BasePlugin] | None` |
| `.app(value)` | `App | None` |
| `.plugin_close_timeout(value)` | {py:class}`float` |

---

(builder-Runner)=
## Runner

> Fluent builder for `google.adk.runners.Runner`

The Runner class is used to run agents.

**Quick start:**

```python
from adk_fluent import Runner

result = (
    Runner("session_service_value")
    .build()
)
```

### Constructor

```python
Runner(session_service: BaseSessionService)
```

| Argument | Type |
|----------|------|
| `session_service` | `BaseSessionService` |

### Control Flow & Execution

#### `.build() -> Runner` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK Runner.

**Example:**

```python
runner = Runner("runner").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.app(value)` | `App | None` |
| `.app_name(value)` | `str | None` |
| `.agent(value)` | `BaseAgent | None` |
| `.plugins(value)` | `list[BasePlugin] | None` |
| `.artifact_service(value)` | `BaseArtifactService | None` |
| `.memory_service(value)` | `BaseMemoryService | None` |
| `.credential_service(value)` | `BaseCredentialService | None` |
| `.plugin_close_timeout(value)` | {py:class}`float` |
| `.auto_create_session(value)` | {py:class}`bool` |
