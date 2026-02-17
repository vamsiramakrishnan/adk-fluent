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
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent, indent

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
    name: str                           # e.g., "Agent"
    source_class: str                   # e.g., "google.adk.agents.LlmAgent"
    source_class_short: str             # e.g., "LlmAgent"
    output_module: str                  # e.g., "agent"
    doc: str
    constructor_args: list[str]         # Fields passed to __init__
    aliases: dict[str, str]             # fluent_name → pydantic_field_name
    reverse_aliases: dict[str, str]     # pydantic_field_name → fluent_name
    callback_aliases: dict[str, str]    # short_name → full_callback_field_name
    skip_fields: set[str]              # Fields not exposed
    additive_fields: set[str]           # Callback fields with append semantics
    list_extend_fields: set[str]        # List fields with extend semantics
    fields: list[dict]                  # From manifest (all Pydantic fields)
    terminals: list[dict]               # Terminal methods
    extras: list[dict]                  # Extra hand-written methods
    is_composite: bool                  # True if __composite__ (no Pydantic class)
    is_standalone: bool                 # True if __standalone__ (no ADK class at all)
    field_docs: dict[str, str]          # Override docstrings


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
        if not is_composite and not is_standalone:
            cls_data = manifest_classes.get(source_class)
            if cls_data is None:
                # Try matching by class name only
                class_name = source_class.split(".")[-1]
                cls_data = manifest_classes.get(class_name)
            
            if cls_data:
                fields = cls_data.get("fields", [])
                source_short = cls_data["name"]
            else:
                print(f"WARNING: {source_class} not found in manifest for builder {builder_name}",
                      file=sys.stderr)
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
        )
        specs.append(spec)
    
    return specs


# ---------------------------------------------------------------------------
# CODE GENERATION: Runtime .py
# ---------------------------------------------------------------------------

def gen_runtime_imports(spec: BuilderSpec) -> str:
    """Generate import statements for a builder module."""
    lines = [
        '"""Auto-generated by adk-fluent generator. Manual edits will be overwritten."""',
        "",
        "from __future__ import annotations",
        "",
        "from collections import defaultdict",
        "from typing import Any, Callable, Self",
        "",
    ]
    
    if not spec.is_composite and not spec.is_standalone:
        # Import the source class
        module_path = ".".join(spec.source_class.split(".")[:-1])
        class_name = spec.source_class.split(".")[-1]
        lines.append(f"from {module_path} import {class_name}")
    
    return "\n".join(lines)


def gen_alias_maps(spec: BuilderSpec) -> str:
    """Generate the alias and callback alias constants."""
    lines = []
    
    if spec.aliases:
        lines.append(f"_ALIASES: dict[str, str] = {repr(spec.aliases)}")
    else:
        lines.append("_ALIASES: dict[str, str] = {}")
    
    if spec.callback_aliases:
        lines.append(f"_CALLBACK_ALIASES: dict[str, str] = {repr(spec.callback_aliases)}")
    else:
        lines.append("_CALLBACK_ALIASES: dict[str, str] = {}")
    
    additive = spec.additive_fields & {f["name"] for f in spec.fields}
    if additive:
        lines.append(f"_ADDITIVE_FIELDS: set[str] = {repr(additive)}")
    else:
        lines.append("_ADDITIVE_FIELDS: set[str] = set()")
    
    return "\n".join(lines)


def gen_init_method(spec: BuilderSpec) -> str:
    """Generate __init__."""
    params = ", ".join(f"{arg}: str" for arg in spec.constructor_args)
    body_lines = []
    
    if spec.constructor_args:
        config_init = ", ".join(f'"{arg}": {arg}' for arg in spec.constructor_args)
        body_lines.append(f"self._config: dict[str, Any] = {{{config_init}}}")
    else:
        body_lines.append("self._config: dict[str, Any] = {}")
    
    body_lines.append("self._callbacks: dict[str, list[Callable]] = defaultdict(list)")
    body_lines.append("self._lists: dict[str, list] = defaultdict(list)")
    
    body = "\n        ".join(body_lines)
    return f"""
    def __init__(self, {params}) -> None:
        {body}
"""


def gen_alias_methods(spec: BuilderSpec) -> str:
    """Generate explicit alias methods."""
    methods = []
    
    for fluent_name, field_name in spec.aliases.items():
        # Find field info from manifest
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        type_hint = field_info["type_str"] if field_info else "Any"
        doc = spec.field_docs.get(field_name, "")
        if not doc and field_info:
            doc = field_info.get("description", "")
        
        methods.append(f'''
    def {fluent_name}(self, value: {type_hint}) -> Self:
        """{doc or f'Set the `{field_name}` field.'}"""
        self._config["{field_name}"] = value
        return self
''')
    
    return "\n".join(methods)


def gen_callback_methods(spec: BuilderSpec) -> str:
    """Generate additive callback methods."""
    methods = []
    
    for short_name, full_name in spec.callback_aliases.items():
        methods.append(f'''
    def {short_name}(self, fn: Callable) -> Self:
        """Append a callback to `{full_name}`. Multiple calls accumulate."""
        self._callbacks["{full_name}"].append(fn)
        return self
''')
    
    return "\n".join(methods)


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
            body = f'''
        item = agent.build() if hasattr(agent, "build") else agent
        self._lists["{target}"].append(item)
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
        else:
            body = '''
        raise NotImplementedError("Implement in hand-written layer")'''
        
        methods.append(f'''
    def {name}{sig.replace("(self", "(self")}:
        """{doc}"""
        {body.strip()}
''')
    
    return "\n".join(methods)


def gen_getattr_method(spec: BuilderSpec) -> str:
    """Generate the __getattr__ forwarding method."""
    if spec.is_composite or spec.is_standalone:
        return ""  # No Pydantic introspection for these
    
    class_short = spec.source_class_short
    
    return f'''
    def __getattr__(self, name: str):
        """Forward unknown methods to {class_short}.model_fields for zero-maintenance compatibility."""
        if name.startswith("_"):
            raise AttributeError(name)
        
        # Resolve through alias map
        field_name = _ALIASES.get(name, name)
        
        # Check if it's a callback alias
        if name in _CALLBACK_ALIASES:
            cb_field = _CALLBACK_ALIASES[name]
            def _cb_setter(fn: Callable) -> Self:
                self._callbacks[cb_field].append(fn)
                return self
            return _cb_setter
        
        # Validate against actual Pydantic schema
        if field_name not in {class_short}.model_fields:
            available = sorted(
                set({class_short}.model_fields.keys())
                | set(_ALIASES.keys())
                | set(_CALLBACK_ALIASES.keys())
            )
            raise AttributeError(
                f"'{{name}}' is not a recognized field on {class_short}. "
                f"Available: {{', '.join(available)}}"
            )
        
        # Return a setter that stores value and returns self for chaining
        def _setter(value: Any) -> Self:
            if field_name in _ADDITIVE_FIELDS:
                self._callbacks[field_name].append(value)
            else:
                self._config[field_name] = value
            return self
        
        return _setter
'''


def gen_build_method(spec: BuilderSpec) -> str:
    """Generate the build() terminal method."""
    if spec.is_composite or spec.is_standalone:
        return ""  # Hand-written in the template layer
    
    class_short = spec.source_class_short
    
    return f'''
    def build(self) -> {class_short}:
        """{spec.doc} Resolve into a native ADK {class_short}."""
        config = {{**self._config}}
        
        # Merge accumulated callbacks
        for field, fns in self._callbacks.items():
            if fns:
                config[field] = fns if len(fns) > 1 else fns[0]
        
        # Merge accumulated lists
        for field, items in self._lists.items():
            existing = config.get(field, [])
            if isinstance(existing, list):
                config[field] = existing + items
            else:
                config[field] = items
        
        return {class_short}(**config)
'''


def gen_runtime_class(spec: BuilderSpec) -> str:
    """Generate complete runtime class code."""
    sections = [
        f'\nclass {spec.name}:',
        f'    """{spec.doc}"""',
        "",
        gen_init_method(spec),
        "    # --- Ergonomic aliases ---",
        gen_alias_methods(spec),
        "    # --- Additive callback methods ---",
        gen_callback_methods(spec),
        "    # --- Extra methods ---",
        gen_extra_methods(spec),
        "    # --- Dynamic field forwarding ---",
        gen_getattr_method(spec),
        "    # --- Terminal methods ---",
        gen_build_method(spec),
    ]
    
    return "\n".join(sections)


def gen_runtime_module(specs_for_module: list[BuilderSpec]) -> str:
    """Generate a complete .py module for a group of builders."""
    # Collect all unique imports
    all_imports = set()
    import_blocks = []
    
    for spec in specs_for_module:
        import_blocks.append(gen_runtime_imports(spec))
    
    # Deduplicate and combine imports
    seen_imports = set()
    unique_import_lines = []
    for block in import_blocks:
        for line in block.split("\n"):
            if line not in seen_imports:
                seen_imports.add(line)
                unique_import_lines.append(line)
    
    # Generate alias maps and classes
    body_parts = []
    for spec in specs_for_module:
        body_parts.append("\n# " + "=" * 70)
        body_parts.append(f"# Builder: {spec.name}")
        body_parts.append("# " + "=" * 70)
        body_parts.append("")
        body_parts.append(gen_alias_maps(spec))
        body_parts.append(gen_runtime_class(spec))
    
    return "\n".join(unique_import_lines) + "\n" + "\n".join(body_parts)


# ---------------------------------------------------------------------------
# CODE GENERATION: Type Stubs .pyi
# ---------------------------------------------------------------------------

def gen_stub_method(method_name: str, type_hint: str, doc: str = "") -> str:
    """Generate a single .pyi stub method."""
    return f"    def {method_name}(self, value: {type_hint}) -> Self: ..."


def gen_stub_class(spec: BuilderSpec, adk_version: str) -> str:
    """Generate .pyi stub for a single builder."""
    lines = [
        f"class {spec.name}:",
        f'    """{spec.doc}"""',
    ]
    
    # Constructor
    params = ", ".join(f"{arg}: str" for arg in spec.constructor_args)
    lines.append(f"    def __init__(self, {params}) -> None: ...")
    
    # Alias methods (with proper types from manifest)
    for fluent_name, field_name in spec.aliases.items():
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        type_str = field_info["type_str"] if field_info else "Any"
        lines.append(f"    def {fluent_name}(self, value: {type_str}) -> Self: ...")
    
    # Callback methods
    for short_name in spec.callback_aliases:
        lines.append(f"    def {short_name}(self, fn: Callable) -> Self: ...")
    
    # All remaining Pydantic fields (not aliased, not skipped)
    aliased_fields = set(spec.aliases.values())
    callback_fields = set(spec.callback_aliases.values())
    
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
        lines.append(f"    def {fname}(self, value: {type_str}) -> Self: ...")
    
    # Extra methods
    for extra in spec.extras:
        sig = extra.get("signature", "(self) -> Self")
        lines.append(f"    def {extra['name']}{sig}: ...")
    
    # Terminal methods
    for terminal in spec.terminals:
        if "signature" in terminal:
            lines.append(f"    def {terminal['name']}{terminal['signature']}: ...")
        elif "returns" in terminal:
            lines.append(f"    def {terminal['name']}(self) -> {terminal['returns']}: ...")
    
    return "\n".join(lines)


def gen_stub_module(specs_for_module: list[BuilderSpec], adk_version: str) -> str:
    """Generate a complete .pyi stub module."""
    lines = [
        "# AUTO-GENERATED by adk-fluent generator — do not edit manually",
        f"# Generated from google-adk {adk_version}",
        f"# Timestamp: {datetime.now(timezone.utc).isoformat()}",
        "",
        "from typing import Any, AsyncGenerator, Callable, Self",
        "",
    ]
    
    # Collect imports from source classes
    for spec in specs_for_module:
        if not spec.is_composite and not spec.is_standalone:
            module_path = ".".join(spec.source_class.split(".")[:-1])
            class_name = spec.source_class.split(".")[-1]
            lines.append(f"from {module_path} import {class_name}")
    
    lines.append("")
    
    for spec in specs_for_module:
        lines.append(gen_stub_class(spec, adk_version))
        lines.append("")
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CODE GENERATION: Test Scaffolds
# ---------------------------------------------------------------------------

def gen_test_class(spec: BuilderSpec) -> str:
    """Generate equivalence test scaffold for a builder."""
    if spec.is_composite or spec.is_standalone:
        return f'''
class Test{spec.name}Builder:
    """Tests for {spec.name} builder."""
    
    def test_builds_without_error(self):
        """Smoke test: builder creates without crashing."""
        builder = {spec.name}({", ".join(repr(f"test_{a}") for a in spec.constructor_args)})
        assert builder is not None
'''
    
    class_short = spec.source_class_short
    constructor_args_str = ", ".join(repr(f"test_{a}") for a in spec.constructor_args)
    
    lines = [f'''
class Test{spec.name}Builder:
    """Equivalence tests: every fluent chain must produce the same result as native ADK construction."""
    
    def test_minimal_build(self):
        """Minimal builder produces valid {class_short}."""
        agent = {spec.name}({constructor_args_str}).build()
        assert isinstance(agent, {class_short})
        assert agent.name == "test_name"
''']
    
    # Test each alias
    for fluent_name, field_name in spec.aliases.items():
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        if not field_info:
            continue
        
        # Generate a test value based on type
        test_value = _test_value_for_type(field_info["type_str"])
        
        lines.append(f'''
    def test_alias_{fluent_name}(self):
        """.{fluent_name}() sets {field_name} correctly."""
        agent = {spec.name}({constructor_args_str}).{fluent_name}({test_value}).build()
        assert agent.{field_name} == {test_value}
''')
    
    # Test __getattr__ forwarding for non-aliased fields
    non_aliased_count = 0
    aliased_fields = set(spec.aliases.values()) | set(spec.callback_aliases.values())
    
    for field in spec.fields:
        fname = field["name"]
        if fname in spec.skip_fields or fname in aliased_fields:
            continue
        if field["is_callback"]:
            continue
        if non_aliased_count >= 3:  # Sample 3 fields max
            break
        
        test_value = _test_value_for_type(field["type_str"])
        if test_value == "...":  # Can't generate a good test value
            continue
        
        lines.append(f'''
    def test_getattr_{fname}(self):
        """__getattr__ forwarding: .{fname}() sets field correctly."""
        agent = {spec.name}({constructor_args_str}).{fname}({test_value}).build()
        assert agent.{fname} == {test_value}
''')
        non_aliased_count += 1
    
    # Test typo detection
    lines.append(f'''
    def test_typo_raises_attribute_error(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = {spec.name}({constructor_args_str})
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.instuction("oops")  # intentional typo
''')
    
    # Test callback accumulation
    if spec.callback_aliases:
        first_cb = next(iter(spec.callback_aliases.items()))
        lines.append(f'''
    def test_callback_accumulates(self):
        """Multiple .{first_cb[0]}() calls accumulate, not replace."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        agent = (
            {spec.name}({constructor_args_str})
            .{first_cb[0]}(fn1)
            .{first_cb[0]}(fn2)
            .build()
        )
        assert agent.{first_cb[1]} == [fn1, fn2]
''')
    
    return "\n".join(lines)


def gen_test_module(specs_for_module: list[BuilderSpec]) -> str:
    """Generate a complete test module."""
    lines = [
        '"""Auto-generated equivalence tests. Verify fluent builders produce correct ADK objects."""',
        "",
        "import pytest",
        "",
    ]
    
    # Imports
    for spec in specs_for_module:
        lines.append(f"from adk_fluent.{spec.output_module} import {spec.name}")
        if not spec.is_composite and not spec.is_standalone:
            module_path = ".".join(spec.source_class.split(".")[:-1])
            class_name = spec.source_class.split(".")[-1]
            lines.append(f"from {module_path} import {class_name}")
    
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
# ORCHESTRATOR
# ---------------------------------------------------------------------------

def generate_all(seed_path: str, manifest_path: str, output_dir: str,
                 test_dir: str | None = None,
                 stubs_only: bool = False, tests_only: bool = False):
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
            code = gen_runtime_module(module_specs)
            filepath = output_path / f"{module_name}.py"
            filepath.write_text(code)
            print(f"  Generated: {filepath}")
        
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
        init_lines.append("]")
        
        init_path = output_path / "__init__.py"
        init_path.write_text("\n".join(init_lines))
        print(f"  Generated: {init_path}")
    
    # --- Generate .pyi stubs ---
    if not tests_only:
        for module_name, module_specs in by_module.items():
            stub = gen_stub_module(module_specs, adk_version)
            filepath = output_path / f"{module_name}.pyi"
            filepath.write_text(stub)
            print(f"  Generated: {filepath}")
    
    # --- Generate test scaffolds ---
    if test_dir and not stubs_only:
        test_path = Path(test_dir)
        test_path.mkdir(parents=True, exist_ok=True)
        
        for module_name, module_specs in by_module.items():
            test_code = gen_test_module(module_specs)
            filepath = test_path / f"test_{module_name}_builder.py"
            filepath.write_text(test_code)
            print(f"  Generated: {filepath}")
    
    # --- Summary ---
    print(f"\n  Summary:")
    print(f"    ADK version:    {adk_version}")
    print(f"    Builders:       {len(specs)}")
    print(f"    Modules:        {len(by_module)}")
    total_methods = sum(
        len(s.aliases) + len(s.callback_aliases) + len(s.extras) +
        len([f for f in s.fields if f['name'] not in s.skip_fields])
        for s in specs if not s.is_composite and not s.is_standalone
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
