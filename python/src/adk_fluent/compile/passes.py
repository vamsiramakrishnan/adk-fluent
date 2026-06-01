"""IR optimization passes.

Passes transform an IR tree before it is lowered to a backend-specific
runnable. They operate on frozen dataclasses (IR nodes) and return new
IR trees — the originals are never mutated.

Current passes:

- ``fuse_transforms``: Merge adjacent TransformNodes into a single node.
- ``validate_contracts``: Run static contract checks (delegates to
  ``testing.contracts``).

The ``run_passes`` entry point runs fuse_transforms. Contract validation
is advisory and should be invoked explicitly via ``validate_contracts()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from adk_fluent._ir import TransformNode
from adk_fluent._ir_generated import SequenceNode

__all__ = [
    "run_passes",
    "fuse_transforms",
    "validate_contracts",
    "annotate_checkpoints",
    "CheckpointAnnotation",
]


# ======================================================================
# Pass: fuse adjacent TransformNodes
# ======================================================================


def _is_sequence_node(node: Any) -> bool:
    """Check if node is a SequenceNode."""
    return isinstance(node, SequenceNode)


def _get_children(node: Any) -> tuple:
    """Get children tuple from a node."""
    return getattr(node, "children", ())


def fuse_transforms(ir: Any) -> Any:
    """Merge adjacent TransformNodes in sequences into a single TransformNode.

    Two adjacent TransformNodes with ``semantics="merge"`` can be fused
    into one node whose ``fn`` applies both transforms in order. This
    reduces the number of agents compiled by the backend.
    """
    if _is_sequence_node(ir):
        children = _get_children(ir)
        if len(children) < 2:
            # Recurse into single child
            new_children = tuple(_recurse_fuse(c) for c in children)
            return replace(ir, children=new_children)

        fused: list[Any] = []
        i = 0
        while i < len(children):
            child = children[i]
            if isinstance(child, TransformNode) and child.semantics == "merge":
                # Collect consecutive merge TransformNodes
                group = [child]
                j = i + 1
                while j < len(children):
                    next_child = children[j]
                    if isinstance(next_child, TransformNode) and next_child.semantics == "merge":
                        group.append(next_child)
                        j += 1
                    else:
                        break
                if len(group) > 1:
                    # Fuse into a single TransformNode
                    fused_fn = _compose_transform_fns([g.fn for g in group])
                    # Merge affected_keys and reads_keys
                    all_writes = frozenset().union(*(g.affected_keys or frozenset() for g in group))
                    all_reads = frozenset().union(*(g.reads_keys or frozenset() for g in group))
                    fused_node = TransformNode(
                        name=f"_fused_{'_'.join(g.name for g in group)}",
                        fn=fused_fn,
                        semantics="merge",
                        affected_keys=all_writes or None,
                        reads_keys=all_reads or None,
                    )
                    fused.append(fused_node)
                else:
                    fused.append(child)
                i = j
            else:
                fused.append(_recurse_fuse(child))
                i += 1

        return replace(ir, children=tuple(fused))

    return _recurse_fuse(ir)


def _recurse_fuse(node: Any) -> Any:
    """Recursively apply fuse_transforms to children."""
    children = _get_children(node)
    if not children:
        return node
    new_children = tuple(fuse_transforms(c) for c in children)
    if new_children == children:
        return node
    return replace(node, children=new_children)


def _compose_transform_fns(fns: list) -> Any:
    """Compose a list of transform functions into a single function."""

    def _composed(state: dict) -> dict:
        result = state
        for fn in fns:
            result = fn(result)
        return result

    return _composed


# ======================================================================
# Pass: validate contracts
# ======================================================================


def validate_contracts(ir: Any) -> list:
    """Run static contract checks on the IR tree.

    Delegates to ``testing.contracts.check_contracts()`` and returns
    a list of violation dicts. Does NOT modify the IR.
    """
    try:
        from adk_fluent.testing.contracts import check_contracts

        return check_contracts(ir)
    except ImportError:
        return []


# ======================================================================
# Pass: annotate checkpoints
# ======================================================================


# Node types whose execution performs I/O (LLM calls, tool calls, remote
# agents, child-workflow dispatch). These are the natural activity /
# checkpoint boundaries for durable backends: their results must be
# recorded so a crashed workflow can replay deterministically without
# re-issuing the (expensive, non-deterministic) call.
_IO_NODE_TYPES = frozenset(
    {
        "AgentNode",  # LLM call
        "RemoteA2aNode",  # remote agent call
        "MapOverNode",  # iterates an LLM body over a list
        "DispatchNode",  # launches a durable child workflow
        "GateNode",  # waits for an external signal (human-in-the-loop)
    }
)

# Everything else (SequenceNode, ParallelNode, LoopNode, FallbackNode,
# RaceNode, RouteNode, TransformNode, TapNode, JoinNode, TimeoutNode, ...) is
# deterministic orchestration / pure compute: it needs no checkpoint of its
# own — its I/O-bearing descendants are tagged individually.


@dataclass(frozen=True)
class CheckpointAnnotation:
    """Result of :func:`annotate_checkpoints`.

    Carries the (unchanged) IR tree plus a checkpoint map that durable
    backends consume to decide activity / step boundaries. ``checkpoints``
    maps a stable node *path* (a tuple of child indices from the root) to a
    descriptor with the node name, type, and whether it is a checkpoint
    (I/O) boundary. ``boundary_names`` is the convenience set of node names
    that are checkpoint boundaries.
    """

    ir: Any
    checkpoints: dict[tuple[int, ...], dict[str, Any]] = field(default_factory=dict)
    boundary_names: frozenset[str] = frozenset()

    def is_boundary(self, name: str) -> bool:
        """Return True if a node with ``name`` is a checkpoint boundary."""
        return name in self.boundary_names

    def __iter__(self):
        """Allow ``ir_tree, _ = annotate_checkpoints(...)``-style use is not
        intended; iterate descriptor entries instead."""
        return iter(self.checkpoints.values())


def _child_nodes(node: Any) -> list[Any]:
    """Return the ordered child IR nodes of any node type.

    Handles the three shapes used across the IR: ``children`` tuples,
    a single ``body`` node, and ``RouteNode.rules`` (predicate, child) pairs
    plus an optional ``default``.
    """
    children: list[Any] = list(getattr(node, "children", ()) or ())
    body = getattr(node, "body", None)
    if body is not None:
        children.append(body)
    for entry in getattr(node, "rules", ()) or ():
        # RouteNode rules are (predicate, child) tuples.
        if isinstance(entry, tuple) and len(entry) == 2:
            children.append(entry[1])
    default = getattr(node, "default", None)
    if default is not None and hasattr(default, "name"):
        children.append(default)
    return children


def _is_io_node(node: Any) -> bool:
    """Decide whether a node performs I/O (and so is a checkpoint boundary).

    An ``AgentNode`` is always I/O (it issues an LLM call). Any node that
    carries a non-empty ``tools`` attribute also performs I/O. Otherwise we
    consult the static node-type sets.
    """
    node_type = type(node).__name__
    if node_type in _IO_NODE_TYPES:
        return True
    # Tool-bearing nodes call out to tools (I/O).
    return bool(getattr(node, "tools", ()))


def annotate_checkpoints(ir: Any) -> CheckpointAnnotation:
    """Tag I/O-bearing nodes as checkpoint / activity boundaries.

    Walks the IR tree and classifies every node as either a checkpoint
    boundary (LLM calls, tool calls, remote/child-workflow dispatch,
    signal gates) or deterministic orchestration that needs no checkpoint
    of its own. Durable backends (Temporal, DBOS, Prefect) consume the
    resulting :class:`CheckpointAnnotation` to decide which nodes become
    activities / steps / tasks (cached on replay) versus inline workflow
    code (replayed deterministically from history).

    The IR itself is **not** mutated — the nodes are frozen dataclasses —
    so the original tree is returned inside the annotation unchanged.

    Args:
        ir: The root IR node (or a previously produced annotation, in which
            case its IR is re-annotated).

    Returns:
        A :class:`CheckpointAnnotation` whose ``checkpoints`` maps each
        node's path (tuple of child indices) to a descriptor and whose
        ``boundary_names`` lists every checkpoint-boundary node name.
    """
    root = ir.ir if isinstance(ir, CheckpointAnnotation) else ir

    checkpoints: dict[tuple[int, ...], dict[str, Any]] = {}
    boundary_names: set[str] = set()

    def _walk(node: Any, path: tuple[int, ...]) -> None:
        node_type = type(node).__name__
        is_boundary = _is_io_node(node)
        checkpoints[path] = {
            "name": getattr(node, "name", "unknown"),
            "node_type": node_type,
            "checkpoint": is_boundary,
            "deterministic": not is_boundary,
        }
        if is_boundary:
            boundary_names.add(getattr(node, "name", "unknown"))
        for i, child in enumerate(_child_nodes(node)):
            _walk(child, path + (i,))

    _walk(root, ())

    return CheckpointAnnotation(
        ir=root,
        checkpoints=checkpoints,
        boundary_names=frozenset(boundary_names),
    )


# ======================================================================
# Entry point
# ======================================================================


def run_passes(ir: Any) -> Any:
    """Run all optimization passes in sequence.

    Pass order:
    1. fuse_transforms — merge adjacent TransformNodes

    Contract validation is NOT run here — it is advisory and should be
    invoked explicitly via ``validate_contracts(ir)`` when needed.
    """
    ir = fuse_transforms(ir)
    # annotate_checkpoints is NOT run here: it returns a CheckpointAnnotation
    # (IR + sidecar checkpoint map), not an IR tree, and is invoked explicitly
    # by durable backends that need checkpoint / activity-boundary metadata.
    return ir
