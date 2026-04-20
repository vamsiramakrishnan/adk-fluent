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
import json
import os
import stat
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from code_ir import emit_python, emit_stub, emit_typescript

from .module_builder import specs_to_ir_module
from .spec import BuilderSpec, parse_manifest, parse_seed, resolve_builder_specs
from .stubs import specs_to_ir_stub_module
from .tests import specs_to_ir_test_module

# ---------------------------------------------------------------------------
# GENERATION STATS
# ---------------------------------------------------------------------------


@dataclass
class GenerationStats:
    """Structured statistics about a generation run."""

    adk_version: str = "unknown"
    builder_count: int = 0
    module_count: int = 0
    stub_count: int = 0
    test_count: int = 0
    total_methods: int = 0
    total_extras: int = 0
    total_aliases: int = 0
    total_callbacks: int = 0
    total_fields_forwarded: int = 0
    builders_by_module: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def to_json(self) -> str:
        """Serialize stats to JSON."""
        return json.dumps(asdict(self), indent=2)

    def print_summary(self, *, verbose: bool = False):
        """Print a human-readable summary to stdout."""
        print("\n  Generation Stats:")
        print(f"    ADK version:      {self.adk_version}")
        print(f"    Builders:         {self.builder_count}")
        print(f"    Modules:          {self.module_count}")
        print(f"    Stubs:            {self.stub_count}")
        print(f"    Test files:       {self.test_count}")
        print(f"    Total methods:    ~{self.total_methods}")
        print(f"      - aliases:      {self.total_aliases}")
        print(f"      - callbacks:    {self.total_callbacks}")
        print(f"      - extras:       {self.total_extras}")
        print(f"      - forwarded:    {self.total_fields_forwarded}")
        print(f"    Elapsed:          {self.elapsed_seconds:.2f}s")

        if verbose:
            print("\n    Builders by module:")
            for mod, count in sorted(self.builders_by_module.items()):
                print(f"      {mod}: {count}")


def _compute_stats(
    specs: list[BuilderSpec], by_module: dict[str, list[BuilderSpec]], adk_version: str
) -> GenerationStats:
    """Compute generation statistics from resolved specs."""

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

    total_aliases = 0
    total_callbacks = 0
    total_extras = 0
    total_forwarded = 0

    for s in specs:
        if s.is_composite or s.is_standalone:
            continue
        total_aliases += len(s.aliases) + len(s.deprecated_aliases or {})
        total_callbacks += len(s.callback_aliases)
        total_extras += len(s.extras)
        total_forwarded += _count_forwarded(s)

    return GenerationStats(
        adk_version=adk_version,
        builder_count=len(specs),
        module_count=len(by_module),
        total_methods=total_aliases + total_callbacks + total_extras + total_forwarded,
        total_aliases=total_aliases,
        total_callbacks=total_callbacks,
        total_extras=total_extras,
        total_fields_forwarded=total_forwarded,
        builders_by_module={mod: len(specs_list) for mod, specs_list in sorted(by_module.items())},
    )


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
    stats_json: str | None = None,
    target: str = "python",
    ts_output_dir: str | None = None,
) -> GenerationStats:
    """Main generation pipeline.

    Returns a GenerationStats object with structured metrics.
    If *stats_json* is a file path, write the stats as JSON to that file.

    Parameters
    ----------
    target : ``"python"``, ``"typescript"``, or ``"both"``.
        Selects which language emitter to drive. Defaults to ``"python"``
        for backwards compatibility.
    ts_output_dir : str | None
        Output directory for the TypeScript builders. Required when
        ``target`` includes TypeScript. Typically ``ts/src/builders``.
    """
    t0 = time.monotonic()

    if target not in {"python", "typescript", "both"}:
        raise ValueError(
            f"Invalid target {target!r}; expected python|typescript|both"
        )
    if target in {"typescript", "both"} and not ts_output_dir:
        raise ValueError(
            "ts_output_dir is required when target includes typescript"
        )

    emit_python_files = target in {"python", "both"}
    emit_typescript_files = target in {"typescript", "both"}

    seed = parse_seed(seed_path)
    manifest = parse_manifest(manifest_path)
    specs = resolve_builder_specs(seed, manifest)

    adk_version = manifest.get("adk_version", "unknown")

    # Group specs by output module
    by_module: dict[str, list[BuilderSpec]] = defaultdict(list)
    for spec in specs:
        by_module[spec.output_module].append(spec)

    output_path = Path(output_dir)
    if emit_python_files:
        output_path.mkdir(parents=True, exist_ok=True)

    stats = _compute_stats(specs, by_module, adk_version)

    # ------------------------------------------------------------------
    # TypeScript emission — runs alongside (or instead of) Python emission.
    # ------------------------------------------------------------------
    # Modules whose TS counterpart is hand-written. These two live outside
    # the codegen loop because their TS source carries patterns the emitter
    # cannot round-trip today:
    #
    # * ``workflow`` — ``registerWorkflow()`` calls at module bottom that
    #   break a circular import in ``builder-base``, custom ``.build()``
    #   bodies that call ``_applyNativeHooks``, and ``Fallback``'s private
    #   ``_children`` field. These are TS-specific shapes with no Python
    #   counterpart in the IR.
    # * ``agent`` — the A2UI auto-wiring logic inside ``.ui()`` plus the
    #   TS-side ``sub_agents``/``_children`` registration. ``runtime_helper``
    #   extras (``.instruct()``, ``.context()``, ``.guard()``, ``.ui()``,
    #   …) are already mapped via ``_INLINE_HELPERS`` in ``ts_emitter.py``,
    #   but the A2UI-specific wiring around ``.ui()`` still needs a
    #   hand-written escape hatch.
    _TS_SKIP_MODULES = {"workflow", "agent"}

    if emit_typescript_files:
        ts_path = Path(ts_output_dir)  # type: ignore[arg-type]
        ts_path.mkdir(parents=True, exist_ok=True)
        ts_module_names: list[str] = []

        for module_name, module_specs in by_module.items():
            if module_name in _TS_SKIP_MODULES:
                # Hand-written TS module — preserve user-authored content.
                ts_module_names.append(module_name)
                print(f"  Skipped (hand-written): {ts_path / f'{module_name}.ts'}")
                continue
            ir_module = specs_to_ir_module(module_specs, manifest=manifest)
            ts_code = emit_typescript(ir_module)
            ts_filepath = ts_path / f"{module_name}.ts"
            _write_file(ts_filepath, ts_code)
            ts_module_names.append(module_name)
            print(f"  Generated: {ts_filepath}")

        # Emit a barrel `index.ts` re-exporting every generated builder.
        index_lines = [
            "// Auto-generated by the adk-fluent codegen pipeline.",
            "// Do not edit by hand — re-run `just ts-generate`.",
            "",
        ]
        for module_name in sorted(ts_module_names):
            index_lines.append(f'export * from "./{module_name}.js";')
        index_lines.append("")
        index_path = ts_path / "index.ts"
        _write_file(index_path, "\n".join(index_lines))
        print(f"  Generated: {index_path}")

        if not emit_python_files:
            stats.elapsed_seconds = round(time.monotonic() - t0, 3)
            stats.print_summary()
            if stats_json:
                Path(stats_json).write_text(stats.to_json() + "\n")
                print(f"\n  Stats written to: {stats_json}")
            return stats

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
                # Skip private symbols — they're implementation internals
                # that shouldn't be part of the public API
                if name.startswith("_"):
                    continue
                manual_names.append(name)
                manual_import_lines.append(f"from {module_name} import {name}")

        # Generate __init__.py with lazy imports via __getattr__
        # This avoids loading heavy ADK dependencies until actually needed.
        init_lines = [
            '"""adk-fluent: Fluent builder API for Google ADK."""',
            f"# Auto-generated for google-adk {adk_version}",
            "",
        ]

        # Build the lazy import mapping: name -> (module, name)
        lazy_map: dict[str, tuple[str, str]] = {}
        seen_names: set[str] = set()

        for spec in specs:
            lazy_map[spec.name] = (f".{spec.output_module}", spec.name)
            seen_names.add(spec.name)

        for name in manual_names:
            if name not in seen_names:
                # Find the module for this manual name
                for module_name, names in manual_exports:
                    stem = module_name.lstrip(".")
                    if stem in generated_modules:
                        continue
                    if name in names:
                        lazy_map[name] = (module_name, name)
                        break
                seen_names.add(name)

        # Named-word aliases for the single-letter namespace classes.
        # Every single-letter namespace (S, C, P, G, M, T, A, E, R, H, UI) has
        # a named-word alias that resolves to the same class. These must be
        # applied last so they override any name collision (e.g. ``Middleware``
        # Protocol from ``.middleware`` is shadowed by ``M`` the namespace).
        _NAMED_ALIASES: list[tuple[str, str, str]] = [
            ("State", "._transforms", "S"),
            ("Context", "._context", "C"),
            ("Prompt", "._prompt", "P"),
            ("Guard", "._guards", "G"),
            ("Middleware", "._middleware", "M"),
            ("Tool", "._tools", "T"),
            ("Artifact", "._artifacts", "A"),
            ("Eval", "._eval", "E"),
            ("Reactive", "._reactor", "R"),
            ("Harness", "._harness", "H"),
            ("Ui", ".prelude", "UI"),
        ]
        for alias, mod, attr in _NAMED_ALIASES:
            lazy_map[alias] = (mod, attr)
            seen_names.add(alias)

        # Emit __all__
        init_lines.append("__all__ = [")
        for name in lazy_map:
            init_lines.append(f'    "{name}",')
        init_lines.append("]")

        # Emit the lazy import map
        init_lines.append("")
        init_lines.append("_LAZY_IMPORTS: dict[str, tuple[str, str]] = {")
        for name, (mod, attr) in lazy_map.items():
            init_lines.append(f'    "{name}": ("{mod}", "{attr}"),')
        init_lines.append("}")

        # Detect subpackage names that conflict with exported names.
        # When importing e.g. CompilationResult from .compile, Python auto-sets
        # adk_fluent.compile = <module>, shadowing the lazy function export.
        subpkg_names = {
            d.name
            for d in output_path.iterdir()
            if d.is_dir() and (d / "__init__.py").exists() and not d.name.startswith("_")
        }
        subpkg_conflicts = sorted(subpkg_names & set(lazy_map.keys()))
        if subpkg_conflicts:
            init_lines.append("")
            init_lines.append("# Names that conflict with subpackage names — need special resolution")
            init_lines.append("_SUBPACKAGE_EXPORTS: dict[str, tuple[str, str]] = {")
            for name in subpkg_conflicts:
                mod, attr = lazy_map[name]
                init_lines.append(f'    "{name}": ("{mod}", "{attr}"),')
            init_lines.append("}")

        # Emit __getattr__ for lazy loading
        init_lines.append("")
        init_lines.append("")
        init_lines.append("def _fix_subpackage_shadows():")
        init_lines.append('    """Fix attributes shadowed by subpackage auto-imports.')
        init_lines.append("")
        init_lines.append("    Python's import system auto-sets parent.child = <module>")
        init_lines.append("    when importing parent.child. This can shadow our lazy")
        init_lines.append("    function/class exports when a subpackage name matches")
        init_lines.append("    an exported name (e.g. 'compile' is both a subpackage")
        init_lines.append("    and an exported function).")
        init_lines.append('    """')
        init_lines.append("    import types")
        init_lines.append("")
        init_lines.append('    _spx = globals().get("_SUBPACKAGE_EXPORTS", {})')
        init_lines.append("    for _name, (_mod, _attr) in _spx.items():")
        init_lines.append("        _val = globals().get(_name)")
        init_lines.append("        if isinstance(_val, types.ModuleType):")
        init_lines.append("            globals()[_name] = getattr(_val, _attr)")
        init_lines.append("")
        init_lines.append("")
        init_lines.append("def __getattr__(name: str):")
        init_lines.append("    if name in _LAZY_IMPORTS:")
        init_lines.append("        import importlib")
        init_lines.append("")
        init_lines.append("        _mod, _attr = _LAZY_IMPORTS[name]")
        init_lines.append("        module = importlib.import_module(_mod, __name__)")
        init_lines.append("        value = getattr(module, _attr)")
        init_lines.append("        globals()[name] = value")
        init_lines.append("        # Importing a submodule may auto-set subpackage names")
        init_lines.append("        # in our namespace — fix any that got shadowed.")
        init_lines.append("        _fix_subpackage_shadows()")
        init_lines.append("        return value")
        init_lines.append('    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")')
        init_lines.append("")
        init_lines.append("")
        init_lines.append("def __dir__():")
        init_lines.append("    return __all__")

        init_path = output_path / "__init__.py"
        _write_file(init_path, "\n".join(init_lines) + "\n")
        print(f"  Generated: {init_path}")

        # Generate __init__.pyi so pyright resolves lazy imports correctly
        pyi_lines = [
            '"""adk-fluent: Fluent builder API for Google ADK."""',
            f"# Auto-generated for google-adk {adk_version}",
            "",
        ]

        # Group specs by module for organized imports
        for module_name_key in sorted(by_module.keys()):
            module_spec_names = sorted(s.name for s in by_module[module_name_key])
            for spec_name in module_spec_names:
                pyi_lines.append(f"from .{module_name_key} import {spec_name} as {spec_name}")

        # Re-export manual modules
        for module_name, names in manual_exports:
            stem = module_name.lstrip(".")
            if stem in generated_modules:
                continue
            for name in names:
                if name.startswith("_"):
                    continue
                pyi_lines.append(f"from {module_name} import {name} as {name}")

        pyi_lines.append("")
        pyi_lines.append("__all__ = [")
        for name in lazy_map:
            pyi_lines.append(f'    "{name}",')
        pyi_lines.append("]")

        init_pyi_path = output_path / "__init__.pyi"
        _write_file(init_pyi_path, "\n".join(pyi_lines) + "\n")
        print(f"  Generated: {init_pyi_path}")

    # --- Generate .pyi stubs ---
    if not tests_only:
        for module_name, module_specs in by_module.items():
            ir_stub_module = specs_to_ir_stub_module(module_specs, adk_version, manifest=manifest)
            stub = emit_stub(ir_stub_module)
            filepath = output_path / f"{module_name}.pyi"
            _write_file(filepath, stub)
            print(f"  Generated: {filepath}")
        stats.stub_count = len(by_module)

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
        stats.test_count = len(by_module)

    stats.elapsed_seconds = round(time.monotonic() - t0, 3)
    stats.print_summary()

    # Write stats JSON if requested
    if stats_json:
        Path(stats_json).write_text(stats.to_json() + "\n")
        print(f"\n  Stats written to: {stats_json}")

    return stats
