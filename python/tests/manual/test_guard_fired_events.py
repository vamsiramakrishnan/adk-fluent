"""Tests for Phase H: GuardFired event emission from guard sites."""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import EventBus, GuardViolation
from adk_fluent._base import _resolve_guard_tuple
from adk_fluent._harness._event_bus import use_bus


class _CBX:
    agent_name = "tester"


class _Part:
    def __init__(self, text: str) -> None:
        self.text = text


class _Content:
    def __init__(self, text: str) -> None:
        self.parts = [_Part(text)]


class _Response:
    def __init__(self, text: str) -> None:
        self.content = _Content(text)


def test_length_guard_emits_guard_fired_on_violation() -> None:
    bus = EventBus()
    fired: list = []
    bus.on("guard_fired", lambda e: fired.append(e))

    guard = _resolve_guard_tuple(("guard:length", {"min": 0, "max": 5}))

    async def _run() -> None:
        with use_bus(bus), pytest.raises(GuardViolation):
            await guard(callback_context=_CBX(), llm_response=_Response("way-too-long"))

    asyncio.run(_run())

    assert len(fired) == 1
    evt = fired[0]
    assert evt.guard_name == "length"
    assert evt.agent_name == "tester"
    assert evt.action == "reject"
    assert "too long" in evt.reason


def test_json_guard_emits_guard_fired() -> None:
    bus = EventBus()
    fired: list = []
    bus.on("guard_fired", lambda e: fired.append(e))

    guard = _resolve_guard_tuple(("guard:json", None))

    async def _run() -> None:
        with use_bus(bus), pytest.raises(GuardViolation):
            await guard(callback_context=_CBX(), llm_response=_Response("not json"))

    asyncio.run(_run())

    assert len(fired) == 1
    assert fired[0].guard_name == "json"


def test_guard_fired_noop_without_bus() -> None:
    """Guard still raises without an ambient bus — emit path is best-effort."""
    guard = _resolve_guard_tuple(("guard:length", {"min": 0, "max": 5}))

    async def _run() -> None:
        with pytest.raises(GuardViolation):
            await guard(callback_context=_CBX(), llm_response=_Response("overlong"))

    asyncio.run(_run())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
