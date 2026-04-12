"""MemoryBackend — in-memory :class:`FsBackend` for tests and ephemeral workspaces.

The backend stores files in a dict keyed by normalised absolute path. It
supports the same API as :class:`LocalBackend` so tools swap cleanly between
the two — unit tests can point the harness at a MemoryBackend to avoid
touching the real disk at all.
"""

from __future__ import annotations

import fnmatch
import posixpath
import time
from collections.abc import Iterator

from adk_fluent._fs._backend import FsEntry, FsStat

__all__ = ["MemoryBackend"]


def _norm(path: str) -> str:
    """Normalise a path to an absolute POSIX-style string.

    MemoryBackend uses POSIX semantics internally regardless of host OS so
    tests are portable.
    """
    if not posixpath.isabs(path):
        path = posixpath.join("/", path)
    return posixpath.normpath(path)


class MemoryBackend:
    """Dict-backed filesystem.

    Files are stored as ``bytes`` in an internal mapping. Directories are
    tracked as a set of paths so ``list_dir`` can distinguish "empty dir"
    from "no such dir".
    """

    def __init__(self, files: dict[str, str | bytes] | None = None) -> None:
        self._files: dict[str, bytes] = {}
        self._dirs: set[str] = {"/"}
        self._mtimes: dict[str, float] = {}
        if files:
            for p, c in files.items():
                self.write_bytes(p, c.encode("utf-8") if isinstance(c, str) else c)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        p = _norm(path)
        return p in self._files or p in self._dirs

    def stat(self, path: str) -> FsStat:
        p = _norm(path)
        if p in self._files:
            return FsStat(
                path=p,
                size=len(self._files[p]),
                is_dir=False,
                is_file=True,
                mtime=self._mtimes.get(p, 0.0),
            )
        if p in self._dirs:
            return FsStat(
                path=p,
                size=0,
                is_dir=True,
                is_file=False,
                mtime=self._mtimes.get(p, 0.0),
            )
        raise FileNotFoundError(path)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding, errors="replace")

    def read_bytes(self, path: str) -> bytes:
        p = _norm(path)
        if p not in self._files:
            raise FileNotFoundError(path)
        return self._files[p]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_text(self, path: str, content: str, *, encoding: str = "utf-8") -> None:
        self.write_bytes(path, content.encode(encoding))

    def write_bytes(self, path: str, content: bytes) -> None:
        p = _norm(path)
        # Ensure parent directories exist.
        parent = posixpath.dirname(p)
        while parent and parent not in self._dirs:
            self._dirs.add(parent)
            parent = posixpath.dirname(parent)
        self._files[p] = content
        self._mtimes[p] = time.time()

    def delete(self, path: str) -> None:
        p = _norm(path)
        if p in self._files:
            del self._files[p]
            self._mtimes.pop(p, None)
            return
        if p in self._dirs:
            # Refuse to delete non-empty directories, matching LocalBackend.
            if any(f.startswith(p + "/") for f in self._files):
                raise OSError(f"Directory not empty: {path}")
            if any(d.startswith(p + "/") for d in self._dirs):
                raise OSError(f"Directory not empty: {path}")
            self._dirs.discard(p)
            return
        raise FileNotFoundError(path)

    def mkdir(self, path: str, *, parents: bool = True, exist_ok: bool = True) -> None:
        p = _norm(path)
        if p in self._dirs:
            if not exist_ok:
                raise FileExistsError(path)
            return
        if not parents and posixpath.dirname(p) not in self._dirs:
            raise FileNotFoundError(posixpath.dirname(p))
        cursor = ""
        for part in [x for x in p.split("/") if x]:
            cursor = cursor + "/" + part
            self._dirs.add(cursor)
            self._mtimes.setdefault(cursor, time.time())

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def list_dir(self, path: str) -> list[FsEntry]:
        p = _norm(path)
        if p not in self._dirs:
            raise FileNotFoundError(path)
        entries: list[FsEntry] = []
        seen_dirs: set[str] = set()
        prefix = p + "/" if p != "/" else "/"
        # Files that live directly in this dir.
        for f in self._files:
            if f.startswith(prefix):
                rest = f[len(prefix) :]
                if "/" not in rest:
                    entries.append(
                        FsEntry(
                            name=rest,
                            path=f,
                            is_dir=False,
                            is_file=True,
                        )
                    )
                else:
                    sub = rest.split("/", 1)[0]
                    seen_dirs.add(sub)
        # Explicit subdirectories.
        for d in self._dirs:
            if d.startswith(prefix):
                rest = d[len(prefix) :]
                if rest and "/" not in rest:
                    seen_dirs.add(rest)
        for name in sorted(seen_dirs):
            entries.append(
                FsEntry(
                    name=name,
                    path=posixpath.join(p, name),
                    is_dir=True,
                    is_file=False,
                )
            )
        return sorted(entries, key=lambda e: (not e.is_dir, e.name))

    def iter_files(self, root: str) -> Iterator[str]:
        r = _norm(root)
        prefix = r + "/" if r != "/" else "/"
        for f in sorted(self._files):
            if f.startswith(prefix) or (r == "/" and f.startswith("/")):
                yield f

    def glob(self, pattern: str, *, root: str | None = None) -> list[str]:
        r = _norm(root) if root is not None else "/"
        # Build a list of candidate relative paths.
        matches: list[str] = []
        prefix = r + "/" if r != "/" else "/"
        for f in sorted(self._files):
            if not f.startswith(prefix) and not (r == "/" and f.startswith("/")):
                continue
            rel = f[len(prefix) :] if r != "/" else f.lstrip("/")
            if _matches_glob(pattern, rel):
                matches.append(f)
        return matches


def _matches_glob(pattern: str, path: str) -> bool:
    """Match ``path`` against ``pattern`` with ``**`` support."""
    # fnmatch does not understand ``**``. Split the pattern on ``/`` and
    # handle ``**`` as "zero or more components".
    pat_parts = pattern.split("/")
    path_parts = path.split("/") if path else [""]

    def match_here(pi: int, xi: int) -> bool:
        while pi < len(pat_parts):
            part = pat_parts[pi]
            if part == "**":
                # Zero-or-more components.
                if pi + 1 == len(pat_parts):
                    return True
                return any(match_here(pi + 1, k) for k in range(xi, len(path_parts) + 1))
            if xi >= len(path_parts):
                return False
            if not fnmatch.fnmatchcase(path_parts[xi], part):
                return False
            pi += 1
            xi += 1
        return xi == len(path_parts)

    return match_here(0, 0)
