"""adk_fluent._fs — pluggable filesystem backend for workspace tools.

The harness's workspace tools (``read_file``, ``edit_file``, ``write_file``,
``list_dir``, ``glob_search``, ``grep_search``) historically called
:mod:`pathlib` directly. That made them impossible to unit-test without a
real disk and impossible to retarget at in-memory or remote storage.

This package factors the filesystem behind a small :class:`FsBackend`
protocol and ships three implementations:

- :class:`LocalBackend` — real on-disk I/O via :mod:`pathlib`.
- :class:`MemoryBackend` — dict-backed fake useful for tests and for
  ephemeral scratch workspaces that should never touch the disk.
- :class:`SandboxedBackend` — decorator that wraps any backend with a
  :class:`~adk_fluent._harness._sandbox.SandboxPolicy` and refuses
  operations that escape the allowed paths.

The backend is injected into :func:`workspace_tools` as a keyword
argument; when omitted the tools fall back to a
``SandboxedBackend(LocalBackend())`` so existing call sites keep working.

Design rules:

1. **Backends do not know about sandboxing.** The sandbox decorator is
   layered on top so the same policy logic applies no matter which
   backend is underneath.
2. **Backends are synchronous.** ADK tools are invoked in the sync path;
   an async backend can still be wrapped via ``asyncio.run`` internally,
   but the protocol itself stays sync to keep the call sites simple.
3. **Paths are always strings.** The backend normalises to whatever
   internal representation it prefers. This keeps MemoryBackend free of
   ``Path`` objects and lets remote backends use URIs.
"""

from adk_fluent._fs._backend import FsBackend, FsEntry, FsStat
from adk_fluent._fs._local import LocalBackend
from adk_fluent._fs._memory import MemoryBackend
from adk_fluent._fs._sandbox import SandboxedBackend, SandboxViolation
from adk_fluent._fs._tools import workspace_tools_with_backend

__all__ = [
    "FsBackend",
    "FsEntry",
    "FsStat",
    "LocalBackend",
    "MemoryBackend",
    "SandboxedBackend",
    "SandboxViolation",
    "workspace_tools_with_backend",
]
