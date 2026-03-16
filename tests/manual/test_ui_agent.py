"""Tests for Agent .ui() integration: config storage, explain output."""

from adk_fluent import UI, Agent
from adk_fluent._ui import UISurface, _UIAutoSpec


class TestAgentUI:
    """Agent .ui() method integration."""

    def test_ui_stores_spec(self):
        agent = Agent("test").ui(UI.form("F", fields={"x": "text"}))
        assert agent._config.get("_ui_spec") is not None

    def test_ui_returns_self(self):
        agent = Agent("test")
        result = agent.ui(UI.text("Hi"))
        assert result is agent

    def test_ui_with_surface(self):
        s = UI.surface("dash", UI.text("Hello"))
        agent = Agent("test").ui(s)
        assert isinstance(agent._config["_ui_spec"], UISurface)

    def test_ui_with_auto(self):
        agent = Agent("test").ui(UI.auto())
        assert isinstance(agent._config["_ui_spec"], _UIAutoSpec)

    def test_ui_with_component(self):
        agent = Agent("test").ui(UI.text("Hello"))
        assert agent._config["_ui_spec"] is not None

    def test_ui_chainable(self):
        agent = Agent("test", "gemini-2.5-flash").instruct("Help users.").ui(UI.form("F", fields={"name": "text"}))
        assert agent._config.get("instruction") is not None
        assert agent._config.get("_ui_spec") is not None


class TestAgentExplainUI:
    """UI info in .explain() output."""

    def test_explain_json_includes_ui(self):
        agent = Agent("test").ui(UI.surface("dash", UI.text("Hi")))
        info = agent._explain_json()
        assert "ui" in info
        assert info["ui"]["surface"] == "dash"
        assert info["ui"]["mode"] == "declarative"

    def test_explain_json_auto_mode(self):
        agent = Agent("test").ui(UI.auto())
        info = agent._explain_json()
        assert "ui" in info
        assert info["ui"]["mode"] == "llm_guided"

    def test_explain_json_no_ui(self):
        agent = Agent("test")
        info = agent._explain_json()
        assert "ui" not in info

    def test_explain_json_component_count(self):
        root = UI.text("a") | UI.text("b")  # Row with 2 text
        agent = Agent("test").ui(UI.surface("s", root))
        info = agent._explain_json()
        assert info["ui"]["components"] == 3  # Row + 2 Text
