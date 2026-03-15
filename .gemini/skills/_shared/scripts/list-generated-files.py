#!/usr/bin/env python3
"""Print generated vs hand-written file classification.

Reads .gitattributes to determine which files are auto-generated.

Usage:
    uv run .claude/skills/_shared/scripts/list-generated-files.py
"""

from __future__ import annotations

from pathlib import Path

project_root = Path(__file__).resolve().parent
for _ in range(10):
    if (project_root / ".gitattributes").exists():
        break
    project_root = project_root.parent


def main():
    gitattributes = project_root / ".gitattributes"
    if not gitattributes.exists():
        print("ERROR: .gitattributes not found.")
        return

    generated = []
    for line in gitattributes.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "linguist-generated=true" in line:
            generated.append(line.split()[0])

    print("GENERATED FILES (do not edit directly):")
    print("=" * 50)
    for path in sorted(generated):
        print(f"  {path}")

    print()
    print("HAND-WRITTEN CORE (safe to edit):")
    print("=" * 50)
    src = project_root / "src" / "adk_fluent"
    if src.exists():
        for f in sorted(src.glob("*.py")):
            rel = f.relative_to(project_root)
            is_gen = any(str(rel) == g or str(rel).replace("\\", "/") == g for g in generated)
            if not is_gen:
                print(f"  {rel}")


if __name__ == "__main__":
    main()
