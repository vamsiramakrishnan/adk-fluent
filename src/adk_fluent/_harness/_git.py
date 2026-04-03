"""Git checkpoint/rollback — undo support for file edits.

Real coding harnesses (Claude Code, Codex, Gemini CLI) create git stash
or checkpoint commits before making changes, enabling clean undo.

Usage::

    checkpoint = GitCheckpointer("/project")
    sha = checkpoint.create("before refactoring auth module")
    # ... agent makes changes ...
    checkpoint.restore(sha)  # undo all changes
    checkpoint.list_checkpoints()  # show history

Design:
    - Checkpoints use ``git stash create`` (no-op if clean) + tracking
    - Restore uses ``git checkout`` to revert to checkpoint state
    - Non-destructive: never force-pushes or rewrites history
    - Falls back gracefully if workspace is not a git repo
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["GitCheckpointer"]


@dataclass
class _Checkpoint:
    """A recorded git checkpoint."""

    sha: str
    message: str
    method: str  # "stash" or "commit"
    timestamp: float = 0.0


class GitCheckpointer:
    """Creates and restores git checkpoints for undo support.

    Args:
        workspace: Path to the git repository.
    """

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = str(Path(workspace).resolve())
        self._checkpoints: list[_Checkpoint] = []
        self._is_git_repo: bool | None = None

    @property
    def is_git_repo(self) -> bool:
        """Check if workspace is a git repository."""
        if self._is_git_repo is None:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self._is_git_repo = result.returncode == 0
            except Exception:
                self._is_git_repo = False
        return self._is_git_repo

    def create(self, message: str = "checkpoint") -> str | None:
        """Create a checkpoint of the current workspace state.

        Uses ``git stash create`` to capture uncommitted changes without
        modifying the working tree. If clean, records the HEAD commit.

        Returns:
            The checkpoint SHA, or None if not a git repo.
        """
        if not self.is_git_repo:
            return None

        import time

        try:
            # Try stash create (captures changes without modifying working tree)
            result = subprocess.run(
                ["git", "stash", "create", message],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            sha = result.stdout.strip()

            if sha:
                # There were uncommitted changes — stash captured them
                method = "stash"
            else:
                # Working tree is clean — record HEAD
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                sha = result.stdout.strip()
                method = "commit"

            if sha:
                self._checkpoints.append(_Checkpoint(
                    sha=sha,
                    message=message,
                    method=method,
                    timestamp=time.time(),
                ))
                return sha
        except Exception:
            pass
        return None

    def restore(self, sha: str | None = None) -> bool:
        """Restore workspace to a checkpoint state.

        Args:
            sha: Checkpoint SHA to restore. If None, restores the most
                recent checkpoint.

        Returns:
            True if restoration succeeded.
        """
        if not self.is_git_repo:
            return False

        if sha is None:
            if not self._checkpoints:
                return False
            cp = self._checkpoints[-1]
            sha = cp.sha
            method = cp.method
        else:
            method = "stash"
            for cp in self._checkpoints:
                if cp.sha == sha:
                    method = cp.method
                    break

        try:
            if method == "stash":
                # Apply stash (restores the captured state)
                result = subprocess.run(
                    ["git", "stash", "apply", sha],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return result.returncode == 0
            else:
                # Hard reset to the commit (clean checkout)
                result = subprocess.run(
                    ["git", "checkout", sha, "--", "."],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return result.returncode == 0
        except Exception:
            return False

    def list_checkpoints(self) -> list[dict[str, str]]:
        """Return a list of recorded checkpoints."""
        return [
            {"sha": cp.sha[:8], "message": cp.message, "method": cp.method}
            for cp in self._checkpoints
        ]

    def diff_since(self, sha: str | None = None) -> str:
        """Show diff since a checkpoint.

        Args:
            sha: Checkpoint SHA. If None, uses the most recent.

        Returns:
            Git diff output or error message.
        """
        if not self.is_git_repo:
            return "Not a git repository."

        if sha is None:
            if not self._checkpoints:
                return "No checkpoints recorded."
            sha = self._checkpoints[-1].sha

        try:
            result = subprocess.run(
                ["git", "diff", sha],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout or "(no changes)"
        except Exception as e:
            return f"Error getting diff: {e}"
