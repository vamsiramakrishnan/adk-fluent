"""FsBackend protocol — the surface every filesystem backend must implement.

Only the operations the harness's workspace tools actually need are in the
protocol. A backend that wants to add extras (random-access seeks, chunked
reads, partial writes) is free to expose them through subclass-specific
methods, but the tools themselves never reach for anything outside this
protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol, runtime_checkable

__all__ = ["FsBackend", "FsEntry", "FsStat"]


@dataclass(frozen=True, slots=True)
class FsStat:
    """Minimal stat result returned by :meth:`FsBackend.stat`."""

    path: str
    size: int
    is_dir: bool
    is_file: bool
    mtime: float


@dataclass(frozen=True, slots=True)
class FsEntry:
    """One entry produced by :meth:`FsBackend.list_dir`."""

    name: str
    path: str
    is_dir: bool
    is_file: bool


@runtime_checkable
class FsBackend(Protocol):
    """The subset of filesystem operations workspace tools need."""

    # ------------------------------------------------------------------
    # Existence / metadata
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        """Return True if ``path`` exists under this backend."""

    def stat(self, path: str) -> FsStat:
        """Return an :class:`FsStat` for ``path``. Raise FileNotFoundError if missing."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        """Read ``path`` as text. Raise FileNotFoundError if missing."""

    def read_bytes(self, path: str) -> bytes:
        """Read ``path`` as bytes. Raise FileNotFoundError if missing."""

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_text(self, path: str, content: str, *, encoding: str = "utf-8") -> None:
        """Write text to ``path``, creating parent directories."""

    def write_bytes(self, path: str, content: bytes) -> None:
        """Write bytes to ``path``, creating parent directories."""

    def delete(self, path: str) -> None:
        """Delete ``path``. Raise FileNotFoundError if missing."""

    def mkdir(self, path: str, *, parents: bool = True, exist_ok: bool = True) -> None:
        """Create a directory at ``path``."""

    # ------------------------------------------------------------------
    # Directory traversal
    # ------------------------------------------------------------------

    def list_dir(self, path: str) -> list[FsEntry]:
        """List the contents of ``path`` one level deep."""

    def iter_files(self, root: str) -> Iterator[str]:
        """Yield every file path under ``root`` recursively."""

    def glob(self, pattern: str, *, root: str | None = None) -> list[str]:
        """Return paths under ``root`` matching the glob ``pattern``."""
