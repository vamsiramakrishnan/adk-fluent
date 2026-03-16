"""Asyncio backend — direct IR interpreter using plain Python asyncio.

This is the zero-dependency reference backend. It proves that the
five-layer architecture works without any external framework (no ADK,
no Temporal, no DBOS). It interprets IR nodes directly using asyncio
primitives.

No durability — execution is ephemeral. Use for testing, simple
deployments, or as a reference implementation for new backends.

Requires a ``ModelProvider`` for LLM calls (from the compute layer).

Usage::

    from adk_fluent.backends.asyncio_backend import AsyncioBackend
    from adk_fluent.compute import ComputeConfig

    backend = AsyncioBackend(model_provider=my_provider)
    result = compile(ir, backend=backend)
    events = await backend.run(result, "Hello")
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from adk_fluent._ir import AgentEvent, ExecutionConfig
from adk_fluent.compile import EngineCapabilities

__all__ = ["AsyncioBackend"]


class AsyncioBackend:
    """Direct IR interpreter using asyncio. No framework dependency.

    Walks the IR tree and executes each node:
    - AgentNode: calls ModelProvider.generate()
    - SequenceNode: runs children sequentially
    - ParallelNode: runs children with asyncio.gather()
    - LoopNode: loops children up to max_iterations
    - TransformNode: applies transform function to state
    - TapNode: runs observation function (no state mutation)
    - FallbackNode: tries children in order, first success wins
    - RouteNode: evaluates predicates and routes to matching child
    """

    name: str = "asyncio"

    def __init__(
        self,
        *,
        model_provider: Any = None,
        tool_runtime: Any = None,
    ):
        self._provider = model_provider
        self._tool_runtime = tool_runtime

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            streaming=True,
            parallel=True,
            durable=False,
            replay=False,
            checkpointing=False,
            signals=False,
            dispatch_join=True,
            distributed=False,
        )

    def compile(self, node: Any, config: ExecutionConfig | None = None) -> Any:
        """No-op compilation — the asyncio backend interprets IR directly."""
        return _AsyncioRunnable(node=node, config=config)

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute the IR tree and collect all events."""
        runnable = compiled if isinstance(compiled, _AsyncioRunnable) else _AsyncioRunnable(node=compiled)
        state = kwargs.get("session", _DictState()).state if hasattr(kwargs.get("session"), "state") else {}

        events: list[AgentEvent] = []
        await self._execute_node(runnable.node, prompt, state, events)

        # Mark the last event as final
        if events and not any(e.is_final for e in events):
            events[-1] = AgentEvent(
                author=events[-1].author,
                content=events[-1].content,
                state_delta=events[-1].state_delta,
                is_final=True,
            )

        return events

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Stream events as they are produced."""
        events = await self.run(compiled, prompt, **kwargs)
        for event in events:
            yield event

    # ------------------------------------------------------------------
    # Node interpreters
    # ------------------------------------------------------------------

    async def _execute_node(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """Dispatch to the appropriate node interpreter."""
        node_type = type(node).__name__
        handler = _NODE_HANDLERS.get(node_type)
        if handler is not None:
            await handler(self, node, prompt, state, events)
        else:
            # Unknown node type — treat as no-op with warning
            events.append(
                AgentEvent(
                    author=getattr(node, "name", "unknown"),
                    content=f"[asyncio backend: unsupported node type {node_type}]",
                )
            )

    async def _run_agent(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """AgentNode → call ModelProvider.generate()."""
        if self._provider is None:
            # No provider — return a placeholder
            logging.getLogger("adk_fluent.backends.asyncio").warning(
                "No ModelProvider configured — agent '%s' will return a placeholder response",
                node.name,
            )
            events.append(
                AgentEvent(
                    author=node.name,
                    content=f"[no model provider configured for '{node.name}']",
                )
            )
            return

        from adk_fluent.compute._protocol import GenerateConfig, Message

        # Build messages
        messages = []
        instruction = getattr(node, "instruction", "")
        if instruction:
            messages.append(Message(role="system", content=str(instruction)))
        messages.append(Message(role="user", content=prompt))

        # Build tool definitions
        tools = None
        raw_tools = getattr(node, "tools", ())
        if raw_tools:
            from adk_fluent.compute._protocol import ToolDef

            tools = []
            for t in raw_tools:
                name = getattr(t, "__name__", getattr(t, "name", str(t)))
                doc = getattr(t, "__doc__", "") or ""
                tools.append(ToolDef(name=name, description=doc, fn=t))

        # Call provider
        config = GenerateConfig()
        gen_config = getattr(node, "generate_content_config", None)
        if gen_config is not None and hasattr(gen_config, "temperature"):
            config = GenerateConfig(temperature=gen_config.temperature)

        result = await self._provider.generate(messages, tools, config)

        # Handle tool calls
        while result.has_tool_calls and tools:
            for tc in result.tool_calls:
                tc_name = tc.get("name", "")
                tc_args = tc.get("args", {})

                # Find the tool function
                tool_fn = None
                for td in tools:
                    if td.name == tc_name and td.fn is not None:
                        tool_fn = td.fn
                        break

                if tool_fn is not None:
                    if self._tool_runtime:
                        tool_result = await self._tool_runtime.execute(tc_name, tool_fn, tc_args)
                    else:
                        tool_result = tool_fn(**tc_args)
                        if asyncio.iscoroutine(tool_result):
                            tool_result = await tool_result
                else:
                    tool_result = f"[tool {tc_name} not found]"

                messages.append(
                    Message(
                        role="tool",
                        content=str(tool_result),
                        tool_results=[{"name": tc_name, "result": tool_result}],
                    )
                )

            result = await self._provider.generate(messages, tools, config)

        # Store output key if configured
        output_key = getattr(node, "output_key", None)
        state_delta = {}
        if output_key and result.text:
            state[output_key] = result.text
            state_delta[output_key] = result.text

        events.append(
            AgentEvent(
                author=node.name,
                content=result.text,
                state_delta=state_delta,
            )
        )

        # Recurse into children (sub-agents)
        for child in getattr(node, "children", ()):
            await self._execute_node(child, prompt, state, events)

    async def _run_sequence(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """SequenceNode → run children sequentially."""
        for child in getattr(node, "children", ()):
            await self._execute_node(child, prompt, state, events)

    async def _run_parallel(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """ParallelNode → run children concurrently with asyncio.gather()."""
        children = getattr(node, "children", ())
        if not children:
            return

        # Each branch gets its own events list and state copy
        branch_events: list[list[AgentEvent]] = [[] for _ in children]
        branch_states = [dict(state) for _ in children]

        async def _run_branch(i: int, child: Any) -> None:
            await self._execute_node(child, prompt, branch_states[i], branch_events[i])

        await asyncio.gather(*[_run_branch(i, c) for i, c in enumerate(children)])

        # Merge events and state
        for be in branch_events:
            events.extend(be)
        # Detect parallel write conflicts
        seen_keys: dict[str, int] = {}
        for bs in branch_states:
            for k in bs:
                if k not in state or bs[k] != state.get(k):
                    seen_keys[k] = seen_keys.get(k, 0) + 1
            state.update(bs)
        conflicts = [k for k, count in seen_keys.items() if count > 1]
        if conflicts:
            logging.getLogger("adk_fluent.backends.asyncio").warning(
                "Parallel branches wrote same key(s): %s — last write wins",
                ", ".join(sorted(conflicts)),
            )

    async def _run_loop(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """LoopNode → loop children up to max_iterations."""
        max_iter = getattr(node, "max_iterations", None) or 10
        children = getattr(node, "children", ())

        for _iteration in range(max_iter):
            for child in children:
                await self._execute_node(child, prompt, state, events)

    async def _run_transform(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """TransformNode → apply transform function to state."""
        fn = getattr(node, "fn", None)
        if fn is not None:
            result = fn(dict(state))
            if isinstance(result, dict):
                state_delta = {k: v for k, v in result.items() if state.get(k) != v}
                state.update(result)
                if state_delta:
                    events.append(
                        AgentEvent(
                            author=node.name,
                            state_delta=state_delta,
                        )
                    )

    async def _run_tap(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """TapNode → observation only, no state mutation."""
        fn = getattr(node, "fn", None)
        if fn is not None:
            fn(dict(state))

    async def _run_fallback(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """FallbackNode → try children in order, first success wins."""
        children = getattr(node, "children", ())
        last_error: Exception | None = None

        for child in children:
            try:
                child_events: list[AgentEvent] = []
                await self._execute_node(child, prompt, state, child_events)
                events.extend(child_events)
                return  # Success
            except Exception as e:
                last_error = e
                continue

        if last_error is not None:
            raise last_error

    async def _run_route(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """RouteNode → evaluate predicates and route to matching child."""
        rules = getattr(node, "rules", ())
        default = getattr(node, "default", None)

        for pred, child in rules:
            try:
                if pred(state):
                    await self._execute_node(child, prompt, state, events)
                    return
            except Exception:
                continue

        if default is not None:
            await self._execute_node(default, prompt, state, events)

    async def _run_gate(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """GateNode → asyncio.Event wait (no true HITL without external trigger).

        In the asyncio backend, gates check a predicate against state.
        If the predicate is not satisfied, the gate is skipped with a warning
        (no external signal mechanism in plain asyncio).
        """
        predicate = getattr(node, "predicate", None)
        if predicate is not None:
            try:
                if predicate(state):
                    return  # Gate passed
            except Exception:
                pass

        events.append(
            AgentEvent(
                author=node.name,
                content=f"[gate '{node.name}' passed (asyncio backend has no signal support)]",
            )
        )

    async def _run_dispatch(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """DispatchNode → asyncio.create_task (fire-and-forget)."""
        children = getattr(node, "children", ())
        tasks = []
        for child in children:
            child_events: list[AgentEvent] = []
            task = asyncio.create_task(
                self._execute_node(child, prompt, dict(state), child_events)
            )
            tasks.append((task, child_events))

        # Store task references for JoinNode to pick up
        task_names = getattr(node, "task_names", ())
        for i, name in enumerate(task_names):
            if i < len(tasks):
                state[f"_dispatch_{name}"] = tasks[i]

        events.append(
            AgentEvent(
                author=node.name,
                content=f"[dispatched {len(tasks)} background task(s)]",
            )
        )

    async def _run_join(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """JoinNode → await dispatched tasks."""
        target_names = getattr(node, "target_names", None)
        if target_names is None:
            # Join all dispatched tasks
            target_names = [
                k.replace("_dispatch_", "")
                for k in list(state.keys())
                if k.startswith("_dispatch_")
            ]

        for name in target_names:
            dispatch_entry = state.pop(f"_dispatch_{name}", None)
            if dispatch_entry is not None:
                task, child_events = dispatch_entry
                await task
                events.extend(child_events)

    async def _run_timeout(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """TimeoutNode → asyncio.wait_for wrapper."""
        body = getattr(node, "body", None)
        seconds = getattr(node, "seconds", 0)

        if body is None:
            return

        try:
            await asyncio.wait_for(
                self._execute_node(body, prompt, state, events),
                timeout=seconds if seconds > 0 else None,
            )
        except TimeoutError:
            events.append(
                AgentEvent(
                    author=node.name,
                    content=f"[timeout after {seconds}s]",
                )
            )

    async def _run_race(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """RaceNode → first-to-complete wins."""
        children = getattr(node, "children", ())
        if not children:
            return

        # Each branch gets its own events list and state copy
        branch_data = []
        tasks = []
        for child in children:
            child_events: list[AgentEvent] = []
            child_state = dict(state)
            branch_data.append((child_events, child_state))

            async def _run_branch(c: Any, ev: list, st: dict) -> int:
                await self._execute_node(c, prompt, st, ev)
                return len(ev)

            tasks.append(asyncio.create_task(_run_branch(child, child_events, child_state)))

        # Wait for first to complete
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Cancel remaining
        for p in pending:
            p.cancel()

        # Collect events from the winner
        for i, task in enumerate(tasks):
            if task in done:
                child_events, child_state = branch_data[i]
                events.extend(child_events)
                state.update(child_state)
                break

    async def _run_mapover(
        self,
        node: Any,
        prompt: str,
        state: dict[str, Any],
        events: list[AgentEvent],
    ) -> None:
        """MapOverNode → iterate over list items and execute body for each."""
        body = getattr(node, "body", None)
        list_key = getattr(node, "list_key", "")

        if body is None or not list_key:
            return

        items = state.get(list_key, [])
        if not isinstance(items, list):
            return

        for i, item in enumerate(items):
            item_state = dict(state)
            item_state["_item"] = item
            item_state["_index"] = i
            await self._execute_node(body, prompt, item_state, events)
            # Merge back any state changes (excluding temp keys)
            for k, v in item_state.items():
                if not k.startswith("_"):
                    state[k] = v


class _AsyncioRunnable:
    """Wrapper around an IR node for the asyncio backend."""

    __slots__ = ("node", "config")

    def __init__(self, node: Any, config: ExecutionConfig | None = None):
        self.node = node
        self.config = config


class _DictState:
    """Minimal state wrapper for when no session is provided."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}


# Dispatch table for node handlers
_NODE_HANDLERS: dict[str, Any] = {
    "AgentNode": AsyncioBackend._run_agent,
    "SequenceNode": AsyncioBackend._run_sequence,
    "ParallelNode": AsyncioBackend._run_parallel,
    "LoopNode": AsyncioBackend._run_loop,
    "TransformNode": AsyncioBackend._run_transform,
    "TapNode": AsyncioBackend._run_tap,
    "FallbackNode": AsyncioBackend._run_fallback,
    "RouteNode": AsyncioBackend._run_route,
    "GateNode": AsyncioBackend._run_gate,
    "DispatchNode": AsyncioBackend._run_dispatch,
    "JoinNode": AsyncioBackend._run_join,
    "TimeoutNode": AsyncioBackend._run_timeout,
    "RaceNode": AsyncioBackend._run_race,
    "MapOverNode": AsyncioBackend._run_mapover,
}
