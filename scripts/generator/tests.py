"""Test scaffold generation — produce builder-mechanics tests from BuilderSpecs.

Generates pytest test classes that verify:
  - Builder creation
  - Chaining returns self
  - Config accumulation
  - Callback accumulation
  - Typo detection
"""

from __future__ import annotations

from code_ir import AssignStmt, ClassNode, MethodNode, ModuleNode, Param, RawStmt

from .spec import BuilderSpec


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


def spec_to_ir_test(spec: BuilderSpec) -> ClassNode:
    """Build a test ClassNode for a single BuilderSpec."""
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
    """Build a ModuleNode for test scaffold emission."""
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
