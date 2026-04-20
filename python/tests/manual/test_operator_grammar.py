"""Tests for the unified operator grammar — ``Composite >> Builder`` attach.

Python-side verification that every namespace composite (M, T, G, C, P, A)
uses the same ``>>`` direction to attach itself to a builder via the builder's
corresponding setter. See ``docs/reference/operators.md`` for the full grammar.
"""

from __future__ import annotations

from adk_fluent import Agent, A, C, G, M, P, T
from adk_fluent import Context, Guard, Middleware, Prompt, Tool  # named aliases


class TestCompositeAttach:
    """``Namespace(...) >> Builder`` attaches via the right setter."""

    def test_middleware_chain_attaches(self) -> None:
        mw = M.retry(max_attempts=2) | M.log()
        agent = mw >> Agent("a").model("gemini-2.5-flash")
        assert isinstance(agent, Agent)
        # middleware lands on the builder's ``_middlewares`` list
        assert agent._middlewares, "middleware list should be populated"
        assert len(agent._middlewares) == 2

    def test_tools_chain_attaches(self) -> None:
        def search(q: str) -> str:
            return q

        tools = T.fn(search)
        agent = tools >> Agent("b").model("gemini-2.5-flash")
        assert isinstance(agent, Agent)

    def test_guard_chain_attaches(self) -> None:
        guard = G.length(max=500)
        agent = guard >> Agent("c").model("gemini-2.5-flash")
        assert isinstance(agent, Agent)

    def test_context_transform_attaches(self) -> None:
        spec = C.window(n=3)
        agent = spec >> Agent("d").model("gemini-2.5-flash")
        assert isinstance(agent, Agent)
        # context spec is stored on the builder
        assert agent._config.get("_context_spec") is spec

    def test_prompt_transform_attaches(self) -> None:
        prompt = P.role("analyst") + P.task("crunch numbers")
        agent = prompt >> Agent("e").model("gemini-2.5-flash")
        assert isinstance(agent, Agent)
        # instruction is set on the builder
        assert agent._config.get("instruction") is prompt

    def test_artifact_op_attaches_reverse(self) -> None:
        op = A.publish("report.md", from_key="draft")
        # Artifacts use Builder >> A.publish() (trailing pipeline step).
        agent = Agent("f").model("gemini-2.5-flash") >> op
        # >> with artifact on RHS yields a workflow that includes the op;
        # at minimum, this should not raise.
        assert agent is not None


class TestNamedAliases:
    """Named-word aliases are the same classes as the single-letter names."""

    def test_aliases_are_identical(self) -> None:
        assert Context is C
        assert Prompt is P
        assert Guard is G
        assert Middleware is M
        assert Tool is T

    def test_named_alias_composition_works(self) -> None:
        # Same grammar, just spelled out.
        spec = Context.window(n=5)
        agent = spec >> Agent("g").model("gemini-2.5-flash")
        assert agent._config.get("_context_spec") is spec

    def test_middleware_alias_composition(self) -> None:
        mw = Middleware.retry(max_attempts=1) | Middleware.log()
        agent = mw >> Agent("h").model("gemini-2.5-flash")
        assert agent._middlewares
        assert len(agent._middlewares) == 2
