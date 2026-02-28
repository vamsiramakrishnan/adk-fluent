"""Orchestrator — main pipeline from manifest.json to seed.toml.

Steps:
    1. Iterate manifest["classes"]
    2. Classify each class
    3. Filter to builder-worthy only
    4. For each: detect constructor args, compute field policies,
       generate aliases, determine output module, generate extras
    5. Determine builder name (with renames)
    6. Create terminal: build() returning source class name
    7. Collect global skip/additive/list_extend fields
    8. Call emit_seed_toml()
"""

from __future__ import annotations

from .aliases import (
    SEMANTIC_OVERRIDES,
    _EXTRA_ALIASES,
    derive_aliases,
    generate_callback_aliases,
)
from .classifier import classify_class, is_builder_worthy
from .emitter import emit_seed_toml
from .extras import infer_extras
from .field_policy import infer_field_policy, is_parent_reference

# ---------------------------------------------------------------------------
# CONSTRUCTOR ARG DETECTION
# ---------------------------------------------------------------------------

_MAX_CONSTRUCTOR_ARGS = 3


def detect_constructor_args(
    fields: list[dict],
    inspection_mode: str,
    init_params: list[dict],
) -> list[str]:
    """Detect which fields/params should be positional constructor arguments.

    For Pydantic models: required fields, capped at _MAX_CONSTRUCTOR_ARGS.
    For init_signature: required __init__ params, capped at _MAX_CONSTRUCTOR_ARGS.
    """
    if inspection_mode == "pydantic":
        required = [f["name"] for f in fields if f.get("required", False)]
        return required[:_MAX_CONSTRUCTOR_ARGS]
    else:
        required = [p["name"] for p in init_params if p.get("required", False)]
        return required[:_MAX_CONSTRUCTOR_ARGS]


# ---------------------------------------------------------------------------
# OUTPUT MODULE GROUPING
# ---------------------------------------------------------------------------

_WORKFLOW_AGENTS = frozenset({"SequentialAgent", "ParallelAgent", "LoopAgent"})


def determine_output_module(class_name: str, tag: str, module: str) -> str:
    """Determine which output module a builder belongs in.

    Workflow agents get their own module; everything else groups by tag.
    """
    if class_name in _WORKFLOW_AGENTS:
        return "workflow"
    return tag


# ---------------------------------------------------------------------------
# BUILDER NAMING
# ---------------------------------------------------------------------------

_DEFAULT_BUILDER_RENAMES = {
    "LlmAgent": "Agent",
    "SequentialAgent": "Pipeline",
    "ParallelAgent": "FanOut",
    "LoopAgent": "Loop",
}


def _builder_name_for_class(class_name: str, tag: str, renames: dict[str, str] | None = None) -> str:
    """Determine the builder name for a class, applying renames for well-known types."""
    rename_map = renames if renames is not None else _DEFAULT_BUILDER_RENAMES
    return rename_map.get(class_name, class_name)


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------


def generate_seed_from_manifest(manifest: dict, renames: dict[str, str] | None = None) -> str:
    """Main pipeline: transform a manifest dict into a seed.toml string."""
    builders: list[dict] = []
    global_skip: set[str] = set()
    global_additive: set[str] = set()
    global_list_extend: set[str] = set()

    for cls_info in manifest["classes"]:
        name = cls_info["name"]
        module = cls_info["module"]
        mro_chain = cls_info["mro_chain"]

        # Classify
        tag = classify_class(name, module, mro_chain)

        # Filter
        if not is_builder_worthy(tag):
            continue

        # Constructor args
        fields = cls_info.get("fields", [])
        inspection_mode = cls_info.get("inspection_mode", "pydantic")
        init_params = cls_info.get("init_params", [])
        constructor_args = detect_constructor_args(fields, inspection_mode, init_params)

        # Field policies
        callback_fields: list[str] = []
        all_field_names: list[str] = []
        extra_skip_fields: list[str] = []

        for f in fields:
            fname = f["name"]
            ftype = f.get("type_str", "")
            is_cb = f.get("is_callback", False)
            is_parent_ref = is_parent_reference(fname, ftype, mro_chain)
            policy = infer_field_policy(fname, ftype, is_cb, is_parent_ref=is_parent_ref)

            if policy == "skip":
                global_skip.add(fname)
            elif policy == "additive":
                global_additive.add(fname)
                callback_fields.append(fname)
            elif policy == "list_extend":
                global_list_extend.add(fname)

            all_field_names.append(fname)

        # Aliases (morphological derivation + semantic overrides)
        _overrides = {**SEMANTIC_OVERRIDES, **_EXTRA_ALIASES}
        aliases = derive_aliases(all_field_names, overrides=_overrides)
        cb_aliases = generate_callback_aliases(callback_fields)

        # Output module
        output_module = determine_output_module(name, tag, module)

        # Extras (type-driven inference)
        source_class = cls_info.get("qualname", f"{module}.{name}")
        extras = infer_extras(name, tag, fields)

        # Builder name
        builder_name = _builder_name_for_class(name, tag, renames)

        # Terminal
        terminals = [{"name": "build", "returns": name, "doc": f"Resolve into a native ADK {name}."}]

        # Doc
        doc = cls_info.get("doc", "") or f"Fluent builder for {name}."
        if not doc.endswith("."):
            doc += "."

        builder = {
            "name": builder_name,
            "source_class": source_class,
            "output_module": output_module,
            "doc": doc,
            "tag": tag,
            "constructor_args": constructor_args,
            "aliases": aliases,
            "callback_aliases": cb_aliases,
            "extra_skip_fields": extra_skip_fields,
            "terminals": terminals,
            "extras": extras,
        }
        builders.append(builder)

    # Deduplicate builder names: keep the first occurrence of each name
    seen_names: set[str] = set()
    deduped: list[dict] = []
    for builder in builders:
        if builder["name"] not in seen_names:
            seen_names.add(builder["name"])
            deduped.append(builder)
    builders = deduped

    # Global config
    global_config = {
        "skip_fields": sorted(global_skip),
        "additive_fields": sorted(global_additive),
        "list_extend_fields": sorted(global_list_extend),
    }

    # Emit
    adk_version = manifest.get("adk_version", "unknown")
    return emit_seed_toml(builders, global_config, adk_version=adk_version)
