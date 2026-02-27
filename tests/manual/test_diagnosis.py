"""Tests for structured diagnostics (v0.9.2 — Tier 2)."""

from pydantic import BaseModel


class Intent(BaseModel):
    category: str
    confidence: float


def test_diagnose_returns_diagnosis():
    """diagnose() returns a Diagnosis dataclass."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import Diagnosis, diagnose

    pipeline = Agent("a").outputs("x") >> Agent("b").instruct("Use {x}.")
    ir = pipeline.to_ir()
    diag = diagnose(ir)
    assert isinstance(diag, Diagnosis)


def test_diagnosis_ok_property():
    """Diagnosis.ok is True when no errors."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose

    pipeline = Agent("a").outputs("x") >> Agent("b").instruct("Use {x}.")
    diag = diagnose(pipeline.to_ir())
    assert diag.ok


def test_diagnosis_not_ok_with_errors():
    """Diagnosis.ok is False when there are errors."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose

    pipeline = Agent("a") >> Agent("b").instruct("Use {missing}.")
    diag = diagnose(pipeline.to_ir())
    assert not diag.ok
    assert diag.error_count >= 1


def test_diagnosis_agents_populated():
    """Diagnosis.agents contains summaries of all nodes."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose

    pipeline = Agent("writer").outputs("draft") >> Agent("reviewer")
    diag = diagnose(pipeline.to_ir())
    agent_names = [a.name for a in diag.agents]
    assert "writer" in agent_names
    assert "reviewer" in agent_names


def test_diagnosis_data_flow_populated():
    """Diagnosis.data_flow tracks key flows."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose

    pipeline = Agent("writer").outputs("draft") >> Agent("reviewer").instruct("Review {draft}.")
    diag = diagnose(pipeline.to_ir())
    flow_keys = [f.key for f in diag.data_flow]
    assert "draft" in flow_keys
    draft_flow = [f for f in diag.data_flow if f.key == "draft"][0]
    assert draft_flow.producer == "writer"
    assert "reviewer" in draft_flow.consumers


def test_diagnosis_issues_structured():
    """Diagnosis.issues are ContractIssue dataclasses."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import ContractIssue, diagnose

    pipeline = Agent("a") >> Agent("b").instruct("Use {missing}.")
    diag = diagnose(pipeline.to_ir())
    assert len(diag.issues) > 0
    assert all(isinstance(i, ContractIssue) for i in diag.issues)
    assert diag.issues[0].level in ("error", "info")


def test_diagnosis_topology_is_mermaid():
    """Diagnosis.topology contains Mermaid source."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose

    pipeline = Agent("a") >> Agent("b")
    diag = diagnose(pipeline.to_ir())
    assert "graph TD" in diag.topology


def test_diagnosis_errors_property():
    """Diagnosis.errors filters to error-level issues."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose

    pipeline = Agent("a") >> Agent("b").instruct("Use {missing}.")
    diag = diagnose(pipeline.to_ir())
    assert all(i.level == "error" for i in diag.errors)


def test_diagnosis_warnings_property():
    """Diagnosis.warnings filters to info-level issues."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose

    pipeline = Agent("a").instruct("Write.") >> Agent("b").instruct("Next.")
    diag = diagnose(pipeline.to_ir())
    for w in diag.warnings:
        assert w.level == "info"


def test_builder_diagnose_method():
    """.diagnose() on builder returns Diagnosis."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import Diagnosis

    pipeline = Agent("a") >> Agent("b")
    diag = pipeline.diagnose()
    assert isinstance(diag, Diagnosis)


def test_builder_doctor_method(capsys):
    """.doctor() prints and returns report."""
    from adk_fluent import Agent

    pipeline = Agent("a").outputs("x") >> Agent("b").instruct("Use {x}.")
    report = pipeline.doctor()
    assert isinstance(report, str)
    assert "Pipeline Diagnosis" in report
    captured = capsys.readouterr()
    assert "Pipeline Diagnosis" in captured.out


def test_format_diagnosis_shows_agents():
    """Formatted report includes agent names."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose, format_diagnosis

    pipeline = Agent("writer").outputs("draft") >> Agent("reviewer").instruct("Review {draft}.")
    diag = diagnose(pipeline.to_ir())
    report = format_diagnosis(diag)
    assert "writer" in report
    assert "reviewer" in report


def test_format_diagnosis_shows_data_flow():
    """Formatted report includes data flow arrows."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose, format_diagnosis

    pipeline = Agent("writer").outputs("draft") >> Agent("reviewer").instruct("Review {draft}.")
    diag = diagnose(pipeline.to_ir())
    report = format_diagnosis(diag)
    assert "draft" in report
    assert "--[" in report  # flow arrow format


def test_format_diagnosis_shows_issues():
    """Formatted report includes issue details."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose, format_diagnosis

    pipeline = Agent("a") >> Agent("b").instruct("Use {missing}.")
    diag = diagnose(pipeline.to_ir())
    report = format_diagnosis(diag)
    assert "ERROR" in report
    assert "missing" in report


def test_diagnosis_with_produces_consumes():
    """Diagnosis captures produces/consumes type info."""
    from adk_fluent import Agent
    from adk_fluent.testing.diagnosis import diagnose

    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    diag = diagnose(pipeline.to_ir())
    a_summary = [s for s in diag.agents if s.name == "a"][0]
    b_summary = [s for s in diag.agents if s.name == "b"][0]
    assert a_summary.produces_type == "Intent"
    assert b_summary.consumes_type == "Intent"


def test_diagnosis_exports():
    """Tier 2 exports available from top-level."""
    from adk_fluent import AgentSummary, ContractIssue, Diagnosis, KeyFlow, diagnose, format_diagnosis

    assert Diagnosis is not None
    assert AgentSummary is not None
    assert KeyFlow is not None
    assert ContractIssue is not None
    assert callable(diagnose)
    assert callable(format_diagnosis)
