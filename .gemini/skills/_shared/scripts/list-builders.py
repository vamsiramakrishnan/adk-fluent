#!/usr/bin/env python3
"""Print adk-fluent builder inventory from manifest.json.

Usage:
    uv run .claude/skills/_shared/scripts/list-builders.py
    uv run .claude/skills/_shared/scripts/list-builders.py --module agent
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
for _ in range(10):
    if (project_root / "manifest.json").exists():
        break
    project_root = project_root.parent


def main():
    manifest_path = project_root / "manifest.json"
    if not manifest_path.exists():
        print(
            f"ERROR: {manifest_path} not found. Run `just scan` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    module_filter = None
    if len(sys.argv) > 2 and sys.argv[1] == "--module":
        module_filter = sys.argv[2]

    print(f"ADK version: {manifest.get('adk_version', '?')}")
    print(f"Total classes: {manifest.get('total_classes', '?')}")
    print(f"Total fields: {manifest.get('total_fields', '?')}")
    print()

    for cls in sorted(manifest.get("classes", []), key=lambda c: c["name"]):
        name = cls["name"]
        qualname = cls.get("qualname", "?")
        field_count = len(cls.get("fields", []))
        if module_filter and module_filter not in qualname:
            continue
        print(f"  {name:30s}  {qualname:60s}  ({field_count} fields)")


if __name__ == "__main__":
    main()
