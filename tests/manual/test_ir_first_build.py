"""Tests for IR-first build path with default contract checking."""

import pytest

from adk_fluent import Agent, S


class TestIRFirstBuildPath:
    """build() internally routes through to_ir → check_contracts."""

    def test_simple_agent_builds(self):
        """Single agent build still works (no IR contracts for single agents)."""
        a = Agent("a").model("gemini-2.5-flash").instruct("Hi")
        built = a.build()
        assert built is not None
        assert built.name == "a"

    def test_pipeline_builds_via_ir(self):
        """Pipeline.build() runs contracts by default (advisory mode)."""
        pipeline = Agent("a").model("m").instruct("Classify.").outputs("intent") >> Agent("b").model("m").instruct(
            "Handle: {intent}"
        )
        built = pipeline.build()
        assert built is not None
        assert len(built.sub_agents) == 2


class TestDefaultContractChecking:
    """Contract checking runs by default on build()."""

    def test_build_advisory_still_succeeds(self):
        """Pipeline with unresolved template var builds (advisory mode logs only)."""
        pipeline = Agent("a").model("m").instruct("Do stuff.") >> Agent("b").model("m").instruct("Summary: {summary}")
        # Build should succeed — advisory diagnostics don't block
        built = pipeline.build()
        assert built is not None

    def test_strict_raises_on_errors(self):
        """strict().build() promotes errors to ValueError."""
        pipeline = Agent("a").model("m").instruct("Do stuff.") >> Agent("b").model("m").instruct("Summary: {summary}")
        with pytest.raises(ValueError, match="[Cc]ontract"):
            pipeline.strict().build()

    def test_unchecked_skips_contracts(self):
        """unchecked().build() skips contract checking entirely."""
        pipeline = Agent("a").model("m").instruct("Do stuff.") >> Agent("b").model("m").instruct("Summary: {summary}")
        # No error — checking is off
        built = pipeline.unchecked().build()
        assert built is not None


class TestStrictAndUncheckedMethods:
    """Builder API for controlling contract check mode."""

    def test_strict_returns_self(self):
        pipeline = Agent("a").model("m").instruct("A.") >> Agent("b").model("m").instruct("B.")
        result = pipeline.strict()
        assert result is pipeline

    def test_unchecked_returns_self(self):
        pipeline = Agent("a").model("m").instruct("A.") >> Agent("b").model("m").instruct("B.")
        result = pipeline.unchecked()
        assert result is pipeline

    def test_strict_sets_config(self):
        pipeline = Agent("a").model("m").instruct("A.") >> Agent("b").model("m").instruct("B.")
        pipeline.strict()
        assert pipeline._config.get("_check_mode") == "strict"

    def test_unchecked_sets_config(self):
        pipeline = Agent("a").model("m").instruct("A.") >> Agent("b").model("m").instruct("B.")
        pipeline.unchecked()
        assert pipeline._config.get("_check_mode") is False


class TestStrictWithValidPipeline:
    """strict().build() succeeds when contracts are satisfied."""

    def test_valid_pipeline_strict(self):
        pipeline = Agent("classifier").model("m").instruct("Classify.").outputs("intent") >> Agent("handler").model(
            "m"
        ).instruct("Handle: {intent}")
        # No error — template var is resolved
        built = pipeline.strict().build()
        assert built is not None

    def test_capture_satisfies_template(self):
        pipeline = S.capture("user_message") >> Agent("a").model("m").instruct("User said: {user_message}")
        built = pipeline.strict().build()
        assert built is not None
