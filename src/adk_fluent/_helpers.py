"""Runtime helpers for adk-fluent ergonomic features. Hand-written, not generated."""
from __future__ import annotations
import asyncio
import copy
import re as _re
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

__all__ = [
    "deep_clone_builder",
    "run_one_shot",
    "run_one_shot_async",
    "run_stream",
    "run_inline_test",
    "ChatSession",
    "create_session",
    "run_map",
    "run_map_async",
]

def _debug_log(agent_name: str, msg: str):
    """Emit a debug trace line to stderr."""
    print(f"[{agent_name}] {msg}", file=sys.stderr)


def deep_clone_builder(builder: Any, new_name: str) -> Any:
    """Deep-copy a builder's internal state and set a new name."""
    new_builder = object.__new__(type(builder))
    new_builder._config = copy.deepcopy(builder._config)
    new_builder._callbacks = copy.deepcopy(builder._callbacks)
    new_builder._lists = copy.deepcopy(builder._lists)
    new_builder._config["name"] = new_name
    return new_builder


async def _run_single_attempt(builder, prompt: str, *, model_override: str | None = None) -> str:
    """Core execution: build agent, send prompt, return raw text."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    debug = builder._config.get("_debug", False)
    agent_name = builder._config.get("name", "?")

    if model_override:
        # Temporarily override model for fallback
        original_model = builder._config.get("model")
        builder._config["model"] = model_override
        if debug:
            _debug_log(agent_name, f"Trying fallback model: {model_override}")

    try:
        agent = builder.build()
        app_name = f"_ask_{agent.name}"
        runner = InMemoryRunner(agent=agent, app_name=app_name)
        session = await runner.session_service.create_session(
            app_name=app_name, user_id="_ask_user"
        )
        content = types.Content(
            role="user", parts=[types.Part(text=prompt)]
        )

        if debug:
            _debug_log(agent_name, f"Sending prompt ({len(prompt)} chars)")
            t0 = time.monotonic()

        last_text = ""
        async for event in runner.run_async(
            user_id="_ask_user", session_id=session.id, new_message=content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        last_text = part.text

        if debug:
            elapsed = time.monotonic() - t0
            _debug_log(agent_name, f"Response received ({len(last_text)} chars, {elapsed:.2f}s)")

        return last_text
    finally:
        if model_override:
            # Restore original model
            if original_model is not None:
                builder._config["model"] = original_model
            else:
                builder._config.pop("model", None)


async def run_one_shot_async(builder, prompt: str) -> str:
    """Execute a builder as a one-shot agent and return the text response.

    Supports retry, fallback, structured output, and debug tracing.
    """
    debug = builder._config.get("_debug", False)
    agent_name = builder._config.get("name", "?")
    retry_cfg = builder._config.get("_retry")
    fallbacks = builder._config.get("_fallbacks", [])

    max_attempts = retry_cfg["max_attempts"] if retry_cfg else 1
    backoff = retry_cfg["backoff"] if retry_cfg else 1.0

    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            if debug and attempt > 1:
                _debug_log(agent_name, f"Retry attempt {attempt}/{max_attempts}")
            last_text = await _run_single_attempt(builder, prompt)
            break
        except Exception as exc:
            last_exc = exc
            if debug:
                _debug_log(agent_name, f"Attempt {attempt} failed: {exc}")
            if attempt < max_attempts:
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
    else:
        # All retries exhausted, try fallbacks
        for fb_model in fallbacks:
            try:
                if debug:
                    _debug_log(agent_name, f"Trying fallback model: {fb_model}")
                last_text = await _run_single_attempt(builder, prompt, model_override=fb_model)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if debug:
                    _debug_log(agent_name, f"Fallback {fb_model} failed: {exc}")
        if last_exc is not None:
            raise last_exc

    # Structured output parsing
    schema = builder._config.get("_output_schema")
    if schema is not None:
        import json as _json
        try:
            return schema.model_validate_json(last_text)
        except Exception:
            try:
                data = _json.loads(last_text)
                return schema.model_validate(data)
            except Exception:
                pass

    return last_text


async def run_map_async(builder, prompts, *, concurrency=5):
    """Run agent against multiple prompts concurrently with bounded concurrency."""
    semaphore = asyncio.Semaphore(concurrency)
    async def _one(prompt):
        async with semaphore:
            return await run_one_shot_async(builder, prompt)
    return await asyncio.gather(*[_one(p) for p in prompts])


def run_map(builder, prompts, *, concurrency=5):
    """Synchronous batch execution against multiple prompts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, run_map_async(builder, prompts, concurrency=concurrency)).result()
    else:
        return asyncio.run(run_map_async(builder, prompts, concurrency=concurrency))


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
