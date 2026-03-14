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
            ArtifactNode,
            CaptureNode,
            DispatchNode,
            FallbackNode,
            GateNode,
            JoinNode,
            MapOverNode,
            RaceNode,
            RouteNode,
            TapNode,
            TimeoutNode,
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
        elif isinstance(n, FallbackNode):
            lines.append(f'    {nid}[/"{_sanitize(name)} (fallback)"\\]')
        elif isinstance(n, RaceNode):
            lines.append(f'    {nid}{{{{"{_sanitize(name)} (race)"}}}}')
        elif isinstance(n, MapOverNode):
            list_key = getattr(n, "list_key", "?")
            lines.append(f'    {nid}(("{_sanitize(name)} (map {list_key})"))')
        elif isinstance(n, TimeoutNode):
            seconds = getattr(n, "seconds", "?")
            lines.append(f'    {nid}["{_sanitize(name)} (timeout {seconds}s)"]')
        elif isinstance(n, DispatchNode):
            task_count = len(getattr(n, "children", ()))
            lines.append(f'    {nid}>"{_sanitize(name)} dispatch({task_count})"]')
        elif isinstance(n, JoinNode):
            targets = getattr(n, "target_names", None)
            label = f"{name} join({', '.join(targets)})" if targets else f"{name} join(all)"
            lines.append(f'    {nid}(("{_sanitize(label)}"))')
        elif isinstance(n, ArtifactNode):
            op = getattr(n, "op", "?")
            fname = getattr(n, "filename", "?")
            label = f"{op} ({fname})" if fname else op
            lines.append(f'    {nid}{{{{"{_sanitize(label)} artifact"}}}}')
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

            # Artifact flow tracking
            if isinstance(n, ArtifactNode):
                for afn in getattr(n, "produces_artifact", frozenset()):
                    _producers.setdefault(f"artifact:{afn}", []).append(nid)
                for afn in getattr(n, "consumes_artifact", frozenset()):
                    _consumers.setdefault(f"artifact:{afn}", []).append(nid)
                # State keys produced/consumed by artifact ops
                for sk in getattr(n, "produces_state", frozenset()):
                    _producers.setdefault(sk, []).append(nid)
                for sk in getattr(n, "consumes_state", frozenset()):
                    _consumers.setdefault(sk, []).append(nid)

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


def ir_to_sequence_diagram(
    node: Any,
    *,
    show_data_flow: bool = True,
    show_context: bool = True,
) -> str:
    """Convert an IR node tree to a Mermaid sequence diagram.

    Unlike ``ir_to_mermaid`` which shows topology (what connects to what),
    this shows *execution order* — what calls what, in what sequence, and
    what data moves where.  Parallel branches are shown with ``par`` blocks.
    Loops are shown with ``loop`` blocks.  Route/Fallback uses ``alt``.

    Args:
        node: Root IR node.
        show_data_flow: Annotate state key writes as messages.
        show_context: Add notes showing each agent's context strategy.

    Returns:
        Mermaid ``sequenceDiagram`` source text.
    """
    from adk_fluent._ir import (
        ArtifactNode,
        CaptureNode,
        DispatchNode,
        FallbackNode,
        GateNode,
        JoinNode,
        MapOverNode,
        RaceNode,
        RouteNode,
        TapNode,
        TimeoutNode,
        TransformNode,
    )
    from adk_fluent._ir_generated import AgentNode, LoopNode, ParallelNode, SequenceNode

    lines: list[str] = ["sequenceDiagram"]
    _declared: set[str] = set()

    def _safe(name: str) -> str:
        """Make a name safe for Mermaid participant IDs."""
        return name.replace(" ", "_").replace("-", "_").replace(".", "_")

    def _label(name: str) -> str:
        return name.replace('"', "'")

    def _declare(n: Any) -> None:
        """Declare a participant if not already declared."""
        name = getattr(n, "name", None)
        if not name or name in _declared:
            return
        _declared.add(name)
        sid = _safe(name)
        if isinstance(n, AgentNode):
            lines.append(f"    participant {sid} as {_label(name)}")
        elif isinstance(n, (TransformNode, CaptureNode, TapNode)):
            lines.append(f"    participant {sid} as {_label(name)}")
        elif isinstance(n, RouteNode):
            lines.append(f"    participant {sid} as {_label(name)}")
        elif isinstance(n, GateNode):
            lines.append(f"    participant {sid} as {_label(name)}")

    def _context_note(n: Any) -> str | None:
        """Get a context description for an agent node."""
        if not show_context or not isinstance(n, AgentNode):
            return None
        context_spec = getattr(n, "context_spec", None)
        if context_spec is not None:
            try:
                from adk_fluent.testing.contracts import _context_description
                return _context_description(context_spec)
            except (ImportError, Exception):
                return str(context_spec)
        include = getattr(n, "include_contents", "default")
        if include != "default":
            return f"history: {include}"
        return None

    def _writes_label(n: Any) -> str | None:
        """Get a state-write description for an agent node."""
        if not show_data_flow:
            return None
        output_key = getattr(n, "output_key", None)
        writes = getattr(n, "writes_keys", frozenset())
        keys = set()
        if output_key:
            keys.add(output_key)
        keys.update(writes)
        if keys:
            return ", ".join(sorted(keys))
        return None

    def _collect_participants(n: Any) -> None:
        """Pre-scan tree to declare all participants in order."""
        if isinstance(n, SequenceNode):
            for child in getattr(n, "children", ()):
                _collect_participants(child)
        elif isinstance(n, ParallelNode):
            for child in getattr(n, "children", ()):
                _collect_participants(child)
        elif isinstance(n, LoopNode):
            for child in getattr(n, "children", ()):
                _collect_participants(child)
        elif isinstance(n, RouteNode):
            _declare(n)
            for _pred, agent_node in getattr(n, "rules", ()):
                _collect_participants(agent_node)
            default = getattr(n, "default", None)
            if default is not None:
                _collect_participants(default)
        elif isinstance(n, FallbackNode):
            for child in getattr(n, "children", ()):
                _collect_participants(child)
        elif isinstance(n, RaceNode):
            for child in getattr(n, "children", ()):
                _collect_participants(child)
        elif isinstance(n, (TimeoutNode, MapOverNode)):
            body = getattr(n, "body", None)
            if body:
                _collect_participants(body)
        else:
            _declare(n)

    def _emit(n: Any, caller: str | None = None) -> str | None:
        """Emit sequence diagram lines for a node. Returns the node's safe ID."""
        name = getattr(n, "name", None)
        sid = _safe(name) if name else None

        if isinstance(n, SequenceNode):
            children = getattr(n, "children", ())
            prev_sid = caller
            for child in children:
                child_sid = _emit(child, caller=prev_sid)
                if child_sid:
                    prev_sid = child_sid
            return prev_sid

        elif isinstance(n, ParallelNode):
            children = getattr(n, "children", ())
            if len(children) > 1:
                for i, child in enumerate(children):
                    if i == 0:
                        lines.append("    par Parallel execution")
                    else:
                        lines.append("    and")
                    _emit(child, caller=caller)
                lines.append("    end")
            elif children:
                _emit(children[0], caller=caller)
            return caller

        elif isinstance(n, LoopNode):
            max_iter = getattr(n, "max_iterations", None)
            label = f"max {max_iter} iterations" if max_iter else "loop"
            # Check for a loop predicate description
            lines.append(f"    loop {label}")
            children = getattr(n, "children", ())
            prev = caller
            for child in children:
                child_sid = _emit(child, caller=prev)
                if child_sid:
                    prev = child_sid
            lines.append("    end")
            return prev

        elif isinstance(n, AgentNode):
            if not sid:
                return caller
            # Incoming call
            if caller and caller != sid:
                writes = _writes_label(n)
                if writes:
                    lines.append(f"    {caller}->>{sid}: state[{writes}]")
                else:
                    lines.append(f"    {caller}->>{sid}: ")
            # Context note
            ctx = _context_note(n)
            if ctx:
                lines.append(f"    Note right of {sid}: {_label(ctx)}")
            # LLM call (self-call)
            lines.append(f"    {sid}->>{sid}: LLM call")
            # Output
            writes = _writes_label(n)
            if writes:
                lines.append(f"    Note right of {sid}: writes {writes}")
            return sid

        elif isinstance(n, CaptureNode):
            if not sid:
                return caller
            key = getattr(n, "key", "?")
            if caller:
                lines.append(f"    {caller}->>{sid}: capture")
            lines.append(f"    Note right of {sid}: state[{key}] = user input")
            return sid

        elif isinstance(n, TransformNode):
            if not sid:
                return caller
            affected = getattr(n, "affected_keys", None)
            label = f"transform({', '.join(sorted(affected))})" if affected else "transform"
            if caller:
                lines.append(f"    {caller}->>{sid}: {label}")
            else:
                lines.append(f"    Note right of {sid}: {label}")
            return sid

        elif isinstance(n, TapNode):
            if not sid:
                return caller
            if caller:
                lines.append(f"    {caller}->>{sid}: observe")
            lines.append(f"    Note right of {sid}: tap (no mutation)")
            return sid

        elif isinstance(n, RouteNode):
            if not sid:
                return caller
            route_key = getattr(n, "key", "?")
            if caller:
                lines.append(f"    {caller}->>{sid}: route on {route_key}")
            lines.append(f"    Note right of {sid}: deterministic (no LLM)")
            rules = getattr(n, "rules", ())
            default = getattr(n, "default", None)
            if rules or default:
                for i, (_pred, agent_node) in enumerate(rules):
                    branch_name = getattr(agent_node, "name", "?")
                    if i == 0:
                        lines.append(f"    alt {route_key} matches")
                    else:
                        lines.append(f"    else")
                    _emit(agent_node, caller=sid)
                if default:
                    lines.append(f"    else otherwise")
                    _emit(default, caller=sid)
                lines.append("    end")
            return sid

        elif isinstance(n, FallbackNode):
            children = getattr(n, "children", ())
            if children:
                for i, child in enumerate(children):
                    child_name = getattr(child, "name", "?")
                    if i == 0:
                        lines.append(f"    alt try {child_name}")
                    else:
                        lines.append(f"    else fallback to {child_name}")
                    _emit(child, caller=caller)
                lines.append("    end")
            return caller

        elif isinstance(n, GateNode):
            if not sid:
                return caller
            msg = getattr(n, "message", "Approval required")
            if caller:
                lines.append(f"    {caller}->>{sid}: gate check")
            lines.append(f"    Note right of {sid}: {_label(msg)}")
            return sid

        elif isinstance(n, RaceNode):
            children = getattr(n, "children", ())
            if children:
                lines.append("    par Race (first to finish wins)")
                for i, child in enumerate(children):
                    if i > 0:
                        lines.append("    and")
                    _emit(child, caller=caller)
                lines.append("    end")
            return caller

        elif isinstance(n, (TimeoutNode, MapOverNode)):
            body = getattr(n, "body", None)
            if body:
                if isinstance(n, TimeoutNode):
                    secs = getattr(n, "seconds", "?")
                    lines.append(f"    Note over {caller or sid}: timeout {secs}s")
                return _emit(body, caller=caller)
            return caller

        # Unknown node type — emit as generic
        if sid and caller:
            lines.append(f"    {caller}->>{sid}: ")
        return sid or caller

    # 1. Collect and declare all participants in order
    _collect_participants(node)

    # 2. Emit the sequence
    _emit(node)

    return "\n".join(lines)
