"""Tests for check_contracts() contract verification."""
import pytest
from pydantic import BaseModel


class Intent(BaseModel):
    category: str
    confidence: float


class Resolution(BaseModel):
    ticket_id: str
    status: str


def test_valid_contract_no_issues():
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    issues = check_contracts(pipeline.to_ir())
    assert issues == []


def test_missing_producer_reports_issue():
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    pipeline = Agent("a") >> Agent("b").consumes(Intent)
    issues = check_contracts(pipeline.to_ir())
    assert len(issues) >= 1
    assert "category" in issues[0] or "confidence" in issues[0]


def test_untyped_agents_no_issues():
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    pipeline = Agent("a") >> Agent("b")
    issues = check_contracts(pipeline.to_ir())
    assert issues == []


def test_multi_step_contract_chain():
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    pipeline = (
        Agent("a").produces(Intent)
        >> Agent("b").consumes(Intent).produces(Resolution)
        >> Agent("c").consumes(Resolution)
    )
    issues = check_contracts(pipeline.to_ir())
    assert issues == []


def test_partial_overlap_reports_missing():
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts

    class Partial(BaseModel):
        category: str

    pipeline = Agent("a").produces(Partial) >> Agent("b").consumes(Intent)
    issues = check_contracts(pipeline.to_ir())
    assert len(issues) == 1
    assert "confidence" in issues[0]


def test_check_contracts_on_non_sequence():
    from adk_fluent import Agent
    from adk_fluent.testing import check_contracts
    issues = check_contracts(Agent("solo").to_ir())
    assert issues == []
