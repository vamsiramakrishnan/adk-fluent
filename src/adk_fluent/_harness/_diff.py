"""Diff-mode edit tool — preview changes before applying.

Claude Code shows diffs before applying edits and lets users approve.
This module wraps the standard edit_file tool with a two-phase flow:

1. Phase 1: ``edit_file(path, old, new)`` → returns a unified diff + token
2. Phase 2: ``apply_edit(token)`` → applies the pending edit

This composes naturally with ``H.ask_before("apply_edit")`` — the
permission check fires on apply, not preview::

    tools = H.workspace("/project", diff_mode=True)
    # edit_file now returns a diff preview
    # apply_edit applies the pending change
"""

from __future__ import annotations

import difflib
import hashlib
import time
from collections.abc import Callable
from pathlib import Path

from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["make_diff_edit_file", "make_apply_edit", "PendingEditStore"]


class PendingEditStore:
    """In-memory store for pending edits awaiting approval.

    Each edit gets a short token. Tokens expire after ``ttl`` seconds.

    Args:
        ttl: Seconds before a pending edit expires (default: 300).
    """

    def __init__(self, ttl: int = 300) -> None:
        self.ttl = ttl
        self._pending: dict[str, dict] = {}

    def store(self, path: str, old_string: str, new_string: str, resolved: str) -> str:
        """Store a pending edit and return its token."""
        self._gc()
        key = hashlib.sha256(f"{path}:{old_string}:{new_string}:{time.time()}".encode()).hexdigest()[:12]
        self._pending[key] = {
            "path": path,
            "resolved": resolved,
            "old_string": old_string,
            "new_string": new_string,
            "created": time.time(),
        }
        return key

    def pop(self, token: str) -> dict | None:
        """Retrieve and remove a pending edit by token."""
        self._gc()
        return self._pending.pop(token, None)

    def _gc(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, v in self._pending.items() if now - v["created"] > self.ttl]
        for k in expired:
            del self._pending[k]


def _make_diff(path: str, old_content: str, new_content: str) -> str:
    """Generate a unified diff between old and new content."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}")
    return "".join(diff) or "(no differences)"


def make_diff_edit_file(sandbox: SandboxPolicy, store: PendingEditStore) -> Callable:
    """Create a diff-mode edit tool that previews changes.

    Instead of applying edits immediately, returns a unified diff and
    a token. The agent must call ``apply_edit(token)`` to apply.

    Args:
        sandbox: Sandbox policy for path validation.
        store: Pending edit store for managing unapplied edits.
    """

    def edit_file(path: str, old_string: str, new_string: str) -> str:
        """Preview an edit as a unified diff. Returns a diff and a token.

        The edit is NOT applied immediately. Call ``apply_edit(token)``
        to apply the change after reviewing the diff.

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
            diff = _make_diff(path, content, new_content)
            token = store.store(path, old_string, new_string, resolved)
            return f'Diff preview for {path}:\n\n{diff}\n\nTo apply this edit, call: apply_edit("{token}")'
        except Exception as e:
            return f"Error: {e}"

    return edit_file


def make_apply_edit(sandbox: SandboxPolicy, store: PendingEditStore) -> Callable:
    """Create a tool that applies a pending edit by token.

    Args:
        sandbox: Sandbox policy for path validation.
        store: Pending edit store to retrieve edits from.
    """

    def apply_edit(token: str) -> str:
        """Apply a previously previewed edit.

        Args:
            token: The token returned by edit_file's diff preview.
        """
        edit = store.pop(token)
        if edit is None:
            return f"Error: no pending edit found for token '{token}'. It may have expired."
        resolved = edit["resolved"]
        if not sandbox.validate_path(resolved, write=True):
            return "Error: path is outside the allowed workspace."
        try:
            content = Path(resolved).read_text(encoding="utf-8")
            count = content.count(edit["old_string"])
            if count == 0:
                return f"Error: old_string no longer found in {edit['path']} (file may have changed)."
            if count > 1:
                return f"Error: old_string now appears {count} times (file may have changed)."
            new_content = content.replace(edit["old_string"], edit["new_string"], 1)
            Path(resolved).write_text(new_content, encoding="utf-8")
            return f"Successfully applied edit to {edit['path']}"
        except Exception as e:
            return f"Error applying edit: {e}"

    return apply_edit
