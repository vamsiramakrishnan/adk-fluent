"""Tests for the Code IR data model."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.code_ir import (
    AppendStmt,
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


def test_method_node_basic():
    m = MethodNode(
        name="instruct",
        params=[Param("self"), Param("value", type="str")],
        returns="Self",
        doc="Set the instruction field.",
        body=[
            SubscriptAssign(target="self._config", key="instruction", value="value"),
            ReturnStmt("self"),
        ],
    )
    assert m.name == "instruct"
    assert len(m.params) == 2
    assert len(m.body) == 2


def test_class_node_contains_methods():
    c = ClassNode(
        name="Agent",
        bases=["BuilderBase"],
        doc="Fluent builder for LlmAgent.",
        methods=[
            MethodNode(
                name="instruct",
                params=[Param("self"), Param("value", type="str")],
                returns="Self",
                body=[ReturnStmt("self")],
            ),
        ],
    )
    assert c.name == "Agent"
    assert len(c.methods) == 1


def test_emit_python_method():
    m = MethodNode(
        name="instruct",
        params=[Param("self"), Param("value", type="str")],
        returns="Self",
        doc="Set the instruction field.",
        body=[
            SubscriptAssign(target="self._config", key="instruction", value="value"),
            ReturnStmt("self"),
        ],
    )
    source = emit_python(m)
    assert "def instruct(self, value: str) -> Self:" in source
    assert 'self._config["instruction"] = value' in source
    assert "return self" in source


def test_emit_python_async_method():
    m = MethodNode(
        name="ask_async",
        params=[Param("self"), Param("prompt", type="str")],
        returns="str",
        is_async=True,
        body=[ReturnStmt('"result"')],
    )
    source = emit_python(m)
    assert "async def ask_async" in source


def test_emit_python_callback_method():
    m = MethodNode(
        name="before_model",
        params=[Param("self"), Param("*fns", type="Callable")],
        returns="Self",
        doc="Append callbacks.",
        body=[
            ForAppendStmt(var="fn", iterable="fns", target="self._callbacks", key="before_model_callback"),
            ReturnStmt("self"),
        ],
    )
    source = emit_python(m)
    assert "for fn in fns:" in source
    assert 'self._callbacks["before_model_callback"].append(fn)' in source


def test_emit_python_conditional():
    m = MethodNode(
        name="before_model_if",
        params=[Param("self"), Param("condition", type="bool"), Param("fn", type="Callable")],
        returns="Self",
        body=[
            IfStmt(
                condition="condition",
                body=(AppendStmt(target="self._callbacks", key="before_model_callback", value="fn"),),
            ),
            ReturnStmt("self"),
        ],
    )
    source = emit_python(m)
    assert "if condition:" in source
    assert 'self._callbacks["before_model_callback"].append(fn)' in source


def test_emit_python_import_stmt():
    m = MethodNode(
        name="tool",
        params=[Param("self"), Param("fn_or_tool")],
        returns="Self",
        body=[
            ImportStmt(module="adk_fluent._helpers", name="_add_tool", call="return _add_tool(self, fn_or_tool)"),
        ],
    )
    source = emit_python(m)
    assert "from adk_fluent._helpers import _add_tool" in source
    assert "return _add_tool(self, fn_or_tool)" in source


def test_emit_python_class():
    c = ClassNode(
        name="Agent",
        bases=["BuilderBase"],
        doc="Fluent builder.",
        attrs=[ClassAttr("_ALIASES", "dict[str, str]", '{"instruct": "instruction"}')],
        methods=[
            MethodNode(
                name="instruct",
                params=[Param("self"), Param("value", type="str")],
                returns="Self",
                body=[ReturnStmt("self")],
            ),
        ],
    )
    source = emit_python(c)
    assert "class Agent(BuilderBase):" in source
    assert '"""Fluent builder."""' in source
    assert '_ALIASES: dict[str, str] = {"instruct": "instruction"}' in source
    assert "def instruct(self, value: str) -> Self:" in source


def test_emit_python_module():
    mod = ModuleNode(
        doc="Auto-generated.",
        imports=["from typing import Self", "from typing import Any", "from typing import Self"],
        classes=[
            ClassNode(name="Agent", bases=["BuilderBase"], methods=[]),
        ],
    )
    source = emit_python(mod)
    # Should deduplicate imports
    assert source.count("from typing import Self") == 1
    assert "class Agent(BuilderBase):" in source


def test_emit_stub_method():
    m = MethodNode(
        name="instruct",
        params=[Param("self"), Param("value", type="str")],
        returns="Self",
    )
    stub = emit_stub(m)
    assert "def instruct(self, value: str) -> Self: ..." in stub


def test_emit_stub_class():
    c = ClassNode(
        name="Agent",
        bases=["BuilderBase"],
        doc="Fluent builder.",
        methods=[
            MethodNode(name="instruct", params=[Param("self"), Param("value", type="str")], returns="Self"),
            MethodNode(name="build", params=[Param("self")], returns="LlmAgent"),
        ],
    )
    stub = emit_stub(c)
    assert "class Agent(BuilderBase):" in stub
    assert "def instruct(self, value: str) -> Self: ..." in stub
    assert "def build(self) -> LlmAgent: ..." in stub


def test_emit_python_keyword_only_params():
    m = MethodNode(
        name="tool",
        params=[
            Param("self"),
            Param("fn_or_tool"),
            Param("require_confirmation", type="bool", default="False", keyword_only=True),
        ],
        returns="Self",
        body=[ReturnStmt("self")],
    )
    source = emit_python(m)
    assert "def tool(self, fn_or_tool, *, require_confirmation: bool = False) -> Self:" in source


def test_emit_python_raw_stmt():
    m = MethodNode(
        name="guardrail",
        params=[Param("self"), Param("fn", type="Callable")],
        returns="Self",
        body=[
            RawStmt(
                'self._callbacks["before_model_callback"].append(fn)\nself._callbacks["after_model_callback"].append(fn)'
            ),
            ReturnStmt("self"),
        ],
    )
    source = emit_python(m)
    assert 'self._callbacks["before_model_callback"].append(fn)' in source
    assert 'self._callbacks["after_model_callback"].append(fn)' in source


def test_roundtrip_builder_spec_to_ir_to_python():
    """BuilderSpec -> IR -> Python source should produce valid code."""
    from scripts.code_ir import emit_python
    from scripts.generator import BuilderSpec, spec_to_ir

    spec = BuilderSpec(
        name="TestBuilder",
        source_class="google.adk.test.TestClass",
        source_class_short="TestClass",
        output_module="test",
        doc="Test builder.",
        constructor_args=["name"],
        aliases={"instruct": "instruction"},
        reverse_aliases={"instruction": "instruct"},
        callback_aliases={"before_model": "before_model_callback"},
        skip_fields={"name", "parent_agent"},
        additive_fields={"before_model_callback"},
        list_extend_fields=set(),
        fields=[
            {"name": "name", "type_str": "str", "required": True, "is_callback": False},
            {
                "name": "instruction",
                "type_str": "str | None",
                "required": False,
                "is_callback": False,
                "description": "",
            },
            {"name": "before_model_callback", "type_str": "Callable | None", "required": False, "is_callback": True},
        ],
        terminals=[{"name": "build", "returns": "TestClass"}],
        extras=[],
        is_composite=False,
        is_standalone=False,
        field_docs={},
    )
    ir_class = spec_to_ir(spec)
    source = emit_python(ir_class)

    # Verify key structural elements
    assert "class TestBuilder(BuilderBase):" in source
    assert "def __init__(self, name: str)" in source
    assert "def instruct(self, value: str" in source
    assert "def before_model(self, *fns: Callable) -> Self:" in source
    assert "def before_model_if(self, condition: bool" in source
    assert "def build(self)" in source
    assert 'self._config["instruction"] = value' in source
    assert "return self" in source


def test_stub_emission_from_spec():
    """spec_to_ir → emit_stub should produce valid .pyi content."""
    from scripts.code_ir import emit_stub
    from scripts.generator import BuilderSpec, spec_to_ir

    spec = BuilderSpec(
        name="TestBuilder",
        source_class="google.adk.test.TestClass",
        source_class_short="TestClass",
        output_module="test",
        doc="Test builder.",
        constructor_args=["name"],
        aliases={"instruct": "instruction"},
        reverse_aliases={"instruction": "instruct"},
        callback_aliases={},
        skip_fields={"name", "parent_agent"},
        additive_fields=set(),
        list_extend_fields=set(),
        fields=[
            {"name": "name", "type_str": "str", "required": True, "is_callback": False},
            {
                "name": "instruction",
                "type_str": "str | None",
                "required": False,
                "is_callback": False,
                "description": "",
            },
        ],
        terminals=[{"name": "build", "returns": "TestClass"}],
        extras=[],
        is_composite=False,
        is_standalone=False,
        field_docs={},
    )
    ir_class = spec_to_ir(spec)
    stub = emit_stub(ir_class)

    assert "class TestBuilder(BuilderBase):" in stub
    assert "def instruct(self, value: str" in stub
    assert "def build(self)" in stub
    assert "..." in stub  # Stubs use ellipsis bodies


def test_test_generation_from_ir():
    """spec_to_ir_test should produce a test class with standard test methods."""
    from scripts.code_ir import emit_python
    from scripts.generator import BuilderSpec, spec_to_ir_test

    spec = BuilderSpec(
        name="TestBuilder",
        source_class="google.adk.test.TestClass",
        source_class_short="TestClass",
        output_module="test",
        doc="Test builder.",
        constructor_args=["name"],
        aliases={"instruct": "instruction"},
        reverse_aliases={"instruction": "instruct"},
        callback_aliases={"before_model": "before_model_callback"},
        skip_fields={"name", "parent_agent"},
        additive_fields={"before_model_callback"},
        list_extend_fields=set(),
        fields=[
            {"name": "name", "type_str": "str", "required": True, "is_callback": False},
            {
                "name": "instruction",
                "type_str": "str | None",
                "required": False,
                "is_callback": False,
                "description": "",
            },
            {"name": "before_model_callback", "type_str": "Callable | None", "required": False, "is_callback": True},
        ],
        terminals=[{"name": "build", "returns": "TestClass"}],
        extras=[],
        is_composite=False,
        is_standalone=False,
        field_docs={},
    )
    ir_test = spec_to_ir_test(spec)
    source = emit_python(ir_test)

    assert "TestTestBuilderBuilder" in source or "TestTestBuilder" in source
    assert "test_builder_creation" in source
    assert "test_chaining_returns_self" in source
    assert "test_typo_detection" in source
