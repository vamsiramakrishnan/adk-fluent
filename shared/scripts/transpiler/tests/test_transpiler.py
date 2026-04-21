"""Tests for the Python-to-TypeScript transpiler."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure transpiler is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from transpiler import transpile


class TestSimpleExpressions:
    """Test basic expression transpilation."""

    def test_agent_constructor(self):
        result = transpile('Agent("helper", "gemini-2.5-flash")')
        assert 'new Agent("helper", "gemini-2.5-flash")' in result

    def test_method_chain(self):
        result = transpile('Agent("x").instruct("Be helpful.").build()')
        assert '.instruct("Be helpful.")' in result
        assert ".build()" in result

    def test_writes(self):
        result = transpile('Agent("x").writes("result")')
        assert '.writes("result")' in result


class TestOperators:
    """Test operator → method transpilation."""

    def test_rshift_to_then(self):
        result = transpile("a >> b")
        assert "a.then(b)" in result

    def test_bitor_to_parallel(self):
        result = transpile("a | b")
        assert "a.parallel(b)" in result

    def test_mul_to_times(self):
        result = transpile("a * 3")
        assert "a.times(3)" in result

    def test_floordiv_to_fallback(self):
        result = transpile("a // b")
        assert "a.fallback(b)" in result

    def test_matmul_to_output_as(self):
        result = transpile("agent @ Schema")
        assert "agent.outputAs(Schema)" in result

    def test_complex_pipeline(self):
        result = transpile("(writer >> reviewer) * 3")
        assert "writer.then(reviewer).times(3)" in result


class TestNamespaces:
    """Test namespace call transpilation."""

    def test_s_pick(self):
        result = transpile('S.pick("a", "b")')
        assert 'S.pick("a", "b")' in result

    def test_c_none(self):
        result = transpile("C.none()")
        assert "C.none()" in result

    def test_p_role(self):
        result = transpile('P.role("Analyst")')
        assert 'P.role("Analyst")' in result

    def test_t_fn(self):
        result = transpile("T.fn(search)")
        assert "T.fn(search)" in result


class TestLambdas:
    """Test lambda → arrow function transpilation."""

    def test_simple_lambda(self):
        result = transpile('lambda s: s["key"]')
        assert '(s) => s["key"]' in result

    def test_comparison_lambda(self):
        result = transpile('lambda s: s["done"] == True')
        assert "=== true" in result


class TestConstants:
    """Test Python → TS constant mapping."""

    def test_none_to_undefined(self):
        result = transpile("x = None")
        assert "undefined" in result

    def test_true_to_true(self):
        result = transpile("x = True")
        assert "true" in result

    def test_false_to_false(self):
        result = transpile("x = False")
        assert "false" in result


class TestImports:
    """Test import auto-generation."""

    def test_agent_import_generated(self):
        result = transpile('Agent("x")')
        assert 'import { Agent } from "adk-fluent-ts"' in result

    def test_namespace_import_generated(self):
        result = transpile('S.pick("a")')
        assert 'import { S } from "adk-fluent-ts"' in result

    def test_python_import_commented(self):
        result = transpile("from adk_fluent import Agent")
        assert "auto-resolved" in result


class TestSnakeToCamel:
    """Test snake_case → camelCase method name conversion."""

    def test_transfer_to(self):
        result = transpile("x.transfer_to(y)")
        assert ".transferTo(y)" in result

    def test_before_model(self):
        result = transpile("x.before_model(fn)")
        assert ".beforeModel(fn)" in result

    def test_max_iterations(self):
        result = transpile("x.max_iterations(5)")
        assert ".maxIterations(5)" in result

    def test_global_instruct(self):
        result = transpile('x.global_instruct("Be polite")')
        assert '.globalInstruct("Be polite")' in result


class TestGoldenFiles:
    """Test transpilation of golden example files."""

    GOLDEN_DIR = Path(__file__).parent / "golden"

    @pytest.mark.parametrize("filename", [
        "simple_agent.py",
        "pipeline_operators.py",
        "namespaces.py",
    ])
    def test_golden_transpiles_without_error(self, filename):
        source = (self.GOLDEN_DIR / filename).read_text()
        result = transpile(source, filename=filename)
        # Should produce non-empty output
        assert len(result.strip()) > 0
        # Should not contain Python-only syntax
        assert "self." not in result
        assert "def " not in result or "function " in result
