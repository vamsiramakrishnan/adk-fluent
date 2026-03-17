"""Reusable composition patterns for common agent workflows. Hand-written, not generated.

Each function returns a builder (Pipeline, Loop, FanOut, etc.) that
composes agents, transforms, and routing into a production-ready workflow
with a single call.

These are higher-order constructors — they accept builders and return
builders, so they compose freely with the rest of the expression language.

Usage::

    from adk_fluent.patterns import review_loop, map_reduce, cascade, fan_out_merge

    # Refinement loop: writer → reviewer → repeat until quality target
    pipeline = review_loop(
        worker=Agent("writer").instruct("Write article.").writes("draft"),
        reviewer=Agent("reviewer").instruct("Rate quality of: {draft}").writes("quality"),
        quality_key="quality",
        target="good",
        max_rounds=3,
    )

    # Fan-out research + merge results
    pipeline = fan_out_merge(
        Agent("web").instruct("Search web for {topic}").writes("web_results"),
        Agent("papers").instruct("Search papers for {topic}").writes("paper_results"),
        merge_key="research",
    )

    # Cascading fallback models
    pipeline = cascade(
        Agent("fast").model("gemini-2.0-flash"),
        Agent("smart").model("gemini-2.5-pro"),
    )
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = [
    "review_loop",
    "map_reduce",
    "cascade",
    "fan_out_merge",
    "chain",
    "conditional",
    "supervised",
    "a2a_cascade",
    "a2a_fanout",
    "a2a_delegate",
    "ui_form_agent",
    "ui_dashboard_agent",
]


def review_loop(
    worker: Any,
    reviewer: Any,
    *,
    quality_key: str = "quality",
    target: str = "good",
    max_rounds: int = 3,
) -> Any:
    """Create a refinement loop: worker produces, reviewer evaluates, repeat until target.

    The worker and reviewer run sequentially in a loop. The reviewer writes
    its assessment to ``quality_key``. The loop exits when
    ``state[quality_key] == target`` or ``max_rounds`` is exhausted.

    Args:
        worker: Agent builder that produces work (should write output via .writes()).
        reviewer: Agent builder that evaluates work (must write to quality_key).
        quality_key: State key where the reviewer writes its quality assessment.
        target: Value of quality_key that signals the loop should exit.
        max_rounds: Maximum iterations before the loop stops regardless.

    Returns:
        A Loop builder ready for ``.build()`` or further composition.

    Usage::

        pipeline = review_loop(
            worker=Agent("writer").instruct("Write article about {topic}.").writes("draft"),
            reviewer=Agent("reviewer").instruct("Rate: {draft}").writes("quality"),
        )
    """
    from adk_fluent._base import until

    return (worker >> reviewer) * until(
        lambda s, k=quality_key, t=target: s.get(k) == t,
        max=max_rounds,
    )


def map_reduce(
    mapper: Any,
    reducer: Any,
    *,
    items_key: str,
    item_key: str = "_item",
    result_key: str = "results",
) -> Any:
    """Fan-out a mapper agent over items in state, then reduce.

    Iterates ``mapper`` over each item in ``state[items_key]``, collecting
    results into ``state[result_key]``. Then runs ``reducer`` on the
    collected results.

    Args:
        mapper: Agent builder applied to each item. Receives current item in state[item_key].
        reducer: Agent builder that synthesizes the collected results.
        items_key: State key containing the list of items to iterate over.
        item_key: State key where each individual item is placed (default "_item").
        result_key: State key where collected results are stored (default "results").

    Returns:
        A Pipeline builder ready for ``.build()`` or further composition.

    Usage::

        pipeline = map_reduce(
            mapper=Agent("researcher").instruct("Research {_item}").writes("finding"),
            reducer=Agent("synthesizer").instruct("Synthesize: {results}"),
            items_key="topics",
        )
    """
    from adk_fluent._primitive_builders import map_over

    return map_over(items_key, mapper, item_key=item_key, output_key=result_key) >> reducer


def cascade(*agents: Any) -> Any:
    """Try agents in order. First success wins (fallback chain).

    Creates a fallback chain using the ``//`` operator. If the first agent
    fails (raises an exception), the second is tried, and so on.

    Args:
        *agents: Two or more agent builders to try in order.

    Returns:
        A fallback builder ready for ``.build()`` or further composition.

    Raises:
        ValueError: If fewer than 2 agents are provided.

    Usage::

        pipeline = cascade(
            Agent("fast").model("gemini-2.0-flash").instruct("Answer: {question}"),
            Agent("smart").model("gemini-2.5-pro").instruct("Answer: {question}"),
        )
    """
    if len(agents) < 2:
        raise ValueError("cascade() requires at least 2 agents")
    result = agents[0]
    for a in agents[1:]:
        result = result // a
    return result


def fan_out_merge(
    *agents: Any,
    merge_key: str = "merged",
    merge_fn: Callable | None = None,
) -> Any:
    """Run agents in parallel, then merge their outputs into one state key.

    Each agent should write to a unique output key via ``.writes()``.
    After all branches complete, their outputs are merged into
    ``state[merge_key]``.

    Args:
        *agents: Two or more agent builders to run in parallel.
            Each should have a unique output key set via .writes().
        merge_key: State key where the merged result is stored.
        merge_fn: Optional function to merge values. Receives positional
            args in agent order. Default: newline-joined concatenation.

    Returns:
        A Pipeline builder (FanOut >> merge transform) ready for ``.build()``.

    Usage::

        pipeline = fan_out_merge(
            Agent("web").instruct("Search web.").writes("web_results"),
            Agent("papers").instruct("Search papers.").writes("paper_results"),
            merge_key="research",
        )
    """
    from adk_fluent._transforms import S

    if len(agents) < 2:
        raise ValueError("fan_out_merge() requires at least 2 agents")

    # Build the fan-out
    fanout = agents[0]
    for a in agents[1:]:
        fanout = fanout | a

    # Collect output keys for merge
    output_keys = []
    for a in agents:
        ok = getattr(a, "_config", {}).get("output_key") if hasattr(a, "_config") else None
        if ok:
            output_keys.append(ok)

    if not output_keys:
        return fanout

    return fanout >> S.merge(*output_keys, into=merge_key, fn=merge_fn)


def chain(*steps: Any) -> Any:
    """Chain steps sequentially using ``>>`` (Pipeline).

    A convenience wrapper that avoids deeply nested ``>>`` expressions
    when composing many steps programmatically (e.g., from a list).

    Args:
        *steps: Two or more builders, callables, or S transforms.

    Returns:
        A Pipeline builder ready for ``.build()`` or further composition.

    Usage::

        steps = [Agent("a"), S.pick("out"), Agent("b"), S.rename(out="input"), Agent("c")]
        pipeline = chain(*steps)
    """
    if len(steps) < 2:
        raise ValueError("chain() requires at least 2 steps")
    result = steps[0]
    for step in steps[1:]:
        result = result >> step
    return result


def conditional(
    predicate: Callable[[dict], bool],
    if_true: Any,
    if_false: Any | None = None,
    *,
    key: str | None = None,
) -> Any:
    """Route to different agents based on a state predicate.

    A convenience wrapper around ``Route().when()`` for simple
    if/else branching without importing Route.

    Args:
        predicate: Function receiving state dict, returns truthy/falsy.
        if_true: Agent builder to run when predicate is True.
        if_false: Optional agent builder to run when predicate is False.
        key: Optional state key shorthand. When provided, predicate receives
            the value of state[key] instead of the full state dict.

    Returns:
        A Route (can be used in ``>>`` pipelines).

    Usage::

        pipeline = (
            Agent("classifier").writes("intent")
            >> conditional(
                lambda s: s.get("intent") == "booking",
                if_true=Agent("booker"),
                if_false=Agent("faq"),
            )
        )
    """
    from adk_fluent._routing import Route

    if key is not None:
        route = Route(key)
        # For key-based routing, we need eq checks
        # Since we have a predicate, use .when()
        wrapped_pred = predicate if key is None else lambda s, k=key: predicate(s.get(k))
        route.when(wrapped_pred, if_true)
    else:
        route = Route()
        route.when(predicate, if_true)

    if if_false is not None:
        route.otherwise(if_false)

    return route


def supervised(
    worker: Any,
    supervisor: Any,
    *,
    approval_key: str = "approved",
    max_revisions: int = 3,
) -> Any:
    """Worker-supervisor pattern: worker produces, supervisor approves or requests revision.

    Similar to ``review_loop`` but semantically oriented toward an
    approval workflow rather than quality iteration. The supervisor
    writes ``True``/``"yes"`` to ``approval_key`` when satisfied.

    Args:
        worker: Agent builder that produces work.
        supervisor: Agent builder that approves or requests revision.
            Should write to approval_key.
        approval_key: State key where the supervisor writes its decision.
        max_revisions: Maximum revision cycles before forced acceptance.

    Returns:
        A Loop builder ready for ``.build()`` or further composition.

    Usage::

        pipeline = supervised(
            worker=Agent("writer").instruct("Write report.").writes("draft"),
            supervisor=Agent("editor").instruct("Review: {draft}").writes("approved"),
            max_revisions=2,
        )
    """
    from adk_fluent._base import until

    def _is_approved(state: dict) -> bool:
        val = state.get(approval_key)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("yes", "true", "approved", "accept", "ok")
        return bool(val)

    return (worker >> supervisor) * until(_is_approved, max=max_revisions)


# ---------------------------------------------------------------------------
# A2A composition patterns
# ---------------------------------------------------------------------------


def a2a_cascade(
    *endpoints: str,
    names: list[str] | None = None,
    timeout: float = 300.0,
) -> Any:
    """Fallback chain across remote A2A agents.

    Tries each remote agent in order. First success wins.
    Uses the ``//`` (fallback) operator internally.

    Requires ``pip install adk-fluent[a2a]``.

    Args:
        *endpoints: Two or more A2A server URLs to try in order.
        names: Optional agent names (default: ``remote_0``, ``remote_1``, ...).
        timeout: Per-agent HTTP timeout in seconds.

    Returns:
        A fallback builder ready for ``.build()`` or further composition.

    Raises:
        ValueError: If fewer than 2 endpoints are provided.

    Usage::

        pipeline = a2a_cascade(
            "http://fast-model:8001",
            "http://accurate-model:8002",
            "http://fallback-model:8003",
        )
    """
    from adk_fluent.a2a import RemoteAgent

    if len(endpoints) < 2:
        raise ValueError("a2a_cascade() requires at least 2 endpoints")

    agents = []
    for i, ep in enumerate(endpoints):
        name = names[i] if names and i < len(names) else f"remote_{i}"
        agents.append(RemoteAgent(name, ep).timeout(timeout))

    return cascade(*agents)


def a2a_fanout(
    *endpoints: str,
    names: list[str] | None = None,
    timeout: float = 300.0,
) -> Any:
    """Fan-out across remote A2A agents in parallel.

    All remote agents run concurrently via the ``|`` (parallel) operator.

    Requires ``pip install adk-fluent[a2a]``.

    Args:
        *endpoints: Two or more A2A server URLs to query in parallel.
        names: Optional agent names (default: ``remote_0``, ``remote_1``, ...).
        timeout: Per-agent HTTP timeout in seconds.

    Returns:
        A FanOut builder ready for ``.build()`` or further composition.

    Raises:
        ValueError: If fewer than 2 endpoints are provided.

    Usage::

        pipeline = a2a_fanout(
            "http://web-search:8001",
            "http://paper-search:8002",
            "http://patent-search:8003",
        )
    """
    from adk_fluent.a2a import RemoteAgent

    if len(endpoints) < 2:
        raise ValueError("a2a_fanout() requires at least 2 endpoints")

    agents = []
    for i, ep in enumerate(endpoints):
        name = names[i] if names and i < len(names) else f"remote_{i}"
        agents.append(RemoteAgent(name, ep).timeout(timeout))

    result = agents[0]
    for a in agents[1:]:
        result = result | a
    return result


def a2a_delegate(
    coordinator: Any,
    **remotes: str,
) -> Any:
    """Coordinator agent with named remote specialists as sub-agents.

    The coordinator LLM decides which remote agent to delegate to based
    on its instruction and the remote agents' descriptions. Uses ADK's
    native sub-agent delegation (the parent LLM sees each remote agent's
    name and description).

    Requires ``pip install adk-fluent[a2a]``.

    Args:
        coordinator: Local agent builder (the orchestrator).
        **remotes: ``name=endpoint`` pairs for remote specialists.

    Returns:
        The coordinator builder with remote sub-agents attached,
        ready for ``.build()`` or further composition.

    Usage::

        pipeline = a2a_delegate(
            Agent("coordinator", "gemini-2.5-flash")
            .instruct("Route tasks to the right specialist."),
            research="http://research:8001",
            writing="http://writing:8002",
            analysis="http://analysis:8003",
        )
    """
    from adk_fluent.a2a import RemoteAgent

    for name, endpoint in remotes.items():
        coordinator = coordinator.sub_agent(RemoteAgent(name, endpoint))
    return coordinator


# ======================================================================
# A2UI composition patterns
# ======================================================================


def ui_form_agent(
    name: str,
    model: str,
    *,
    fields: dict[str, str | list[str]],
    on_submit: Callable | None = None,
    instruction: str = "",
    submit_label: str = "Submit",
) -> Any:
    """Create an agent with an attached form UI surface.

    Generates a :class:`UISurface` with labeled fields, a submit button,
    and optional submit handler. State keys match field names.

    Args:
        name: Agent name.
        model: LLM model identifier.
        fields: Mapping of field name → field type (``"text"``, ``"email"``,
            ``"longText"``, ``"number"``, ``"choice"``).
        on_submit: Async callback ``fn(callback_context)`` invoked on submit.
        instruction: Agent instruction text.
        submit_label: Label for the submit button.

    Returns:
        An Agent builder with ``.ui()`` pre-configured.

    Usage::

        agent = ui_form_agent(
            "intake", "gemini-2.5-flash",
            fields={"name": "text", "email": "email"},
            instruction="Collect user info.",
        ).build()
    """
    from adk_fluent import UI, Agent

    agent = Agent(name, model)
    if instruction:
        agent = agent.instruct(instruction)
    agent = agent.ui(UI.form(name, fields=fields, submit=submit_label))
    if on_submit:
        agent = agent.after_agent(on_submit)
    return agent


def ui_dashboard_agent(
    name: str,
    model: str,
    *,
    cards: list[dict[str, Any]],
    instruction: str = "",
) -> Any:
    """Create an agent with an attached dashboard UI surface.

    Generates a :class:`UISurface` with metric cards, each bound to
    a data model path.

    Args:
        name: Agent name.
        model: LLM model identifier.
        cards: List of dicts with ``"title"`` and ``"bind"`` keys.
        instruction: Agent instruction text.

    Returns:
        An Agent builder with ``.ui()`` pre-configured.

    Usage::

        agent = ui_dashboard_agent(
            "metrics", "gemini-2.5-flash",
            cards=[
                {"title": "Users", "bind": "/stats/users"},
                {"title": "Revenue", "bind": "/stats/revenue"},
            ],
        ).build()
    """
    from adk_fluent import UI, Agent

    agent = Agent(name, model)
    if instruction:
        agent = agent.instruct(instruction)
    agent = agent.ui(UI.dashboard(name, cards=cards))
    return agent
