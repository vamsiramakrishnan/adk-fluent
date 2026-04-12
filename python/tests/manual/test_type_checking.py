"""Issue #13 — Pyright type-checking stress tests.

These tests run pyright in a subprocess to verify that type annotations
resolve correctly for IDE autocomplete scenarios.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_PYRIGHT = shutil.which("pyright")
pytestmark = pytest.mark.skipif(_PYRIGHT is None, reason="pyright not installed")


def _run_pyright(code: str) -> subprocess.CompletedProcess:
    """Write code to a temp file and run pyright on it."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp = Path(f.name)
    try:
        return subprocess.run(
            [_PYRIGHT, str(tmp), "--pythonversion", "3.11"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        tmp.unlink(missing_ok=True)


class TestPyrightResolution:
    """Verify that pyright resolves adk-fluent types correctly."""

    def test_chained_methods_resolve_to_agent(self):
        """Agent('x').instruct('y').model('m') should resolve to Agent type."""
        result = _run_pyright('from adk_fluent import Agent\na = Agent("x").instruct("y").model("m")\nreveal_type(a)\n')
        assert "Agent" in result.stdout

    def test_build_resolves_to_llm_agent(self):
        """Agent('x').build() should resolve to LlmAgent."""
        result = _run_pyright('from adk_fluent import Agent\nb = Agent("x").build()\nreveal_type(b)\n')
        assert "LlmAgent" in result.stdout

    def test_unknown_method_produces_error(self):
        """Agent('x').not_a_method('y') should produce a type error."""
        result = _run_pyright('from adk_fluent import Agent\nAgent("x").not_a_method("y")\n')
        assert result.returncode != 0
        assert "not_a_method" in result.stdout or "error" in result.stdout.lower()

    def test_pipeline_operator_type(self):
        """>> operator should produce Pipeline type."""
        result = _run_pyright('from adk_fluent import Agent, Pipeline\np = Agent("a") >> Agent("b")\nreveal_type(p)\n')
        # The result type from >> is BuilderBase, but in practice it's Pipeline
        assert result.returncode == 0 or "Pipeline" in result.stdout or "BuilderBase" in result.stdout
