"""Tests for the Middleware protocol and _MiddlewarePlugin adapter."""

import asyncio

from adk_fluent.middleware import Middleware, _MiddlewarePlugin

# --- Protocol tests ---


def test_middleware_is_runtime_checkable():
    class Conforming:
        pass

    class HasBeforeModel:
        async def before_model(self, ctx, request):
            return None

    assert isinstance(Conforming(), Middleware)
    assert isinstance(HasBeforeModel(), Middleware)


def test_middleware_protocol_has_expected_methods():
    members = [m for m in dir(Middleware) if not m.startswith("_")]
    expected = {
        "on_user_message",
        "before_run",
        "after_run",
        "on_event",
        "before_agent",
        "after_agent",
        "before_model",
        "after_model",
        "on_model_error",
        "before_tool",
        "after_tool",
        "on_tool_error",
        "close",
    }
    assert expected.issubset(set(members))


# --- _MiddlewarePlugin adapter tests ---


def test_middleware_plugin_is_base_plugin():
    from google.adk.plugins.base_plugin import BasePlugin

    plugin = _MiddlewarePlugin(name="test", stack=[])
    assert isinstance(plugin, BasePlugin)


def test_middleware_plugin_runs_stack_in_order():
    call_log = []

    class MW1:
        async def before_model(self, ctx, request):
            call_log.append("mw1")
            return None

    class MW2:
        async def before_model(self, ctx, request):
            call_log.append("mw2")
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[MW1(), MW2()])

    async def run():
        return await plugin.before_model_callback(callback_context=None, llm_request=None)

    result = asyncio.run(run())
    assert call_log == ["mw1", "mw2"]
    assert result is None


def test_middleware_plugin_short_circuits_on_non_none():
    call_log = []

    class MW1:
        async def before_model(self, ctx, request):
            call_log.append("mw1")
            return "intercepted"

    class MW2:
        async def before_model(self, ctx, request):
            call_log.append("mw2")
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[MW1(), MW2()])

    async def run():
        return await plugin.before_model_callback(callback_context=None, llm_request=None)

    result = asyncio.run(run())
    assert call_log == ["mw1"]
    assert result == "intercepted"


def test_middleware_plugin_skips_unimplemented_hooks():
    class OnlyBeforeModel:
        async def before_model(self, ctx, request):
            return "result"

    plugin = _MiddlewarePlugin(name="test", stack=[OnlyBeforeModel()])

    async def run():
        return await plugin.after_model_callback(callback_context=None, llm_response=None)

    result = asyncio.run(run())
    assert result is None


def test_middleware_plugin_before_agent_passes_agent_name():
    captured = {}

    class NameCapture:
        async def before_agent(self, ctx, agent_name):
            captured["name"] = agent_name
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[NameCapture()])

    class FakeAgent:
        name = "my_agent"

    async def run():
        return await plugin.before_agent_callback(agent=FakeAgent(), callback_context=None)

    asyncio.run(run())
    assert captured["name"] == "my_agent"


def test_middleware_plugin_before_tool_passes_tool_name():
    captured = {}

    class ToolCapture:
        async def before_tool(self, ctx, tool_name, args):
            captured["name"] = tool_name
            captured["args"] = args
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[ToolCapture()])

    class FakeTool:
        name = "search"

    async def run():
        return await plugin.before_tool_callback(tool=FakeTool(), tool_args={"q": "hello"}, tool_context=None)

    asyncio.run(run())
    assert captured["name"] == "search"
    assert captured["args"] == {"q": "hello"}


def test_middleware_plugin_on_model_error_passes_error():
    captured = {}

    class ErrorCapture:
        async def on_model_error(self, ctx, request, error):
            captured["error"] = error
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[ErrorCapture()])
    err = ValueError("test error")

    async def run():
        return await plugin.on_model_error_callback(callback_context=None, llm_request=None, error=err)

    asyncio.run(run())
    assert captured["error"] is err


def test_middleware_plugin_close_calls_all():
    closed = []

    class MW1:
        async def close(self):
            closed.append("mw1")

    class MW2:
        async def close(self):
            closed.append("mw2")

    plugin = _MiddlewarePlugin(name="test", stack=[MW1(), MW2()])
    asyncio.run(plugin.close())
    assert closed == ["mw1", "mw2"]
