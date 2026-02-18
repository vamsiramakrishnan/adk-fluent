"""Tests for middleware wiring through ExecutionConfig -> ADKBackend -> App."""
import asyncio
import pytest
from adk_fluent._ir import ExecutionConfig
from adk_fluent._ir_generated import AgentNode
from adk_fluent.backends.adk import ADKBackend
from adk_fluent.middleware import Middleware


def test_execution_config_has_middlewares_field():
    cfg = ExecutionConfig()
    assert cfg.middlewares == ()


def test_execution_config_accepts_middleware_tuple():
    class LogMW:
        pass
    cfg = ExecutionConfig(middlewares=(LogMW(),))
    assert len(cfg.middlewares) == 1


def test_backend_compile_without_middleware():
    backend = ADKBackend()
    node = AgentNode(name="test")
    app = backend.compile(node)
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 0


def test_backend_compile_with_middleware():
    from adk_fluent.middleware import _MiddlewarePlugin
    class LogMW:
        async def before_model(self, ctx, request):
            return None
    backend = ADKBackend()
    node = AgentNode(name="test")
    cfg = ExecutionConfig(middlewares=(LogMW(),))
    app = backend.compile(node, config=cfg)
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
    assert isinstance(plugins[0], _MiddlewarePlugin)


def test_backend_compile_middleware_preserves_stack_order():
    call_log = []
    class MW1:
        async def before_model(self, ctx, request):
            call_log.append("mw1")
            return None
    class MW2:
        async def before_model(self, ctx, request):
            call_log.append("mw2")
            return None
    backend = ADKBackend()
    node = AgentNode(name="test")
    cfg = ExecutionConfig(middlewares=(MW1(), MW2()))
    app = backend.compile(node, config=cfg)
    plugin = app.plugins[0]
    async def run():
        await plugin.before_model_callback(callback_context=None, llm_request=None)
    asyncio.run(run())
    assert call_log == ["mw1", "mw2"]


def test_to_app_with_middleware():
    from adk_fluent import Agent
    from adk_fluent.middleware import _MiddlewarePlugin
    class LogMW:
        async def before_model(self, ctx, request):
            return None
    cfg = ExecutionConfig(middlewares=(LogMW(),))
    app = Agent("test").to_app(config=cfg)
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
    assert isinstance(plugins[0], _MiddlewarePlugin)
