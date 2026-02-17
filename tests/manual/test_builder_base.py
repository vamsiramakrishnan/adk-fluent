"""Tests for BuilderBase mixin inheritance and shared methods."""
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


class TestCloneFromBuilderBase:
    """clone() is defined on BuilderBase and works for all builder types."""

    def test_agent_clone_exists(self):
        agent = Agent("a")
        cloned = agent.clone("b")
        assert cloned is not agent
        assert cloned._config["name"] == "b"
        assert type(cloned) is Agent

    def test_pipeline_clone_exists(self):
        pipeline = Pipeline("p1")
        cloned = pipeline.clone("p2")
        assert cloned is not pipeline
        assert cloned._config["name"] == "p2"
        assert type(cloned) is Pipeline

    def test_fanout_clone_exists(self):
        fanout = FanOut("f1")
        cloned = fanout.clone("f2")
        assert cloned is not fanout
        assert cloned._config["name"] == "f2"
        assert type(cloned) is FanOut

    def test_loop_clone_exists(self):
        loop = Loop("l1")
        cloned = loop.clone("l2")
        assert cloned is not loop
        assert cloned._config["name"] == "l2"
        assert type(cloned) is Loop

    def test_clone_preserves_config(self):
        agent = Agent("original").instruct("Do something")
        cloned = agent.clone("copy")
        assert cloned._config["instruction"] == "Do something"
        assert cloned._config["name"] == "copy"

    def test_clone_is_deep_independent(self):
        agent = Agent("original").instruct("X")
        cloned = agent.clone("copy")
        cloned._config["instruction"] = "Y"
        assert agent._config["instruction"] == "X"

    def test_clone_not_generated_as_explicit_method(self):
        """clone should come from BuilderBase, not be generated as an extra."""
        # Verify it is inherited from BuilderBase, not defined on the class itself
        assert "clone" in dir(Agent)
        assert "clone" not in Agent.__dict__, (
            "clone should be inherited from BuilderBase, not defined on Agent"
        )


class TestPrepareBuildConfig:
    """_prepare_build_config() strips internal fields and auto-builds sub-builders."""

    def test_strips_underscore_prefixed_fields(self):
        agent = Agent("test")
        agent._config["_debug"] = True
        agent._config["_retry"] = {"max_attempts": 3, "backoff": 1.0}
        agent._config["_fallbacks"] = ["model-b"]
        agent._config["_output_schema"] = object
        agent._config["model"] = "gemini-2.0-flash"
        config = agent._prepare_build_config()
        assert "_debug" not in config
        assert "_retry" not in config
        assert "_fallbacks" not in config
        assert "_output_schema" not in config
        assert config["model"] == "gemini-2.0-flash"
        assert config["name"] == "test"

    def test_merges_callbacks(self):
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        agent = Agent("test")
        agent._callbacks["before_model_callback"].append(fn1)
        agent._callbacks["before_model_callback"].append(fn2)
        config = agent._prepare_build_config()
        assert config["before_model_callback"] == [fn1, fn2]

    def test_single_callback_unwrapped(self):
        fn1 = lambda ctx: None
        agent = Agent("test")
        agent._callbacks["before_model_callback"].append(fn1)
        config = agent._prepare_build_config()
        assert config["before_model_callback"] is fn1

    def test_merges_lists(self):
        agent = Agent("test")
        agent._lists["tools"].append("tool_a")
        agent._lists["tools"].append("tool_b")
        config = agent._prepare_build_config()
        assert config["tools"] == ["tool_a", "tool_b"]

    def test_auto_builds_sub_builders_in_lists(self):
        """Sub-builders in lists should be auto-built via _prepare_build_config."""
        outer = Agent("outer")
        inner = Agent("inner").instruct("inner instruction").model("gemini-2.0-flash")
        outer._lists["sub_agents"].append(inner)
        config = outer._prepare_build_config()
        # The inner builder should have been replaced with a built ADK agent
        resolved = config["sub_agents"][0]
        assert not isinstance(resolved, BuilderBase)
        assert hasattr(resolved, "name")
        assert resolved.name == "inner"

    def test_auto_builds_sub_builders_in_config(self):
        """Sub-builders in config values should be auto-built."""
        # Use a builder as a config value
        agent = Agent("test")
        inner_builder = Agent("sub").instruct("sub instruction").model("gemini-2.0-flash")
        agent._config["some_agent"] = inner_builder
        config = agent._prepare_build_config()
        resolved = config["some_agent"]
        assert not isinstance(resolved, BuilderBase)
        assert hasattr(resolved, "name")
        assert resolved.name == "sub"
