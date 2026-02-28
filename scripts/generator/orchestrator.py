"""Orchestrator — drives the full generation pipeline and writes output files.

This is the top-level coordinator that:
  1. Parses seed.toml + manifest.json
  2. Resolves BuilderSpecs
  3. Groups specs by output module
  4. Generates .py, .pyi, and test files
  5. Writes __init__.py with re-exports
"""

from __future__ import annotations

import ast
import os
import stat
from collections import defaultdict
from pathlib import Path

from code_ir import emit_python, emit_stub

from .module_builder import specs_to_ir_module
from .spec import BuilderSpec, parse_manifest, parse_seed, resolve_builder_specs
from .stubs import specs_to_ir_stub_module
from .tests import specs_to_ir_test_module


# ---------------------------------------------------------------------------
# FILE HELPERS
# ---------------------------------------------------------------------------


def _write_file(path: Path, content: str):
    """Write content to a file.
    If the file exists and is read-only, make it writable first.
    """
    if path.exists():
        # Make it writable if it's read-only
        current_mode = os.stat(path).st_mode
        if not current_mode & stat.S_IWUSR:
            os.chmod(path, current_mode | stat.S_IWUSR)

    path.write_text(content)


def _extract_all_from_file(py_file: Path) -> list[str] | None:
    """Extract __all__ list from a Python file using ast."""
    try:
        tree = ast.parse(py_file.read_text())
    except SyntaxError:
        return None

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, ast.List):
                    names = []
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            names.append(elt.value)
                    return names
    return None


def _discover_manual_exports(output_dir: str) -> list[tuple[str, list[str]]]:
    """Auto-discover manual Python files and their __all__ exports.

    Scans the output directory for .py files that weren't generated,
    and also scans subdirectory packages (*/__init__.py) for exports.
    """
    output_path = Path(output_dir)
    result = []

    # Top-level .py files
    for py_file in sorted(output_path.glob("*.py")):
        if py_file.name == "__init__.py":
            continue

        all_names = _extract_all_from_file(py_file)
        if all_names:
            module_name = f".{py_file.stem}"
            result.append((module_name, all_names))

    # Subdirectory packages (*/__init__.py)
    for init_file in sorted(output_path.glob("*/__init__.py")):
        pkg_name = init_file.parent.name
        all_names = _extract_all_from_file(init_file)
        if all_names:
            module_name = f".{pkg_name}"
            result.append((module_name, all_names))

        # Also scan non-__init__ .py files inside the subpackage
        for sub_file in sorted(init_file.parent.glob("*.py")):
            if sub_file.name == "__init__.py":
                continue
            sub_names = _extract_all_from_file(sub_file)
            if sub_names:
                sub_module = f".{pkg_name}.{sub_file.stem}"
                result.append((sub_module, sub_names))

    return result


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------


def generate_all(
    seed_path: str,
    manifest_path: str,
    output_dir: str,
    test_dir: str | None = None,
    stubs_only: bool = False,
    tests_only: bool = False,
):
    """Main generation pipeline."""
    seed = parse_seed(seed_path)
    manifest = parse_manifest(manifest_path)
    specs = resolve_builder_specs(seed, manifest)

    adk_version = manifest.get("adk_version", "unknown")

    # Group specs by output module
    by_module: dict[str, list[BuilderSpec]] = defaultdict(list)
    for spec in specs:
        by_module[spec.output_module].append(spec)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # --- Generate runtime .py files ---
    if not stubs_only and not tests_only:
        for module_name, module_specs in by_module.items():
            ir_module = specs_to_ir_module(module_specs, manifest=manifest)
            code = emit_python(ir_module)
            filepath = output_path / f"{module_name}.py"
            _write_file(filepath, code)
            print(f"  Generated: {filepath}")

        # Auto-discover manual module exports first (needed for __all__)
        generated_modules = set(by_module.keys())
        manual_exports = _discover_manual_exports(output_dir)
        manual_names: list[str] = []
        manual_import_lines: list[str] = []
        for module_name, names in manual_exports:
            stem = module_name.lstrip(".")
            if stem in generated_modules:
                continue
            for name in names:
                manual_names.append(name)
                manual_import_lines.append(f"from {module_name} import {name}")

        # Generate __init__.py with re-exports
        init_lines = [
            '"""adk-fluent: Fluent builder API for Google ADK."""',
            f"# Auto-generated for google-adk {adk_version}",
            "",
        ]
        for spec in specs:
            init_lines.append(f"from .{spec.output_module} import {spec.name}")

        init_lines.append("")
        init_lines.append("__all__ = [")
        for spec in specs:
            init_lines.append(f'    "{spec.name}",')
        for name in manual_names:
            init_lines.append(f'    "{name}",')
        init_lines.append("]")

        if manual_import_lines:
            init_lines.append("")
            init_lines.append("# --- Manual module exports (auto-discovered from __all__) ---")
            init_lines.extend(manual_import_lines)

        init_path = output_path / "__init__.py"
        _write_file(init_path, "\n".join(init_lines) + "\n")
        print(f"  Generated: {init_path}")

    # --- Generate .pyi stubs ---
    if not tests_only:
        for module_name, module_specs in by_module.items():
            ir_stub_module = specs_to_ir_stub_module(module_specs, adk_version, manifest=manifest)
            stub = emit_stub(ir_stub_module)
            filepath = output_path / f"{module_name}.pyi"
            _write_file(filepath, stub)
            print(f"  Generated: {filepath}")

    # --- Generate test scaffolds ---
    if test_dir and not stubs_only:
        test_path = Path(test_dir)
        test_path.mkdir(parents=True, exist_ok=True)

        for module_name, module_specs in by_module.items():
            ir_test_module = specs_to_ir_test_module(module_specs)
            test_code = emit_python(ir_test_module)
            filepath = test_path / f"test_{module_name}_builder.py"
            _write_file(filepath, test_code)
            print(f"  Generated: {filepath}")

    # --- Summary ---
    print("\n  Summary:")
    print(f"    ADK version:    {adk_version}")
    print(f"    Builders:       {len(specs)}")
    print(f"    Modules:        {len(by_module)}")

    def _count_forwarded(s: BuilderSpec) -> int:
        if s.inspection_mode == "init_signature" and s.init_params:
            return len(
                [
                    p
                    for p in s.init_params
                    if p["name"] not in ("self", "args", "kwargs", "kwds") and p["name"] not in s.skip_fields
                ]
            )
        return len([f for f in s.fields if f["name"] not in s.skip_fields])

    total_methods = sum(
        len(s.aliases) + len(s.deprecated_aliases or {}) + len(s.callback_aliases) + len(s.extras) + _count_forwarded(s)
        for s in specs
        if not s.is_composite and not s.is_standalone
    )
    print(f"    Total methods:  ~{total_methods} (aliases + callbacks + forwarded)")
