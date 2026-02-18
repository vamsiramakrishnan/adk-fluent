"""Tests for callback composition in build config."""
import pytest
from adk_fluent import Agent


def test_single_callback_passes_through():
    """A single callback should be passed as-is."""
    fn = lambda ctx: None
    a = Agent("test").after_model(fn)
    config = a._prepare_build_config()
    assert config.get("after_model_callback") is fn


def test_multiple_callbacks_composed_into_single():
    """Multiple callbacks should be composed into a single callable."""
    call_log = []
    def fn1(ctx): call_log.append("fn1")
    def fn2(ctx): call_log.append("fn2")

    a = Agent("test").after_model(fn1).after_model(fn2)
    config = a._prepare_build_config()

    cb = config.get("after_model_callback")
    # Must be a single callable, not a list
    assert callable(cb), f"Expected callable, got {type(cb)}"
    assert not isinstance(cb, list), "Should be a single composed callable, not a list"


def test_composed_callbacks_run_in_order():
    """Composed callbacks should execute in registration order."""
    import asyncio
    call_log = []

    async def fn1(*args, **kwargs): call_log.append("fn1")
    async def fn2(*args, **kwargs): call_log.append("fn2")
    async def fn3(*args, **kwargs): call_log.append("fn3")

    a = Agent("test").after_model(fn1).after_model(fn2).after_model(fn3)
    config = a._prepare_build_config()
    cb = config.get("after_model_callback")

    # Run the composed callback
    asyncio.run(cb())
    assert call_log == ["fn1", "fn2", "fn3"]


def test_composed_callback_first_non_none_wins():
    """In composed callbacks, first non-None return value wins."""
    import asyncio

    async def fn1(*args, **kwargs): return None
    async def fn2(*args, **kwargs): return "blocked"
    async def fn3(*args, **kwargs): return "should not reach"

    a = Agent("test").before_model(fn1).before_model(fn2).before_model(fn3)
    config = a._prepare_build_config()
    cb = config.get("before_model_callback")

    result = asyncio.run(cb())
    assert result == "blocked"
