"""Shared test fixtures for the adk-fluent test suite.

Provides reusable builders, manifest data, and seed data so individual
test files don't have to construct these from scratch every time.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# MINIMAL MANIFEST FIXTURE (no ADK install required)
# ---------------------------------------------------------------------------

_MINIMAL_MANIFEST = {
    "adk_version": "0.0.0-test",
    "classes": [
        {
            "name": "LlmAgent",
            "qualname": "google.adk.agents.LlmAgent",
            "module": "google.adk.agents.llm_agent",
            "mro_chain": ["LlmAgent", "BaseAgent", "BaseModel"],
            "inspection_mode": "pydantic",
            "fields": [
                {"name": "name", "type_str": "str", "required": True},
                {"name": "model", "type_str": "str", "required": False},
                {"name": "instruction", "type_str": "str | None", "required": False},
                {"name": "description", "type_str": "str | None", "required": False},
                {"name": "tools", "type_str": "list[BaseTool]", "required": False, "is_callback": False},
                {"name": "sub_agents", "type_str": "list[BaseAgent]", "required": False, "is_callback": False},
                {
                    "name": "before_model_callback",
                    "type_str": "Callable | None",
                    "required": False,
                    "is_callback": True,
                },
                {"name": "parent_agent", "type_str": "BaseAgent | None", "required": False},
            ],
            "init_params": [],
            "doc": "An agent powered by a large language model.",
        },
        {
            "name": "SequentialAgent",
            "qualname": "google.adk.agents.SequentialAgent",
            "module": "google.adk.agents.sequential_agent",
            "mro_chain": ["SequentialAgent", "BaseAgent", "BaseModel"],
            "inspection_mode": "pydantic",
            "fields": [
                {"name": "name", "type_str": "str", "required": True},
                {"name": "sub_agents", "type_str": "list[BaseAgent]", "required": False},
            ],
            "init_params": [],
            "doc": "Run sub-agents sequentially.",
        },
        {
            "name": "RunConfig",
            "qualname": "google.adk.agents.RunConfig",
            "module": "google.adk.agents.run_config",
            "mro_chain": ["RunConfig", "BaseModel"],
            "inspection_mode": "pydantic",
            "fields": [
                {"name": "max_llm_calls", "type_str": "int", "required": False},
                {"name": "speech_config", "type_str": "SpeechConfig | None", "required": False},
            ],
            "init_params": [],
            "doc": "Configuration for agent runs.",
        },
    ],
}


@pytest.fixture
def minimal_manifest():
    """A minimal manifest dict with 3 classes — no ADK install required."""
    return json.loads(json.dumps(_MINIMAL_MANIFEST))


@pytest.fixture
def minimal_manifest_path(tmp_path, minimal_manifest):
    """Write the minimal manifest to a temp file and return the path."""
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(minimal_manifest, indent=2))
    return str(p)


# ---------------------------------------------------------------------------
# REAL MANIFEST FIXTURE (uses committed manifest.json if present)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_COMMITTED_MANIFEST = _PROJECT_ROOT / "manifest.json"


@pytest.fixture
def committed_manifest():
    """The real committed manifest.json, or skip if not present."""
    if not _COMMITTED_MANIFEST.exists():
        pytest.skip("manifest.json not committed")
    with open(_COMMITTED_MANIFEST) as f:
        return json.load(f)


@pytest.fixture
def committed_manifest_path():
    """Path to the committed manifest.json, or skip."""
    if not _COMMITTED_MANIFEST.exists():
        pytest.skip("manifest.json not committed")
    return str(_COMMITTED_MANIFEST)


# ---------------------------------------------------------------------------
# SEED FIXTURES
# ---------------------------------------------------------------------------

_COMMITTED_SEED = _PROJECT_ROOT / "seeds" / "seed.toml"


@pytest.fixture
def committed_seed_path():
    """Path to the committed seed.toml, or skip."""
    if not _COMMITTED_SEED.exists():
        pytest.skip("seeds/seed.toml not committed")
    return str(_COMMITTED_SEED)


@pytest.fixture
def minimal_seed_path(tmp_path, minimal_manifest):
    """Generate a minimal seed.toml from the minimal manifest and return the path."""
    from scripts.seed_generator import generate_seed_from_manifest

    seed_toml = generate_seed_from_manifest(minimal_manifest)
    p = tmp_path / "seed.toml"
    p.write_text(seed_toml)
    return str(p)


# ---------------------------------------------------------------------------
# BUILDER FIXTURES (require ADK install)
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_builder():
    """A simple Agent builder instance."""
    from adk_fluent import Agent

    return Agent("test-agent")


@pytest.fixture
def pipeline_builder():
    """A simple Pipeline builder instance."""
    from adk_fluent import Pipeline

    return Pipeline("test-pipeline")


# ---------------------------------------------------------------------------
# GENERATOR SPEC FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_builder_specs(minimal_seed_path, minimal_manifest_path):
    """Resolved BuilderSpec list from the minimal manifest."""
    from scripts.generator import parse_manifest, parse_seed, resolve_builder_specs

    seed = parse_seed(minimal_seed_path)
    manifest = parse_manifest(minimal_manifest_path)
    return resolve_builder_specs(seed, manifest)


# ---------------------------------------------------------------------------
# GOLDEN FILE SUPPORT
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", default=False, help="Update golden files on disk")
