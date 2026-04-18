"""Tests for Phase H: HookRegistry.bridge_to mirrors HookFired to a bus."""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import EventBus, H
from adk_fluent._hooks._decision import HookDecision
from adk_fluent._hooks._events import HookContext


def _ctx(event: str = "pre_tool_use", tool_name: str = "bash") -> HookContext:
    return HookContext(
        event=event,
        tool_name=tool_name,
        tool_input={"command": "ls"},
        agent_name="tester",
        session_id="s1",
        invocation_id="i1",
    )


def test_bridge_to_emits_hook_fired_allow() -> None:
    bus = EventBus()
    fires: list = []
    bus.on("hook_fired", lambda e: fires.append(e))

    registry = H.hooks().bridge_to(bus)
    registry.on("pre_tool_use", lambda ctx: HookDecision.allow(), name="noop")

    asyncio.run(registry.dispatch(_ctx()))

    assert len(fires) == 1
    assert fires[0].hook_name == "noop"
    assert "pre_tool_use:" in fires[0].trigger


def test_bridge_to_captures_deny_trigger() -> None:
    bus = EventBus()
    fires: list = []
    bus.on("hook_fired", lambda e: fires.append(e))

    registry = H.hooks().bridge_to(bus)
    registry.on(
        "pre_tool_use",
        lambda ctx: HookDecision.deny(reason="blocked"),
        name="block_rm",
    )

    asyncio.run(registry.dispatch(_ctx()))

    assert len(fires) == 1
    assert fires[0].hook_name == "block_rm"
    assert fires[0].trigger.endswith(":deny")


def test_bridge_detach_with_none() -> None:
    bus = EventBus()
    fires: list = []
    bus.on("hook_fired", lambda e: fires.append(e))

    registry = H.hooks().bridge_to(bus).bridge_to(None)
    registry.on("pre_tool_use", lambda ctx: HookDecision.allow(), name="noop")

    asyncio.run(registry.dispatch(_ctx()))

    assert fires == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
