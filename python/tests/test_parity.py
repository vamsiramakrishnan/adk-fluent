"""Cross-language parity check — Python ↔ TypeScript API surface.

Reads ``shared/parity.toml`` (the single source of truth) and verifies:

  1. Every ``[[operators]]`` row's ``python_operator`` dunder exists on the
     Python ``BuilderBase`` and its ``ts_method`` name is a real method on
     the TS ``BuilderBase`` class (checked by grepping the TS source).
  2. Every ``[[composites]]`` row's ``target_method`` exists on
     ``BuilderBase`` in both languages.
  3. Every ``[[aliases]]`` row with a non-empty ``ts_name`` appears as a
     named export in the TS package entry, and the ``python_name`` appears
     in the Python package ``__all__``.

The test fails fast with a precise diff so adding an operator or alias to
one language without the other breaks CI.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARITY_TOML = REPO_ROOT / "shared" / "parity.toml"
TS_BUILDER_BASE = REPO_ROOT / "ts" / "src" / "core" / "builder-base.ts"
TS_INDEX = REPO_ROOT / "ts" / "src" / "index.ts"


@pytest.fixture(scope="module")
def parity() -> dict:
    """Load the parity table once per module."""
    if not PARITY_TOML.exists():
        pytest.skip(f"parity table not found at {PARITY_TOML}")
    with open(PARITY_TOML, "rb") as f:
        return tomllib.load(f)


@pytest.fixture(scope="module")
def ts_builder_source() -> str:
    """Load the TS BuilderBase source as a single string."""
    if not TS_BUILDER_BASE.exists():
        pytest.skip(f"TS BuilderBase not found at {TS_BUILDER_BASE}")
    return TS_BUILDER_BASE.read_text()


@pytest.fixture(scope="module")
def ts_index_source() -> str:
    """Load the TS package entry point so we can grep its re-exports."""
    if not TS_INDEX.exists():
        pytest.skip(f"TS index not found at {TS_INDEX}")
    return TS_INDEX.read_text()


def _ts_has_method(source: str, method: str) -> bool:
    """Return True if ``method`` is defined on the TS BuilderBase class.

    Matches forms like ``methodName(``, ``methodName<T>(`` and
    ``methodName:`` on a class-body line. Accepts an optional leading
    modifier (``async`` / ``public`` / ``private`` / ``protected``).
    """
    pattern = rf"^\s*(?:(?:async|public|private|protected|readonly|static)\s+)*{re.escape(method)}\s*[<(:]"
    return re.search(pattern, source, re.MULTILINE) is not None


class TestOperatorParity:
    def test_python_operators_exist(self, parity: dict) -> None:
        from adk_fluent._base import BuilderBase

        missing: list[str] = []
        for row in parity.get("operators", []):
            dunder = row["python_operator"]
            if not hasattr(BuilderBase, dunder):
                missing.append(f"{row['name']}: BuilderBase.{dunder}")
        assert not missing, (
            "Python operators missing from BuilderBase (parity.toml drift): "
            + ", ".join(missing)
        )

    def test_ts_methods_exist(self, parity: dict, ts_builder_source: str) -> None:
        missing: list[str] = []
        for row in parity.get("operators", []):
            method = row["ts_method"]
            if not _ts_has_method(ts_builder_source, method):
                missing.append(f"{row['name']}: BuilderBase.{method}()")
        assert not missing, (
            "TS methods missing from BuilderBase (parity.toml drift): "
            + ", ".join(missing)
        )


class TestCompositeParity:
    def test_python_target_setters_exist(self, parity: dict) -> None:
        # Composite setters are generated per-builder, so we check Agent
        # (the canonical builder) rather than BuilderBase.
        from adk_fluent import Agent

        probe = Agent("parity-probe")
        missing: list[str] = []
        for row in parity.get("composites", []):
            setter = row["target_method"]
            if not hasattr(probe, setter):
                missing.append(f"{row['namespace']}: Agent.{setter}")
        assert not missing, (
            "Python composite target setters missing from Agent: "
            + ", ".join(missing)
        )

    def test_ts_target_setters_exist(self, parity: dict, ts_builder_source: str) -> None:
        # These setters live on the generated Agent — not BuilderBase — in TS.
        # We check both: pass if either file exposes the method.
        agent_ts = REPO_ROOT / "ts" / "src" / "builders" / "agent.ts"
        combined = ts_builder_source + "\n" + (
            agent_ts.read_text() if agent_ts.exists() else ""
        )
        missing: list[str] = []
        for row in parity.get("composites", []):
            setter = row["target_method"]
            if not _ts_has_method(combined, setter):
                missing.append(f"{row['namespace']}: {setter}()")
        assert not missing, (
            "TS composite target setters missing: " + ", ".join(missing)
        )


class TestAliasParity:
    def test_python_aliases_exported(self, parity: dict) -> None:
        import adk_fluent

        missing: list[str] = []
        for row in parity.get("aliases", []):
            name = row["python_name"]
            if name not in adk_fluent.__all__:
                missing.append(name)
        assert not missing, (
            "Python package missing named aliases declared in parity.toml: "
            + ", ".join(missing)
        )

    def test_ts_aliases_exported(self, parity: dict, ts_index_source: str) -> None:
        # Named aliases flow through re-exports in ts/src/index.ts. We grep
        # for ``export { ... Name ... }`` or ``export { ... Name as ... }``.
        missing: list[str] = []
        for row in parity.get("aliases", []):
            ts_name = row.get("ts_name", "")
            if not ts_name:
                continue  # intentionally skipped (see `reason`)
            pattern = rf"\b{re.escape(ts_name)}\b"
            if not re.search(pattern, ts_index_source):
                missing.append(ts_name)
        assert not missing, (
            "TS package missing named aliases declared in parity.toml: "
            + ", ".join(missing)
        )


class TestTableShape:
    """Guard against accidental schema drift in parity.toml itself."""

    def test_schema_version(self, parity: dict) -> None:
        assert parity["meta"]["schema_version"] == 1, (
            "If you bumped the parity.toml schema, update the loader too."
        )

    def test_operators_have_required_fields(self, parity: dict) -> None:
        required = {"name", "python_operator", "ts_method", "returns"}
        for row in parity.get("operators", []):
            missing = required - set(row.keys())
            assert not missing, f"operator row {row.get('name')!r} missing {missing}"

    def test_composites_have_required_fields(self, parity: dict) -> None:
        required = {"namespace", "target_method"}
        for row in parity.get("composites", []):
            missing = required - set(row.keys())
            assert not missing, f"composite row {row.get('namespace')!r} missing {missing}"

    def test_aliases_have_required_fields(self, parity: dict) -> None:
        required = {"python_name", "short"}
        for row in parity.get("aliases", []):
            missing = required - set(row.keys())
            assert not missing, f"alias row {row.get('python_name')!r} missing {missing}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
