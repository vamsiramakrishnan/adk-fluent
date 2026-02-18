#!/usr/bin/env python3
"""
IR NODE GENERATOR
=================
Reads manifest.json and generates frozen dataclass IR nodes for ADK agent types.

Maps ADK classes to IR node names:
    LlmAgent        -> AgentNode
    SequentialAgent  -> SequenceNode
    ParallelAgent    -> ParallelNode
    LoopAgent        -> LoopNode

Each generated node is a @dataclass(frozen=True) with:
    - name: str as the first required field
    - All ADK fields with defaults (mapped to frozen-friendly types)
    - callbacks merged into a single dict field
    - Extension fields: writes_keys, reads_keys, produces_type, consumes_type

Usage:
    python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Which ADK classes to generate IR nodes for, and what to name them.
CLASS_MAP: dict[str, str] = {
    "LlmAgent": "AgentNode",
    "SequentialAgent": "SequenceNode",
    "ParallelAgent": "ParallelNode",
    "LoopAgent": "LoopNode",
}

# Fields to skip (internal ADK implementation details).
SKIP_FIELDS: set[str] = {
    "parent_agent",
    "canonical_model",
    "model_config",
}

# Field renames (ADK name -> IR name).
FIELD_RENAMES: dict[str, str] = {
    "sub_agents": "children",
}

# Fields whose is_callback=True should be merged into a single
# `callbacks: dict[str, tuple[Callable, ...]]` field.
# We detect callback fields from the manifest by checking is_callback,
# BUT we exclude certain fields that are really typed values
# (like `instruction`, `tools`).
CALLBACK_VALUE_FIELDS: set[str] = {
    "instruction",
    "global_instruction",
    "static_instruction",
    "tools",
}


# ---------------------------------------------------------------------------
# TYPE MAPPING
# ---------------------------------------------------------------------------

def map_type_to_ir(field: dict) -> str:
    """Map a manifest field type to a frozen-friendly IR type annotation."""
    name = field["name"]
    type_str = field["type_str"]
    is_list = field.get("is_list", False)

    # Renamed fields
    ir_name = FIELD_RENAMES.get(name, name)

    # sub_agents -> children: tuple of nodes
    if ir_name == "children":
        return "tuple"

    # List fields -> tuples for frozen friendliness
    if is_list:
        return "tuple"

    # Everything else: use Any as a flexible default
    return "Any"


def default_for_ir(field: dict) -> str:
    """Return the default value expression for a field in the IR node."""
    name = field["name"]
    ir_name = FIELD_RENAMES.get(name, name)

    if ir_name == "children":
        return "()"

    if field.get("is_list", False):
        return "()"

    raw_default = field.get("default")

    if raw_default is None:
        # Required field in ADK, but we want defaults in IR
        type_str = field["type_str"]
        if "str" in type_str.lower():
            return '""'
        if "int" in type_str.lower():
            return "0"
        if "float" in type_str.lower():
            return "0.0"
        if "bool" in type_str.lower():
            return "False"
        return "None"

    # Handle manifest default representations
    if raw_default == "None":
        return "None"
    if raw_default == "list()":
        return "()"
    if raw_default in ("True", "False"):
        return raw_default
    if raw_default.startswith("'") or raw_default.startswith('"'):
        return raw_default

    # Numeric defaults
    try:
        _ = int(raw_default)
        return raw_default
    except (ValueError, TypeError):
        pass
    try:
        _ = float(raw_default)
        return raw_default
    except (ValueError, TypeError):
        pass

    return "None"


# ---------------------------------------------------------------------------
# GENERATION
# ---------------------------------------------------------------------------

def classify_fields(fields: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split fields into regular fields and callback fields.

    Returns (regular_fields, callback_fields).
    Callback fields are those with is_callback=True that are NOT in
    CALLBACK_VALUE_FIELDS (those are kept as regular fields).
    """
    regular = []
    callbacks = []
    for f in fields:
        if f["name"] in SKIP_FIELDS:
            continue
        if f["name"] == "name":
            continue  # name is always the first required field
        if f.get("is_callback", False) and f["name"] not in CALLBACK_VALUE_FIELDS:
            callbacks.append(f)
        else:
            regular.append(f)
    return regular, callbacks


def gen_node_class(adk_name: str, ir_name: str, cls_data: dict) -> str:
    """Generate a single frozen dataclass IR node."""
    fields = cls_data.get("fields", [])
    doc = cls_data.get("doc", f"IR node for ADK {adk_name}.")

    regular_fields, callback_fields = classify_fields(fields)

    lines = []
    lines.append(f"@dataclass(frozen=True)")
    lines.append(f"class {ir_name}:")
    lines.append(f'    """Generated IR node for ADK {adk_name}.')
    lines.append(f"")
    lines.append(f"    {doc}")
    lines.append(f'    """')
    lines.append(f"")

    # Required field first
    lines.append(f"    name: str")

    # Regular fields with defaults
    for f in regular_fields:
        ir_field_name = FIELD_RENAMES.get(f["name"], f["name"])
        ir_type = map_type_to_ir(f)
        ir_default = default_for_ir(f)
        lines.append(f"    {ir_field_name}: {ir_type} = {ir_default}")

    # Merged callbacks dict
    if callback_fields:
        cb_names = [f["name"] for f in callback_fields]
        lines.append(f"    # Merged callback fields: {', '.join(cb_names)}")
    lines.append(
        '    callbacks: dict[str, tuple[Callable, ...]] = field(default_factory=dict)'
    )

    # adk-fluent extension fields
    lines.append("")
    lines.append("    # --- adk-fluent extension fields ---")
    lines.append("    writes_keys: frozenset[str] = frozenset()")
    lines.append("    reads_keys: frozenset[str] = frozenset()")
    lines.append("    produces_type: type | None = None")
    lines.append("    consumes_type: type | None = None")

    lines.append("")
    return "\n".join(lines)


def gen_full_module(manifest: dict) -> str:
    """Generate the complete _ir_generated.py module."""
    classes = {cls["name"]: cls for cls in manifest.get("classes", [])}

    timestamp = datetime.now(timezone.utc).isoformat()
    adk_version = manifest.get("adk_version", "unknown")

    header_lines = [
        '"""Auto-generated IR node types for ADK agent classes.',
        "",
        "DO NOT EDIT MANUALLY. This file is regenerated by:",
        "    python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py",
        "",
        f"Generated from google-adk {adk_version}",
        f"Timestamp: {timestamp}",
        '"""',
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass, field",
        "from typing import Any, Callable, Union",
        "",
        "from adk_fluent._ir import (",
        "    TransformNode, TapNode, FallbackNode, RaceNode,",
        "    GateNode, MapOverNode, TimeoutNode, RouteNode,",
        "    TransferNode,",
        ")",
        "",
        "__all__ = [",
    ]

    # Add node names to __all__
    for ir_name in CLASS_MAP.values():
        header_lines.append(f'    "{ir_name}",')
    header_lines.append('    "FullNode",')
    header_lines.append("]")
    header_lines.append("")
    header_lines.append("")

    body_parts = []

    # Generate each node class
    for adk_name, ir_name in CLASS_MAP.items():
        cls_data = classes.get(adk_name)
        if cls_data is None:
            print(
                f"WARNING: {adk_name} not found in manifest, skipping {ir_name}",
                file=sys.stderr,
            )
            continue
        body_parts.append(gen_node_class(adk_name, ir_name, cls_data))

    # Generate FullNode type union
    generated_names = list(CLASS_MAP.values())
    hand_written_names = [
        "TransformNode", "TapNode", "FallbackNode", "RaceNode",
        "GateNode", "MapOverNode", "TimeoutNode", "RouteNode",
        "TransferNode",
    ]
    all_node_names = generated_names + hand_written_names

    union_lines = [
        "# ======================================================================",
        "# Full Node type union (generated + hand-written)",
        "# ======================================================================",
        "",
        "FullNode = Union[",
    ]
    for i, name in enumerate(all_node_names):
        comma = "," if i < len(all_node_names) - 1 else ","
        union_lines.append(f"    {name}{comma}")
    union_lines.append("]")
    union_lines.append("")

    return "\n".join(header_lines) + "\n".join(body_parts) + "\n" + "\n".join(union_lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate frozen dataclass IR nodes from ADK manifest"
    )
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument(
        "--output",
        default="src/adk_fluent/_ir_generated.py",
        help="Output file path (default: src/adk_fluent/_ir_generated.py)",
    )
    args = parser.parse_args()

    # Read manifest
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Generate
    code = gen_full_module(manifest)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code)

    print(f"  Generated: {output_path}")
    print(f"  ADK version: {manifest.get('adk_version', 'unknown')}")
    print(f"  Nodes: {', '.join(CLASS_MAP.values())}")


if __name__ == "__main__":
    main()
