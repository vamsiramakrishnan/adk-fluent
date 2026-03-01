"""Tests for enhanced contract checking (v0.9.1 — Passes 8-9, context-aware diagnostics)."""

from pydantic import BaseModel

from adk_fluent.testing.contracts import _context_description, check_contracts


class Intent(BaseModel):
    category: str
    confidence: float


class PartialIntent(BaseModel):
    category: str


class Resolution(BaseModel):
    ticket_id: str
    status: str


# ======================================================================
# Pass 8: Dead key detection
# ======================================================================


def test_dead_key_detected():
    """Key produced but never consumed by downstream triggers info."""
    from adk_fluent import Agent

    pipeline = (
        Agent("a").instruct("Classify.").writes("classification")
        >> Agent("b").instruct("Write a report.")  # doesn't use {classification}
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    dead_issues = [i for i in issues if isinstance(i, dict) and "not consumed" in i.get("message", "")]
    assert any("classification" in i["message"] for i in dead_issues)


def test_no_dead_key_when_consumed():
    """Key produced and consumed via template var is not flagged."""
    from adk_fluent import Agent

    pipeline = Agent("a").instruct("Classify.").writes("classification") >> Agent("b").instruct(
        "Review the {classification}."
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    dead_issues = [i for i in issues if isinstance(i, dict) and "not consumed" in i.get("message", "")]
    # classification IS consumed, so no dead key
    assert not any("classification" in i["message"] for i in dead_issues)


def test_no_dead_key_for_last_agent():
    """Last agent's output_key is not flagged as dead (goes to user)."""
    from adk_fluent import Agent

    pipeline = Agent("a").instruct("Write.") >> Agent("b").instruct("Review.").writes("final_report")
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    dead_issues = [i for i in issues if isinstance(i, dict) and "not consumed" in i.get("message", "")]
    assert not any("final_report" in i["message"] for i in dead_issues)


def test_dead_key_with_writes_keys():
    """Dead key detection works with produces schema writes_keys."""
    from adk_fluent import Agent

    pipeline = Agent("a").produces(Intent) >> Agent("b").instruct("Next step.")
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    dead_issues = [i for i in issues if isinstance(i, dict) and "not consumed" in i.get("message", "")]
    # Both category and confidence are dead
    dead_keys = {i["message"].split("'")[1] for i in dead_issues}
    assert "category" in dead_keys
    assert "confidence" in dead_keys


# ======================================================================
# Pass 9: Type compatibility
# ======================================================================


def test_type_mismatch_detected():
    """consumes_type with fields not in produces_type triggers error."""
    from adk_fluent import Agent

    pipeline = (
        Agent("a").produces(PartialIntent)
        >> Agent("b").consumes(Intent)  # Intent has 'confidence' not in PartialIntent
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    type_issues = [i for i in issues if isinstance(i, dict) and "missing fields" in i.get("message", "")]
    assert len(type_issues) >= 1
    assert "confidence" in type_issues[0]["message"]


def test_type_match_clean():
    """Matching produces_type and consumes_type triggers no type error."""
    from adk_fluent import Agent

    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    type_issues = [i for i in issues if isinstance(i, dict) and "missing fields" in i.get("message", "")]
    assert len(type_issues) == 0


# ======================================================================
# Context-aware diagnostics
# ======================================================================


def test_context_description_user_only():
    from adk_fluent._context import CUserOnly

    assert "user_only" in _context_description(CUserOnly())


def test_context_description_window():
    from adk_fluent._context import CWindow

    desc = _context_description(CWindow(n=5))
    assert "window" in desc
    assert "5" in desc


def test_context_description_from_state():
    from adk_fluent._context import CFromState

    desc = _context_description(CFromState(keys=("topic",)))
    assert "from_state" in desc
    assert "topic" in desc


def test_context_description_none():
    assert "full conversation history" in _context_description(None)


def test_context_description_composite():
    from adk_fluent._context import CFromState, CWindow

    composite = CWindow(n=3) + CFromState(keys=("topic",))
    desc = _context_description(composite)
    assert "window" in desc
    assert "from_state" in desc


def test_data_loss_with_user_only_context():
    """Pass 6 uses context_spec kind for better message."""
    from adk_fluent import Agent, C

    pipeline = Agent("a").instruct("Write.") >> Agent("b").instruct("Review.").context(C.user_only())
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    loss_issues = [
        i for i in issues if isinstance(i, dict) and i.get("level") == "error" and "lost" in i.get("message", "")
    ]
    if loss_issues:
        assert "user messages" in loss_issues[0]["message"]


def test_data_loss_with_from_agents_including_predecessor():
    """No data loss when from_agents includes the predecessor."""
    from adk_fluent import Agent, C

    pipeline = Agent("writer").instruct("Write.") >> Agent("reviewer").instruct("Review.").context(
        C.from_agents("writer")
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    loss_issues = [
        i for i in issues if isinstance(i, dict) and i.get("level") == "error" and "lost" in i.get("message", "")
    ]
    # writer IS in from_agents, so output is NOT lost
    assert len(loss_issues) == 0


def test_data_loss_with_from_agents_excluding_predecessor():
    """Data loss when from_agents does not include the predecessor."""
    from adk_fluent import Agent, C

    pipeline = Agent("writer").instruct("Write.") >> Agent("reviewer").instruct("Review.").context(
        C.from_agents("other_agent")
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    loss_issues = [
        i for i in issues if isinstance(i, dict) and i.get("level") == "error" and "lost" in i.get("message", "")
    ]
    assert len(loss_issues) >= 1
    assert "does not include" in loss_issues[0]["message"]
