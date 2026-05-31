"""Control flow primitives for the fluent expression language. Hand-written, not generated."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["Route", "Fallback", "CostRoute"]

# Reference token counts used to compare model costs deterministically.
# Cost routing ranks candidate models, not absolute spend, so any fixed
# probe size yields the same ordering. 1k in / 1k out is a neutral default.
_PROBE_INPUT_TOKENS = 1_000
_PROBE_OUTPUT_TOKENS = 1_000


def _model_of(agent_or_builder: Any) -> str | None:
    """Best-effort extraction of an agent's model name.

    Works for fluent builders (model lives in ``_config["model"]``) and for
    already-built native ADK agents (``.model`` attribute). Returns ``None``
    when no model can be determined or the model is not a plain string
    (e.g. a ``BaseLlm`` instance).
    """
    model: Any = None
    if hasattr(agent_or_builder, "_config"):
        model = agent_or_builder._config.get("model")
    if model is None:
        model = getattr(agent_or_builder, "model", None)
    return model if isinstance(model, str) else None


def _estimate_cost(cost_table, model: str | None) -> float:
    """Estimate the per-call USD cost of ``model`` under ``cost_table``.

    An unknown model — one with no explicit entry and no ``"*"`` wildcard —
    costs ``+inf`` so it is never auto-selected when a known option exists.
    Uses a fixed probe token count; only the relative ordering matters.
    """
    if model is None:
        return float("inf")
    rates = getattr(cost_table, "rates", {})
    if model not in rates and "*" not in rates:
        return float("inf")
    rate = cost_table.rate_for(model)
    return rate.cost_for(_PROBE_INPUT_TOKENS, _PROBE_OUTPUT_TOKENS)


def _make_fallback_builder(children: list):
    """Create a _FallbackBuilder from a list of children."""
    from adk_fluent._primitive_builders import _FallbackBuilder

    names = []
    for c in children:
        if hasattr(c, "_config"):
            names.append(c._config.get("name", "?"))
        elif hasattr(c, "name"):
            names.append(c.name)
        else:
            names.append("?")
    name = "_or_".join(names)
    return _FallbackBuilder(name, _children=children)


class Route:
    """Deterministic state-based routing. No LLM call -- evaluates predicates against session state.

    Usage:
        # Branch on a single key
        classifier.writes("intent") >> Route("intent").eq("booking", booker).eq("info", info_agent)

        # Pattern matching
        analyzer.writes("text") >> Route("text").contains("urgent", escalation).otherwise(standard)

        # Threshold
        scorer.outputs("score") >> Route("score").gt(0.8, premium).otherwise(basic)

        # Complex multi-key predicates
        Route().when(lambda s: s["ok"] == "yes" and float(s["score"]) > 0.8, premium).otherwise(standard)
    """

    def __init__(self, key: str | None = None):
        self._key = key
        self._rules: list[tuple[Callable, Any]] = []
        self._default: Any = None

    @classmethod
    def by_cost(cls, cost_table=None) -> CostRoute:
        """Begin a cost-aware route over candidate agents.

        Returns a :class:`CostRoute` that selects among candidate agents by
        the estimated per-call USD cost of each agent's model, using
        ``cost_table`` (a :class:`~adk_fluent.CostTable`). The selection is
        deterministic and side-effect free: model costs are known at build
        time, so ``.cheapest(...)`` resolves to a single chosen agent with no
        LLM call.

        Args:
            cost_table: A :class:`CostTable` mapping model name → rate. If
                ``None``, every candidate model is treated as unknown
                (``+inf`` cost) and the first candidate is used as a tie-break.

        Usage::

            Route.by_cost(cost_table).cheapest(flash_agent, pro_agent)

        A candidate whose model is unknown to ``cost_table`` (no explicit
        entry and no ``"*"`` wildcard) is treated as costing ``+inf`` and is
        never auto-selected when a known cheaper option exists.
        """
        return CostRoute(cost_table=cost_table)

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

    def gte(self, threshold: float | int, agent) -> Route:
        """Branch to agent when ``float(state[key]) >= threshold``."""
        key = self._require_key("gte")
        self._rules.append((lambda s, t=threshold, k=key: float(s.get(k, 0)) >= t, agent))
        return self

    def lte(self, threshold: float | int, agent) -> Route:
        """Branch to agent when ``float(state[key]) <= threshold``."""
        key = self._require_key("lte")
        self._rules.append((lambda s, t=threshold, k=key: float(s.get(k, 0)) <= t, agent))
        return self

    def ne(self, value: Any, agent) -> Route:
        """Branch to agent when ``state[key] != value``."""
        key = self._require_key("ne")
        self._rules.append((lambda s, v=value, k=key: s.get(k) != v, agent))
        return self

    def when(self, predicate: Callable | type, agent) -> Route:
        """Branch to agent when predicate(state) is truthy.

        Accepts a callable or a PredicateSchema class.
        """
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


class CostRoute:
    """Cost-aware selection among candidate agents.

    Created via :meth:`Route.by_cost`. Picks a single agent based on the
    estimated per-call USD cost of its model under a
    :class:`~adk_fluent.CostTable`. Because model rates are known at build
    time, the choice is fully deterministic and involves no LLM call — it is
    consistent with the "deterministic routing" philosophy of :class:`Route`.

    Usage::

        # Pick the cheapest model that can do the job.
        chosen = Route.by_cost(cost_table).cheapest(flash_agent, pro_agent)

        chosen  # resolves to flash_agent if it is cheaper

    Resolution rules:
        * Each candidate's model is read from its builder config
          (``_config["model"]``) or, for built agents, the ``.model``
          attribute.
        * A model unknown to the cost table (no entry and no ``"*"`` wildcard)
          is treated as ``+inf`` cost and never auto-chosen when a known
          cheaper option exists.
        * Ties (including all-unknown candidates) are broken by declaration
          order — the first candidate wins.
    """

    def __init__(self, cost_table=None):
        self._cost_table = cost_table

    def cheapest(self, *candidates):
        """Return the candidate whose model has the lowest estimated cost.

        Args:
            *candidates: Two or more agent builders (or built agents) to
                choose between.

        Returns:
            The single cheapest candidate (unchanged), ready to drop into a
            pipeline, ``>>`` chain, or ``Route.otherwise(...)``.

        Raises:
            ValueError: If no candidates are supplied.
        """
        if not candidates:
            raise ValueError("Route.by_cost(...).cheapest() requires at least one candidate.")

        best = candidates[0]
        best_cost = _estimate_cost(self._cost_table, _model_of(best))
        for candidate in candidates[1:]:
            cost = _estimate_cost(self._cost_table, _model_of(candidate))
            if cost < best_cost:
                best, best_cost = candidate, cost
        return best

    def costliest(self, *candidates):
        """Return the candidate whose model has the highest *finite* cost.

        Symmetric counterpart to :meth:`cheapest` for callers who want to
        deliberately escalate to the strongest known model. Candidates with
        unknown models (``+inf`` cost) are skipped; if every candidate is
        unknown the first one is returned. Ties break by declaration order.

        Raises:
            ValueError: If no candidates are supplied.
        """
        if not candidates:
            raise ValueError("Route.by_cost(...).costliest() requires at least one candidate.")

        best = candidates[0]
        best_cost = _estimate_cost(self._cost_table, _model_of(best))
        best_finite = best_cost != float("inf")
        for candidate in candidates[1:]:
            cost = _estimate_cost(self._cost_table, _model_of(candidate))
            finite = cost != float("inf")
            # Prefer finite over infinite; among same finiteness, prefer higher cost.
            if (finite and not best_finite) or (finite and best_finite and cost > best_cost):
                best, best_cost, best_finite = candidate, cost, finite
        return best

    def __repr__(self) -> str:
        has_table = self._cost_table is not None
        return f"CostRoute(cost_table={'set' if has_table else 'None'})"


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
                # Fire topology hook
                from adk_fluent._primitives import _get_topology_hooks

                hooks = _get_topology_hooks()
                if hooks:
                    fn = getattr(hooks, "on_route_selected", None)
                    if fn is not None:
                        await fn(ctx, name, getattr(target, "name", str(target)))

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


class Fallback:
    """Fluent builder for fallback chains. Builder equivalent of the ``//`` operator.

    Tries each agent in order. First success wins.

    Usage::

        from adk_fluent import Fallback

        # These are equivalent:
        pipeline_a = agent_a // agent_b // agent_c
        pipeline_b = Fallback("recovery").attempt(agent_a).attempt(agent_b).attempt(agent_c)
    """

    def __init__(self, name: str = "fallback"):
        self._name = name
        self._children: list[Any] = []

    def attempt(self, agent: Any) -> Fallback:
        """Add an agent to try. Agents are tried in order; first success wins."""
        self._children.append(agent)
        return self

    def build(self) -> Any:
        """Build the fallback chain."""
        fb = _make_fallback_builder(self._children)
        fb._config["name"] = self._name
        return fb.build()

    def to_ir(self) -> Any:
        """Convert to IR."""
        fb = _make_fallback_builder(self._children)
        fb._config["name"] = self._name
        return fb.to_ir()

    def __floordiv__(self, other: Any) -> Fallback:
        """Support ``Fallback("f").attempt(a) // b`` syntax."""
        self._children.append(other)
        return self
