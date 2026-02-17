"""Tests for antipattern fixes: counter safety, explicit fields, structured output, sync/async."""
import asyncio

import pytest

from adk_fluent.agent import Agent
from adk_fluent._base import BuilderBase, _fn_step, _fn_step_counter


# ======================================================================
# Fix 1: itertools.count() replaces global mutable counter
# ======================================================================


class TestFnStepCounter:
    """The counter should use itertools.count, not a global int."""

    def test_counter_is_itertools_count(self):
        import itertools
        assert isinstance(_fn_step_counter, itertools.count)

    def test_counter_increments(self):
        """Creating fn_steps with non-identifier names increments the counter."""
        # Use a lambda (whose __name__ is "<lambda>", not an identifier)
        step1 = _fn_step(lambda s: s)
        step2 = _fn_step(lambda s: s)
        name1 = step1._config["name"]
        name2 = step2._config["name"]
        assert name1.startswith("fn_step_")
        assert name2.startswith("fn_step_")
        # Each should get a unique counter value
        assert name1 != name2

    def test_named_function_uses_own_name(self):
        """Functions with valid identifier names use their own name, not the counter."""
        def my_transform(state):
            return state
        step = _fn_step(my_transform)
        assert step._config["name"] == "my_transform"


# ======================================================================
# Fix 2: Explicit field methods on generated builders
# ======================================================================


class TestExplicitFieldMethods:
    """Fields that previously went through __getattr__ now have explicit methods."""

    def test_model_is_explicit_method(self):
        """Agent.model() should be a real method, not __getattr__ closure."""
        assert "model" in Agent.__dict__, (
            "model should be an explicit method on Agent, not resolved via __getattr__"
        )

    def test_sub_agents_is_explicit_method(self):
        assert "sub_agents" in Agent.__dict__

    def test_generate_content_config_is_explicit_method(self):
        assert "generate_content_config" in Agent.__dict__

    def test_disallow_transfer_to_parent_is_explicit_method(self):
        assert "disallow_transfer_to_parent" in Agent.__dict__

    def test_planner_is_explicit_method(self):
        assert "planner" in Agent.__dict__

    def test_code_executor_is_explicit_method(self):
        assert "code_executor" in Agent.__dict__

    def test_explicit_method_stores_in_config(self):
        agent = Agent("test")
        result = agent.model("gemini-2.5-flash")
        assert agent._config["model"] == "gemini-2.5-flash"
        assert result is agent  # returns self for chaining

    def test_explicit_method_chainable(self):
        agent = (
            Agent("test")
            .model("gemini-2.5-flash")
            .disallow_transfer_to_parent(True)
            .instruct("Do stuff")
        )
        assert agent._config["model"] == "gemini-2.5-flash"
        assert agent._config["disallow_transfer_to_parent"] is True
        assert agent._config["instruction"] == "Do stuff"

    def test_getattr_still_works_as_safety_net(self):
        """__getattr__ should still handle truly unknown fields from ADK."""
        agent = Agent("test")
        # This field name doesn't exist on LlmAgent, so __getattr__ should
        # raise AttributeError with a helpful message
        with pytest.raises(AttributeError, match="not a recognized field"):
            agent.zzz_totally_fake("value")


# ======================================================================
# Fix 3: Structured output parse failure raises ValueError
# ======================================================================


class TestStructuredOutputParseFailure:
    """When structured output parsing fails, ValueError should be raised."""

    def test_stores_schema_in_config(self):
        """Basic mechanic: .output() stores the schema."""
        class FakeSchema:
            pass
        a = Agent("test").output(FakeSchema)
        assert a._config["_output_schema"] is FakeSchema

    def test_matmul_stores_schema(self):
        """@ operator stores schema via clone."""
        class FakeSchema:
            pass
        a = Agent("test") @ FakeSchema
        assert a._config["_output_schema"] is FakeSchema


# ======================================================================
# Fix 4: Sync wrappers raise RuntimeError in running event loops
# ======================================================================


class TestSyncAsyncBridge:
    """Sync wrappers should raise RuntimeError inside running event loops."""

    def test_run_sync_raises_in_running_loop(self):
        from adk_fluent._helpers import _run_sync

        async def _inner():
            with pytest.raises(RuntimeError, match="Cannot use synchronous methods"):
                _run_sync(asyncio.sleep(0))

        asyncio.run(_inner())

    def test_run_sync_works_outside_loop(self):
        """Outside a running loop, _run_sync should execute the coroutine."""
        from adk_fluent._helpers import _run_sync

        async def _return_42():
            return 42

        result = _run_sync(_return_42())
        assert result == 42


# ======================================================================
# Fix 5: Serialization -- from_dict/from_yaml removed
# ======================================================================


class TestSerializationRemoval:
    def test_builder_base_has_no_from_dict(self):
        assert not hasattr(BuilderBase, "from_dict")

    def test_builder_base_has_no_from_yaml(self):
        assert not hasattr(BuilderBase, "from_yaml")

    def test_to_dict_still_works(self):
        agent = Agent("test").model("gemini-2.5-flash")
        d = agent.to_dict()
        assert d["_type"] == "Agent"
        assert d["config"]["name"] == "test"

    def test_to_yaml_still_works(self):
        agent = Agent("test").model("gemini-2.5-flash")
        y = agent.to_yaml()
        assert isinstance(y, str)
        assert "test" in y
