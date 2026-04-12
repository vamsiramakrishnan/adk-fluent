"""Shared utilities for the adk-fluent codegen pipeline.

Used by both the Core ADK pipeline (scanner, seed_generator, generator)
and the A2UI pipeline (a2ui/scanner, a2ui/seed_generator, a2ui/generator).

Extract common patterns here to avoid duplication across pipelines.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# TOML/JSON Loading
# ---------------------------------------------------------------------------

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore[assignment]


def load_toml_or_json(path: Path) -> dict[str, Any]:
    """Load a file as JSON first, falling back to TOML.

    This is the standard loading pattern for seed files which may be
    in either format.
    """
    text = path.read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return tomllib.loads(text)


def load_manifest(path: Path) -> dict[str, Any]:
    """Load a JSON manifest file with existence check."""
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def write_toml_or_json(
    data: dict[str, Any],
    path: Path,
    *,
    prefer_json: bool = False,
) -> str:
    """Write data as TOML (preferred) or JSON fallback.

    Returns the format name ("TOML" or "JSON") that was written.
    """
    if prefer_json or tomli_w is None:
        path.write_text(json.dumps(data, indent=2) + "\n")
        if not prefer_json and tomli_w is None:
            print(
                "Warning: tomli_w not installed, wrote JSON instead of TOML",
                file=sys.stderr,
            )
        return "JSON"
    tomli_w.dump(data, path.open("wb"))
    return "TOML"


# ---------------------------------------------------------------------------
# String Utilities
# ---------------------------------------------------------------------------


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case.

    Examples:
        TextField → text_field
        DateTimeInput → date_time_input
        BarChart → bar_chart
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# ---------------------------------------------------------------------------
# Pipeline Stage Protocol (documentation, not enforced)
# ---------------------------------------------------------------------------
#
# Each pipeline stage (scan, seed, generate) follows this contract:
#
#   1. A `main()` function that uses argparse and sys.argv (for standalone CLI)
#   2. A `run(*, key=val)` function that accepts kwargs (for programmatic use)
#
# The unified CLI dispatcher (__main__.py) should call `run()` with parsed
# args — never manipulate sys.argv.
#
# Scanner:   run(spec_dir=Path, output=Path|None, summary=bool) → manifest
# Seed:      run(manifest=Path, output=Path, merge=Path|None, json=bool) → seed
# Generator: run(seed=Path, output_dir=Path, test_dir=Path) → None
