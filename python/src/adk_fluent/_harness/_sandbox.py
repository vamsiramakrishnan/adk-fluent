"""Sandbox policies — filesystem and execution constraints.

Provides path validation with symlink-safe resolution, workspace scoping,
and configurable shell/network access::

    sandbox = SandboxPolicy(workspace="/project")
    assert sandbox.validate_path("/project/src/main.py")       # True
    assert not sandbox.validate_path("/etc/passwd")             # False
    assert not sandbox.validate_path("/project/../../etc/passwd")  # False (symlink-safe)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

__all__ = ["SandboxPolicy"]


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    """Filesystem and network constraints for tool execution.

    All path validation uses ``os.path.realpath()`` to resolve symlinks
    and ``..`` traversals before checking containment. This prevents
    symlink-based escapes from the workspace.
    """

    workspace: str | None = None
    read_paths: frozenset[str] = frozenset()
    write_paths: frozenset[str] = frozenset()
    allow_network: bool = True
    allow_shell: bool = True
    max_output_bytes: int = 100_000

    def resolve_path(self, path: str) -> str:
        """Resolve a path relative to workspace, following symlinks.

        This is the single point of path resolution. All tools should
        call this before accessing the filesystem.
        """
        if self.workspace and not os.path.isabs(path):
            path = os.path.join(self.workspace, path)
        return os.path.realpath(path)

    def validate_path(self, path: str, *, write: bool = False) -> bool:
        """Check if a path is allowed under this policy.

        Resolves symlinks and ``..`` to prevent escape attacks.
        A path that symlinks outside the workspace is rejected.
        """
        resolved = os.path.realpath(path)
        if self.workspace:
            ws = os.path.realpath(self.workspace)
            # Use os.sep to prevent prefix attacks: /workspace2 matching /workspace
            if resolved == ws or resolved.startswith(ws + os.sep):
                return True
        allowed = self.write_paths if write else (self.read_paths | self.write_paths)
        for p in allowed:
            rp = os.path.realpath(p)
            if resolved == rp or resolved.startswith(rp + os.sep):
                return True
        return False

    def is_path_within_workspace(self, path: str) -> bool:
        """Quick check if a resolved path is within the workspace."""
        if not self.workspace:
            return True  # No workspace constraint
        resolved = os.path.realpath(path)
        ws = os.path.realpath(self.workspace)
        return resolved == ws or resolved.startswith(ws + os.sep)
