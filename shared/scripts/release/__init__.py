"""Release engineering for adk-fluent.

Single source of truth: ``VERSION`` at the repo root.

Sub-modules
-----------
- :mod:`version`    — read / bump / sync the root VERSION into language-specific files.
- :mod:`changelog`  — parse + update CHANGELOG.md (Keep-a-Changelog).
- :mod:`preflight`  — pre-release readiness checks (versions agree, changelog entry, clean tree).

CLI
---
Invoke via ``python -m shared.scripts.release <subcommand>`` (see ``__main__.py``).
The ``justfile.release`` module wraps these subcommands as ``just rel-*`` recipes.
"""

from .version import (
    VERSION_FILE,
    PYTHON_VERSION_FILE,
    TS_PACKAGE_FILE,
    DOCS_CONF_FILE,
    read_version,
    bump_version,
    sync_versions,
    current_versions,
)

__all__ = [
    "VERSION_FILE",
    "PYTHON_VERSION_FILE",
    "TS_PACKAGE_FILE",
    "DOCS_CONF_FILE",
    "read_version",
    "bump_version",
    "sync_versions",
    "current_versions",
]
