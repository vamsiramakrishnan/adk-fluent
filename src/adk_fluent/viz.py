"""Graph visualization for IR node trees."""
from __future__ import annotations

from typing import Any


def ir_to_mermaid(node: Any, *, show_contracts: bool = True) -> str:
    """Convert an IR node tree to a Mermaid graph definition.

    Args:
        node: Root IR node.
        show_contracts: Include data-flow annotations from produces/consumes.

    Returns:
        Mermaid graph source text.
    """
    lines = ["graph TD"]
    edges: list[str] = []
    contract_notes: list[str] = []
    _counter = [0]

    def _id():
        _counter[0] += 1
        return f"n{_counter[0]}"

    def _walk(n: Any) -> str:
        from adk_fluent._ir_generated import SequenceNode, ParallelNode, LoopNode, AgentNode
        from adk_fluent._ir import (
            TransformNode, TapNode, FallbackNode, RaceNode,
            GateNode, MapOverNode, TimeoutNode, RouteNode, TransferNode,
        )

        nid = _id()
        name = getattr(n, "name", "?")
        children = getattr(n, "children", ())

        # Node shape based on type
        if isinstance(n, AgentNode):
            lines.append(f'    {nid}["{name}"]')
        elif isinstance(n, SequenceNode):
            lines.append(f'    {nid}[["{name} (sequence)"]]')
        elif isinstance(n, ParallelNode):
            lines.append(f'    {nid}{{"{name} (parallel)"}}')
        elif isinstance(n, LoopNode):
            max_iter = getattr(n, "max_iterations", None)
            label = f"{name} (loop x{max_iter})" if max_iter else f"{name} (loop)"
            lines.append(f'    {nid}(("{label}"))')
        elif isinstance(n, TransformNode):
            lines.append(f'    {nid}>"{name} transform"]')
        elif isinstance(n, TapNode):
            lines.append(f'    {nid}>"{name} tap"]')
        elif isinstance(n, RouteNode):
            lines.append(f'    {nid}{{"{name} (route)"}}')
        elif isinstance(n, GateNode):
            lines.append(f'    {nid}{{{{"{name} (gate)"}}}}')
        elif isinstance(n, TransferNode):
            lines.append(f'    {nid}[/"{name} transfer"\\]')
        else:
            lines.append(f'    {nid}["{name}"]')

        # Contract annotations
        if show_contracts:
            produces = getattr(n, "produces_type", None)
            consumes = getattr(n, "consumes_type", None)
            if produces:
                contract_notes.append(f'    {nid} -. "produces {produces.__name__}" .-o {nid}')
            if consumes:
                contract_notes.append(f'    {nid} -. "consumes {consumes.__name__}" .-o {nid}')

        # Children — handle each node type's structure
        if isinstance(n, SequenceNode) and children:
            child_ids = []
            for child in children:
                cid = _walk(child)
                child_ids.append(cid)
            for i in range(len(child_ids) - 1):
                edges.append(f"    {child_ids[i]} --> {child_ids[i+1]}")
        elif children:
            for child in children:
                cid = _walk(child)
                edges.append(f"    {nid} --> {cid}")

        # Body (MapOverNode, TimeoutNode)
        body = getattr(n, "body", None)
        if body is not None:
            bid = _walk(body)
            edges.append(f"    {nid} --> {bid}")

        # Rules (RouteNode)
        if isinstance(n, RouteNode):
            for _pred, agent_node in getattr(n, "rules", ()):
                rid = _walk(agent_node)
                edges.append(f"    {nid} --> {rid}")
            default = getattr(n, "default", None)
            if default is not None:
                did = _walk(default)
                edges.append(f"    {nid} -.-> {did}")

        return nid

    _walk(node)
    return "\n".join(lines + edges + contract_notes)
