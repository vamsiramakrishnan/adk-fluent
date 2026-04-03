"""Workspace tool factories — sandboxed file and shell operations.

Each factory takes a SandboxPolicy and returns a plain Python function
suitable for use as an ADK FunctionTool. Tools are scoped to the
workspace directory and respect sandbox constraints.

Tool inventory:
    - ``read_file``    — read with line numbers, offset, limit
    - ``edit_file``    — search-and-replace (unique match required)
    - ``write_file``   — create/overwrite with auto-mkdir
    - ``glob_search``  — gitignore-aware glob
    - ``grep_search``  — gitignore-aware regex search
    - ``bash``         — shell command execution
    - ``list_dir``     — directory listing
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from adk_fluent._harness._gitignore import load_gitignore
from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = [
    "make_read_file",
    "make_edit_file",
    "make_write_file",
    "make_glob_search",
    "make_grep_search",
    "make_bash",
    "make_list_dir",
    "workspace_tools",
]


def make_read_file(sandbox: SandboxPolicy) -> Callable:
    """Create a sandboxed file-read tool."""

    def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read a file with line numbers. Returns up to `limit` lines starting from `offset`.

        Args:
            path: Absolute or workspace-relative file path.
            offset: Line number to start from (0-based).
            limit: Maximum number of lines to return.
        """
        resolved = sandbox.resolve_path(path)
        if not sandbox.validate_path(resolved, write=False):
            return f"Error: path '{path}' is outside the allowed workspace."
        try:
            with open(resolved, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            selected = lines[offset : offset + limit]
            numbered = [f"{offset + i + 1}\t{line}" for i, line in enumerate(selected)]
            return "".join(numbered)
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:
            return f"Error reading file: {e}"

    return read_file


def make_edit_file(sandbox: SandboxPolicy) -> Callable:
    """Create a sandboxed file-edit tool (search-and-replace)."""

    def edit_file(path: str, old_string: str, new_string: str) -> str:
        """Replace an exact string in a file. The old_string must appear exactly once.

        Args:
            path: Absolute or workspace-relative file path.
            old_string: The exact text to find and replace.
            new_string: The replacement text.
        """
        resolved = sandbox.resolve_path(path)
        if not sandbox.validate_path(resolved, write=True):
            return f"Error: path '{path}' is outside the allowed workspace."
        try:
            content = Path(resolved).read_text(encoding="utf-8")
            count = content.count(old_string)
            if count == 0:
                return f"Error: old_string not found in {path}"
            if count > 1:
                return f"Error: old_string appears {count} times in {path}. Must be unique."
            new_content = content.replace(old_string, new_string, 1)
            Path(resolved).write_text(new_content, encoding="utf-8")
            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error editing file: {e}"

    return edit_file


def make_write_file(sandbox: SandboxPolicy) -> Callable:
    """Create a sandboxed file-write tool."""

    def write_file(path: str, content: str) -> str:
        """Write content to a file, creating it if it doesn't exist.

        Args:
            path: Absolute or workspace-relative file path.
            content: The full file content to write.
        """
        resolved = sandbox.resolve_path(path)
        if not sandbox.validate_path(resolved, write=True):
            return f"Error: path '{path}' is outside the allowed workspace."
        try:
            Path(resolved).parent.mkdir(parents=True, exist_ok=True)
            Path(resolved).write_text(content, encoding="utf-8")
            return f"Successfully wrote {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    return write_file


def make_glob_search(sandbox: SandboxPolicy) -> Callable:
    """Create a workspace-aware, gitignore-respecting glob search tool."""

    def glob_search(pattern: str) -> str:
        """Find files matching a glob pattern in the workspace.

        Respects .gitignore rules. Hidden files (dotfiles) are excluded
        by default unless the pattern explicitly matches them.

        Args:
            pattern: Glob pattern (e.g., '**/*.py', 'src/**/*.ts').
        """
        root = Path(sandbox.workspace) if sandbox.workspace else Path(".")
        matcher = load_gitignore(root)
        matches = sorted(root.glob(pattern))[:200]
        results = []
        for m in matches:
            if not m.is_file():
                continue
            rel = str(m.relative_to(root))
            if matcher.is_ignored(rel):
                continue
            results.append(rel)
            if len(results) >= 100:
                break
        if not results:
            return "No files found matching the pattern."
        return "\n".join(results)

    return glob_search


def make_grep_search(sandbox: SandboxPolicy) -> Callable:
    """Create a workspace-aware, gitignore-respecting grep tool."""

    def grep_search(pattern: str, glob: str = "**/*", max_results: int = 50) -> str:
        """Search file contents for a regex pattern.

        Respects .gitignore rules. Binary files are skipped.

        Args:
            pattern: Regular expression to search for.
            glob: File glob to limit search scope (default: all files).
            max_results: Maximum number of matching lines to return.
        """
        import re

        root = Path(sandbox.workspace) if sandbox.workspace else Path(".")
        matcher = load_gitignore(root)
        results: list[str] = []
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regex: {e}"
        for filepath in sorted(root.glob(glob)):
            if not filepath.is_file():
                continue
            rel = str(filepath.relative_to(root))
            if matcher.is_ignored(rel):
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        results.append(f"{rel}:{i}: {line.rstrip()}")
                        if len(results) >= max_results:
                            return "\n".join(results)
            except Exception:
                continue
        if not results:
            return "No matches found."
        return "\n".join(results)

    return grep_search


def make_bash(sandbox: SandboxPolicy) -> Callable:
    """Create a sandboxed shell execution tool."""

    def bash(command: str, timeout: int = 120) -> str:
        """Execute a shell command and return its output.

        Args:
            command: The shell command to execute.
            timeout: Maximum execution time in seconds (default: 120).
        """
        if not sandbox.allow_shell:
            return "Error: shell execution is disabled by sandbox policy."
        cwd = sandbox.workspace or None
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            max_bytes = sandbox.max_output_bytes
            if len(output) > max_bytes:
                output = output[:max_bytes] + f"\n... (truncated to {max_bytes} bytes)"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"

    return bash


def make_list_dir(sandbox: SandboxPolicy) -> Callable:
    """Create a workspace-aware directory listing tool."""

    def list_dir(path: str = ".") -> str:
        """List files and directories at the given path.

        Args:
            path: Directory path (default: workspace root).
        """
        resolved = sandbox.resolve_path(path)
        if not sandbox.validate_path(resolved, write=False):
            return f"Error: path '{path}' is outside the allowed workspace."
        try:
            entries = sorted(Path(resolved).iterdir())
            lines = []
            for e in entries[:200]:
                prefix = "d " if e.is_dir() else "f "
                lines.append(f"{prefix}{e.name}")
            return "\n".join(lines) or "(empty directory)"
        except FileNotFoundError:
            return f"Error: directory not found: {path}"
        except Exception as e:
            return f"Error listing directory: {e}"

    return list_dir


def workspace_tools(
    sandbox: SandboxPolicy,
    *,
    read_only: bool = False,
) -> list[Callable]:
    """Create the full set of workspace tools for a sandbox.

    Args:
        sandbox: The sandbox policy to scope tools to.
        read_only: If True, exclude edit/write tools.

    Returns:
        List of tool functions.
    """
    tools: list[Callable] = [
        make_read_file(sandbox),
        make_glob_search(sandbox),
        make_grep_search(sandbox),
        make_list_dir(sandbox),
    ]
    if not read_only:
        tools.append(make_edit_file(sandbox))
        tools.append(make_write_file(sandbox))
    if sandbox.allow_shell:
        tools.append(make_bash(sandbox))
    return tools
