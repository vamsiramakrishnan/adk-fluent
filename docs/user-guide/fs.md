# Virtual filesystem -- pluggable backends for workspace tools

The harness's workspace tools (`read_file`, `edit_file`, `write_file`,
`list_dir`, `glob_search`, `grep_search`) used to call `pathlib`
directly. That made them impossible to unit-test without a real disk
and impossible to retarget at in-memory or remote storage.

`adk_fluent._fs` factors the filesystem behind a small `FsBackend`
Protocol. Every workspace tool now routes through the backend, so the
same tool code runs against real disk, an in-memory fake, or a
sandbox-decorated wrapper of either.

:::{admonition} Why a separate namespace?
:class: tip

`_fs` is deliberately **unaware of sandboxing, auth, or workspace
policy**. The sandbox is a *decorator* layered on top. This keeps the
concrete backends trivial to test, and it means the same policy logic
applies no matter which backend sits underneath -- local, memory, or
a future remote/S3 backend.
:::

## The three backends

| Backend | Role |
| --- | --- |
| `LocalBackend` | Real on-disk I/O via `pathlib` / Node `fs`. The default. |
| `MemoryBackend` | Dict-backed fake. POSIX semantics regardless of host OS. Ideal for tests and ephemeral scratch workspaces that should never touch disk. |
| `SandboxedBackend` | Decorator that wraps any backend with a `SandboxPolicy` and refuses operations that would escape the allowed paths. |

All three satisfy the same `FsBackend` Protocol, so tools swap
cleanly between them.

## The `FsBackend` protocol

```python
from adk_fluent import FsBackend, FsEntry, FsStat

class FsBackend(Protocol):
    # metadata
    def exists(self, path: str) -> bool: ...
    def stat(self, path: str) -> FsStat: ...
    # read
    def read_text(self, path: str, *, encoding: str = "utf-8") -> str: ...
    def read_bytes(self, path: str) -> bytes: ...
    # write
    def write_text(self, path: str, content: str, *, encoding: str = "utf-8") -> None: ...
    def write_bytes(self, path: str, content: bytes) -> None: ...
    def delete(self, path: str) -> None: ...
    def mkdir(self, path: str, *, parents: bool = True, exist_ok: bool = True) -> None: ...
    # traversal
    def list_dir(self, path: str) -> list[FsEntry]: ...
    def iter_files(self, root: str) -> Iterator[str]: ...
    def glob(self, pattern: str, *, root: str | None = None) -> list[str]: ...
```

`FsStat` and `FsEntry` are frozen dataclasses (`path`, `size`,
`is_dir`, `is_file`, `mtime` for `FsStat`; `name`, `path`, `is_dir`,
`is_file` for `FsEntry`). Backends are **synchronous** by design --
ADK tools are invoked in the sync path, and any async backend can
still be wrapped via `asyncio.run` internally without polluting the
protocol surface.

## Quick start

### In-memory workspace for tests

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, MemoryBackend, workspace_tools_with_backend

backend = MemoryBackend({
    "/ws/README.md": "# hello",
    "/ws/src/main.py": "print('hi')\n",
})

agent = (
    Agent("coder", "gemini-2.5-flash")
    .instruct("Edit files in /ws.")
    .tools(workspace_tools_with_backend(backend))
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, MemoryBackend } from "adk-fluent-ts";

const backend = new MemoryBackend({
  "/ws/README.md": "# hello",
  "/ws/src/main.ts": "console.log('hi')\n",
});

// workspace tool builders live on H.workspace(...) in TS; pass the
// backend through the workspace factory.
```
:::
::::

Every operation on the agent's tools goes through the dict-backed
fake. No temp directories, no cleanup, no cross-test bleed.

### Sandbox a real disk

```python
from adk_fluent import H, LocalBackend, SandboxedBackend

policy  = H.workspace_only("/project")
backend = SandboxedBackend(LocalBackend(), policy)

# Any tool built from `backend` can only touch /project.
# Attempts to escape raise SandboxViolation, which the tool shims
# translate into "Error: path '...' is outside the allowed workspace."
```

`SandboxedBackend` is a pure decorator: it resolves every path
through the policy, validates it (write-enabled or read-only), and
forwards to the inner backend on success. The inner backend never
learns that sandboxing happened.

### Compose: in-memory + sandboxed

```python
from adk_fluent import MemoryBackend, SandboxedBackend, H

policy  = H.workspace_only("/tmp/scratch")
backend = SandboxedBackend(MemoryBackend(), policy)
# Ephemeral, sandbox-safe workspace with zero disk I/O.
```

Useful for property-based testing and reproducible CI runs --
the fake is clean per test, and the sandbox policy stops tools
from accidentally assuming host-OS paths.

## The sandbox decorator

`SandboxedBackend` is the workspace-safety half of the `H` namespace.
Pair it with any `SandboxPolicy` (workspace-only, read-only, explicit
allow-list) from the harness. Violations raise `SandboxViolation`
(a subclass of `PermissionError`), which the workspace tool shims
catch and translate into user-facing error strings:

```
Error: path '/etc/passwd' is outside the allowed workspace.
```

The tool's public surface therefore stays the same whether you're
pointed at a local disk, an in-memory fake, or a sandboxed decorator.

## Building a custom backend

Anything that satisfies the Protocol works. A remote S3-backed
backend might look like:

```python
from adk_fluent import FsBackend, FsStat, FsEntry

class S3Backend:
    def __init__(self, bucket: str, client): ...

    def exists(self, path: str) -> bool:
        return self._client.head_object(Bucket=self._bucket, Key=path).ok

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        obj = self._client.get_object(Bucket=self._bucket, Key=path)
        return obj["Body"].read().decode(encoding)

    # ... implement the rest of FsBackend ...

# Protocol is @runtime_checkable so isinstance works:
from adk_fluent import FsBackend
assert isinstance(S3Backend("bucket", client), FsBackend)
```

The harness never reaches for anything outside the `FsBackend`
surface, so any custom backend plugs straight in.

## When to reach for what

| Goal | Reach for |
| --- | --- |
| Default production use | `LocalBackend` wrapped in `SandboxedBackend` (the default when no backend is passed) |
| Unit test a workspace tool | `MemoryBackend({...})` seeded with fixtures |
| CI run with zero disk I/O | `SandboxedBackend(MemoryBackend(), workspace_only("/tmp/x"))` |
| Remote / cloud-backed workspace | Implement `FsBackend`, compose with `SandboxedBackend` |
| Read-only agent | `workspace_tools_with_backend(backend, read_only=True)` |

See also [harness](harness.md) for the wider `H` namespace and
[permissions](permissions.md) for how tool-level permission policies
combine with sandbox enforcement.
