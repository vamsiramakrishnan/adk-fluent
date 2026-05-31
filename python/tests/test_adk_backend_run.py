"""Tests for :meth:`ADKBackend.run` and :meth:`ADKBackend.stream`.

These drive the primary ``adk`` backend through its unified execution
interface fully offline: the agent's LLM is mocked via the fluent builder's
``.mock([...])``, which injects a ``before_model_callback`` returning a canned
``LlmResponse``. No network or API key is required.
"""

from __future__ import annotations

import pytest

from adk_fluent import Agent
from adk_fluent._ir import AgentEvent
from adk_fluent.backends import final_text
from adk_fluent.backends.adk import ADKBackend


def _compiled(text: str):
    """Compile a mocked single agent through the backend's compile() path."""
    builder = Agent("helper", "gemini-2.5-flash").instruct("Be helpful.").mock([text])
    backend = ADKBackend()
    return backend, backend.compile(builder.to_ir())


@pytest.mark.asyncio
async def test_run_returns_events_with_mocked_text():
    backend, app = _compiled("hello from mock")
    events = await backend.run(app, "say hi")

    assert isinstance(events, list)
    assert events, "run() should return at least one event"
    assert all(isinstance(e, AgentEvent) for e in events)
    assert any(e.content == "hello from mock" for e in events)


@pytest.mark.asyncio
async def test_run_marks_a_final_event():
    backend, app = _compiled("done")
    events = await backend.run(app, "go")

    assert any(e.is_final for e in events)
    assert final_text(events) == "done"


@pytest.mark.asyncio
async def test_stream_yields_mocked_text():
    backend, app = _compiled("streamed reply")
    chunks = [e async for e in backend.stream(app, "go")]

    assert chunks, "stream() should yield at least one event"
    assert all(isinstance(e, AgentEvent) for e in chunks)
    assert any(e.content == "streamed reply" for e in chunks)


@pytest.mark.asyncio
async def test_run_accepts_bare_agent():
    """run() also accepts a bare ADK agent, not only a compiled App."""
    builder = Agent("solo", "gemini-2.5-flash").instruct("Be brief.").mock(["bare ok"])
    backend = ADKBackend()
    raw_agent = builder.build()

    events = await backend.run(raw_agent, "go")
    assert final_text(events) == "bare ok"


@pytest.mark.asyncio
async def test_run_accepts_custom_user_id():
    backend, app = _compiled("hi user")
    events = await backend.run(app, "go", user_id="custom_user")
    assert final_text(events) == "hi user"


@pytest.mark.asyncio
async def test_run_with_injected_session_service():
    from google.adk.sessions import InMemorySessionService

    backend, app = _compiled("injected")
    events = await backend.run(app, "go", session_service=InMemorySessionService())
    assert final_text(events) == "injected"


def test_backend_satisfies_protocol():
    from adk_fluent.backends import Backend

    assert isinstance(ADKBackend(), Backend)
