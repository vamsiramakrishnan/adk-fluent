"""Golden-file tests for the code generator.

Uses a minimal fixture manifest (no ADK install) to verify the generator
produces deterministic, expected output.  The golden files are stored in
tests/golden/ and can be regenerated with::

    pytest tests/test_generator_golden.py --update-golden
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GOLDEN_DIR = Path(__file__).parent / "golden"


def _generate_outputs(minimal_seed_path, minimal_manifest_path, tmp_path):
    """Run the generator and return dict of {filename: content}."""
    from collections import defaultdict

    from scripts.code_ir import emit_python, emit_stub
    from scripts.generator import parse_manifest, parse_seed, resolve_builder_specs
    from scripts.generator.module_builder import specs_to_ir_module
    from scripts.generator.stubs import specs_to_ir_stub_module
    from scripts.generator.tests import specs_to_ir_test_module

    seed = parse_seed(minimal_seed_path)
    manifest = parse_manifest(minimal_manifest_path)
    specs = resolve_builder_specs(seed, manifest)
    adk_version = manifest.get("adk_version", "unknown")

    by_module: dict[str, list] = defaultdict(list)
    for spec in specs:
        by_module[spec.output_module].append(spec)

    outputs = {}
    for module_name, module_specs in sorted(by_module.items()):
        # Runtime .py
        ir_module = specs_to_ir_module(module_specs, manifest=manifest)
        outputs[f"{module_name}.py"] = emit_python(ir_module)

        # Stub .pyi
        ir_stub = specs_to_ir_stub_module(module_specs, adk_version, manifest=manifest)
        outputs[f"{module_name}.pyi"] = emit_stub(ir_stub)

        # Test scaffold
        ir_test = specs_to_ir_test_module(module_specs)
        outputs[f"test_{module_name}_builder.py"] = emit_python(ir_test)

    return outputs


@pytest.fixture
def generated_outputs(minimal_seed_path, minimal_manifest_path, tmp_path):
    """Generate code from the minimal manifest and return {filename: content}."""
    return _generate_outputs(minimal_seed_path, minimal_manifest_path, tmp_path)


class TestGoldenFiles:
    """Compare generator output against stored golden files."""

    def test_golden_files_exist(self):
        """Verify golden files have been generated at least once."""
        if not GOLDEN_DIR.exists() or not list(GOLDEN_DIR.glob("*")):
            pytest.skip("No golden files yet — run with --update-golden to create them")

    def test_output_is_deterministic(self, minimal_seed_path, minimal_manifest_path, tmp_path):
        """Running the generator twice produces identical output."""
        out1 = _generate_outputs(minimal_seed_path, minimal_manifest_path, tmp_path)
        out2 = _generate_outputs(minimal_seed_path, minimal_manifest_path, tmp_path)
        for filename in out1:
            assert out1[filename] == out2[filename], f"Non-deterministic output for {filename}"

    def test_generated_code_compiles(self, generated_outputs):
        """Every generated .py file is valid Python (compiles without errors)."""
        import ast

        for filename, content in generated_outputs.items():
            if filename.endswith(".py"):
                try:
                    ast.parse(content, filename=filename)
                except SyntaxError as e:
                    pytest.fail(f"{filename} has a syntax error: {e}")

    def test_generated_stubs_compile(self, generated_outputs):
        """Every generated .pyi file is valid Python."""
        import ast

        for filename, content in generated_outputs.items():
            if filename.endswith(".pyi"):
                try:
                    ast.parse(content, filename=filename)
                except SyntaxError as e:
                    pytest.fail(f"{filename} has a syntax error: {e}")

    def test_every_builder_has_build_method(self, generated_outputs):
        """Every generated .py file contains a build() method."""
        for filename, content in generated_outputs.items():
            if filename.endswith(".py") and not filename.startswith("test_"):
                assert "def build(self)" in content, f"{filename} missing build() method"

    def test_golden_match(self, generated_outputs):
        """Generated output matches golden files on disk."""
        if not GOLDEN_DIR.exists() or not list(GOLDEN_DIR.glob("*")):
            pytest.skip("No golden files yet — run with --update-golden to create them")

        for filename, content in sorted(generated_outputs.items()):
            golden_path = GOLDEN_DIR / filename
            if not golden_path.exists():
                pytest.fail(f"Golden file missing: {golden_path}. Run with --update-golden")
            expected = golden_path.read_text()
            assert content == expected, (
                f"Golden file mismatch for {filename}. "
                f"Run `pytest tests/test_generator_golden.py --update-golden` to update."
            )

    def test_no_extra_golden_files(self, generated_outputs):
        """No stale golden files that no longer correspond to generator output."""
        if not GOLDEN_DIR.exists():
            pytest.skip("No golden files yet")
        golden_files = {p.name for p in GOLDEN_DIR.glob("*") if not p.name.startswith(".")}
        generated_files = set(generated_outputs.keys())
        extra = golden_files - generated_files
        assert not extra, f"Stale golden files: {extra}. Delete them or run with --update-golden."


# ---------------------------------------------------------------------------
# SEED GENERATOR GOLDEN TEST
# ---------------------------------------------------------------------------


class TestSeedGeneratorGolden:
    """Verify seed generation is deterministic."""

    def test_seed_generation_deterministic(self, minimal_manifest):
        """Generating seed.toml twice from the same manifest produces identical output (modulo timestamp)."""
        import re

        from scripts.seed_generator import generate_seed_from_manifest

        out1 = generate_seed_from_manifest(minimal_manifest)
        out2 = generate_seed_from_manifest(minimal_manifest)
        # Strip generated_at timestamps (they'll differ by microseconds)
        ts_re = re.compile(r'^generated_at = ".*"$', re.MULTILINE)
        assert ts_re.sub("", out1) == ts_re.sub("", out2)

    def test_seed_is_valid_toml(self, minimal_manifest):
        """Generated seed.toml is valid TOML."""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        from scripts.seed_generator import generate_seed_from_manifest

        toml_str = generate_seed_from_manifest(minimal_manifest)
        parsed = tomllib.loads(toml_str)
        assert "builders" in parsed
        assert "global" in parsed


# ---------------------------------------------------------------------------
# --update-golden FIXTURE
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _maybe_update_golden(request, minimal_seed_path, minimal_manifest_path, tmp_path):
    """If --update-golden is passed, regenerate and write golden files."""
    if not request.config.getoption("--update-golden", default=False):
        return

    outputs = _generate_outputs(minimal_seed_path, minimal_manifest_path, tmp_path)
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    # Remove stale golden files
    for existing in GOLDEN_DIR.glob("*"):
        if existing.name not in outputs and not existing.name.startswith("."):
            existing.unlink()

    for filename, content in outputs.items():
        (GOLDEN_DIR / filename).write_text(content)

    print(f"\n  Updated {len(outputs)} golden files in {GOLDEN_DIR}/")
