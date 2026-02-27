"""Issue #10 — .native() escape hatch tests."""

from __future__ import annotations

from adk_fluent import Agent


class TestNativeHook:
    """.native() should register post-build hooks."""

    def test_native_chains(self):
        fn = lambda obj: None
        a = Agent("x").model("gemini-2.0-flash").instruct("hi").native(fn)
        assert "_native_hooks" in a._config
        assert fn in a._config["_native_hooks"]

    def test_build_calls_hook(self):
        called_with = []
        fn = lambda obj: called_with.append(obj)
        agent = Agent("x").model("gemini-2.0-flash").instruct("hi").native(fn).build()
        assert len(called_with) == 1
        assert called_with[0] is agent

    def test_multiple_hooks_chain_in_order(self):
        order = []
        fn1 = lambda obj: order.append("first")
        fn2 = lambda obj: order.append("second")
        Agent("x").model("gemini-2.0-flash").instruct("hi").native(fn1).native(fn2).build()
        assert order == ["first", "second"]

    def test_hook_can_mutate_adk_object(self):
        def set_description(obj):
            obj.description = "mutated"

        agent = Agent("x").model("gemini-2.0-flash").instruct("hi").native(set_description).build()
        assert agent.description == "mutated"
