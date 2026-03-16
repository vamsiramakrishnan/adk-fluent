"""Prefect backend — compiles IR to Prefect flows and tasks.

This backend maps adk-fluent IR nodes to Prefect concepts:

- Non-deterministic nodes (AgentNode = LLM calls) become ``@task``
  functions whose results are cached by Prefect's result persistence.
- Deterministic nodes (TransformNode, TapNode, RouteNode) become inline
  flow code — pure Python that executes directly in the flow body.

Task result caching means that if a flow run is retried, completed tasks
return their cached results instead of re-executing (reducing LLM costs).

Requires: ``pip install adk-fluent[prefect]`` (adds ``prefect``).

Usage::

    from adk_fluent.backends.prefect_backend import PrefectBackend
    from adk_fluent.compile import compile

    backend = PrefectBackend()
    result = compile(ir, backend=backend)

Note: This module can be imported without prefect installed — it only
fails at runtime when you try to compile or run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._ir import AgentEvent, ExecutionConfig
from adk_fluent.compile import EngineCapabilities

__all__ = ["PrefectBackend", "PrefectRunnable"]


@dataclass
class PrefectRunnable:
    """Compiled Prefect execution plan.

    Contains the flow structure and task definitions needed to execute
    the agent pipeline via Prefect.
    """

    ir: Any
    """Original IR tree for introspection."""

    node_plan: list[dict[str, Any]] = field(default_factory=list)
    """Execution plan: ordered list of node descriptors with Prefect type annotations."""

    config: ExecutionConfig | None = None
    """Original execution config."""


class PrefectBackend:
    """Compiles IR to Prefect flows + tasks.

    Deterministic vs. non-deterministic classification:

    - **Tasks** (non-deterministic, cached on retry):
      AgentNode (LLM calls), tool executions

    - **Flow code** (deterministic, inline):
      TransformNode, TapNode, RouteNode, SequenceNode, ParallelNode,
      LoopNode, FallbackNode

    - **Pause/resume** (human-in-the-loop):
      GateNode → ``pause_flow_run()``

    The backend generates an execution plan that can be interpreted at
    runtime or used to generate Prefect flow source code via
    ``prefect_worker.py``.
    """

    name: str = "prefect"

    def __init__(
        self,
        *,
        work_pool: str | None = None,
        model_provider: Any = None,
    ):
        self._work_pool = work_pool
        self._model_provider = model_provider

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            streaming=False,  # Prefect doesn't natively stream LLM output
            parallel=True,
            durable=True,  # With Prefect server or Prefect Cloud
            replay=False,  # Prefect retries tasks, not deterministic replay
            checkpointing=True,  # Task results are persisted
            signals=True,  # pause_flow_run / resume_flow_run for HITL
            dispatch_join=True,
            distributed=True,  # With work pools and workers
        )

    def compile(self, node: Any, config: ExecutionConfig | None = None) -> PrefectRunnable:
        """Walk IR tree and generate a Prefect execution plan.

        The plan annotates each node with:
        - ``deterministic``: whether it runs as inline flow code
        - ``prefect_type``: "task", "flow", "inline", "pause", or "deployment"
        - ``cache_result``: whether Prefect should cache the task result
        """
        plan = self._walk_node(node)
        return PrefectRunnable(ir=node, node_plan=plan, config=config)

    async def run(self, compiled: PrefectRunnable, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute via Prefect flow.

        Creates and runs a Prefect flow from the compiled plan.
        Requires Prefect to be installed and optionally a running server.
        """
        try:
            import prefect  # type: ignore[import-not-found]  # noqa: F401 — verify prefect is installed
        except ImportError:
            raise ImportError(
                "prefect is required for PrefectBackend.run(). "
                "Install with: pip install adk-fluent[prefect]"
            ) from None

        # Execute the plan as a Prefect flow
        events = await self._execute_plan(compiled.node_plan, prompt, kwargs.get("session"))
        return events

    async def stream(self, compiled: PrefectRunnable, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Prefect doesn't natively support streaming.

        Falls back to run() and yields all events at once.
        """
        events = await self.run(compiled, prompt, **kwargs)
        for event in events:
            yield event

    async def _execute_plan(
        self,
        plan: list[dict[str, Any]],
        prompt: str,
        session: Any = None,
    ) -> list[AgentEvent]:
        """Interpret the execution plan and run it as Prefect tasks/flows."""
        from prefect import flow, task  # type: ignore[import-not-found]

        state: dict[str, Any] = {}
        if session and hasattr(session, "state"):
            state.update(session.state)
        events: list[AgentEvent] = []

        @task(name="llm_call", retries=2)
        async def llm_task(node_name: str, node_model: str, prompt_text: str, current_state: dict) -> dict:
            """Non-deterministic task: calls LLM via ModelProvider."""
            if self._model_provider is None:
                return {"text": f"[no model provider for '{node_name}']", "state": current_state}

            from adk_fluent.compute._protocol import GenerateConfig, Message

            messages = [Message(role="user", content=prompt_text)]
            result = await self._model_provider.generate(messages, None, GenerateConfig())
            return {"text": result.text, "state": current_state}

        @flow(name="adk_fluent_pipeline")
        async def pipeline_flow(prompt_text: str) -> list[dict]:
            results = []
            for node in plan:
                if node.get("prefect_type") == "task":
                    result = await llm_task(
                        node.get("name", "unknown"),
                        node.get("model", ""),
                        prompt_text,
                        state,
                    )
                    results.append(result)
            return results

        results = await pipeline_flow(prompt)
        for result in results:
            if isinstance(result, dict):
                events.append(
                    AgentEvent(
                        author=result.get("name", "agent"),
                        content=result.get("text", ""),
                        state_delta=result.get("state", {}),
                    )
                )

        # Mark last event as final
        if events and not any(e.is_final for e in events):
            events[-1] = AgentEvent(
                author=events[-1].author,
                content=events[-1].content,
                state_delta=events[-1].state_delta,
                is_final=True,
            )

        return events

    # ------------------------------------------------------------------
    # IR → Prefect plan
    # ------------------------------------------------------------------

    def _walk_node(self, node: Any) -> list[dict[str, Any]]:
        """Recursively classify nodes for Prefect execution."""
        node_type = type(node).__name__
        classifier = _NODE_CLASSIFIERS.get(node_type, _classify_unknown)
        return classifier(self, node)

    def _classify_agent(self, node: Any) -> list[dict[str, Any]]:
        """AgentNode → Task (non-deterministic: LLM call)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "AgentNode",
                "name": node.name,
                "prefect_type": "task",
                "deterministic": False,
                "cache_result": True,
                "model": getattr(node, "model", ""),
                "has_tools": bool(getattr(node, "tools", ())),
                "children": children_plans,
            }
        ]

    def _classify_sequence(self, node: Any) -> list[dict[str, Any]]:
        """SequenceNode → Flow body (sequential task calls)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "SequenceNode",
                "name": node.name,
                "prefect_type": "flow",
                "deterministic": True,
                "cache_result": False,
                "children": children_plans,
            }
        ]

    def _classify_parallel(self, node: Any) -> list[dict[str, Any]]:
        """ParallelNode → Concurrent task submission with .submit() + wait()."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "ParallelNode",
                "name": node.name,
                "prefect_type": "flow",
                "deterministic": True,
                "cache_result": False,
                "concurrency": "submit_wait",
                "children": children_plans,
            }
        ]

    def _classify_loop(self, node: Any) -> list[dict[str, Any]]:
        """LoopNode → Python for loop in flow body."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "LoopNode",
                "name": node.name,
                "prefect_type": "flow",
                "deterministic": True,
                "cache_result": False,
                "max_iterations": getattr(node, "max_iterations", None),
                "children": children_plans,
            }
        ]

    def _classify_transform(self, node: Any) -> list[dict[str, Any]]:
        """TransformNode → Inline flow code (pure function, no I/O)."""
        return [
            {
                "node_type": "TransformNode",
                "name": node.name,
                "prefect_type": "inline",
                "deterministic": True,
                "cache_result": False,
            }
        ]

    def _classify_tap(self, node: Any) -> list[dict[str, Any]]:
        """TapNode → Inline flow code (observation, no mutation)."""
        return [
            {
                "node_type": "TapNode",
                "name": node.name,
                "prefect_type": "inline",
                "deterministic": True,
                "cache_result": False,
            }
        ]

    def _classify_fallback(self, node: Any) -> list[dict[str, Any]]:
        """FallbackNode → try/except chain over tasks."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "FallbackNode",
                "name": node.name,
                "prefect_type": "flow",
                "deterministic": True,
                "cache_result": False,
                "children": children_plans,
            }
        ]

    def _classify_route(self, node: Any) -> list[dict[str, Any]]:
        """RouteNode → Conditional in flow body."""
        children_plans = []
        for _pred, child in getattr(node, "rules", ()):
            children_plans.extend(self._walk_node(child))
        if getattr(node, "default", None) is not None:
            children_plans.extend(self._walk_node(node.default))

        return [
            {
                "node_type": "RouteNode",
                "name": node.name,
                "prefect_type": "inline",
                "deterministic": True,
                "cache_result": False,
                "children": children_plans,
            }
        ]

    def _classify_gate(self, node: Any) -> list[dict[str, Any]]:
        """GateNode → pause_flow_run() for human-in-the-loop."""
        return [
            {
                "node_type": "GateNode",
                "name": node.name,
                "prefect_type": "pause",
                "deterministic": True,
                "cache_result": False,
                "message": getattr(node, "message", ""),
            }
        ]

    def _classify_dispatch(self, node: Any) -> list[dict[str, Any]]:
        """DispatchNode → run_deployment() (child flow)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "DispatchNode",
                "name": node.name,
                "prefect_type": "deployment",
                "deterministic": True,
                "cache_result": False,
                "task_names": getattr(node, "task_names", ()),
                "children": children_plans,
            }
        ]

    def _classify_join(self, node: Any) -> list[dict[str, Any]]:
        """JoinNode → Await deployment flow run handles."""
        return [
            {
                "node_type": "JoinNode",
                "name": node.name,
                "prefect_type": "inline",
                "deterministic": True,
                "cache_result": False,
                "target_names": getattr(node, "target_names", None),
            }
        ]

    def _classify_timeout(self, node: Any) -> list[dict[str, Any]]:
        """TimeoutNode → task(timeout_seconds=) wrapper."""
        children_plans = []
        if getattr(node, "body", None) is not None:
            children_plans.extend(self._walk_node(node.body))

        return [
            {
                "node_type": "TimeoutNode",
                "name": node.name,
                "prefect_type": "flow",
                "deterministic": True,
                "cache_result": False,
                "seconds": getattr(node, "seconds", 0),
                "children": children_plans,
            }
        ]

    def _classify_race(self, node: Any) -> list[dict[str, Any]]:
        """RaceNode → Submit tasks, wait for FIRST_COMPLETED."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "RaceNode",
                "name": node.name,
                "prefect_type": "flow",
                "deterministic": True,
                "cache_result": False,
                "children": children_plans,
            }
        ]

    def _classify_mapover(self, node: Any) -> list[dict[str, Any]]:
        """MapOverNode → task.map() over list items."""
        children_plans = []
        if getattr(node, "body", None) is not None:
            children_plans.extend(self._walk_node(node.body))

        return [
            {
                "node_type": "MapOverNode",
                "name": node.name,
                "prefect_type": "flow",
                "deterministic": True,
                "cache_result": False,
                "list_key": getattr(node, "list_key", ""),
                "children": children_plans,
            }
        ]


def _classify_unknown(backend: PrefectBackend, node: Any) -> list[dict[str, Any]]:
    """Unknown node type — treat as task (safe default)."""
    return [
        {
            "node_type": type(node).__name__,
            "name": getattr(node, "name", "unknown"),
            "prefect_type": "task",
            "deterministic": False,
            "cache_result": True,
        }
    ]


# Dispatch table for node classification
_NODE_CLASSIFIERS: dict[str, Any] = {
    "AgentNode": PrefectBackend._classify_agent,
    "SequenceNode": PrefectBackend._classify_sequence,
    "ParallelNode": PrefectBackend._classify_parallel,
    "LoopNode": PrefectBackend._classify_loop,
    "TransformNode": PrefectBackend._classify_transform,
    "TapNode": PrefectBackend._classify_tap,
    "FallbackNode": PrefectBackend._classify_fallback,
    "RouteNode": PrefectBackend._classify_route,
    "GateNode": PrefectBackend._classify_gate,
    "DispatchNode": PrefectBackend._classify_dispatch,
    "JoinNode": PrefectBackend._classify_join,
    "TimeoutNode": PrefectBackend._classify_timeout,
    "RaceNode": PrefectBackend._classify_race,
    "MapOverNode": PrefectBackend._classify_mapover,
}
