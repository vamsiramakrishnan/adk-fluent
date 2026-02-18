"""Tests for tap read-only state view."""
import types
import pytest
from adk_fluent._base import TapAgent

def test_mapping_proxy_is_immutable():
    """MappingProxyType should raise TypeError on mutation attempts."""
    proxy = types.MappingProxyType({"a": 1, "b": 2})
    with pytest.raises(TypeError):
        proxy["new_key"] = "value"
    with pytest.raises(TypeError):
        del proxy["a"]

def test_tap_agent_exists_at_module_level():
    """TapAgent should be importable from adk_fluent._base."""
    assert TapAgent is not None

def test_tap_builder_produces_tap_agent():
    """tap() builder should produce a TapAgent instance."""
    from adk_fluent import tap
    fn = lambda state: None
    agent = tap(fn).build()
    assert isinstance(agent, TapAgent)


def test_tap_callback_receives_mapping_proxy():
    """TapAgent should pass MappingProxyType to the callback at runtime."""
    import asyncio
    from unittest.mock import MagicMock

    received = {}

    def capture(state):
        received["type"] = type(state)
        received["data"] = dict(state)

    agent = TapAgent(name="test_tap", fn=capture)

    ctx = MagicMock()
    ctx.session.state = {"a": 1, "b": 2}

    async def run():
        result = agent._run_async_impl(ctx)
        # Handle both coroutine and async generator
        if hasattr(result, '__anext__'):
            async for _ in result:
                pass
        else:
            await result

    asyncio.run(run())

    assert received["type"] is types.MappingProxyType
    assert received["data"] == {"a": 1, "b": 2}
