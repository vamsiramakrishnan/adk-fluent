"""Tests for cross-channel contract checker (v5.1)."""

from pydantic import BaseModel

from adk_fluent import Agent
from adk_fluent._routing import Route
from adk_fluent.testing import check_contracts


class TestTemplateVariableResolution:
    def test_resolved_template_var_no_issue(self):
        pipeline = (
            Agent("classifier").model("m").instruct("Classify.").outputs("intent")
            >> Agent("handler").model("m").instruct("Intent: {intent}")
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert len(errors) == 0

    def test_unresolved_template_var_reports_error(self):
        pipeline = (
            Agent("a").model("m").instruct("Do stuff.")
            >> Agent("b").model("m").instruct("Summary: {summary}")
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert any("summary" in str(i) for i in errors)


class TestChannelDuplication:
    def test_duplication_warning(self):
        pipeline = (
            Agent("classifier").model("m").instruct("Classify.").outputs("intent")
            >> Agent("handler").model("m").instruct("Intent: {intent}")
        )
        issues = check_contracts(pipeline.to_ir())
        info = [i for i in issues if isinstance(i, dict) and i.get("level") == "info"]
        assert any("duplication" in str(i).lower() or "duplicate" in str(i).lower() for i in info)


class TestRouteKeyValidation:
    def test_route_key_satisfied(self):
        pipeline = (
            Agent("classifier").model("m").instruct("Classify.").outputs("intent")
            >> Route("intent").eq("booking", Agent("booker").model("m").instruct("Book."))
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert len(errors) == 0

    def test_route_key_missing(self):
        pipeline = (
            Agent("classifier").model("m").instruct("Classify.")
            >> Route("intent").eq("booking", Agent("booker").model("m").instruct("Book."))
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert any("intent" in str(i) for i in errors)


class TestDataLossDetection:
    def test_no_data_loss_with_outputs(self):
        pipeline = (
            Agent("a").model("m").instruct("Do.").outputs("result")
            >> Agent("b").model("m").instruct("Use: {result}")
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert len(errors) == 0


class TestVisibilityCoherence:
    def test_internal_agent_without_output_key_info(self):
        pipeline = (
            Agent("a").model("m").instruct("Process.")
            >> Agent("b").model("m").instruct("Consume.")
        )
        issues = check_contracts(pipeline.to_ir())
        # Should have at least one info about "a" being internal without output_key
        info = [i for i in issues if isinstance(i, dict) and i.get("level") == "info"]
        assert len(info) >= 1


class TestBackwardCompatibility:
    def test_old_style_reads_writes(self):
        # Old-style uses reads_keys/writes_keys frozensets on IR nodes via Pydantic schemas

        class Intent(BaseModel):
            category: str
            confidence: float

        pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
        result = check_contracts(pipeline.to_ir())
        assert isinstance(result, list)

    def test_untyped_agents_return_empty_for_pass1(self):
        """Backward compat: untyped agents produce no Pass 1 string issues."""
        pipeline = Agent("a") >> Agent("b")
        result = check_contracts(pipeline.to_ir())
        # Pass 1 (old-style) should produce no string issues
        string_issues = [i for i in result if isinstance(i, str)]
        assert string_issues == []

    def test_missing_producer_returns_string(self):
        """Backward compat: missing producer still returns a string issue."""

        class Intent(BaseModel):
            category: str
            confidence: float

        pipeline = Agent("a") >> Agent("b").consumes(Intent)
        result = check_contracts(pipeline.to_ir())
        string_issues = [i for i in result if isinstance(i, str)]
        assert len(string_issues) >= 1
        assert any("category" in s or "confidence" in s for s in string_issues)

    def test_non_sequence_returns_empty(self):
        """Backward compat: non-sequence nodes return empty list."""
        result = check_contracts(Agent("solo").model("m").instruct("Hi.").to_ir())
        assert result == []
