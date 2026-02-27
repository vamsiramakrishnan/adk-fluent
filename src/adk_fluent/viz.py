"""Graph visualization for IR node trees.

Generates Mermaid diagrams with:
- Node topology (agent shapes, sequence/parallel/loop structures)
- Contract annotations (produces/consumes type schemas)
- Data flow edges showing which state keys flow between agents
- Context strategy annotations showing what each agent sees
"""

from __future__ import annotations

from typing import Any


def ir_to_mermaid(
    node: Any,
    *,
    show_contracts: bool = True,
    show_data_flow: bool = True,
    show_context: bool = False,
) -> str:
    """Convert an IR node tree to a Mermaid graph definition.

    Args:
        node: Root IR node.
        show_contracts: Include data-flow annotations from produces/consumes.
        show_data_flow: Include edges showing state key flow between agents.
        show_context: Include annotations showing each agent's context strategy.

    Returns:
        Mermaid graph source text.
    """
    lines = ["graph TD"]
    edges: list[str] = []
    contract_notes: list[str] = []
    data_flow_edges: list[str] = []
    context_notes: list[str] = []
    _counter = [0]

    # Track which nodes produce/consume which keys, for data flow edges
    _producers: dict[str, list[str]] = {}  # key -> [node_id, ...]
    _consumers: dict[str, list[str]] = {}  # key -> [node_id, ...]

    def _id():
        _counter[0] += 1
        return f"n{_counter[0]}"

    def _sanitize(text: str) -> str:
        """Sanitize text for Mermaid labels."""
        return text.replace('"', "'").replace("\n", " ")

    def _walk(n: Any) -> str:
        from adk_fluent._ir import (
            CaptureNode,
            GateNode,
            RouteNode,
            TapNode,
            TransferNode,
            TransformNode,
        )
        from adk_fluent._ir_generated import AgentNode, LoopNode, ParallelNode, SequenceNode

        nid = _id()
        name = getattr(n, "name", "?")
        children = getattr(n, "children", ())

        # Node shape based on type
        if isinstance(n, AgentNode):
            lines.append(f'    {nid}["{_sanitize(name)}"]')
        elif isinstance(n, SequenceNode):
            lines.append(f'    {nid}[["{_sanitize(name)} (sequence)"]]')
        elif isinstance(n, ParallelNode):
            lines.append(f'    {nid}{{"{_sanitize(name)} (parallel)"}}')
        elif isinstance(n, LoopNode):
            max_iter = getattr(n, "max_iterations", None)
            label = f"{name} (loop x{max_iter})" if max_iter else f"{name} (loop)"
            lines.append(f'    {nid}(("{_sanitize(label)}"))')
        elif isinstance(n, TransformNode):
            lines.append(f'    {nid}>"{_sanitize(name)} transform"]')
        elif isinstance(n, TapNode):
            lines.append(f'    {nid}>"{_sanitize(name)} tap"]')
        elif isinstance(n, CaptureNode):
            capture_key = getattr(n, "key", "?")
            lines.append(f'    {nid}>"{_sanitize(name)} capture({capture_key})"]')
        elif isinstance(n, RouteNode):
            lines.append(f'    {nid}{{"{_sanitize(name)} (route)"}}')
        elif isinstance(n, GateNode):
            lines.append(f'    {nid}{{{{"{_sanitize(name)} (gate)"}}}}')
        elif isinstance(n, TransferNode):
            lines.append(f'    {nid}[/"{_sanitize(name)} transfer"\\]')
        else:
            lines.append(f'    {nid}["{_sanitize(name)}"]')

        # Contract annotations
        if show_contracts:
            produces = getattr(n, "produces_type", None)
            consumes = getattr(n, "consumes_type", None)
            if produces:
                contract_notes.append(f'    {nid} -. "produces {produces.__name__}" .-o {nid}')
            if consumes:
                contract_notes.append(f'    {nid} -. "consumes {consumes.__name__}" .-o {nid}')

        # Data flow tracking
        if show_data_flow:
            # Track what this node produces
            output_key = getattr(n, "output_key", None)
            if output_key:
                _producers.setdefault(output_key, []).append(nid)

            if isinstance(n, CaptureNode):
                capture_key = getattr(n, "key", None)
                if capture_key:
                    _producers.setdefault(capture_key, []).append(nid)

            if isinstance(n, TransformNode):
                affected = getattr(n, "affected_keys", None)
                if affected:
                    for key in affected:
                        _producers.setdefault(key, []).append(nid)

            writes = getattr(n, "writes_keys", frozenset())
            for key in writes:
                _producers.setdefault(key, []).append(nid)

            # Track what this node consumes (from template vars and reads_keys)
            instruction = getattr(n, "instruction", "")
            if isinstance(instruction, str) and instruction:
                import re

                template_vars = re.findall(r"\{(\w+)\??\}", instruction)
                for var in template_vars:
                    _consumers.setdefault(var, []).append(nid)

            reads = getattr(n, "reads_keys", frozenset())
            for key in reads:
                _consumers.setdefault(key, []).append(nid)

            if isinstance(n, RouteNode):
                route_key = getattr(n, "key", None)
                if route_key:
                    _consumers.setdefault(route_key, []).append(nid)

        # Context annotations
        if show_context and isinstance(n, AgentNode):
            context_spec = getattr(n, "context_spec", None)
            if context_spec is not None:
                from adk_fluent.testing.contracts import _context_description

                ctx_desc = _context_description(context_spec)
                context_notes.append(f'    {nid} -. "{_sanitize(ctx_desc)}" .-o {nid}')
            else:
                include = getattr(n, "include_contents", "default")
                if include != "default":
                    context_notes.append(f'    {nid} -. "history: {include}" .-o {nid}')

        # Children — handle each node type's structure
        if isinstance(n, SequenceNode) and children:
            child_ids = []
            for child in children:
                cid = _walk(child)
                child_ids.append(cid)
            for i in range(len(child_ids) - 1):
                edges.append(f"    {child_ids[i]} --> {child_ids[i + 1]}")
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

    # Build data flow edges: producer --"key"--> consumer
    if show_data_flow:
        seen_flow_edges: set[str] = set()
        for key in sorted(set(_producers.keys()) & set(_consumers.keys())):
            for prod_id in _producers[key]:
                for cons_id in _consumers[key]:
                    if prod_id != cons_id:
                        edge_key = f"{prod_id}-{key}-{cons_id}"
                        if edge_key not in seen_flow_edges:
                            seen_flow_edges.add(edge_key)
                            data_flow_edges.append(f'    {prod_id} -. "{key}" .-> {cons_id}')

    result_parts = lines + edges
    if contract_notes:
        result_parts.extend(contract_notes)
    if data_flow_edges:
        result_parts.extend(data_flow_edges)
    if context_notes:
        result_parts.extend(context_notes)

    return "\n".join(result_parts)
