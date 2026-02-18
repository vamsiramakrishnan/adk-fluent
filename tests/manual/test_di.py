"""Tests for Resource DI (dependency injection)."""

import asyncio
import inspect


def test_inject_resources_hides_params():
    """_inject_resources removes resource params from __signature__."""
    from adk_fluent.di import inject_resources

    def greet(name: str, db: object) -> str:
        return f"Hello {name}, db={db}"

    wrapped = inject_resources(greet, {"db": "fake_db"})
    sig = inspect.signature(wrapped)
    assert "name" in sig.parameters
    assert "db" not in sig.parameters


def test_inject_resources_provides_values():
    """Injected resources are provided at call time."""
    from adk_fluent.di import inject_resources

    def greet(name: str, db: object) -> str:
        return f"Hello {name}, db={db}"

    wrapped = inject_resources(greet, {"db": "fake_db"})
    result = asyncio.run(wrapped(name="World"))
    assert result == "Hello World, db=fake_db"


def test_inject_resources_async_fn():
    """Works with async functions."""
    from adk_fluent.di import inject_resources

    async def greet(name: str, db: object) -> str:
        return f"Hello {name}, db={db}"

    wrapped = inject_resources(greet, {"db": "fake_db"})
    result = asyncio.run(wrapped(name="World"))
    assert result == "Hello World, db=fake_db"


def test_inject_preserves_tool_context():
    """tool_context param is never injected even if in resources."""
    from adk_fluent.di import inject_resources

    def tool_fn(query: str, tool_context: object) -> str:
        return "ok"

    wrapped = inject_resources(tool_fn, {"tool_context": "bad"})
    sig = inspect.signature(wrapped)
    assert "tool_context" in sig.parameters


def test_inject_no_overlap_passthrough():
    """If no params match resources, return unchanged."""
    from adk_fluent.di import inject_resources

    def greet(name: str) -> str:
        return f"Hello {name}"

    wrapped = inject_resources(greet, {"db": "fake"})
    # Should return the original function unchanged
    assert wrapped is greet


def test_builder_inject_method():
    """Agent.inject(key=value) stores resources for DI."""
    from adk_fluent import Agent

    a = Agent("a").inject(db="fake_db")
    assert a._config["_resources"] == {"db": "fake_db"}


def test_builder_inject_chainable():
    """inject() returns self."""
    from adk_fluent import Agent

    a = Agent("a")
    result = a.inject(db="fake")
    assert result is a


def test_builder_inject_accumulates():
    """Multiple inject() calls merge resources."""
    from adk_fluent import Agent

    a = Agent("a").inject(db="fake").inject(cache="mem")
    assert a._config["_resources"] == {"db": "fake", "cache": "mem"}
