"""Tests for verb harmonization: new features, renamed methods, removed methods, and deprecated aliases."""

import warnings

import pytest

from adk_fluent import Agent

# ---------------------------------------------------------------------------
# 1. Fallback builder
# ---------------------------------------------------------------------------


class TestFallbackBuilder:
    def test_fallback_basic_build(self):
        from adk_fluent._routing import Fallback

        a = Agent("primary").instruct("Try first.")
        b = Agent("backup").instruct("Try second.")
        fb = Fallback("recovery").attempt(a).attempt(b)
        built = fb.build()
        assert built.name == "recovery"
        assert len(built.sub_agents) == 2

    def test_fallback_to_ir(self):
        from adk_fluent._ir import FallbackNode
        from adk_fluent._routing import Fallback

        a = Agent("a").instruct("A.")
        b = Agent("b").instruct("B.")
        ir = Fallback("fb").attempt(a).attempt(b).to_ir()
        assert isinstance(ir, FallbackNode)
        assert ir.name == "fb"
        assert len(ir.children) == 2

    def test_fallback_floordiv(self):
        from adk_fluent._routing import Fallback

        a = Agent("a").instruct("A.")
        b = Agent("b").instruct("B.")
        c = Agent("c").instruct("C.")
        fb = Fallback("chain").attempt(a) // b // c
        assert isinstance(fb, Fallback)
        built = fb.build()
        assert len(built.sub_agents) == 3

    def test_fallback_importable_from_prelude(self):
        from adk_fluent.prelude import Fallback as F

        assert F is not None

    def test_fallback_importable_from_top_level(self):
        from adk_fluent import Fallback as F

        assert F is not None


# ---------------------------------------------------------------------------
# 2. Route comparison operators
# ---------------------------------------------------------------------------


class TestRouteOperators:
    def test_route_gte(self):
        from adk_fluent._routing import Route

        a = Agent("high").instruct("High.")
        r = Route("score").gte(0.8, a)
        assert len(r._rules) == 1
        pred, agent = r._rules[0]
        assert agent is a
        assert pred({"score": "0.9"}) is True
        assert pred({"score": "0.8"}) is True
        assert pred({"score": "0.7"}) is False

    def test_route_lte(self):
        from adk_fluent._routing import Route

        a = Agent("low").instruct("Low.")
        r = Route("score").lte(0.5, a)
        assert len(r._rules) == 1
        pred, agent = r._rules[0]
        assert pred({"score": "0.3"}) is True
        assert pred({"score": "0.5"}) is True
        assert pred({"score": "0.6"}) is False

    def test_route_ne(self):
        from adk_fluent._routing import Route

        a = Agent("handler").instruct("Handle.")
        r = Route("status").ne("done", a)
        assert len(r._rules) == 1
        pred, _ = r._rules[0]
        assert pred({"status": "pending"}) is True
        assert pred({"status": "done"}) is False

    def test_route_gte_requires_key(self):
        from adk_fluent._routing import Route

        with pytest.raises(ValueError, match="key"):
            Route().gte(0.5, Agent("a"))

    def test_route_lte_requires_key(self):
        from adk_fluent._routing import Route

        with pytest.raises(ValueError, match="key"):
            Route().lte(0.5, Agent("a"))

    def test_route_ne_requires_key(self):
        from adk_fluent._routing import Route

        with pytest.raises(ValueError, match="key"):
            Route().ne("x", Agent("a"))


# ---------------------------------------------------------------------------
# 3. Removed deprecated shims (0.18.0)
# ---------------------------------------------------------------------------


class TestRemovedAliases:
    """Verify that the 0.18.0 removal sticks — these methods MUST NOT come back."""

    @pytest.mark.parametrize(
        "method,successor",
        [
            ("save_as", "writes"),
            ("outputs", "writes"),
            ("guardrail", "guard"),
            ("delegate", "agent_tool"),
            ("retry_if", "loop_while"),
            ("inject_context", "prepend"),
            ("history", "context"),
            ("include_history", "context"),
        ],
    )
    def test_removed_method_raises(self, method: str, successor: str) -> None:
        agent = Agent("a")
        assert not hasattr(agent, method), (
            f"Agent.{method}() was removed in 0.18.0 — use .{successor}() instead"
        )


# ---------------------------------------------------------------------------
# 4. Canonical methods work without warnings
# ---------------------------------------------------------------------------


class TestCanonicalMethods:
    def test_writes_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("a").writes("key")
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    def test_guard_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("a").guard(lambda *a: None)
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    def test_agent_tool_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("a").agent_tool(Agent("b"))
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    def test_loop_while_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("a").loop_while(lambda s: False)
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    def test_prepend_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("a").prepend(lambda ctx: "text")
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0


# ---------------------------------------------------------------------------
# 5. Removed methods raise AttributeError
# ---------------------------------------------------------------------------


class TestRemovedMethods:
    def test_retry_removed(self):
        a = Agent("a")
        assert not hasattr(a, "retry")

    def test_fallback_method_removed(self):
        """BuilderBase no longer has a .fallback() method."""
        from adk_fluent._base import BuilderBase

        assert not hasattr(BuilderBase, "fallback")


# ---------------------------------------------------------------------------
# 6. Renamed internal types
# ---------------------------------------------------------------------------


class TestRenamedTypes:
    def test_timed_agent_importable(self):
        from adk_fluent._primitive_builders import TimedAgent

        assert TimedAgent is not None

    def test_background_task_importable(self):
        from adk_fluent._primitive_builders import BackgroundTask

        assert BackgroundTask is not None

    def test_timeout_returns_timed_agent(self):
        from adk_fluent._primitive_builders import TimedAgent

        result = Agent("a").timeout(5)
        assert isinstance(result, TimedAgent)

    def test_dispatch_returns_background_task(self):
        from adk_fluent import dispatch
        from adk_fluent._primitive_builders import BackgroundTask

        result = dispatch(Agent("a"))
        assert isinstance(result, BackgroundTask)


# ---------------------------------------------------------------------------
# 7. Tools always-append semantics
# ---------------------------------------------------------------------------


class TestToolsReplace:
    def test_tools_list_replaces(self):
        """.tools([list]) replaces — it has 'set' semantics, not append."""

        def tool_a(x: str) -> str:
            """Tool A."""
            return x

        def tool_b(x: str) -> str:
            """Tool B."""
            return x

        agent = Agent("a").tool(tool_a).tools([tool_b])
        tools = agent._lists.get("tools", [])
        # .tools() replaces: only tool_b remains
        assert len(tools) == 1
        assert tools[0] is tool_b

    def test_tools_chain_accumulates(self):
        """Multiple .tool() calls should accumulate."""

        def t1(x: str) -> str:
            """T1."""
            return x

        def t2(x: str) -> str:
            """T2."""
            return x

        def t3(x: str) -> str:
            """T3."""
            return x

        agent = Agent("a").tool(t1).tool(t2).tool(t3)
        tools = agent._lists.get("tools", [])
        assert len(tools) == 3
