"""Version single-source-of-truth for the monorepo.

Canonical file
--------------
``VERSION`` at the repo root contains a plain semver string, one line, no prefix::

    0.14.1

Consumers (kept in sync automatically)
--------------------------------------
- ``python/src/adk_fluent/_version.py``  (Python wheel metadata; docs/conf.py reads from this)
- ``ts/package.json``                    (npm publish source)

Never edit those files by hand. Run ``just rel-bump LEVEL`` or ``just rel-sync``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

VERSION_FILE = REPO_ROOT / "VERSION"
PYTHON_VERSION_FILE = REPO_ROOT / "python" / "src" / "adk_fluent" / "_version.py"
TS_PACKAGE_FILE = REPO_ROOT / "ts" / "package.json"
# docs/conf.py reads from _version.py — no direct sync required.
DOCS_CONF_FILE = REPO_ROOT / "docs" / "conf.py"

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-[\w.]+)?(?:\+[\w.]+)?$")
_PY_VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')


class VersionError(RuntimeError):
    """Raised when the monorepo version state is inconsistent or invalid."""


@dataclass(frozen=True)
class VersionState:
    root: str
    python: str
    ts: str

    @property
    def consistent(self) -> bool:
        return self.root == self.python == self.ts

    def summary(self) -> str:
        mark = "✓" if self.consistent else "✗"
        return (
            f"{mark} VERSION={self.root}  python={self.python}  ts={self.ts}"
            + ("" if self.consistent else "  (drift)")
        )


def read_version() -> str:
    """Return the canonical version from ``VERSION``."""
    if not VERSION_FILE.exists():
        raise VersionError(f"{VERSION_FILE} missing — create it with the current version.")
    raw = VERSION_FILE.read_text().strip()
    if not SEMVER_RE.match(raw):
        raise VersionError(f"{VERSION_FILE} contains invalid semver: {raw!r}")
    return raw


def write_root_version(version: str) -> None:
    if not SEMVER_RE.match(version):
        raise VersionError(f"Refusing to write invalid semver: {version!r}")
    VERSION_FILE.write_text(version + "\n")


def read_python_version() -> str:
    text = PYTHON_VERSION_FILE.read_text()
    m = _PY_VERSION_RE.search(text)
    if not m:
        raise VersionError(f"No __version__ in {PYTHON_VERSION_FILE}")
    return m.group(1)


def write_python_version(version: str) -> None:
    PYTHON_VERSION_FILE.write_text(
        f'"""Single source of truth for adk-fluent version."""\n\n'
        f'__version__ = "{version}"\n'
    )


def read_ts_version() -> str:
    data = json.loads(TS_PACKAGE_FILE.read_text())
    return data["version"]


def write_ts_version(version: str) -> None:
    text = TS_PACKAGE_FILE.read_text()
    new_text, n = re.subn(
        r'(\n\s*"version"\s*:\s*)"[^"]+"',
        lambda m: f'{m.group(1)}"{version}"',
        text,
        count=1,
    )
    if n != 1:
        raise VersionError(f"Failed to rewrite version in {TS_PACKAGE_FILE}")
    TS_PACKAGE_FILE.write_text(new_text)


def current_versions() -> VersionState:
    return VersionState(
        root=read_version(),
        python=read_python_version(),
        ts=read_ts_version(),
    )


def sync_versions(version: str | None = None) -> VersionState:
    """Propagate the root VERSION into Python + TS consumer files.

    If ``version`` is given, write it to VERSION first. Otherwise read the
    existing VERSION and only fan out to the consumers.
    """
    if version is not None:
        write_root_version(version)
    target = read_version()
    write_python_version(target)
    write_ts_version(target)
    return current_versions()


def bump_version(level: str) -> tuple[str, str]:
    """Bump patch/minor/major, persist everywhere, return (old, new)."""
    if level not in {"patch", "minor", "major"}:
        raise VersionError(f"invalid bump level {level!r}; use patch|minor|major")
    current = read_version()
    m = SEMVER_RE.match(current)
    if not m:
        raise VersionError(f"VERSION is not plain semver: {current!r}")
    major, minor, patch = (int(m.group(i)) for i in (1, 2, 3))
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new = f"{major}.{minor}.{patch}"
    sync_versions(new)
    return current, new
