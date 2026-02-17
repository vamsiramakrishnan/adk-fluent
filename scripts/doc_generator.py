#!/usr/bin/env python3
"""
Documentation generator for adk-fluent.

Reads manifest + seed (via generator's BuilderSpec) and produces:
  1. API reference Markdown (one per module)
  2. Cookbook Markdown (from annotated example files)
  3. Migration guide (class + field mapping tables)

Usage:
    python scripts/doc_generator.py seeds/seed.toml manifest.json
    python scripts/doc_generator.py seeds/seed.toml manifest.json --api-only
    python scripts/doc_generator.py seeds/seed.toml manifest.json --cookbook-only
    python scripts/doc_generator.py seeds/seed.toml manifest.json --migration-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Import BuilderSpec resolution from generator (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from generator import parse_seed, parse_manifest, resolve_builder_specs, BuilderSpec


# ---------------------------------------------------------------------------
# API REFERENCE GENERATION
# ---------------------------------------------------------------------------

def gen_api_reference_for_builder(spec: BuilderSpec) -> str:
    """Generate Markdown API reference for a single builder.

    Sections:
      - Header with description
      - Constructor args table
      - Alias methods
      - Callback methods
      - Extra methods
      - Terminal methods
      - Forwarded fields table
    """
    lines: list[str] = []

    # --- Header ---
    lines.append(f"# {spec.name}")
    lines.append("")
    if spec.is_composite:
        lines.append(f"> Composite builder (no single ADK class)")
    elif spec.is_standalone:
        lines.append(f"> Standalone builder (no ADK class)")
    else:
        lines.append(f"> Fluent builder for `{spec.source_class}`")
    lines.append("")
    if spec.doc:
        lines.append(spec.doc)
        lines.append("")

    # --- Constructor ---
    if spec.constructor_args:
        lines.append("## Constructor")
        lines.append("")
        lines.append(f"```python")
        args_str = ", ".join(spec.constructor_args)
        lines.append(f"{spec.name}({args_str})")
        lines.append("```")
        lines.append("")
        lines.append("| Argument | Type |")
        lines.append("|----------|------|")
        for arg in spec.constructor_args:
            # Try to find type from manifest fields or init_params
            arg_type = "str"
            if spec.inspection_mode == "init_signature" and spec.init_params:
                param_info = next((p for p in spec.init_params if p["name"] == arg), None)
                if param_info:
                    arg_type = param_info.get("type_str", "str")
            else:
                field_info = next((f for f in spec.fields if f["name"] == arg), None)
                if field_info:
                    arg_type = field_info["type_str"]
            lines.append(f"| `{arg}` | `{arg_type}` |")
        lines.append("")

    # --- Alias Methods ---
    if spec.aliases:
        lines.append("## Methods")
        lines.append("")
        for fluent_name, field_name in spec.aliases.items():
            field_info = next((f for f in spec.fields if f["name"] == field_name), None)
            type_hint = field_info["type_str"] if field_info else "Any"
            doc = spec.field_docs.get(field_name, "")
            if not doc and field_info:
                doc = field_info.get("description", "")
            if not doc:
                doc = f"Set the `{field_name}` field."
            lines.append(f"### `.{fluent_name}(value)`")
            lines.append("")
            lines.append(f"- **Type:** `{type_hint}`")
            lines.append(f"- **Maps to:** `{field_name}`")
            lines.append(f"- {doc}")
            lines.append("")

    # --- Callback Methods ---
    if spec.callback_aliases:
        lines.append("## Callbacks")
        lines.append("")
        for short_name, full_name in spec.callback_aliases.items():
            lines.append(f"### `.{short_name}(*fns)`")
            lines.append("")
            lines.append(f"Append callback(s) to `{full_name}`. Multiple calls accumulate.")
            lines.append("")
            lines.append(f"### `.{short_name}_if(condition, fn)`")
            lines.append("")
            lines.append(f"Append callback to `{full_name}` only if `condition` is `True`.")
            lines.append("")

    # --- Extra Methods ---
    if spec.extras:
        lines.append("## Extra Methods")
        lines.append("")
        for extra in spec.extras:
            name = extra["name"]
            sig = extra.get("signature", "(self) -> Self")
            doc = extra.get("doc", "")
            # Clean up signature for display
            display_sig = sig.replace("(self, ", "(").replace("(self)", "()")
            lines.append(f"### `.{name}{display_sig}`")
            lines.append("")
            if doc:
                lines.append(doc)
                lines.append("")

    # --- Terminal Methods ---
    if spec.terminals:
        lines.append("## Terminal Methods")
        lines.append("")
        for terminal in spec.terminals:
            t_name = terminal["name"]
            if "signature" in terminal:
                display_sig = terminal["signature"].replace("(self, ", "(").replace("(self)", "()")
                lines.append(f"### `.{t_name}{display_sig}`")
            elif "returns" in terminal:
                lines.append(f"### `.{t_name}() -> {terminal['returns']}`")
            else:
                lines.append(f"### `.{t_name}()`")
            lines.append("")
            t_doc = terminal.get("doc", "")
            if t_doc:
                lines.append(t_doc)
                lines.append("")

    # --- Forwarded Fields ---
    if not spec.is_composite and not spec.is_standalone:
        aliased_fields = set(spec.aliases.values())
        callback_fields = set(spec.callback_aliases.values())
        extra_names = {e["name"] for e in spec.extras}

        forwarded = []
        if spec.inspection_mode == "init_signature" and spec.init_params:
            for param in spec.init_params:
                pname = param["name"]
                if pname in ("self", "args", "kwargs", "kwds"):
                    continue
                if pname in spec.skip_fields:
                    continue
                if pname in aliased_fields:
                    continue
                if pname in callback_fields:
                    continue
                if pname in extra_names:
                    continue
                if pname in spec.constructor_args:
                    continue
                forwarded.append((pname, param.get("type_str", "Any")))
        else:
            for field in spec.fields:
                fname = field["name"]
                if fname in spec.skip_fields:
                    continue
                if fname in aliased_fields:
                    continue
                if fname in callback_fields:
                    continue
                if fname in extra_names:
                    continue
                if fname in spec.constructor_args:
                    continue
                forwarded.append((fname, field["type_str"]))

        if forwarded:
            lines.append("## Forwarded Fields")
            lines.append("")
            lines.append("These fields are available via `__getattr__` forwarding.")
            lines.append("")
            lines.append("| Field | Type |")
            lines.append("|-------|------|")
            for fname, ftype in forwarded:
                lines.append(f"| `.{fname}(value)` | `{ftype}` |")
            lines.append("")

    return "\n".join(lines)


def gen_api_reference_module(specs: list[BuilderSpec], module_name: str) -> str:
    """Generate API reference Markdown for an entire module (multiple builders)."""
    parts: list[str] = []
    parts.append(f"# Module: `{module_name}`")
    parts.append("")

    for i, spec in enumerate(specs):
        if i > 0:
            parts.append("---")
            parts.append("")
        parts.append(gen_api_reference_for_builder(spec))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# COOKBOOK PROCESSOR
# ---------------------------------------------------------------------------

def process_cookbook_file(filepath: str) -> dict:
    """Parse an annotated cookbook example into sections."""
    text = Path(filepath).read_text()

    # Extract title from module docstring
    title_match = re.match(r'"""(.+?)"""', text, re.DOTALL)
    title = title_match.group(1).strip() if title_match else Path(filepath).stem

    sections = {"native": "", "fluent": "", "assertion": ""}
    current = None
    for line in text.split("\n"):
        if "# --- NATIVE ---" in line:
            current = "native"
            continue
        elif "# --- FLUENT ---" in line:
            current = "fluent"
            continue
        elif "# --- ASSERT ---" in line:
            current = "assertion"
            continue
        if current:
            sections[current] += line + "\n"

    return {
        "title": title,
        "native": sections["native"].strip(),
        "fluent": sections["fluent"].strip(),
        "assertion": sections["assertion"].strip(),
        "filename": Path(filepath).name,
    }


def cookbook_to_markdown(parsed: dict) -> str:
    """Convert parsed cookbook data to Markdown with side-by-side comparison."""
    lines: list[str] = []

    lines.append(f"# {parsed['title']}")
    lines.append("")
    lines.append(f"_Source: `{parsed['filename']}`_")
    lines.append("")

    if parsed["native"]:
        lines.append("## Native ADK")
        lines.append("")
        lines.append("```python")
        lines.append(parsed["native"])
        lines.append("```")
        lines.append("")

    if parsed["fluent"]:
        lines.append("## adk-fluent")
        lines.append("")
        lines.append("```python")
        lines.append(parsed["fluent"])
        lines.append("```")
        lines.append("")

    if parsed["assertion"]:
        lines.append("## Equivalence")
        lines.append("")
        lines.append("```python")
        lines.append(parsed["assertion"])
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MIGRATION GUIDE GENERATOR
# ---------------------------------------------------------------------------

def gen_migration_guide(specs: list[BuilderSpec]) -> str:
    """Generate a migration guide with class and field mapping tables."""
    lines: list[str] = []

    lines.append("# Migration Guide: Native ADK to adk-fluent")
    lines.append("")
    lines.append("This guide maps every ADK class to its adk-fluent builder equivalent,")
    lines.append("and lists field name mappings for builders that define aliases.")
    lines.append("")

    # --- Class mapping table ---
    lines.append("## Class Mapping")
    lines.append("")
    lines.append("| Native ADK Class | adk-fluent Builder | Import |")
    lines.append("|------------------|-------------------|--------|")

    for spec in sorted(specs, key=lambda s: s.name):
        if spec.is_composite or spec.is_standalone:
            lines.append(f"| _(composite)_ | `{spec.name}` | `from adk_fluent import {spec.name}` |")
        else:
            lines.append(
                f"| `{spec.source_class_short}` | `{spec.name}` | "
                f"`from adk_fluent import {spec.name}` |"
            )
    lines.append("")

    # --- Per-builder field mapping ---
    builders_with_aliases = [s for s in specs if s.aliases or s.callback_aliases]

    if builders_with_aliases:
        lines.append("## Field Mappings")
        lines.append("")
        lines.append("The tables below show fluent method names that differ from the native field names.")
        lines.append("")

        for spec in sorted(builders_with_aliases, key=lambda s: s.name):
            lines.append(f"### {spec.name}")
            lines.append("")
            lines.append("| Native Field | Fluent Method | Notes |")
            lines.append("|-------------|---------------|-------|")

            for fluent_name, field_name in sorted(spec.aliases.items()):
                lines.append(f"| `{field_name}` | `.{fluent_name}()` | alias |")

            for short_name, full_name in sorted(spec.callback_aliases.items()):
                lines.append(f"| `{full_name}` | `.{short_name}()` | callback, additive |")

            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------

def generate_docs(
    seed_path: str,
    manifest_path: str,
    output_dir: str = "docs/generated",
    cookbook_dir: str = "examples/cookbook",
    api_only: bool = False,
    cookbook_only: bool = False,
    migration_only: bool = False,
) -> None:
    """Main documentation generation orchestrator."""
    seed = parse_seed(seed_path)
    manifest = parse_manifest(manifest_path)
    specs = resolve_builder_specs(seed, manifest)

    out = Path(output_dir)

    # Group specs by output_module
    by_module: dict[str, list[BuilderSpec]] = defaultdict(list)
    for spec in specs:
        by_module[spec.output_module].append(spec)

    # --- API Reference ---
    if not cookbook_only and not migration_only:
        api_dir = out / "api"
        api_dir.mkdir(parents=True, exist_ok=True)

        for module_name, module_specs in sorted(by_module.items()):
            md = gen_api_reference_module(module_specs, module_name)
            filepath = api_dir / f"{module_name}.md"
            filepath.write_text(md)
            print(f"  Generated: {filepath}")

    # --- Cookbook ---
    if not api_only and not migration_only:
        cookbook_path = Path(cookbook_dir)
        if cookbook_path.exists():
            cookbook_out = out / "cookbook"
            cookbook_out.mkdir(parents=True, exist_ok=True)

            for py_file in sorted(cookbook_path.glob("*.py")):
                parsed = process_cookbook_file(str(py_file))
                md = cookbook_to_markdown(parsed)
                md_file = cookbook_out / f"{py_file.stem}.md"
                md_file.write_text(md)
                print(f"  Generated: {md_file}")
        else:
            print(f"  Cookbook directory {cookbook_dir} not found, skipping.")

    # --- Migration Guide ---
    if not api_only and not cookbook_only:
        migration_dir = out / "migration"
        migration_dir.mkdir(parents=True, exist_ok=True)

        md = gen_migration_guide(specs)
        filepath = migration_dir / "from-native-adk.md"
        filepath.write_text(md)
        print(f"  Generated: {filepath}")

    # --- Summary ---
    print(f"\n  Documentation generated in {out}/")
    print(f"    Builders:  {len(specs)}")
    print(f"    Modules:   {len(by_module)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate adk-fluent documentation from seed + manifest"
    )
    parser.add_argument("seed", help="Path to seed.toml")
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument(
        "--output-dir", default="docs/generated",
        help="Output directory (default: docs/generated)"
    )
    parser.add_argument(
        "--cookbook-dir", default="examples/cookbook",
        help="Cookbook examples directory (default: examples/cookbook)"
    )
    parser.add_argument(
        "--api-only", action="store_true",
        help="Generate API reference only"
    )
    parser.add_argument(
        "--cookbook-only", action="store_true",
        help="Generate cookbook only"
    )
    parser.add_argument(
        "--migration-only", action="store_true",
        help="Generate migration guide only"
    )
    args = parser.parse_args()

    generate_docs(
        seed_path=args.seed,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        cookbook_dir=args.cookbook_dir,
        api_only=args.api_only,
        cookbook_only=args.cookbook_only,
        migration_only=args.migration_only,
    )


if __name__ == "__main__":
    main()
