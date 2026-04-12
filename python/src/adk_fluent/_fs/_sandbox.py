"""SandboxedBackend — enforce a :class:`SandboxPolicy` around any backend.

The sandbox decorator intercepts every path on its way into the wrapped
backend, resolves it via the policy, and refuses the operation if it would
escape the allowed workspace. It mirrors the check semantics the harness's
workspace tools historically did inline, but applies them uniformly and
keeps the underlying backend unaware of sandboxing.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from adk_fluent._fs._backend import FsBackend, FsEntry, FsStat

if TYPE_CHECKING:
    from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["SandboxedBackend", "SandboxViolation"]


class SandboxViolation(PermissionError):
    """Raised when a tool tries to touch a path outside the sandbox."""


class SandboxedBackend:
    """A :class:`FsBackend` that enforces a :class:`SandboxPolicy`.

    Wrap any concrete backend (local, memory, remote) with this decorator
    to apply the same workspace scope + symlink-safe path validation.
    """

    def __init__(self, inner: FsBackend, sandbox: SandboxPolicy) -> None:
        self._inner = inner
        self._sandbox = sandbox

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check(self, path: str, *, write: bool) -> str:
        resolved = self._sandbox.resolve_path(path)
        if not self._sandbox.validate_path(resolved, write=write):
            raise SandboxViolation(f"Path {path!r} is outside the sandboxed workspace.")
        return resolved

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        try:
            resolved = self._check(path, write=False)
        except SandboxViolation:
            return False
        return self._inner.exists(resolved)

    def stat(self, path: str) -> FsStat:
        resolved = self._check(path, write=False)
        return self._inner.stat(resolved)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        resolved = self._check(path, write=False)
        return self._inner.read_text(resolved, encoding=encoding)

    def read_bytes(self, path: str) -> bytes:
        resolved = self._check(path, write=False)
        return self._inner.read_bytes(resolved)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_text(self, path: str, content: str, *, encoding: str = "utf-8") -> None:
        resolved = self._check(path, write=True)
        self._inner.write_text(resolved, content, encoding=encoding)

    def write_bytes(self, path: str, content: bytes) -> None:
        resolved = self._check(path, write=True)
        self._inner.write_bytes(resolved, content)

    def delete(self, path: str) -> None:
        resolved = self._check(path, write=True)
        self._inner.delete(resolved)

    def mkdir(self, path: str, *, parents: bool = True, exist_ok: bool = True) -> None:
        resolved = self._check(path, write=True)
        self._inner.mkdir(resolved, parents=parents, exist_ok=exist_ok)

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def list_dir(self, path: str) -> list[FsEntry]:
        resolved = self._check(path, write=False)
        return self._inner.list_dir(resolved)

    def iter_files(self, root: str) -> Iterator[str]:
        resolved = self._check(root, write=False)
        yield from self._inner.iter_files(resolved)

    def glob(self, pattern: str, *, root: str | None = None) -> list[str]:
        if root is not None:
            resolved = self._check(root, write=False)
        else:
            resolved = self._sandbox.workspace
        return self._inner.glob(pattern, root=resolved)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def sandbox(self) -> SandboxPolicy:
        return self._sandbox

    @property
    def inner(self) -> FsBackend:
        return self._inner
