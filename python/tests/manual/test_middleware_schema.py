"""Tests for MiddlewareSchema -- typed middleware declarations."""

from __future__ import annotations

import asyncio
from typing import Annotated

from adk_fluent._middleware_schema import MiddlewareSchema
from adk_fluent._schema_base import Reads, Writes


class AppMiddleware(MiddlewareSchema):
    request_id: Annotated[str, Reads(scope="app")]
    session_token: Annotated[str, Reads()]


class TempMiddleware(MiddlewareSchema):
    log_entry: Annotated[str, Writes(scope="temp")]
    trace_id: Annotated[str, Writes()]


class MixedMiddleware(MiddlewareSchema):
    config_key: Annotated[str, Reads(scope="app")]
    result: Annotated[int, Writes(scope="temp")]


class EmptyMiddleware(MiddlewareSchema):
    pass


class TestMiddlewareSchema:
    def test_reads_keys(self):
        assert AppMiddleware.reads_keys() == frozenset({"app:request_id", "session_token"})

    def test_writes_keys(self):
        assert TempMiddleware.writes_keys() == frozenset({"temp:log_entry", "trace_id"})

    def test_mixed_reads_writes(self):
        assert MixedMiddleware.reads_keys() == frozenset({"app:config_key"})
        assert MixedMiddleware.writes_keys() == frozenset({"temp:result"})

    def test_empty_schema(self):
        assert EmptyMiddleware.reads_keys() == frozenset()
        assert EmptyMiddleware.writes_keys() == frozenset()

    def test_repr(self):
        m = MixedMiddleware()
        r = repr(m)
        assert "MixedMiddleware" in r
        assert "config_key" in r
        assert "result" in r


class TestConditionalMiddlewareDeferred:
    """_ConditionalMiddleware returns guarded wrappers, not None."""

    def test_guarded_wrapper_is_callable(self):
        """__getattr__ returns a callable wrapper even when condition is false."""
        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            async def before_agent(self, ctx, name):
                return "fired"

        cond = _ConditionalMiddleware(lambda: False, Inner())
        hook = cond.before_agent
        assert callable(hook)

    def test_guarded_wrapper_skips_when_false(self):
        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            async def before_agent(self, ctx, name):
                return "fired"

        cond = _ConditionalMiddleware(lambda: False, Inner())
        result = asyncio.run(cond.before_agent(None, "x"))
        assert result is None

    def test_guarded_wrapper_fires_when_true(self):
        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            async def before_agent(self, ctx, name):
                return "fired"

        cond = _ConditionalMiddleware(lambda: True, Inner())
        result = asyncio.run(cond.before_agent(None, "x"))
        assert result == "fired"

    def test_string_shortcut_still_works(self):
        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            async def before_agent(self, ctx, name):
                return "fired"

        # "stream" won't match default execution mode
        cond = _ConditionalMiddleware("stream", Inner())
        hook = cond.before_agent
        assert callable(hook)

    def test_schema_forwarded(self):
        """schema attribute is forwarded from inner middleware."""
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent.middleware import _ConditionalMiddleware

        class MySchema(MiddlewareSchema):
            pass

        class Inner:
            schema = MySchema

        cond = _ConditionalMiddleware(lambda: True, Inner())
        assert cond.schema is MySchema

    def test_agents_forwarded(self):
        """agents attribute is forwarded from inner middleware."""
        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            agents = "writer"

        cond = _ConditionalMiddleware(lambda: True, Inner())
        assert cond.agents == "writer"

    def test_missing_attr_raises(self):
        """Accessing non-existent attribute raises AttributeError."""
        import pytest

        from adk_fluent.middleware import _ConditionalMiddleware

        class Inner:
            pass

        cond = _ConditionalMiddleware(lambda: True, Inner())
        with pytest.raises(AttributeError):
            _ = cond.nonexistent_hook


class TestScopedMiddlewareSchema:
    """_ScopedMiddleware forwards schema from inner middleware."""

    def test_schema_accessible_via_getattr(self):
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent.middleware import _ScopedMiddleware

        class MySchema(MiddlewareSchema):
            pass

        class Inner:
            schema = MySchema

            async def before_agent(self, ctx, name):
                pass

        scoped = _ScopedMiddleware("writer", Inner())
        assert scoped.schema is MySchema

    def test_agents_overrides_inner(self):
        from adk_fluent.middleware import _ScopedMiddleware

        class Inner:
            agents = "original"

        scoped = _ScopedMiddleware("overridden", Inner())
        assert scoped.agents == "overridden"


class TestMWhenPredicateSchema:
    """M.when() accepts PredicateSchema subclasses."""

    def test_m_when_predicate_creates_conditional(self):
        from adk_fluent._middleware import M
        from adk_fluent._predicate_schema import PredicateSchema

        class IsPremium(PredicateSchema):
            @staticmethod
            def evaluate():
                return True

        class Inner:
            async def before_agent(self, ctx, name):
                pass

        result = M.when(IsPremium, Inner())
        assert len(result) == 1
        wrapped = result.to_stack()[0]
        assert callable(getattr(wrapped, "before_agent", None))

    def test_m_when_string_still_works(self):
        from adk_fluent._middleware import M

        class Inner:
            async def before_agent(self, ctx, name):
                pass

        result = M.when("stream", Inner())
        assert len(result) == 1

    def test_m_when_callable_still_works(self):
        from adk_fluent._middleware import M

        class Inner:
            async def before_agent(self, ctx, name):
                pass

        result = M.when(lambda: True, Inner())
        assert len(result) == 1


class TestContractCheckerPass14:
    """Pass 14: Middleware schema validation in contract checker."""

    def _make_agent_node(self, name, output_key=None):
        """Create a minimal AgentNode-like object for testing."""
        from types import SimpleNamespace

        return SimpleNamespace(
            name=name,
            output_key=output_key,
            tool_schema=None,
            callback_schema=None,
            prompt_schema=None,
            writes_keys=frozenset(),
            reads_keys=frozenset(),
            include_contents="default",
            instruction="",
            context_spec=None,
            produces_type=None,
            consumes_type=None,
            rules=(),
            predicate=None,
        )

    def _make_sequence(self, children, middlewares=()):
        """Create a SequenceNode with optional middlewares."""
        from adk_fluent._ir_generated import SequenceNode

        return SequenceNode(
            name="test_seq",
            children=tuple(children),
            middlewares=tuple(middlewares),
        )

    def test_scoped_middleware_reads_satisfied(self):
        """Scoped middleware whose reads are produced upstream: no warnings."""
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent.testing.contracts import check_contracts

        class NeedsResult(MiddlewareSchema):
            result: Annotated[str, Reads()]

        class MyMW:
            agents = "reviewer"
            schema = NeedsResult

        producer = self._make_agent_node("writer", output_key="result")
        consumer = self._make_agent_node("reviewer")
        seq = self._make_sequence([producer, consumer], middlewares=[MyMW()])

        issues = check_contracts(seq)
        mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
        assert len(mw_issues) == 0

    def test_scoped_middleware_reads_unsatisfied(self):
        """Scoped middleware whose reads are NOT produced upstream: warning."""
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent.testing.contracts import check_contracts

        class NeedsMissing(MiddlewareSchema):
            missing_key: Annotated[str, Reads()]

        class MyMW:
            agents = "reviewer"
            schema = NeedsMissing

        producer = self._make_agent_node("writer", output_key="result")
        consumer = self._make_agent_node("reviewer")
        seq = self._make_sequence([producer, consumer], middlewares=[MyMW()])

        issues = check_contracts(seq)
        mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
        assert len(mw_issues) == 1
        assert "missing_key" in mw_issues[0]["message"]

    def test_unscoped_middleware_skipped(self):
        """Middleware without agents scope: no validation."""
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent.testing.contracts import check_contracts

        class NeedsMissing(MiddlewareSchema):
            missing_key: Annotated[str, Reads()]

        class GlobalMW:
            schema = NeedsMissing

        agent = self._make_agent_node("writer")
        seq = self._make_sequence([agent], middlewares=[GlobalMW()])

        issues = check_contracts(seq)
        mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
        assert len(mw_issues) == 0

    def test_middleware_writes_promoted(self):
        """Scoped middleware writes become available to downstream middleware."""
        from adk_fluent._middleware_schema import MiddlewareSchema
        from adk_fluent.testing.contracts import check_contracts

        class WriterSchema(MiddlewareSchema):
            enriched: Annotated[str, Writes()]

        class WriterMW:
            agents = "enricher"
            schema = WriterSchema

        class ReaderSchema(MiddlewareSchema):
            enriched: Annotated[str, Reads()]

        class ReaderMW:
            agents = "consumer"
            schema = ReaderSchema

        enricher = self._make_agent_node("enricher")
        consumer = self._make_agent_node("consumer")
        seq = self._make_sequence([enricher, consumer], middlewares=[WriterMW(), ReaderMW()])

        issues = check_contracts(seq)
        mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
        assert len(mw_issues) == 0
