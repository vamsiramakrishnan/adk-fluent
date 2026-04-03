"""Gitignore-aware file filtering.

Parses ``.gitignore`` files and provides a matcher that workspace tools
(glob, grep) use to skip ignored files — just like real coding harnesses.

The parser handles the core gitignore syntax:
    - ``#`` comments and blank lines
    - ``!`` negation patterns
    - ``/`` directory-only patterns
    - ``**`` recursive wildcards
    - Nested ``.gitignore`` files in subdirectories

Usage::

    matcher = load_gitignore(Path("/project"))
    if matcher.is_ignored("node_modules/foo.js"):
        skip()
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

__all__ = ["GitignoreMatcher", "load_gitignore"]

# Always ignore these regardless of .gitignore content
_ALWAYS_IGNORED = frozenset(
    {
        ".git",
        "__pycache__",
        ".DS_Store",
        "Thumbs.db",
    }
)


@dataclass
class _Rule:
    """A single gitignore rule."""

    pattern: str
    negated: bool = False
    dir_only: bool = False
    anchored: bool = False  # Contains / (path-specific)


class GitignoreMatcher:
    """Matches file paths against gitignore rules.

    Thread-safe for reads after construction.
    """

    def __init__(self, rules: list[_Rule] | None = None) -> None:
        self._rules: list[_Rule] = rules or []

    def is_ignored(self, rel_path: str) -> bool:
        """Check if a relative path should be ignored.

        Args:
            rel_path: Path relative to the workspace root (forward slashes).
        """
        # Normalize to forward slashes
        rel_path = rel_path.replace(os.sep, "/")

        # Always-ignored paths
        parts = rel_path.split("/")
        for part in parts:
            if part in _ALWAYS_IGNORED:
                return True

        # Skip dotfiles/dirs (common harness behavior)
        for part in parts:
            if part.startswith(".") and part not in (".", ".."):
                return True

        # Apply rules in order; last matching rule wins
        ignored = False
        for rule in self._rules:
            if self._matches(rule, rel_path):
                ignored = not rule.negated
        return ignored

    @staticmethod
    def _matches(rule: _Rule, rel_path: str) -> bool:
        """Check if a single rule matches a path."""
        pattern = rule.pattern

        # If pattern has no slash, match against basename and path components
        if not rule.anchored:
            basename = rel_path.rsplit("/", 1)[-1]
            if fnmatch.fnmatch(basename, pattern):
                return True
            # For dir_only patterns, also match against path components
            if rule.dir_only:
                for part in rel_path.split("/"):
                    if fnmatch.fnmatch(part, pattern):
                        return True
            # Also try matching against full path for ** patterns
            return "**" in pattern and fnmatch.fnmatch(rel_path, pattern)

        # Anchored pattern: match against full path
        # Handle ** as recursive wildcard
        if "**" in pattern:
            import re

            regex_pattern = pattern.replace("**", "DOUBLESTAR")
            regex_pattern = fnmatch.translate(regex_pattern)
            regex_pattern = regex_pattern.replace("DOUBLESTAR", ".*")
            return bool(re.match(regex_pattern, rel_path))

        return fnmatch.fnmatch(rel_path, pattern)

    def add_rules(self, lines: list[str], prefix: str = "") -> None:
        """Parse and add gitignore rules from lines.

        Args:
            lines: Lines from a .gitignore file.
            prefix: Path prefix for nested .gitignore files.
        """
        for line in lines:
            line = line.rstrip("\n\r")
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            negated = False
            if line.startswith("!"):
                negated = True
                line = line[1:]

            # Strip trailing spaces (unless escaped)
            if not line.endswith("\\ "):
                line = line.rstrip()

            if not line:
                continue

            dir_only = line.endswith("/")
            if dir_only:
                line = line.rstrip("/")

            # If pattern contains a slash (not just trailing), it's anchored
            anchored = "/" in line

            # Prepend prefix for nested .gitignore
            if prefix:
                line = f"{prefix}/{line}"
                anchored = True

            self._rules.append(
                _Rule(
                    pattern=line,
                    negated=negated,
                    dir_only=dir_only,
                    anchored=anchored,
                )
            )


def load_gitignore(root: str | Path) -> GitignoreMatcher:
    """Load all .gitignore files from a project directory.

    Walks the directory tree and loads nested .gitignore files
    with appropriate path prefixes.

    Args:
        root: Project root directory.

    Returns:
        A matcher ready for use with ``is_ignored()``.
    """
    matcher = GitignoreMatcher()
    root = Path(root)

    # Root .gitignore
    root_gi = root / ".gitignore"
    if root_gi.is_file():
        try:
            lines = root_gi.read_text(encoding="utf-8", errors="replace").splitlines()
            matcher.add_rules(lines)
        except Exception:
            pass

    # Walk for nested .gitignore files (limit depth to avoid perf issues)
    max_depth = 5
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune always-ignored directories
        dirnames[:] = [d for d in dirnames if d not in _ALWAYS_IGNORED and not d.startswith(".")]

        depth = str(dirpath).count(os.sep) - str(root).count(os.sep)
        if depth >= max_depth:
            dirnames.clear()
            continue

        if ".gitignore" in filenames and dirpath != str(root):
            gi_path = Path(dirpath) / ".gitignore"
            prefix = str(Path(dirpath).relative_to(root)).replace(os.sep, "/")
            try:
                lines = gi_path.read_text(encoding="utf-8", errors="replace").splitlines()
                matcher.add_rules(lines, prefix=prefix)
            except Exception:
                pass

    return matcher
