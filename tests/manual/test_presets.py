"""Tests for Preset class and .use() method."""
from adk_fluent.agent import Agent
from adk_fluent.presets import Preset


def _log_before(ctx):
    pass


def _log_after(ctx):
    pass


class TestPreset:
    def test_creation_stores_fields(self):
        p = Preset(model="gemini-2.5-flash", instruction="Be helpful.")
        assert p._fields["model"] == "gemini-2.5-flash"
        assert p._fields["instruction"] == "Be helpful."

    def test_creation_with_callbacks(self):
        p = Preset(before_model_callback=_log_before)
        assert _log_before in p._callbacks["before_model_callback"]


class TestUse:
    def test_applies_fields(self):
        p = Preset(model="gemini-2.5-flash")
        agent = Agent("math").use(p)
        assert agent._config["model"] == "gemini-2.5-flash"

    def test_returns_self(self):
        p = Preset(model="gemini-2.5-flash")
        agent = Agent("math")
        result = agent.use(p)
        assert result is agent

    def test_applies_callbacks_with_alias_resolution(self):
        """Preset with before_model_callback should resolve to callback storage."""
        p = Preset(before_model_callback=_log_before)
        agent = Agent("math").use(p)
        assert _log_before in agent._callbacks["before_model_callback"]

    def test_chainable(self):
        p1 = Preset(model="gemini-2.5-flash")
        p2 = Preset(instruction="Be helpful.")
        agent = Agent("math").use(p1).use(p2)
        assert agent._config["model"] == "gemini-2.5-flash"
        assert agent._config["instruction"] == "Be helpful."

    def test_multiple_presets(self):
        p1 = Preset(model="gemini-2.5-flash")
        p2 = Preset(before_model_callback=_log_before)
        agent = Agent("math").use(p1).use(p2)
        assert agent._config["model"] == "gemini-2.5-flash"
        assert _log_before in agent._callbacks["before_model_callback"]

    def test_model_string_not_treated_as_callable(self):
        """'model' is always a field, even though strings are not callable."""
        p = Preset(model="gemini-2.5-flash")
        # model should be in _fields, not _callbacks
        assert "model" in p._fields
        assert "model" not in p._callbacks
