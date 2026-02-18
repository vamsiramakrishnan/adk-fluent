#!/usr/bin/env python3
"""
Convert cookbook examples into adk-web-compatible agent folders.

Each cookbook example becomes a folder under examples/ with:
  - agent.py  — extracts the FLUENT section, assigns result to root_agent
  - __init__.py — empty

Only converts examples that produce a buildable agent. Examples that test
pure builder mechanics (serialization, validate, etc.) are skipped.

Usage:
    python scripts/cookbook_to_agents.py                          # Convert all
    python scripts/cookbook_to_agents.py --dry-run                # Preview only
    python scripts/cookbook_to_agents.py --only 28                # Convert one
    python scripts/cookbook_to_agents.py --output-dir examples/   # Custom output
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# PARSING
# ---------------------------------------------------------------------------


def parse_cookbook(filepath: Path) -> dict:
    """Parse a cookbook file into title and sections."""
    text = filepath.read_text()

    # Extract title from docstring
    title_match = re.match(r'"""(.+?)"""', text, re.DOTALL)
    title = title_match.group(1).strip() if title_match else filepath.stem

    sections = {"native": "", "fluent": "", "assert": ""}
    current = None
    for line in text.split("\n"):
        if "# --- NATIVE ---" in line:
            current = "native"
            continue
        elif "# --- FLUENT ---" in line:
            current = "fluent"
            continue
        elif "# --- ASSERT ---" in line:
            current = "assert"
            continue
        if current:
            sections[current] += line + "\n"

    return {"title": title, "filepath": filepath, **sections}


def _find_root_agent_var(fluent_code: str) -> str | None:
    """Find the variable name that holds the main agent/builder in the fluent section.

    Heuristic: the last top-level variable assignment is the root agent,
    unless there's a variable with .build() in which case we prefer that.
    """
    # Find all .build() assignments
    build_vars = re.findall(r"^(\w+)\s*=\s*\([\s\S]*?\.build\(\)\s*\)$", fluent_code, re.MULTILINE)
    if not build_vars:
        build_vars = re.findall(r"^(\w+)\s*=.*\.build\(\)", fluent_code, re.MULTILINE)
    if build_vars:
        return build_vars[-1]  # Last .build() assignment

    # Find the last top-level variable assignment (not imports, not comments)
    # This handles multiline expressions with >>, |, * on subsequent lines
    all_vars = re.findall(r"^(\w+)\s*=\s*(?!.*__)", fluent_code, re.MULTILINE)
    # Filter out common non-agent variables
    skip_names = {"result", "data", "yaml_str", "explanation", "from_yaml", "restored"}
    agent_vars = [v for v in all_vars if v not in skip_names]
    if agent_vars:
        return agent_vars[-1]

    return None


def _needs_build(fluent_code: str, var_name: str) -> bool:
    """Check if the variable needs .build() called on it."""
    # Look for the assignment and check if it already has .build()
    pattern = rf"{var_name}\s*=.*\.build\(\)"
    return not bool(re.search(pattern, fluent_code, re.DOTALL))


def _is_buildable_example(parsed: dict) -> bool:
    """Check if this cookbook example produces a meaningful agent for adk web."""
    fluent = parsed["fluent"].strip()
    if not fluent:
        return False

    # Must have an Agent or workflow builder construction
    if not any(kw in fluent for kw in ["Agent(", "Pipeline(", "FanOut(", "Loop(", "Route(", "@agent("]):
        return False

    # Skip pure StateKey/Artifact examples (no agent at all)
    return (
        "Agent(" in fluent or "Pipeline(" in fluent or "FanOut(" in fluent or "Loop(" in fluent or "@agent(" in fluent
    )


# ---------------------------------------------------------------------------
# AGENT.PY GENERATION
# ---------------------------------------------------------------------------


def generate_agent_py(parsed: dict) -> str | None:
    """Generate an agent.py file from a parsed cookbook example.

    Returns None if the example isn't suitable for adk web.
    """
    if not _is_buildable_example(parsed):
        return None

    fluent_code = parsed["fluent"].strip()
    var_name = _find_root_agent_var(fluent_code)
    if not var_name:
        return None

    title = parsed["title"]
    cookbook_name = parsed["filepath"].stem
    folder_name = _cookbook_to_folder_name(cookbook_name)

    lines = []
    lines.append('"""')
    lines.append(f"{title}")
    lines.append("")
    lines.append(f"Converted from cookbook example: {parsed['filepath'].name}")
    lines.append("")
    lines.append("Usage:")
    lines.append("    cd examples")
    lines.append(f"    adk web {folder_name}")
    lines.append('"""')
    lines.append("")

    # Include any function/class definitions from the native section that
    # are referenced in the fluent section (tools, callbacks)
    native_defs = _extract_referenced_definitions(parsed["native"], fluent_code)
    if native_defs:
        lines.append(native_defs)
        lines.append("")

    # Add the fluent code — inject dotenv after the last import line
    fluent_lines = fluent_code.split("\n")
    last_import_idx = -1
    for i, fl in enumerate(fluent_lines):
        stripped = fl.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            last_import_idx = i
    if last_import_idx >= 0:
        fluent_lines.insert(last_import_idx + 1, "from dotenv import load_dotenv")
        fluent_lines.insert(last_import_idx + 2, "")
        fluent_lines.insert(
            last_import_idx + 3, "load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)"
        )
    lines.append("\n".join(fluent_lines))
    lines.append("")

    # Assign root_agent
    needs_build = _needs_build(fluent_code, var_name)
    if needs_build:
        lines.append(f"root_agent = {var_name}.build()")
    else:
        lines.append(f"root_agent = {var_name}")

    lines.append("")
    return "\n".join(lines)


def _extract_referenced_definitions(native_code: str, fluent_code: str) -> str:
    """Extract function/class definitions from native section that are used in fluent section."""
    if not native_code.strip():
        return ""

    # Parse function/class definitions by tracking indentation
    lines = native_code.split("\n")
    defs: list[tuple[str, list[str]]] = []  # (name, lines)
    current_name = None
    current_lines: list[str] = []

    for line in lines:
        # New top-level def/class
        match = re.match(r"^(def|class)\s+(\w+)", line)
        if match:
            # Save previous definition
            if current_name:
                defs.append((current_name, current_lines))
            current_name = match.group(2)
            current_lines = [line]
        elif current_name is not None:
            # Continuation of current definition (indented or blank)
            if line.strip() == "" or line.startswith("    ") or line.startswith("\t"):
                current_lines.append(line)
            else:
                # Unindented non-def line: end of definition
                defs.append((current_name, current_lines))
                current_name = None
                current_lines = []

    # Save last definition
    if current_name:
        defs.append((current_name, current_lines))

    # Filter to definitions referenced in fluent code
    referenced = []
    for name, def_lines in defs:
        if re.search(rf"\b{name}\b", fluent_code):
            referenced.append("\n".join(def_lines).rstrip())

    if not referenced:
        return ""

    result = "\n# --- Tools & Callbacks ---\n\n"
    result += "\n\n".join(referenced)
    return result


def _cookbook_to_folder_name(stem: str) -> str:
    """Convert cookbook filename stem to folder name.

    '01_simple_agent' -> 'simple_agent'
    '28_real_world_pipeline' -> 'real_world_pipeline'
    """
    # Strip leading number prefix
    return re.sub(r"^\d+_", "", stem)


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------


def convert_all(
    cookbook_dir: str = "examples/cookbook",
    output_dir: str = "examples",
    dry_run: bool = False,
    only: str | None = None,
    force: bool = False,
) -> None:
    """Convert cookbook examples to adk-web-compatible agent folders."""
    cookbook_path = Path(cookbook_dir)
    out_path = Path(output_dir)

    if not cookbook_path.exists():
        print(f"  Cookbook directory {cookbook_dir} not found.", file=sys.stderr)
        sys.exit(1)

    # Collect cookbook files
    files = sorted(cookbook_path.glob("[0-9][0-9]_*.py"))
    if only:
        files = [f for f in files if f.stem.startswith(only) or only in f.stem]

    converted = []
    skipped = []

    for filepath in files:
        parsed = parse_cookbook(filepath)
        agent_py = generate_agent_py(parsed)

        folder_name = _cookbook_to_folder_name(filepath.stem)
        folder_path = out_path / folder_name

        if agent_py is None:
            skipped.append((filepath.name, "not a buildable agent"))
            continue

        if folder_path.exists() and not force:
            skipped.append((filepath.name, f"folder {folder_name}/ already exists"))
            continue

        if dry_run:
            print(f"\n  === {filepath.name} -> {folder_name}/ ===")
            print(agent_py)
            converted.append(filepath.name)
            continue

        # Create folder structure
        folder_path.mkdir(parents=True, exist_ok=True)
        (folder_path / "agent.py").write_text(agent_py)
        (folder_path / "__init__.py").write_text("")
        converted.append(filepath.name)
        print(f"  Created: {folder_path}/agent.py")

    # Summary
    print(f"\n  Converted: {len(converted)}")
    if skipped:
        print(f"  Skipped:   {len(skipped)}")
        for name, reason in skipped:
            print(f"    {name}: {reason}")

    if converted and not dry_run:
        print("\n  Run any agent with:")
        print(f"    cd {output_dir}")
        print("    adk web <folder_name>")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Convert cookbook examples to adk-web-compatible agent folders")
    parser.add_argument(
        "--cookbook-dir", default="examples/cookbook", help="Cookbook examples directory (default: examples/cookbook)"
    )
    parser.add_argument(
        "--output-dir", default="examples", help="Output directory for agent folders (default: examples)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview generated files without writing")
    parser.add_argument("--only", type=str, default=None, help="Convert only files matching this prefix/substring")
    parser.add_argument("--force", action="store_true", help="Overwrite existing folders")
    args = parser.parse_args()

    convert_all(
        cookbook_dir=args.cookbook_dir,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        only=args.only,
        force=args.force,
    )


if __name__ == "__main__":
    main()
