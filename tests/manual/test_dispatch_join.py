"""Tests for dispatch/join primitives: builders, factory functions, IR generation."""

from adk_fluent._base import BuilderBase
from adk_fluent._primitive_builders import (
    _DispatchBuilder,
    _JoinBuilder,
    dispatch,
    join,
)
from adk_fluent._primitives import DispatchAgent, JoinAgent
from adk_fluent.agent import Agent
from adk_fluent.workflow import Pipeline

# ======================================================================
# dispatch() factory function
# ======================================================================


class TestDispatchFactory:
    def test_dispatch_creates_builder(self):
        a = Agent("worker").model("gemini-2.5-flash")
        result = dispatch(a)
        assert isinstance(result, BuilderBase)
        assert isinstance(result, _DispatchBuilder)

    def test_dispatch_names_auto_derived(self):
        a = Agent("my_agent").model("gemini-2.5-flash")
        b = Agent("other_agent").model("gemini-2.5-flash")
        d = dispatch(a, b)
        assert d._task_names == ("my_agent", "other_agent")

    def test_dispatch_names_explicit(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        d = dispatch(a, b, names=["email", "seo"])
        assert d._task_names == ("email", "seo")

    def test_dispatch_stream_to_param(self):
        a = Agent("a").model("gemini-2.5-flash")
        d = dispatch(a, stream_to="my_key")
        assert d._stream_to == "my_key"

    def test_dispatch_progress_key_deprecated_alias(self):
        a = Agent("a").model("gemini-2.5-flash")
        d = dispatch(a, progress_key="my_key")
        assert d._stream_to == "my_key"

    def test_dispatch_max_tasks_param(self):
        a = Agent("a").model("gemini-2.5-flash")
        d = dispatch(a, max_tasks=10)
        assert d._max_tasks == 10

    def test_dispatch_task_budget_deprecated_alias(self):
        a = Agent("a").model("gemini-2.5-flash")
        d = dispatch(a, task_budget=10)
        assert d._max_tasks == 10


# ======================================================================
# _DispatchBuilder
# ======================================================================


class TestDispatchBuilder:
    def test_dispatch_builder_creates_agent(self):
        a = Agent("worker").model("gemini-2.5-flash")
        d = dispatch(a)
        built = d.build()
        assert isinstance(built, DispatchAgent)

    def test_dispatch_builder_correct_sub_agents(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        d = dispatch(a, b)
        built = d.build()
        assert len(built.sub_agents) == 2

    def test_dispatch_builder_correct_task_names(self):
        a = Agent("email").model("gemini-2.5-flash")
        b = Agent("seo").model("gemini-2.5-flash")
        d = dispatch(a, b)
        built = d.build()
        assert built._task_names == ("email", "seo")

    def test_dispatch_to_ir(self):
        from adk_fluent._ir import DispatchNode

        a = Agent("worker").model("gemini-2.5-flash")
        d = dispatch(a)
        ir = d.to_ir()
        assert isinstance(ir, DispatchNode)
        assert len(ir.children) == 1
        assert ir.task_names == ("worker",)

    def test_dispatch_to_ir_with_stream_to(self):
        from adk_fluent._ir import DispatchNode

        a = Agent("worker").model("gemini-2.5-flash")
        d = dispatch(a, stream_to="progress")
        ir = d.to_ir()
        assert isinstance(ir, DispatchNode)
        assert ir.progress_key == "progress"

    def test_dispatch_builder_fork(self):
        """_fork_for_operator preserves agents list (independent copy)."""
        a = Agent("a").model("gemini-2.5-flash")
        d = dispatch(a)
        forked = d._fork_for_operator()
        # Should be equal but independent
        assert forked._agents == d._agents
        assert forked._agents is not d._agents

    def test_dispatch_builder_max_tasks_method(self):
        a = Agent("a").model("gemini-2.5-flash")
        d = dispatch(a)
        result = d.max_tasks(5)
        assert result._max_tasks == 5
        assert result is d  # returns self


# ======================================================================
# _DispatchBuilder method form (.dispatch() on any builder)
# ======================================================================


class TestDispatchMethodForm:
    def test_dispatch_method_form(self):
        """agent.dispatch(name='x') creates a _DispatchBuilder."""
        a = Agent("email_sender").model("gemini-2.5-flash")
        d = a.dispatch(name="email")
        assert isinstance(d, _DispatchBuilder)

    def test_dispatch_method_form_builds(self):
        a = Agent("email_sender").model("gemini-2.5-flash")
        d = a.dispatch(name="email")
        built = d.build()
        assert isinstance(built, DispatchAgent)


# ======================================================================
# join() factory function
# ======================================================================


class TestJoinFactory:
    def test_join_creates_builder(self):
        result = join()
        assert isinstance(result, BuilderBase)
        assert isinstance(result, _JoinBuilder)

    def test_join_all(self):
        j = join()
        assert j._target_names is None

    def test_join_selective(self):
        j = join("email", "seo")
        assert j._target_names == ("email", "seo")

    def test_join_with_timeout(self):
        j = join(timeout=30)
        assert j._timeout == 30


# ======================================================================
# _JoinBuilder
# ======================================================================


class TestJoinBuilder:
    def test_join_builder_creates_agent(self):
        j = join()
        built = j.build()
        assert isinstance(built, JoinAgent)

    def test_join_builder_target_names(self):
        j = join("email")
        built = j.build()
        assert built._target_names == ("email",)

    def test_join_builder_timeout(self):
        j = join(timeout=30)
        built = j.build()
        assert built._timeout == 30

    def test_join_to_ir(self):
        from adk_fluent._ir import JoinNode

        j = join("seo", timeout=30)
        ir = j.to_ir()
        assert isinstance(ir, JoinNode)
        assert ir.target_names == ("seo",)
        assert ir.timeout == 30


# ======================================================================
# Composition: dispatch + join in pipelines
# ======================================================================


class TestDispatchJoinComposition:
    def test_dispatch_join_compose_with_pipeline(self):
        """a >> dispatch(b) >> c >> join() builds without error."""
        a = Agent("writer").model("gemini-2.5-flash")
        b = Agent("email").model("gemini-2.5-flash")
        c = Agent("formatter").model("gemini-2.5-flash")
        p = a >> dispatch(b) >> c >> join()
        assert isinstance(p, Pipeline)

    def test_dispatch_join_pipeline_builds(self):
        """Full pipeline with dispatch/join builds to ADK agents."""
        from google.adk.agents.base_agent import BaseAgent

        a = Agent("writer").model("gemini-2.5-flash")
        b = Agent("email").model("gemini-2.5-flash")
        c = Agent("formatter").model("gemini-2.5-flash")
        d = Agent("publisher").model("gemini-2.5-flash")
        p = a >> dispatch(b) >> c >> join() >> d
        built = p.build()
        assert isinstance(built, BaseAgent)

    def test_named_dispatch_selective_join(self):
        """Named dispatch + selective join composes correctly."""
        a = Agent("writer").model("gemini-2.5-flash")
        b = Agent("email").model("gemini-2.5-flash")
        c = Agent("seo").model("gemini-2.5-flash")
        d = Agent("formatter").model("gemini-2.5-flash")
        e = Agent("publisher").model("gemini-2.5-flash")
        p = a >> dispatch(b, c, names=["email", "seo"]) >> d >> join("seo", timeout=30) >> e >> join("email")
        assert isinstance(p, Pipeline)
