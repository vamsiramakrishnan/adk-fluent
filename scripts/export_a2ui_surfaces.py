#!/usr/bin/env python3
"""
Export all A2UI surfaces from cookbooks into standalone JSON files.

Mechanism: imports each A2UI cookbook, finds all UISurface and UIComponent
objects created at module scope, compiles them via compile_surface(), and
writes the result to visual/surfaces/ as individual JSON files.

Usage:
    python scripts/export_a2ui_surfaces.py                    # Export all
    python scripts/export_a2ui_surfaces.py --only 70          # Export one
    python scripts/export_a2ui_surfaces.py --output-dir path  # Custom output
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_module(filepath: Path):
    """Load a Python module from path without executing __main__ blocks."""
    spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
    mod = importlib.util.module_from_spec(spec)
    # Suppress print output during import
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"  Warning: {filepath.name} raised {type(e).__name__}: {e}", file=sys.stderr)
            return None
    return mod


def _extract_surfaces(mod) -> list[dict]:
    """Extract all UISurface and UIComponent objects from a module's namespace."""
    from adk_fluent._ui import UIComponent, UISurface, compile_surface

    surfaces = []

    for name, obj in vars(mod).items():
        if name.startswith("_"):
            continue

        if isinstance(obj, UISurface):
            try:
                messages = compile_surface(obj)
                surfaces.append(
                    {
                        "name": obj.name,
                        "var": name,
                        "messages": messages,
                    }
                )
            except Exception as e:
                print(f"    Warning: failed to compile surface '{name}': {e}", file=sys.stderr)

        elif isinstance(obj, UIComponent):
            # Wrap bare components in a default surface
            try:
                temp_surface = UISurface(name=name, root=obj)
                messages = compile_surface(temp_surface)
                surfaces.append(
                    {
                        "name": name,
                        "var": name,
                        "messages": messages,
                    }
                )
            except Exception as e:
                print(f"    Warning: failed to compile component '{name}': {e}", file=sys.stderr)

    return surfaces


def export_all(
    cookbook_dir: str = "examples/cookbook",
    output_dir: str = "visual/surfaces",
    only: str | None = None,
) -> list[dict]:
    """Export A2UI surfaces from cookbook examples.

    Returns an index of exported surfaces.
    """
    cookbook_path = Path(cookbook_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Find A2UI cookbook files (70-79 range, or any with a2ui in name)
    files = sorted(cookbook_path.glob("[0-9][0-9]_*a2ui*.py"))
    if only:
        files = [f for f in files if f.stem.startswith(only) or only in f.stem]

    if not files:
        print("No A2UI cookbook files found.", file=sys.stderr)
        return []

    index = []
    file_counter = 0

    for filepath in files:
        print(f"  Processing {filepath.name}...")
        mod = _load_module(filepath)
        if mod is None:
            continue

        surfaces = _extract_surfaces(mod)
        if not surfaces:
            print(f"    No surfaces found in {filepath.name}")
            continue

        for surface in surfaces:
            file_counter += 1
            filename = f"{filepath.stem}__{surface['var']}.json"
            out_file = out_path / filename

            export_data = {
                "source": filepath.name,
                "variable": surface["var"],
                "surface_name": surface["name"],
                "messages": surface["messages"],
            }

            out_file.write_text(json.dumps(export_data, indent=2))
            print(f"    Exported: {filename} ({len(surface['messages'])} messages)")

            index.append(
                {
                    "id": f"{filepath.stem}__{surface['var']}",
                    "name": surface["name"],
                    "file": filename,
                    "source": filepath.name,
                    "message_count": len(surface["messages"]),
                }
            )

    # Write index
    index_file = out_path / "_index.json"
    index_file.write_text(json.dumps(index, indent=2))
    print(f"\n  Exported {file_counter} surfaces to {out_path}/")
    print(f"  Index: {index_file}")

    return index


def main():
    parser = argparse.ArgumentParser(description="Export A2UI surfaces from cookbooks")
    parser.add_argument("--cookbook-dir", default="examples/cookbook", help="Cookbook directory")
    parser.add_argument("--output-dir", default="visual/surfaces", help="Output directory")
    parser.add_argument("--only", default=None, help="Filter by filename prefix")
    args = parser.parse_args()

    export_all(
        cookbook_dir=args.cookbook_dir,
        output_dir=args.output_dir,
        only=args.only,
    )


if __name__ == "__main__":
    main()
