"""Tests for adk_fluent._hooks — the unified hook foundation.

Dedicated module for the hooks package. Exercises each public surface:

- :class:`HookEvent` taxonomy + :class:`HookContext`
- :class:`HookDecision` constructors, predicates, and folding semantics
- :class:`HookMatcher` (event / tool_name / args / predicate)
- :class:`HookRegistry` registration + dispatch + merge
- :class:`HookPlugin` ADK integration and decision translators
- :class:`SystemMessageChannel` append / drain
- ``H.hooks()`` / ``H.hook_decision()`` / ``H.hook_match()`` namespace helpers
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from adk_fluent import H
from adk_fluent._hooks import (
    ALL_EVENTS,
    SYSTEM_MESSAGE_STATE_KEY,
    HookAction,
    HookContext,
    HookDecision,
    HookEntry,
    HookEvent,
    HookMatcher,
    HookPlugin,
    HookRegistry,
    SystemMessageChannel,
)
from adk_fluent._hooks._plugin import HookAsk


def _run(coro):
    return asyncio.run(coro)


# ======================================================================
# Event taxonomy
# ======================================================================


class TestHookEvent:
    def test_all_events_is_frozenset(self) -> None:
        assert isinstance(ALL_EVENTS, frozenset)

    def test_tool_lifecycle_events_present(self) -> None:
        assert HookEvent.PRE_TOOL_USE in ALL_EVENTS
        assert HookEvent.POST_TOOL_USE in ALL_EVENTS
        assert HookEvent.TOOL_ERROR in ALL_EVENTS

    def test_model_lifecycle_events_present(self) -> None:
        assert HookEvent.PRE_MODEL in ALL_EVENTS
        assert HookEvent.POST_MODEL in ALL_EVENTS
        assert HookEvent.MODEL_ERROR in ALL_EVENTS

    def test_agent_lifecycle_events_present(self) -> None:
        assert HookEvent.PRE_AGENT in ALL_EVENTS
        assert HookEvent.POST_AGENT in ALL_EVENTS
        assert HookEvent.AGENT_ERROR in ALL_EVENTS

    def test_session_lifecycle_events_present(self) -> None:
        assert HookEvent.SESSION_START in ALL_EVENTS
        assert HookEvent.USER_PROMPT_SUBMIT in ALL_EVENTS
        assert HookEvent.SESSION_END in ALL_EVENTS

    def test_harness_extension_events_present(self) -> None:
        assert HookEvent.PRE_COMPACT in ALL_EVENTS
        assert HookEvent.PERMISSION_REQUEST in ALL_EVENTS
        assert HookEvent.NOTIFICATION in ALL_EVENTS


# ======================================================================
# HookContext
# ======================================================================


class TestHookContext:
    def test_context_has_sensible_defaults(self) -> None:
        ctx = HookContext(event=HookEvent.PRE_TOOL_USE)
        assert ctx.event == HookEvent.PRE_TOOL_USE
        assert ctx.tool_name is None
        assert ctx.extra == {}

    def test_context_is_mutable_for_plugin_updates(self) -> None:
        """Plugin sets tool_output / error post-hoc — must be assignable."""
        ctx = HookContext(event=HookEvent.POST_TOOL_USE, tool_name="bash")
        ctx.tool_output = {"stdout": "ok"}
        assert ctx.tool_output == {"stdout": "ok"}

    def test_get_prefers_top_level(self) -> None:
        ctx = HookContext(event=HookEvent.PRE_TOOL_USE, tool_name="edit_file")
        ctx.extra["tool_name"] = "SHOULD_NOT_SHADOW"
        assert ctx.get("tool_name") == "edit_file"

    def test_get_falls_back_to_extra(self) -> None:
        ctx = HookContext(event=HookEvent.NOTIFICATION)
        ctx.extra["custom"] = 42
        assert ctx.get("custom") == 42

    def test_get_returns_default(self) -> None:
        ctx = HookContext(event=HookEvent.NOTIFICATION)
        assert ctx.get("missing", "fallback") == "fallback"


# ======================================================================
# HookDecision
# ======================================================================


class TestHookDecision:
    def test_allow(self) -> None:
        d = HookDecision.allow()
        assert d.action == HookAction.ALLOW
        assert d.is_allow
        assert not d.is_terminal

    def test_deny(self) -> None:
        d = HookDecision.deny("forbidden")
        assert d.action == HookAction.DENY
        assert d.reason == "forbidden"
        assert d.is_terminal
        assert not d.is_allow

    def test_modify_requires_dict(self) -> None:
        with pytest.raises(TypeError):
            HookDecision.modify("not a dict")  # type: ignore[arg-type]

    def test_modify_copies_dict(self) -> None:
        args = {"path": "foo"}
        d = HookDecision.modify(args)
        args["path"] = "mutated"
        assert d.tool_input == {"path": "foo"}

    def test_replace(self) -> None:
        d = HookDecision.replace(output={"result": "stub"})
        assert d.is_terminal
        assert d.output == {"result": "stub"}

    def test_ask(self) -> None:
        d = HookDecision.ask("May I proceed?")
        assert d.is_terminal
        assert d.prompt == "May I proceed?"

    def test_inject_is_side_effect(self) -> None:
        d = HookDecision.inject("you just edited main.py")
        assert d.is_side_effect
        assert not d.is_terminal
        assert d.system_message == "you just edited main.py"


# ======================================================================
# HookMatcher
# ======================================================================


class TestHookMatcher:
    def test_unknown_event_raises(self) -> None:
        with pytest.raises(ValueError):
            HookMatcher(event="definitely_not_an_event")

    def test_any_matches_every_context_for_event(self) -> None:
        m = HookMatcher.any(HookEvent.PRE_TOOL_USE)
        ctx = HookContext(event=HookEvent.PRE_TOOL_USE, tool_name="anything")
        assert m.matches(ctx)

    def test_event_must_equal_context_event(self) -> None:
        m = HookMatcher.any(HookEvent.PRE_TOOL_USE)
        ctx = HookContext(event=HookEvent.POST_TOOL_USE, tool_name="x")
        assert not m.matches(ctx)

    def test_tool_name_regex_fullmatch(self) -> None:
        m = HookMatcher(event=HookEvent.PRE_TOOL_USE, tool_name="edit_.*")
        assert m.matches(HookContext(event=HookEvent.PRE_TOOL_USE, tool_name="edit_file"))
        assert not m.matches(HookContext(event=HookEvent.PRE_TOOL_USE, tool_name="my_edit_file"))

    def test_args_glob(self) -> None:
        m = HookMatcher(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="edit_file",
            args={"file_path": "*.py"},
        )
        assert m.matches(
            HookContext(
                event=HookEvent.PRE_TOOL_USE,
                tool_name="edit_file",
                tool_input={"file_path": "foo.py"},
            )
        )
        assert not m.matches(
            HookContext(
                event=HookEvent.PRE_TOOL_USE,
                tool_name="edit_file",
                tool_input={"file_path": "foo.md"},
            )
        )

    def test_predicate_failure_is_isolated(self) -> None:
        def boom(ctx: HookContext) -> bool:
            raise RuntimeError("bad predicate")

        m = HookMatcher(event=HookEvent.PRE_TOOL_USE, predicate=boom)
        ctx = HookContext(event=HookEvent.PRE_TOOL_USE, tool_name="x")
        # Predicate error should be caught and return False rather than bubble.
        assert not m.matches(ctx)


# ======================================================================
# HookRegistry dispatch
# ======================================================================


class TestHookRegistryDispatch:
    def test_empty_registry_allows(self) -> None:
        reg = HookRegistry()
        ctx = HookContext(event=HookEvent.PRE_TOOL_USE)
        decision = _run(reg.dispatch(ctx))
        assert decision.is_allow

    def test_deny_is_terminal(self) -> None:
        reg = HookRegistry()
        reg.on(HookEvent.PRE_TOOL_USE, lambda c: HookDecision.deny("nope"))
        reg.on(
            HookEvent.PRE_TOOL_USE,
            lambda c: pytest.fail("second hook should not run after terminal"),
        )
        decision = _run(reg.dispatch(HookContext(event=HookEvent.PRE_TOOL_USE)))
        assert decision.action == HookAction.DENY
        assert decision.reason == "nope"

    def test_modify_continues_chain_with_rewritten_args(self) -> None:
        reg = HookRegistry()
        reg.on(
            HookEvent.PRE_TOOL_USE,
            lambda c: HookDecision.modify({"command": "echo safe"}),
        )
        seen: dict[str, Any] = {}
        reg.on(
            HookEvent.PRE_TOOL_USE,
            lambda c: seen.setdefault("cmd", (c.tool_input or {}).get("command"))
            or HookDecision.allow(),
        )
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="bash",
            tool_input={"command": "echo unsafe"},
        )
        _run(reg.dispatch(ctx))
        assert seen["cmd"] == "echo safe"
        assert ctx.tool_input == {"command": "echo safe"}

    def test_inject_is_collected_as_side_effect(self) -> None:
        reg = HookRegistry()
        reg.on(HookEvent.POST_TOOL_USE, lambda c: HookDecision.inject("a"))
        reg.on(HookEvent.POST_TOOL_USE, lambda c: HookDecision.inject("b"))
        reg.on(HookEvent.POST_TOOL_USE, lambda c: HookDecision.allow())
        ctx = HookContext(event=HookEvent.POST_TOOL_USE, tool_name="edit_file")
        decision = _run(reg.dispatch(ctx))
        assert decision.is_allow
        assert decision.metadata["pending_injects"] == ["a", "b"]

    def test_async_hook(self) -> None:
        reg = HookRegistry()

        async def handler(ctx: HookContext) -> HookDecision:
            await asyncio.sleep(0)
            return HookDecision.deny("async-block")

        reg.on(HookEvent.PRE_TOOL_USE, handler)
        decision = _run(reg.dispatch(HookContext(event=HookEvent.PRE_TOOL_USE)))
        assert decision.action == HookAction.DENY

    def test_hook_exception_becomes_deny(self) -> None:
        reg = HookRegistry()

        def raiser(ctx: HookContext) -> HookDecision:
            raise RuntimeError("boom")

        reg.on(HookEvent.PRE_TOOL_USE, raiser)
        decision = _run(reg.dispatch(HookContext(event=HookEvent.PRE_TOOL_USE)))
        assert decision.action == HookAction.DENY
        assert "boom" in decision.reason

    def test_hook_returning_non_decision_is_deny(self) -> None:
        reg = HookRegistry()
        reg.on(HookEvent.PRE_TOOL_USE, lambda c: "oops")  # type: ignore[return-value]
        decision = _run(reg.dispatch(HookContext(event=HookEvent.PRE_TOOL_USE)))
        assert decision.action == HookAction.DENY

    def test_hook_returning_none_is_allow(self) -> None:
        reg = HookRegistry()
        reg.on(HookEvent.PRE_TOOL_USE, lambda c: None)
        decision = _run(reg.dispatch(HookContext(event=HookEvent.PRE_TOOL_USE)))
        assert decision.is_allow

    def test_matcher_mismatch_skips_hook(self) -> None:
        reg = HookRegistry()
        reg.on(
            HookEvent.PRE_TOOL_USE,
            lambda c: HookDecision.deny("should not fire"),
            match=HookMatcher.for_tool(HookEvent.PRE_TOOL_USE, "edit_file"),
        )
        decision = _run(
            reg.dispatch(HookContext(event=HookEvent.PRE_TOOL_USE, tool_name="bash"))
        )
        assert decision.is_allow


# ======================================================================
# HookRegistry registration
# ======================================================================


class TestHookRegistryRegistration:
    def test_chainable(self) -> None:
        reg = (
            HookRegistry()
            .on(HookEvent.PRE_TOOL_USE, lambda c: HookDecision.allow())
            .on(HookEvent.POST_TOOL_USE, lambda c: HookDecision.allow())
        )
        assert set(reg.registered_events) == {
            HookEvent.PRE_TOOL_USE,
            HookEvent.POST_TOOL_USE,
        }

    def test_on_rejects_mismatched_matcher_event(self) -> None:
        reg = HookRegistry()
        with pytest.raises(ValueError):
            reg.on(
                HookEvent.PRE_TOOL_USE,
                lambda c: HookDecision.allow(),
                match=HookMatcher.any(HookEvent.POST_TOOL_USE),
            )

    def test_shell_entry_is_registered(self) -> None:
        reg = HookRegistry(workspace="/tmp")
        reg.shell(HookEvent.POST_TOOL_USE, "echo {tool_name}")
        entries = reg.entries_for(HookEvent.POST_TOOL_USE)
        assert len(entries) == 1
        assert isinstance(entries[0], HookEntry)
        assert entries[0].command == "echo {tool_name}"
        assert entries[0].fn is None

    def test_shell_rejects_mismatched_matcher_event(self) -> None:
        reg = HookRegistry()
        with pytest.raises(ValueError):
            reg.shell(
                HookEvent.PRE_TOOL_USE,
                "echo hi",
                match=HookMatcher.any(HookEvent.POST_TOOL_USE),
            )

    def test_merge_combines_entries(self) -> None:
        a = HookRegistry().on(HookEvent.PRE_TOOL_USE, lambda c: HookDecision.allow())
        b = HookRegistry().on(HookEvent.POST_TOOL_USE, lambda c: HookDecision.allow())
        c = HookRegistry().on(HookEvent.PRE_TOOL_USE, lambda c: HookDecision.allow())
        merged = a.merge(b).merge(c)
        assert len(merged.entries_for(HookEvent.PRE_TOOL_USE)) == 2
        assert len(merged.entries_for(HookEvent.POST_TOOL_USE)) == 1

    def test_merge_preserves_workspace(self) -> None:
        a = HookRegistry(workspace="/tmp")
        b = HookRegistry()
        assert a.merge(b).workspace == "/tmp"
        assert b.merge(a).workspace == "/tmp"

    def test_as_plugin_returns_hook_plugin(self) -> None:
        from google.adk.plugins.base_plugin import BasePlugin

        plugin = HookRegistry().as_plugin()
        assert isinstance(plugin, BasePlugin)
        assert isinstance(plugin, HookPlugin)

    def test_repr_summarizes_counts(self) -> None:
        reg = HookRegistry().on(HookEvent.PRE_TOOL_USE, lambda c: HookDecision.allow())
        text = repr(reg)
        assert "HookRegistry" in text
        assert HookEvent.PRE_TOOL_USE in text


# ======================================================================
# Shell hook rendering
# ======================================================================


class TestShellHooks:
    def test_blocking_shell_hook_executes(self) -> None:
        """Verify blocking shell hooks run by writing to a sentinel file."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            sentinel = os.path.join(tmp, "touched")
            reg = HookRegistry(workspace=tmp)
            reg.shell(HookEvent.POST_TOOL_USE, f"touch {sentinel}", blocking=True)
            _run(
                reg.dispatch(
                    HookContext(event=HookEvent.POST_TOOL_USE, tool_name="bash")
                )
            )
            assert os.path.exists(sentinel)

    def test_shell_hook_returns_allow_decision(self) -> None:
        """Shell hooks are notification-only — dispatch always resolves to allow."""
        reg = HookRegistry()
        reg.shell(HookEvent.POST_TOOL_USE, "true", blocking=True)
        decision = _run(
            reg.dispatch(HookContext(event=HookEvent.POST_TOOL_USE, tool_name="x"))
        )
        assert decision.is_allow

    def test_placeholder_substitution_shell_quotes(self) -> None:
        """Ensures {tool_input[...]} substitutes and values are shell-quoted.

        We use a blocking hook writing into a temp file to verify the rendered
        command actually saw the substituted value. This exercises both the
        ``{tool_input[...]}`` branch and the shlex.quote wrapping.
        """
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.txt")
            reg = HookRegistry(workspace=tmp)
            reg.shell(
                HookEvent.POST_TOOL_USE,
                f"printf %s {{tool_input[file_path]}} > {out}",
                blocking=True,
            )
            ctx = HookContext(
                event=HookEvent.POST_TOOL_USE,
                tool_name="edit_file",
                tool_input={"file_path": "hello world.py"},
            )
            _run(reg.dispatch(ctx))
            with open(out) as f:
                assert f.read() == "hello world.py"


# ======================================================================
# SystemMessageChannel
# ======================================================================


class TestSystemMessageChannel:
    def test_append_creates_bucket(self) -> None:
        state: dict[str, Any] = {}
        ch = SystemMessageChannel(state)
        ch.append("hello")
        assert state[SYSTEM_MESSAGE_STATE_KEY] == ["hello"]

    def test_drain_clears_bucket(self) -> None:
        state: dict[str, Any] = {}
        ch = SystemMessageChannel(state)
        ch.append("a")
        ch.append("b")
        drained = ch.drain()
        assert drained == ["a", "b"]
        assert ch.peek() == []
        assert ch.pending_count == 0

    def test_empty_drain_is_noop(self) -> None:
        ch = SystemMessageChannel({})
        assert ch.drain() == []

    def test_none_state_is_silent(self) -> None:
        ch = SystemMessageChannel(None)
        ch.append("ignored")  # must not raise
        assert ch.drain() == []

    def test_append_skips_empty_messages(self) -> None:
        state: dict[str, Any] = {}
        ch = SystemMessageChannel(state)
        ch.append("")
        assert SYSTEM_MESSAGE_STATE_KEY not in state


# ======================================================================
# HookPlugin decision translators
# ======================================================================


class TestHookPluginTranslators:
    def test_tool_decision_allow_returns_none(self) -> None:
        from adk_fluent._hooks._plugin import _tool_decision_to_adk

        assert _tool_decision_to_adk(HookDecision.allow()) is None

    def test_tool_decision_deny_returns_error_dict(self) -> None:
        from adk_fluent._hooks._plugin import _tool_decision_to_adk

        result = _tool_decision_to_adk(HookDecision.deny("nope"))
        assert isinstance(result, dict)
        assert result["error"] == "nope"

    def test_tool_decision_replace_with_dict(self) -> None:
        from adk_fluent._hooks._plugin import _tool_decision_to_adk

        result = _tool_decision_to_adk(HookDecision.replace({"stdout": "stub"}))
        assert result == {"stdout": "stub"}

    def test_tool_decision_replace_with_scalar(self) -> None:
        from adk_fluent._hooks._plugin import _tool_decision_to_adk

        result = _tool_decision_to_adk(HookDecision.replace("raw"))
        assert result == {"result": "raw"}

    def test_tool_decision_ask_raises_hookask(self) -> None:
        from adk_fluent._hooks._plugin import _tool_decision_to_adk

        with pytest.raises(HookAsk):
            _tool_decision_to_adk(HookDecision.ask("proceed?"))

    def test_model_decision_deny_returns_llm_response(self) -> None:
        from google.adk.models.llm_response import LlmResponse

        from adk_fluent._hooks._plugin import _model_decision_to_adk

        result = _model_decision_to_adk(HookDecision.deny("bad model"))
        assert isinstance(result, LlmResponse)
        assert result.error_message == "bad model"

    def test_content_decision_deny_returns_content(self) -> None:
        from google.genai import types as genai_types

        from adk_fluent._hooks._plugin import _content_decision_to_adk

        result = _content_decision_to_adk(HookDecision.deny("no"))
        assert isinstance(result, genai_types.Content)
        assert result.parts[0].text == "no"


# ======================================================================
# H namespace factory helpers
# ======================================================================


class TestHNamespace:
    def test_h_hooks_returns_registry(self) -> None:
        reg = H.hooks("/tmp/project")
        assert isinstance(reg, HookRegistry)
        assert reg.workspace == "/tmp/project"

    def test_h_hooks_accepts_none_workspace(self) -> None:
        reg = H.hooks()
        assert isinstance(reg, HookRegistry)
        assert reg.workspace is None

    def test_h_hook_decision_returns_class(self) -> None:
        assert H.hook_decision() is HookDecision

    def test_h_hook_match_builds_matcher(self) -> None:
        m = H.hook_match(HookEvent.PRE_TOOL_USE, "edit_file", file_path="*.py")
        assert isinstance(m, HookMatcher)
        assert m.event == HookEvent.PRE_TOOL_USE
        assert m.tool_name == "edit_file"
        assert m.args == {"file_path": "*.py"}

    def test_h_hook_match_without_tool_name(self) -> None:
        m = H.hook_match(HookEvent.USER_PROMPT_SUBMIT)
        assert isinstance(m, HookMatcher)
        assert m.tool_name is None
