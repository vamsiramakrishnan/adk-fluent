"""Tests for the ``adk_fluent._plan_mode`` package.

Covers the latch, the tool factory, the policy wrapper that ties a
latch to a :class:`PermissionPolicy`, the ADK plugin, and the H
namespace factories (plan_mode, plan_mode_policy, plan_mode_plugin).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from adk_fluent import H
from adk_fluent._harness import (
    MUTATING_TOOLS,
    PlanMode,
    PlanModePlugin,
    PlanModePolicy,
    PlanState,
    plan_mode_tools,
)
from adk_fluent._permissions import (
    PermissionBehavior,
    PermissionMode,
    PermissionPolicy,
)


class TestPlanModeLatch:
    def test_default_state_is_off(self):
        latch = PlanMode()
        assert latch.current == "off"
        assert latch.current_plan == ""
        assert not latch.is_planning
        assert not latch.is_executing

    def test_enter_transitions_to_planning(self):
        latch = PlanMode()
        latch.enter()
        assert latch.current == "planning"
        assert latch.is_planning
        assert latch.current_plan == ""

    def test_exit_captures_plan_text(self):
        latch = PlanMode()
        latch.enter()
        latch.exit("1. Do X\n2. Do Y")
        assert latch.current == "executing"
        assert latch.is_executing
        assert latch.current_plan == "1. Do X\n2. Do Y"

    def test_reset_returns_to_off(self):
        latch = PlanMode()
        latch.enter()
        latch.exit("plan")
        latch.reset()
        assert latch.current == "off"
        assert latch.current_plan == ""

    def test_enter_clears_old_plan(self):
        latch = PlanMode()
        latch.enter()
        latch.exit("old")
        latch.enter()
        assert latch.current_plan == ""

    def test_is_mutating_classification(self):
        assert PlanMode.is_mutating("write_file")
        assert PlanMode.is_mutating("edit_file")
        assert PlanMode.is_mutating("bash")
        assert PlanMode.is_mutating("run_code")
        assert not PlanMode.is_mutating("read_file")
        assert not PlanMode.is_mutating("glob_search")

    def test_mutating_tools_set_is_frozen(self):
        assert isinstance(MUTATING_TOOLS, frozenset)
        assert "write_file" in MUTATING_TOOLS


class TestPlanModeObservers:
    def test_subscribe_receives_all_transitions(self):
        latch = PlanMode()
        events: list[tuple[str, str]] = []
        latch.subscribe(lambda state, plan: events.append((state, plan)))
        latch.enter()
        latch.exit("step 1")
        latch.reset()
        assert events == [
            ("planning", ""),
            ("executing", "step 1"),
            ("off", ""),
        ]

    def test_unsubscribe_stops_notifications(self):
        latch = PlanMode()
        events: list[str] = []
        unsub = latch.subscribe(lambda state, plan: events.append(state))
        latch.enter()
        unsub()
        latch.exit("x")
        assert events == ["planning"]

    def test_observer_exception_does_not_break_latch(self):
        latch = PlanMode()

        def broken(state: str, plan: str) -> None:
            raise RuntimeError("boom")

        latch.subscribe(broken)
        # Must not raise
        latch.enter()
        assert latch.current == "planning"


class TestPlanModeTools:
    def test_tool_pair_names(self):
        latch = PlanMode()
        tools = plan_mode_tools(latch)
        names = [t.__name__ for t in tools]
        assert names == ["enter_plan_mode", "exit_plan_mode"]

    def test_enter_tool_flips_latch(self):
        latch = PlanMode()
        enter, _ = plan_mode_tools(latch)
        result = enter()
        assert result == {"state": "planning"}
        assert latch.is_planning

    def test_exit_tool_captures_plan(self):
        latch = PlanMode()
        enter, exit_tool = plan_mode_tools(latch)
        enter()
        result = exit_tool(plan="1. step one\n2. step two")
        assert result["state"] == "executing"
        assert result["plan"] == "1. step one\n2. step two"

    def test_latch_tools_method_equivalent(self):
        latch = PlanMode()
        tools_a = latch.tools()
        tools_b = plan_mode_tools(latch)
        assert [t.__name__ for t in tools_a] == [t.__name__ for t in tools_b]


class TestPlanModePolicy:
    def test_off_state_delegates_to_base(self):
        base = PermissionPolicy(allow=frozenset({"read_file"}))
        latch = PlanMode()
        policy = PlanModePolicy(base=base, latch=latch)
        decision = policy.check("read_file")
        assert decision.is_allow

    def test_planning_denies_mutating(self):
        base = PermissionPolicy(allow=frozenset({"write_file"}))
        latch = PlanMode()
        policy = PlanModePolicy(base=base, latch=latch)
        latch.enter()
        decision = policy.check("write_file")
        assert decision.is_deny
        assert "Plan mode" in (decision.reason or "")

    def test_planning_still_allows_reads(self):
        base = PermissionPolicy(allow=frozenset({"read_file"}))
        latch = PlanMode()
        policy = PlanModePolicy(base=base, latch=latch)
        latch.enter()
        decision = policy.check("read_file")
        assert decision.is_allow

    def test_executing_behaves_like_off(self):
        base = PermissionPolicy(allow=frozenset({"write_file"}))
        latch = PlanMode()
        policy = PlanModePolicy(base=base, latch=latch)
        latch.enter()
        latch.exit("done")
        decision = policy.check("write_file")
        assert decision.is_allow

    def test_mode_reflects_latch(self):
        base = PermissionPolicy()
        latch = PlanMode()
        policy = PlanModePolicy(base=base, latch=latch)
        assert policy.mode == base.mode
        latch.enter()
        assert policy.mode == PermissionMode.PLAN
        latch.reset()
        assert policy.mode == base.mode

    def test_passthrough_allow_deny_ask(self):
        base = PermissionPolicy(
            allow=frozenset({"read_file"}),
            deny=frozenset({"rm"}),
            ask=frozenset({"bash"}),
        )
        latch = PlanMode()
        policy = PlanModePolicy(base=base, latch=latch)
        assert policy.allow == base.allow
        assert policy.deny == base.deny
        assert policy.ask == base.ask

    def test_policy_is_frozen(self):
        base = PermissionPolicy()
        latch = PlanMode()
        policy = PlanModePolicy(base=base, latch=latch)
        with pytest.raises(Exception):
            policy.base = PermissionPolicy()  # type: ignore[misc]


class TestPlanModePlugin:
    @pytest.mark.asyncio
    async def test_allows_tool_when_off(self):
        plugin = PlanModePlugin()
        tool = SimpleNamespace(name="write_file")
        result = await plugin.before_tool_callback(tool=tool)
        assert result is None

    @pytest.mark.asyncio
    async def test_denies_mutating_when_planning(self):
        plugin = PlanModePlugin()
        plugin.latch.enter()
        tool = SimpleNamespace(name="write_file")
        result = await plugin.before_tool_callback(tool=tool)
        assert result is not None
        assert "Plan mode" in result["error"]
        assert result["plan_mode_state"] == "planning"

    @pytest.mark.asyncio
    async def test_allows_read_when_planning(self):
        plugin = PlanModePlugin()
        plugin.latch.enter()
        tool = SimpleNamespace(name="read_file")
        result = await plugin.before_tool_callback(tool=tool)
        assert result is None

    @pytest.mark.asyncio
    async def test_allows_mutating_after_exit(self):
        plugin = PlanModePlugin()
        plugin.latch.enter()
        plugin.latch.exit("ok")
        tool = SimpleNamespace(name="edit_file")
        result = await plugin.before_tool_callback(tool=tool)
        assert result is None

    def test_plugin_accepts_pre_built_latch(self):
        latch = PlanMode()
        plugin = PlanModePlugin(latch)
        assert plugin.latch is latch

    def test_plugin_is_base_plugin(self):
        from google.adk.plugins.base_plugin import BasePlugin

        assert isinstance(PlanModePlugin(), BasePlugin)


class TestHNamespaceFactories:
    def test_plan_mode_factory(self):
        latch = H.plan_mode()
        assert isinstance(latch, PlanMode)
        assert latch.current == "off"

    def test_plan_mode_policy_factory(self):
        base = PermissionPolicy()
        policy = H.plan_mode_policy(base)
        assert isinstance(policy, PlanModePolicy)
        assert policy.base is base
        assert isinstance(policy.latch, PlanMode)

    def test_plan_mode_policy_factory_with_latch(self):
        base = PermissionPolicy()
        latch = PlanMode()
        policy = H.plan_mode_policy(base, latch)
        assert policy.latch is latch

    def test_plan_mode_plugin_factory(self):
        plugin = H.plan_mode_plugin()
        assert isinstance(plugin, PlanModePlugin)
        assert plugin.latch.current == "off"

    def test_plan_mode_plugin_factory_custom_name(self):
        plugin = H.plan_mode_plugin(name="my_plan_mode")
        assert plugin.name == "my_plan_mode"
