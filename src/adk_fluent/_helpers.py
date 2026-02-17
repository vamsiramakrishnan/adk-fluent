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
    "delegate_agent",
    "run_one_shot",
    "run_one_shot_async",
    "run_stream",
    "run_events",
    "run_inline_test",
    "ChatSession",
    "create_session",
    "run_map",
    "run_map_async",
    "StateKey",
    "Artifact",
]

def delegate_agent(builder, agent):
    """Wrap an agent (or builder) as an AgentTool and add it to the builder's tools list.

    This enables the coordinator pattern: the parent agent's LLM can decide
    to delegate tasks to the wrapped agent via transfer_to_agent.
    """
    from google.adk.tools.agent_tool import AgentTool

    # Auto-build if it's a builder
    built = agent.build() if hasattr(agent, 'build') and hasattr(agent, '_config') else agent
    tool = AgentTool(agent=built)
    builder._lists.setdefault("tools", []).append(tool)
    return builder


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
                raise ValueError(
                    f"Structured output parsing failed for schema "
                    f"{schema.__name__}. The LLM returned text that could "
                    f"not be parsed as the requested type.\n"
                    f"Raw response:\n{last_text}"
                )

    return last_text


async def run_map_async(builder, prompts, *, concurrency=5):
    """Run agent against multiple prompts concurrently with bounded concurrency."""
    semaphore = asyncio.Semaphore(concurrency)
    async def _one(prompt):
        async with semaphore:
            return await run_one_shot_async(builder, prompt)
    return await asyncio.gather(*[_one(p) for p in prompts])


def _run_sync(coro):
    """Run a coroutine synchronously. Raises RuntimeError inside async contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError(
            "Cannot use synchronous methods (.ask(), .map(), run_one_shot(), "
            "run_map()) inside an already-running event loop (e.g. Jupyter, "
            "async frameworks). Use the async variants instead: "
            ".ask_async(), .map_async(), run_one_shot_async(), run_map_async()."
        )
    return asyncio.run(coro)


def run_map(builder, prompts, *, concurrency=5):
    """Synchronous batch execution against multiple prompts.

    Raises RuntimeError if called inside an already-running event loop.
    Use run_map_async() in async contexts.
    """
    return _run_sync(run_map_async(builder, prompts, concurrency=concurrency))


def run_one_shot(builder, prompt: str) -> str:
    """Synchronous wrapper around run_one_shot_async.

    Raises RuntimeError if called inside an already-running event loop.
    Use run_one_shot_async() in async contexts.
    """
    return _run_sync(run_one_shot_async(builder, prompt))


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


# ======================================================================
# StateKey — typed state descriptor
# ======================================================================

class StateKey:
    """Typed state key descriptor for ergonomic state access in callbacks and tools.

    Usage:
        call_count = StateKey("call_count", scope="temp", type=int, default=0)

        # In a callback or tool:
        current = call_count.get(ctx)  # Returns int, not Any
        call_count.set(ctx, current + 1)
        call_count.increment(ctx)  # Convenience for numeric types
    """

    _VALID_SCOPES = frozenset({"temp", "user", "app", "session"})

    def __init__(self, name: str, *, scope: str = "session", type: type = str, default: Any = None):
        if scope not in self._VALID_SCOPES:
            raise ValueError(f"Invalid scope '{scope}'. Must be one of: {', '.join(sorted(self._VALID_SCOPES))}")
        self._name = name
        self._scope = scope
        self._type = type
        self._default = default
        # Build the full key with prefix
        if scope == "session":
            self._full_key = name
        else:
            self._full_key = f"{scope}:{name}"

    @property
    def key(self) -> str:
        """The full state key including scope prefix."""
        return self._full_key

    @property
    def name(self) -> str:
        """The bare name without scope prefix."""
        return self._name

    @property
    def scope(self) -> str:
        """The scope: 'temp', 'user', 'app', or 'session'."""
        return self._scope

    def get(self, ctx) -> Any:
        """Get the value from context state. Returns default if not set.

        Works with CallbackContext, ToolContext, or any object with a .state dict-like attribute.
        """
        state = ctx.state if hasattr(ctx, 'state') else ctx
        if callable(state) and not isinstance(state, dict):
            state = state()  # ReadonlyContext.state() is a method
        return state.get(self._full_key, self._default)

    def set(self, ctx, value: Any) -> None:
        """Set the value in context state.

        Works with CallbackContext, ToolContext, or any object with a .state dict-like attribute.
        """
        state = ctx.state if hasattr(ctx, 'state') else ctx
        if callable(state) and not isinstance(state, dict):
            state = state()
        state[self._full_key] = value

    def increment(self, ctx, amount: int = 1) -> Any:
        """Increment a numeric state value. Returns the new value."""
        current = self.get(ctx)
        if current is None:
            current = self._default if self._default is not None else 0
        new_value = current + amount
        self.set(ctx, new_value)
        return new_value

    def append(self, ctx, item: Any) -> None:
        """Append to a list state value. Creates the list if not set."""
        current = self.get(ctx)
        if current is None:
            current = []
        if not isinstance(current, list):
            current = [current]
        current.append(item)
        self.set(ctx, current)

    def __repr__(self) -> str:
        return f"StateKey('{self._name}', scope='{self._scope}', type={self._type.__name__})"


# ======================================================================
# Artifact — fluent artifact descriptor
# ======================================================================

class Artifact:
    """Fluent artifact descriptor for ergonomic artifact operations in tools and callbacks.

    Usage:
        report = Artifact("quarterly_report")

        # In a tool:
        await report.save(ctx, "Report content here")
        content = await report.load(ctx)
        versions = await report.list_versions(ctx)
    """

    def __init__(self, filename: str):
        self._filename = filename

    @property
    def filename(self) -> str:
        """The artifact filename."""
        return self._filename

    async def save(self, ctx, content: str | bytes) -> int:
        """Save content as an artifact. Returns the version number.

        Automatically wraps string/bytes content in a genai Part.
        Works with CallbackContext or ToolContext.
        """
        from google.genai import types
        if isinstance(content, bytes):
            part = types.Part.from_data(data=content, mime_type="application/octet-stream")
        else:
            part = types.Part.from_text(text=str(content))
        version = await ctx.save_artifact(self._filename, part)
        return version

    async def load(self, ctx, *, version: int | None = None) -> str | None:
        """Load artifact content. Returns text string or None if not found.

        Automatically extracts text from the Part wrapper.
        Works with CallbackContext or ToolContext.
        """
        part = await ctx.load_artifact(self._filename, version=version)
        if part is None:
            return None
        if hasattr(part, 'text') and part.text:
            return part.text
        if hasattr(part, 'inline_data') and part.inline_data:
            return part.inline_data.data
        return str(part)

    async def list_versions(self, ctx) -> list[int]:
        """List available version numbers for this artifact.

        Works with ToolContext (which has list_artifacts).
        """
        if hasattr(ctx, 'list_artifacts'):
            all_artifacts = await ctx.list_artifacts()
            # Filter for this filename — ADK returns all artifact keys
            return [i for i, name in enumerate(all_artifacts) if name == self._filename]
        return []

    def __repr__(self) -> str:
        return f"Artifact('{self._filename}')"


# ======================================================================
# run_events — raw event streaming
# ======================================================================

async def run_events(builder, prompt: str):
    """Stream raw ADK Event objects from a one-shot agent execution.

    Unlike .ask() which returns only the final text, this yields every
    Event including state deltas, function calls, tool results, etc.

    Usage:
        async for event in agent.events("What is 2+2?"):
            if event.is_final_response():
                print(event.content.parts[0].text)
            if event.actions and event.actions.state_delta:
                print(f"State changed: {event.actions.state_delta}")
    """
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = builder.build()
    app_name = f"_events_{agent.name}"
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="_events_user"
    )
    content = types.Content(
        role="user", parts=[types.Part(text=prompt)]
    )

    async for event in runner.run_async(
        user_id="_events_user", session_id=session.id, new_message=content
    ):
        yield event
