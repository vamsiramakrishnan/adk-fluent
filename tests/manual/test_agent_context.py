"""Tests for Agent.context() — wiring C transforms into agent compilation."""
import pytest
from adk_fluent import Agent
from adk_fluent._context import C


class TestAgentContextMethod:
    """Agent builder accepts .context() for C transforms."""

    def test_context_method_exists(self):
        a = Agent("a").model("gemini-2.5-flash").context(C.none())
        assert a is not None

    def test_context_returns_self_for_chaining(self):
        a = Agent("a").model("gemini-2.5-flash")
        result = a.context(C.none())
        assert result is a

    def test_context_stored_in_config(self):
        a = Agent("a").model("gemini-2.5-flash").context(C.user_only())
        assert "_context_spec" in a._config


class TestAgentContextCompilation:
    """Agent.context() affects LlmAgent compilation."""

    def test_c_none_sets_include_contents(self):
        a = Agent("a").model("gemini-2.5-flash").context(C.none())
        built = a.build()
        assert built.include_contents == "none"

    def test_c_default_keeps_include_contents(self):
        a = Agent("a").model("gemini-2.5-flash").context(C.default())
        built = a.build()
        assert built.include_contents == "default"

    def test_c_user_only_sets_instruction_provider(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Do something.")
            .context(C.user_only())
        )
        built = a.build()
        assert built.include_contents == "none"
        assert callable(built.instruction)

    def test_c_from_state_sets_instruction_provider(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Use context.")
            .context(C.from_state("intent", "confidence"))
        )
        built = a.build()
        assert built.include_contents == "none"
        assert callable(built.instruction)

    def test_context_with_template(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Respond helpfully.")
            .context(C.template("User: {user_message}\nIntent: {intent}"))
        )
        built = a.build()
        # CTemplate keeps include_contents="default" (base default)
        assert built.include_contents == "default"
        assert callable(built.instruction)


class TestAgentContextInPipeline:
    """Context integrates with pipeline composition."""

    def test_pipeline_with_context(self):
        pipeline = (
            Agent("classifier")
            .model("gemini-2.5-flash")
            .instruct("Classify.")
            .outputs("intent")
            >> Agent("handler")
            .model("gemini-2.5-flash")
            .instruct("Handle request.")
            .context(C.from_state("intent"))
        )
        built = pipeline.build()
        handler = built.sub_agents[1]
        assert handler.include_contents == "none"
        assert callable(handler.instruction)

    def test_context_with_window(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Process.")
            .context(C.window(n=5))
        )
        built = a.build()
        assert built.include_contents == "none"
        assert callable(built.instruction)
