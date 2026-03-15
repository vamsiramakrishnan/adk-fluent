#!/usr/bin/env python3
"""
A2UI CATALOG SCANNER
====================
Introspects A2UI JSON Schema files (basic_catalog.json, common_types.json,
server_to_client.json) and produces a2ui_manifest.json describing every
component, function, theme property, dynamic type, and message type.

This is the A2UI counterpart to scanner.py — it reads the A2UI spec
instead of the ADK Python package.

Pipeline:
    A2UI JSON Schemas → a2ui_manifest.json → a2ui_seed.toml → _ui_generated.py

Usage:
    python scripts/a2ui_scanner.py specification/v0_10/json/ -o a2ui_manifest.json
    python scripts/a2ui_scanner.py specification/v0_10/json/ --summary
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------


@dataclass
class PropertyInfo:
    """A single property on an A2UI component or function."""

    name: str
    type: str  # "string", "enum", "DynamicString", "DynamicNumber", etc.
    required: bool = False
    description: str = ""
    default: Any = None
    enum_values: list[str] | None = None
    ref: str | None = None  # JSON Schema $ref if present
    items_type: str | None = None  # for array properties


@dataclass
class ComponentInfo:
    """Describes a single A2UI catalog component."""

    name: str
    category: str  # "content", "layout", "input"
    description: str = ""
    properties: list[PropertyInfo] = field(default_factory=list)
    required_props: list[str] = field(default_factory=list)
    supports_children: bool = False
    child_mode: str | None = None  # "single", "list", "template", "tabs"
    supports_action: bool = False
    supports_checks: bool = False
    supports_weight: bool = True  # CatalogComponentCommon gives all weight


@dataclass
class FunctionInfo:
    """Describes a single A2UI catalog function."""

    name: str
    category: str  # "validation", "formatting", "logic", "navigation"
    description: str = ""
    args: list[PropertyInfo] = field(default_factory=list)
    required_args: list[str] = field(default_factory=list)
    return_type: str = "boolean"


@dataclass
class ThemeProperty:
    """A theme property."""

    name: str
    type: str
    description: str = ""
    pattern: str | None = None


@dataclass
class A2UIManifest:
    """Complete scan result."""

    a2ui_version: str = "v0.10"
    scan_timestamp: str = ""
    catalog_uri: str = ""
    spec_dir: str = ""
    components: list[ComponentInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    dynamic_types: list[str] = field(default_factory=list)
    theme_properties: list[ThemeProperty] = field(default_factory=list)
    message_types: list[str] = field(default_factory=list)
    common_type_names: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CATEGORIZATION
# ---------------------------------------------------------------------------

CONTENT_COMPONENTS = {"Text", "Image", "Icon", "Video", "AudioPlayer"}
LAYOUT_COMPONENTS = {"Row", "Column", "List", "Card", "Tabs", "Modal", "Divider"}
INPUT_COMPONENTS = {"Button", "TextField", "CheckBox", "ChoicePicker", "Slider", "DateTimeInput"}

VALIDATION_FUNCTIONS = {"required", "regex", "length", "numeric", "email"}
FORMATTING_FUNCTIONS = {"formatString", "formatNumber", "formatCurrency", "formatDate", "pluralize"}
LOGIC_FUNCTIONS = {"and", "or", "not"}
NAVIGATION_FUNCTIONS = {"openUrl"}

# Components that reference Checkable
CHECKABLE_COMPONENTS = {"Button", "TextField", "CheckBox", "ChoicePicker", "Slider", "DateTimeInput"}

# Components that have an action property
ACTION_COMPONENTS = {"Button"}

# Children patterns
CHILD_LIST_COMPONENTS = {"Row", "Column", "List"}  # children: ChildList
CHILD_SINGLE_COMPONENTS = {"Card", "Modal"}  # child: ComponentId (or trigger/content)
CHILD_TABS_COMPONENTS = {"Tabs"}  # tabs: [{title, child}]
CHILD_BUTTON_COMPONENTS = {"Button"}  # child: ComponentId (label child)


# ---------------------------------------------------------------------------
# TYPE RESOLUTION
# ---------------------------------------------------------------------------

def _resolve_type(prop_schema: dict, prop_name: str) -> str:
    """Resolve a JSON Schema property definition to a human-readable type name."""
    if "$ref" in prop_schema:
        ref = prop_schema["$ref"]
        # Extract type name from $ref
        if "DynamicString" in ref:
            return "DynamicString"
        if "DynamicNumber" in ref:
            return "DynamicNumber"
        if "DynamicBoolean" in ref:
            return "DynamicBoolean"
        if "DynamicStringList" in ref:
            return "DynamicStringList"
        if "DynamicValue" in ref:
            return "DynamicValue"
        if "ComponentId" in ref:
            return "ComponentId"
        if "ChildList" in ref:
            return "ChildList"
        if "Action" in ref:
            return "Action"
        if "DataBinding" in ref:
            return "DataBinding"
        if "FunctionCall" in ref:
            return "FunctionCall"
        if "Checkable" in ref:
            return "Checkable"
        # Generic ref
        return ref.split("/")[-1]

    if "const" in prop_schema:
        return f"const:{prop_schema['const']}"

    if "enum" in prop_schema:
        return "enum"

    if "allOf" in prop_schema:
        # Check each allOf member for a $ref
        for item in prop_schema["allOf"]:
            if "$ref" in item:
                return _resolve_type(item, prop_name)
        return "allOf"

    schema_type = prop_schema.get("type", "any")
    if schema_type == "array":
        items = prop_schema.get("items", {})
        if "$ref" in items:
            return f"array<{_resolve_type(items, prop_name)}>"
        return f"array<{items.get('type', 'any')}>"

    if schema_type == "object":
        return "object"

    return schema_type


def _categorize_component(name: str) -> str:
    """Categorize a component as content, layout, or input."""
    if name in CONTENT_COMPONENTS:
        return "content"
    if name in LAYOUT_COMPONENTS:
        return "layout"
    if name in INPUT_COMPONENTS:
        return "input"
    return "unknown"


def _categorize_function(name: str) -> str:
    """Categorize a function."""
    if name in VALIDATION_FUNCTIONS:
        return "validation"
    if name in FORMATTING_FUNCTIONS:
        return "formatting"
    if name in LOGIC_FUNCTIONS:
        return "logic"
    if name in NAVIGATION_FUNCTIONS:
        return "navigation"
    return "unknown"


def _get_child_mode(name: str) -> str | None:
    """Determine child mode for a component."""
    if name in CHILD_LIST_COMPONENTS:
        return "list"
    if name in CHILD_TABS_COMPONENTS:
        return "tabs"
    if name in CHILD_SINGLE_COMPONENTS:
        return "single"
    if name in CHILD_BUTTON_COMPONENTS:
        return "single"
    return None


# ---------------------------------------------------------------------------
# SCANNER
# ---------------------------------------------------------------------------


def scan_component(name: str, schema: dict) -> ComponentInfo:
    """Extract component info from its JSON Schema definition."""
    comp = ComponentInfo(
        name=name,
        category=_categorize_component(name),
        supports_children=name in CHILD_LIST_COMPONENTS | CHILD_SINGLE_COMPONENTS | CHILD_TABS_COMPONENTS | CHILD_BUTTON_COMPONENTS,
        child_mode=_get_child_mode(name),
        supports_action=name in ACTION_COMPONENTS,
        supports_checks=name in CHECKABLE_COMPONENTS,
    )

    # Walk allOf to collect properties
    all_props: dict[str, dict] = {}
    all_required: set[str] = set()

    for schema_part in schema.get("allOf", []):
        ref = schema_part.get("$ref", "")
        if "Checkable" in ref:
            comp.supports_checks = True
            continue
        if "CatalogComponentCommon" in ref:
            comp.supports_weight = True
            continue
        if "ComponentCommon" in ref:
            continue

        # Inline type object with properties
        props = schema_part.get("properties", {})
        required = schema_part.get("required", [])
        desc = schema_part.get("description", "")
        if desc and not comp.description:
            comp.description = desc

        for prop_name, prop_schema in props.items():
            if prop_name == "component":
                continue  # Skip discriminator
            all_props[prop_name] = prop_schema

        all_required.update(required)
        all_required.discard("component")

    # Build property list
    for prop_name, prop_schema in all_props.items():
        prop_type = _resolve_type(prop_schema, prop_name)
        prop_info = PropertyInfo(
            name=prop_name,
            type=prop_type,
            required=prop_name in all_required,
            description=prop_schema.get("description", ""),
            default=prop_schema.get("default"),
            enum_values=prop_schema.get("enum"),
            ref=prop_schema.get("$ref"),
        )

        # Handle array items
        if prop_schema.get("type") == "array" and "items" in prop_schema:
            items = prop_schema["items"]
            if "$ref" in items:
                prop_info.items_type = _resolve_type(items, prop_name)
            elif items.get("type") == "object":
                prop_info.items_type = "object"
            else:
                prop_info.items_type = items.get("type", "any")

        comp.properties.append(prop_info)

    comp.required_props = [p for p in all_required if p != "component"]
    return comp


def scan_function(name: str, schema: dict) -> FunctionInfo:
    """Extract function info from its JSON Schema definition."""
    func = FunctionInfo(
        name=name,
        category=_categorize_function(name),
        description=schema.get("description", ""),
    )

    # Get return type
    ret_prop = schema.get("properties", {}).get("returnType", {})
    if "const" in ret_prop:
        func.return_type = ret_prop["const"]

    # Get args
    args_schema = schema.get("properties", {}).get("args", {})
    args_props = args_schema.get("properties", {})
    args_required = set(args_schema.get("required", []))

    for arg_name, arg_schema in args_props.items():
        arg_type = _resolve_type(arg_schema, arg_name)
        func.args.append(PropertyInfo(
            name=arg_name,
            type=arg_type,
            required=arg_name in args_required,
            description=arg_schema.get("description", ""),
            default=arg_schema.get("default"),
        ))

    func.required_args = [a for a in args_required]
    return func


def scan_theme(theme_schema: dict) -> list[ThemeProperty]:
    """Extract theme properties from the catalog $defs."""
    result = []
    for name, prop in theme_schema.get("properties", {}).items():
        result.append(ThemeProperty(
            name=name,
            type=prop.get("type", "string"),
            description=prop.get("description", ""),
            pattern=prop.get("pattern"),
        ))
    return result


def scan_catalog(spec_dir: Path) -> A2UIManifest:
    """Scan A2UI JSON Schema files and produce a manifest."""
    catalog_path = spec_dir / "basic_catalog.json"
    common_path = spec_dir / "common_types.json"
    s2c_path = spec_dir / "server_to_client.json"

    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}")
    if not common_path.exists():
        raise FileNotFoundError(f"Common types not found: {common_path}")

    catalog = json.loads(catalog_path.read_text())
    common = json.loads(common_path.read_text())

    manifest = A2UIManifest(
        scan_timestamp=datetime.now(UTC).isoformat(),
        catalog_uri=catalog.get("$id", ""),
        spec_dir=str(spec_dir),
    )

    # Extract version from catalog or server_to_client
    if s2c_path.exists():
        s2c = json.loads(s2c_path.read_text())
        # Version from createSurface schema
        cs = s2c.get("$defs", {}).get("CreateSurfaceMessage", {})
        version_prop = cs.get("properties", {}).get("version", {})
        if "const" in version_prop:
            manifest.a2ui_version = version_prop["const"]

        # Message types
        for ref_item in s2c.get("oneOf", []):
            ref = ref_item.get("$ref", "")
            msg_name = ref.split("/")[-1].replace("Message", "")
            # camelCase conversion
            msg_camel = msg_name[0].lower() + msg_name[1:]
            manifest.message_types.append(msg_camel)

    # Scan components
    components = catalog.get("components", {})
    for comp_name, comp_schema in components.items():
        manifest.components.append(scan_component(comp_name, comp_schema))

    # Scan functions
    functions = catalog.get("functions", {})
    for func_name, func_schema in functions.items():
        manifest.functions.append(scan_function(func_name, func_schema))

    # Scan theme
    theme_schema = catalog.get("$defs", {}).get("theme", {})
    manifest.theme_properties = scan_theme(theme_schema)

    # Dynamic types from common_types
    defs = common.get("$defs", {})
    manifest.dynamic_types = [
        name for name in defs
        if name.startswith("Dynamic")
    ]
    manifest.common_type_names = list(defs.keys())

    return manifest


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------


def manifest_to_dict(manifest: A2UIManifest) -> dict:
    """Convert manifest to JSON-serializable dict."""
    return asdict(manifest)


def print_summary(manifest: A2UIManifest) -> None:
    """Print a human-readable summary."""
    print(f"A2UI Spec Scanner — {manifest.a2ui_version}")
    print(f"  Catalog: {manifest.catalog_uri}")
    print(f"  Scanned: {manifest.scan_timestamp}")
    print()
    print(f"  Components: {len(manifest.components)}")
    by_cat: dict[str, list[str]] = {}
    for c in manifest.components:
        by_cat.setdefault(c.category, []).append(c.name)
    for cat, names in sorted(by_cat.items()):
        print(f"    {cat}: {', '.join(names)}")
    print()
    print(f"  Functions: {len(manifest.functions)}")
    by_cat2: dict[str, list[str]] = {}
    for f in manifest.functions:
        by_cat2.setdefault(f.category, []).append(f.name)
    for cat, names in sorted(by_cat2.items()):
        print(f"    {cat}: {', '.join(names)}")
    print()
    print(f"  Dynamic types: {', '.join(manifest.dynamic_types)}")
    print(f"  Theme properties: {', '.join(t.name for t in manifest.theme_properties)}")
    print(f"  Message types: {', '.join(manifest.message_types)}")
    print(f"  Common types: {', '.join(manifest.common_type_names)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan A2UI JSON Schema spec files → a2ui_manifest.json"
    )
    parser.add_argument(
        "spec_dir",
        help="Directory containing A2UI JSON Schema files (basic_catalog.json, etc.)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print human-readable summary instead of JSON",
    )
    args = parser.parse_args()

    spec_dir = Path(args.spec_dir)
    manifest = scan_catalog(spec_dir)

    if args.summary:
        print_summary(manifest)
        return

    result = json.dumps(manifest_to_dict(manifest), indent=2)

    if args.output:
        Path(args.output).write_text(result + "\n")
        print(f"Wrote {args.output} ({len(manifest.components)} components, "
              f"{len(manifest.functions)} functions)", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
