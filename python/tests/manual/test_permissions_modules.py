"""Dedicated tests for the ``adk_fluent._permissions`` foundation.

Covers the decision dataclass, mode constants, policy precedence across all
five modes, argument rewriting, approval memory, and the synchronous
:func:`make_permission_callback` adapter. The async :class:`PermissionPlugin`
is exercised end-to-end by the integration tests; here we focus on the
building blocks in isolation.
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from adk_fluent import H, PermissionMode
from adk_fluent._permissions import (
    ALL_MODES,
    DEFAULT_MUTATING_TOOLS,
    DEFAULT_READ_ONLY_TOOLS,
    ApprovalMemory,
    PermissionBehavior,
    PermissionDecision,
    PermissionPlugin,
    PermissionPolicy,
)
from adk_fluent._permissions._callback import make_permission_callback

# ======================================================================
# PermissionDecision
# ======================================================================


class TestPermissionDecision:
    def test_allow_constructor(self):
        d = PermissionDecision.allow()
        assert d.is_allow and not d.is_deny and not d.is_ask
        assert d.is_terminal
        assert d.behavior == PermissionBehavior.ALLOW
        assert d.updated_input is None

    def test_allow_with_updated_input_copies_dict(self):
        src = {"path": "/tmp/x"}
        d = PermissionDecision.allow(updated_input=src)
        assert d.updated_input == src
        # Should not alias the caller's dict.
        src["path"] = "/tmp/y"
        assert d.updated_input == {"path": "/tmp/x"}

    def test_allow_rejects_non_dict_updated_input(self):
        with pytest.raises(TypeError):
            PermissionDecision.allow(updated_input=["not", "a", "dict"])  # type: ignore[arg-type]

    def test_deny_carries_reason(self):
        d = PermissionDecision.deny("nope")
        assert d.is_deny and d.is_terminal
        assert d.reason == "nope"

    def test_ask_carries_prompt(self):
        d = PermissionDecision.ask("Allow bash?")
        assert d.is_ask and not d.is_terminal
        assert d.prompt == "Allow bash?"

    def test_is_frozen(self):
        d = PermissionDecision.allow()
        with pytest.raises(FrozenInstanceError):
            d.behavior = "mutated"  # type: ignore[misc]


# ======================================================================
# PermissionMode
# ======================================================================


class TestPermissionMode:
    def test_all_modes_populated(self):
        assert frozenset(
            {
                PermissionMode.DEFAULT,
                PermissionMode.ACCEPT_EDITS,
                PermissionMode.PLAN,
                PermissionMode.BYPASS,
                PermissionMode.DONT_ASK,
            }
        ) == ALL_MODES

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown permission mode"):
            PermissionPolicy(mode="turbo")


# ======================================================================
# PermissionPolicy — precedence across modes
# ======================================================================


class TestPolicyPrecedence:
    def test_deny_beats_everything(self):
        policy = PermissionPolicy(
            mode=PermissionMode.BYPASS,
            deny=frozenset({"edit_file"}),
        )
        assert policy.check("edit_file").is_deny

    def test_deny_pattern_beats_mode(self):
        policy = PermissionPolicy(
            mode=PermissionMode.BYPASS,
            deny_patterns=("*secret*",),
        )
        assert policy.check("read_secret").is_deny

    def test_bypass_allows_unlisted(self):
        policy = PermissionPolicy(mode=PermissionMode.BYPASS)
        assert policy.check("anything").is_allow

    def test_plan_denies_mutating(self):
        policy = PermissionPolicy(mode=PermissionMode.PLAN)
        d = policy.check("edit_file")
        assert d.is_deny
        assert "Plan mode" in d.reason

    def test_plan_allows_read_only(self):
        policy = PermissionPolicy(
            mode=PermissionMode.PLAN,
            allow=frozenset({"read_file"}),
        )
        assert policy.check("read_file").is_allow

    def test_plan_denies_even_listed_mutating(self):
        policy = PermissionPolicy(
            mode=PermissionMode.PLAN,
            allow=frozenset({"edit_file"}),
        )
        # Plan mode denies mutating tools *before* consulting allow list.
        assert policy.check("edit_file").is_deny

    def test_accept_edits_allows_mutating(self):
        policy = PermissionPolicy(mode=PermissionMode.ACCEPT_EDITS)
        assert policy.check("edit_file").is_allow
        assert policy.check("write_file").is_allow

    def test_accept_edits_still_asks_for_non_mutating(self):
        policy = PermissionPolicy(mode=PermissionMode.ACCEPT_EDITS)
        d = policy.check("some_random_tool")
        assert d.is_ask

    def test_dont_ask_denies_unlisted(self):
        policy = PermissionPolicy(
            mode=PermissionMode.DONT_ASK,
            allow=frozenset({"read_file"}),
        )
        assert policy.check("read_file").is_allow
        assert policy.check("edit_file").is_deny

    def test_default_mode_asks(self):
        policy = PermissionPolicy()  # default mode
        assert policy.check("read_file").is_ask

    def test_allow_pattern(self):
        policy = PermissionPolicy(allow_patterns=("read_*",))
        assert policy.check("read_file").is_allow
        assert policy.check("read_notebook").is_allow
        assert policy.check("edit_file").is_ask

    def test_ask_pattern(self):
        policy = PermissionPolicy(ask_patterns=("bash*",))
        assert policy.check("bash").is_ask
        assert policy.check("bash_streaming").is_ask

    def test_regex_pattern_mode(self):
        policy = PermissionPolicy(
            allow_patterns=(r"^(read|list)_.*$",),
            pattern_mode="regex",
        )
        assert policy.check("read_file").is_allow
        assert policy.check("list_dir").is_allow
        assert policy.check("write_file").is_ask

    def test_pattern_mode_validation(self):
        with pytest.raises(ValueError, match="pattern_mode"):
            PermissionPolicy(pattern_mode="fuzzy")


# ======================================================================
# Policy composition
# ======================================================================


class TestPolicyComposition:
    def test_merge_unions_sets(self):
        p1 = PermissionPolicy(allow=frozenset({"read_file"}))
        p2 = PermissionPolicy(allow=frozenset({"list_dir"}))
        merged = p1.merge(p2)
        assert merged.check("read_file").is_allow
        assert merged.check("list_dir").is_allow

    def test_merge_deny_wins(self):
        p1 = PermissionPolicy(allow=frozenset({"bash"}))
        p2 = PermissionPolicy(deny=frozenset({"bash"}))
        merged = p1.merge(p2)
        assert merged.check("bash").is_deny

    def test_merge_mode_precedence(self):
        p1 = PermissionPolicy(mode=PermissionMode.DEFAULT)
        p2 = PermissionPolicy(mode=PermissionMode.BYPASS)
        merged = p1.merge(p2)
        assert merged.mode == PermissionMode.BYPASS
        # And the other direction: an explicit mode beats a default.
        merged2 = p2.merge(p1)
        assert merged2.mode == PermissionMode.BYPASS

    def test_merge_concatenates_patterns(self):
        p1 = PermissionPolicy(allow_patterns=("read_*",))
        p2 = PermissionPolicy(deny_patterns=("*secret*",))
        merged = p1.merge(p2)
        assert merged.check("read_file").is_allow
        assert merged.check("read_secret").is_deny

    def test_merge_regex_infects(self):
        p1 = PermissionPolicy(pattern_mode="glob")
        p2 = PermissionPolicy(pattern_mode="regex")
        assert p1.merge(p2).pattern_mode == "regex"

    def test_with_mode(self):
        policy = PermissionPolicy(allow=frozenset({"read_file"}))
        planned = policy.with_mode(PermissionMode.PLAN)
        assert planned.mode == PermissionMode.PLAN
        assert planned.allow == policy.allow

    def test_is_mutating_default_list(self):
        policy = PermissionPolicy()
        assert policy.is_mutating("edit_file")
        assert not policy.is_mutating("read_file")

    def test_default_mutating_list_stable(self):
        # Sanity-check the exported constant.
        assert "edit_file" in DEFAULT_MUTATING_TOOLS
        assert "bash" in DEFAULT_MUTATING_TOOLS
        assert "read_file" not in DEFAULT_MUTATING_TOOLS
        assert "read_file" in DEFAULT_READ_ONLY_TOOLS


# ======================================================================
# ApprovalMemory
# ======================================================================


class TestApprovalMemory:
    def test_remember_and_recall(self):
        mem = ApprovalMemory()
        mem.remember_specific("bash", {"cmd": "ls"}, True)
        assert mem.recall("bash", {"cmd": "ls"}) is True
        assert mem.recall("bash", {"cmd": "rm -rf /"}) is None

    def test_remember_tool_wide(self):
        mem = ApprovalMemory()
        mem.remember_tool("read_file", True)
        assert mem.recall("read_file", {"path": "/a"}) is True
        assert mem.recall("read_file", {"path": "/b"}) is True

    def test_deny_is_recalled(self):
        mem = ApprovalMemory()
        mem.remember_specific("bash", {}, False)
        assert mem.recall("bash", {}) is False

    def test_clear(self):
        mem = ApprovalMemory()
        mem.remember_tool("bash", True)
        mem.clear()
        assert mem.recall("bash", {}) is None


# ======================================================================
# make_permission_callback — synchronous adapter
# ======================================================================


def _fake_tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


class TestSyncCallback:
    def test_allow_returns_none(self):
        cb = make_permission_callback(
            PermissionPolicy(allow=frozenset({"read_file"}))
        )
        args: dict = {}
        result = cb(None, _fake_tool("read_file"), args, None)
        assert result is None

    def test_deny_returns_error_dict(self):
        cb = make_permission_callback(
            PermissionPolicy(deny=frozenset({"edit_file"}))
        )
        result = cb(None, _fake_tool("edit_file"), {}, None)
        assert isinstance(result, dict)
        assert "error" in result
        assert "deny" in result["error"].lower() or "edit_file" in result["error"]

    def test_ask_without_handler_denies(self):
        cb = make_permission_callback(PermissionPolicy())  # default → ask
        result = cb(None, _fake_tool("read_file"), {}, None)
        assert isinstance(result, dict) and "error" in result

    def test_ask_with_handler_allows(self):
        calls: list[tuple[str, dict]] = []

        def handler(name: str, args: dict) -> bool:
            calls.append((name, dict(args)))
            return True

        cb = make_permission_callback(PermissionPolicy(), handler=handler)
        assert cb(None, _fake_tool("read_file"), {"path": "/a"}, None) is None
        assert calls == [("read_file", {"path": "/a"})]

    def test_ask_with_handler_denies(self):
        cb = make_permission_callback(
            PermissionPolicy(), handler=lambda *_: False
        )
        result = cb(None, _fake_tool("read_file"), {}, None)
        assert isinstance(result, dict) and "denied" in result["error"].lower()

    def test_memory_short_circuits_handler(self):
        mem = ApprovalMemory()
        mem.remember_specific("read_file", {"path": "/a"}, True)
        calls: list[int] = []

        def handler(*_):
            calls.append(1)
            return False

        cb = make_permission_callback(
            PermissionPolicy(), handler=handler, memory=mem
        )
        assert cb(None, _fake_tool("read_file"), {"path": "/a"}, None) is None
        assert calls == []  # handler never consulted

    def test_handler_result_persisted_to_memory(self):
        mem = ApprovalMemory()
        cb = make_permission_callback(
            PermissionPolicy(), handler=lambda *_: True, memory=mem
        )
        cb(None, _fake_tool("read_file"), {"path": "/a"}, None)
        assert mem.recall("read_file", {"path": "/a"}) is True

    def test_handler_exception_becomes_deny(self):
        def handler(*_):
            raise RuntimeError("boom")

        cb = make_permission_callback(PermissionPolicy(), handler=handler)
        result = cb(None, _fake_tool("read_file"), {}, None)
        assert isinstance(result, dict) and "handler raised" in result["error"]


# ======================================================================
# PermissionPlugin — async path, end-to-end
# ======================================================================


class TestPermissionPlugin:
    def test_allow_path(self):
        plugin = PermissionPlugin(
            PermissionPolicy(allow=frozenset({"read_file"}))
        )
        args: dict = {"path": "/a"}
        result = asyncio.run(
            plugin.before_tool_callback(
                tool=_fake_tool("read_file"),
                tool_args=args,
                tool_context=None,
            )
        )
        assert result is None
        assert args == {"path": "/a"}

    def test_deny_path(self):
        plugin = PermissionPlugin(
            PermissionPolicy(deny=frozenset({"edit_file"}))
        )
        result = asyncio.run(
            plugin.before_tool_callback(
                tool=_fake_tool("edit_file"),
                tool_args={},
                tool_context=None,
            )
        )
        assert isinstance(result, dict) and "error" in result

    def test_updated_input_is_applied(self):
        class RewritingPolicy(PermissionPolicy):
            def check(self, tool_name, tool_input=None):  # type: ignore[override]
                return PermissionDecision.allow(
                    updated_input={"path": "/safe/path"}
                )

        plugin = PermissionPlugin(RewritingPolicy())
        args: dict = {"path": "/tmp/unsafe"}
        asyncio.run(
            plugin.before_tool_callback(
                tool=_fake_tool("edit_file"),
                tool_args=args,
                tool_context=None,
            )
        )
        assert args == {"path": "/safe/path"}

    def test_async_handler_awaited(self):
        async def handler(tool_name, tool_args, decision):
            await asyncio.sleep(0)
            return True

        plugin = PermissionPlugin(PermissionPolicy(), handler=handler)
        result = asyncio.run(
            plugin.before_tool_callback(
                tool=_fake_tool("read_file"),
                tool_args={},
                tool_context=None,
            )
        )
        assert result is None

    def test_sync_handler_supported(self):
        plugin = PermissionPlugin(
            PermissionPolicy(), handler=lambda *_: True
        )
        assert (
            asyncio.run(
                plugin.before_tool_callback(
                    tool=_fake_tool("read_file"),
                    tool_args={},
                    tool_context=None,
                )
            )
            is None
        )

    def test_handler_exception_becomes_deny(self):
        def handler(*_):
            raise RuntimeError("boom")

        plugin = PermissionPlugin(PermissionPolicy(), handler=handler)
        result = asyncio.run(
            plugin.before_tool_callback(
                tool=_fake_tool("read_file"),
                tool_args={},
                tool_context=None,
            )
        )
        assert isinstance(result, dict) and "handler raised" in result["error"]

    def test_missing_handler_on_ask_denies(self):
        plugin = PermissionPlugin(PermissionPolicy())
        result = asyncio.run(
            plugin.before_tool_callback(
                tool=_fake_tool("read_file"),
                tool_args={},
                tool_context=None,
            )
        )
        assert isinstance(result, dict) and "error" in result

    def test_memory_persists_across_calls(self):
        mem = ApprovalMemory()
        plugin = PermissionPlugin(
            PermissionPolicy(),
            handler=lambda *_: True,
            memory=mem,
        )
        asyncio.run(
            plugin.before_tool_callback(
                tool=_fake_tool("read_file"),
                tool_args={"path": "/a"},
                tool_context=None,
            )
        )
        assert mem.recall("read_file", {"path": "/a"}) is True


# ======================================================================
# H namespace sugar
# ======================================================================


class TestHNamespaceSugar:
    def test_permissions_plan(self):
        p = H.permissions_plan()
        assert p.mode == PermissionMode.PLAN
        assert p.check("edit_file").is_deny

    def test_permissions_bypass(self):
        p = H.permissions_bypass()
        assert p.mode == PermissionMode.BYPASS
        assert p.check("edit_file").is_allow

    def test_permissions_accept_edits(self):
        p = H.permissions_accept_edits()
        assert p.mode == PermissionMode.ACCEPT_EDITS
        assert p.check("edit_file").is_allow

    def test_permissions_dont_ask(self):
        p = H.permissions_dont_ask(allow=["read_file"])
        assert p.mode == PermissionMode.DONT_ASK
        assert p.check("read_file").is_allow
        assert p.check("edit_file").is_deny

    def test_permissions_factory(self):
        p = H.permissions(
            mode=PermissionMode.DEFAULT,
            allow=["read_file"],
            deny=["bash"],
        )
        assert p.check("read_file").is_allow
        assert p.check("bash").is_deny

    def test_ask_before_shortcut(self):
        p = H.ask_before("bash", "edit_file")
        assert p.check("bash").is_ask
        assert p.check("edit_file").is_ask

    def test_auto_allow_shortcut(self):
        p = H.auto_allow("read_file")
        assert p.check("read_file").is_allow

    def test_deny_shortcut(self):
        p = H.deny("rm")
        assert p.check("rm").is_deny

    def test_approval_memory_factory(self):
        mem = H.approval_memory()
        assert isinstance(mem, ApprovalMemory)

    def test_permission_plugin_factory(self):
        policy = H.auto_allow("read_file")
        plugin = H.permission_plugin(policy)
        assert isinstance(plugin, PermissionPlugin)
        assert plugin.policy is policy

    def test_permission_decision_factory(self):
        decision_cls = H.permission_decision()
        assert decision_cls is PermissionDecision
        assert decision_cls.allow().is_allow
