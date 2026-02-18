"""ADK Backend -- compiles IR node trees into native ADK objects."""
from __future__ import annotations

__all__ = ["ADKBackend"]

from typing import Any, AsyncIterator

from adk_fluent._ir import (
    AgentEvent,
    ExecutionConfig,
    FallbackNode,
    GateNode,
    MapOverNode,
    RaceNode,
    RouteNode,
    TapNode,
    TimeoutNode,
    TransferNode,
    TransformNode,
)
from adk_fluent._ir_generated import (
    AgentNode,
    FullNode,
    LoopNode,
    ParallelNode,
    SequenceNode,
)


class ADKBackend:
    """Compiles IR node trees into native Google ADK objects wrapped in an App."""

    # ------------------------------------------------------------------
    # Public API (satisfies Backend protocol)
    # ------------------------------------------------------------------

    def compile(self, node: FullNode, config: ExecutionConfig | None = None) -> Any:
        """Transform an IR node tree into a native ADK App.

        Args:
            node: Root IR node of the agent tree.
            config: Optional execution configuration (app name, resumability, etc.).

        Returns:
            A ``google.adk.apps.app.App`` wrapping the compiled root agent.
        """
        from google.adk.apps.app import App

        root_agent = self._compile_node(node)
        cfg = config or ExecutionConfig()

        app_kwargs: dict[str, Any] = {
            "name": cfg.app_name,
            "root_agent": root_agent,
        }

        # Resumability
        if cfg.resumable:
            from google.adk.apps.app import ResumabilityConfig
            app_kwargs["resumability_config"] = ResumabilityConfig(is_resumable=True)

        # Compaction
        if cfg.compaction:
            from google.adk.apps.app import EventsCompactionConfig
            ecc_kwargs: dict[str, Any] = {
                "compaction_interval": cfg.compaction.interval,
                "overlap_size": cfg.compaction.overlap,
            }
            if cfg.compaction.token_threshold is not None:
                ecc_kwargs["token_threshold"] = cfg.compaction.token_threshold
            if cfg.compaction.event_retention_size is not None:
                ecc_kwargs["event_retention_size"] = cfg.compaction.event_retention_size
            app_kwargs["events_compaction_config"] = EventsCompactionConfig(**ecc_kwargs)

        # Middleware -> plugin
        if cfg.middlewares:
            from adk_fluent.middleware import _MiddlewarePlugin
            plugin = _MiddlewarePlugin(
                name=f"{cfg.app_name}_middleware",
                stack=list(cfg.middlewares),
            )
            app_kwargs["plugins"] = [plugin]

        return App(**app_kwargs)

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute the compiled App and return all events.

        Requires a running session service. Not tested in unit tests
        (needs API keys).
        """
        raise NotImplementedError(
            "ADKBackend.run() requires a session service and API key. "
            "Use compile() for unit-testable compilation."
        )

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Stream events from the compiled App.

        Requires a running session service. Not tested in unit tests
        (needs API keys).
        """
        raise NotImplementedError(
            "ADKBackend.stream() requires a session service and API key. "
            "Use compile() for unit-testable compilation."
        )
        # Make this an async generator to satisfy the protocol
        yield  # type: ignore[misc]  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _compile_node(self, node: FullNode) -> Any:
        """Dispatch to the appropriate type-specific compiler."""
        dispatch = {
            AgentNode: self._compile_agent,
            SequenceNode: self._compile_sequence,
            ParallelNode: self._compile_parallel,
            LoopNode: self._compile_loop,
            TransformNode: self._compile_transform,
            TapNode: self._compile_tap,
            FallbackNode: self._compile_fallback,
            RaceNode: self._compile_race,
            GateNode: self._compile_gate,
            MapOverNode: self._compile_mapover,
            TimeoutNode: self._compile_timeout,
            RouteNode: self._compile_route,
            TransferNode: self._compile_transfer,
        }
        compiler = dispatch.get(type(node))
        if compiler is None:
            raise TypeError(
                f"ADKBackend cannot compile node of type {type(node).__name__}. "
                f"Supported: {', '.join(t.__name__ for t in dispatch)}"
            )
        return compiler(node)

    def _compile_children(self, children: tuple) -> list:
        """Recursively compile a tuple of child IR nodes."""
        return [self._compile_node(child) for child in children]

    # ------------------------------------------------------------------
    # Type-specific compilers
    # ------------------------------------------------------------------

    def _compile_agent(self, node: AgentNode) -> Any:
        """AgentNode -> LlmAgent."""
        from google.adk.agents.llm_agent import LlmAgent
        from adk_fluent._base import _compose_callbacks

        kwargs: dict[str, Any] = {"name": node.name}

        # Simple fields -- only set if non-default to avoid Pydantic issues
        if node.model:
            kwargs["model"] = node.model
        if node.instruction:
            kwargs["instruction"] = node.instruction
        if node.description:
            kwargs["description"] = node.description
        if node.global_instruction:
            kwargs["global_instruction"] = node.global_instruction
        if node.static_instruction is not None:
            kwargs["static_instruction"] = node.static_instruction
        if node.tools:
            kwargs["tools"] = list(node.tools)
        if node.generate_content_config is not None:
            kwargs["generate_content_config"] = node.generate_content_config
        if node.disallow_transfer_to_parent:
            kwargs["disallow_transfer_to_parent"] = node.disallow_transfer_to_parent
        if node.disallow_transfer_to_peers:
            kwargs["disallow_transfer_to_peers"] = node.disallow_transfer_to_peers
        if node.include_contents != "default":
            kwargs["include_contents"] = node.include_contents
        if node.input_schema is not None:
            kwargs["input_schema"] = node.input_schema
        if node.output_schema is not None:
            kwargs["output_schema"] = node.output_schema
        if node.output_key is not None:
            kwargs["output_key"] = node.output_key
        if node.planner is not None:
            kwargs["planner"] = node.planner
        if node.code_executor is not None:
            kwargs["code_executor"] = node.code_executor

        # Sub-agents (children)
        if node.children:
            kwargs["sub_agents"] = self._compile_children(node.children)

        # Callbacks: compose tuples into single callables
        for cb_field, cb_fns in node.callbacks.items():
            if cb_fns:
                kwargs[cb_field] = _compose_callbacks(list(cb_fns))

        return LlmAgent(**kwargs)

    def _compile_sequence(self, node: SequenceNode) -> Any:
        """SequenceNode -> SequentialAgent."""
        from google.adk.agents.sequential_agent import SequentialAgent
        from adk_fluent._base import _compose_callbacks

        kwargs: dict[str, Any] = {
            "name": node.name,
            "sub_agents": self._compile_children(node.children),
        }
        if node.description:
            kwargs["description"] = node.description

        for cb_field, cb_fns in node.callbacks.items():
            if cb_fns:
                kwargs[cb_field] = _compose_callbacks(list(cb_fns))

        return SequentialAgent(**kwargs)

    def _compile_parallel(self, node: ParallelNode) -> Any:
        """ParallelNode -> ParallelAgent."""
        from google.adk.agents.parallel_agent import ParallelAgent
        from adk_fluent._base import _compose_callbacks

        kwargs: dict[str, Any] = {
            "name": node.name,
            "sub_agents": self._compile_children(node.children),
        }
        if node.description:
            kwargs["description"] = node.description

        for cb_field, cb_fns in node.callbacks.items():
            if cb_fns:
                kwargs[cb_field] = _compose_callbacks(list(cb_fns))

        return ParallelAgent(**kwargs)

    def _compile_loop(self, node: LoopNode) -> Any:
        """LoopNode -> LoopAgent."""
        from google.adk.agents.loop_agent import LoopAgent
        from adk_fluent._base import _compose_callbacks

        kwargs: dict[str, Any] = {
            "name": node.name,
            "sub_agents": self._compile_children(node.children),
        }
        if node.description:
            kwargs["description"] = node.description
        if node.max_iterations is not None:
            kwargs["max_iterations"] = node.max_iterations

        for cb_field, cb_fns in node.callbacks.items():
            if cb_fns:
                kwargs[cb_field] = _compose_callbacks(list(cb_fns))

        return LoopAgent(**kwargs)

    def _compile_transform(self, node: TransformNode) -> Any:
        """TransformNode -> FnAgent."""
        from adk_fluent._base import FnAgent
        return FnAgent(name=node.name, fn=node.fn)

    def _compile_tap(self, node: TapNode) -> Any:
        """TapNode -> TapAgent."""
        from adk_fluent._base import TapAgent
        return TapAgent(name=node.name, fn=node.fn)

    def _compile_fallback(self, node: FallbackNode) -> Any:
        """FallbackNode -> FallbackAgent."""
        from adk_fluent._base import FallbackAgent
        return FallbackAgent(
            name=node.name,
            sub_agents=self._compile_children(node.children),
        )

    def _compile_race(self, node: RaceNode) -> Any:
        """RaceNode -> RaceAgent."""
        from adk_fluent._base import RaceAgent
        return RaceAgent(
            name=node.name,
            sub_agents=self._compile_children(node.children),
        )

    def _compile_gate(self, node: GateNode) -> Any:
        """GateNode -> GateAgent."""
        from adk_fluent._base import GateAgent
        return GateAgent(
            name=node.name,
            predicate=node.predicate,
            message=node.message,
            gate_key=node.gate_key,
        )

    def _compile_mapover(self, node: MapOverNode) -> Any:
        """MapOverNode -> MapOverAgent."""
        from adk_fluent._base import MapOverAgent
        sub_agents = []
        if node.body is not None:
            sub_agents.append(self._compile_node(node.body))
        return MapOverAgent(
            name=node.name,
            sub_agents=sub_agents,
            list_key=node.list_key,
            item_key=node.item_key,
            output_key=node.output_key,
        )

    def _compile_timeout(self, node: TimeoutNode) -> Any:
        """TimeoutNode -> TimeoutAgent."""
        from adk_fluent._base import TimeoutAgent
        sub_agents = []
        if node.body is not None:
            sub_agents.append(self._compile_node(node.body))
        return TimeoutAgent(
            name=node.name,
            sub_agents=sub_agents,
            seconds=node.seconds,
        )

    def _compile_route(self, node: RouteNode) -> Any:
        """RouteNode -> _RouteAgent (via closure-based factory)."""
        from adk_fluent._routing import _make_route_agent

        built_rules = []
        sub_agents = []
        for pred, agent_node in node.rules:
            compiled_agent = self._compile_node(agent_node)
            built_rules.append((pred, compiled_agent))
            sub_agents.append(compiled_agent)

        built_default = None
        if node.default is not None:
            built_default = self._compile_node(node.default)
            sub_agents.append(built_default)

        return _make_route_agent(node.name, built_rules, built_default, sub_agents)

    def _compile_transfer(self, node: TransferNode) -> Any:
        """TransferNode -> a minimal BaseAgent that performs transfer_to_agent."""
        from google.adk.agents.base_agent import BaseAgent

        target_name = node.target
        condition_fn = node.condition

        class _TransferAgent(BaseAgent):
            """Compiled transfer agent. Delegates to target by name."""

            async def _run_async_impl(self, ctx):
                should_transfer = True
                if condition_fn is not None:
                    try:
                        should_transfer = bool(condition_fn(dict(ctx.session.state)))
                    except (KeyError, TypeError, ValueError):
                        should_transfer = False

                if should_transfer and target_name:
                    from google.adk.events.event import Event
                    from google.adk.events.event_actions import EventActions
                    yield Event(
                        invocation_id=ctx.invocation_id,
                        author=self.name,
                        branch=ctx.branch,
                        actions=EventActions(transfer_to_agent=target_name),
                    )

        return _TransferAgent(name=node.name)
