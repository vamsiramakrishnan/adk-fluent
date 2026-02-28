"""BuilderSpec — the resolved configuration for a single fluent builder.

Combines seed.toml (human intent) with manifest.json (machine truth)
to produce the complete specification that drives code generation.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------


@dataclass
class BuilderSpec:
    """Parsed builder specification from seed + manifest."""

    name: str  # e.g., "Agent"
    source_class: str  # e.g., "google.adk.agents.LlmAgent"
    source_class_short: str  # e.g., "LlmAgent"
    output_module: str  # e.g., "agent"
    doc: str
    constructor_args: list[str]  # Fields passed to __init__
    aliases: dict[str, str]  # fluent_name → pydantic_field_name
    reverse_aliases: dict[str, str]  # pydantic_field_name → fluent_name
    callback_aliases: dict[str, str]  # short_name → full_callback_field_name
    skip_fields: set[str]  # Fields not exposed
    additive_fields: set[str]  # Callback fields with append semantics
    list_extend_fields: set[str]  # List fields with extend semantics
    fields: list[dict]  # From manifest (all Pydantic fields)
    terminals: list[dict]  # Terminal methods
    extras: list[dict]  # Extra hand-written methods
    is_composite: bool  # True if __composite__ (no Pydantic class)
    is_standalone: bool  # True if __standalone__ (no ADK class at all)
    field_docs: dict[str, str]  # Override docstrings
    inspection_mode: str = "pydantic"  # "pydantic" or "init_signature"
    init_params: list[dict] | None = None  # __init__ params for init_signature mode
    optional_constructor_args: list[str] | None = None  # Optional positional args (e.g. model)
    deprecated_aliases: dict[str, dict[str, str]] | None = None  # fluent_name → {field, use}


# ---------------------------------------------------------------------------
# PARSING: seed.toml + manifest.json → BuilderSpec[]
# ---------------------------------------------------------------------------


def parse_seed(seed_path: str) -> dict:
    """Parse the seed.toml file."""
    with open(seed_path, "rb") as f:
        return tomllib.load(f)


def parse_manifest(manifest_path: str) -> dict:
    """Parse the manifest.json file."""
    with open(manifest_path) as f:
        return json.load(f)


def resolve_builder_specs(seed: dict, manifest: dict) -> list[BuilderSpec]:
    """Merge seed config with manifest data to produce BuilderSpecs."""
    global_config = seed.get("global", {})
    global_skip = set(global_config.get("skip_fields", []))
    global_additive = set(global_config.get("additive_fields", []))
    global_list_extend = set(global_config.get("list_extend_fields", []))
    field_docs = seed.get("field_docs", {})

    # Index manifest classes by qualname
    manifest_classes = {}
    for cls in manifest.get("classes", []):
        manifest_classes[cls["qualname"]] = cls
        # Also index by short name for convenience
        manifest_classes[cls["name"]] = cls

    specs = []

    for builder_name, builder_config in seed.get("builders", {}).items():
        source_class = builder_config.get("source_class", "")
        is_composite = source_class == "__composite__"
        is_standalone = source_class == "__standalone__"

        # Look up manifest data for this class
        fields = []
        source_short = ""
        inspection_mode = "pydantic"
        init_params = []
        if not is_composite and not is_standalone:
            cls_data = manifest_classes.get(source_class)
            if cls_data is None:
                # Try matching by class name only
                class_name = source_class.split(".")[-1]
                cls_data = manifest_classes.get(class_name)

            if cls_data:
                fields = cls_data.get("fields", [])
                source_short = cls_data["name"]
                inspection_mode = cls_data.get("inspection_mode", "pydantic")
                init_params = cls_data.get("init_params", [])
            else:
                print(f"WARNING: {source_class} not found in manifest for builder {builder_name}", file=sys.stderr)
                source_short = source_class.split(".")[-1]
        else:
            source_short = builder_name

        # Merge skip fields
        extra_skip = set(builder_config.get("extra_skip_fields", []))
        skip_fields = global_skip | extra_skip | set(builder_config.get("constructor_args", []))

        # Build alias maps
        aliases = dict(builder_config.get("aliases", {}))
        reverse_aliases = {v: k for k, v in aliases.items()}
        callback_aliases = dict(builder_config.get("callback_aliases", {}))

        # Parse deprecated aliases
        deprecated_aliases: dict[str, dict[str, str]] = {}
        for dep_name, dep_val in builder_config.get("deprecated_aliases", {}).items():
            if isinstance(dep_val, dict):
                deprecated_aliases[dep_name] = dep_val
            else:
                deprecated_aliases[dep_name] = {"use": str(dep_val)}

        spec = BuilderSpec(
            name=builder_name,
            source_class=source_class,
            source_class_short=source_short,
            output_module=builder_config.get("output_module", builder_name.lower()),
            doc=builder_config.get("doc", ""),
            constructor_args=builder_config.get("constructor_args", []),
            aliases=aliases,
            reverse_aliases=reverse_aliases,
            callback_aliases=callback_aliases,
            skip_fields=skip_fields,
            additive_fields=global_additive,
            list_extend_fields=global_list_extend,
            fields=fields,
            terminals=builder_config.get("terminals", []),
            extras=builder_config.get("extras", []),
            is_composite=is_composite,
            is_standalone=is_standalone,
            field_docs=field_docs,
            deprecated_aliases=deprecated_aliases,
            inspection_mode=inspection_mode,
            init_params=init_params,
            optional_constructor_args=builder_config.get("optional_constructor_args"),
        )
        specs.append(spec)

    return specs
