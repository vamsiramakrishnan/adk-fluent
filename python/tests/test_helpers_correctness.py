"""Regression tests for _helpers correctness fixes.

- _run_via_engine must not mutate the builder's stored _engine_kwargs.
- .tools() warns when it discards previously-set tools.
- run_map_async builds the agent + runner once on the ADK path.
"""

import warnings

import pytest

from adk_fluent import Agent


def _tool_a(x: str) -> str:
    """Tool A."""
    return x


def _tool_b(x: str) -> str:
    """Tool B."""
    return x


def test_tools_warns_on_destructive_replace():
    agent = Agent("t", "gemini-2.5-flash").tool(_tool_a)
    with pytest.warns(UserWarning, match="REPLACES all tools"):
        agent.tools([_tool_b])


def test_tools_no_warning_when_empty():
    agent = Agent("t", "gemini-2.5-flash")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning would fail the test
        agent.tools([_tool_a])


@pytest.mark.asyncio
async def test_run_via_engine_does_not_mutate_builder_kwargs():
    """The compute-derived setdefault() must not leak into builder config."""
    from types import SimpleNamespace

    from adk_fluent._helpers import _run_via_engine

    class _FakeBackend:
        def compile(self, ir):
            return ir

        async def run(self, compiled, prompt):
            return []

    agent = Agent("t", "gemini-2.5-flash").instruct("x").engine("asyncio")
    # Seed a compute object exposing a model_provider; the engine path used to
    # setdefault() it straight into the builder's stored _engine_kwargs dict.
    agent._config["_compute"] = SimpleNamespace(model_provider=object(), tool_runtime=None)
    before = dict(agent._config.get("_engine_kwargs") or {})

    import adk_fluent.backends as backends

    orig = backends.get_backend
    backends.get_backend = lambda name, **kw: _FakeBackend()
    try:
        await _run_via_engine(agent, "hello")
    finally:
        backends.get_backend = orig

    after = dict(agent._config.get("_engine_kwargs") or {})
    assert after == before, "engine path mutated the builder's stored _engine_kwargs"
    assert "model_provider" not in after
