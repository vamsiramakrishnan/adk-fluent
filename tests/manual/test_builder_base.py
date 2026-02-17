"""Tests for BuilderBase mixin inheritance."""
from adk_fluent.agent import Agent
from adk_fluent.workflow import Pipeline, FanOut, Loop
from adk_fluent._base import BuilderBase


class TestBuilderBaseInheritance:
    def test_agent_is_builder_base(self):
        assert issubclass(Agent, BuilderBase)

    def test_pipeline_is_builder_base(self):
        assert issubclass(Pipeline, BuilderBase)

    def test_fanout_is_builder_base(self):
        assert issubclass(FanOut, BuilderBase)

    def test_loop_is_builder_base(self):
        assert issubclass(Loop, BuilderBase)

    def test_instance_check(self):
        agent = Agent("test")
        assert isinstance(agent, BuilderBase)

    def test_existing_functionality_preserved(self):
        agent = Agent("test")
        result = agent.instruct("Do stuff.")
        assert result is agent
        assert agent._config["instruction"] == "Do stuff."
