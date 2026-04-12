"""Git workspace tools — commit, status, log, branch, diff as tool closures.

Extends the harness tool surface with git operations that the LLM can
invoke directly. Follows the same ``make_xxx(sandbox) → Callable``
pattern as workspace tools.

Usage::

    tools = H.git_tools("/project")
    agent = Agent("coder").tools(H.workspace("/project") + tools)
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["git_tools"]


def _run_git(args: list[str], cwd: str, timeout: int = 30) -> tuple[int, str]:
    """Run a git command and return (returncode, output)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr.strip():
            output = result.stderr.strip()
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "Error: git command timed out."
    except Exception as e:
        return 1, f"Error: {e}"


def make_git_status(sandbox: SandboxPolicy) -> Callable:
    """Create a git_status tool."""
    cwd = sandbox.workspace or "."

    def git_status() -> str:
        """Show the working tree status (staged, unstaged, untracked files)."""
        rc, out = _run_git(["status", "--short"], cwd)
        if rc != 0:
            return f"Error: {out}"
        return out or "(clean working tree)"

    return git_status


def make_git_diff(sandbox: SandboxPolicy) -> Callable:
    """Create a git_diff tool."""
    cwd = sandbox.workspace or "."

    def git_diff(staged: bool = False) -> str:
        """Show file changes in the working tree.

        Args:
            staged: If True, show staged changes only. Otherwise show unstaged.
        """
        args = ["diff", "--stat"]
        if staged:
            args.append("--cached")
        rc, out = _run_git(args, cwd)
        if rc != 0:
            return f"Error: {out}"
        return out or "(no changes)"

    return git_diff


def make_git_log(sandbox: SandboxPolicy) -> Callable:
    """Create a git_log tool."""
    cwd = sandbox.workspace or "."

    def git_log(n: int = 10) -> str:
        """Show recent commit history.

        Args:
            n: Number of commits to show (default 10, max 50).
        """
        n = min(max(n, 1), 50)
        rc, out = _run_git(["log", "--oneline", f"-{n}"], cwd)
        if rc != 0:
            return f"Error: {out}"
        return out or "(no commits)"

    return git_log


def make_git_commit(sandbox: SandboxPolicy) -> Callable:
    """Create a git_commit tool."""
    cwd = sandbox.workspace or "."

    def git_commit(message: str, files: str = ".") -> str:
        """Stage files and create a commit.

        Args:
            message: Commit message.
            files: Space-separated file paths to stage, or "." for all.
        """
        if not sandbox.allow_shell:
            return "Error: shell execution disabled by sandbox policy."

        # Stage
        file_list = files.split() if files != "." else ["."]
        rc, out = _run_git(["add", *file_list], cwd)
        if rc != 0:
            return f"Error staging files: {out}"

        # Commit
        rc, out = _run_git(["commit", "-m", message], cwd)
        if rc != 0:
            return f"Error committing: {out}"
        return out

    return git_commit


def make_git_branch(sandbox: SandboxPolicy) -> Callable:
    """Create a git_branch tool."""
    cwd = sandbox.workspace or "."

    def git_branch(name: str = "", create: bool = False, switch: bool = False) -> str:
        """List, create, or switch branches.

        Args:
            name: Branch name. If empty, lists all branches.
            create: Create the branch.
            switch: Switch to the branch (creates if needed with create=True).
        """
        if not name:
            rc, out = _run_git(["branch", "--list"], cwd)
            return out if rc == 0 else f"Error: {out}"

        if create and switch:
            rc, out = _run_git(["checkout", "-b", name], cwd)
        elif create:
            rc, out = _run_git(["branch", name], cwd)
        elif switch:
            rc, out = _run_git(["checkout", name], cwd)
        else:
            rc, out = _run_git(["branch", "--list", name], cwd)

        return out if rc == 0 else f"Error: {out}"

    return git_branch


def git_tools(
    path: str | Path | None = None,
    *,
    allow_shell: bool = True,
) -> list[Callable]:
    """Create the git tool set.

    Returns [git_status, git_diff, git_log, git_commit, git_branch].

    Args:
        path: Workspace directory (git repo root).
        allow_shell: Allow write operations (commit, branch create).
    """
    sandbox = SandboxPolicy(
        workspace=str(Path(path).resolve()) if path else None,
        allow_shell=allow_shell,
    )
    tools: list[Callable] = [
        make_git_status(sandbox),
        make_git_diff(sandbox),
        make_git_log(sandbox),
    ]
    if allow_shell:
        tools.append(make_git_commit(sandbox))
        tools.append(make_git_branch(sandbox))
    return tools
