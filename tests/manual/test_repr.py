"""Tests for BuilderBase.__repr__."""
from adk_fluent.agent import Agent
from adk_fluent.workflow import Pipeline, FanOut, Loop


def _log_fn(ctx):
    pass


def _calculator(ctx):
    """A fake tool."""
    pass


class _FakeTool:
    name = "calculator"


class TestReprBasic:
    def test_simple_agent_contains_class_and_name(self):
        agent = Agent("math")
        r = repr(agent)
        assert 'Agent("math")' in r

    def test_agent_with_config_shows_instruct_and_model(self):
        agent = Agent("math").model("gemini-2.5-flash").instruct("Solve math problems.")
        r = repr(agent)
        assert ".instruct(" in r
        assert ".model(" in r
        assert "gemini-2.5-flash" in r
        assert "Solve math problems." in r

    def test_agent_with_callbacks_shows_alias_and_fn_name(self):
        agent = Agent("math").before_model(_log_fn)
        r = repr(agent)
        assert ".before_model(" in r
        assert "_log_fn" in r

    def test_agent_with_tools_shows_tools(self):
        tool = _FakeTool()
        agent = Agent("math").tool(tool)
        r = repr(agent)
        assert ".tools(" in r
        assert "calculator" in r

    def test_pipeline_repr_works(self):
        a = Agent("a").model("gemini-2.5-flash")
        p = Pipeline("pipe").step(a)
        r = repr(p)
        assert 'Pipeline("pipe")' in r

    def test_repr_uses_aliases(self):
        """Shows .instruct not .instruction in repr."""
        agent = Agent("math").instruct("Do things.")
        r = repr(agent)
        assert ".instruct(" in r
        assert ".instruction(" not in r

    def test_long_strings_truncated(self):
        long_str = "x" * 100
        agent = Agent("math").instruct(long_str)
        r = repr(agent)
        # The truncated value should end with ...
        assert "..." in r
        # Should not contain the full 100-char string
        assert long_str not in r

    def test_repr_skips_name_from_config(self):
        """Name is shown as constructor arg, not as .name()."""
        agent = Agent("math")
        r = repr(agent)
        assert ".name(" not in r

    def test_repr_skips_internal_fields(self):
        """Fields starting with _ should not be shown."""
        agent = Agent("math")
        r = repr(agent)
        assert "._" not in r
