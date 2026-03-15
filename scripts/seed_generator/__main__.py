"""CLI entry point: python -m scripts.seed_generator OR python scripts/seed_generator manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback

from .merger import merge_manual_seed
from .orchestrator import generate_seed_from_manifest


def main():
    parser = argparse.ArgumentParser(
        description="Generate seed.toml from manifest.json",
    )
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--merge", help="Path to manual seed.toml overlay to merge")
    args = parser.parse_args()

    # Load manifest
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Load renames from manual file if --merge is specified
    renames = None
    if args.merge:
        merge_path = Path(args.merge)
        if merge_path.exists():
            with open(merge_path, "rb") as f:
                manual = tomllib.load(f)
            renames = manual.get("renames", None)

    # Generate seed (pass renames so builder names are correct before merge)
    toml_str = generate_seed_from_manifest(manifest, renames=renames)

    # Merge manual extras if --merge is specified
    if args.merge:
        toml_str = merge_manual_seed(toml_str, args.merge)

    # Write output
    if args.output:
        Path(args.output).write_text(toml_str.rstrip("\n") + "\n")
        print(f"Seed written to {args.output}", file=sys.stderr)
        top_level = [
            line
            for line in toml_str.split("\n")
            if line.startswith("[builders.") and "." not in line[len("[builders.") : -1]
        ]
        print(f"  Builders generated: {len(top_level)}", file=sys.stderr)
    else:
        print(toml_str)


if __name__ == "__main__":
    main()
