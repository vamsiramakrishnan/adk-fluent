#!/usr/bin/env python3
"""
Cookbook example generator for adk-fluent.

Auto-generates runnable cookbook example stubs from seed.toml + manifest.json.
Each generated file follows the NATIVE / FLUENT / ASSERT pattern and serves as:
  1. A live equivalence test (collected by conftest.py)
  2. Input for doc_generator.py → cookbook markdown
  3. A starting point for hand-crafted examples

Usage:
    # Generate stubs for all builders that don't have a cookbook yet
    python scripts/cookbook_generator.py seeds/seed.toml manifest.json

    # Preview what would be generated (dry-run)
    python scripts/cookbook_generator.py seeds/seed.toml manifest.json --dry-run

    # Force overwrite existing files
    python scripts/cookbook_generator.py seeds/seed.toml manifest.json --force

    # Generate for a specific builder
    python scripts/cookbook_generator.py seeds/seed.toml manifest.json --only Agent

    # Start numbering from a specific index
    python scripts/cookbook_generator.py seeds/seed.toml manifest.json --start-index 30
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent

# Import shared parsing from generator
sys.path.insert(0, str(Path(__file__).parent))
from generator import parse_seed, parse_manifest, resolve_builder_specs, BuilderSpec


# ---------------------------------------------------------------------------
# TEMPLATE RENDERING
# ---------------------------------------------------------------------------

def _render_native_section(spec: BuilderSpec) -> str:
    """Render the NATIVE ADK section for a builder."""
    if spec.is_composite:
        return (
            f"# Native ADK: {spec.name} is a composite builder with no single ADK class.\n"
            f"# It orchestrates multiple ADK components."
        )
    if spec.is_standalone:
        return (
            f"# Native ADK has no direct equivalent for {spec.name}.\n"
            f"# This is an adk-fluent convenience builder."
        )

    short = spec.source_class_short
    module = spec.source_class.rsplit(".", 1)[0] if "." in spec.source_class else spec.source_class

    lines = [f"from {module} import {short}"]
    lines.append("")

    # Constructor args
    ctor_args = []
    for arg in spec.constructor_args:
        if arg == "name":
            ctor_args.append(f'    name="example_{spec.name.lower()}"')
        else:
            # Find type from fields
            field_info = next((f for f in spec.fields if f["name"] == arg), None)
            type_str = field_info["type_str"] if field_info else "str"
            if "str" in type_str:
                ctor_args.append(f'    {arg}="example_value"')
            elif "int" in type_str:
                ctor_args.append(f"    {arg}=1")
            elif "float" in type_str:
                ctor_args.append(f"    {arg}=1.0")
            elif "bool" in type_str:
                ctor_args.append(f"    {arg}=True")
            elif "list" in type_str.lower():
                ctor_args.append(f"    {arg}=[]")
            elif "dict" in type_str.lower():
                ctor_args.append(f"    {arg}={{}}")
            else:
                ctor_args.append(f"    {arg}=None  # type: {type_str}")

    # Add common aliased fields
    for fluent_name, field_name in sorted(spec.aliases.items()):
        if field_name in spec.constructor_args:
            continue
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        if field_info:
            type_str = field_info["type_str"]
            if "str" in type_str:
                ctor_args.append(f'    {field_name}="example_value"')
            elif "int" in type_str:
                ctor_args.append(f"    {field_name}=1")

    if ctor_args:
        lines.append(f"native = {short}(")
        lines.append(",\n".join(ctor_args))
        lines.append(")")
    else:
        lines.append(f"native = {short}()")

    return "\n".join(lines)


def _render_fluent_section(spec: BuilderSpec) -> str:
    """Render the FLUENT adk-fluent section for a builder."""
    lines = [f"from adk_fluent import {spec.name}"]
    lines.append("")

    chain_parts = []

    # Constructor
    if "name" in spec.constructor_args:
        chain_parts.append(f'{spec.name}("example_{spec.name.lower()}")')
    else:
        other_args = [a for a in spec.constructor_args if a != "name"]
        if other_args:
            arg_strs = []
            for a in other_args:
                field_info = next((f for f in spec.fields if f["name"] == a), None)
                type_str = field_info["type_str"] if field_info else "str"
                if "str" in type_str:
                    arg_strs.append(f'"{a}_value"')
                else:
                    arg_strs.append(f"None")
            chain_parts.append(f"{spec.name}({', '.join(arg_strs)})")
        else:
            chain_parts.append(f"{spec.name}()")

    # Aliased methods
    for fluent_name, field_name in sorted(spec.aliases.items()):
        if field_name in spec.constructor_args:
            continue
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        if field_info:
            type_str = field_info["type_str"]
            if "str" in type_str:
                chain_parts.append(f'.{fluent_name}("example_value")')
            elif "int" in type_str:
                chain_parts.append(f".{fluent_name}(1)")
        else:
            chain_parts.append(f'.{fluent_name}("example_value")')

    # Build
    if not spec.is_composite and not spec.is_standalone:
        chain_parts.append(".build()")

    if len(chain_parts) <= 2:
        lines.append("fluent = " + "".join(chain_parts))
    else:
        lines.append("fluent = (")
        lines.append("    " + chain_parts[0])
        for part in chain_parts[1:]:
            lines.append("    " + part)
        lines.append(")")

    return "\n".join(lines)


def _render_assert_section(spec: BuilderSpec) -> str:
    """Render the ASSERT equivalence section for a builder."""
    if spec.is_composite or spec.is_standalone:
        return f"assert fluent is not None\nassert fluent._config[\"name\"] is not None"

    lines = [
        "assert type(native) == type(fluent)",
    ]

    # Check name if available
    if "name" in spec.constructor_args:
        lines.append(f'assert fluent.name == "example_{spec.name.lower()}"')

    # Check aliased fields
    for fluent_name, field_name in sorted(spec.aliases.items()):
        if field_name in spec.constructor_args:
            continue
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        if field_info and "str" in field_info["type_str"]:
            lines.append(f'assert fluent.{field_name} == "example_value"')
            break  # One sample assertion is enough

    return "\n".join(lines)


def generate_cookbook(spec: BuilderSpec) -> str:
    """Generate a complete cookbook file for a builder spec."""
    title = _spec_title(spec)

    native = _render_native_section(spec)
    fluent = _render_fluent_section(spec)
    assertion = _render_assert_section(spec)

    return f'"""{title}"""\n\n# --- NATIVE ---\n{native}\n\n# --- FLUENT ---\n{fluent}\n\n# --- ASSERT ---\n{assertion}\n'


def _spec_title(spec: BuilderSpec) -> str:
    """Generate a human-readable title for a builder spec."""
    if spec.is_composite:
        return f"{spec.name} (Composite Builder)"
    if spec.is_standalone:
        return f"{spec.name} (Standalone Builder)"
    return f"{spec.name} Builder"


# ---------------------------------------------------------------------------
# FILE MANAGEMENT
# ---------------------------------------------------------------------------

def _existing_cookbook_builders(cookbook_dir: Path) -> set[str]:
    """Scan existing cookbook files to determine which builders are already covered."""
    covered = set()
    for py_file in cookbook_dir.glob("*.py"):
        if py_file.name == "conftest.py":
            continue
        text = py_file.read_text()
        # Check imports for builder names
        for line in text.split("\n"):
            if "from adk_fluent import" in line:
                imports = line.split("import", 1)[1].strip()
                for name in imports.split(","):
                    name = name.strip()
                    if name:
                        covered.add(name)
    return covered


def _next_index(cookbook_dir: Path, start: int = 30) -> int:
    """Find the next available cookbook file index."""
    existing = set()
    for py_file in cookbook_dir.glob("[0-9][0-9]_*.py"):
        try:
            idx = int(py_file.name[:2])
            existing.add(idx)
        except ValueError:
            pass
    idx = start
    while idx in existing:
        idx += 1
    return idx


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------

def generate_all_cookbooks(
    seed_path: str,
    manifest_path: str,
    cookbook_dir: str = "examples/cookbook",
    dry_run: bool = False,
    force: bool = False,
    only: str | None = None,
    start_index: int = 30,
) -> None:
    """Generate cookbook example stubs for all builders."""
    seed = parse_seed(seed_path)
    manifest = parse_manifest(manifest_path)
    specs = resolve_builder_specs(seed, manifest)

    out_dir = Path(cookbook_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Find already-covered builders
    covered = _existing_cookbook_builders(out_dir) if not force else set()

    # Filter specs
    if only:
        specs = [s for s in specs if s.name == only]
        if not specs:
            print(f"  No builder named '{only}' found in seed.", file=sys.stderr)
            sys.exit(1)

    # Skip builders that already have cookbook coverage
    to_generate = [s for s in specs if s.name not in covered]

    if not to_generate:
        print("  All builders already have cookbook examples. Nothing to generate.")
        return

    print(f"  Found {len(to_generate)} builders needing cookbook examples:")
    for spec in to_generate:
        print(f"    - {spec.name}")

    if dry_run:
        print("\n  Dry run — no files written.")
        for spec in to_generate:
            print(f"\n  === {spec.name} ===")
            print(generate_cookbook(spec))
        return

    # Generate files
    idx = _next_index(out_dir, start_index)
    generated = []
    for spec in to_generate:
        filename = f"{idx:02d}_{spec.name.lower()}_builder.py"
        filepath = out_dir / filename
        content = generate_cookbook(spec)
        filepath.write_text(content)
        generated.append(filepath)
        print(f"  Generated: {filepath}")
        idx += 1

    print(f"\n  Generated {len(generated)} cookbook examples.")
    print(f"  Run: pytest {cookbook_dir}/ -v  to verify they pass.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate cookbook example stubs from seed + manifest"
    )
    parser.add_argument("seed", help="Path to seed.toml")
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument(
        "--cookbook-dir", default="examples/cookbook",
        help="Output directory for cookbook files (default: examples/cookbook)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview generated files without writing"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing cookbook files"
    )
    parser.add_argument(
        "--only", type=str, default=None,
        help="Generate only for a specific builder name"
    )
    parser.add_argument(
        "--start-index", type=int, default=30,
        help="Starting file index for generated examples (default: 30)"
    )
    args = parser.parse_args()

    generate_all_cookbooks(
        seed_path=args.seed,
        manifest_path=args.manifest,
        cookbook_dir=args.cookbook_dir,
        dry_run=args.dry_run,
        force=args.force,
        only=args.only,
        start_index=args.start_index,
    )


if __name__ == "__main__":
    main()
