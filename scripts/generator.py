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
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.code_ir import (
        ClassNode, ClassAttr, MethodNode, Param, ModuleNode,
        SubscriptAssign, ReturnStmt, ForAppendStmt, IfStmt, AppendStmt,
        ImportStmt, AssignStmt, RawStmt,
        emit_python, emit_stub,
    )
except ModuleNotFoundError:
    # When running as `python scripts/generator.py`, the scripts package
    # isn't on sys.path.  Fall back to a direct import from the same dir.
    from code_ir import (  # type: ignore[no-redef]
        ClassNode, ClassAttr, MethodNode, Param, ModuleNode,
        SubscriptAssign, ReturnStmt, ForAppendStmt, IfStmt, AppendStmt,
        ImportStmt, AssignStmt, RawStmt,
        emit_python, emit_stub,
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
# CODE GENERATION: Runtime .py
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


def _sort_imports(raw_lines: list[str]) -> str:
    """Sort and group import lines into future / stdlib / third-party / first-party."""
    future, stdlib, third_party, first_party = [], [], [], []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("from __future__"):
            future.append(stripped)
        elif any(stripped.startswith(f"from {mod}") or stripped.startswith(f"import {mod}") for mod in ("adk_fluent",)):
            first_party.append(stripped)
        elif any(stripped.startswith(f"from {mod}") or stripped.startswith(f"import {mod}") for mod in ("google.",)):
            third_party.append(stripped)
        else:
            stdlib.append(stripped)

    groups = []
    for grp in (future, sorted(set(stdlib)), sorted(set(third_party)), sorted(set(first_party))):
        if grp:
            groups.append("\n".join(grp))
    return "\n\n".join(groups)


def gen_alias_maps(spec: BuilderSpec) -> str:
    """Generate the alias and callback alias class-level constants.

    These are emitted *inside* the class body so that multiple builders
    in the same module each get their own copy (avoids the last-writer-wins
    bug with module-level variables).
    """
    lines = []

    if spec.aliases:
        lines.append(f"    _ALIASES: dict[str, str] = {repr(spec.aliases)}")
    else:
        lines.append("    _ALIASES: dict[str, str] = {}")

    if spec.callback_aliases:
        lines.append(f"    _CALLBACK_ALIASES: dict[str, str] = {repr(spec.callback_aliases)}")
    else:
        lines.append("    _CALLBACK_ALIASES: dict[str, str] = {}")

    additive = spec.additive_fields & {f["name"] for f in spec.fields}
    if additive:
        lines.append(f"    _ADDITIVE_FIELDS: set[str] = {repr(additive)}")
    else:
        lines.append("    _ADDITIVE_FIELDS: set[str] = set()")

    # Emit _ADK_TARGET_CLASS for Pydantic-mode builders (used by BuilderBase.__getattr__)
    if not spec.is_composite and not spec.is_standalone and spec.inspection_mode != "init_signature":
        import_name = _adk_import_name(spec)
        lines.append(f"    _ADK_TARGET_CLASS = {import_name}")

    # For init_signature mode, emit a static _KNOWN_PARAMS set from the manifest
    if spec.inspection_mode == "init_signature" and spec.init_params:
        param_names = sorted(
            {p["name"] for p in spec.init_params if p["name"] not in ("self", "args", "kwargs", "kwds")}
        )
        if param_names:
            lines.append(f"    _KNOWN_PARAMS: set[str] = {repr(set(param_names))}")
        else:
            lines.append("    _KNOWN_PARAMS: set[str] = set()")
    elif spec.inspection_mode == "init_signature":
        lines.append("    _KNOWN_PARAMS: set[str] = set()")

    return "\n".join(lines)


def gen_init_method(spec: BuilderSpec) -> str:
    """Generate __init__."""
    required_params = [f"{arg}: str" for arg in spec.constructor_args]
    optional_params = []
    optional_args = spec.optional_constructor_args or []
    for arg in optional_args:
        optional_params.append(f"{arg}: str | None = None")
    all_params = ", ".join(required_params + optional_params)

    body_lines = []

    if spec.constructor_args:
        config_init = ", ".join(f'"{arg}": {arg}' for arg in spec.constructor_args)
        body_lines.append(f"self._config: dict[str, Any] = {{{config_init}}}")
    else:
        body_lines.append("self._config: dict[str, Any] = {}")

    body_lines.append("self._callbacks: dict[str, list[Callable]] = defaultdict(list)")
    body_lines.append("self._lists: dict[str, list] = defaultdict(list)")

    # Set optional args into config if provided
    for arg in optional_args:
        body_lines.append(f"if {arg} is not None:")
        body_lines.append(f'    self._config["{arg}"] = {arg}')

    body = "\n        ".join(body_lines)
    return f"""
    def __init__(self, {all_params}) -> None:
        {body}
"""


def gen_alias_methods(spec: BuilderSpec) -> str:
    """Generate explicit alias methods."""
    methods = []

    for fluent_name, field_name in spec.aliases.items():
        # Find field info from manifest
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        type_hint = field_info["type_str"] if field_info else "Any"
        # Per-alias doc takes priority, then per-field doc, then field description
        doc = spec.field_docs.get(fluent_name, "")
        if not doc:
            doc = spec.field_docs.get(field_name, "")
        if not doc and field_info:
            doc = field_info.get("description", "")

        methods.append(f'''
    def {fluent_name}(self, value: {type_hint}) -> Self:
        """{doc or f"Set the `{field_name}` field."}"""
        self._config["{field_name}"] = value
        return self
''')

    return "\n".join(methods)


def gen_callback_methods(spec: BuilderSpec) -> str:
    """Generate additive callback methods with variadic and conditional support."""
    methods = []

    for short_name, full_name in spec.callback_aliases.items():
        # Variadic version
        methods.append(f'''
    def {short_name}(self, *fns: Callable) -> Self:
        """Append callback(s) to `{full_name}`. Multiple calls accumulate."""
        for fn in fns:
            self._callbacks["{full_name}"].append(fn)
        return self
''')
        # Conditional version
        methods.append(f'''
    def {short_name}_if(self, condition: bool, fn: Callable) -> Self:
        """Append callback to `{full_name}` only if condition is True."""
        if condition:
            self._callbacks["{full_name}"].append(fn)
        return self
''')

    return "\n".join(methods)


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


def gen_extra_methods(spec: BuilderSpec) -> str:
    """Generate extra methods defined in the seed."""
    methods = []

    for extra in spec.extras:
        name = extra["name"]
        sig = extra.get("signature", "(self) -> Self")
        doc = extra.get("doc", "")
        behavior = extra.get("behavior", "custom")
        target = extra.get("target_field", "")

        if behavior == "list_append":
            # Lazy append — building deferred to _prepare_build_config()
            # This allows sub-expression reuse in operators (>> | *)
            body = f'''
        self._lists["{target}"].append(agent)
        return self'''
            # Rewrite signature param name for list_append on tools
            if "fn_or_tool" in sig:
                body = f'''
        self._lists["{target}"].append(fn_or_tool)
        return self'''
            elif "agent" not in sig:
                body = f'''
        self._lists["{target}"].append(value)
        return self'''
        elif behavior == "field_set":
            param_name = sig.split("self, ")[1].split(":")[0].strip() if "self, " in sig else "value"
            body = f'''
        self._config["{target}"] = {param_name}
        return self'''
        elif behavior == "dual_callback":
            target_fields = extra.get("target_fields", [])
            # Extract param name from signature
            if "self, " in sig:
                param_name = sig.split("self, ")[1].split(":")[0].strip()
            else:
                param_name = "fn"
            append_lines = "\n        ".join(f'self._callbacks["{tf}"].append({param_name})' for tf in target_fields)
            body = f"""
        {append_lines}
        return self"""
        elif behavior == "deep_copy":
            # Extract param name from signature
            if "self, " in sig:
                param_name = sig.split("self, ")[1].split(":")[0].strip()
            else:
                param_name = "new_name"
            body = f"""
        from adk_fluent._helpers import deep_clone_builder
        return deep_clone_builder(self, {param_name})"""
        elif behavior == "runtime_helper":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body = f"""
        from adk_fluent._helpers import {helper_func}
        return {helper_func}(self, {args_fwd})"""
        elif behavior == "runtime_helper_async":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body = f"""
        from adk_fluent._helpers import {helper_func}
        return await {helper_func}(self, {args_fwd})"""
        elif behavior == "runtime_helper_async_gen":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body = f"""
        from adk_fluent._helpers import {helper_func}
        async for chunk in {helper_func}(self, {args_fwd}):
            yield chunk"""
        elif behavior == "runtime_helper_ctx":
            helper_func = extra.get("helper_func", name)
            body = f"""
        from adk_fluent._helpers import {helper_func}
        return {helper_func}(self)"""
        elif behavior == "deprecation_alias":
            target_method = extra.get("target_method", name)
            body = f"""
        import warnings
        warnings.warn(
            ".{name}() is deprecated, use .{target_method}() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.{target_method}(agent)"""
        else:
            body = """
        raise NotImplementedError("Implement in hand-written layer")"""

        is_async = behavior in ("runtime_helper_async", "runtime_helper_async_gen")
        async_prefix = "async " if is_async else ""
        methods.append(f'''
    {async_prefix}def {name}{sig.replace("(self", "(self")}:
        """{doc}"""
        {body.strip()}
''')

    return "\n".join(methods)


def gen_field_methods(spec: BuilderSpec) -> str:
    """Generate explicit setter methods for all remaining fields.

    Covers every Pydantic field (or init param) NOT already handled by:
    - constructor args (skip_fields)
    - alias methods
    - callback alias methods
    - extra methods

    This eliminates the need for __getattr__ on the common path while
    keeping __getattr__ as a safety net for fields added after codegen.
    """
    if spec.is_composite or spec.is_standalone:
        return ""

    # Collect names already covered by explicit methods
    aliased_fields = set(spec.aliases.values())
    callback_fields = set(spec.callback_aliases.values())
    extra_names = {e["name"] for e in spec.extras}
    # Aliases are also method names -- don't generate a method that shadows them
    alias_method_names = set(spec.aliases.keys())
    callback_method_names = set(spec.callback_aliases.keys())
    # _if variants too
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

    methods = []

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
            methods.append(f'''
    def {pname}(self, value: {type_str}) -> Self:
        """Set the ``{pname}`` field."""
        self._config["{pname}"] = value
        return self
''')
    else:
        for field in spec.fields:
            fname = field["name"]
            if fname in covered:
                continue
            if fname in spec.constructor_args:
                continue
            if field.get("is_callback") and fname in spec.additive_fields:
                # Additive callback not aliased -- generate append method
                methods.append(f'''
    def {fname}(self, *fns: Callable) -> Self:
        """Append callback(s) to ``{fname}``. Multiple calls accumulate."""
        for fn in fns:
            self._callbacks["{fname}"].append(fn)
        return self
''')
            else:
                type_str = field["type_str"]
                doc = spec.field_docs.get(fname, field.get("description", ""))
                methods.append(f'''
    def {fname}(self, value: {type_str}) -> Self:
        """{doc or f"Set the ``{fname}`` field."}"""
        self._config["{fname}"] = value
        return self
''')

    return "\n".join(methods)


def gen_getattr_method(spec: BuilderSpec) -> str:
    """Generate the __getattr__ forwarding method.

    Returns empty string — __getattr__ is now provided by BuilderBase,
    parameterized via _ADK_TARGET_CLASS and _KNOWN_PARAMS class attributes.
    """
    return ""


def gen_build_method(spec: BuilderSpec) -> str:
    """Generate the build() terminal method."""
    if spec.is_composite or spec.is_standalone:
        return ""  # Hand-written in the template layer

    class_short = _adk_import_name(spec)

    return f'''
    def build(self) -> {class_short}:
        """{spec.doc} Resolve into a native ADK {class_short}."""
        config = self._prepare_build_config()
        return {class_short}(**config)
'''


def gen_runtime_class(spec: BuilderSpec) -> str:
    """Generate complete runtime class code."""
    sections = [
        f"\nclass {spec.name}(BuilderBase):",
        f'    """{spec.doc}"""',
        "",
        "    # --- Class-level alias / field maps ---",
        gen_alias_maps(spec),
        "",
        gen_init_method(spec),
        "    # --- Ergonomic aliases ---",
        gen_alias_methods(spec),
        "    # --- Additive callback methods ---",
        gen_callback_methods(spec),
        "    # --- Explicit field methods ---",
        gen_field_methods(spec),
        "    # --- Extra methods ---",
        gen_extra_methods(spec),
        "    # --- Dynamic field forwarding (safety net) ---",
        gen_getattr_method(spec),
        "    # --- Terminal methods ---",
        gen_build_method(spec),
    ]

    return "\n".join(sections)


def gen_runtime_module(specs_for_module: list[BuilderSpec]) -> str:
    """Generate a complete .py module for a group of builders."""
    # Collect all unique import lines across specs
    all_import_lines: list[str] = []
    for spec in specs_for_module:
        all_import_lines.extend(gen_runtime_imports(spec))

    header = '"""Auto-generated by adk-fluent generator. Manual edits will be overwritten."""\n\nfrom __future__ import annotations\n'
    sorted_imports = _sort_imports(all_import_lines)

    # Generate classes
    body_parts = []
    for spec in specs_for_module:
        body_parts.append("\n# " + "=" * 70)
        body_parts.append(f"# Builder: {spec.name}")
        body_parts.append("# " + "=" * 70)
        body_parts.append(gen_runtime_class(spec))

    return header + "\n" + sorted_imports + "\n" + "\n".join(body_parts)


# ---------------------------------------------------------------------------
# CODE GENERATION: IR-based emission (parallel path)
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

        params.append(Param(
            name=name,
            type=type_str,
            default=default,
            keyword_only=kw_only,
        ))

    return params, return_type


def _ir_class_attrs(spec: BuilderSpec) -> list[ClassAttr]:
    """Build ClassAttr nodes equivalent to gen_alias_maps()."""
    attrs: list[ClassAttr] = []

    attrs.append(ClassAttr("_ALIASES", "dict[str, str]", repr(spec.aliases) if spec.aliases else "{}"))
    attrs.append(ClassAttr("_CALLBACK_ALIASES", "dict[str, str]", repr(spec.callback_aliases) if spec.callback_aliases else "{}"))

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
    for arg in (spec.optional_constructor_args or []):
        params.append(Param(arg, type="str | None", default="None"))

    body: list = []

    if spec.constructor_args:
        config_init = ", ".join(f'"{arg}": {arg}' for arg in spec.constructor_args)
        body.append(AssignStmt("self._config: dict[str, Any]", f"{{{config_init}}}"))
    else:
        body.append(AssignStmt("self._config: dict[str, Any]", "{}"))

    body.append(AssignStmt("self._callbacks: dict[str, list[Callable]]", "defaultdict(list)"))
    body.append(AssignStmt("self._lists: dict[str, list]", "defaultdict(list)"))

    for arg in (spec.optional_constructor_args or []):
        body.append(IfStmt(
            condition=f"{arg} is not None",
            body=(SubscriptAssign("self._config", arg, arg),),
        ))

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

        methods.append(MethodNode(
            name=fluent_name,
            params=[Param("self"), Param("value", type=type_hint)],
            returns="Self",
            doc=doc or f"Set the `{field_name}` field.",
            body=[
                SubscriptAssign("self._config", field_name, "value"),
                ReturnStmt("self"),
            ],
        ))

    return methods


def _ir_callback_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for callback methods equivalent to gen_callback_methods()."""
    methods: list[MethodNode] = []

    for short_name, full_name in spec.callback_aliases.items():
        # Variadic version
        methods.append(MethodNode(
            name=short_name,
            params=[Param("self"), Param("*fns", type="Callable")],
            returns="Self",
            doc=f"Append callback(s) to `{full_name}`. Multiple calls accumulate.",
            body=[
                ForAppendStmt(var="fn", iterable="fns", target="self._callbacks", key=full_name),
                ReturnStmt("self"),
            ],
        ))
        # Conditional version
        methods.append(MethodNode(
            name=f"{short_name}_if",
            params=[Param("self"), Param("condition", type="bool"), Param("fn", type="Callable")],
            returns="Self",
            doc=f"Append callback to `{full_name}` only if condition is True.",
            body=[
                IfStmt(
                    condition="condition",
                    body=(AppendStmt("self._callbacks", full_name, "fn"),),
                ),
                ReturnStmt("self"),
            ],
        ))

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
            methods.append(MethodNode(
                name=pname,
                params=[Param("self"), Param("value", type=type_str)],
                returns="Self",
                doc=f"Set the ``{pname}`` field.",
                body=[
                    SubscriptAssign("self._config", pname, "value"),
                    ReturnStmt("self"),
                ],
            ))
    else:
        for field in spec.fields:
            fname = field["name"]
            if fname in covered:
                continue
            if fname in spec.constructor_args:
                continue
            if field.get("is_callback") and fname in spec.additive_fields:
                methods.append(MethodNode(
                    name=fname,
                    params=[Param("self"), Param("*fns", type="Callable")],
                    returns="Self",
                    doc=f"Append callback(s) to ``{fname}``. Multiple calls accumulate.",
                    body=[
                        ForAppendStmt(var="fn", iterable="fns", target="self._callbacks", key=fname),
                        ReturnStmt("self"),
                    ],
                ))
            else:
                type_str = field["type_str"]
                doc = spec.field_docs.get(fname, field.get("description", ""))
                methods.append(MethodNode(
                    name=fname,
                    params=[Param("self"), Param("value", type=type_str)],
                    returns="Self",
                    doc=doc or f"Set the ``{fname}`` field.",
                    body=[
                        SubscriptAssign("self._config", fname, "value"),
                        ReturnStmt("self"),
                    ],
                ))

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
            body.append(ImportStmt(
                module="adk_fluent._helpers",
                name="deep_clone_builder",
                call=f"return deep_clone_builder(self, {param_name})",
            ))

        elif behavior == "runtime_helper":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(ImportStmt(
                module="adk_fluent._helpers",
                name=helper_func,
                call=f"return {helper_func}(self, {args_fwd})",
            ))

        elif behavior == "runtime_helper_async":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(ImportStmt(
                module="adk_fluent._helpers",
                name=helper_func,
                call=f"return await {helper_func}(self, {args_fwd})",
            ))

        elif behavior == "runtime_helper_async_gen":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(RawStmt(
                f"from adk_fluent._helpers import {helper_func}\n"
                f"async for chunk in {helper_func}(self, {args_fwd}):\n"
                f"    yield chunk"
            ))

        elif behavior == "runtime_helper_ctx":
            helper_func = extra.get("helper_func", name)
            body.append(ImportStmt(
                module="adk_fluent._helpers",
                name=helper_func,
                call=f"return {helper_func}(self)",
            ))

        elif behavior == "deprecation_alias":
            target_method = extra.get("target_method", name)
            body.append(RawStmt(
                f"import warnings\n"
                f"warnings.warn(\n"
                f'    ".{name}() is deprecated, use .{target_method}() instead",\n'
                f"    DeprecationWarning,\n"
                f"    stacklevel=2,\n"
                f")\n"
                f"return self.{target_method}(agent)"
            ))

        else:
            # custom / unknown
            body.append(RawStmt('raise NotImplementedError("Implement in hand-written layer")'))

        methods.append(MethodNode(
            name=name,
            params=params,
            returns=return_type,
            doc=doc,
            body=body,
            is_async=is_async,
            is_generator=is_generator,
        ))

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

    Produces an IR representation equivalent to what gen_runtime_class()
    produces as a string.
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


def specs_to_ir_stub_module(specs: list[BuilderSpec], adk_version: str) -> ModuleNode:
    """Build a ModuleNode suitable for stub (.pyi) emission.

    Reuses spec_to_ir() since emit_stub() already ignores method bodies
    and just outputs ``...`` for each method.
    """
    timestamp = datetime.now(UTC).isoformat()

    all_import_lines: list[str] = [
        "from collections.abc import AsyncGenerator, Callable",
        "from typing import Any, Self",
        "from adk_fluent._base import BuilderBase",
    ]

    for spec in specs:
        if not spec.is_composite and not spec.is_standalone:
            module_path = ".".join(spec.source_class.split(".")[:-1])
            class_name = spec.source_class.split(".")[-1]
            import_name = _adk_import_name(spec)
            if import_name != class_name:
                all_import_lines.append(f"from {module_path} import {class_name} as {import_name}")
            else:
                all_import_lines.append(f"from {module_path} import {class_name}")

    classes = [spec_to_ir(spec) for spec in specs]

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


# ---------------------------------------------------------------------------
# CODE GENERATION: Type Stubs .pyi
# ---------------------------------------------------------------------------


def gen_stub_method(method_name: str, type_hint: str, doc: str = "") -> str:
    """Generate a single .pyi stub method."""
    if doc:
        return f'    def {method_name}(self, value: {type_hint}) -> Self:\n        """{doc}"""\n        ...'
    return f"    def {method_name}(self, value: {type_hint}) -> Self: ..."


def gen_stub_class(spec: BuilderSpec, adk_version: str) -> str:
    """Generate .pyi stub for a single builder."""
    lines = [
        f"class {spec.name}(BuilderBase):",
        f'    """{spec.doc}"""',
    ]

    # Constructor
    required_params = [f"{arg}: str" for arg in spec.constructor_args]
    optional_args = spec.optional_constructor_args or []
    optional_params = [f"{arg}: str | None = None" for arg in optional_args]
    all_params = ", ".join(required_params + optional_params)
    lines.append(f"    def __init__(self, {all_params}) -> None: ...")

    # Alias methods (with proper types from manifest)
    for fluent_name, field_name in spec.aliases.items():
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        type_str = field_info["type_str"] if field_info else "Any"
        doc = spec.field_docs.get(fluent_name, "") or spec.field_docs.get(field_name, "")
        if not doc and field_info:
            doc = field_info.get("description", "")
        if not doc:
            doc = f"Set the ``{field_name}`` field."
        lines.append(f"    def {fluent_name}(self, value: {type_str}) -> Self:")
        lines.append(f'        """{doc}"""')
        lines.append("        ...")

    # Callback methods
    for short_name, full_name in spec.callback_aliases.items():
        lines.append(f"    def {short_name}(self, fn: Callable) -> Self:")
        lines.append(f'        """Append callback to ``{full_name}``. Multiple calls accumulate."""')
        lines.append("        ...")

    # Conditional callback stubs
    for short_name, full_name in spec.callback_aliases.items():
        lines.append(f"    def {short_name}_if(self, condition: bool, fn: Callable) -> Self:")
        lines.append(f'        """Append callback to ``{full_name}`` only if *condition* is True."""')
        lines.append("        ...")

    # All remaining fields (not aliased, not skipped)
    aliased_fields = set(spec.aliases.values())
    callback_fields = set(spec.callback_aliases.values())

    if spec.inspection_mode == "init_signature" and spec.init_params:
        # For init_signature mode, expose init params as stub methods
        for param in spec.init_params:
            pname = param["name"]
            if pname in ("self", "args", "kwargs", "kwds"):
                continue
            if pname in spec.skip_fields:
                continue
            if pname in aliased_fields:
                continue  # Already covered by alias
            if pname in callback_fields:
                continue  # Already covered by callback alias
            if pname in {a["name"] for a in spec.extras}:
                continue  # Already covered by extra
            if pname in spec.constructor_args:
                continue  # Already in constructor

            type_str = param.get("type_str", "Any")
            doc = param.get("description", f"Set the ``{pname}`` parameter.")
            lines.append(f"    def {pname}(self, value: {type_str}) -> Self:")
            lines.append(f'        """{doc}"""')
            lines.append("        ...")
    else:
        # Pydantic mode: list Pydantic fields
        for field in spec.fields:
            fname = field["name"]
            if fname in spec.skip_fields:
                continue
            if fname in aliased_fields:
                continue  # Already covered by alias
            if fname in callback_fields:
                continue  # Already covered by callback alias
            if fname in {a["name"] for a in spec.extras}:
                continue  # Already covered by extra

            type_str = field["type_str"]
            doc = spec.field_docs.get(fname, field.get("description", f"Set the ``{fname}`` field."))
            lines.append(f"    def {fname}(self, value: {type_str}) -> Self:")
            lines.append(f'        """{doc}"""')
            lines.append("        ...")

    # Extra methods
    for extra in spec.extras:
        sig = extra.get("signature", "(self) -> Self")
        doc = extra.get("doc", "")
        behavior = extra.get("behavior", "")
        prefix = "async " if behavior in ("runtime_helper_async", "runtime_helper_async_gen") else ""
        if doc:
            lines.append(f"    {prefix}def {extra['name']}{sig}:")
            lines.append(f'        """{doc}"""')
            lines.append("        ...")
        else:
            lines.append(f"    {prefix}def {extra['name']}{sig}: ...")

    # Terminal methods
    for terminal in spec.terminals:
        t_doc = terminal.get("doc", "")
        if "signature" in terminal:
            if t_doc:
                lines.append(f"    def {terminal['name']}{terminal['signature']}:")
                lines.append(f'        """{t_doc}"""')
                lines.append("        ...")
            else:
                lines.append(f"    def {terminal['name']}{terminal['signature']}: ...")
        elif "returns" in terminal:
            if t_doc:
                lines.append(f"    def {terminal['name']}(self) -> {terminal['returns']}:")
                lines.append(f'        """{t_doc}"""')
                lines.append("        ...")
            else:
                lines.append(f"    def {terminal['name']}(self) -> {terminal['returns']}: ...")

    return "\n".join(lines)


def gen_stub_module(specs_for_module: list[BuilderSpec], adk_version: str) -> str:
    """Generate a complete .pyi stub module."""
    header_lines = [
        "# AUTO-GENERATED by adk-fluent generator — do not edit manually",
        f"# Generated from google-adk {adk_version}",
        f"# Timestamp: {datetime.now(UTC).isoformat()}",
    ]

    raw_imports = [
        "from collections.abc import AsyncGenerator, Callable",
        "from typing import Any, Self",
        "from adk_fluent._base import BuilderBase",
    ]

    # Collect imports from source classes (alias when builder name collides)
    for spec in specs_for_module:
        if not spec.is_composite and not spec.is_standalone:
            module_path = ".".join(spec.source_class.split(".")[:-1])
            class_name = spec.source_class.split(".")[-1]
            import_name = _adk_import_name(spec)
            if import_name != class_name:
                raw_imports.append(f"from {module_path} import {class_name} as {import_name}")
            else:
                raw_imports.append(f"from {module_path} import {class_name}")

    sorted_imports = _sort_imports(raw_imports)

    body_lines = []
    for spec in specs_for_module:
        body_lines.append(gen_stub_class(spec, adk_version))
        body_lines.append("")

    return "\n".join(header_lines) + "\n\n" + sorted_imports + "\n\n" + "\n".join(body_lines)


# ---------------------------------------------------------------------------
# CODE GENERATION: Test Scaffolds
# ---------------------------------------------------------------------------


def gen_test_class(spec: BuilderSpec) -> str:
    """Generate test scaffold for a builder.

    Tests exercise BUILDER MECHANICS only — they never call ``.build()``
    which would attempt to construct real ADK objects (many of which are
    abstract, require complex validators, or need specific value types).
    """
    constructor_args_str = ", ".join(repr(f"test_{a}") for a in spec.constructor_args)

    if spec.is_composite or spec.is_standalone:
        return f'''
class Test{spec.name}Builder:
    """Tests for {spec.name} builder mechanics."""

    def test_builder_creation(self):
        """Smoke test: builder creates without crashing."""
        builder = {spec.name}({constructor_args_str})
        assert builder is not None
'''

    # --- Determine which field and callback to use for accumulation tests ---

    # Pick the first non-skip field to test config accumulation
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

    # --- Build test class ---
    lines = [
        f'''
class Test{spec.name}Builder:
    """Tests for {spec.name} builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = {spec.name}({constructor_args_str})
        assert builder is not None
        assert isinstance(builder._config, dict)
'''
    ]

    # test_chaining_returns_self — pick any alias or config field method
    chain_method = None
    chain_arg = '"test_value"'
    if spec.aliases:
        chain_method = next(iter(spec.aliases))
    elif config_test_field:
        chain_method = config_test_field
        chain_arg = config_test_value or '"test_value"'

    if chain_method:
        lines.append(f'''
    def test_chaining_returns_self(self):
        """.{chain_method}() returns the builder instance for chaining."""
        builder = {spec.name}({constructor_args_str})
        result = builder.{chain_method}({chain_arg})
        assert result is builder
''')

    # test_config_accumulation
    if config_test_field:
        lines.append(f'''
    def test_config_accumulation(self):
        """Setting .{config_test_field}() stores the value in builder._config."""
        builder = {spec.name}({constructor_args_str})
        builder.{config_test_field}({config_test_value})
        assert builder._config["{config_test_field}"] == {config_test_value}
''')

    # test_callback_accumulation
    if spec.callback_aliases:
        first_cb_short, first_cb_full = next(iter(spec.callback_aliases.items()))
        lines.append(f'''
    def test_callback_accumulation(self):
        """Multiple .{first_cb_short}() calls accumulate in builder._callbacks."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        builder = (
            {spec.name}({constructor_args_str})
            .{first_cb_short}(fn1)
            .{first_cb_short}(fn2)
        )
        assert builder._callbacks["{first_cb_full}"] == [fn1, fn2]
''')

    # test_typo_detection
    match_str = "not a recognized parameter" if spec.inspection_mode == "init_signature" else "not a recognized field"
    lines.append(f'''
    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = {spec.name}({constructor_args_str})
        with pytest.raises(AttributeError, match="{match_str}"):
            builder.zzz_not_a_real_field("oops")
''')

    return "\n".join(lines)


def gen_test_module(specs_for_module: list[BuilderSpec]) -> str:
    """Generate a complete test module.

    Tests exercise builder mechanics only — they never import ADK classes
    or call ``.build()``.
    """
    lines = [
        '"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""',
        "",
        "import pytest  # noqa: F401 (used inside test methods)",
        "",
    ]

    # Only import our builder classes — no ADK class imports needed (sorted for I001)
    builder_imports = sorted(f"from adk_fluent.{spec.output_module} import {spec.name}" for spec in specs_for_module)
    lines.extend(builder_imports)

    lines.append("")

    for spec in specs_for_module:
        lines.append(gen_test_class(spec))

    return "\n".join(lines)


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
# CODE GENERATION: IR-based Test Scaffolds
# ---------------------------------------------------------------------------


def spec_to_ir_test(spec: BuilderSpec) -> ClassNode:
    """Build a test ClassNode for a single BuilderSpec.

    Produces the same test methods as gen_test_class() but as IR nodes,
    using RawStmt for assertions since they don't fit standard IR statement types.
    """
    constructor_args_str = ", ".join(repr(f"test_{a}") for a in spec.constructor_args)
    class_name = f"Test{spec.name}Builder"

    methods: list[MethodNode] = []

    # test_builder_creation
    if spec.is_composite or spec.is_standalone:
        methods.append(MethodNode(
            name="test_builder_creation",
            params=[Param("self")],
            doc="Smoke test: builder creates without crashing.",
            body=[
                AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
                RawStmt("assert builder is not None"),
            ],
        ))
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
    methods.append(MethodNode(
        name="test_builder_creation",
        params=[Param("self")],
        doc="Builder constructor stores args in _config.",
        body=[
            AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
            RawStmt("assert builder is not None"),
            RawStmt("assert isinstance(builder._config, dict)"),
        ],
    ))

    # test_chaining_returns_self
    chain_method = None
    chain_arg = '"test_value"'
    if spec.aliases:
        chain_method = next(iter(spec.aliases))
    elif config_test_field:
        chain_method = config_test_field
        chain_arg = config_test_value or '"test_value"'

    if chain_method:
        methods.append(MethodNode(
            name="test_chaining_returns_self",
            params=[Param("self")],
            doc=f".{chain_method}() returns the builder instance for chaining.",
            body=[
                AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
                AssignStmt("result", f"builder.{chain_method}({chain_arg})"),
                RawStmt("assert result is builder"),
            ],
        ))

    # test_config_accumulation
    if config_test_field:
        methods.append(MethodNode(
            name="test_config_accumulation",
            params=[Param("self")],
            doc=f"Setting .{config_test_field}() stores the value in builder._config.",
            body=[
                AssignStmt("builder", f"{spec.name}({constructor_args_str})"),
                RawStmt(f"builder.{config_test_field}({config_test_value})"),
                RawStmt(f'assert builder._config["{config_test_field}"] == {config_test_value}'),
            ],
        ))

    # test_callback_accumulation
    if spec.callback_aliases:
        first_cb_short, first_cb_full = next(iter(spec.callback_aliases.items()))
        methods.append(MethodNode(
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
        ))

    # test_typo_detection
    match_str = "not a recognized parameter" if spec.inspection_mode == "init_signature" else "not a recognized field"
    methods.append(MethodNode(
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
    ))

    return ClassNode(
        name=class_name,
        doc=f"Tests for {spec.name} builder mechanics (no .build() calls).",
        methods=methods,
    )


def specs_to_ir_test_module(specs: list[BuilderSpec]) -> ModuleNode:
    """Build a ModuleNode for test scaffold emission.

    Produces the same output as gen_test_module() but via IR nodes.
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


def generate_all(
    seed_path: str,
    manifest_path: str,
    output_dir: str,
    test_dir: str | None = None,
    stubs_only: bool = False,
    tests_only: bool = False,
    use_ir: bool = False,
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

    if use_ir:
        print("  Using IR emission path")

    # --- Generate runtime .py files ---
    if not stubs_only and not tests_only:
        for module_name, module_specs in by_module.items():
            if use_ir:
                ir_module = specs_to_ir_module(module_specs)
                code = emit_python(ir_module)
            else:
                code = gen_runtime_module(module_specs)
            filepath = output_path / f"{module_name}.py"
            filepath.write_text(code)
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
        init_path.write_text("\n".join(init_lines) + "\n")
        print(f"  Generated: {init_path}")

    # --- Generate .pyi stubs ---
    if not tests_only:
        for module_name, module_specs in by_module.items():
            if use_ir:
                ir_stub_module = specs_to_ir_stub_module(module_specs, adk_version)
                stub = emit_stub(ir_stub_module)
            else:
                stub = gen_stub_module(module_specs, adk_version)
            filepath = output_path / f"{module_name}.pyi"
            filepath.write_text(stub)
            print(f"  Generated: {filepath}")

    # --- Generate test scaffolds ---
    if test_dir and not stubs_only:
        test_path = Path(test_dir)
        test_path.mkdir(parents=True, exist_ok=True)

        for module_name, module_specs in by_module.items():
            if use_ir:
                ir_test_module = specs_to_ir_test_module(module_specs)
                test_code = emit_python(ir_test_module)
            else:
                test_code = gen_test_module(module_specs)
            filepath = test_path / f"test_{module_name}_builder.py"
            filepath.write_text(test_code)
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
    parser.add_argument("--use-ir", action="store_true", help="Use IR-based emission path for .py files")
    args = parser.parse_args()

    generate_all(
        seed_path=args.seed,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        test_dir=args.test_dir,
        stubs_only=args.stubs_only,
        tests_only=args.tests_only,
        use_ir=args.use_ir,
    )


if __name__ == "__main__":
    main()
