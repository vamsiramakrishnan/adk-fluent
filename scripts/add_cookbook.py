#!/usr/bin/env python3
"""
Scaffold a new cookbook example.
Usage: just add-cookbook "Example Name"
"""

import argparse
import sys
from pathlib import Path

COOKBOOK_DIR = Path("examples/cookbook")

TEMPLATE = '''"""
{title}
{underline}

Description of what this example demonstrates.
"""

from adk_fluent import Agent, Pipeline, S, C

def main():
    # Implement example here
    agent = Agent("example").model("gemini-2.5-flash").instruct("Hello").build()
    print("Example scaffold created!")

if __name__ == "__main__":
    main()
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="Name of the cookbook example")
    args = parser.parse_args()

    if not COOKBOOK_DIR.exists():
        print(f"Error: {COOKBOOK_DIR} does not exist.")
        sys.exit(1)

    # Find next index
    existing = sorted(COOKBOOK_DIR.glob("*.py"))
    max_idx = 0
    for p in existing:
        try:
            idx = int(p.name.split("_")[0])
            if idx > max_idx:
                max_idx = idx
        except (ValueError, IndexError):
            continue

    next_idx = max_idx + 1
    safe_name = args.name.lower().replace(" ", "_").replace("-", "_")
    filename = f"{next_idx:02d}_{safe_name}.py"
    filepath = COOKBOOK_DIR / filename

    title = args.name
    underline = "=" * len(title)

    content = TEMPLATE.format(title=title, underline=underline)
    filepath.write_text(content)

    print(f"Created new cookbook: {filepath}")


if __name__ == "__main__":
    main()
