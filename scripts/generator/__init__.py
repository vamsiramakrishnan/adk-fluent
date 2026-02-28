"""ADK-FLUENT GENERATOR — modular code generation pipeline.

Combines manifest.json (machine truth from scanner) with seed.toml (human intent)
to produce:
  1. Runtime .py files  — builder classes with __getattr__ forwarding
  2. Type stub .pyi files — full IDE autocomplete and pyright/mypy support
  3. Test scaffolds — equivalence tests for every builder

Package structure:
    spec.py             — BuilderSpec dataclass, seed/manifest parsing
    imports.py          — Import resolution and type discovery
    sig_parser.py       — Signature string → Param list conversion
    ir_builders.py      — BuilderSpec → ClassNode IR construction
    module_builder.py   — BuilderSpec[] → ModuleNode (runtime .py)
    stubs.py            — BuilderSpec[] → ModuleNode (.pyi stubs)
    tests.py            — BuilderSpec[] → ModuleNode (test scaffolds)
    type_normalization.py — Type annotation cleanup for generated code
    orchestrator.py     — Top-level pipeline: parse → generate → write

Usage:
    python scripts/generator.py seed.toml manifest.json --output-dir src/adk_fluent
    python scripts/generator.py seed.toml manifest.json --stubs-only
    python scripts/generator.py seed.toml manifest.json --tests-only --test-dir tests/
"""

# Ensure scripts/ dir is on sys.path so that `from code_ir import ...` resolves
# regardless of where Python is invoked from (project root vs scripts/).
import sys as _sys
from pathlib import Path as _Path

_scripts_dir = str(_Path(__file__).resolve().parent.parent)
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)

# Ensure module identity: whether loaded as 'scripts.generator' or 'generator'
_sys.modules.setdefault("generator", _sys.modules[__name__])

# Public API — preserves backward compatibility with the old monolithic generator.py
from .ir_builders import spec_to_ir
from .module_builder import specs_to_ir_module
from .orchestrator import generate_all
from .spec import BuilderSpec, parse_manifest, parse_seed, resolve_builder_specs
from .stubs import specs_to_ir_stub_module
from .tests import spec_to_ir_test, specs_to_ir_test_module

__all__ = [
    "BuilderSpec",
    "generate_all",
    "parse_manifest",
    "parse_seed",
    "resolve_builder_specs",
    "spec_to_ir",
    "spec_to_ir_test",
    "specs_to_ir_module",
    "specs_to_ir_stub_module",
    "specs_to_ir_test_module",
]
