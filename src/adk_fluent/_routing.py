"""Control flow primitives for the fluent expression language. Hand-written, not generated."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["Route"]


def _make_fallback_builder(children: list):
    """Create a _FallbackBuilder from a list of children."""
    from adk_fluent._base import _FallbackBuilder

    names = []
    for c in children:
        if hasattr(c, "_config"):
            names.append(c._config.get("name", "?"))
        elif hasattr(c, "name"):
            names.append(c.name)
        else:
            names.append("?")
    name = "_or_".join(names)
    return _FallbackBuilder(name, children)


class Route:
    """Deterministic state-based routing. No LLM call -- evaluates predicates against session state.

    Usage:
        # Branch on a single key
        classifier.outputs("intent") >> Route("intent").eq("booking", booker).eq("info", info_agent)

        # Pattern matching
        analyzer.outputs("text") >> Route("text").contains("urgent", escalation).otherwise(standard)

        # Threshold
        scorer.outputs("score") >> Route("score").gt(0.8, premium).otherwise(basic)

        # Complex multi-key predicates
        Route().when(lambda s: s["ok"] == "yes" and float(s["score"]) > 0.8, premium).otherwise(standard)
    """

    def __init__(self, key: str | None = None):
        self._key = key
        self._rules: list[tuple[Callable, Any]] = []
        self._default: Any = None

    def eq(self, value: Any, agent) -> Route:
        """Branch to agent when state[key] == value."""
        key = self._require_key("eq")
        self._rules.append((lambda s, v=value, k=key: s.get(k) == v, agent))
        return self

    def contains(self, substring: str, agent) -> Route:
        """Branch to agent when substring is in str(state[key])."""
        key = self._require_key("contains")
        self._rules.append((lambda s, sub=substring, k=key: sub in str(s.get(k, "")), agent))
        return self

    def gt(self, threshold: float, agent) -> Route:
        """Branch to agent when state[key] > threshold."""
        key = self._require_key("gt")
        self._rules.append((lambda s, t=threshold, k=key: float(s.get(k, 0)) > t, agent))
        return self

    def lt(self, threshold: float, agent) -> Route:
        """Branch to agent when state[key] < threshold."""
        key = self._require_key("lt")
        self._rules.append((lambda s, t=threshold, k=key: float(s.get(k, 0)) < t, agent))
        return self

    def when(self, predicate: Callable, agent) -> Route:
        """Branch to agent when predicate(state) is truthy. Supports complex multi-key logic."""
        self._rules.append((predicate, agent))
        return self

    def otherwise(self, agent) -> Route:
        """Default branch when no other rule matches."""
        self._default = agent
        return self

    def _require_key(self, method: str) -> str:
        if self._key is None:
            raise ValueError(
                f"Route.{method}() requires a key. Use Route('key_name').{method}(...) "
                f"or Route().when(lambda s: ...) for keyless predicates."
            )
        return self._key

    def to_ir(self):
        """Convert this Route to an IR RouteNode."""
        from adk_fluent._base import BuilderBase
        from adk_fluent._ir import RouteNode

        ir_rules = []
        for pred, agent_or_builder in self._rules:
            if isinstance(agent_or_builder, BuilderBase):
                ir_agent = agent_or_builder.to_ir()
            else:
                ir_agent = agent_or_builder
            ir_rules.append((pred, ir_agent))

        ir_default = None
        if self._default is not None:
            if isinstance(self._default, BuilderBase):
                ir_default = self._default.to_ir()
            else:
                ir_default = self._default

        name = f"route_{self._key}" if self._key else "route"
        return RouteNode(
            name=name,
            key=self._key,
            rules=tuple(ir_rules),
            default=ir_default,
        )

    def build(self):
        """Build a deterministic RouteAgent from the configured rules."""
        from adk_fluent._base import BuilderBase

        built_rules = []
        sub_agents = []

        for pred, agent_or_builder in self._rules:
            if isinstance(agent_or_builder, BuilderBase):
                built = agent_or_builder.build()
            else:
                built = agent_or_builder
            built_rules.append((pred, built))
            sub_agents.append(built)

        built_default = None
        if self._default is not None:
            if isinstance(self._default, BuilderBase):
                built_default = self._default.build()
            else:
                built_default = self._default
            sub_agents.append(built_default)

        name = f"route_{self._key}" if self._key else "route"
        return _make_route_agent(name, built_rules, built_default, sub_agents)

    def to_mermaid(self) -> str:
        """Generate a Mermaid graph visualization of this Route's branching structure."""
        from adk_fluent.viz import ir_to_mermaid

        return ir_to_mermaid(self.to_ir())

    def __repr__(self) -> str:
        key_str = f"'{self._key}'" if self._key else "multi-key"
        rules_str = f"{len(self._rules)} rules"
        default_str = " + otherwise" if self._default else ""
        return f"Route({key_str}, {rules_str}{default_str})"


def _make_route_agent(name, rules, default_agent, sub_agents):
    """Create a deterministic routing agent that evaluates predicates against session state.

    Uses closure-based approach to avoid Pydantic extra='forbid' constraint on BaseAgent.
    """
    from google.adk.agents.base_agent import BaseAgent

    class _RouteAgent(BaseAgent):
        """Internal deterministic routing agent. Zero LLM calls."""

        async def _run_async_impl(self, ctx):
            state = ctx.session.state
            target = None

            for predicate, agent in rules:
                try:
                    if predicate(state):
                        target = agent
                        break
                except (KeyError, TypeError, ValueError):
                    continue

            if target is None:
                target = default_agent

            if target is not None:
                async for event in target.run_async(ctx):
                    yield event

    return _RouteAgent(name=name, sub_agents=sub_agents)


def _make_checkpoint_agent(name, predicate):
    """Create a tiny agent that checks a predicate and escalates to exit a loop.

    Used by loop_until() to implement conditional loop exit using ADK's native
    escalate mechanism.
    """
    from google.adk.agents.base_agent import BaseAgent
    from google.adk.events.event import Event
    from google.adk.events.event_actions import EventActions

    class _CheckpointAgent(BaseAgent):
        """Internal checkpoint agent. Evaluates predicate, escalates if satisfied."""

        async def _run_async_impl(self, ctx):
            state = ctx.session.state
            try:
                if predicate(state):
                    yield Event(
                        invocation_id=ctx.invocation_id,
                        author=self.name,
                        branch=ctx.branch,
                        actions=EventActions(escalate=True),
                    )
            except (KeyError, TypeError, ValueError):
                pass  # Predicate evaluation failed -- don't escalate

    return _CheckpointAgent(name=name)
