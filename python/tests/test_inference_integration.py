"""End-to-end test: verify the inference engine produces valid output
from a real ADK manifest scan."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def test_inferred_seed_covers_all_old_builders():
    """The inference engine should produce builders for at least every class
    the old system did."""
    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)
    toml_str = generate_seed_from_manifest(manifest_dict)
    parsed = tomllib.loads(toml_str)

    builders = list(parsed["builders"].keys())

    # These must always be present (renamed from ADK classes)
    assert "Agent" in builders or "LlmAgent" in builders
    assert len(builders) >= 7, f"Expected >=7 builders, got {len(builders)}: {builders}"


def test_inferred_seed_has_correct_policies():
    """Verify that inferred field policies match expected semantics."""
    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)
    toml_str = generate_seed_from_manifest(manifest_dict)
    parsed = tomllib.loads(toml_str)

    global_cfg = parsed["global"]
    # Callbacks should be in additive
    assert "before_model_callback" in global_cfg["additive_fields"]
    # List fields should be in list_extend
    assert "tools" in global_cfg["list_extend_fields"]
    assert "sub_agents" in global_cfg["list_extend_fields"]


def test_inferred_seed_has_extras_for_agent():
    """The Agent builder should have inferred extras (singular adders)."""
    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)
    toml_str = generate_seed_from_manifest(manifest_dict)
    parsed = tomllib.loads(toml_str)

    # Find the Agent builder (might be named LlmAgent before manual merge)
    agent_builder = parsed["builders"].get("Agent") or parsed["builders"].get("LlmAgent")
    assert agent_builder is not None, "Agent/LlmAgent builder not found"

    extras = agent_builder.get("extras", [])
    extra_names = [e["name"] for e in extras]
    # Should have auto-inferred singular adders
    assert "tool" in extra_names, f"Expected 'tool' in extras, got: {extra_names}"
    assert "sub_agent" in extra_names, f"Expected 'sub_agent' in extras, got: {extra_names}"


def test_inferred_seed_has_derived_aliases():
    """Aliases should be morphologically derived, not just from lookup table."""
    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)
    toml_str = generate_seed_from_manifest(manifest_dict)
    parsed = tomllib.loads(toml_str)

    agent_builder = parsed["builders"].get("Agent") or parsed["builders"].get("LlmAgent")
    assert agent_builder is not None

    aliases = agent_builder.get("aliases", {})
    # These should be derived morphologically
    assert "instruct" in aliases, f"Expected 'instruct' alias, got: {aliases}"
    assert "describe" in aliases, f"Expected 'describe' alias, got: {aliases}"


def test_full_pipeline_scan_seed_no_crash():
    """Run scan -> seed and verify no crashes with real ADK data."""
    import json
    import tempfile
    from pathlib import Path

    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write manifest
        manifest_path = Path(tmpdir) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_dict))

        # Generate seed
        toml_str = generate_seed_from_manifest(manifest_dict)
        seed_path = Path(tmpdir) / "seed.toml"
        seed_path.write_text(toml_str)

        # Verify seed parses
        parsed = tomllib.loads(toml_str)
        assert len(parsed["builders"]) > 0
        assert "meta" in parsed
        assert "global" in parsed
