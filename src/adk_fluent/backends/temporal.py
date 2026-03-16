"""Temporal backend — compiles IR to Temporal workflows and activities.

This backend maps adk-fluent IR nodes to Temporal concepts:

- Deterministic nodes (TransformNode, TapNode, RouteNode) become inline
  workflow code that replays identically from history.
- Non-deterministic nodes (AgentNode = LLM calls) become Activities
  whose results are cached by Temporal and replayed on failure recovery.

Crash recovery: if a 10-step pipeline crashes at step 7, Temporal replays
steps 1-6 from cached activity results (zero LLM cost) and re-executes
only step 7+.

Requires: ``pip install adk-fluent[temporal]`` (adds ``temporalio``).

Usage::

    from temporalio.client import Client
    from adk_fluent.backends.temporal import TemporalBackend
    from adk_fluent.compile import compile

    client = await Client.connect("localhost:7233")
    backend = TemporalBackend(client=client, task_queue="agents")
    result = compile(ir, backend=backend)

Note: This module can be imported without temporalio installed — it only
fails at runtime when you try to compile or run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._ir import AgentEvent, ExecutionConfig
from adk_fluent.compile import EngineCapabilities

__all__ = ["TemporalBackend", "TemporalRunnable"]


@dataclass
class TemporalRunnable:
    """Compiled Temporal execution plan.

    Contains the workflow class, activity definitions, and worker
    configuration needed to execute the agent pipeline via Temporal.
    """

    ir: Any
    """Original IR tree for introspection."""

    node_plan: list[dict[str, Any]] = field(default_factory=list)
    """Execution plan: ordered list of node descriptors with determinism annotations."""

    config: ExecutionConfig | None = None
    """Original execution config."""


class TemporalBackend:
    """Compiles IR to Temporal workflows + activities.

    Deterministic vs. non-deterministic classification:

    - **Activities** (non-deterministic, cached on replay):
      AgentNode (LLM calls), tool executions

    - **Workflow code** (deterministic, replayed from history):
      TransformNode, TapNode, RouteNode, SequenceNode, ParallelNode,
      LoopNode, FallbackNode, GateNode (waits for signal)

    The backend generates an execution plan that a Temporal worker
    interprets. The actual workflow/activity registration happens at
    worker startup, not at compile time.
    """

    name: str = "temporal"

    def __init__(
        self,
        *,
        client: Any = None,
        task_queue: str = "adk-fluent",
        model_provider: Any = None,
    ):
        self._client = client
        self._task_queue = task_queue
        self._model_provider = model_provider

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            streaming=False,  # Temporal doesn't natively support streaming
            parallel=True,
            durable=True,
            replay=True,
            checkpointing=True,
            signals=True,  # For human-in-the-loop (GateNode)
            dispatch_join=True,
            distributed=True,
        )

    def compile(self, node: Any, config: ExecutionConfig | None = None) -> TemporalRunnable:
        """Walk IR tree and generate a Temporal execution plan.

        The plan annotates each node with:
        - ``deterministic``: whether it can be replayed from history
        - ``temporal_type``: "activity", "workflow", or "inline"
        - ``checkpoint``: whether Temporal should checkpoint after this node
        """
        plan = self._walk_node(node)
        return TemporalRunnable(ir=node, node_plan=plan, config=config)

    async def run(self, compiled: TemporalRunnable, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute via Temporal workflow.

        Starts a workflow on the Temporal server and waits for completion.
        Requires a running Temporal worker with registered activities.
        """
        if self._client is None:
            raise RuntimeError(
                "TemporalBackend.run() requires a Temporal client. "
                "Pass client= to the constructor, or use compile() for "
                "offline plan generation."
            )

        try:
            from temporalio.client import Client as _Client
        except ImportError:
            raise ImportError(
                "temporalio is required for TemporalBackend.run(). "
                "Install with: pip install adk-fluent[temporal]"
            ) from None

        # Start workflow
        workflow_id = f"adk-fluent-{_generate_id()}"
        handle = await self._client.start_workflow(
            "adk_fluent_agent_workflow",
            args=[prompt, compiled.node_plan],
            id=workflow_id,
            task_queue=self._task_queue,
        )
        result = await handle.result()
        return result

    async def stream(self, compiled: TemporalRunnable, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Temporal doesn't natively support streaming.

        Falls back to run() and yields all events at once.
        """
        events = await self.run(compiled, prompt, **kwargs)
        for event in events:
            yield event

    # ------------------------------------------------------------------
    # IR → Temporal plan
    # ------------------------------------------------------------------

    def _walk_node(self, node: Any) -> list[dict[str, Any]]:
        """Recursively classify nodes as deterministic or non-deterministic."""
        node_type = type(node).__name__
        classifier = _NODE_CLASSIFIERS.get(node_type, _classify_unknown)
        return classifier(self, node)

    def _classify_agent(self, node: Any) -> list[dict[str, Any]]:
        """AgentNode → Activity (non-deterministic: LLM call)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "AgentNode",
                "name": node.name,
                "temporal_type": "activity",
                "deterministic": False,
                "checkpoint": True,
                "model": getattr(node, "model", ""),
                "has_tools": bool(getattr(node, "tools", ())),
                "children": children_plans,
            }
        ]

    def _classify_sequence(self, node: Any) -> list[dict[str, Any]]:
        """SequenceNode → Workflow body (deterministic orchestration)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "SequenceNode",
                "name": node.name,
                "temporal_type": "workflow",
                "deterministic": True,
                "checkpoint": False,
                "children": children_plans,
            }
        ]

    def _classify_parallel(self, node: Any) -> list[dict[str, Any]]:
        """ParallelNode → Workflow with concurrent activities."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "ParallelNode",
                "name": node.name,
                "temporal_type": "workflow",
                "deterministic": True,
                "checkpoint": False,
                "children": children_plans,
            }
        ]

    def _classify_loop(self, node: Any) -> list[dict[str, Any]]:
        """LoopNode → Workflow loop (each iteration checkpointed)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "LoopNode",
                "name": node.name,
                "temporal_type": "workflow",
                "deterministic": True,
                "checkpoint": True,  # Checkpoint after each iteration
                "max_iterations": getattr(node, "max_iterations", None),
                "children": children_plans,
            }
        ]

    def _classify_transform(self, node: Any) -> list[dict[str, Any]]:
        """TransformNode → Inline workflow code (deterministic, no I/O)."""
        return [
            {
                "node_type": "TransformNode",
                "name": node.name,
                "temporal_type": "inline",
                "deterministic": True,
                "checkpoint": False,
            }
        ]

    def _classify_tap(self, node: Any) -> list[dict[str, Any]]:
        """TapNode → Inline workflow code (observation, no mutation)."""
        return [
            {
                "node_type": "TapNode",
                "name": node.name,
                "temporal_type": "inline",
                "deterministic": True,
                "checkpoint": False,
            }
        ]

    def _classify_fallback(self, node: Any) -> list[dict[str, Any]]:
        """FallbackNode → Workflow with try/except chain."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "FallbackNode",
                "name": node.name,
                "temporal_type": "workflow",
                "deterministic": True,
                "checkpoint": True,  # Checkpoint after each attempt
                "children": children_plans,
            }
        ]

    def _classify_route(self, node: Any) -> list[dict[str, Any]]:
        """RouteNode → Inline workflow code (deterministic routing)."""
        children_plans = []
        for _pred, child in getattr(node, "rules", ()):
            children_plans.extend(self._walk_node(child))
        if getattr(node, "default", None) is not None:
            children_plans.extend(self._walk_node(node.default))

        return [
            {
                "node_type": "RouteNode",
                "name": node.name,
                "temporal_type": "inline",
                "deterministic": True,
                "checkpoint": False,
                "children": children_plans,
            }
        ]

    def _classify_dispatch(self, node: Any) -> list[dict[str, Any]]:
        """DispatchNode → Child workflow (durable, survives crashes)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "DispatchNode",
                "name": node.name,
                "temporal_type": "child_workflow",
                "deterministic": True,
                "checkpoint": True,
                "task_names": getattr(node, "task_names", ()),
                "children": children_plans,
            }
        ]

    def _classify_join(self, node: Any) -> list[dict[str, Any]]:
        """JoinNode → Await child workflow handles."""
        return [
            {
                "node_type": "JoinNode",
                "name": node.name,
                "temporal_type": "inline",
                "deterministic": True,
                "checkpoint": True,
                "target_names": getattr(node, "target_names", None),
            }
        ]

    def _classify_gate(self, node: Any) -> list[dict[str, Any]]:
        """GateNode → Signal wait (human-in-the-loop)."""
        return [
            {
                "node_type": "GateNode",
                "name": node.name,
                "temporal_type": "signal_wait",
                "deterministic": True,
                "checkpoint": True,
                "message": getattr(node, "message", ""),
            }
        ]

    def _classify_timeout(self, node: Any) -> list[dict[str, Any]]:
        """TimeoutNode → Activity timeout wrapper."""
        children_plans = []
        if getattr(node, "body", None) is not None:
            children_plans.extend(self._walk_node(node.body))

        return [
            {
                "node_type": "TimeoutNode",
                "name": node.name,
                "temporal_type": "workflow",
                "deterministic": True,
                "checkpoint": False,
                "seconds": getattr(node, "seconds", 0),
                "children": children_plans,
            }
        ]

    def _classify_race(self, node: Any) -> list[dict[str, Any]]:
        """RaceNode → First-completed over parallel activities."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "RaceNode",
                "name": node.name,
                "temporal_type": "workflow",
                "deterministic": True,
                "checkpoint": False,
                "children": children_plans,
            }
        ]

    def _classify_mapover(self, node: Any) -> list[dict[str, Any]]:
        """MapOverNode → Workflow loop, each item = activity."""
        children_plans = []
        if getattr(node, "body", None) is not None:
            children_plans.extend(self._walk_node(node.body))

        return [
            {
                "node_type": "MapOverNode",
                "name": node.name,
                "temporal_type": "workflow",
                "deterministic": True,
                "checkpoint": True,
                "list_key": getattr(node, "list_key", ""),
                "children": children_plans,
            }
        ]


def _classify_unknown(backend: TemporalBackend, node: Any) -> list[dict[str, Any]]:
    """Unknown node type — treat as activity (safe default)."""
    return [
        {
            "node_type": type(node).__name__,
            "name": getattr(node, "name", "unknown"),
            "temporal_type": "activity",
            "deterministic": False,
            "checkpoint": True,
        }
    ]


def _generate_id() -> str:
    """Generate a short unique ID."""
    from uuid import uuid4

    return uuid4().hex[:12]


# Dispatch table for node classification
_NODE_CLASSIFIERS: dict[str, Any] = {
    "AgentNode": TemporalBackend._classify_agent,
    "SequenceNode": TemporalBackend._classify_sequence,
    "ParallelNode": TemporalBackend._classify_parallel,
    "LoopNode": TemporalBackend._classify_loop,
    "TransformNode": TemporalBackend._classify_transform,
    "TapNode": TemporalBackend._classify_tap,
    "FallbackNode": TemporalBackend._classify_fallback,
    "RouteNode": TemporalBackend._classify_route,
    "DispatchNode": TemporalBackend._classify_dispatch,
    "JoinNode": TemporalBackend._classify_join,
    "GateNode": TemporalBackend._classify_gate,
    "TimeoutNode": TemporalBackend._classify_timeout,
    "RaceNode": TemporalBackend._classify_race,
    "MapOverNode": TemporalBackend._classify_mapover,
}
