"""Tests for the Code IR data model."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.code_ir import (
    ModuleNode, ClassNode, ClassAttr, MethodNode, Param,
    AssignStmt, ReturnStmt, SubscriptAssign, AppendStmt,
    ForAppendStmt, IfStmt, ImportStmt, RawStmt,
    emit_python, emit_stub,
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
            IfStmt(condition="condition", body=(
                AppendStmt(target="self._callbacks", key="before_model_callback", value="fn"),
            )),
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
            RawStmt('self._callbacks["before_model_callback"].append(fn)\nself._callbacks["after_model_callback"].append(fn)'),
            ReturnStmt("self"),
        ],
    )
    source = emit_python(m)
    assert 'self._callbacks["before_model_callback"].append(fn)' in source
    assert 'self._callbacks["after_model_callback"].append(fn)' in source
