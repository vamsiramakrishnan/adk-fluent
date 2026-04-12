"""Backend-driven workspace tool factories.

The existing :mod:`adk_fluent._harness._tools` factories build tools that
talk to :mod:`pathlib` directly. The adapters here build the *same* tool
shapes (same name, same signature, same return format) but route every
filesystem op through a :class:`FsBackend`.

Callers who do not care about the backend should keep using
:func:`adk_fluent._harness.workspace_tools`, which now delegates to these
adapters with a ``SandboxedBackend(LocalBackend())`` default.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from adk_fluent._fs._backend import FsBackend
from adk_fluent._fs._sandbox import SandboxViolation

__all__ = ["workspace_tools_with_backend"]


def make_read_file_backend(backend: FsBackend) -> Callable:
    def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read a file with line numbers. Returns up to ``limit`` lines from ``offset``."""
        try:
            text = backend.read_text(path)
        except SandboxViolation:
            return f"Error: path '{path}' is outside the allowed workspace."
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:  # noqa: BLE001
            return f"Error reading file: {e}"
        lines = text.splitlines(keepends=True)
        selected = lines[offset : offset + limit]
        numbered = [f"{offset + i + 1}\t{line}" for i, line in enumerate(selected)]
        return "".join(numbered)

    return read_file


def make_edit_file_backend(backend: FsBackend) -> Callable:
    def edit_file(path: str, old_string: str, new_string: str) -> str:
        """Replace an exact string in a file. ``old_string`` must appear exactly once."""
        try:
            content = backend.read_text(path)
        except SandboxViolation:
            return f"Error: path '{path}' is outside the allowed workspace."
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:  # noqa: BLE001
            return f"Error reading file: {e}"
        count = content.count(old_string)
        if count == 0:
            return f"Error: old_string not found in {path}"
        if count > 1:
            return f"Error: old_string appears {count} times in {path}. Must be unique."
        new_content = content.replace(old_string, new_string, 1)
        try:
            backend.write_text(path, new_content)
        except SandboxViolation:
            return f"Error: path '{path}' is outside the allowed workspace."
        except Exception as e:  # noqa: BLE001
            return f"Error writing file: {e}"
        return f"Successfully edited {path}"

    return edit_file


def make_write_file_backend(backend: FsBackend) -> Callable:
    def write_file(path: str, content: str) -> str:
        """Write content to a file, creating it if it does not exist."""
        try:
            backend.write_text(path, content)
        except SandboxViolation:
            return f"Error: path '{path}' is outside the allowed workspace."
        except Exception as e:  # noqa: BLE001
            return f"Error writing file: {e}"
        return f"Successfully wrote {path}"

    return write_file


def make_list_dir_backend(backend: FsBackend) -> Callable:
    def list_dir(path: str = ".") -> str:
        """List files and directories at the given path."""
        try:
            entries = backend.list_dir(path)
        except SandboxViolation:
            return f"Error: path '{path}' is outside the allowed workspace."
        except FileNotFoundError:
            return f"Error: directory not found: {path}"
        except Exception as e:  # noqa: BLE001
            return f"Error listing directory: {e}"
        lines = [f"{'d ' if e.is_dir else 'f '}{e.name}" for e in entries[:200]]
        return "\n".join(lines) or "(empty directory)"

    return list_dir


def make_glob_search_backend(backend: FsBackend) -> Callable:
    def glob_search(pattern: str) -> str:
        """Find files matching a glob pattern in the workspace."""
        try:
            matches = backend.glob(pattern)
        except SandboxViolation:
            return "Error: glob root is outside the allowed workspace."
        except Exception as e:  # noqa: BLE001
            return f"Error running glob: {e}"
        results = matches[:100]
        if not results:
            return "No files found matching the pattern."
        return "\n".join(results)

    return glob_search


def make_grep_search_backend(backend: FsBackend) -> Callable:
    def grep_search(pattern: str, glob: str = "**/*", max_results: int = 50) -> str:
        """Search file contents for a regex pattern."""
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regex: {e}"
        try:
            candidates = backend.glob(glob)
        except SandboxViolation:
            return "Error: glob root is outside the allowed workspace."
        except Exception as e:  # noqa: BLE001
            return f"Error running glob: {e}"
        results: list[str] = []
        for filepath in candidates:
            try:
                text = backend.read_text(filepath)
            except (SandboxViolation, FileNotFoundError, IsADirectoryError, OSError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    results.append(f"{filepath}:{i}: {line.rstrip()}")
                    if len(results) >= max_results:
                        return "\n".join(results)
        return "\n".join(results) or "No matches found."

    return grep_search


def workspace_tools_with_backend(
    backend: FsBackend,
    *,
    read_only: bool = False,
) -> list[Callable]:
    """Build a full tool set against ``backend``.

    Unlike :func:`adk_fluent._harness.workspace_tools` this adapter does not
    include a ``bash`` tool — shell execution is a separate concern handled
    by :mod:`adk_fluent._harness._tools` directly. Pair the two lists if
    you need both.
    """
    tools: list[Callable] = [
        make_read_file_backend(backend),
        make_glob_search_backend(backend),
        make_grep_search_backend(backend),
        make_list_dir_backend(backend),
    ]
    if not read_only:
        tools.append(make_edit_file_backend(backend))
        tools.append(make_write_file_backend(backend))
    return tools
