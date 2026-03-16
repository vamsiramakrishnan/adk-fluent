"""IR optimization passes.

Passes transform an IR tree before it is lowered to a backend-specific
runnable. They operate on frozen dataclasses (IR nodes) and return new
IR trees — the originals are never mutated.

Current passes:

- ``fuse_transforms``: Merge adjacent TransformNodes into a single node.
- ``validate_contracts``: Run static contract checks (delegates to
  ``testing.contracts``).
- ``annotate_checkpoints``: Mark nodes that need checkpointing for durable
  backends (placeholder for future use).

The ``run_passes`` entry point runs all passes in sequence.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from adk_fluent._ir import TransformNode

__all__ = [
    "run_passes",
    "fuse_transforms",
    "validate_contracts",
    "annotate_checkpoints",
]


# ======================================================================
# Pass: fuse adjacent TransformNodes
# ======================================================================


def _is_sequence_node(node: Any) -> bool:
    """Check if node is a SequenceNode without importing (avoids circular)."""
    return type(node).__name__ == "SequenceNode"


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


def annotate_checkpoints(ir: Any) -> Any:
    """Mark nodes that need checkpointing for durable backends.

    This is a placeholder pass. Durable backends (Temporal, DBOS) will
    use node metadata to decide which nodes become activities vs. inline
    workflow code. Currently returns the IR unchanged.

    Future: will add ``checkpoint: bool`` to node metadata based on
    whether the node performs I/O (AgentNode, tool calls) or is
    deterministic (TransformNode, TapNode, RouteNode).
    """
    return ir


# ======================================================================
# Entry point
# ======================================================================


def run_passes(ir: Any) -> Any:
    """Run all optimization passes in sequence.

    Pass order:
    1. fuse_transforms — merge adjacent TransformNodes
    2. annotate_checkpoints — mark checkpoint boundaries

    Contract validation is NOT run here — it is advisory and should be
    invoked explicitly via ``validate_contracts(ir)`` when needed.
    """
    ir = fuse_transforms(ir)
    ir = annotate_checkpoints(ir)
    return ir
