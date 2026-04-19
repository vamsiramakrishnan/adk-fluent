"""Changelog helpers.

The repo's ``CHANGELOG.md`` follows Keep-a-Changelog; each release is a
level-2 heading ``## [X.Y.Z] - YYYY-MM-DD`` with an ``[Unreleased]`` section at
the top that accumulates work between releases.

Operations provided
-------------------
- ``has_entry(version)``: check that the file contains a heading for the given
  version (used by preflight).
- ``promote_unreleased(version, date)``: rename the ``[Unreleased]`` heading
  into the given version and re-seed an empty ``[Unreleased]`` block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .version import REPO_ROOT

CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"
_UNRELEASED_HEADING = "## [Unreleased]"


class ChangelogError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangelogStatus:
    has_unreleased: bool
    unreleased_has_content: bool
    released_versions: tuple[str, ...]

    def summary(self) -> str:
        head = "yes" if self.has_unreleased else "MISSING"
        body = "populated" if self.unreleased_has_content else "empty"
        last = self.released_versions[0] if self.released_versions else "<none>"
        return f"Unreleased: {head} ({body})  · Last released: {last}"


def _read() -> str:
    if not CHANGELOG_FILE.exists():
        raise ChangelogError(f"{CHANGELOG_FILE} missing")
    return CHANGELOG_FILE.read_text()


def status() -> ChangelogStatus:
    text = _read()
    has_unreleased = _UNRELEASED_HEADING in text
    released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, flags=re.M)
    # Detect if Unreleased has meaningful body text — more than a blank line
    unreleased_has_content = False
    if has_unreleased:
        m = re.search(
            rf"{re.escape(_UNRELEASED_HEADING)}\s*\n(.*?)(?=\n## \[|\Z)",
            text,
            flags=re.S,
        )
        if m and m.group(1).strip():
            unreleased_has_content = True
    return ChangelogStatus(
        has_unreleased=has_unreleased,
        unreleased_has_content=unreleased_has_content,
        released_versions=tuple(released),
    )


def has_entry(version: str) -> bool:
    text = _read()
    return bool(re.search(rf"^## \[{re.escape(version)}\]", text, flags=re.M))


def promote_unreleased(version: str, when: date | None = None) -> None:
    """Rename ``## [Unreleased]`` to ``## [version] - DATE`` and re-seed empty Unreleased."""
    if when is None:
        when = date.today()
    text = _read()
    if _UNRELEASED_HEADING not in text:
        raise ChangelogError(
            "CHANGELOG.md has no ## [Unreleased] section; add notes before releasing."
        )
    if has_entry(version):
        raise ChangelogError(f"CHANGELOG.md already has an entry for [{version}]")
    new = text.replace(
        _UNRELEASED_HEADING,
        f"{_UNRELEASED_HEADING}\n\n## [{version}] - {when.isoformat()}",
        1,
    )
    CHANGELOG_FILE.write_text(new)
