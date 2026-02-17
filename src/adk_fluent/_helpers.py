"""Runtime helpers for adk-fluent ergonomic features. Hand-written, not generated."""
from __future__ import annotations
import asyncio
import copy
import re as _re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

def deep_clone_builder(builder: Any, new_name: str) -> Any:
    """Deep-copy a builder's internal state and set a new name."""
    new_builder = object.__new__(type(builder))
    new_builder._config = copy.deepcopy(builder._config)
    new_builder._callbacks = copy.deepcopy(builder._callbacks)
    new_builder._lists = copy.deepcopy(builder._lists)
    new_builder._config["name"] = new_name
    return new_builder


async def run_one_shot_async(builder, prompt: str) -> str:
    """Execute a builder as a one-shot agent and return the text response."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = builder.build()
    app_name = f"_ask_{agent.name}"
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="_ask_user"
    )
    content = types.Content(
        role="user", parts=[types.Part(text=prompt)]
    )

    last_text = ""
    async for event in runner.run_async(
        user_id="_ask_user", session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    last_text = part.text

    return last_text


def run_one_shot(builder, prompt: str) -> str:
    """Synchronous wrapper around run_one_shot_async."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, run_one_shot_async(builder, prompt)).result()
    else:
        return asyncio.run(run_one_shot_async(builder, prompt))


async def run_stream(builder, prompt: str):
    """Stream text chunks from a one-shot agent execution."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = builder.build()
    app_name = f"_stream_{agent.name}"
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="_stream_user"
    )
    content = types.Content(
        role="user", parts=[types.Part(text=prompt)]
    )

    async for event in runner.run_async(
        user_id="_stream_user", session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    yield part.text


def run_inline_test(builder, prompt: str, *, contains=None, matches=None, equals=None):
    """Run a smoke test against this agent configuration.

    Calls .ask() internally, asserts output matches condition.
    Returns the builder for chaining.
    """
    response = run_one_shot(builder, prompt)

    if contains is not None and contains not in response:
        raise AssertionError(
            f"Agent '{builder._config.get('name', '?')}' test failed:\n"
            f"  prompt:   {prompt!r}\n"
            f"  expected: contains {contains!r}\n"
            f"  got:      {response!r}"
        )
    if matches is not None and not _re.search(matches, response):
        raise AssertionError(
            f"Agent '{builder._config.get('name', '?')}' test failed:\n"
            f"  prompt:   {prompt!r}\n"
            f"  expected: matches {matches!r}\n"
            f"  got:      {response!r}"
        )
    if equals is not None and response.strip() != equals.strip():
        raise AssertionError(
            f"Agent '{builder._config.get('name', '?')}' test failed:\n"
            f"  prompt:   {prompt!r}\n"
            f"  expected: {equals!r}\n"
            f"  got:      {response!r}"
        )

    return builder


class ChatSession:
    """Interactive chat session wrapping ADK Runner + Session."""

    def __init__(self, runner, session, user_id: str):
        self._runner = runner
        self._session = session
        self._user_id = user_id

    async def send(self, text: str) -> str:
        """Send a message and return the response text."""
        from google.genai import types

        content = types.Content(
            role="user", parts=[types.Part(text=text)]
        )
        last_text = ""
        async for event in self._runner.run_async(
            user_id=self._user_id,
            session_id=self._session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        last_text = part.text
        return last_text


@asynccontextmanager
async def create_session(builder):
    """Create an interactive session context manager."""
    from google.adk.runners import InMemoryRunner

    agent = builder.build()
    app_name = f"_session_{agent.name}"
    user_id = "_session_user"
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id=user_id
    )

    try:
        yield ChatSession(runner, session, user_id)
    finally:
        pass  # InMemoryRunner has no cleanup needed
