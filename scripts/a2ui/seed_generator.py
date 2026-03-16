#!/usr/bin/env python3
"""
A2UI SEED GENERATOR
===================
Transforms a2ui_manifest.json into seeds/a2ui_seed.toml — the factory
configuration consumed by the UI code generator.

Pipeline:
    a2ui_manifest.json → a2ui_seed.toml (+ merge a2ui_seed.manual.toml)
                        → a2ui_generator.py → _ui_generated.py

Usage:
    python scripts/a2ui_seed_generator.py a2ui_manifest.json -o seeds/a2ui_seed.toml
    python scripts/a2ui_seed_generator.py a2ui_manifest.json -o seeds/a2ui_seed.toml \
        --merge seeds/a2ui_seed.manual.toml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.shared import camel_to_snake as _camel_to_snake
from scripts.shared import load_manifest, load_toml, write_toml_or_json

# ---------------------------------------------------------------------------
# TYPE MAPPING: A2UI schema types → Python type hints
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "DynamicString": "str | UIBinding",
    "DynamicNumber": "int | float | UIBinding",
    "DynamicBoolean": "bool | UIBinding",
    "DynamicStringList": "list[str] | UIBinding",
    "DynamicValue": "Any",
    "ComponentId": "str",
    "ChildList": "tuple[UIComponent, ...]",
    "Action": "UIAction | str",
    "string": "str",
    "number": "int | float",
    "integer": "int",
    "boolean": "bool",
    "object": "dict[str, Any]",
    "enum": "str",
    "array<string>": "list[str]",
    "array<object>": "list[dict]",
}


def _resolve_python_type(a2ui_type: str) -> str:
    """Map A2UI schema type to Python type hint string."""
    return _TYPE_MAP.get(a2ui_type, "Any")


# ---------------------------------------------------------------------------
# SEED GENERATION
# ---------------------------------------------------------------------------


def generate_seed(manifest: dict, manual: dict | None = None) -> dict:
    """Generate a2ui_seed.toml content from manifest."""
    seed: dict = {
        "meta": {
            "a2ui_version": manifest.get("a2ui_version", "v0.10"),
            "catalog_uri": manifest.get("catalog_uri", ""),
            "scan_timestamp": manifest.get("scan_timestamp", ""),
        },
        "components": [],
        "functions": [],
    }

    # Manual overrides
    factory_renames = {}
    component_aliases = {}
    extra_factories = {}
    if manual:
        factory_renames = manual.get("factory_renames", {})
        component_aliases = manual.get("component_aliases", {})
        extra_factories = manual.get("extra_factories", {})

    # --- Components ---
    for comp in manifest.get("components", []):
        name = comp["name"]
        default_factory = _camel_to_snake(name)
        factory_name = factory_renames.get(default_factory, default_factory)

        # Determine positional (required) and keyword (optional) args
        required_args = []
        optional_args = []
        default_values = {}
        arg_types = {}
        enum_values = {}

        for prop in comp.get("properties", []):
            prop_name = prop["name"]
            prop_type = prop.get("type", "string")
            python_type = _resolve_python_type(prop_type)
            arg_types[prop_name] = python_type

            if prop.get("enum_values"):
                enum_values[prop_name] = prop["enum_values"]

            if prop.get("required"):
                required_args.append(prop_name)
            else:
                optional_args.append(prop_name)
                if prop.get("default") is not None:
                    default_values[prop_name] = prop["default"]

        comp_entry = {
            "name": name,
            "factory_name": factory_name,
            "category": comp.get("category", "unknown"),
            "description": comp.get("description", ""),
            "required_args": required_args,
            "optional_args": optional_args,
            "default_values": default_values,
            "arg_types": arg_types,
            "enum_values": enum_values,
            "has_children": comp.get("supports_children", False),
            "child_mode": comp.get("child_mode"),
            "has_action": comp.get("supports_action", False),
            "has_checks": comp.get("supports_checks", False),
            "has_weight": comp.get("supports_weight", True),
            "has_bind": any(
                p["name"] == "value" and p.get("type", "").startswith("Dynamic") for p in comp.get("properties", [])
            ),
        }
        seed["components"].append(comp_entry)

    # --- Functions ---
    for func in manifest.get("functions", []):
        name = func["name"]
        factory_name = factory_renames.get(name, name)

        args = []
        for arg in func.get("args", []):
            args.append(
                {
                    "name": arg["name"],
                    "type": _resolve_python_type(arg.get("type", "string")),
                    "required": arg.get("required", False),
                    "description": arg.get("description", ""),
                }
            )

        func_entry = {
            "name": name,
            "factory_name": factory_name,
            "category": func.get("category", "unknown"),
            "description": func.get("description", ""),
            "args": args,
            "required_args": func.get("required_args", []),
            "return_type": func.get("return_type", "boolean"),
        }
        seed["functions"].append(func_entry)

    # --- Component aliases ---
    if component_aliases:
        seed["aliases"] = component_aliases

    # --- Extra factories ---
    if extra_factories:
        seed["extra_factories"] = extra_factories

    return seed


# ---------------------------------------------------------------------------
# PROGRAMMATIC ENTRY POINT
# ---------------------------------------------------------------------------


def run(
    *,
    manifest: Path,
    output: Path,
    merge: Path | None = None,
    prefer_json: bool = False,
) -> dict:
    """Run the seed generator programmatically (no sys.argv manipulation).

    Returns the generated seed dict.
    """
    manifest_data = load_manifest(manifest)

    manual = None
    if merge and merge.exists():
        manual = load_toml(merge)

    seed = generate_seed(manifest_data, manual)

    output.parent.mkdir(parents=True, exist_ok=True)
    fmt = write_toml_or_json(seed, output, prefer_json=prefer_json)

    print(
        f"Wrote {output} ({fmt}: {len(seed['components'])} components, {len(seed['functions'])} functions)",
        file=sys.stderr,
    )
    return seed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a2ui_seed.toml from a2ui_manifest.json")
    parser.add_argument("manifest", help="Path to a2ui_manifest.json")
    parser.add_argument("-o", "--output", required=True, help="Output seed file path")
    parser.add_argument(
        "--merge",
        help="Path to manual overrides TOML file (a2ui_seed.manual.toml)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of TOML")
    args = parser.parse_args()

    run(
        manifest=Path(args.manifest),
        output=Path(args.output),
        merge=Path(args.merge) if args.merge else None,
        prefer_json=args.json,
    )


if __name__ == "__main__":
    main()
