"""Tests for CAPABILITY #9 — the shipped human-in-the-loop approval UX.

Exercises :class:`InteractiveApprovalHandler` (returned by ``UI.approval``)
through the real :class:`PermissionPlugin` ask path. No real human / stdin is
used: every test injects a fake responder.

Covers:

- responder returns True  → tool allowed (plugin returns ``None``)
- responder returns False → tool denied (plugin returns an error dict)
- the rendered confirm surface / request message names the tool
- an ``always`` verdict is remembered in ``ApprovalMemory`` so the second
  ask for the same tool never invokes the responder
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from adk_fluent import UI
from adk_fluent._permissions import (
    ApprovalMemory,
    ApprovalRequest,
    ApprovalVerdict,
    InteractiveApprovalHandler,
    PermissionPlugin,
    PermissionPolicy,
)


def _fake_tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _ask_bash_policy() -> PermissionPolicy:
    """A policy that returns ``ask`` for bash (default mode asks for unknowns)."""
    return PermissionPolicy(ask=frozenset({"bash"}))


def _run(plugin: PermissionPlugin, tool_name: str, args: dict):
    return asyncio.run(
        plugin.before_tool_callback(
            tool=_fake_tool(tool_name),
            tool_args=args,
            tool_context=None,
        )
    )


# ======================================================================
# UI.approval factory
# ======================================================================


class TestApprovalFactory:
    def test_returns_interactive_handler(self):
        handler = UI.approval(responder=lambda req: True)
        assert isinstance(handler, InteractiveApprovalHandler)

    def test_handler_is_callable_with_permission_signature(self):
        handler = UI.approval(responder=lambda req: True)
        from adk_fluent._permissions import PermissionDecision

        assert handler("bash", {"cmd": "ls"}, PermissionDecision.ask("Allow?")) is True


# ======================================================================
# End-to-end through the PermissionPlugin ask path
# ======================================================================


class TestPluginAskPath:
    def test_responder_true_allows(self):
        handler = UI.approval(responder=lambda req: True)
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler)
        assert _run(plugin, "bash", {"cmd": "ls"}) is None

    def test_responder_false_denies(self):
        handler = UI.approval(responder=lambda req: False)
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler)
        result = _run(plugin, "bash", {"cmd": "rm -rf /"})
        assert isinstance(result, dict) and "error" in result

    def test_verdict_allow_string_allows(self):
        handler = UI.approval(responder=lambda req: ApprovalVerdict.ALLOW)
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler)
        assert _run(plugin, "bash", {"cmd": "ls"}) is None

    def test_verdict_deny_string_denies(self):
        handler = UI.approval(responder=lambda req: ApprovalVerdict.DENY)
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler)
        result = _run(plugin, "bash", {})
        assert isinstance(result, dict) and "error" in result


# ======================================================================
# Confirm surface / request rendering
# ======================================================================


class TestSurfaceRendering:
    def test_request_message_names_tool(self):
        captured: list[ApprovalRequest] = []

        def responder(req: ApprovalRequest) -> bool:
            captured.append(req)
            return True

        handler = UI.approval(responder=responder)
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler)
        _run(plugin, "bash", {"cmd": "ls"})

        assert len(captured) == 1
        req = captured[0]
        assert "bash" in req.prompt
        assert req.tool_name == "bash"

    def test_confirm_surface_text_includes_tool(self):
        captured: list[ApprovalRequest] = []

        def responder(req: ApprovalRequest) -> bool:
            captured.append(req)
            return True

        handler = UI.approval(responder=responder)
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler)
        _run(plugin, "bash", {"cmd": "ls"})

        surface = captured[0].surface
        # confirm() builds Column(Text(message), Row(buttons))
        text_props = dict(surface.root._children[0]._props)
        assert "bash" in text_props["text"]

    def test_policy_prompt_is_used_when_present(self):
        captured: list[ApprovalRequest] = []

        def responder(req: ApprovalRequest) -> bool:
            captured.append(req)
            return True

        # PermissionPolicy with a custom ask prompt for bash.
        class PromptPolicy(PermissionPolicy):
            def check(self, tool_name, tool_input=None):  # type: ignore[override]
                from adk_fluent._permissions import PermissionDecision

                return PermissionDecision.ask("Custom: run bash now?")

        handler = UI.approval(responder=responder)
        plugin = PermissionPlugin(PromptPolicy(), handler=handler)
        _run(plugin, "bash", {"cmd": "ls"})
        assert captured[0].prompt == "Custom: run bash now?"


# ======================================================================
# ApprovalMemory — "always allow this tool"
# ======================================================================


class TestApprovalMemory:
    def test_always_short_circuits_second_call(self):
        calls: list[str] = []

        def responder(req: ApprovalRequest) -> str:
            calls.append(req.tool_name)
            return ApprovalVerdict.ALWAYS

        mem = ApprovalMemory()
        handler = UI.approval(responder=responder, memory=mem)
        # Same memory wired into the plugin so its pre-handler recall wins.
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler, memory=mem)

        # First call: responder consulted, verdict ALWAYS remembered.
        assert _run(plugin, "bash", {"cmd": "ls"}) is None
        assert calls == ["bash"]
        assert mem.recall("bash") is True

        # Second call: tool-level memory short-circuits before the handler.
        assert _run(plugin, "bash", {"cmd": "whoami"}) is None
        assert calls == ["bash"]  # responder NOT invoked again

    def test_never_remembers_denial(self):
        calls: list[str] = []

        def responder(req: ApprovalRequest) -> str:
            calls.append(req.tool_name)
            return ApprovalVerdict.NEVER

        mem = ApprovalMemory()
        handler = UI.approval(responder=responder, memory=mem)
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler, memory=mem)

        result = _run(plugin, "bash", {"cmd": "ls"})
        assert isinstance(result, dict) and "error" in result
        assert mem.recall("bash") is False

        # Second call short-circuits to deny, responder not re-invoked.
        result2 = _run(plugin, "bash", {"cmd": "whoami"})
        assert isinstance(result2, dict) and "error" in result2
        assert calls == ["bash"]

    def test_one_shot_allow_not_remembered(self):
        calls: list[str] = []

        def responder(req: ApprovalRequest) -> str:
            calls.append(req.tool_name)
            return ApprovalVerdict.ALLOW

        mem = ApprovalMemory()
        handler = UI.approval(responder=responder, memory=mem)
        plugin = PermissionPlugin(_ask_bash_policy(), handler=handler, memory=mem)

        _run(plugin, "bash", {"cmd": "ls"})
        # ALLOW is one-shot: no tool-level memory, but the plugin records the
        # specific tool+args decision. A different args set is asked again.
        assert mem.recall("bash") is None
        _run(plugin, "bash", {"cmd": "whoami"})
        assert calls == ["bash", "bash"]


# ======================================================================
# Verdict validation
# ======================================================================


class TestVerdictValidation:
    def test_unknown_string_verdict_raises(self):
        handler = UI.approval(responder=lambda req: "maybe")
        from adk_fluent._permissions import PermissionDecision

        with pytest.raises(ValueError):
            handler("bash", {}, PermissionDecision.ask())

    def test_bad_type_verdict_raises(self):
        handler = UI.approval(responder=lambda req: 123)
        from adk_fluent._permissions import PermissionDecision

        with pytest.raises(TypeError):
            handler("bash", {}, PermissionDecision.ask())
