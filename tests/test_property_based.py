"""Property-based tests for the codegen pipeline.

Uses Hypothesis to fuzz the generator's pure-function components with random
inputs and verify structural invariants hold for all inputs.
"""

from __future__ import annotations

import ast
import os
import sys

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="hypothesis not installed")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# STRATEGIES
# ---------------------------------------------------------------------------

# Valid Python identifiers for field names
_identifier = st.from_regex(r"[a-z][a-z0-9_]{0,30}", fullmatch=True)

# Type strings
_simple_types = st.sampled_from(["str", "int", "float", "bool", "bytes", "Any"])
_list_types = _simple_types.map(lambda t: f"list[{t}]")
_optional_types = _simple_types.map(lambda t: f"{t} | None")
_type_str = st.one_of(_simple_types, _list_types, _optional_types)

# MRO chains
_mro_chain = st.lists(
    st.sampled_from(["LlmAgent", "BaseAgent", "BaseModel", "SequentialAgent", "RunConfig", "BaseTool"]),
    min_size=1,
    max_size=5,
)

# Module paths
_module_path = st.from_regex(r"google\.adk\.[a-z_]{1,20}", fullmatch=True)

# Class names
_class_name = st.from_regex(r"[A-Z][a-zA-Z]{2,20}", fullmatch=True)


# ---------------------------------------------------------------------------
# CLASSIFIER PROPERTIES
# ---------------------------------------------------------------------------


class TestClassifierProperties:
    """Property-based tests for the class classifier."""

    @given(name=_class_name, module=_module_path, mro=_mro_chain)
    @settings(max_examples=200)
    def test_classify_always_returns_string(self, name, module, mro):
        """classify_class always returns a non-empty string tag."""
        from scripts.seed_generator.classifier import classify_class

        tag = classify_class(name, module, mro)
        assert isinstance(tag, str)
        assert len(tag) > 0

    @given(name=_class_name, module=_module_path, mro=_mro_chain)
    @settings(max_examples=200)
    def test_classify_returns_known_tag(self, name, module, mro):
        """classify_class always returns one of the known tags."""
        from scripts.seed_generator.classifier import classify_class

        known_tags = {
            "agent",
            "runtime",
            "eval",
            "auth",
            "service",
            "config",
            "tool",
            "plugin",
            "planner",
            "executor",
            "data",
        }
        tag = classify_class(name, module, mro)
        assert tag in known_tags, f"Unknown tag: {tag}"

    @given(name=_class_name, module=_module_path, mro=_mro_chain)
    @settings(max_examples=200)
    def test_classify_is_deterministic(self, name, module, mro):
        """Classifying the same inputs twice always gives the same result."""
        from scripts.seed_generator.classifier import classify_class

        assert classify_class(name, module, mro) == classify_class(name, module, mro)

    def test_base_agent_in_mro_always_means_agent(self):
        """If BaseAgent is in the MRO, the tag is always 'agent'."""
        from scripts.seed_generator.classifier import classify_class

        assert classify_class("Foo", "google.adk.foo", ["Foo", "BaseAgent"]) == "agent"
        assert classify_class("Bar", "google.adk.bar", ["Bar", "BaseAgent", "BaseModel"]) == "agent"


# ---------------------------------------------------------------------------
# ALIAS DERIVATION PROPERTIES
# ---------------------------------------------------------------------------


class TestAliasDeriveProperties:
    """Property-based tests for alias derivation."""

    @given(field_name=_identifier)
    @settings(max_examples=300)
    def test_derive_alias_returns_none_or_shorter(self, field_name):
        """derive_alias returns None or a string shorter than the input."""
        from scripts.seed_generator.aliases import derive_alias

        alias = derive_alias(field_name)
        if alias is not None:
            assert isinstance(alias, str)
            assert len(alias) < len(field_name)
            assert len(alias) > 0

    @given(field_names=st.lists(_identifier, min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_derive_aliases_returns_dict(self, field_names):
        """derive_aliases always returns a dict mapping alias->field_name."""
        from scripts.seed_generator.aliases import derive_aliases

        aliases = derive_aliases(field_names)
        assert isinstance(aliases, dict)
        # Every value should be from the input field_names
        for alias, field in aliases.items():
            assert field in field_names
            assert isinstance(alias, str)

    @given(field_names=st.lists(_identifier, min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_derive_aliases_is_deterministic(self, field_names):
        """Deriving aliases twice gives the same result."""
        from scripts.seed_generator.aliases import derive_aliases

        assert derive_aliases(field_names) == derive_aliases(field_names)


# ---------------------------------------------------------------------------
# FIELD POLICY PROPERTIES
# ---------------------------------------------------------------------------


class TestFieldPolicyProperties:
    """Property-based tests for field policy inference."""

    @given(
        field_name=_identifier,
        type_str=_type_str,
        is_callback=st.booleans(),
    )
    @settings(max_examples=300)
    def test_infer_field_policy_returns_known_policy(self, field_name, type_str, is_callback):
        """infer_field_policy always returns one of the known policies."""
        from scripts.seed_generator.field_policy import infer_field_policy

        known_policies = {"skip", "additive", "list_extend", "normal"}
        policy = infer_field_policy(field_name, type_str, is_callback)
        assert policy in known_policies

    @given(field_name=st.from_regex(r"_[a-z_]{1,20}", fullmatch=True))
    @settings(max_examples=50)
    def test_private_fields_are_skipped(self, field_name):
        """Fields starting with _ are always skipped."""
        from scripts.seed_generator.field_policy import infer_field_policy

        assert infer_field_policy(field_name, "str", False) == "skip"


# ---------------------------------------------------------------------------
# SIGNATURE PARSER PROPERTIES
# ---------------------------------------------------------------------------


class TestSigParserProperties:
    """Property-based tests for the signature parser."""

    @given(
        params=st.lists(
            st.tuples(_identifier, _simple_types),
            min_size=0,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_parse_signature_roundtrips_simple_params(self, params):
        """Parsing a simple signature recovers all parameter names."""
        from scripts.generator.sig_parser import parse_signature

        parts = ["self"] + [f"{name}: {type_}" for name, type_ in params]
        sig = f"({', '.join(parts)}) -> Self"

        parsed_params, return_type = parse_signature(sig)
        assert return_type == "Self"
        parsed_names = [p.name for p in parsed_params]
        assert parsed_names[0] == "self"
        for name, _ in params:
            assert name in parsed_names


# ---------------------------------------------------------------------------
# END-TO-END PROPERTY: generated code is always valid Python
# ---------------------------------------------------------------------------


class TestGeneratedCodeProperties:
    """Property-based tests for the full generation pipeline."""

    @given(
        field_names=st.lists(
            _identifier,
            min_size=1,
            max_size=8,
            unique=True,
        ),
    )
    @settings(max_examples=30, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_generated_code_always_compiles(self, field_names, minimal_manifest, tmp_path):
        """Code generated from any valid field set is syntactically valid Python."""
        import json

        # Build a manifest with random fields
        manifest = {
            "adk_version": "0.0.0-test",
            "classes": [
                {
                    "name": "TestClass",
                    "qualname": "google.adk.test.TestClass",
                    "module": "google.adk.test",
                    "mro_chain": ["TestClass", "BaseModel"],
                    "inspection_mode": "pydantic",
                    "fields": [{"name": fn, "type_str": "str", "required": False} for fn in field_names],
                    "init_params": [],
                    "doc": "Test class.",
                },
            ],
        }

        from scripts.code_ir import emit_python
        from scripts.generator import parse_manifest, parse_seed, resolve_builder_specs
        from scripts.generator.module_builder import specs_to_ir_module
        from scripts.seed_generator import generate_seed_from_manifest

        # Generate seed
        seed_toml = generate_seed_from_manifest(manifest)
        seed_path = tmp_path / "seed.toml"
        seed_path.write_text(seed_toml)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # Generate code
        seed = parse_seed(str(seed_path))
        m = parse_manifest(str(manifest_path))
        specs = resolve_builder_specs(seed, m)

        if not specs:
            return  # No builders generated — that's fine

        from collections import defaultdict

        by_module: dict[str, list] = defaultdict(list)
        for spec in specs:
            by_module[spec.output_module].append(spec)

        for module_name, module_specs in by_module.items():
            ir_module = specs_to_ir_module(module_specs, manifest=m)
            code = emit_python(ir_module)
            try:
                ast.parse(code)
            except SyntaxError as e:
                pytest.fail(f"Generated code for {module_name} has syntax error: {e}\n\n{code}")
