"""Topology-inferred event visibility with pipeline-level policies.

Walks the IR tree to classify each agent's visibility as "user" (terminal,
visible to end-user), "internal" (intermediate, hidden), or "zero_cost"
(no LLM call -- transforms, taps, routes, captures).

Also provides a VisibilityPlugin (ADK BasePlugin) that annotates or filters
events based on the inferred visibility map.
"""

from __future__ import annotations

from typing import Any, Literal

from google.adk.plugins.base_plugin import BasePlugin

__all__ = [
    "infer_visibility",
    "VisibilityPlugin",
]

# Node type names that are zero-cost (no LLM call) and have no children to recurse.
# RouteNode is also zero-cost but handled separately because it has branches.
_ZERO_COST_TYPES = frozenset({
    "TransformNode",
    "TapNode",
    "CaptureNode",
})


def infer_visibility(
    node: Any,
    has_successor: bool = False,
    policy: str = "filtered",
) -> dict[str, Literal["user", "internal", "zero_cost"]]:
    """Walk the IR tree and classify each agent's visibility.

    Args:
        node: An IR node (AgentNode, SequenceNode, etc.).
        has_successor: Whether this node has a successor in a sequence.
        policy: One of "filtered" (default), "transparent", or "annotate".
            - "filtered": topology-inferred -- terminal=user, intermediate=internal.
            - "transparent": all agents user-facing (debugging/demos).
            - "annotate": same as filtered but caller uses annotate mode on the plugin.

    Returns:
        A dict mapping agent name to visibility level.
    """
    result: dict[str, Literal["user", "internal", "zero_cost"]] = {}
    _walk(node, has_successor, policy, result)
    return result


def _walk(
    node: Any,
    has_successor: bool,
    policy: str,
    result: dict[str, Literal["user", "internal", "zero_cost"]],
) -> None:
    """Recursive walker that populates the result dict."""
    type_name = type(node).__name__

    # Zero-cost types are always zero_cost regardless of policy
    if type_name in _ZERO_COST_TYPES:
        result[node.name] = "zero_cost"
        return

    # SequenceNode: each child's has_successor depends on position
    if type_name == "SequenceNode":
        children = getattr(node, "children", ())
        for i, child in enumerate(children):
            child_has_successor = (i < len(children) - 1) or has_successor
            _walk(child, child_has_successor, policy, result)
        return

    # ParallelNode: children inherit parent's has_successor
    if type_name == "ParallelNode":
        children = getattr(node, "children", ())
        for child in children:
            _walk(child, has_successor, policy, result)
        return

    # LoopNode: loop body children always have has_successor=True
    if type_name == "LoopNode":
        children = getattr(node, "children", ())
        for child in children:
            _walk(child, True, policy, result)
        return

    # RouteNode: zero_cost for the route itself, recurse into branches
    if type_name == "RouteNode":
        result[node.name] = "zero_cost"
        rules = getattr(node, "rules", ())
        for rule in rules:
            # rules are typically (value, node) tuples or similar
            if hasattr(rule, "__len__") and len(rule) >= 2:
                _walk(rule[1], False, policy, result)
            elif hasattr(rule, "agent"):
                _walk(rule.agent, False, policy, result)
        default = getattr(node, "default", None)
        if default is not None:
            _walk(default, False, policy, result)
        return

    # FallbackNode, RaceNode, MapOverNode, TimeoutNode: recurse children/body
    if type_name in ("FallbackNode", "RaceNode"):
        children = getattr(node, "children", ())
        for child in children:
            _walk(child, has_successor, policy, result)
        return

    if type_name == "MapOverNode":
        body = getattr(node, "body", None)
        if body is not None:
            _walk(body, has_successor, policy, result)
        return

    if type_name == "TimeoutNode":
        body = getattr(node, "body", None)
        if body is not None:
            _walk(body, has_successor, policy, result)
        return

    # Leaf node (AgentNode or any other): classify visibility
    # Check for visibility override
    override = getattr(node, "_visibility_override", None)
    if override is not None:
        result[node.name] = override
        return

    # Transparent policy: all agents are user-facing
    if policy == "transparent":
        result[node.name] = "user"
        return

    # Filtered / annotate: topology-inferred
    if has_successor:
        result[node.name] = "internal"
    else:
        result[node.name] = "user"

    # Recurse into children of AgentNode (sub-agents)
    children = getattr(node, "children", ())
    for child in children:
        _walk(child, True, policy, result)


class VisibilityPlugin(BasePlugin):
    """ADK plugin that annotates/filters events based on inferred visibility.

    Modes:
        - "annotate": All events pass through with visibility metadata added.
        - "filter": Internal events have their content stripped.
    """

    def __init__(
        self,
        visibility_map: dict[str, str],
        mode: str = "annotate",
    ) -> None:
        super().__init__(name="adk_fluent_visibility")
        self._visibility = visibility_map
        self._mode = mode

    async def on_event_callback(self, *, invocation_context, event):
        """Annotate or filter events based on the visibility map."""
        vis = self._visibility.get(getattr(event, "author", ""), "user")

        # Always annotate
        if not hasattr(event, "custom_metadata") or event.custom_metadata is None:
            event.custom_metadata = {}
        event.custom_metadata["adk_fluent.visibility"] = vis
        event.custom_metadata["adk_fluent.is_user_facing"] = vis == "user"

        # Error events always pass through
        if self._is_error_event(event):
            event.custom_metadata["adk_fluent.visibility"] = "user"
            event.custom_metadata["adk_fluent.is_user_facing"] = True
            return event

        # Filter mode: strip content of internal events
        if self._mode == "filter" and vis != "user":
            self._strip_content(event)

        return event

    @staticmethod
    def _is_error_event(event) -> bool:
        """Check if an event represents an error (error_code or escalate)."""
        if hasattr(event, "error_code") and event.error_code:
            return True
        if hasattr(event, "actions") and event.actions:
            if hasattr(event.actions, "escalate") and event.actions.escalate:
                return True
        return False

    @staticmethod
    def _strip_content(event) -> None:
        """Remove content from an event (for filter mode)."""
        if hasattr(event, "content") and event.content and hasattr(event.content, "parts") and event.content.parts:
            event.content = None
