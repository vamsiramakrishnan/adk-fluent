"""Tests for cross-namespace A2UI integration: T.a2ui, G.a2ui, P.ui_schema."""

import pytest

from adk_fluent import T
from adk_fluent._guards import G, GComposite
from adk_fluent._ir import UINode
from adk_fluent._prompt import P
from adk_fluent._tools import TComposite
from adk_fluent.patterns import ui_dashboard_agent, ui_form_agent

# ======================================================================
# T.a2ui()
# ======================================================================


class TestTa2ui:
    """T.a2ui() tool composition."""

    def test_ta2ui_returns_tcomposite(self):
        tc = T.a2ui()
        assert isinstance(tc, TComposite)

    def test_ta2ui_kind(self):
        tc = T.a2ui()
        assert tc._kind == "a2ui"

    def test_ta2ui_composable(self):
        tc = T.google_search() | T.a2ui()
        assert isinstance(tc, TComposite)
        assert len(tc) >= 1


# ======================================================================
# G.a2ui()
# ======================================================================


class TestGa2ui:
    """G.a2ui() output guard."""

    def test_ga2ui_returns_gcomposite(self):
        gc = G.a2ui()
        assert isinstance(gc, GComposite)

    def test_ga2ui_max_components(self):
        gc = G.a2ui(max_components=20)
        assert isinstance(gc, GComposite)

    def test_ga2ui_allowed_types(self):
        gc = G.a2ui(allowed_types=["Text", "Button"])
        assert isinstance(gc, GComposite)

    def test_ga2ui_deny_types(self):
        gc = G.a2ui(deny_types=["Modal"])
        assert isinstance(gc, GComposite)

    def test_ga2ui_composable(self):
        gc = G.pii() | G.a2ui()
        assert isinstance(gc, GComposite)


# ======================================================================
# P.ui_schema()
# ======================================================================


class TestPuiSchema:
    """P.ui_schema() prompt injection."""

    def test_pui_schema_returns_psection(self):
        ps = P.ui_schema()
        assert hasattr(ps, "content")
        assert hasattr(ps, "_kind")

    def test_pui_schema_has_content(self):
        ps = P.ui_schema()
        assert len(ps.content) > 0

    def test_pui_schema_kind(self):
        ps = P.ui_schema()
        assert ps._kind == "section"

    def test_pui_schema_name(self):
        ps = P.ui_schema()
        assert ps.name == "ui_schema"

    def test_pui_schema_composable(self):
        composed = P.role("UI designer") + P.ui_schema() + P.task("Build a form")
        assert composed is not None


# ======================================================================
# UINode IR
# ======================================================================


class TestUINodeIR:
    """UINode IR type."""

    def test_uinode_creation(self):
        node = UINode(
            name="test",
            surface_name="dashboard",
            component_count=5,
            bindings=("/users", "/revenue"),
            actions=("refresh",),
        )
        assert node.surface_name == "dashboard"
        assert node.component_count == 5

    def test_uinode_defaults(self):
        node = UINode(name="test", surface_name="main")
        assert node.component_count == 0
        assert node.bindings == ()
        assert node.actions == ()
        assert node.mode == "declarative"

    def test_uinode_frozen(self):
        node = UINode(name="test", surface_name="main")
        with pytest.raises(AttributeError):
            node.surface_name = "other"


# ======================================================================
# Pattern helpers
# ======================================================================


class TestUIPatterns:
    """ui_form_agent, ui_dashboard_agent patterns."""

    def test_ui_form_agent_basic(self):
        agent = ui_form_agent(
            "intake",
            "gemini-2.5-flash",
            fields={"name": "text", "email": "email"},
        )
        assert agent._config.get("_ui_spec") is not None
        assert agent._config.get("name") == "intake"

    def test_ui_form_agent_with_instruction(self):
        agent = ui_form_agent(
            "intake",
            "gemini-2.5-flash",
            fields={"name": "text"},
            instruction="Collect info.",
        )
        assert agent._config.get("instruction") == "Collect info."

    def test_ui_dashboard_agent_basic(self):
        agent = ui_dashboard_agent(
            "metrics",
            "gemini-2.5-flash",
            cards=[{"title": "Users", "bind": "/users"}],
        )
        assert agent._config.get("_ui_spec") is not None
