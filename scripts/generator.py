#!/usr/bin/env python3
"""
ADK-FLUENT GENERATOR
====================
Combines manifest.json (machine truth from scanner) with seed.toml (human intent)
to produce:
  1. Runtime .py files  — builder classes with __getattr__ forwarding
  2. Type stub .pyi files — full IDE autocomplete and pyright/mypy support
  3. Test scaffolds — equivalence tests for every builder

This is the core of the codegen pipeline:
    seed.toml + manifest.json → src/adk_fluent/*.py + *.pyi + tests/*

Usage:
    python scripts/generator.py seed.toml manifest.json --output-dir src/adk_fluent
    python scripts/generator.py seed.toml manifest.json --stubs-only
    python scripts/generator.py seed.toml manifest.json --tests-only --test-dir tests/
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.code_ir import (
        AppendStmt,
        AssignStmt,
        ClassAttr,
        ClassNode,
        ForAppendStmt,
        IfStmt,
        ImportStmt,
        MethodNode,
        ModuleNode,
        Param,
        RawStmt,
        ReturnStmt,
        SubscriptAssign,
        emit_python,
        emit_stub,
    )
except ModuleNotFoundError:
    # When running as `python scripts/generator.py`, the scripts package
    # isn't on sys.path.  Fall back to a direct import from the same dir.
    from code_ir import (  # type: ignore[no-redef]
        AppendStmt,
        AssignStmt,
        ClassAttr,
        ClassNode,
        ForAppendStmt,
        IfStmt,
        ImportStmt,
        MethodNode,
        ModuleNode,
        Param,
        RawStmt,
        ReturnStmt,
        SubscriptAssign,
        emit_python,
        emit_stub,
    )

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
            inspection_mode=inspection_mode,
            init_params=init_params,
            optional_constructor_args=builder_config.get("optional_constructor_args"),
        )
        specs.append(spec)

    return specs


# ---------------------------------------------------------------------------
# CODE GENERATION HELPERS
# ---------------------------------------------------------------------------


def _adk_import_name(spec: BuilderSpec) -> str:
    """Return the name used to reference the ADK class in generated code.

    When the builder has the same name as the ADK class, we alias the import
    to _ADK_ClassName to avoid shadowing.
    """
    class_name = spec.source_class.split(".")[-1]
    if spec.name == class_name:
        return f"_ADK_{class_name}"
    return class_name


def gen_runtime_imports(spec: BuilderSpec) -> list[str]:
    """Return raw import lines for a single builder spec (no header/grouping)."""
    lines = [
        "from collections import defaultdict",
        "from collections.abc import Callable",
        "from typing import Any, Self",
        "from adk_fluent._base import BuilderBase",
    ]

    if not spec.is_composite and not spec.is_standalone:
        module_path = ".".join(spec.source_class.split(".")[:-1])
        class_name = spec.source_class.split(".")[-1]
        import_name = _adk_import_name(spec)
        if import_name != class_name:
            lines.append(f"from {module_path} import {class_name} as {import_name}")
        else:
            lines.append(f"from {module_path} import {class_name}")

    return lines


def _extract_forwarding_args(sig: str) -> str:
    """Extract parameter names from a signature and build a forwarding argument string.

    Handles keyword-only parameters (those after ``*``) by forwarding them
    as ``name=name`` so the target helper receives them correctly.
    """
    if "self, " in sig:
        params_str = sig.split("(self, ", 1)[1].rsplit(")", 1)[0]
    elif "(self)" in sig:
        return ""
    else:
        params_str = ""
    parts = []
    kw_only = False
    for p in params_str.split(","):
        p = p.strip()
        if not p:
            continue
        if p == "*":
            kw_only = True
            continue
        pname = p.split(":")[0].strip().split("=")[0].strip().lstrip("*")
        if not pname:
            continue
        if kw_only:
            parts.append(f"{pname}={pname}")
        else:
            parts.append(pname)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# CODE GENERATION: IR-based emission
# ---------------------------------------------------------------------------


def _parse_signature(sig: str) -> tuple[list[Param], str | None]:
    """Parse a raw signature string into (params, return_type).

    Handles signatures like:
        (self, agent: BaseAgent | AgentBuilder) -> Self
        (self, fn_or_tool, *, require_confirmation: bool = False) -> Self
        (self) -> Self
        (self)
    """
    # Split off return type
    if " -> " in sig:
        params_part, return_type = sig.rsplit(" -> ", 1)
    else:
        params_part = sig
        return_type = None

    # Strip outer parens
    params_part = params_part.strip()
    if params_part.startswith("("):
        params_part = params_part[1:]
    if params_part.endswith(")"):
        params_part = params_part[:-1]

    params: list[Param] = []
    kw_only = False

    # Split on commas, but be careful about nested types like `dict[str, str]`
    # Use a simple bracket-depth approach
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in params_part:
        if ch in ("(", "[", "{"):
            depth += 1
            current.append(ch)
        elif ch in (")", "]", "}"):
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        remainder = "".join(current).strip()
        if remainder:
            parts.append(remainder)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part == "*":
            kw_only = True
            continue

        # Parse name, type, default
        default = None
        if "=" in part:
            before_eq, default = part.rsplit("=", 1)
            part = before_eq.strip()
            default = default.strip()

        if ":" in part:
            name, type_str = part.split(":", 1)
            name = name.strip()
            type_str = type_str.strip()
        else:
            name = part.strip()
            type_str = None

        params.append(
            Param(
                name=name,
                type=type_str,
                default=default,
                keyword_only=kw_only,
            )
        )

    return params, return_type


def _ir_class_attrs(spec: BuilderSpec) -> list[ClassAttr]:
    """Build ClassAttr nodes equivalent to gen_alias_maps()."""
    attrs: list[ClassAttr] = []

    attrs.append(ClassAttr("_ALIASES", "dict[str, str]", repr(spec.aliases) if spec.aliases else "{}"))
    attrs.append(
        ClassAttr("_CALLBACK_ALIASES", "dict[str, str]", repr(spec.callback_aliases) if spec.callback_aliases else "{}")
    )

    additive = spec.additive_fields & {f["name"] for f in spec.fields}
    attrs.append(ClassAttr("_ADDITIVE_FIELDS", "set[str]", repr(additive) if additive else "set()"))

    if not spec.is_composite and not spec.is_standalone and spec.inspection_mode != "init_signature":
        import_name = _adk_import_name(spec)
        attrs.append(ClassAttr("_ADK_TARGET_CLASS", "", import_name))

    if spec.inspection_mode == "init_signature" and spec.init_params:
        param_names = sorted(
            {p["name"] for p in spec.init_params if p["name"] not in ("self", "args", "kwargs", "kwds")}
        )
        attrs.append(ClassAttr("_KNOWN_PARAMS", "set[str]", repr(set(param_names)) if param_names else "set()"))
    elif spec.inspection_mode == "init_signature":
        attrs.append(ClassAttr("_KNOWN_PARAMS", "set[str]", "set()"))

    return attrs


def _ir_init_method(spec: BuilderSpec) -> MethodNode:
    """Build MethodNode for __init__ equivalent to gen_init_method()."""
    params: list[Param] = [Param("self")]
    for arg in spec.constructor_args:
        params.append(Param(arg, type="str"))
    for arg in spec.optional_constructor_args or []:
        params.append(Param(arg, type="str | None", default="None"))

    body: list = []

    if spec.constructor_args:
        config_init = ", ".join(f'"{arg}": {arg}' for arg in spec.constructor_args)
        body.append(AssignStmt("self._config: dict[str, Any]", f"{{{config_init}}}"))
    else:
        body.append(AssignStmt("self._config: dict[str, Any]", "{}"))

    body.append(AssignStmt("self._callbacks: dict[str, list[Callable]]", "defaultdict(list)"))
    body.append(AssignStmt("self._lists: dict[str, list]", "defaultdict(list)"))

    for arg in spec.optional_constructor_args or []:
        body.append(
            IfStmt(
                condition=f"{arg} is not None",
                body=(SubscriptAssign("self._config", arg, arg),),
            )
        )

    return MethodNode(name="__init__", params=params, returns="None", body=body)


def _ir_alias_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for alias methods equivalent to gen_alias_methods()."""
    methods: list[MethodNode] = []

    for fluent_name, field_name in spec.aliases.items():
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        type_hint = field_info["type_str"] if field_info else "Any"

        doc = spec.field_docs.get(fluent_name, "")
        if not doc:
            doc = spec.field_docs.get(field_name, "")
        if not doc and field_info:
            doc = field_info.get("description", "")

        methods.append(
            MethodNode(
                name=fluent_name,
                params=[Param("self"), Param("value", type=type_hint)],
                returns="Self",
                doc=doc or f"Set the `{field_name}` field.",
                body=[
                    SubscriptAssign("self._config", field_name, "value"),
                    ReturnStmt("self"),
                ],
            )
        )

    return methods


def _ir_callback_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for callback methods equivalent to gen_callback_methods()."""
    methods: list[MethodNode] = []

    for short_name, full_name in spec.callback_aliases.items():
        # Variadic version
        methods.append(
            MethodNode(
                name=short_name,
                params=[Param("self"), Param("*fns", type="Callable[..., Any]")],
                returns="Self",
                doc=f"Append callback(s) to `{full_name}`. Multiple calls accumulate.",
                body=[
                    ForAppendStmt(var="fn", iterable="fns", target="self._callbacks", key=full_name),
                    ReturnStmt("self"),
                ],
            )
        )
        # Conditional version
        methods.append(
            MethodNode(
                name=f"{short_name}_if",
                params=[Param("self"), Param("condition", type="bool"), Param("fn", type="Callable[..., Any]")],
                returns="Self",
                doc=f"Append callback to `{full_name}` only if condition is True.",
                body=[
                    IfStmt(
                        condition="condition",
                        body=(AppendStmt("self._callbacks", full_name, "fn"),),
                    ),
                    ReturnStmt("self"),
                ],
            )
        )

    return methods


def _ir_field_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for field methods equivalent to gen_field_methods()."""
    if spec.is_composite or spec.is_standalone:
        return []

    aliased_fields = set(spec.aliases.values())
    callback_fields = set(spec.callback_aliases.values())
    extra_names = {e["name"] for e in spec.extras}
    alias_method_names = set(spec.aliases.keys())
    callback_method_names = set(spec.callback_aliases.keys())
    callback_if_names = {f"{n}_if" for n in spec.callback_aliases}

    covered = (
        spec.skip_fields
        | aliased_fields
        | callback_fields
        | extra_names
        | alias_method_names
        | callback_method_names
        | callback_if_names
    )

    methods: list[MethodNode] = []

    if spec.inspection_mode == "init_signature" and spec.init_params:
        for param in spec.init_params:
            pname = param["name"]
            if pname in ("self", "args", "kwargs", "kwds"):
                continue
            if pname in covered:
                continue
            if pname in spec.constructor_args:
                continue
            type_str = param.get("type_str", "Any")
            methods.append(
                MethodNode(
                    name=pname,
                    params=[Param("self"), Param("value", type=type_str)],
                    returns="Self",
                    doc=f"Set the ``{pname}`` field.",
                    body=[
                        SubscriptAssign("self._config", pname, "value"),
                        ReturnStmt("self"),
                    ],
                )
            )
    else:
        for field in spec.fields:
            fname = field["name"]
            if fname in covered:
                continue
            if fname in spec.constructor_args:
                continue
            if field.get("is_callback") and fname in spec.additive_fields:
                methods.append(
                    MethodNode(
                        name=fname,
                        params=[Param("self"), Param("*fns", type="Callable[..., Any]")],
                        returns="Self",
                        doc=f"Append callback(s) to ``{fname}``. Multiple calls accumulate.",
                        body=[
                            ForAppendStmt(var="fn", iterable="fns", target="self._callbacks", key=fname),
                            ReturnStmt("self"),
                        ],
                    )
                )
            else:
                type_str = field["type_str"]
                doc = spec.field_docs.get(fname, field.get("description", ""))
                methods.append(
                    MethodNode(
                        name=fname,
                        params=[Param("self"), Param("value", type=type_str)],
                        returns="Self",
                        doc=doc or f"Set the ``{fname}`` field.",
                        body=[
                            SubscriptAssign("self._config", fname, "value"),
                            ReturnStmt("self"),
                        ],
                    )
                )

    return methods


def _ir_extra_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for extra methods equivalent to gen_extra_methods()."""
    methods: list[MethodNode] = []

    for extra in spec.extras:
        name = extra["name"]
        sig = extra.get("signature", "(self) -> Self")
        doc = extra.get("doc", "")
        behavior = extra.get("behavior", "custom")
        target = extra.get("target_field", "")

        params, return_type = _parse_signature(sig)
        is_async = behavior in ("runtime_helper_async", "runtime_helper_async_gen")
        is_generator = behavior == "runtime_helper_async_gen"

        body: list = []

        if behavior == "list_append":
            # Determine which param name to use for append
            if "fn_or_tool" in sig:
                append_value = "fn_or_tool"
            elif "agent" in sig:
                append_value = "agent"
            else:
                append_value = "value"
            body.append(AppendStmt("self._lists", target, append_value))
            body.append(ReturnStmt("self"))

        elif behavior == "field_set":
            param_name = sig.split("self, ")[1].split(":")[0].strip() if "self, " in sig else "value"
            body.append(SubscriptAssign("self._config", target, param_name))
            body.append(ReturnStmt("self"))

        elif behavior == "dual_callback":
            target_fields = extra.get("target_fields", [])
            if "self, " in sig:
                param_name = sig.split("self, ")[1].split(":")[0].strip()
            else:
                param_name = "fn"
            for tf in target_fields:
                body.append(AppendStmt("self._callbacks", tf, param_name))
            body.append(ReturnStmt("self"))

        elif behavior == "deep_copy":
            if "self, " in sig:
                param_name = sig.split("self, ")[1].split(":")[0].strip()
            else:
                param_name = "new_name"
            body.append(
                ImportStmt(
                    module="adk_fluent._helpers",
                    name="deep_clone_builder",
                    call=f"return deep_clone_builder(self, {param_name})",
                )
            )

        elif behavior == "runtime_helper":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(
                ImportStmt(
                    module="adk_fluent._helpers",
                    name=helper_func,
                    call=f"return {helper_func}(self, {args_fwd})",
                )
            )

        elif behavior == "runtime_helper_async":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(
                ImportStmt(
                    module="adk_fluent._helpers",
                    name=helper_func,
                    call=f"return await {helper_func}(self, {args_fwd})",
                )
            )

        elif behavior == "runtime_helper_async_gen":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(
                RawStmt(
                    f"from adk_fluent._helpers import {helper_func}\n"
                    f"async for chunk in {helper_func}(self, {args_fwd}):\n"
                    f"    yield chunk"
                )
            )

        elif behavior == "runtime_helper_ctx":
            helper_func = extra.get("helper_func", name)
            body.append(
                ImportStmt(
                    module="adk_fluent._helpers",
                    name=helper_func,
                    call=f"return {helper_func}(self)",
                )
            )

        elif behavior == "deprecation_alias":
            target_method = extra.get("target_method", name)
            body.append(
                RawStmt(
                    f"import warnings\n"
                    f"warnings.warn(\n"
                    f'    ".{name}() is deprecated, use .{target_method}() instead",\n'
                    f"    DeprecationWarning,\n"
                    f"    stacklevel=2,\n"
                    f")\n"
                    f"return self.{target_method}(agent)"
                )
            )

        else:
            # custom / unknown
            body.append(RawStmt('raise NotImplementedError("Implement in hand-written layer")'))

        methods.append(
            MethodNode(
                name=name,
                params=params,
                returns=return_type,
                doc=doc,
                body=body,
                is_async=is_async,
                is_generator=is_generator,
            )
        )

    return methods


def _ir_build_method(spec: BuilderSpec) -> MethodNode | None:
    """Build MethodNode for build() equivalent to gen_build_method()."""
    if spec.is_composite or spec.is_standalone:
        return None

    class_short = _adk_import_name(spec)

    return MethodNode(
        name="build",
        params=[Param("self")],
        returns=class_short,
        doc=f"{spec.doc} Resolve into a native ADK {class_short}.",
        body=[
            AssignStmt("config", "self._prepare_build_config()"),
            ReturnStmt(f"{class_short}(**config)"),
        ],
    )


def spec_to_ir(spec: BuilderSpec) -> ClassNode:
    """Convert a BuilderSpec into a ClassNode IR.

    Produces an IR representation of a builder class.
    """
    attrs = _ir_class_attrs(spec)

    methods: list[MethodNode] = []
    methods.append(_ir_init_method(spec))
    methods.extend(_ir_alias_methods(spec))
    methods.extend(_ir_callback_methods(spec))
    methods.extend(_ir_field_methods(spec))
    methods.extend(_ir_extra_methods(spec))

    build = _ir_build_method(spec)
    if build:
        methods.append(build)

    return ClassNode(
        name=spec.name,
        bases=["BuilderBase"],
        doc=spec.doc,
        attrs=attrs,
        methods=methods,
    )


def specs_to_ir_module(specs: list[BuilderSpec]) -> ModuleNode:
    """Convert a list of BuilderSpecs into a ModuleNode IR.

    Collects imports from all specs (reusing gen_runtime_imports()),
    converts each spec to a ClassNode, and returns a ModuleNode.
    """
    all_import_lines: list[str] = [
        "from __future__ import annotations",
    ]
    for spec in specs:
        all_import_lines.extend(gen_runtime_imports(spec))

    classes = [spec_to_ir(spec) for spec in specs]

    return ModuleNode(
        doc="Auto-generated by adk-fluent generator. Manual edits will be overwritten.",
        imports=all_import_lines,
        classes=classes,
    )


def _build_type_import_map(manifest: dict) -> dict[str, str]:
    """Build a map of short type names to their fully-qualified import paths.

    Scans all ``type_raw`` fields in the manifest to discover every ADK/genai
    type and its module path, producing entries like:
        ``{"BaseAgent": "from google.adk.agents.base_agent import BaseAgent"}``

    Also performs runtime discovery for types referenced in ``type_str`` but
    missing from ``type_raw`` (e.g. types from forward-reference annotations).
    """
    type_map: dict[str, str] = {}

    # Phase 0: apply explicit overrides (correct defining modules)
    type_map.update(_IMPORT_OVERRIDES)

    # Phase 1: extract from fully-qualified type_raw strings
    for cls in manifest.get("classes", []):
        all_params = cls.get("fields", []) + cls.get("init_params", [])
        for field in all_params:
            raw = field.get("type_raw", "")
            for fqn in re.findall(r"(google\.\w+(?:\.\w+)+)", raw):
                short_name = fqn.split(".")[-1]
                module_path = ".".join(fqn.split(".")[:-1])
                if short_name not in type_map:
                    type_map[short_name] = f"from {module_path} import {short_name}"

    # Phase 2: collect type names from type_str that we can't resolve yet
    _IDENT = re.compile(r"\b([A-Z]\w+)")
    _SKIP = {
        "Any",
        "Self",
        "None",
        "Callable",
        "AsyncGenerator",
        "BuilderBase",
        "Union",
        "Optional",
        "Literal",
        "List",
        "Dict",
        "Tuple",
        "Set",
    }
    unresolved: set[str] = set()
    for cls in manifest.get("classes", []):
        # Scan both fields and init_params for type references
        all_params = cls.get("fields", []) + cls.get("init_params", [])
        for field in all_params:
            for name in _IDENT.findall(field.get("type_str", "")):
                if name not in type_map and name not in _SKIP:
                    unresolved.add(name)

    # Phase 3: runtime discovery for unresolved types
    if unresolved:
        import importlib
        import pkgutil

        try:
            import google.adk

            for _imp, modname, _ispkg in pkgutil.walk_packages(google.adk.__path__, "google.adk."):
                if not unresolved:
                    break
                try:
                    mod = importlib.import_module(modname)
                except Exception:
                    continue
                found = []
                for name in unresolved:
                    if hasattr(mod, name):
                        type_map[name] = f"from {modname} import {name}"
                        found.append(name)
                for name in found:
                    unresolved.discard(name)
        except ImportError:
            pass

    # Add pydantic BaseModel if referenced (fallback if override not present)
    if "BaseModel" not in type_map:
        type_map["BaseModel"] = "from pydantic import BaseModel"

    return type_map


# --- Import correctness overrides ---
# Maps type names to their correct import statements, overriding runtime
# discovery.  Needed because pkgutil.walk_packages finds types in the first
# module that has the attribute, but pyright requires imports from the
# defining module (where __module__ matches or the symbol is assigned).
_IMPORT_OVERRIDES: dict[str, str] = {
    # Pydantic
    "BaseModel": "from pydantic import BaseModel",
    # FastAPI OpenAPI models (re-exported by ADK but not in their __all__)
    "OAuth2": "from fastapi.openapi.models import OAuth2",
    "HTTPBearer": "from fastapi.openapi.models import HTTPBearer",
    "APIKey": "from fastapi.openapi.models import APIKey",
    "HTTPBase": "from fastapi.openapi.models import HTTPBase",
    "OpenIdConnect": "from fastapi.openapi.models import OpenIdConnect",
    "Operation": "from fastapi.openapi.models import Operation",
    # MCP protocol types
    "StdioServerParameters": "from mcp.client.stdio import StdioServerParameters",
    "ProgressFnT": "from mcp.shared.session import ProgressFnT",
    # ADK types where runtime discovery finds wrong re-exporting module
    "ToolPredicate": "from google.adk.tools.base_toolset import ToolPredicate",
    "APIHubClient": "from google.adk.tools.apihub_tool.clients.apihub_client import APIHubClient",
    "BigQueryToolConfig": "from google.adk.tools.bigquery.config import BigQueryToolConfig",
    "BigtableToolSettings": "from google.adk.tools.bigtable.settings import BigtableToolSettings",
    "SpannerToolSettings": "from google.adk.tools.spanner.settings import SpannerToolSettings",
    # AuthScheme is a Union alias defined at module level in auth_schemes
    "AuthScheme": "from google.adk.auth.auth_schemes import AuthScheme",
    # google.genai.types that appear without module prefix after normalization
    "VertexAISearchDataStoreSpec": "from google.genai.types import VertexAISearchDataStoreSpec",
    "ThinkingConfig": "from google.genai.types import ThinkingConfig",
}

# Types that cannot be resolved at stub-generation time (optional deps,
# private internals, forward-only references).  Replaced with ``Any``.
_UNRESOLVABLE_TYPES: set[str] = {
    "Task",  # asyncio.Task (appears as bare "Task" from string annotation)
    "CredentialConfig",  # toolbox_adk.CredentialConfig (optional dependency)
    "_ArtifactEntry",  # private internal type
}

# Module-qualified prefixes in type_str that should be stripped.
# In ADK, "types.X" always means "google.genai.types.X".
_MODULE_PREFIX_REWRITES: dict[str, str] = {
    "types.": "",
    "genai_types.": "",
}

# Module-qualified prefixes that need stdlib imports (kept in type string).
_STDLIB_MODULE_REFS: dict[str, str] = {
    "ssl.": "import ssl",
}


def _normalize_stub_classes(classes: list[ClassNode]) -> list[str]:
    """Normalize type references in stub class method signatures.

    Resolves module-qualified types (``types.Content`` → ``Content``),
    replaces unresolvable types with ``Any``, and tracks additional
    import lines needed (e.g., ``import ssl``).

    Mutates *classes* in place and returns extra import lines.
    """
    extra_imports: list[str] = []
    needs_ssl = False

    def _normalize_type(type_str: str | None) -> str | None:
        nonlocal needs_ssl
        if type_str is None:
            return None
        result = type_str
        # Resolve module-qualified types (types.Content → Content)
        for prefix, replacement in _MODULE_PREFIX_REWRITES.items():
            result = result.replace(prefix, replacement)
        # Check for stdlib module refs (ssl.SSLContext → keep, add import)
        for prefix, _import_line in _STDLIB_MODULE_REFS.items():
            if prefix in result:
                needs_ssl = True
        # Replace unresolvable types with Any
        for utype in _UNRESOLVABLE_TYPES:
            result = re.sub(rf"\b{re.escape(utype)}\b", "Any", result)
        # Ensure bare Callable has type args (pyright requires them)
        result = re.sub(r"\bCallable\b(?!\[)", "Callable[..., Any]", result)
        # Ensure bare AsyncIterator has type args
        result = re.sub(r"\bAsyncIterator\b(?!\[)", "AsyncIterator[Any]", result)
        return result

    for cls in classes:
        for method in cls.methods:
            new_params = []
            for param in method.params:
                new_type = _normalize_type(param.type)
                if new_type != param.type:
                    new_params.append(
                        Param(name=param.name, type=new_type, default=param.default, keyword_only=param.keyword_only)
                    )
                else:
                    new_params.append(param)
            method.params = new_params
            method.returns = _normalize_type(method.returns)

    if needs_ssl:
        extra_imports.append("import ssl")

    return extra_imports


def _resolve_stub_name_conflicts(classes: list[ClassNode], already_imported: set[str]) -> None:
    """Resolve name conflicts where a type import name matches a builder class.

    When a builder class ``Foo`` exists in the module AND ``Foo`` is used
    as a parameter type in another builder's methods, the bare import
    ``from ... import Foo`` conflicts with ``class Foo(BuilderBase):``.

    This function updates method signatures to use ``_ADK_Foo`` (which is
    already imported as the build-target alias) instead of bare ``Foo``.
    """
    builder_names = {cls.name for cls in classes}

    for cls in classes:
        for method in cls.methods:
            new_params = []
            for param in method.params:
                if param.type:
                    new_type = param.type
                    for bname in builder_names:
                        # Only replace if the _ADK_ aliased import exists
                        if bname in new_type and f"_ADK_{bname}" in already_imported:
                            new_type = re.sub(rf"\b(?<!_ADK_){bname}\b", f"_ADK_{bname}", new_type)
                    if new_type != param.type:
                        new_params.append(
                            Param(
                                name=param.name, type=new_type, default=param.default, keyword_only=param.keyword_only
                            )
                        )
                    else:
                        new_params.append(param)
                else:
                    new_params.append(param)
            method.params = new_params


# Stdlib typing names that need explicit imports when referenced in stubs.
_TYPING_NAMES: dict[str, str] = {
    "Union": "typing",
    "Optional": "typing",
    "Literal": "typing",
    "Awaitable": "collections.abc",
    "AsyncIterator": "collections.abc",
    "Mapping": "collections.abc",
    "Sequence": "collections.abc",
    "Dict": "typing",
    "TextIO": "typing",
}


def _collect_stub_type_refs(classes: list[ClassNode]) -> set[str]:
    """Walk all method signatures in *classes* and return referenced type names."""
    refs: set[str] = set()
    _IDENT = re.compile(r"\b([A-Z]\w+)")
    # Strip Literal[...] contents so string values like Literal['BaseAgent']
    # don't create false-positive type references.
    _LITERAL_CONTENT = re.compile(r"(Literal\[)[^\]]*\]")

    def _scan(type_str: str) -> None:
        cleaned = _LITERAL_CONTENT.sub(r"\1]", type_str)
        refs.update(_IDENT.findall(cleaned))

    for cls in classes:
        for method in cls.methods:
            for param in method.params:
                if param.type:
                    _scan(param.type)
            if method.returns:
                _scan(method.returns)
    return refs


def specs_to_ir_stub_module(specs: list[BuilderSpec], adk_version: str, *, manifest: dict | None = None) -> ModuleNode:
    """Build a ModuleNode suitable for stub (.pyi) emission.

    Reuses spec_to_ir() since emit_stub() already ignores method bodies
    and just outputs ``...`` for each method.

    When *manifest* is provided, the emitted imports are auto-discovered
    from type references in method signatures so that pyright/mypy can
    resolve every annotation.
    """
    timestamp = datetime.now(UTC).isoformat()

    classes = [spec_to_ir(spec) for spec in specs]

    # --- Pre-processing: normalize types in method signatures ---
    extra_imports = _normalize_stub_classes(classes)

    # Collect all type names referenced in method signatures
    refs = _collect_stub_type_refs(classes)

    # --- Build imports based on what's actually referenced ---
    all_import_lines: list[str] = list(extra_imports)
    already_imported: set[str] = set()

    # 1. Base stdlib typing imports — only include names that are referenced
    _BASE_COLLECTIONS = {"AsyncGenerator", "Callable"}
    _BASE_TYPING = {"Any", "Self"}
    needed_collections = sorted(_BASE_COLLECTIONS & refs)
    needed_typing = sorted(_BASE_TYPING & refs)
    if needed_collections:
        all_import_lines.append(f"from collections.abc import {', '.join(needed_collections)}")
        already_imported.update(needed_collections)
    if needed_typing:
        all_import_lines.append(f"from typing import {', '.join(needed_typing)}")
        already_imported.update(needed_typing)

    # 2. Internal import — always needed for base class
    all_import_lines.append("from adk_fluent._base import BuilderBase")
    already_imported.add("BuilderBase")

    # 3. ADK source class imports (build targets)
    builder_names = {cls.name for cls in classes}
    for spec in specs:
        if not spec.is_composite and not spec.is_standalone:
            module_path = ".".join(spec.source_class.split(".")[:-1])
            class_name = spec.source_class.split(".")[-1]
            import_name = _adk_import_name(spec)
            if import_name != class_name:
                all_import_lines.append(f"from {module_path} import {class_name} as {import_name}")
            else:
                all_import_lines.append(f"from {module_path} import {class_name}")
            already_imported.add(import_name)

    # 4. Additional stdlib typing imports (Union, Optional, Literal, etc.)
    typing_needed: dict[str, list[str]] = {}
    for name in sorted(refs):
        if name in already_imported:
            continue
        if name in _TYPING_NAMES:
            module = _TYPING_NAMES[name]
            typing_needed.setdefault(module, []).append(name)
            already_imported.add(name)
    for module, names in sorted(typing_needed.items()):
        all_import_lines.append(f"from {module} import {', '.join(sorted(names))}")

    # 5. Domain type imports (ADK/genai types) from manifest
    if manifest:
        type_map = _build_type_import_map(manifest)
        for name in sorted(refs):
            if name in already_imported:
                continue
            # Skip types that conflict with builder class names — these
            # are already imported as _ADK_ aliases via build targets.
            if name in builder_names and f"_ADK_{name}" in already_imported:
                continue
            if name in type_map:
                all_import_lines.append(type_map[name])
                already_imported.add(name)

    # 6. Resolve name conflicts: update method signatures to use _ADK_ prefix
    # where a bare type name would shadow a builder class definition.
    _resolve_stub_name_conflicts(classes, already_imported)

    header = (
        f"AUTO-GENERATED by adk-fluent generator -- do not edit manually\n"
        f"Generated from google-adk {adk_version}\n"
        f"Timestamp: {timestamp}"
    )

    return ModuleNode(
        doc=header,
        imports=all_import_lines,
        classes=classes,
    )


def _test_value_for_type(type_str: str) -> str:
    """Generate a reasonable test value for a given type string."""
    ts = type_str.lower().strip()

    if ts == "str" or "str |" in ts or "| str" in ts:
        return '"test_value"'
    if ts == "bool":
        return "True"
    if ts == "int":
        return "42"
    if ts == "float":
        return "0.5"
    if ts.startswith("list"):
        return "[]"
    if ts.startswith("dict"):
        return "{}"
    if "none" in ts:
        return "None"

    return "..."


# ---------------------------------------------------------------------------
# CODE GENERATION: Test Scaffolds
# ---------------------------------------------------------------------------


def spec_to_ir_test(spec: BuilderSpec) -> ClassNode:
    """Build a test ClassNode for a single BuilderSpec.

    Produces test methods as IR nodes, using RawStmt for assertions
    since they don't fit standard IR statement types.
    """
    constructor_args_str = ", ".join(repr(f"test_{a}") for a in spec.constructor_args)
    class_name = f"Test{spec.name}Builder"

    methods: list[MethodNode] = []

    # test_builder_creation
    if spec.is_composite or spec.is_standalone:
        methods.append(
            MethodNode(
                name="test_builder_creation",
                params=[Param("self")],
                doc="Smoke test: builder creates without crashing.",
                body=[
                    AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
                    RawStmt("assert builder is not None"),
                ],
            )
        )
        return ClassNode(
            name=class_name,
            doc=f"Tests for {spec.name} builder mechanics.",
            methods=methods,
        )

    # --- Non-composite/standalone builders get full test coverage ---

    # Determine config test field and value
    config_test_field = None
    config_test_value = None

    if spec.inspection_mode == "init_signature" and spec.init_params:
        for param in spec.init_params:
            pname = param["name"]
            if pname in ("self", "args", "kwargs", "kwds"):
                continue
            if pname in spec.skip_fields or pname in spec.constructor_args:
                continue
            tv = _test_value_for_type(param.get("type_str", "Any"))
            if tv == "...":
                continue
            config_test_field = pname
            config_test_value = tv
            break
    else:
        aliased_fields = set(spec.aliases.values()) | set(spec.callback_aliases.values())
        for field in spec.fields:
            fname = field["name"]
            if fname in spec.skip_fields or fname in aliased_fields:
                continue
            if field.get("is_callback"):
                continue
            tv = _test_value_for_type(field["type_str"])
            if tv == "...":
                continue
            config_test_field = fname
            config_test_value = tv
            break

    # test_builder_creation
    methods.append(
        MethodNode(
            name="test_builder_creation",
            params=[Param("self")],
            doc="Builder constructor stores args in _config.",
            body=[
                AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
                RawStmt("assert builder is not None"),
                RawStmt("assert isinstance(builder._config, dict)"),
            ],
        )
    )

    # test_chaining_returns_self
    chain_method = None
    chain_arg = '"test_value"'
    if spec.aliases:
        chain_method = next(iter(spec.aliases))
    elif config_test_field:
        chain_method = config_test_field
        chain_arg = config_test_value or '"test_value"'

    if chain_method:
        methods.append(
            MethodNode(
                name="test_chaining_returns_self",
                params=[Param("self")],
                doc=f".{chain_method}() returns the builder instance for chaining.",
                body=[
                    AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
                    AssignStmt("result", f"builder.{chain_method}({chain_arg})"),
                    RawStmt("assert result is builder"),
                ],
            )
        )

    # test_config_accumulation
    if config_test_field:
        methods.append(
            MethodNode(
                name="test_config_accumulation",
                params=[Param("self")],
                doc=f"Setting .{config_test_field}() stores the value in builder._config.",
                body=[
                    AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
                    RawStmt(f"builder.{config_test_field}({config_test_value})"),
                    RawStmt(f'assert builder._config["{config_test_field}"] == {config_test_value}'),
                ],
            )
        )

    # test_callback_accumulation
    if spec.callback_aliases:
        first_cb_short, first_cb_full = next(iter(spec.callback_aliases.items()))
        methods.append(
            MethodNode(
                name="test_callback_accumulation",
                params=[Param("self")],
                doc=f"Multiple .{first_cb_short}() calls accumulate in builder._callbacks.",
                body=[
                    RawStmt("fn1 = lambda ctx: None"),
                    RawStmt("fn2 = lambda ctx: None"),
                    RawStmt(
                        f"builder = (\n"
                        f"    {spec.name}({constructor_args_str})\n"
                        f"    .{first_cb_short}(fn1)\n"
                        f"    .{first_cb_short}(fn2)\n"
                        f")"
                    ),
                    RawStmt(f'assert builder._callbacks["{first_cb_full}"] == [fn1, fn2]'),
                ],
            )
        )

    # test_typo_detection
    match_str = "not a recognized parameter" if spec.inspection_mode == "init_signature" else "not a recognized field"
    methods.append(
        MethodNode(
            name="test_typo_detection",
            params=[Param("self")],
            doc="Typos in method names raise clear AttributeError.",
            body=[
                AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
                RawStmt(
                    f'with pytest.raises(AttributeError, match="{match_str}"):\n'
                    f'    builder.zzz_not_a_real_field("oops")'
                ),
            ],
        )
    )

    return ClassNode(
        name=class_name,
        doc=f"Tests for {spec.name} builder mechanics (no .build() calls).",
        methods=methods,
    )


def specs_to_ir_test_module(specs: list[BuilderSpec]) -> ModuleNode:
    """Build a ModuleNode for test scaffold emission.

    Produces a test module via IR nodes.
    """
    import_lines: list[str] = [
        "import pytest  # noqa: F401 (used inside test methods)",
    ]

    for spec in sorted(specs, key=lambda s: s.output_module):
        import_lines.append(f"from adk_fluent.{spec.output_module} import {spec.name}")

    classes = [spec_to_ir_test(spec) for spec in specs]

    return ModuleNode(
        doc="Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects.",
        imports=import_lines,
        classes=classes,
    )


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------


def _extract_all_from_file(py_file: Path) -> list[str] | None:
    """Extract __all__ list from a Python file using ast."""
    import ast

    try:
        tree = ast.parse(py_file.read_text())
    except SyntaxError:
        return None

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, ast.List):
                    names = []
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            names.append(elt.value)
                    return names
    return None


def _discover_manual_exports(output_dir: str) -> list[tuple[str, list[str]]]:
    """Auto-discover manual Python files and their __all__ exports.

    Scans the output directory for .py files that weren't generated,
    and also scans subdirectory packages (*/__init__.py) for exports.
    """
    output_path = Path(output_dir)
    result = []

    # Top-level .py files
    for py_file in sorted(output_path.glob("*.py")):
        if py_file.name == "__init__.py":
            continue

        all_names = _extract_all_from_file(py_file)
        if all_names:
            module_name = f".{py_file.stem}"
            result.append((module_name, all_names))

    # Subdirectory packages (*/__init__.py)
    for init_file in sorted(output_path.glob("*/__init__.py")):
        pkg_name = init_file.parent.name
        all_names = _extract_all_from_file(init_file)
        if all_names:
            module_name = f".{pkg_name}"
            result.append((module_name, all_names))

        # Also scan non-__init__ .py files inside the subpackage
        for sub_file in sorted(init_file.parent.glob("*.py")):
            if sub_file.name == "__init__.py":
                continue
            sub_names = _extract_all_from_file(sub_file)
            if sub_names:
                sub_module = f".{pkg_name}.{sub_file.stem}"
                result.append((sub_module, sub_names))

    return result


def _write_file(path: Path, content: str):
    """Write content to a file.
    If the file exists and is read-only, make it writable first.
    """
    if path.exists():
        # Make it writable if it's read-only
        current_mode = os.stat(path).st_mode
        if not current_mode & stat.S_IWUSR:
            os.chmod(path, current_mode | stat.S_IWUSR)

    path.write_text(content)


def generate_all(
    seed_path: str,
    manifest_path: str,
    output_dir: str,
    test_dir: str | None = None,
    stubs_only: bool = False,
    tests_only: bool = False,
):
    """Main generation pipeline."""
    seed = parse_seed(seed_path)
    manifest = parse_manifest(manifest_path)
    specs = resolve_builder_specs(seed, manifest)

    adk_version = manifest.get("adk_version", "unknown")

    # Group specs by output module
    by_module: dict[str, list[BuilderSpec]] = defaultdict(list)
    for spec in specs:
        by_module[spec.output_module].append(spec)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # --- Generate runtime .py files ---
    if not stubs_only and not tests_only:
        for module_name, module_specs in by_module.items():
            ir_module = specs_to_ir_module(module_specs)
            code = emit_python(ir_module)
            filepath = output_path / f"{module_name}.py"
            _write_file(filepath, code)
            print(f"  Generated: {filepath}")

        # Auto-discover manual module exports first (needed for __all__)
        generated_modules = set(by_module.keys())
        manual_exports = _discover_manual_exports(output_dir)
        manual_names: list[str] = []
        manual_import_lines: list[str] = []
        for module_name, names in manual_exports:
            stem = module_name.lstrip(".")
            if stem in generated_modules:
                continue
            for name in names:
                manual_names.append(name)
                manual_import_lines.append(f"from {module_name} import {name}")

        # Generate __init__.py with re-exports
        init_lines = [
            '"""adk-fluent: Fluent builder API for Google ADK."""',
            f"# Auto-generated for google-adk {adk_version}",
            "",
        ]
        for spec in specs:
            init_lines.append(f"from .{spec.output_module} import {spec.name}")

        init_lines.append("")
        init_lines.append("__all__ = [")
        for spec in specs:
            init_lines.append(f'    "{spec.name}",')
        for name in manual_names:
            init_lines.append(f'    "{name}",')
        init_lines.append("]")

        if manual_import_lines:
            init_lines.append("")
            init_lines.append("# --- Manual module exports (auto-discovered from __all__) ---")
            init_lines.extend(manual_import_lines)

        init_path = output_path / "__init__.py"
        _write_file(init_path, "\n".join(init_lines) + "\n")
        print(f"  Generated: {init_path}")

    # --- Generate .pyi stubs ---
    if not tests_only:
        for module_name, module_specs in by_module.items():
            ir_stub_module = specs_to_ir_stub_module(module_specs, adk_version, manifest=manifest)
            stub = emit_stub(ir_stub_module)
            filepath = output_path / f"{module_name}.pyi"
            _write_file(filepath, stub)
            print(f"  Generated: {filepath}")

    # --- Generate test scaffolds ---
    if test_dir and not stubs_only:
        test_path = Path(test_dir)
        test_path.mkdir(parents=True, exist_ok=True)

        for module_name, module_specs in by_module.items():
            ir_test_module = specs_to_ir_test_module(module_specs)
            test_code = emit_python(ir_test_module)
            filepath = test_path / f"test_{module_name}_builder.py"
            _write_file(filepath, test_code)
            print(f"  Generated: {filepath}")

    # --- Summary ---
    print("\n  Summary:")
    print(f"    ADK version:    {adk_version}")
    print(f"    Builders:       {len(specs)}")
    print(f"    Modules:        {len(by_module)}")

    def _count_forwarded(s: BuilderSpec) -> int:
        if s.inspection_mode == "init_signature" and s.init_params:
            return len(
                [
                    p
                    for p in s.init_params
                    if p["name"] not in ("self", "args", "kwargs", "kwds") and p["name"] not in s.skip_fields
                ]
            )
        return len([f for f in s.fields if f["name"] not in s.skip_fields])

    total_methods = sum(
        len(s.aliases) + len(s.callback_aliases) + len(s.extras) + _count_forwarded(s)
        for s in specs
        if not s.is_composite and not s.is_standalone
    )
    print(f"    Total methods:  ~{total_methods} (aliases + callbacks + forwarded)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Generate adk-fluent code from seed + manifest")
    parser.add_argument("seed", help="Path to seed.toml")
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("--output-dir", default="src/adk_fluent", help="Output directory for generated code")
    parser.add_argument("--test-dir", default=None, help="Output directory for test scaffolds")
    parser.add_argument("--stubs-only", action="store_true", help="Generate only .pyi stubs")
    parser.add_argument("--tests-only", action="store_true", help="Generate only test scaffolds")
    args = parser.parse_args()

    generate_all(
        seed_path=args.seed,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        test_dir=args.test_dir,
        stubs_only=args.stubs_only,
        tests_only=args.tests_only,
    )


if __name__ == "__main__":
    main()
