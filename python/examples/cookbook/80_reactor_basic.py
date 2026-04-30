"""Reactive Conversation Phases — Signal, Predicate, Reactor Fundamentals

Real-world scenario: a debt collection system where conversation state
drives agent behavior. Signals track conversation phase, customer
sentiment, and payment agreement status. Predicates fire when phases
transition or sentiment drops. A computed signal derives overall
conversation health from multiple inputs.

When the customer commits to a payment plan, a reactor handler logs
the agreement to CRM — no polling, no manual dispatch.

Concepts:
  Signal        — typed state cell (phase, sentiment, agreement)
  Predicate     — edge-triggered filter (.rising, .falling, .where)
  computed()    — derived signal that auto-tracks reads
  Reactor       — cursor-following scheduler over the session tape

Run: uv run pytest examples/cookbook/80_reactor_basic.py -v
"""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import H, Reactor, Signal, computed


# ── Simulated CRM ──

crm_log: list[dict] = []


# ======================================================================
# Test 1: Phase signals emit change events on the tape
# ======================================================================


def test_phase_signal_emits_on_transition() -> None:
    """Setting a new phase emits a change; repeating is a no-op."""
    bus = H.event_bus()
    tape = bus.tape()

    phase = Signal("phase", "greeting", bus=bus)

    assert phase.set("verification") is True
    assert phase.set("verification") is False  # same value — skipped
    assert phase.set("negotiation") is True

    changes = [e for e in tape.events if e["kind"] == "signal_changed"]
    assert len(changes) == 2
    assert changes[0]["value"] == "verification"
    assert changes[1]["value"] == "negotiation"


# ======================================================================
# Test 2: Sentiment predicates filter by edge direction
# ======================================================================


def test_sentiment_predicates_detect_drops() -> None:
    """`.falling` + `.where()` triggers only when sentiment drops below 0.3."""
    sentiment = Signal("sentiment", 0.7)
    upset = sentiment.falling.where(lambda v, prev: v < 0.3)

    from adk_fluent._reactor._predicate import _Change

    assert upset.matches(_Change("sentiment", 0.2, 0.7))  # fell below 0.3
    assert not upset.matches(_Change("sentiment", 0.5, 0.7))  # fell but above 0.3
    assert not upset.matches(_Change("sentiment", 0.8, 0.5))  # rising, not falling


# ======================================================================
# Test 3: Computed health score from sentiment + phase progress
# ======================================================================


def test_computed_conversation_health() -> None:
    """Derived signal combines sentiment and phase into a health score."""
    phase = Signal("phase", "greeting")
    sentiment = Signal("sentiment", 0.8)

    progress = {"greeting": 0.0, "verification": 0.25, "negotiation": 0.5, "commitment": 0.75, "done": 1.0}

    health = computed("health", lambda: sentiment.get() * 0.6 + progress.get(phase.get(), 0) * 0.4)

    assert health.get() == pytest.approx(0.48)  # 0.8*0.6 + 0.0*0.4

    phase.set("negotiation")
    assert health.get() == pytest.approx(0.68)  # 0.8*0.6 + 0.5*0.4

    sentiment.set(0.3)  # customer getting upset
    assert health.get() == pytest.approx(0.38)  # drops with sentiment


# ======================================================================
# Test 4: Reactor fires CRM handler on payment agreement
# ======================================================================


@pytest.mark.asyncio
async def test_reactor_logs_agreement_to_crm() -> None:
    """When agreement signal changes from None to a plan, CRM handler fires."""
    bus = H.event_bus()
    tape = bus.tape()
    crm_log.clear()

    agreement = Signal("agreement", None, bus=bus)
    done = asyncio.Event()

    async def crm_handler(change) -> None:  # noqa: ANN001
        if change.value is not None:
            crm_log.append({
                "customer": "CUST-4821",
                "plan": change.value,
                "agent": "closer",
            })
            done.set()

    reactor = Reactor(tape, bus=bus)
    reactor.when(
        agreement.changed.where(lambda v, prev: v is not None),
        crm_handler,
        name="crm_log",
        priority=10,
    )

    run_task = asyncio.create_task(reactor.run(budget=1))
    await asyncio.sleep(0)

    agreement.set({"type": "3-month", "monthly": 250.00, "start": "2026-06-01"})

    await asyncio.wait_for(run_task, timeout=2.0)
    await asyncio.wait_for(done.wait(), timeout=1.0)

    assert len(crm_log) == 1
    assert crm_log[0]["plan"]["type"] == "3-month"
    assert crm_log[0]["customer"] == "CUST-4821"


# --- Runnable agent for visual playground ---
from adk_fluent import Agent

root_agent = (
    Agent("collection_agent", "gemini-2.5-flash")
    .instruct(
        "You are a debt collection agent for Acme Collections. "
        "Guide the conversation through phases: greeting, identity "
        "verification, negotiation, and commitment. Track customer "
        "sentiment and offer flexible payment plans."
    )
    .build()
)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
