"""Tests for UI core types: UIComponent, UIBinding, UICheck, UISurface, operators."""

from adk_fluent._ui import (
    UI,
    UIAction,
    UIBinding,
    UICheck,
    UIComponent,
    UISurface,
    _UIAutoSpec,
    _UIGroup,
    _UISchemaSpec,
    _component,
)


# ======================================================================
# UIComponent basics
# ======================================================================


class TestUIComponent:
    """Core UIComponent frozen dataclass."""

    def test_component_creation(self):
        c = _component("Text", text="hello")
        assert c._kind == "Text"
        assert ("text", "hello") in c._props

    def test_component_is_frozen(self):
        c = _component("Text", text="hello")
        try:
            c._kind = "Other"
            assert False, "Should raise"
        except AttributeError:
            pass

    def test_component_with_id(self):
        c = _component("Text", id="my-id", text="hello")
        assert c._id == "my-id"

    def test_component_with_children(self):
        child1 = _component("Text", text="a")
        child2 = _component("Text", text="b")
        parent = _component("Row", _children=(child1, child2))
        assert len(parent._children) == 2

    def test_component_with_bindings(self):
        binding = UIBinding(path="/name", prop="value")
        c = _component("TextField", label="Name", _bindings=(binding,))
        assert len(c._bindings) == 1
        assert c._bindings[0].path == "/name"

    def test_component_with_checks(self):
        check = UICheck(fn="required", message="Required")
        c = _component("TextField", label="Name", _checks=(check,))
        assert len(c._checks) == 1
        assert c._checks[0].fn == "required"

    def test_component_with_action(self):
        action = UIAction(event="click")
        c = _component("Button", label="Go", _action=action)
        assert c._action.event == "click"


# ======================================================================
# UIBinding
# ======================================================================


class TestUIBinding:
    """UIBinding frozen dataclass."""

    def test_binding_defaults(self):
        b = UIBinding(path="/user/name")
        assert b.path == "/user/name"
        assert b.prop == "value"
        assert b.direction == "two_way"

    def test_binding_custom(self):
        b = UIBinding(path="/data", prop="text", direction="read")
        assert b.direction == "read"

    def test_ui_bind_factory(self):
        b = UI.bind("/user/name")
        assert b.path == "/user/name"
        assert b.direction == "two_way"


# ======================================================================
# UICheck
# ======================================================================


class TestUICheck:
    """UICheck frozen dataclass."""

    def test_check_defaults(self):
        c = UICheck(fn="required")
        assert c.fn == "required"
        assert c.message == ""

    def test_check_with_message(self):
        c = UICheck(fn="email", message="Invalid email")
        assert c.message == "Invalid email"


# ======================================================================
# UIAction
# ======================================================================


class TestUIAction:
    """UIAction frozen dataclass."""

    def test_action_defaults(self):
        a = UIAction(event="submit")
        assert a.event == "submit"
        assert a.context == ()

    def test_action_with_context(self):
        a = UIAction(event="submit", context=(("form", "contact"),))
        assert len(a.context) == 1


# ======================================================================
# Composition operators
# ======================================================================


class TestOperators:
    """UIComponent composition operators: |, >>, +."""

    def test_pipe_creates_row(self):
        a = UI.text("a")
        b = UI.text("b")
        result = a | b
        assert result._kind == "Row"
        assert len(result._children) == 2

    def test_rshift_creates_column(self):
        a = UI.text("a")
        b = UI.text("b")
        result = a >> b
        assert result._kind == "Column"
        assert len(result._children) == 2

    def test_add_creates_group(self):
        a = UI.text("a")
        b = UI.text("b")
        result = a + b
        assert isinstance(result, _UIGroup)
        assert len(result._children) == 2

    def test_chained_pipe(self):
        result = UI.text("a") | UI.text("b") | UI.text("c")
        assert result._kind == "Row"
        # Nested: Row(Row(a,b), c)
        assert len(result._children) == 2

    def test_chained_rshift(self):
        result = UI.text("a") >> UI.text("b") >> UI.text("c")
        assert result._kind == "Column"
        # Nested: Column(Column(a,b), c)
        assert len(result._children) == 2

    def test_mixed_operators(self):
        row = UI.text("a") | UI.text("b")
        col = row >> UI.text("c")
        assert col._kind == "Column"


# ======================================================================
# UISurface
# ======================================================================


class TestUISurface:
    """UISurface builder."""

    def test_surface_creation(self):
        s = UI.surface("test")
        assert isinstance(s, UISurface)
        assert s.name == "test"

    def test_surface_with_root(self):
        root = UI.text("Hello")
        s = UI.surface("test", root)
        assert s.root is not None

    def test_surface_on_handler(self):
        async def handler(ctx):
            pass

        s = UI.surface("test").on("submit", handler)
        assert len(s._handlers) == 1

    def test_surface_with_theme(self):
        s = UI.surface("test").with_theme(primaryColor="#ff0000")
        assert len(s.theme) == 1

    def test_surface_with_data(self):
        s = UI.surface("test").with_data(count=0)
        assert len(s.data) == 1


# ======================================================================
# Auto and Schema specs
# ======================================================================


class TestAutoAndSchema:
    """UI.auto() and UI.schema() modes."""

    def test_auto_default(self):
        spec = UI.auto()
        assert isinstance(spec, _UIAutoSpec)
        assert spec.catalog == "basic"

    def test_auto_custom_catalog(self):
        spec = UI.auto(catalog="extended")
        assert spec.catalog == "extended"

    def test_schema_default(self):
        spec = UI.schema()
        assert isinstance(spec, _UISchemaSpec)

    def test_schema_custom_uri(self):
        spec = UI.schema(catalog_uri="https://example.com/catalog.json")
        assert spec.catalog_uri == "https://example.com/catalog.json"


# ======================================================================
# Generic component escape hatch
# ======================================================================


class TestGenericComponent:
    """UI.component() catalog-agnostic factory."""

    def test_generic_component(self):
        c = UI.component("CustomChart", data="test")
        assert c._kind == "CustomChart"
        assert ("data", "test") in c._props
