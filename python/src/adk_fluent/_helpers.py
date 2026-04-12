"""Runtime helpers for adk-fluent ergonomic features. Hand-written, not generated."""

from __future__ import annotations

import asyncio
import copy
import re as _re
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

__all__ = [
    "deep_clone_builder",
    "add_agent_tool",
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
    "_add_artifacts",
    "_add_tool",
    "_add_tools",
    "_agent_to_ir",
    "_pipeline_to_ir",
    "_fanout_to_ir",
    "_loop_to_ir",
    "_show_agent",
    "_hide_agent",
    "_add_memory",
    "_add_memory_auto_save",
    "_isolate_agent",
    "_stay_agent",
    "_no_peers_agent",
    "_eval_inline",
    "_eval_suite",
    "_instruct_with_guard",
    "_context_with_guard",
    "_guard_dispatch",
    "_add_ui_spec",
]


# ---------------------------------------------------------------------------
# Tool helpers
# ---------------------------------------------------------------------------


def _add_tool(builder, fn_or_tool, *, require_confirmation: bool = False):
    """Add a tool to the builder, wrapping plain callables when require_confirmation is set."""
    if require_confirmation and callable(fn_or_tool):
        from google.adk.tools.base_tool import BaseTool as _BaseTool

        if not isinstance(fn_or_tool, _BaseTool):
            from google.adk.tools.function_tool import FunctionTool

            fn_or_tool = FunctionTool(func=fn_or_tool, require_confirmation=True)
    builder._lists["tools"].append(fn_or_tool)
    return builder


def _instruct_with_guard(builder, value):
    """Set instruction with a guard against CTransform misuse."""
    from adk_fluent._context import CTransform

    if isinstance(value, CTransform):
        raise TypeError(
            f"instruct() received a CTransform ({type(value).__name__}). "
            "Did you mean .context(...)? Use .instruct() for prompt text/PTransform, "
            ".context() for CTransform."
        )
    builder = builder._maybe_fork_for_mutation()
    builder._config["instruction"] = value
    return builder


def _context_with_guard(builder, spec):
    """Set context spec with a guard against PTransform misuse."""
    from adk_fluent._prompt import PTransform

    if isinstance(spec, PTransform):
        raise TypeError(
            f"context() received a PTransform ({type(spec).__name__}). "
            "Did you mean .instruct(...)? Use .context() for CTransform, "
            ".instruct() for prompt text/PTransform."
        )
    builder = builder._maybe_fork_for_mutation()
    builder._config["_context_spec"] = spec
    return builder


def _guard_dispatch(builder, value):
    """Route .guard() calls — supports G composites and legacy callables."""
    from adk_fluent._guards import GComposite, GGuard

    if isinstance(value, GComposite):
        value._compile_into(builder)
    elif isinstance(value, GGuard):
        GComposite([value])._compile_into(builder)
    elif callable(value):
        # Backwards compatible — existing dual-callback behavior
        builder._callbacks.setdefault("before_model_callback", []).append(value)
        builder._callbacks.setdefault("after_model_callback", []).append(value)
    else:
        raise TypeError(
            f"guard() expects a callable or G composite, got {type(value).__name__}. "
            f"Use G.json(), G.pii(), etc. to create guard composites."
        )
    return builder


def _add_tools(builder, tools_arg, *, replace: bool = True):
    """Set tools on the builder, handling TComposite, lists, and single items.

    If ``replace`` is True, clears existing tools before adding new ones
    (used by ``.tools()``). If False, appends (used by ``.tool()``).

    If ``tools_arg`` is a ``TComposite``, flattens it and extracts any
    ``_SchemaMarker`` entries to wire ``tool_schema`` on the IR node.
    """
    from adk_fluent._middleware import MComposite
    from adk_fluent._tools import TComposite, _SchemaMarker

    if isinstance(tools_arg, MComposite):
        raise TypeError(
            "tools() received an MComposite (middleware chain). "
            "Did you mean .middleware(...)? Use .tools() for tool functions/TComposite, "
            ".middleware() for MComposite."
        )
    if replace:
        builder._lists["tools"] = []
    if isinstance(tools_arg, TComposite):
        for item in tools_arg.to_tools():
            if isinstance(item, _SchemaMarker):
                builder._config["_tool_schema"] = item._schema_cls
            else:
                builder._lists["tools"].append(item)
    elif isinstance(tools_arg, list):
        builder._lists.setdefault("tools", []).extend(tools_arg)
    else:
        builder._lists["tools"].append(tools_arg)
    return builder


# ---------------------------------------------------------------------------
# IR conversion helpers (used by generated to_ir() methods)
# ---------------------------------------------------------------------------


def _collect_children(builder):
    """Collect and recursively convert sub_agents from builder config and lists."""
    from adk_fluent._base import BuilderBase

    children_raw = list(builder._config.get("sub_agents", []))
    children_raw.extend(builder._lists.get("sub_agents", []))
    result = []
    for c in children_raw:
        if isinstance(c, BuilderBase) or hasattr(c, "to_ir") and callable(c.to_ir):
            result.append(c.to_ir())
        else:
            result.append(c)
    return tuple(result)


def _agent_to_ir(builder):
    """Convert an Agent builder to an AgentNode IR node."""
    from adk_fluent._ir_generated import AgentNode

    callbacks = {k: tuple(v) for k, v in builder._callbacks.items() if v}

    tools = tuple(builder._config.get("tools", []))
    if builder._lists.get("tools"):
        tools = tools + tuple(builder._lists["tools"])

    children = _collect_children(builder)

    produces_schema = builder._config.get("_produces")
    consumes_schema = builder._config.get("_consumes")
    context_spec = builder._config.get("_context_spec")
    prompt_spec = builder._config.get("_prompt_spec")
    tool_schema = builder._config.get("_tool_schema")
    callback_schema = builder._config.get("_callback_schema")
    # Also capture PTransform stored directly in instruction
    if prompt_spec is None:
        from adk_fluent._prompt import PTransform as _PT

        instr = builder._config.get("instruction")
        if isinstance(instr, _PT):
            prompt_spec = instr
    writes_keys = frozenset(produces_schema.model_fields.keys()) if produces_schema else frozenset()
    reads_keys = frozenset(consumes_schema.model_fields.keys()) if consumes_schema else frozenset()
    if tool_schema is not None and hasattr(tool_schema, "reads_keys"):
        reads_keys = reads_keys | tool_schema.reads_keys()
    if tool_schema is not None and hasattr(tool_schema, "writes_keys"):
        writes_keys = writes_keys | tool_schema.writes_keys()
    if callback_schema is not None and hasattr(callback_schema, "reads_keys"):
        reads_keys = reads_keys | callback_schema.reads_keys()
    if callback_schema is not None and hasattr(callback_schema, "writes_keys"):
        writes_keys = writes_keys | callback_schema.writes_keys()

    prompt_schema_cls = builder._config.get("_prompt_schema")
    if prompt_schema_cls is not None and hasattr(prompt_schema_cls, "reads_keys"):
        reads_keys = reads_keys | prompt_schema_cls.reads_keys()
    # Note: NO writes_keys merging — prompts only read state

    artifact_schema_cls = builder._config.get("_artifact_schema")
    guard_specs = builder._config.get("_guard_specs", ())

    return AgentNode(
        name=builder._config.get("name", ""),
        description=builder._config.get("description", ""),
        children=children,
        model=builder._config.get("model", ""),
        instruction=builder._config.get("instruction", ""),
        global_instruction=builder._config.get("global_instruction", ""),
        static_instruction=builder._config.get("static_instruction"),
        tools=tools,
        generate_content_config=builder._config.get("generate_content_config"),
        disallow_transfer_to_parent=builder._config.get("disallow_transfer_to_parent", False),
        disallow_transfer_to_peers=builder._config.get("disallow_transfer_to_peers", False),
        include_contents=builder._config.get("include_contents", "default"),
        input_schema=builder._config.get("input_schema"),
        output_schema=builder._config.get("output_schema") or builder._config.get("_output_schema"),
        output_key=builder._config.get("output_key"),
        planner=builder._config.get("planner"),
        code_executor=builder._config.get("code_executor"),
        callbacks=callbacks,
        writes_keys=writes_keys,
        reads_keys=reads_keys,
        produces_type=produces_schema,
        consumes_type=consumes_schema,
        context_spec=context_spec,
        prompt_spec=prompt_spec,
        tool_schema=tool_schema,
        callback_schema=callback_schema,
        prompt_schema=prompt_schema_cls,
        artifact_schema=artifact_schema_cls,
        guard_specs=guard_specs,
    )


def _pipeline_to_ir(builder):
    """Convert a Pipeline builder to a SequenceNode IR node."""
    from adk_fluent._ir_generated import SequenceNode

    middlewares = tuple(getattr(builder, "_middlewares", []))
    return SequenceNode(
        name=builder._config.get("name", "pipeline"),
        children=_collect_children(builder),
        middlewares=middlewares,
    )


def _fanout_to_ir(builder):
    """Convert a FanOut builder to a ParallelNode IR node."""
    from adk_fluent._ir_generated import ParallelNode

    return ParallelNode(
        name=builder._config.get("name", "fanout"),
        children=_collect_children(builder),
    )


def _loop_to_ir(builder):
    """Convert a Loop builder to a LoopNode IR node."""
    from adk_fluent._ir_generated import LoopNode

    return LoopNode(
        name=builder._config.get("name", "loop"),
        children=_collect_children(builder),
        max_iterations=builder._config.get("max_iterations"),
    )


def _add_artifacts(builder, transforms):
    """Attach artifact transforms to the builder."""
    builder._lists.setdefault("_artifact_transforms", []).extend(transforms)
    return builder


def _add_skill(
    builder,
    skill_id: str,
    name: str,
    *,
    description: str = "",
    tags: list | None = None,
    examples: list | None = None,
    input_modes: list | None = None,
    output_modes: list | None = None,
):
    """Declare an A2A skill on the agent builder.

    Skills are stored as metadata and used by ``A2AServer`` when generating
    the ``AgentCard``.  They have no effect on local agent execution.
    """
    from adk_fluent.a2a import SkillDeclaration

    skill = SkillDeclaration(
        id=skill_id,
        name=name,
        description=description,
        tags=tags or [],
        examples=examples or [],
        input_modes=input_modes or ["text/plain"],
        output_modes=output_modes or ["text/plain"],
    )
    builder._lists.setdefault("_a2a_skills", []).append(skill)
    return builder


def _publish_agent(builder, *, port: int = 8000, host: str = "0.0.0.0"):
    """Publish an agent as an A2A server (returns Starlette app).

    Shorthand for ``A2AServer(builder).port(port).host(host).build()``.
    Forwards any declared `_a2a_skills` to the server.
    """
    from adk_fluent.a2a import A2AServer

    server = A2AServer(builder).port(port).host(host)
    # Pass declared skills to the server
    skills = builder._lists.get("_a2a_skills", [])
    for s in skills:
        server = server.skill(
            s.id,
            s.name,
            description=s.description,
            tags=s.tags,
            examples=s.examples,
            input_modes=s.input_modes,
            output_modes=s.output_modes,
        )
    return server.build()


def add_agent_tool(builder, agent):
    """Wrap an agent (or builder) as an AgentTool and add it to this agent's tools.

    The LLM can invoke the wrapped agent by name. This enables the
    coordinator pattern where a parent agent delegates to specialists.
    """
    from google.adk.tools.agent_tool import AgentTool

    # Auto-build if it's a builder
    built = agent.build() if hasattr(agent, "build") and hasattr(agent, "_config") else agent
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


# ---------------------------------------------------------------------------
# v5.1 Context Engineering helpers
# ---------------------------------------------------------------------------


def _show_agent(builder):
    """Force this agent's events to be user-facing (override topology inference)."""
    builder._config["_visibility_override"] = "user"
    return builder


def _hide_agent(builder):
    """Force this agent's events to be internal (override topology inference)."""
    builder._config["_visibility_override"] = "internal"
    return builder


def _isolate_agent(builder):
    """Prevent this agent from transferring to parent or peers.

    Sets both disallow_transfer_to_parent and disallow_transfer_to_peers to True.
    Use for specialist agents that should complete their task and return.
    """
    builder._config["disallow_transfer_to_parent"] = True
    builder._config["disallow_transfer_to_peers"] = True
    return builder


def _stay_agent(builder):
    """Prevent this agent from transferring back to its parent.

    The agent can still transfer to sibling agents.
    Use for agents that should complete their work before returning.
    """
    builder._config["disallow_transfer_to_parent"] = True
    return builder


def _no_peers_agent(builder):
    """Prevent this agent from transferring to sibling agents.

    The agent can still return to its parent.
    """
    builder._config["disallow_transfer_to_peers"] = True
    return builder


def _add_memory(builder, mode: str = "preload"):
    """Add memory tools to this agent.

    Modes:
      'preload'   — PreloadMemoryTool (retrieves memory at start of each turn)
      'on_demand' — LoadMemoryTool (agent decides when to load)
      'both'      — Both tools
    """
    from google.adk.tools.load_memory_tool import LoadMemoryTool
    from google.adk.tools.preload_memory_tool import PreloadMemoryTool

    if mode == "preload":
        builder._lists.setdefault("tools", []).append(PreloadMemoryTool())
    elif mode == "on_demand":
        builder._lists.setdefault("tools", []).append(LoadMemoryTool())
    elif mode == "both":
        builder._lists.setdefault("tools", []).append(PreloadMemoryTool())
        builder._lists.setdefault("tools", []).append(LoadMemoryTool())
    else:
        raise ValueError(f"Invalid memory mode '{mode}'. Use 'preload', 'on_demand', or 'both'.")
    return builder


def _add_memory_auto_save(builder):
    """Auto-save session to memory after each agent run.

    Adds an after_agent_callback that calls memory_service.add_session_to_memory().
    Requires a memory_service to be configured on the Runner/App.
    """

    async def _auto_save_callback(callback_context):
        memory_service = getattr(callback_context._invocation_context, "memory_service", None)
        if memory_service is not None:
            await memory_service.add_session_to_memory(callback_context._invocation_context.session)

    builder._callbacks["after_agent_callback"].append(_auto_save_callback)
    return builder


def _resolve_engine(builder) -> str | None:
    """Resolve the engine name from builder config or global config.

    Returns the engine name (e.g., "adk", "asyncio", "temporal") or None
    for the default ADK path.
    """
    # Builder-level override takes priority
    engine = builder._config.get("_engine")
    if engine is not None:
        return engine

    # Global config fallback
    from adk_fluent._config_global import get_config

    global_cfg = get_config()
    return global_cfg.get("engine")


async def _run_via_engine(builder, prompt: str) -> tuple[str, list]:
    """Execute a builder through the five-layer engine path.

    Returns (final_text, events_list).
    """
    from adk_fluent._config_global import get_config
    from adk_fluent.backends import get_backend

    engine = _resolve_engine(builder)
    global_cfg = get_config()

    # Resolve backend kwargs
    engine_kwargs = builder._config.get("_engine_kwargs", {})
    if not engine_kwargs:
        engine_kwargs = global_cfg.get("engine_config", {})

    # Resolve compute config
    compute = builder._config.get("_compute")
    if compute is None:
        compute = global_cfg.get("compute")

    # Inject compute into backend kwargs if applicable
    if compute is not None:
        if hasattr(compute, "model_provider") and compute.model_provider is not None:
            engine_kwargs.setdefault("model_provider", compute.model_provider)
        if hasattr(compute, "tool_runtime") and compute.tool_runtime is not None:
            engine_kwargs.setdefault("tool_runtime", compute.tool_runtime)

    assert engine is not None  # Caller guarantees engine is set
    backend = get_backend(engine, **engine_kwargs)

    # Compile IR
    ir = builder.to_ir()
    compiled = backend.compile(ir)

    # Execute
    events = await backend.run(compiled, prompt)

    # Extract final text
    last_text = ""
    for event in events:
        content = getattr(event, "content", None)
        if isinstance(content, str):
            last_text = content
        elif content is not None and hasattr(content, "parts"):
            for part in content.parts:
                if getattr(part, "text", None):
                    last_text = part.text

    return last_text, events


async def run_one_shot_async(builder, prompt: str) -> str:
    """Execute a builder as a one-shot agent and return the text response.

    Supports structured output and debug tracing.
    Routes to the appropriate engine based on builder/global config.
    """
    debug = builder._config.get("_debug", False)
    agent_name = builder._config.get("name", "?")

    engine = _resolve_engine(builder)

    t0 = time.monotonic()
    if debug:
        _debug_log(agent_name, f"Sending prompt ({len(prompt)} chars)")

    # Non-ADK engine path: use five-layer architecture
    if engine is not None and engine != "adk":
        last_text, _events = await _run_via_engine(builder, prompt)
    else:
        # Default ADK path
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        agent = builder.build()
        app_name = f"_ask_{agent.name}"
        runner = InMemoryRunner(agent=agent, app_name=app_name)
        session = await runner.session_service.create_session(app_name=app_name, user_id="_ask_user")
        content = types.Content(role="user", parts=[types.Part(text=prompt)])

        last_text = ""
        async for event in runner.run_async(user_id="_ask_user", session_id=session.id, new_message=content):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        last_text = part.text

    if debug:
        elapsed = time.monotonic() - t0
        _debug_log(agent_name, f"Response received ({len(last_text)} chars, {elapsed:.2f}s)")

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
            except Exception as e:
                raise ValueError(
                    f"Structured output parsing failed for schema "
                    f"{schema.__name__}. The LLM returned text that could "
                    f"not be parsed as the requested type.\n"
                    f"Raw response:\n{last_text}"
                ) from e

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
    engine = _resolve_engine(builder)

    if engine is not None and engine != "adk":
        # Non-ADK engine path
        _text, events = await _run_via_engine(builder, prompt)
        for event in events:
            content = getattr(event, "content", None)
            if isinstance(content, str) and content:
                yield content
            elif content is not None and hasattr(content, "parts"):
                for part in content.parts:  # type: ignore[union-attr]
                    if getattr(part, "text", None):
                        yield part.text
    else:
        # Default ADK path
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        agent = builder.build()
        app_name = f"_stream_{agent.name}"
        runner = InMemoryRunner(agent=agent, app_name=app_name)
        session = await runner.session_service.create_session(app_name=app_name, user_id="_stream_user")
        content = types.Content(role="user", parts=[types.Part(text=prompt)])

        async for event in runner.run_async(user_id="_stream_user", session_id=session.id, new_message=content):
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

        content = types.Content(role="user", parts=[types.Part(text=text)])
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
    session = await runner.session_service.create_session(app_name=app_name, user_id=user_id)

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

    def get(self, ctx: Any) -> Any:
        """Get the value from context state. Returns default if not set.

        Works with CallbackContext, ToolContext, or any object with a .state dict-like attribute.
        """
        state: Any = ctx.state if hasattr(ctx, "state") else ctx
        if callable(state) and not isinstance(state, dict):
            state = state()  # ReadonlyContext.state() is a method
        return state.get(self._full_key, self._default)

    def set(self, ctx: Any, value: Any) -> None:
        """Set the value in context state.

        Works with CallbackContext, ToolContext, or any object with a .state dict-like attribute.
        """
        state: Any = ctx.state if hasattr(ctx, "state") else ctx
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
            part = types.Part.from_data(data=content, mime_type="application/octet-stream")  # type: ignore[reportAttributeAccessIssue]
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
        if hasattr(part, "text") and part.text:
            return part.text
        if hasattr(part, "inline_data") and part.inline_data:
            return part.inline_data.data
        return str(part)

    async def list_versions(self, ctx) -> list[int]:
        """List available version numbers for this artifact.

        Works with ToolContext (which has list_artifacts).
        """
        if hasattr(ctx, "list_artifacts"):
            all_artifacts = await ctx.list_artifacts()
            # Filter for this filename — ADK returns all artifact keys
            return [i for i, name in enumerate(all_artifacts) if name == self._filename]
        return []

    def __repr__(self) -> str:
        return f"Artifact('{self._filename}')"


# ======================================================================
# run_events — raw event streaming
# ======================================================================


# ---------------------------------------------------------------------------
# Eval helpers (used by generated .eval() / .eval_suite() methods)
# ---------------------------------------------------------------------------


def _eval_inline(builder, prompt: str, *, expect: str | None = None, criteria: Any = None) -> Any:
    """Create an EvalSuite with a single case for inline evaluation."""
    from adk_fluent._eval import E, EvalSuite

    suite = EvalSuite(builder)
    suite.case(prompt, expect=expect)
    if criteria is not None:
        suite.criteria(criteria)
    elif expect is not None:
        suite.criteria(E.response_match())
    return suite


def _eval_suite(builder) -> Any:
    """Create an empty EvalSuite bound to this builder."""
    from adk_fluent._eval import EvalSuite

    return EvalSuite(builder)


async def run_events(builder, prompt: str):
    """Stream raw Event objects from a one-shot agent execution.

    Unlike .ask() which returns only the final text, this yields every
    Event including state deltas, function calls, tool results, etc.

    Usage:
        async for event in agent.events("What is 2+2?"):
            if event.is_final_response():
                print(event.content.parts[0].text)
            if event.actions and event.actions.state_delta:
                print(f"State changed: {event.actions.state_delta}")
    """
    engine = _resolve_engine(builder)

    if engine is not None and engine != "adk":
        # Non-ADK engine path
        _text, events = await _run_via_engine(builder, prompt)
        for event in events:
            yield event
    else:
        # Default ADK path
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        agent = builder.build()
        app_name = f"_events_{agent.name}"
        runner = InMemoryRunner(agent=agent, app_name=app_name)
        session = await runner.session_service.create_session(app_name=app_name, user_id="_events_user")
        content = types.Content(role="user", parts=[types.Part(text=prompt)])

        async for event in runner.run_async(user_id="_events_user", session_id=session.id, new_message=content):
            yield event


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _add_ui_spec(builder, spec):
    """Attach A2UI surface/config to the agent.

    Accepts:
      - UISurface: declarative surface definition
      - UIComponent: wrapped in a default surface
      - _UIAutoSpec: LLM-guided mode (schema injection)
      - _UISchemaSpec: schema-only prompt injection
    """
    builder._config["_ui_spec"] = spec
    return builder
