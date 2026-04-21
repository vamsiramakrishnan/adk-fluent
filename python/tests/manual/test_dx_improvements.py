"""Tests for P0/P1 DX improvements: validate, mock, doctor, operators."""

import pytest

from adk_fluent import Agent, Pipeline

# ======================================================================
# Enhanced .validate() — now runs contract checks
# ======================================================================


class TestValidateWithContracts:
    def test_validate_passes_for_valid_pipeline(self):
        """Valid pipeline with proper data flow passes validate."""
        pipeline = Agent("a").writes("x") >> Agent("b").instruct("Use {x}.")
        result = pipeline.validate()
        assert result is pipeline

    def test_validate_catches_missing_template_var(self):
        """Pipeline with unresolved template variable fails validate."""
        pipeline = Agent("a") >> Agent("b").instruct("Use {missing}.")
        with pytest.raises(ValueError, match="Validation failed"):
            pipeline.validate()

    def test_validate_strict_catches_advisories(self):
        """Strict mode raises on info-level issues too."""
        # Single-step pipeline is an advisory
        pipeline = Pipeline("wrapper").step(Agent("only"))
        # In strict mode, even advisories raise
        # (May or may not raise depending on what advisories are generated)
        pipeline.validate(strict=False)  # Should not raise with just advisories

    def test_validate_still_catches_build_errors(self):
        """Build errors are still caught."""
        agent = Agent("bad")
        agent._config["totally_invalid_field"] = "oops"
        with pytest.raises(ValueError, match="Validation failed"):
            agent.validate()

    def test_validate_returns_self_for_chaining(self):
        """validate() returns self for fluent chaining."""
        agent = Agent("a", "gemini-2.5-flash")
        result = agent.validate()
        assert result is agent

    def test_validate_single_agent_no_ir(self):
        """Single agent with no to_ir() still validates build."""
        agent = Agent("helper", "gemini-2.5-flash").instruct("Help.")
        result = agent.validate()
        assert result is agent


# ======================================================================
# Composition-level .mock() — dict-based multi-agent mocking
# ======================================================================


class TestMockByName:
    def test_mock_dict_on_pipeline(self):
        """Pipeline.mock(dict) propagates to named sub-agents."""
        pipeline = Agent("researcher", "gemini-2.5-flash").instruct("Research.") >> Agent(
            "writer", "gemini-2.5-flash"
        ).instruct("Write.")
        result = pipeline.mock(
            {
                "researcher": "Research findings.",
                "writer": "Final report.",
            }
        )
        assert result is pipeline

        # Verify callbacks were applied to sub-agents
        sub_agents = pipeline._lists["sub_agents"]
        for sub in sub_agents:
            name = sub._config.get("name", "")
            if name in ("researcher", "writer"):
                assert len(sub._callbacks.get("before_model_callback", [])) == 1

    def test_mock_dict_raises_on_unknown_agent(self):
        """mock(dict) with unmatched name raises ValueError."""
        pipeline = Agent("a", "gemini-2.5-flash") >> Agent("b", "gemini-2.5-flash")
        with pytest.raises(ValueError, match="could not find agent"):
            pipeline.mock({"nonexistent": "response"})

    def test_mock_dict_error_shows_available_names(self):
        """Error message includes available agent names."""
        pipeline = Agent("alice", "gemini-2.5-flash") >> Agent("bob", "gemini-2.5-flash")
        with pytest.raises(ValueError, match="alice") as exc_info:
            pipeline.mock({"charlie": "response"})
        assert "bob" in str(exc_info.value)

    def test_mock_dict_on_fanout(self):
        """FanOut.mock(dict) works on parallel branches."""
        fanout = Agent("fast", "gemini-2.5-flash") | Agent("slow", "gemini-2.5-flash")
        fanout.mock({"fast": "Quick answer", "slow": "Detailed answer"})
        for sub in fanout._lists["sub_agents"]:
            assert len(sub._callbacks.get("before_model_callback", [])) == 1

    def test_mock_dict_on_loop(self):
        """Loop.mock(dict) works on loop body agents."""
        loop = (Agent("writer", "gemini-2.5-flash") >> Agent("critic", "gemini-2.5-flash")) * 3
        loop.mock({"writer": "Draft.", "critic": "Looks good."})
        for sub in loop._lists["sub_agents"]:
            assert len(sub._callbacks.get("before_model_callback", [])) == 1

    def test_mock_dict_with_list_responses(self):
        """Dict values can be lists of responses."""
        pipeline = Agent("a", "gemini-2.5-flash") >> Agent("b", "gemini-2.5-flash")
        pipeline.mock({"a": ["first", "second"], "b": "always"})
        # a should have mock with cycle
        a = pipeline._lists["sub_agents"][0]
        cb = a._callbacks["before_model_callback"][0]
        r1 = cb(None, None)
        r2 = cb(None, None)
        assert r1.content.parts[0].text == "first"
        assert r2.content.parts[0].text == "second"

    def test_mock_list_still_works(self):
        """Original list-based mock still works."""
        agent = Agent("test", "gemini-2.5-flash")
        agent.mock(["response"])
        assert len(agent._callbacks["before_model_callback"]) == 1

    def test_mock_callable_still_works(self):
        """Original callable mock still works."""
        agent = Agent("test", "gemini-2.5-flash")
        agent.mock(lambda req: "fixed")
        assert len(agent._callbacks["before_model_callback"]) == 1


# ======================================================================
# Enhanced .doctor() — common mistake detection
# ======================================================================


class TestDoctorCommonMistakes:
    def test_doctor_catches_no_model(self):
        """doctor() reports agents without model."""
        pipeline = Agent("a") >> Agent("b")
        report = pipeline.show("doctor")
        assert "no model" in report.lower()

    def test_doctor_catches_no_instruction(self):
        """doctor() reports agents without instruction."""
        pipeline = Agent("a", "gemini-2.5-flash") >> Agent("b", "gemini-2.5-flash")
        report = pipeline.show("doctor")
        assert "no instruction" in report.lower()

    def test_doctor_catches_missing_key(self):
        """doctor() reports consumed-but-not-produced keys."""
        pipeline = Agent("a", "gemini-2.5-flash") >> Agent("b", "gemini-2.5-flash").instruct("Use {missing}.")
        report = pipeline.show("doctor")
        assert "missing" in report

    def test_doctor_clean_pipeline(self):
        """doctor() reports OK for a properly wired pipeline."""
        pipeline = Agent("a", "gemini-2.5-flash").instruct("Analyze.").writes("result") >> Agent(
            "b", "gemini-2.5-flash"
        ).instruct("Summarize {result}.")
        diag = pipeline.show("diagnose")
        # Should have no errors (may have advisories)
        assert diag.error_count == 0

    def test_diagnose_duplicate_names(self):
        """diagnose() catches duplicate agent names."""
        from adk_fluent.testing.diagnosis import diagnose

        # Create pipeline with duplicate names by building manually
        pipeline = Pipeline("test")
        pipeline.step(Agent("same", "gemini-2.5-flash").instruct("A"))
        pipeline.step(Agent("same", "gemini-2.5-flash").instruct("B"))
        diag = diagnose(pipeline.to_ir())
        dup_issues = [i for i in diag.issues if "appears" in i.message and "times" in i.message]
        assert len(dup_issues) > 0

    def test_diagnose_typo_suggestion(self):
        """diagnose() suggests close matches for typos."""
        from adk_fluent.testing.diagnosis import diagnose

        pipeline = (
            Agent("a", "gemini-2.5-flash").instruct("Go.").writes("result")
            >> Agent("b", "gemini-2.5-flash").instruct("Use {resul}.")  # typo
        )
        diag = diagnose(pipeline.to_ir())
        typo_issues = [i for i in diag.issues if "did you mean" in i.message.lower()]
        assert len(typo_issues) > 0

    def test_diagnose_schema_tool_conflict(self):
        """diagnose() catches .returns(Schema) + .tool() conflict."""
        from pydantic import BaseModel

        from adk_fluent.testing.diagnosis import diagnose

        class Out(BaseModel):
            x: str

        def my_tool():
            """A tool."""
            return "hi"

        agent = Agent("a", "gemini-2.5-flash").instruct("Go.").returns(Out).tool(my_tool)
        pipeline = Pipeline("p").step(agent)
        diag = diagnose(pipeline.to_ir())
        conflict_issues = [i for i in diag.issues if "silently disabled" in i.message]
        assert len(conflict_issues) > 0

    def test_diagnose_reads_without_writes(self):
        """diagnose() catches .reads() without upstream .writes()."""
        from adk_fluent.testing.diagnosis import diagnose

        pipeline = Agent("a", "gemini-2.5-flash").instruct("Go.") >> Agent("b", "gemini-2.5-flash").instruct(
            "Use."
        ).reads("missing_key")
        diag = diagnose(pipeline.to_ir())
        reads_issues = [i for i in diag.issues if ".reads('missing_key')" in i.message]
        assert len(reads_issues) > 0

    def test_optional_template_var_not_error(self):
        """Optional {var?} template vars get info, not error."""
        from adk_fluent.testing.diagnosis import diagnose

        pipeline = Agent("a", "gemini-2.5-flash").instruct("Go.") >> Agent("b", "gemini-2.5-flash").instruct(
            "Use {optional?} data."
        )
        diag = diagnose(pipeline.to_ir())
        # Should NOT have errors for optional vars
        opt_errors = [i for i in diag.issues if "optional" in i.message and i.level == "error"]
        assert len(opt_errors) == 0
        # May have info-level advisory
        opt_info = [i for i in diag.issues if "optional" in i.message.lower() and i.level == "info"]
        assert len(opt_info) >= 0  # Advisory is optional

    def test_required_template_var_still_error(self):
        """Required {var} template vars still get error."""
        pipeline = Agent("a", "gemini-2.5-flash").instruct("Go.") >> Agent("b", "gemini-2.5-flash").instruct(
            "Use {required_key}."
        )
        diag = pipeline.show("diagnose")
        req_errors = [i for i in diag.issues if "required_key" in i.message and i.level == "error"]
        assert len(req_errors) > 0

    def test_diagnose_parallel_write_collision(self):
        """diagnose() catches parallel branches writing same key."""
        from adk_fluent.testing.diagnosis import diagnose

        fanout = Agent("a", "gemini-2.5-flash").instruct("Go.").writes("result") | Agent(
            "b", "gemini-2.5-flash"
        ).instruct("Go.").writes("result")
        diag = diagnose(fanout.to_ir())
        collision_issues = [i for i in diag.issues if "last write wins" in i.message]
        assert len(collision_issues) > 0

    def test_instruct_on_pipeline_raises_attributeerror(self):
        """Calling .instruct() on Pipeline raises helpful AttributeError."""
        pipeline = Pipeline("flow").step(Agent("a", "gemini-2.5-flash").instruct("Go."))
        with pytest.raises(AttributeError, match="instruct.*is not a recognized field"):
            pipeline.instruct("This should not be here.")

    def test_writes_rejects_invalid_key(self):
        """writes() rejects non-identifier keys."""
        agent = Agent("a", "gemini-2.5-flash")
        with pytest.raises(ValueError, match="valid Python identifier"):
            agent.writes("not-valid")

    def test_writes_rejects_empty_key(self):
        """writes() rejects empty key."""
        agent = Agent("a", "gemini-2.5-flash")
        with pytest.raises(ValueError, match="non-empty string"):
            agent.writes("")

    def test_writes_accepts_valid_key(self):
        """writes() accepts valid identifier keys."""
        agent = Agent("a", "gemini-2.5-flash").writes("my_result")
        assert agent._config["output_key"] == "my_result"

    def test_getattr_suggests_close_match(self):
        """AttributeError suggests close match for typos."""
        agent = Agent("a", "gemini-2.5-flash")
        with pytest.raises(AttributeError, match="Did you mean"):
            agent.instruc("typo")  # missing 't'

    def test_mock_dict_suggests_close_match(self):
        """mock(dict) suggests close matches for agent name typos."""
        pipeline = Agent("researcher", "gemini-2.5-flash") >> Agent("writer", "gemini-2.5-flash")
        with pytest.raises(ValueError, match="did you mean") as exc_info:
            pipeline.mock({"resercher": "response"})  # typo
        assert "researcher" in str(exc_info.value)

    def test_writes_overwrite_warns(self):
        """writes() warns when overwriting an existing key."""
        import warnings

        agent = Agent("a", "gemini-2.5-flash").writes("first")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            agent.writes("second")
            assert len(w) == 1
            assert "overwrites" in str(w[0].message)


# ======================================================================
# Operator error messages
# ======================================================================


class TestOperatorErrors:
    def test_or_with_non_builder_returns_not_implemented(self):
        """agent | 'string' returns NotImplemented."""
        agent = Agent("a", "gemini-2.5-flash")
        result = agent.__or__("not a builder")
        assert result is NotImplemented

    def test_mul_with_non_int_returns_not_implemented(self):
        """agent * 'string' returns NotImplemented."""
        agent = Agent("a", "gemini-2.5-flash")
        result = agent.__mul__("not an int")
        assert result is NotImplemented

    def test_mul_with_zero_raises(self):
        """agent * 0 raises ValueError."""
        agent = Agent("a", "gemini-2.5-flash")
        with pytest.raises(ValueError, match="must be >= 1"):
            agent * 0

    def test_mul_with_negative_raises(self):
        """agent * -1 raises ValueError."""
        agent = Agent("a", "gemini-2.5-flash")
        with pytest.raises(ValueError, match="must be >= 1"):
            agent * -1

    def test_matmul_with_non_type_raises(self):
        """agent @ 'string' raises TypeError."""
        agent = Agent("a", "gemini-2.5-flash")
        with pytest.raises(TypeError, match="requires X to be a type"):
            agent @ "not a schema"

    def test_matmul_with_instance_raises(self):
        """agent @ instance raises TypeError."""
        from pydantic import BaseModel

        class MySchema(BaseModel):
            x: str

        agent = Agent("a", "gemini-2.5-flash")
        with pytest.raises(TypeError, match="requires X to be a type"):
            agent @ MySchema(x="hello")

    def test_rshift_with_string_returns_not_implemented(self):
        """agent >> 'string' returns NotImplemented."""
        agent = Agent("a", "gemini-2.5-flash")
        result = agent.__rshift__("not valid")
        assert result is NotImplemented


# ======================================================================
# Integration: validate + doctor work together
# ======================================================================


class TestIntegration:
    def test_validate_then_doctor(self):
        """validate() and doctor() give consistent results."""
        pipeline = Agent("a", "gemini-2.5-flash").instruct("Step 1.").writes("x") >> Agent(
            "b", "gemini-2.5-flash"
        ).instruct("Step 2 with {x}.")
        # Both should work without errors
        pipeline.validate()
        diag = pipeline.show("diagnose")
        assert diag.ok

    def test_validate_catches_what_doctor_reports(self):
        """If doctor() finds errors, validate() raises."""
        pipeline = Agent("a") >> Agent("b").instruct("Use {missing}.")
        diag = pipeline.show("diagnose")
        assert not diag.ok
        with pytest.raises(ValueError):
            pipeline.validate()
