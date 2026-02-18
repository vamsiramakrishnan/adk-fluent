"""Tests for builder .middleware() method."""
import asyncio
import pytest
from adk_fluent import Agent


def test_middleware_method_returns_self():
    class LogMW:
        pass
    a = Agent("test")
    result = a.middleware(LogMW())
    assert result is a


def test_middleware_method_chainable():
    class MW1:
        pass
    class MW2:
        pass
    a = Agent("test").middleware(MW1()).middleware(MW2())
    assert len(a._middlewares) == 2


def test_middleware_flows_through_to_app():
    from adk_fluent.middleware import _MiddlewarePlugin
    class LogMW:
        async def before_model(self, ctx, request):
            return None
    app = Agent("test").middleware(LogMW()).to_app()
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
    assert isinstance(plugins[0], _MiddlewarePlugin)


def test_middleware_with_explicit_config_merges():
    from adk_fluent._ir import ExecutionConfig
    from adk_fluent.middleware import _MiddlewarePlugin
    class MW1:
        async def before_model(self, ctx, request):
            return None
    class MW2:
        async def after_model(self, ctx, response):
            return None
    cfg = ExecutionConfig(middlewares=(MW2(),))
    app = Agent("test").middleware(MW1()).to_app(config=cfg)
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
    assert len(plugins[0]._stack) == 2


def test_pipeline_to_app_with_middleware():
    from adk_fluent.middleware import _MiddlewarePlugin
    class LogMW:
        async def before_model(self, ctx, request):
            return None
    app = (Agent("a").middleware(LogMW()) >> Agent("b")).to_app()
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
