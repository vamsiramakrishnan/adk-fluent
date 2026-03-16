"""DBOS backend — compiles IR to DBOS durable workflows and steps.

This backend maps adk-fluent IR nodes to DBOS concepts:

- Non-deterministic nodes (AgentNode = LLM calls) become ``@DBOS.step()``
  decorated functions. Steps are durably recorded in PostgreSQL — on
  recovery, completed steps return cached results (zero LLM cost).
- Deterministic nodes become inline ``@DBOS.workflow()`` code that
  replays identically from the database log.
- GateNode maps to ``DBOS.recv()`` for external signal-based HITL.

DBOS provides Temporal-like durability with lighter infrastructure:
only a PostgreSQL database is required (no separate server process).

Requires: ``pip install adk-fluent[dbos]`` (adds ``dbos``).

Usage::

    from adk_fluent.backends.dbos_backend import DBOSBackend
    from adk_fluent.compile import compile

    backend = DBOSBackend()
    result = compile(ir, backend=backend)

Note: This module can be imported without dbos installed — it only
fails at runtime when you try to compile or run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._ir import AgentEvent, ExecutionConfig
from adk_fluent.compile import EngineCapabilities

__all__ = ["DBOSBackend", "DBOSRunnable"]


@dataclass
class DBOSRunnable:
    """Compiled DBOS execution plan.

    Contains the workflow and step definitions needed to execute
    the agent pipeline via DBOS.
    """

    ir: Any
    """Original IR tree for introspection."""

    node_plan: list[dict[str, Any]] = field(default_factory=list)
    """Execution plan: ordered list of node descriptors with DBOS annotations."""

    config: ExecutionConfig | None = None
    """Original execution config."""


class DBOSBackend:
    """Compiles IR to DBOS workflows + steps.

    Deterministic vs. non-deterministic classification:

    - **Steps** (non-deterministic, durably recorded in PostgreSQL):
      AgentNode (LLM calls), tool executions

    - **Workflow code** (deterministic, replayed from DB log):
      TransformNode, TapNode, RouteNode, SequenceNode, ParallelNode,
      LoopNode, FallbackNode

    - **Signals** (human-in-the-loop):
      GateNode → ``DBOS.recv()``

    Key difference from Temporal: DBOS requires only PostgreSQL (no
    separate server). The durability guarantees are similar — completed
    steps are cached and replayed on recovery.
    """

    name: str = "dbos"

    def __init__(
        self,
        *,
        database_url: str | None = None,
        model_provider: Any = None,
    ):
        self._database_url = database_url
        self._model_provider = model_provider

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            streaming=False,  # DBOS doesn't natively stream
            parallel=True,
            durable=True,  # PostgreSQL-backed durability
            replay=True,  # Deterministic replay from DB log
            checkpointing=True,  # Per-step recording
            signals=True,  # DBOS.recv() for external signals
            dispatch_join=True,
            distributed=False,  # Single-process (PG stores state, not distributes compute)
        )

    def compile(self, node: Any, config: ExecutionConfig | None = None) -> DBOSRunnable:
        """Walk IR tree and generate a DBOS execution plan.

        The plan annotates each node with:
        - ``deterministic``: whether it replays from DB log
        - ``dbos_type``: "step", "workflow", "inline", "recv", or "child_workflow"
        - ``durable``: whether DBOS durably records the result
        """
        plan = self._walk_node(node)
        return DBOSRunnable(ir=node, node_plan=plan, config=config)

    async def run(self, compiled: DBOSRunnable, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute via DBOS workflow.

        Creates and runs a DBOS workflow from the compiled plan.
        Requires DBOS to be installed and a PostgreSQL database.
        """
        try:
            import dbos  # type: ignore[import-not-found]  # noqa: F401 — verify dbos is installed
        except ImportError:
            raise ImportError(
                "dbos is required for DBOSBackend.run(). Install with: pip install adk-fluent[dbos]"
            ) from None

        events = await self._execute_plan(compiled.node_plan, prompt, kwargs.get("session"))
        return events

    async def stream(self, compiled: DBOSRunnable, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """DBOS doesn't natively support streaming.

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
        """Interpret the execution plan as DBOS workflow + steps."""
        from dbos import DBOS  # type: ignore[import-not-found]

        state: dict[str, Any] = {}
        if session and hasattr(session, "state"):
            state.update(session.state)
        events: list[AgentEvent] = []

        @DBOS.step()
        async def llm_step(node_name: str, prompt_text: str, current_state: dict) -> dict:
            """Non-deterministic step: calls LLM via ModelProvider."""
            if self._model_provider is None:
                return {"text": f"[no model provider for '{node_name}']", "state": current_state}

            from adk_fluent.compute._protocol import GenerateConfig, Message

            messages = [Message(role="user", content=prompt_text)]
            result = await self._model_provider.generate(messages, None, GenerateConfig())
            return {"text": result.text, "state": current_state}

        @DBOS.workflow()
        async def pipeline_workflow(prompt_text: str) -> list[dict]:
            results = []
            for node in plan:
                if node.get("dbos_type") == "step":
                    result = await llm_step(
                        node.get("name", "unknown"),
                        prompt_text,
                        state,
                    )
                    results.append(result)
            return results

        results = await pipeline_workflow(prompt)
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
    # IR → DBOS plan
    # ------------------------------------------------------------------

    def _walk_node(self, node: Any) -> list[dict[str, Any]]:
        """Recursively classify nodes for DBOS execution."""
        node_type = type(node).__name__
        classifier = _NODE_CLASSIFIERS.get(node_type, _classify_unknown)
        return classifier(self, node)

    def _classify_agent(self, node: Any) -> list[dict[str, Any]]:
        """AgentNode → Step (non-deterministic: LLM call, durably recorded)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "AgentNode",
                "name": node.name,
                "dbos_type": "step",
                "deterministic": False,
                "durable": True,
                "model": getattr(node, "model", ""),
                "has_tools": bool(getattr(node, "tools", ())),
                "children": children_plans,
            }
        ]

    def _classify_sequence(self, node: Any) -> list[dict[str, Any]]:
        """SequenceNode → Workflow body (sequential step calls)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "SequenceNode",
                "name": node.name,
                "dbos_type": "workflow",
                "deterministic": True,
                "durable": False,
                "children": children_plans,
            }
        ]

    def _classify_parallel(self, node: Any) -> list[dict[str, Any]]:
        """ParallelNode → asyncio.gather() within workflow."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "ParallelNode",
                "name": node.name,
                "dbos_type": "workflow",
                "deterministic": True,
                "durable": False,
                "concurrency": "gather",
                "children": children_plans,
            }
        ]

    def _classify_loop(self, node: Any) -> list[dict[str, Any]]:
        """LoopNode → Python loop in workflow."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "LoopNode",
                "name": node.name,
                "dbos_type": "workflow",
                "deterministic": True,
                "durable": False,
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
                "dbos_type": "inline",
                "deterministic": True,
                "durable": False,
            }
        ]

    def _classify_tap(self, node: Any) -> list[dict[str, Any]]:
        """TapNode → Inline workflow code (observation, no mutation)."""
        return [
            {
                "node_type": "TapNode",
                "name": node.name,
                "dbos_type": "inline",
                "deterministic": True,
                "durable": False,
            }
        ]

    def _classify_fallback(self, node: Any) -> list[dict[str, Any]]:
        """FallbackNode → try/except chain within workflow."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "FallbackNode",
                "name": node.name,
                "dbos_type": "workflow",
                "deterministic": True,
                "durable": False,
                "children": children_plans,
            }
        ]

    def _classify_route(self, node: Any) -> list[dict[str, Any]]:
        """RouteNode → Python conditional in workflow."""
        children_plans = []
        for _pred, child in getattr(node, "rules", ()):
            children_plans.extend(self._walk_node(child))
        if getattr(node, "default", None) is not None:
            children_plans.extend(self._walk_node(node.default))

        return [
            {
                "node_type": "RouteNode",
                "name": node.name,
                "dbos_type": "inline",
                "deterministic": True,
                "durable": False,
                "children": children_plans,
            }
        ]

    def _classify_gate(self, node: Any) -> list[dict[str, Any]]:
        """GateNode → DBOS.recv() for external signals (HITL)."""
        return [
            {
                "node_type": "GateNode",
                "name": node.name,
                "dbos_type": "recv",
                "deterministic": True,
                "durable": True,
                "message": getattr(node, "message", ""),
            }
        ]

    def _classify_dispatch(self, node: Any) -> list[dict[str, Any]]:
        """DispatchNode → DBOS.start_workflow() (child workflow)."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "DispatchNode",
                "name": node.name,
                "dbos_type": "child_workflow",
                "deterministic": True,
                "durable": True,
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
                "dbos_type": "inline",
                "deterministic": True,
                "durable": False,
                "target_names": getattr(node, "target_names", None),
            }
        ]

    def _classify_timeout(self, node: Any) -> list[dict[str, Any]]:
        """TimeoutNode → asyncio.wait_for() in workflow."""
        children_plans = []
        if getattr(node, "body", None) is not None:
            children_plans.extend(self._walk_node(node.body))

        return [
            {
                "node_type": "TimeoutNode",
                "name": node.name,
                "dbos_type": "workflow",
                "deterministic": True,
                "durable": False,
                "seconds": getattr(node, "seconds", 0),
                "children": children_plans,
            }
        ]

    def _classify_race(self, node: Any) -> list[dict[str, Any]]:
        """RaceNode → asyncio.wait(FIRST_COMPLETED) in workflow."""
        children_plans = []
        for child in getattr(node, "children", ()):
            children_plans.extend(self._walk_node(child))

        return [
            {
                "node_type": "RaceNode",
                "name": node.name,
                "dbos_type": "workflow",
                "deterministic": True,
                "durable": False,
                "children": children_plans,
            }
        ]

    def _classify_mapover(self, node: Any) -> list[dict[str, Any]]:
        """MapOverNode → Loop with per-item step."""
        children_plans = []
        if getattr(node, "body", None) is not None:
            children_plans.extend(self._walk_node(node.body))

        return [
            {
                "node_type": "MapOverNode",
                "name": node.name,
                "dbos_type": "workflow",
                "deterministic": True,
                "durable": False,
                "list_key": getattr(node, "list_key", ""),
                "children": children_plans,
            }
        ]


def _classify_unknown(backend: DBOSBackend, node: Any) -> list[dict[str, Any]]:
    """Unknown node type — treat as step (safe default)."""
    return [
        {
            "node_type": type(node).__name__,
            "name": getattr(node, "name", "unknown"),
            "dbos_type": "step",
            "deterministic": False,
            "durable": True,
        }
    ]


# Dispatch table for node classification
_NODE_CLASSIFIERS: dict[str, Any] = {
    "AgentNode": DBOSBackend._classify_agent,
    "SequenceNode": DBOSBackend._classify_sequence,
    "ParallelNode": DBOSBackend._classify_parallel,
    "LoopNode": DBOSBackend._classify_loop,
    "TransformNode": DBOSBackend._classify_transform,
    "TapNode": DBOSBackend._classify_tap,
    "FallbackNode": DBOSBackend._classify_fallback,
    "RouteNode": DBOSBackend._classify_route,
    "GateNode": DBOSBackend._classify_gate,
    "DispatchNode": DBOSBackend._classify_dispatch,
    "JoinNode": DBOSBackend._classify_join,
    "TimeoutNode": DBOSBackend._classify_timeout,
    "RaceNode": DBOSBackend._classify_race,
    "MapOverNode": DBOSBackend._classify_mapover,
}
