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

#### `.build() -> BaseArtifactService`

Resolve into a native ADK BaseArtifactService.

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

#### `.build() -> FileArtifactService`

Resolve into a native ADK FileArtifactService.

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

| Argument      | Type  |
| ------------- | ----- |
| `bucket_name` | `str` |
| `kwargs`      | `Any` |

### Control Flow & Execution

#### `.build() -> GcsArtifactService`

Resolve into a native ADK GcsArtifactService.

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

#### `.build() -> InMemoryArtifactService`

Resolve into a native ADK InMemoryArtifactService.

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

#### `.build() -> PerAgentDatabaseSessionService`

Resolve into a native ADK PerAgentDatabaseSessionService.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                     | Type                          |
| ------------------------- | ----------------------------- |
| `.app_name_to_dir(value)` | `Optional[Mapping[str, str]]` |

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

#### `.build() -> BaseMemoryService`

Resolve into a native ADK BaseMemoryService.

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

#### `.build() -> InMemoryMemoryService`

Resolve into a native ADK InMemoryMemoryService.

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

#### `.build() -> VertexAiMemoryBankService`

Resolve into a native ADK VertexAiMemoryBankService.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type            |
| ------------------------------ | --------------- |
| `.project(value)`              | `Optional[str]` |
| `.location(value)`             | `Optional[str]` |
| `.agent_engine_id(value)`      | `Optional[str]` |
| `.express_mode_api_key(value)` | `Optional[str]` |

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

#### `.build() -> VertexAiRagMemoryService`

Resolve into a native ADK VertexAiRagMemoryService.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                               | Type            |
| ----------------------------------- | --------------- |
| `.rag_corpus(value)`                | `Optional[str]` |
| `.similarity_top_k(value)`          | `Optional[int]` |
| `.vector_distance_threshold(value)` | `float`         |

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

#### `.build() -> BaseSessionService`

Resolve into a native ADK BaseSessionService.

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

| Argument | Type  |
| -------- | ----- |
| `db_url` | `str` |
| `kwargs` | `Any` |

### Control Flow & Execution

#### `.build() -> DatabaseSessionService`

Resolve into a native ADK DatabaseSessionService.

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

#### `.build() -> InMemorySessionService`

Resolve into a native ADK InMemorySessionService.

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

| Argument  | Type  |
| --------- | ----- |
| `db_path` | `str` |

### Control Flow & Execution

#### `.build() -> SqliteSessionService`

Resolve into a native ADK SqliteSessionService.

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

#### `.build() -> VertexAiSessionService`

Resolve into a native ADK VertexAiSessionService.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type            |
| ------------------------------ | --------------- |
| `.project(value)`              | `Optional[str]` |
| `.location(value)`             | `Optional[str]` |
| `.agent_engine_id(value)`      | `Optional[str]` |
| `.express_mode_api_key(value)` | `Optional[str]` |

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

#### `.build() -> ForwardingArtifactService`

Resolve into a native ADK ForwardingArtifactService.
