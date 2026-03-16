#!/usr/bin/env python3
"""
A2UI CODE GENERATOR
===================
Reads a2ui_seed.toml (or JSON) and generates:
  - src/adk_fluent/_ui_generated.py  — typed component & function factories
  - src/adk_fluent/_ui_generated.pyi — type stubs for IDE completion
  - tests/generated/test_ui_generated.py — scaffolded tests

Pipeline:
    a2ui_seed.toml → _ui_generated.py + _ui_generated.pyi + test_ui_generated.py

Usage:
    python scripts/a2ui/generator.py seeds/a2ui_seed.toml \
        --output-dir src/adk_fluent --test-dir tests/generated
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from scripts.shared import load_toml_or_json as _load_seed

# ---------------------------------------------------------------------------
# PYTHON TYPE MAPPING
# ---------------------------------------------------------------------------

_PY_TYPE_MAP = {
    "str | UIBinding": "str | UIBinding",
    "int | float | UIBinding": "int | float | UIBinding",
    "bool | UIBinding": "bool | UIBinding",
    "list[str] | UIBinding": "list[str] | UIBinding",
    "Any": "Any",
    "str": "str",
    "int | float": "int | float",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "dict[str, Any]": "dict[str, Any]",
    "list[str]": "list[str]",
    "list[dict]": "list[dict[str, Any]]",
    "tuple[UIComponent, ...]": "tuple[UIComponent, ...]",
    "UIAction | str": "UIAction | str",
}


def _py_type(seed_type: str) -> str:
    """Resolve seed type string to Python type annotation."""
    return _PY_TYPE_MAP.get(seed_type, "Any")


def _default_repr(value: Any) -> str:
    """Represent a default value as Python source code."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "None"
        return repr(value)
    return repr(value)


# ---------------------------------------------------------------------------
# COMPONENT FACTORY GENERATION
# ---------------------------------------------------------------------------

# Properties that are handled structurally (not as user-facing kwargs)
_STRUCTURAL_PROPS = {"children", "child", "trigger", "content", "tabs", "action"}


def _gen_component_factory(comp: dict) -> str:
    """Generate a single component factory method."""
    name = comp["name"]
    factory = comp["factory_name"]
    category = comp["category"]
    desc = comp.get("description", f"{name} component.")
    has_children = comp.get("has_children", False)
    child_mode = comp.get("child_mode")
    has_action = comp.get("has_action", False)
    has_checks = comp.get("has_checks", False)
    has_bind = comp.get("has_bind", False)

    # Build parameter list
    params: list[str] = []
    kw_params: list[str] = []
    doc_params: list[str] = []

    # Children as *args for list-mode containers
    if has_children and child_mode == "list":
        params.append("*children: UIComponent")
        doc_params.append("*children: Child components.")

    # Required args (positional)
    required = comp.get("required_args", [])
    optional = comp.get("optional_args", [])
    types = comp.get("arg_types", {})
    defaults = comp.get("default_values", {})
    enums = comp.get("enum_values", {})

    for arg in required:
        if arg in _STRUCTURAL_PROPS:
            continue
        py_type = _py_type(types.get(arg, "str"))
        params.append(f"{arg}: {py_type}")
        doc_params.append(f"{arg}: Required.")

    # Keyword-only marker (if we have positional args and keyword args)
    if params and not any("*" in p for p in params):
        kw_params.append("*")

    # Optional args (keyword)
    for arg in optional:
        if arg in _STRUCTURAL_PROPS:
            continue
        py_type = _py_type(types.get(arg, "str"))
        default = defaults.get(arg)
        default_str = _default_repr(default)
        kw_params.append(f"{arg}: {py_type} = {default_str}")
        if enums.get(arg):
            doc_params.append(f"{arg}: One of {enums[arg]}. Default: {default_str}.")

    # Special params
    if has_bind:
        kw_params.append("bind: str | None = None")
        doc_params.append("bind: JSON Pointer path for two-way data binding.")

    if has_checks:
        kw_params.append("checks: list[UICheck] | None = None")
        doc_params.append("checks: Validation rules.")

    if has_action:
        kw_params.append("action: str | None = None")
        doc_params.append("action: Server event name to dispatch on click.")

    if has_children and child_mode == "single":
        kw_params.append("child: UIComponent | None = None")
        doc_params.append("child: Single child component.")

    if has_children and child_mode == "tabs":
        kw_params.append("tabs: list[tuple[str, UIComponent]] | None = None")
        doc_params.append("tabs: List of (title, child_component) tuples.")

    # Always allow explicit ID
    kw_params.append("id: str | None = None")

    # Build signature
    all_params = params + kw_params
    sig = ", ".join(all_params)

    # Build body
    body_lines: list[str] = []

    # Bindings
    if has_bind:
        body_lines.append("_bindings = (UIBinding(path=bind),) if bind else ()")

    # Checks
    if has_checks:
        body_lines.append("_checks = tuple(checks) if checks else ()")

    # Action
    if has_action:
        body_lines.append("_action = UIAction(event=action) if action else None")

    # Children
    if has_children and child_mode == "list":
        body_lines.append("_children = children")
    elif has_children and child_mode == "single":
        body_lines.append("_children = (child,) if child else ()")
    elif has_children and child_mode == "tabs":
        body_lines.append("_children = tuple(c for _, c in (tabs or []))")
        body_lines.append("_tabs_meta = [(t, '') for t, _ in (tabs or [])]")

    # Build _component call
    call_args: list[str] = [repr(name)]
    call_kwargs: list[str] = ["id=id"]

    for arg in required:
        if arg in _STRUCTURAL_PROPS:
            continue
        call_kwargs.append(f"{arg}={arg}")

    for arg in optional:
        if arg in _STRUCTURAL_PROPS:
            continue
        call_kwargs.append(f"{arg}={arg}")

    if has_children:
        call_kwargs.append("_children=_children")
    if has_bind:
        call_kwargs.append("_bindings=_bindings")
    if has_checks:
        call_kwargs.append("_checks=_checks")
    if has_action:
        call_kwargs.append("_action=_action")

    call_str = f"_component({', '.join(call_args)}, {', '.join(call_kwargs)})"
    body_lines.append(f"return {call_str}")

    # Format body
    body = "\n        ".join(body_lines)

    # Docstring
    doc_lines = [f'"""{desc}']
    if doc_params:
        doc_lines.append("")
        doc_lines.append("Args:")
        for dp in doc_params:
            doc_lines.append(f"    {dp}")
    doc_lines.append('"""')
    docstring = "\n        ".join(doc_lines)

    return f"""    @staticmethod
    def {factory}({sig}) -> UIComponent:
        {docstring}
        {body}
"""


# ---------------------------------------------------------------------------
# FUNCTION FACTORY GENERATION
# ---------------------------------------------------------------------------


def _gen_function_factory(func: dict) -> str:
    """Generate a validation/formatting function factory."""
    name = func["name"]
    factory = func["factory_name"]
    desc = func.get("description", f"{name} function.")
    return_type = func.get("return_type", "boolean")
    category = func.get("category", "unknown")
    is_validation = category == "validation"

    # Build params — required first, then optional
    required_params: list[str] = []
    optional_params: list[str] = []
    call_args: list[str] = []

    for arg in func.get("args", []):
        arg_name = arg["name"]
        if arg_name == "value":
            continue  # 'value' is auto-bound to the component's value
        py_type = _py_type(arg.get("type", "str"))
        if arg.get("required"):
            required_params.append(f"{arg_name}: {py_type}")
        else:
            optional_params.append(f"{arg_name}: {py_type} | None = None")
        call_args.append(arg_name)

    # Message param for validation functions
    if is_validation:
        optional_params.append(f'msg: str = "{name.title()} check failed"')

    # Ensure required params come before optional
    all_params = required_params
    if required_params and optional_params:
        all_params = required_params + ["*"] + optional_params
    elif optional_params:
        all_params = optional_params
    sig = ", ".join(all_params) if all_params else ""

    # Return type
    ret_annotation = "UICheck" if is_validation else "dict[str, Any]"

    # Body
    if is_validation:
        if call_args:
            args_pairs = ", ".join(f'("{a}", {a})' for a in call_args)
            body = f'return UICheck(fn="{name}", args=tuple((k, v) for k, v in ({args_pairs},) if v is not None), message=msg)'
        else:
            body = f'return UICheck(fn="{name}", message=msg)'
    else:
        # Non-validation function (formatting, logic, navigation)
        if call_args:
            args_dict = ", ".join(f'"{a}": {a}' for a in call_args)
            body = f'return {{"call": "{name}", "args": {{{args_dict}}}, "returnType": "{return_type}"}}'
        else:
            body = f'return {{"call": "{name}", "returnType": "{return_type}"}}'

    # Truncate description for docstring
    short_desc = desc.split(".")[0] + "." if "." in desc else desc

    return f"""    @staticmethod
    def {factory}({sig}) -> {ret_annotation}:
        \"\"\"{short_desc}\"\"\"
        {body}
"""


# ---------------------------------------------------------------------------
# ALIAS GENERATION
# ---------------------------------------------------------------------------


def _gen_alias(alias_name: str, alias_def: dict) -> str:
    """Generate an alias factory (e.g., UI.h1 → UI.text(..., variant='h1'))."""
    component = alias_def.get("component", "Text")
    default_variant = alias_def.get("default_variant", "body")
    doc = alias_def.get("doc", f"Alias for {component} with variant={default_variant}.")

    # For Text aliases, delegate to text() with fixed variant
    if component == "Text":
        return f"""    @staticmethod
    def {alias_name}(content: str, *, id: str | None = None) -> UIComponent:
        \"\"\"{doc}\"\"\"
        return _component("Text", id=id, text=content, variant="{default_variant}")
"""
    elif component == "Button":
        return f"""    @staticmethod
    def {alias_name}(label: str, *, action: str | None = None, id: str | None = None) -> UIComponent:
        \"\"\"{doc}\"\"\"
        _action = UIAction(event=action) if action else None
        _label = _component("Text", text=label)
        return _component("Button", id=id, variant="{default_variant}", _children=(_label,), _action=_action)
"""
    elif component == "TextField":
        return f"""    @staticmethod
    def {alias_name}(label: str, *, bind: str | None = None, checks: list[UICheck] | None = None, id: str | None = None) -> UIComponent:
        \"\"\"{doc}\"\"\"
        _bindings = (UIBinding(path=bind),) if bind else ()
        _checks = tuple(checks) if checks else ()
        return _component("TextField", id=id, label=label, variant="{default_variant}", _bindings=_bindings, _checks=_checks)
"""
    return ""


# ---------------------------------------------------------------------------
# FULL FILE GENERATION
# ---------------------------------------------------------------------------


def generate_factories(seed: dict) -> str:
    """Generate _ui_generated.py source code from seed."""
    lines: list[str] = []

    lines.append('"""')
    lines.append("AUTO-GENERATED by scripts/a2ui/generator.py from a2ui_seed.toml")
    lines.append("Do not edit manually. Regenerate with: just a2ui-generate")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from typing import Any")
    lines.append("")
    lines.append("from adk_fluent._ui import (")
    lines.append("    UIAction,")
    lines.append("    UIBinding,")
    lines.append("    UICheck,")
    lines.append("    UIComponent,")
    lines.append("    _component,")
    lines.append(")")
    lines.append("")
    lines.append("")
    lines.append("class _GeneratedFactories:")
    lines.append('    """Generated A2UI component and function factories.')
    lines.append("")
    lines.append("    Mixed into the UI class via inheritance in _ui.py.")
    lines.append('    """')
    lines.append("")

    # Component factories
    lines.append("    # === Component factories ===")
    lines.append("")
    for comp in seed.get("components", []):
        lines.append(_gen_component_factory(comp))

    # Function factories
    lines.append("    # === Function factories (validation, formatting, logic) ===")
    lines.append("")
    for func in seed.get("functions", []):
        lines.append(_gen_function_factory(func))

    # Aliases
    aliases = seed.get("aliases", {})
    if aliases:
        lines.append("    # === Aliases (DX sugar) ===")
        lines.append("")
        for alias_name, alias_def in aliases.items():
            code = _gen_alias(alias_name, alias_def)
            if code:
                lines.append(code)

    return "\n".join(lines)


def generate_stubs(seed: dict) -> str:
    """Generate _ui_generated.pyi type stubs."""
    lines: list[str] = []

    lines.append('"""Type stubs for _ui_generated.py — IDE completion support."""')
    lines.append("")
    lines.append("from typing import Any")
    lines.append("")
    lines.append("from adk_fluent._ui import UIAction, UIBinding, UICheck, UIComponent")
    lines.append("")
    lines.append("")
    lines.append("class _GeneratedFactories:")

    for comp in seed.get("components", []):
        factory = comp["factory_name"]
        lines.append("    @staticmethod")
        lines.append(f"    def {factory}(*args: Any, **kwargs: Any) -> UIComponent: ...")

    for func in seed.get("functions", []):
        factory = func["factory_name"]
        lines.append("    @staticmethod")
        lines.append(f"    def {factory}(*args: Any, **kwargs: Any) -> UICheck: ...")

    aliases = seed.get("aliases", {})
    for alias_name in aliases:
        lines.append("    @staticmethod")
        lines.append(f"    def {alias_name}(*args: Any, **kwargs: Any) -> UIComponent: ...")

    return "\n".join(lines) + "\n"


def generate_tests(seed: dict) -> str:
    """Generate test_ui_generated.py scaffolded tests."""
    lines: list[str] = []

    lines.append('"""')
    lines.append("AUTO-GENERATED tests for UI namespace factories.")
    lines.append("Regenerate with: just a2ui-generate")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import pytest")
    lines.append("")
    lines.append("from adk_fluent._ui import UI, UIBinding, UICheck, UIComponent, UISurface")
    lines.append("")
    lines.append("")

    # Component tests
    lines.append("# === Component factory tests ===")
    lines.append("")

    for comp in seed.get("components", []):
        factory = comp["factory_name"]
        name = comp["name"]
        has_children = comp.get("has_children", False)
        child_mode = comp.get("child_mode")
        has_bind = comp.get("has_bind", False)
        has_checks = comp.get("has_checks", False)
        has_action = comp.get("has_action", False)
        required_args = comp.get("required_args", [])
        types = comp.get("arg_types", {})

        # Build minimal call args
        call_args: list[str] = []
        if has_children and child_mode == "list":
            call_args.append("UI.text('child')")

        for arg in required_args:
            if arg in _STRUCTURAL_PROPS:
                continue
            arg_type = types.get(arg, "str")
            if "String" in arg_type or arg_type == "str":
                call_args.append(f'{arg}="test"')
            elif "Number" in arg_type or arg_type in ("int", "float", "int | float", "number"):
                call_args.append(f"{arg}=0")
            elif "Boolean" in arg_type or arg_type == "bool":
                call_args.append(f"{arg}=False")
            elif "StringList" in arg_type or arg_type.startswith("array"):
                call_args.append(f'{arg}=[]')
            else:
                call_args.append(f'{arg}="test"')

        args_str = ", ".join(call_args)

        lines.append(f"def test_ui_{factory}_creates_component():")
        lines.append(f'    c = UI.{factory}({args_str})')
        lines.append('    assert isinstance(c, UIComponent)')
        lines.append(f'    assert c._kind == "{name}"')
        lines.append("")

        # Bind test
        if has_bind:
            bind_args = args_str + (', ' if args_str else '') + 'bind="/test/path"'
            lines.append(f"def test_ui_{factory}_with_bind():")
            lines.append(f'    c = UI.{factory}({bind_args})')
            lines.append("    assert len(c._bindings) == 1")
            lines.append('    assert c._bindings[0].path == "/test/path"')
            lines.append("")

        # Checks test
        if has_checks:
            check_args = args_str + (', ' if args_str else '') + 'checks=[UI.required()]'
            lines.append(f"def test_ui_{factory}_with_checks():")
            lines.append(f'    c = UI.{factory}({check_args})')
            lines.append("    assert len(c._checks) == 1")
            lines.append('    assert c._checks[0].fn == "required"')
            lines.append("")

    # Function tests
    lines.append("# === Function factory tests ===")
    lines.append("")

    for func in seed.get("functions", []):
        factory = func["factory_name"]
        fname = func["name"]
        category = func.get("category", "")

        if category == "validation":
            # Build minimal required args for the test call
            test_args: list[str] = []
            for arg in func.get("args", []):
                if arg["name"] == "value":
                    continue
                if arg.get("required"):
                    py_type = arg.get("type", "str")
                    if "String" in py_type or py_type == "str":
                        test_args.append(f'{arg["name"]}="test"')
                    elif "Number" in py_type:
                        test_args.append(f'{arg["name"]}=0')
                    else:
                        test_args.append(f'{arg["name"]}="test"')
            call_str = ", ".join(test_args)
            lines.append(f"def test_ui_{factory}_check():")
            lines.append(f'    c = UI.{factory}({call_str})')
            lines.append("    assert isinstance(c, UICheck)")
            lines.append(f'    assert c.fn == "{fname}"')
            lines.append("")

    # Alias tests
    aliases = seed.get("aliases", {})
    for alias_name, alias_def in aliases.items():
        component = alias_def.get("component", "Text")
        variant = alias_def.get("default_variant", "body")
        if component == "Text":
            lines.append(f'def test_ui_{alias_name}_alias():')
            lines.append(f'    c = UI.{alias_name}("test")')
            lines.append('    assert c._kind == "Text"')
            lines.append(f'    assert dict(c._props).get("variant") == "{variant}"')
            lines.append("")

    # Surface/preset tests
    lines.append("# === Surface and preset tests ===")
    lines.append("")
    lines.append("def test_ui_surface_creates_surface():")
    lines.append('    s = UI.surface("test")')
    lines.append("    assert isinstance(s, UISurface)")
    lines.append('    assert s.name == "test"')
    lines.append("")
    lines.append("def test_ui_bind_creates_binding():")
    lines.append('    b = UI.bind("/user/name")')
    lines.append("    assert isinstance(b, UIBinding)")
    lines.append('    assert b.path == "/user/name"')
    lines.append("")
    lines.append("def test_ui_form_preset():")
    lines.append('    s = UI.form("Contact", fields={"name": "text", "email": "email"})')
    lines.append("    assert isinstance(s, UISurface)")
    lines.append("    assert s.root is not None")
    lines.append('    assert s.name == "contact"')
    lines.append("")
    lines.append("def test_ui_dashboard_preset():")
    lines.append('    s = UI.dashboard("Metrics", cards=[{"title": "Users", "bind": "/users"}])')
    lines.append("    assert isinstance(s, UISurface)")
    lines.append("    assert s.root is not None")
    lines.append("")
    lines.append("def test_ui_confirm_preset():")
    lines.append('    s = UI.confirm("Are you sure?")')
    lines.append("    assert isinstance(s, UISurface)")
    lines.append("    assert s.root is not None")
    lines.append("")
    lines.append("def test_surface_compile():")
    lines.append('    s = UI.surface("test", UI.text("Hello"))')
    lines.append("    msgs = s.compile()")
    lines.append("    assert len(msgs) >= 2")
    lines.append('    assert "createSurface" in msgs[0]')
    lines.append('    assert "updateComponents" in msgs[1]')
    lines.append("")
    lines.append("def test_component_operators():")
    lines.append('    a = UI.text("A")')
    lines.append('    b = UI.text("B")')
    lines.append('    row = a | b')
    lines.append('    assert row._kind == "Row"')
    lines.append('    col = a >> b')
    lines.append('    assert col._kind == "Column"')
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(
    *,
    seed: Path,
    output_dir: Path = Path("src/adk_fluent"),
    test_dir: Path = Path("tests/generated"),
) -> None:
    """Run the generator programmatically (no sys.argv manipulation)."""
    seed_data = _load_seed(seed)

    output_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    # Generate source
    src = generate_factories(seed_data)
    src_path = output_dir / "_ui_generated.py"
    src_path.write_text(src)
    print(f"Wrote {src_path}", file=sys.stderr)

    # Generate stubs
    stubs = generate_stubs(seed_data)
    stubs_path = output_dir / "_ui_generated.pyi"
    stubs_path.write_text(stubs)
    print(f"Wrote {stubs_path}", file=sys.stderr)

    # Generate tests
    tests = generate_tests(seed_data)
    test_path = test_dir / "test_ui_generated.py"
    test_path.write_text(tests)
    print(f"Wrote {test_path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate UI factories from a2ui_seed"
    )
    parser.add_argument("seed", help="Path to a2ui_seed.toml or JSON")
    parser.add_argument("--output-dir", default="src/adk_fluent")
    parser.add_argument("--test-dir", default="tests/generated")
    args = parser.parse_args()

    run(
        seed=Path(args.seed),
        output_dir=Path(args.output_dir),
        test_dir=Path(args.test_dir),
    )


if __name__ == "__main__":
    main()
