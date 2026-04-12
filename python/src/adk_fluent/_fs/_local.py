"""LocalBackend — :class:`FsBackend` backed by the real filesystem."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from adk_fluent._fs._backend import FsEntry, FsStat

__all__ = ["LocalBackend"]


class LocalBackend:
    """Plain ``pathlib``-backed filesystem.

    The backend does **no** sandboxing. Wrap it with
    :class:`~adk_fluent._fs._sandbox.SandboxedBackend` to enforce a
    workspace scope.
    """

    def __init__(self, root: str | None = None) -> None:
        self._root = root

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        if self._root and not os.path.isabs(path):
            return Path(self._root) / path
        return Path(path)

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def stat(self, path: str) -> FsStat:
        p = self._resolve(path)
        st = p.stat()
        return FsStat(
            path=str(p),
            size=st.st_size,
            is_dir=p.is_dir(),
            is_file=p.is_file(),
            mtime=st.st_mtime,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        return self._resolve(path).read_text(encoding=encoding, errors="replace")

    def read_bytes(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_text(self, path: str, content: str, *, encoding: str = "utf-8") -> None:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)

    def write_bytes(self, path: str, content: bytes) -> None:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    def delete(self, path: str) -> None:
        p = self._resolve(path)
        if p.is_dir():
            # Only allow empty-dir removal; recursive delete belongs in a dedicated helper.
            p.rmdir()
        else:
            p.unlink()

    def mkdir(self, path: str, *, parents: bool = True, exist_ok: bool = True) -> None:
        self._resolve(path).mkdir(parents=parents, exist_ok=exist_ok)

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def list_dir(self, path: str) -> list[FsEntry]:
        p = self._resolve(path)
        entries: list[FsEntry] = []
        for child in sorted(p.iterdir()):
            entries.append(
                FsEntry(
                    name=child.name,
                    path=str(child),
                    is_dir=child.is_dir(),
                    is_file=child.is_file(),
                )
            )
        return entries

    def iter_files(self, root: str) -> Iterator[str]:
        p = self._resolve(root)
        for child in p.rglob("*"):
            if child.is_file():
                yield str(child)

    def glob(self, pattern: str, *, root: str | None = None) -> list[str]:
        base = self._resolve(root) if root is not None else (
            Path(self._root) if self._root else Path(".")
        )
        return sorted(str(p) for p in base.glob(pattern))
