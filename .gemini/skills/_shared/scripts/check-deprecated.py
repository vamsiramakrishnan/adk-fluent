#!/usr/bin/env python3
"""Scan files for deprecated adk-fluent method usage.

Reads deprecated aliases from seeds/seed.manual.toml and searches
target files for their usage.

Usage:
    uv run .claude/skills/_shared/scripts/check-deprecated.py [PATH...]
    uv run .claude/skills/_shared/scripts/check-deprecated.py src/ tests/ examples/
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Find project root (where seeds/ lives)
script_dir = Path(__file__).resolve().parent
project_root = script_dir
for _ in range(10):
    if (project_root / "seeds").exists():
        break
    project_root = project_root.parent

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


def load_deprecated_aliases() -> dict[str, str]:
    """Load deprecated aliases from seed.manual.toml."""
    seed_path = project_root / "seeds" / "seed.manual.toml"
    if not seed_path.exists():
        print(f"ERROR: {seed_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(seed_path, "rb") as f:
        seed = tomllib.load(f)

    aliases: dict[str, str] = {}
    for _builder_name, builder_config in seed.get("builders", {}).items():
        for dep_name, dep_val in builder_config.get("deprecated_aliases", {}).items():
            if isinstance(dep_val, dict):
                aliases[dep_name] = dep_val.get("use", "?")
            else:
                aliases[dep_name] = str(dep_val)
    return aliases


def scan_file(path: Path, aliases: dict[str, str]) -> list[tuple[int, str, str, str]]:
    """Scan a file for deprecated method calls. Returns (line_no, line, deprecated, replacement)."""
    findings = []
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return findings

    for i, line in enumerate(text.splitlines(), 1):
        for dep_name, replacement in aliases.items():
            if re.search(rf"\.{dep_name}\s*\(", line):
                findings.append((i, line.strip(), dep_name, replacement))
    return findings


def main():
    paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else [project_root / "src"]

    aliases = load_deprecated_aliases()
    if not aliases:
        print("No deprecated aliases found in seed.manual.toml")
        return

    total_findings = 0
    for root_path in paths:
        if root_path.is_file():
            files = [root_path]
        else:
            files = sorted(root_path.rglob("*.py"))

        for path in files:
            findings = scan_file(path, aliases)
            for line_no, line_text, dep_name, replacement in findings:
                rel = path.relative_to(project_root) if path.is_relative_to(project_root) else path
                print(f"{rel}:{line_no}: `.{dep_name}()` → use `.{replacement}()` instead")
                print(f"  {line_text}")
                print()
                total_findings += 1

    if total_findings == 0:
        print("No deprecated method usage found.")
    else:
        print(f"Found {total_findings} deprecated method usage(s).")


if __name__ == "__main__":
    main()
