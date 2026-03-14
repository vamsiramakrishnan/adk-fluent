#!/usr/bin/env python3
"""Check for internal adk_fluent module imports.

Imports should be from `adk_fluent` top-level, not internal modules.

Usage:
    uv run .claude/skills/_shared/scripts/validate-imports.py [PATH...]
    uv run .claude/skills/_shared/scripts/validate-imports.py examples/ tests/manual/
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
for _ in range(10):
    if (project_root / "src").exists():
        break
    project_root = project_root.parent

# Internal modules that should not be imported from directly
INTERNAL_PATTERNS = [
    r"from\s+adk_fluent\._",         # from adk_fluent._base import ...
    r"from\s+adk_fluent\.agent\s",   # from adk_fluent.agent import ...
    r"from\s+adk_fluent\.workflow\s", # from adk_fluent.workflow import ...
    r"from\s+adk_fluent\.tool\s",    # from adk_fluent.tool import ...
    r"from\s+adk_fluent\.config\s",  # from adk_fluent.config import ...
    r"from\s+adk_fluent\.runtime\s",
    r"from\s+adk_fluent\.service\s",
    r"from\s+adk_fluent\.plugin\s",
    r"from\s+adk_fluent\.executor\s",
    r"from\s+adk_fluent\.planner\s",
]


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Scan a file for internal imports."""
    findings = []
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return findings

    for i, line in enumerate(text.splitlines(), 1):
        for pattern in INTERNAL_PATTERNS:
            if re.search(pattern, line):
                findings.append((i, line.strip()))
                break
    return findings


def main():
    paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else [
        project_root / "examples",
    ]

    total = 0
    for root_path in paths:
        files = [root_path] if root_path.is_file() else sorted(root_path.rglob("*.py"))
        for path in files:
            findings = scan_file(path)
            for line_no, line_text in findings:
                rel = path.relative_to(project_root) if path.is_relative_to(project_root) else path
                print(f"{rel}:{line_no}: internal import detected")
                print(f"  {line_text}")
                print(f"  → Use: from adk_fluent import ...")
                print()
                total += 1

    if total == 0:
        print("No internal import violations found.")
    else:
        print(f"Found {total} internal import violation(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
