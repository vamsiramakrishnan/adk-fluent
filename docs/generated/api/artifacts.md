# Module: artifacts

> `from adk_fluent import A`

Artifact operations — bridge between state and artifact service.

## Quick Reference

| Method                                                                        | Returns                  | Description                                         |
| ----------------------------------------------------------------------------- | ------------------------ | --------------------------------------------------- |
| `A.publish(filename, from_key, mime=None, metadata=None, scope='session')`    | `ATransform`             | Publish state content to artifact service           |
| `A.snapshot(filename, into_key, version=None, decode=False, scope='session')` | `ATransform`             | Snapshot artifact content into state                |
| `A.save(filename, content, mime=None, metadata=None, scope='session')`        | `ATransform`             | Save literal content to artifact service.           |
| `A.load(filename, scope='session')`                                           | `ATransform`             | Load artifact for pipeline composition.             |
| `A.list(into_key)`                                                            | `ATransform`             | List artifact filenames into state.                 |
| `A.version(filename, into_key)`                                               | `ATransform`             | Get artifact version metadata into state.           |
| `A.delete(filename)`                                                          | `ATransform`             | Delete all versions of an artifact.                 |
| `A.as_json(key)`                                                              | `STransform`             | Parse JSON string in state[key] to dict/list        |
| `A.as_csv(key, columns=None)`                                                 | `STransform`             | Parse CSV string in state[key] to list[dict]        |
| `A.as_text(key, encoding='utf-8')`                                            | `STransform`             | Ensure state[key] is a decoded string.              |
| `A.from_json(key, indent=None)`                                               | `STransform`             | Serialize state[key] dict/list to JSON string       |
| `A.from_csv(key)`                                                             | `STransform`             | Serialize state[key] list[dict] to CSV string       |
| `A.from_markdown(key)`                                                        | `STransform`             | Convert Markdown state[key] to HTML string          |
| `A.when(predicate, transform)`                                                | `ATransform`             | Conditional artifact operation.                     |
| `A.for_llm(filename, version=None, scope='session')`                          | `CTransform`             | Load artifact directly into LLM context.            |
| `A.publish_many(*pairs, mime=None, scope='session')`                          | `tuple[ATransform, ...]` | Batch publish: multiple (filename, from_key) pairs  |
| `A.snapshot_many(*pairs, scope='session')`                                    | `tuple[ATransform, ...]` | Batch snapshot: multiple (filename, into_key) pairs |

## Methods

### `A.publish(filename: str, *, from_key: str, mime: str | None = None, metadata: dict[str, Any] | None = None, scope: "Literal[session, user]" = session) -> ATransform`

Publish state content to artifact service.

STATE BRIDGE: reads state[from_key], copies to versioned artifact.

**Parameters:**

- `filename` (*str*)
- `from_key` (*str*)
- `mime` (*str | None*) — default: `None`
- `metadata` (*dict[str, Any] | None*) — default: `None`
- `scope` (*Literal['session', 'user']*) — default: `'session'`

### `A.snapshot(filename: str, *, into_key: str, version: int | None = None, decode: bool = False, scope: "Literal[session, user]" = session) -> ATransform`

Snapshot artifact content into state.

STATE BRIDGE: loads artifact, copies point-in-time content into state[into_key].

**Parameters:**

- `filename` (*str*)
- `into_key` (*str*)
- `version` (*int | None*) — default: `None`
- `decode` (*bool*) — default: `False`
- `scope` (*Literal['session', 'user']*) — default: `'session'`

### `A.save(filename: str, *, content: str | bytes, mime: str | None = None, metadata: dict[str, Any] | None = None, scope: "Literal[session, user]" = session) -> ATransform`

Save literal content to artifact service. No state bridge.

**Parameters:**

- `filename` (*str*)
- `content` (*str | bytes*)
- `mime` (*str | None*) — default: `None`
- `metadata` (*dict[str, Any] | None*) — default: `None`
- `scope` (*Literal['session', 'user']*) — default: `'session'`

### `A.load(filename: str, *, scope: "Literal[session, user]" = session) -> ATransform`

Load artifact for pipeline composition. No state bridge.

**Parameters:**

- `filename` (*str*)
- `scope` (*Literal['session', 'user']*) — default: `'session'`

### `A.list(*, into_key: str) -> ATransform`

List artifact filenames into state. Lightweight metadata only.

**Parameters:**

- `into_key` (*str*)

### `A.version(filename: str, *, into_key: str) -> ATransform`

Get artifact version metadata into state. Lightweight metadata only.

**Parameters:**

- `filename` (*str*)
- `into_key` (*str*)

### `A.delete(filename: str) -> ATransform`

Delete all versions of an artifact. No state involvement.

**Parameters:**

- `filename` (*str*)

### `A.as_json(key: str) -> STransform`

Parse JSON string in state[key] to dict/list.

Usage: A.snapshot("data.json", into_key="data") >> A.as_json("data")

**Parameters:**

- `key` (*str*)

### `A.as_csv(key: str, *, columns: list[str] | None = None) -> STransform`

Parse CSV string in state[key] to list[dict].

Usage: A.snapshot("data.csv", into_key="rows") >> A.as_csv("rows")

**Parameters:**

- `key` (*str*)
- `columns` (*list[str] | None*) — default: `None`

### `A.as_text(key: str, *, encoding: str = utf-8) -> STransform`

Ensure state[key] is a decoded string. Decodes bytes if needed.

Usage: A.snapshot("raw.bin", into_key="text") >> A.as_text("text")

**Parameters:**

- `key` (*str*)
- `encoding` (*str*) — default: `'utf-8'`

### `A.from_json(key: str, *, indent: int | None = None) -> STransform`

Serialize state[key] dict/list to JSON string.

Usage: A.from_json("config") >> A.publish("config.json", from_key="config")

**Parameters:**

- `key` (*str*)
- `indent` (*int | None*) — default: `None`

### `A.from_csv(key: str) -> STransform`

Serialize state[key] list[dict] to CSV string.

Usage: A.from_csv("rows") >> A.publish("results.csv", from_key="rows")

**Parameters:**

- `key` (*str*)

### `A.from_markdown(key: str) -> STransform`

Convert Markdown state[key] to HTML string.

Uses Python's built-in markdown if available, falls back to minimal conversion.
Usage: A.from_markdown("report") >> A.publish("report.html", from_key="report")

**Parameters:**

- `key` (*str*)

### `A.when(predicate: str | Callable, transform: ATransform) -> ATransform`

Conditional artifact operation. Uniform with S.when(), C.when(), etc.

**Parameters:**

- `predicate` (*str | Callable*)
- `transform` (*ATransform*)

### `A.for_llm(filename: str, *, version: int | None = None, scope: "Literal[session, user]" = session) -> CTransform`

Load artifact directly into LLM context. No state bridge.

Text artifacts are decoded and injected as instruction context.
Binary artifacts get a placeholder description with MIME and size.
Composes with C module: Agent("x").context(C.from_state("topic") + A.for_llm("report.md"))

**Parameters:**

- `filename` (*str*)
- `version` (*int | None*) — default: `None`
- `scope` (*Literal['session', 'user']*) — default: `'session'`

### `A.publish_many(*pairs: tuple[str, str], mime: str | None = None, scope: "Literal[session, user]" = session) -> tuple[ATransform, ...]`

Batch publish: multiple (filename, from_key) pairs.

Usage: Agent("w").artifacts(\*A.publish_many(("r.md", "report"), ("d.json", "data")))

**Parameters:**

- `*pairs` (*tuple[str, str]*)
- `mime` (*str | None*) — default: `None`
- `scope` (*Literal['session', 'user']*) — default: `'session'`

### `A.snapshot_many(*pairs: tuple[str, str], scope: "Literal[session, user]" = session) -> tuple[ATransform, ...]`

Batch snapshot: multiple (filename, into_key) pairs.

Usage: Agent("r").artifacts(\*A.snapshot_many(("r.md", "text"), ("d.json", "data")))

**Parameters:**

- `*pairs` (*tuple[str, str]*)
- `scope` (*Literal['session', 'user']*) — default: `'session'`

## Types

| Type         | Description                              |
| ------------ | ---------------------------------------- |
| `ATransform` | Composable artifact operation descriptor |
