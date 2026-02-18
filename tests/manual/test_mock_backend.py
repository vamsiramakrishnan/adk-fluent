"""Tests for mock_backend and AgentHarness."""
import asyncio


def test_mock_backend_satisfies_protocol():
    """MockBackend satisfies the Backend protocol."""
    from adk_fluent.testing import mock_backend
    from adk_fluent.backends import Backend
    mb = mock_backend({"agent_a": "Hello!"})
    assert isinstance(mb, Backend)


def test_mock_backend_compile():
    """MockBackend.compile returns a passable compiled object."""
    from adk_fluent.testing import mock_backend
    from adk_fluent import Agent
    mb = mock_backend({"agent_a": "Hello!"})
    ir = Agent("agent_a").to_ir()
    compiled = mb.compile(ir)
    assert compiled is not None


def test_mock_backend_run():
    """MockBackend.run returns events with canned responses."""
    from adk_fluent.testing import mock_backend
    from adk_fluent import Agent

    async def _run():
        mb = mock_backend({"agent_a": "Hello from mock!"})
        ir = Agent("agent_a").to_ir()
        compiled = mb.compile(ir)
        events = await mb.run(compiled, "test prompt")
        assert any(e.content == "Hello from mock!" for e in events)

    asyncio.run(_run())


def test_mock_backend_run_state_delta():
    """MockBackend supports dict responses for state_delta."""
    from adk_fluent.testing import mock_backend
    from adk_fluent import Agent

    async def _run():
        mb = mock_backend({"agent_a": {"intent": "billing"}})
        ir = Agent("agent_a").to_ir()
        compiled = mb.compile(ir)
        events = await mb.run(compiled, "test")
        assert any(e.state_delta.get("intent") == "billing" for e in events)

    asyncio.run(_run())


def test_mock_backend_unknown_agent():
    """Unknown agents return a generic event."""
    from adk_fluent.testing import mock_backend
    from adk_fluent import Agent

    async def _run():
        mb = mock_backend({"other": "response"})
        ir = Agent("unknown_agent").to_ir()
        compiled = mb.compile(ir)
        events = await mb.run(compiled, "test")
        assert len(events) >= 1

    asyncio.run(_run())


def test_harness_creation():
    """AgentHarness wraps a builder with a mock backend."""
    from adk_fluent.testing import AgentHarness, mock_backend
    from adk_fluent import Agent
    harness = AgentHarness(
        Agent("a").instruct("test"),
        backend=mock_backend({"a": "response"})
    )
    assert harness is not None


def test_harness_send():
    """AgentHarness.send() returns a response object."""
    from adk_fluent.testing import AgentHarness, mock_backend
    from adk_fluent import Agent

    async def _run():
        harness = AgentHarness(
            Agent("a").instruct("test"),
            backend=mock_backend({"a": "Hello!"})
        )
        response = await harness.send("Hi")
        assert response.final_text == "Hello!"
        assert not response.errors

    asyncio.run(_run())
