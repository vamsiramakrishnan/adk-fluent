# Module: `service`

## Builders in this module

| Builder                                                                  | Description                                                                    |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| [BaseArtifactService](builder-BaseArtifactService)                       | Abstract base class for artifact services.                                     |
| [FileArtifactService](builder-FileArtifactService)                       | Stores filesystem-backed artifacts beneath a configurable root directory.      |
| [GcsArtifactService](builder-GcsArtifactService)                         | An artifact service implementation using Google Cloud Storage (GCS).           |
| [InMemoryArtifactService](builder-InMemoryArtifactService)               | An in-memory implementation of the artifact service.                           |
| [PerAgentDatabaseSessionService](builder-PerAgentDatabaseSessionService) | Routes session storage to per-agent \`.                                        |
| [BaseMemoryService](builder-BaseMemoryService)                           | Base class for memory services.                                                |
| [InMemoryMemoryService](builder-InMemoryMemoryService)                   | An in-memory memory service for prototyping purpose only.                      |
| [VertexAiMemoryBankService](builder-VertexAiMemoryBankService)           | Implementation of the BaseMemoryService using Vertex AI Memory Bank.           |
| [VertexAiRagMemoryService](builder-VertexAiRagMemoryService)             | A memory service that uses Vertex AI RAG for storage and retrieval.            |
| [BaseSessionService](builder-BaseSessionService)                         | Base class for session services.                                               |
| [DatabaseSessionService](builder-DatabaseSessionService)                 | A session service that uses a database for storage.                            |
| [InMemorySessionService](builder-InMemorySessionService)                 | An in-memory implementation of the session service.                            |
| [SqliteSessionService](builder-SqliteSessionService)                     | A session service that uses an SQLite database for storage via aiosqlite.      |
| [VertexAiSessionService](builder-VertexAiSessionService)                 | Connects to the Vertex AI Agent Engine Session Service using Agent Engine SDK. |
| [ForwardingArtifactService](builder-ForwardingArtifactService)           | Artifact service that forwards to the parent tool context.                     |

(builder-BaseArtifactService)=

## BaseArtifactService

> Fluent builder for `google.adk.artifacts.base_artifact_service.BaseArtifactService`

Abstract base class for artifact services.

**Quick start:**

```python
from adk_fluent import BaseArtifactService

result = (
    BaseArtifactService("args_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
BaseArtifactService(args: Any, kwargs: Any)
```

| Argument | Type  |
| -------- | ----- |
| `args`   | `Any` |
| `kwargs` | `Any` |

### Control Flow & Execution

#### `.build() -> BaseArtifactService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseArtifactService.

**Example:**

```python
baseartifactservice = BaseArtifactService("baseartifactservice").build("...")
```

______________________________________________________________________

(builder-FileArtifactService)=

## FileArtifactService

> Fluent builder for `google.adk.artifacts.file_artifact_service.FileArtifactService`

Stores filesystem-backed artifacts beneath a configurable root directory.

**Quick start:**

```python
from adk_fluent import FileArtifactService

result = (
    FileArtifactService("root_dir_value")
    .build()
)
```

### Constructor

```python
FileArtifactService(root_dir: Path | str)
```

| Argument   | Type   |
| ---------- | ------ |
| `root_dir` | \`Path |

### Control Flow & Execution

#### `.build() -> FileArtifactService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK FileArtifactService.

**Example:**

```python
fileartifactservice = FileArtifactService("fileartifactservice").build("...")
```

______________________________________________________________________

(builder-GcsArtifactService)=

## GcsArtifactService

> Fluent builder for `google.adk.artifacts.gcs_artifact_service.GcsArtifactService`

An artifact service implementation using Google Cloud Storage (GCS).

**Quick start:**

```python
from adk_fluent import GcsArtifactService

result = (
    GcsArtifactService("bucket_name_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
GcsArtifactService(bucket_name: str, kwargs: Any)
```

| Argument      | Type            |
| ------------- | --------------- |
| `bucket_name` | {py:class}`str` |
| `kwargs`      | `Any`           |

### Control Flow & Execution

#### `.build() -> GcsArtifactService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK GcsArtifactService.

**Example:**

```python
gcsartifactservice = GcsArtifactService("gcsartifactservice").build("...")
```

______________________________________________________________________

(builder-InMemoryArtifactService)=

## InMemoryArtifactService

> Fluent builder for `google.adk.artifacts.in_memory_artifact_service.InMemoryArtifactService`

An in-memory implementation of the artifact service.

**Quick start:**

```python
from adk_fluent import InMemoryArtifactService

result = (
    InMemoryArtifactService()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> InMemoryArtifactService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK InMemoryArtifactService.

**Example:**

```python
inmemoryartifactservice = InMemoryArtifactService("inmemoryartifactservice").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field               | Type                              |
| ------------------- | --------------------------------- |
| `.artifacts(value)` | `dict[str, list[_ArtifactEntry]]` |

______________________________________________________________________

(builder-PerAgentDatabaseSessionService)=

## PerAgentDatabaseSessionService

> Fluent builder for `google.adk.cli.utils.local_storage.PerAgentDatabaseSessionService`

Routes session storage to per-agent `.adk/session.db` files.

**Quick start:**

```python
from adk_fluent import PerAgentDatabaseSessionService

result = (
    PerAgentDatabaseSessionService("agents_root_value")
    .build()
)
```

### Constructor

```python
PerAgentDatabaseSessionService(agents_root: Path | str)
```

| Argument      | Type   |
| ------------- | ------ |
| `agents_root` | \`Path |

### Control Flow & Execution

#### `.build() -> PerAgentDatabaseSessionService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK PerAgentDatabaseSessionService.

**Example:**

```python
peragentdatabasesessionservice = PerAgentDatabaseSessionService("peragentdatabasesessionservice").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                     | Type                  |
| ------------------------- | --------------------- |
| `.app_name_to_dir(value)` | \`Mapping\[str, str\] |

______________________________________________________________________

(builder-BaseMemoryService)=

## BaseMemoryService

> Fluent builder for `google.adk.memory.base_memory_service.BaseMemoryService`

Base class for memory services.

**Quick start:**

```python
from adk_fluent import BaseMemoryService

result = (
    BaseMemoryService("args_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
BaseMemoryService(args: Any, kwargs: Any)
```

| Argument | Type  |
| -------- | ----- |
| `args`   | `Any` |
| `kwargs` | `Any` |

### Control Flow & Execution

#### `.build() -> BaseMemoryService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseMemoryService.

**Example:**

```python
basememoryservice = BaseMemoryService("basememoryservice").build("...")
```

______________________________________________________________________

(builder-InMemoryMemoryService)=

## InMemoryMemoryService

> Fluent builder for `google.adk.memory.in_memory_memory_service.InMemoryMemoryService`

An in-memory memory service for prototyping purpose only.

**Quick start:**

```python
from adk_fluent import InMemoryMemoryService

result = (
    InMemoryMemoryService()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> InMemoryMemoryService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK InMemoryMemoryService.

**Example:**

```python
inmemorymemoryservice = InMemoryMemoryService("inmemorymemoryservice").build("...")
```

______________________________________________________________________

(builder-VertexAiMemoryBankService)=

## VertexAiMemoryBankService

> Fluent builder for `google.adk.memory.vertex_ai_memory_bank_service.VertexAiMemoryBankService`

Implementation of the BaseMemoryService using Vertex AI Memory Bank.

**Quick start:**

```python
from adk_fluent import VertexAiMemoryBankService

result = (
    VertexAiMemoryBankService()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> VertexAiMemoryBankService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK VertexAiMemoryBankService.

**Example:**

```python
vertexaimemorybankservice = VertexAiMemoryBankService("vertexaimemorybankservice").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type  |
| ------------------------------ | ----- |
| `.project(value)`              | \`str |
| `.location(value)`             | \`str |
| `.agent_engine_id(value)`      | \`str |
| `.express_mode_api_key(value)` | \`str |

______________________________________________________________________

(builder-VertexAiRagMemoryService)=

## VertexAiRagMemoryService

> Fluent builder for `google.adk.memory.vertex_ai_rag_memory_service.VertexAiRagMemoryService`

A memory service that uses Vertex AI RAG for storage and retrieval.

**Quick start:**

```python
from adk_fluent import VertexAiRagMemoryService

result = (
    VertexAiRagMemoryService()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> VertexAiRagMemoryService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK VertexAiRagMemoryService.

**Example:**

```python
vertexairagmemoryservice = VertexAiRagMemoryService("vertexairagmemoryservice").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                               | Type              |
| ----------------------------------- | ----------------- |
| `.rag_corpus(value)`                | \`str             |
| `.similarity_top_k(value)`          | \`int             |
| `.vector_distance_threshold(value)` | {py:class}`float` |

______________________________________________________________________

(builder-BaseSessionService)=

## BaseSessionService

> Fluent builder for `google.adk.sessions.base_session_service.BaseSessionService`

Base class for session services.

**Quick start:**

```python
from adk_fluent import BaseSessionService

result = (
    BaseSessionService("args_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
BaseSessionService(args: Any, kwargs: Any)
```

| Argument | Type  |
| -------- | ----- |
| `args`   | `Any` |
| `kwargs` | `Any` |

### Control Flow & Execution

#### `.build() -> BaseSessionService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseSessionService.

**Example:**

```python
basesessionservice = BaseSessionService("basesessionservice").build("...")
```

______________________________________________________________________

(builder-DatabaseSessionService)=

## DatabaseSessionService

> Fluent builder for `google.adk.sessions.database_session_service.DatabaseSessionService`

A session service that uses a database for storage.

**Quick start:**

```python
from adk_fluent import DatabaseSessionService

result = (
    DatabaseSessionService("db_url_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
DatabaseSessionService(db_url: str, kwargs: Any)
```

| Argument | Type            |
| -------- | --------------- |
| `db_url` | {py:class}`str` |
| `kwargs` | `Any`           |

### Control Flow & Execution

#### `.build() -> DatabaseSessionService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK DatabaseSessionService.

**Example:**

```python
databasesessionservice = DatabaseSessionService("databasesessionservice").build("...")
```

______________________________________________________________________

(builder-InMemorySessionService)=

## InMemorySessionService

> Fluent builder for `google.adk.sessions.in_memory_session_service.InMemorySessionService`

An in-memory implementation of the session service.

**Quick start:**

```python
from adk_fluent import InMemorySessionService

result = (
    InMemorySessionService()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> InMemorySessionService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK InMemorySessionService.

**Example:**

```python
inmemorysessionservice = InMemorySessionService("inmemorysessionservice").build("...")
```

______________________________________________________________________

(builder-SqliteSessionService)=

## SqliteSessionService

> Fluent builder for `google.adk.sessions.sqlite_session_service.SqliteSessionService`

A session service that uses an SQLite database for storage via aiosqlite.

**Quick start:**

```python
from adk_fluent import SqliteSessionService

result = (
    SqliteSessionService("db_path_value")
    .build()
)
```

### Constructor

```python
SqliteSessionService(db_path: str)
```

| Argument  | Type            |
| --------- | --------------- |
| `db_path` | {py:class}`str` |

### Control Flow & Execution

#### `.build() -> SqliteSessionService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK SqliteSessionService.

**Example:**

```python
sqlitesessionservice = SqliteSessionService("sqlitesessionservice").build("...")
```

______________________________________________________________________

(builder-VertexAiSessionService)=

## VertexAiSessionService

> Fluent builder for `google.adk.sessions.vertex_ai_session_service.VertexAiSessionService`

Connects to the Vertex AI Agent Engine Session Service using Agent Engine SDK.

**Quick start:**

```python
from adk_fluent import VertexAiSessionService

result = (
    VertexAiSessionService()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> VertexAiSessionService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK VertexAiSessionService.

**Example:**

```python
vertexaisessionservice = VertexAiSessionService("vertexaisessionservice").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type  |
| ------------------------------ | ----- |
| `.project(value)`              | \`str |
| `.location(value)`             | \`str |
| `.agent_engine_id(value)`      | \`str |
| `.express_mode_api_key(value)` | \`str |

______________________________________________________________________

(builder-ForwardingArtifactService)=

## ForwardingArtifactService

> Fluent builder for `google.adk.tools._forwarding_artifact_service.ForwardingArtifactService`

Artifact service that forwards to the parent tool context.

**Quick start:**

```python
from adk_fluent import ForwardingArtifactService

result = (
    ForwardingArtifactService("tool_context_value")
    .build()
)
```

### Constructor

```python
ForwardingArtifactService(tool_context: ToolContext)
```

| Argument       | Type          |
| -------------- | ------------- |
| `tool_context` | `ToolContext` |

### Control Flow & Execution

#### `.build() -> ForwardingArtifactService` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK ForwardingArtifactService.

**Example:**

```python
forwardingartifactservice = ForwardingArtifactService("forwardingartifactservice").build("...")
```
