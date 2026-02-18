#!/usr/bin/env python3
"""
ADK-FLUENT SEED GENERATOR
==========================
Reads a manifest.json (produced by scanner.py) and generates a seed.toml
that drives the code generation pipeline.

The seed generator automates what was previously a hand-maintained file:
    manifest.json (machine truth) → seed.toml (automated intent) → codegen

Usage:
    python scripts/seed_generator.py manifest.json                # stdout
    python scripts/seed_generator.py manifest.json -o seed.toml   # file output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback


# ---------------------------------------------------------------------------
# TASK 5: CLASSIFICATION ENGINE
# ---------------------------------------------------------------------------


def classify_class(name: str, module: str, mro_chain: list[str]) -> str:
    """Classify an ADK class into a semantic tag.

    Rules are checked in priority order; first match wins.

    Returns one of: agent, runtime, eval, auth, service, config, tool,
    plugin, planner, executor, data.
    """
    # 1. Agent hierarchy
    if "BaseAgent" in mro_chain or name == "BaseAgent":
        return "agent"
    # 2. Runtime singletons
    if name in ("App", "Runner", "InMemoryRunner"):
        return "runtime"
    # 3. Evaluation subsystem
    if "evaluation" in module:
        return "eval"
    # 4. Auth subsystem
    if ".auth" in module:
        return "auth"
    # 5-10. Suffix-based classification
    if name.endswith("Service"):
        return "service"
    if name.endswith("Config"):
        return "config"
    if name.endswith("Tool") or name.endswith("Toolset"):
        return "tool"
    if name.endswith("Plugin"):
        return "plugin"
    if name.endswith("Planner"):
        return "planner"
    if name.endswith("Executor"):
        return "executor"
    # 11. Default
    return "data"


_BUILDER_WORTHY_TAGS = frozenset(
    {
        "agent",
        "config",
        "runtime",
        "executor",
        "planner",
        "service",
        "plugin",
        "tool",
    }
)


def is_builder_worthy(tag: str) -> bool:
    """Return True if classes with this tag should get a fluent builder."""
    return tag in _BUILDER_WORTHY_TAGS


# ---------------------------------------------------------------------------
# TASK 6: FIELD POLICY ENGINE
# ---------------------------------------------------------------------------

_ALWAYS_SKIP = frozenset(
    {
        "parent_agent",
        "model_config",
        "model_fields",
        "model_computed_fields",
        "model_post_init",
    }
)

_LIST_EXTEND_FIELDS = frozenset({"tools", "sub_agents", "plugins"})

_PRIMITIVE_TYPES = frozenset({"str", "int", "float", "bool", "bytes"})

_PYDANTIC_INTERNALS = frozenset(
    {"model_config", "model_fields", "model_computed_fields", "model_post_init"}
)


def _unwrap_optional(type_str: str) -> str:
    """Unwrap ``Union[X, NoneType]``, ``Optional[X]``, and ``X | None`` to just ``X``.

    If *type_str* is not an optional wrapper, return it unchanged.
    """
    s = type_str.strip()

    # Union[X, NoneType]
    if s.startswith("Union[") and s.endswith("]"):
        inner = s[len("Union["):-1]
        parts = [p.strip() for p in inner.split(",")]
        non_none = [p for p in parts if p != "NoneType"]
        if len(non_none) == 1:
            return non_none[0]

    # Optional[X]
    if s.startswith("Optional[") and s.endswith("]"):
        return s[len("Optional["):-1].strip()

    # X | None  (pipe-union syntax, PEP 604)
    if " | " in s:
        parts = [p.strip() for p in s.split("|")]
        non_none = [p for p in parts if p.strip() != "None"]
        if len(non_none) == 1:
            return non_none[0]

    return s


def _is_list_of_complex_type(type_str: str) -> bool:
    """Return True if *type_str* looks like ``list[SomeComplexType]``.

    Handles ``Union[list[X], NoneType]``, ``Optional[list[X]]``, and
    ``list[X] | None`` wrappers by unwrapping them first.

    Primitive element types (str, int, float, bool, bytes) are **not**
    considered complex, so ``list[str]`` returns False.
    """
    s = _unwrap_optional(type_str)
    # Match patterns like "list[Foo]", "List[Foo]"
    for prefix in ("list[", "List["):
        if s.startswith(prefix) and s.endswith("]"):
            inner = s[len(prefix):-1].strip()
            # Inner may be a union like "BaseTool | None"; take the first element
            parts = [p.strip() for p in inner.replace(",", "|").split("|")]
            first = parts[0]
            if first in _PRIMITIVE_TYPES:
                return False
            return True
    return False


def infer_field_policy(
    field_name: str,
    type_str: str,
    is_callback: bool,
    *,
    is_parent_ref: bool = False,
) -> str:
    """Infer the field policy from type information rather than hard-coded sets.

    Returns one of: "skip", "additive", "list_extend", "normal".

    Rules (checked in priority order):
        1. Private fields (``_`` prefix) -> skip
        2. Pydantic internals -> skip
        3. Parent reference fields -> skip
        4. Callable fields with ``_callback`` in the name -> additive
        5. ``list[ComplexType]`` fields -> list_extend
        6. Everything else -> normal
    """
    # 1. Private fields
    if field_name.startswith("_"):
        return "skip"
    # 2. Pydantic internals
    if field_name in _PYDANTIC_INTERNALS:
        return "skip"
    # 3. Parent reference
    if is_parent_ref:
        return "skip"
    # 4. Callback fields
    if is_callback and "_callback" in field_name:
        return "additive"
    # 5. List of complex type
    if _is_list_of_complex_type(type_str):
        return "list_extend"
    # 6. Default
    return "normal"


def get_field_policy(field_name: str, type_str: str, is_callback: bool) -> str:
    """Determine how a field should be handled in the fluent builder.

    Returns one of: "skip", "additive", "list_extend", "normal".

    .. deprecated:: Use :func:`infer_field_policy` instead.
    """
    # Internal / private fields
    if field_name in _ALWAYS_SKIP or field_name.startswith("_"):
        return "skip"
    # Callback fields with _callback suffix get additive semantics
    if is_callback and "_callback" in field_name:
        return "additive"
    # List fields that should use extend semantics
    if field_name in _LIST_EXTEND_FIELDS:
        return "list_extend"
    return "normal"


# ---------------------------------------------------------------------------
# TASK 7: ALIAS ENGINE
# ---------------------------------------------------------------------------

_FIELD_ALIAS_TABLE = {
    "instruction": "instruct",
    "description": "describe",
    "global_instruction": "global_instruct",
    "output_key": "outputs",
    "include_contents": "history",
    "static_instruction": "static",
}

# Additional aliases that map to the same field as an existing alias.
# These are added alongside the primary alias from _FIELD_ALIAS_TABLE.
_EXTRA_ALIASES = {
    "include_history": "include_contents",
}


def generate_aliases(field_names: list[str]) -> dict[str, str]:
    """Generate ergonomic aliases for fields.

    Returns {alias: field_name} for fields that have an entry
    in the alias table or extra aliases table.
    """
    aliases: dict[str, str] = {}
    for field_name in field_names:
        if field_name in _FIELD_ALIAS_TABLE:
            aliases[_FIELD_ALIAS_TABLE[field_name]] = field_name
    # Add extra aliases (secondary short names for the same field)
    for alias, field_name in _EXTRA_ALIASES.items():
        if field_name in field_names:
            aliases[alias] = field_name
    return aliases


def generate_callback_aliases(callback_field_names: list[str]) -> dict[str, str]:
    """Generate short aliases for callback fields by stripping '_callback' suffix.

    Returns {short_name: full_callback_name},
    e.g. {"before_model": "before_model_callback"}.
    """
    aliases: dict[str, str] = {}
    for name in callback_field_names:
        if name.endswith("_callback"):
            short = name[: -len("_callback")]
            aliases[short] = name
    return aliases


# ---------------------------------------------------------------------------
# TASK 8: CONSTRUCTOR ARG DETECTION
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
# TASK 9: OUTPUT MODULE GROUPING
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
# TASK 10: EXTRA METHODS ENGINE
# ---------------------------------------------------------------------------


def generate_extras(class_name: str, tag: str, source_class: str) -> list[dict]:
    """Generate extra (non-field) methods for a builder.

    Returns a list of dicts with keys: name, signature, doc, behavior, target_field.
    """
    extras: list[dict] = []

    if class_name in ("SequentialAgent", "LoopAgent"):
        extras.append(
            {
                "name": "step",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Append an agent as the next step (lazy — built at .build() time).",
                "behavior": "list_append",
                "target_field": "sub_agents",
            }
        )
    elif class_name == "ParallelAgent":
        extras.append(
            {
                "name": "branch",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Add a parallel branch agent (lazy — built at .build() time).",
                "behavior": "list_append",
                "target_field": "sub_agents",
            }
        )
        extras.append(
            {
                "name": "step",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Alias for .branch() — add a parallel branch. Consistent with Pipeline/Loop API.",
                "behavior": "list_append",
                "target_field": "sub_agents",
            }
        )
    elif class_name == "LlmAgent":
        extras.append(
            {
                "name": "tool",
                "signature": "(self, fn_or_tool: Callable | BaseTool) -> Self",
                "doc": "Add a single tool (appends). Multiple .tool() calls accumulate. Use .tools() to replace the full list.",
                "behavior": "list_append",
                "target_field": "tools",
            }
        )
        extras.append(
            {
                "name": "apply",
                "signature": "(self, stack: MiddlewareStack) -> Self",
                "doc": "Apply a reusable middleware stack (bulk callback registration).",
            }
        )
        extras.append(
            {
                "name": "sub_agent",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Add a sub-agent (appends). Multiple .sub_agent() calls accumulate.",
                "behavior": "list_append",
                "target_field": "sub_agents",
            }
        )
        extras.append(
            {
                "name": "member",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Deprecated: use .sub_agent() instead. Add a sub-agent for coordinator pattern.",
                "behavior": "deprecation_alias",
                "target_method": "sub_agent",
            }
        )
        extras.append(
            {
                "name": "delegate",
                "signature": "(self, agent) -> Self",
                "doc": "Add an agent as a delegatable tool (wraps in AgentTool). The coordinator LLM can route to this agent.",
                "behavior": "runtime_helper",
                "helper_func": "delegate_agent",
            }
        )

    # Non-agent classes get no extras
    return extras


# ---------------------------------------------------------------------------
# TASK 11: TOML EMISSION
# ---------------------------------------------------------------------------


def _quote_toml_string(s: str) -> str:
    """Properly quote a string for TOML output."""
    # Use triple-quoted string if it contains quotes or newlines
    if "\n" in s or '"' in s:
        return f'"""{s}"""'
    return f'"{s}"'


def _emit_string_list(items: list[str]) -> str:
    """Format a list of strings for TOML."""
    if not items:
        return "[]"
    inner = ", ".join(f'"{item}"' for item in items)
    return f"[{inner}]"


def emit_seed_toml(
    builders: list[dict],
    global_config: dict,
    adk_version: str = "unknown",
) -> str:
    """Emit a complete seed.toml string from builder definitions and global config.

    Args:
        builders: List of builder dicts with keys: name, source_class, output_module,
                  doc, constructor_args, aliases, callback_aliases, extra_skip_fields,
                  terminals, extras, tag.
        global_config: Dict with keys: skip_fields, additive_fields, list_extend_fields.
        adk_version: ADK version string for the meta section.

    Returns:
        A valid TOML string.
    """
    lines: list[str] = []

    # Meta section
    lines.append("[meta]")
    lines.append('adk_package = "google-adk"')
    lines.append(f'adk_version = "{adk_version}"')
    lines.append(f'generated_at = "{datetime.now(UTC).isoformat()}"')
    lines.append('min_python = "3.11"')
    lines.append('output_package = "adk_fluent"')
    lines.append('output_dir = "src/adk_fluent"')
    lines.append("")

    # Global section
    lines.append("[global]")
    lines.append(f"skip_fields = {_emit_string_list(global_config.get('skip_fields', []))}")
    lines.append(f"additive_fields = {_emit_string_list(global_config.get('additive_fields', []))}")
    lines.append(f"list_extend_fields = {_emit_string_list(global_config.get('list_extend_fields', []))}")
    lines.append("")

    # Field docstring overrides
    field_docs = global_config.get("field_docs", {})
    if field_docs:
        lines.append("[field_docs]")
        for field_name, doc_str in sorted(field_docs.items()):
            lines.append(f"{field_name} = {_quote_toml_string(doc_str)}")
        lines.append("")

    # Builder sections
    for builder in builders:
        name = builder["name"]
        lines.append(f"[builders.{name}]")
        lines.append(f'source_class = "{builder["source_class"]}"')
        lines.append(f'output_module = "{builder["output_module"]}"')
        lines.append(f"doc = {_quote_toml_string(builder.get('doc', ''))}")
        lines.append(f'auto_tag = "{builder.get("tag", "data")}"')
        lines.append(f"constructor_args = {_emit_string_list(builder.get('constructor_args', []))}")
        opt_args = builder.get("optional_constructor_args")
        if opt_args:
            lines.append(f"optional_constructor_args = {_emit_string_list(opt_args)}")
        lines.append(f"extra_skip_fields = {_emit_string_list(builder.get('extra_skip_fields', []))}")
        lines.append("")

        # Aliases
        aliases = builder.get("aliases", {})
        if aliases:
            lines.append(f"[builders.{name}.aliases]")
            for alias, field_name in sorted(aliases.items()):
                lines.append(f'{alias} = "{field_name}"')
            lines.append("")

        # Callback aliases
        cb_aliases = builder.get("callback_aliases", {})
        if cb_aliases:
            lines.append(f"[builders.{name}.callback_aliases]")
            for alias, field_name in sorted(cb_aliases.items()):
                lines.append(f'{alias} = "{field_name}"')
            lines.append("")

        # Terminals
        for terminal in builder.get("terminals", []):
            lines.append(f"[[builders.{name}.terminals]]")
            lines.append(f'name = "{terminal["name"]}"')
            lines.append(f'returns = "{terminal["returns"]}"')
            if "doc" in terminal:
                lines.append(f"doc = {_quote_toml_string(terminal['doc'])}")
            lines.append("")

        # Extras
        for extra in builder.get("extras", []):
            lines.append(f"[[builders.{name}.extras]]")
            lines.append(f'name = "{extra["name"]}"')
            if "signature" in extra:
                lines.append(f'signature = "{extra["signature"]}"')
            if "doc" in extra:
                lines.append(f"doc = {_quote_toml_string(extra['doc'])}")
            if "behavior" in extra:
                lines.append(f'behavior = "{extra["behavior"]}"')
            if "target_field" in extra:
                lines.append(f'target_field = "{extra["target_field"]}"')
            if "target_fields" in extra:
                lines.append(f"target_fields = {_emit_string_list(extra['target_fields'])}")
            if "helper_func" in extra:
                lines.append(f'helper_func = "{extra["helper_func"]}"')
            if "target_method" in extra:
                lines.append(f'target_method = "{extra["target_method"]}"')
            if "example" in extra:
                lines.append(f"example = '''\n{extra['example'].strip()}\n'''")
            if "see_also" in extra:
                lines.append(f"see_also = {_emit_string_list(extra['see_also'])}")
            lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# TASK 12: ORCHESTRATOR
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


def generate_seed_from_manifest(manifest: dict, renames: dict[str, str] | None = None) -> str:
    """Main pipeline: transform a manifest dict into a seed.toml string.

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
    builders: list[dict] = []
    global_skip: set[str] = set()
    global_additive: set[str] = set()
    global_list_extend: set[str] = set()

    for cls_info in manifest["classes"]:
        name = cls_info["name"]
        module = cls_info["module"]
        mro_chain = cls_info["mro_chain"]

        # Step 2: Classify
        tag = classify_class(name, module, mro_chain)

        # Step 3: Filter
        if not is_builder_worthy(tag):
            continue

        # Step 4a: Constructor args
        fields = cls_info.get("fields", [])
        inspection_mode = cls_info.get("inspection_mode", "pydantic")
        init_params = cls_info.get("init_params", [])
        constructor_args = detect_constructor_args(fields, inspection_mode, init_params)

        # Step 4b: Field policies
        callback_fields: list[str] = []
        all_field_names: list[str] = []
        extra_skip_fields: list[str] = []

        for f in fields:
            fname = f["name"]
            ftype = f.get("type_str", "")
            is_cb = f.get("is_callback", False)
            # TODO(A5): replace with MRO-based parent detection
            is_parent_ref = fname == "parent_agent"
            policy = infer_field_policy(fname, ftype, is_cb, is_parent_ref=is_parent_ref)

            if policy == "skip":
                global_skip.add(fname)
            elif policy == "additive":
                global_additive.add(fname)
                callback_fields.append(fname)
            elif policy == "list_extend":
                global_list_extend.add(fname)

            all_field_names.append(fname)

        # Step 4c: Aliases
        aliases = generate_aliases(all_field_names)
        cb_aliases = generate_callback_aliases(callback_fields)

        # Step 4d: Output module
        output_module = determine_output_module(name, tag, module)

        # Step 4e: Extras
        source_class = cls_info.get("qualname", f"{module}.{name}")
        extras = generate_extras(name, tag, source_class)

        # Step 5: Builder name
        builder_name = _builder_name_for_class(name, tag, renames)

        # Step 6: Terminal
        terminals = [{"name": "build", "returns": name, "doc": f"Resolve into a native ADK {name}."}]

        # Step 7: Doc
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

    # Deduplicate builder names: keep the first occurrence of each name,
    # skip later duplicates (same class name from different modules).
    seen_names: set[str] = set()
    deduped: list[dict] = []
    for builder in builders:
        if builder["name"] not in seen_names:
            seen_names.add(builder["name"])
            deduped.append(builder)
    builders = deduped

    # Step 7: Global config
    global_config = {
        "skip_fields": sorted(global_skip),
        "additive_fields": sorted(global_additive),
        "list_extend_fields": sorted(global_list_extend),
    }

    # Step 8: Emit
    adk_version = manifest.get("adk_version", "unknown")
    return emit_seed_toml(builders, global_config, adk_version=adk_version)


# ---------------------------------------------------------------------------
# MANUAL SEED MERGING
# ---------------------------------------------------------------------------

_MANUAL_EXTRA_BEHAVIORS = frozenset(
    {
        "dual_callback",
        "deep_copy",
        "runtime_helper",
        "runtime_helper_async",
        "runtime_helper_async_gen",
        "runtime_helper_ctx",
    }
)


def merge_manual_seed(auto_toml: str, manual_path: str) -> str:
    """Merge a manual seed.toml overlay into auto-generated TOML output.

    1. Parse the auto-generated TOML string.
    2. Load the manual TOML file.
    3. Apply builder renames from [renames] in the manual file.
    4. Append manual extras to the corresponding builder's extras list.
    5. Return the merged TOML string.
    """

    # Parse auto-generated TOML
    auto = tomllib.loads(auto_toml)

    # Load manual TOML
    manual_file = Path(manual_path)
    if not manual_file.exists():
        print(f"WARNING: manual seed {manual_path} not found, skipping merge", file=sys.stderr)
        return auto_toml

    with open(manual_file, "rb") as f:
        manual = tomllib.load(f)

    # Step 1: Extract renames from manual [renames] section
    renames = manual.get("renames", {})

    # Step 2: Apply renames to builder names in the auto dict
    if renames and "builders" in auto:
        old_builders = auto["builders"]
        new_builders = {}
        for builder_name, builder_config in old_builders.items():
            # Check if this builder was generated from a class that should be renamed
            source_class_short = builder_config.get("source_class", "").split(".")[-1]
            new_name = renames.get(source_class_short)
            if new_name and builder_name == source_class_short:
                # Rename this builder
                new_builders[new_name] = builder_config
            else:
                new_builders[builder_name] = builder_config
        auto["builders"] = new_builders

    # Step 2b: Merge field_docs (manual wins on conflict)
    manual_field_docs = manual.get("field_docs", {})
    if manual_field_docs:
        existing_fd = auto.get("field_docs", {})
        existing_fd.update(manual_field_docs)
        auto["field_docs"] = existing_fd

    # Step 3: Merge manual config into matching builders
    manual_builders = manual.get("builders", {})
    for builder_name, manual_config in manual_builders.items():
        if builder_name not in auto.get("builders", {}):
            continue

        # Merge extras (manual overrides replace auto-generated ones with same name)
        manual_extras = manual_config.get("extras", [])
        if manual_extras:
            existing_extras = auto["builders"][builder_name].get("extras", [])
            manual_names = {e["name"] for e in manual_extras}
            # Keep auto extras that aren't overridden, then append manual ones
            merged = [e for e in existing_extras if e["name"] not in manual_names]
            merged.extend(manual_extras)
            auto["builders"][builder_name]["extras"] = merged

        # Merge optional_constructor_args
        opt_args = manual_config.get("optional_constructor_args")
        if opt_args:
            auto["builders"][builder_name]["optional_constructor_args"] = opt_args

    # Re-emit the merged TOML
    builders_list = []
    for name, config in auto.get("builders", {}).items():
        builder = {**config, "name": name}
        builders_list.append(builder)

    global_config = auto.get("global", {})
    # Promote top-level field_docs into global_config for re-emit
    if "field_docs" in auto:
        global_config["field_docs"] = auto["field_docs"]
    adk_version = auto.get("meta", {}).get("adk_version", "unknown")

    return emit_seed_toml(builders_list, global_config, adk_version=adk_version)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Generate seed.toml from manifest.json",
    )
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--merge", help="Path to manual seed.toml overlay to merge")
    args = parser.parse_args()

    # Load manifest
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Load renames from manual file if --merge is specified
    renames = None
    if args.merge:
        merge_path = Path(args.merge)
        if merge_path.exists():
            with open(merge_path, "rb") as f:
                manual = tomllib.load(f)
            renames = manual.get("renames", None)

    # Generate seed (pass renames so builder names are correct before merge)
    toml_str = generate_seed_from_manifest(manifest, renames=renames)

    # Merge manual extras if --merge is specified
    if args.merge:
        toml_str = merge_manual_seed(toml_str, args.merge)

    # Write output
    if args.output:
        Path(args.output).write_text(toml_str)
        print(f"Seed written to {args.output}", file=sys.stderr)
        top_level = [
            line
            for line in toml_str.split("\n")
            if line.startswith("[builders.") and "." not in line[len("[builders.") : -1]
        ]
        print(f"  Builders generated: {len(top_level)}", file=sys.stderr)
    else:
        print(toml_str)


if __name__ == "__main__":
    main()
