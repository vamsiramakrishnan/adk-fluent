"""Tests for MiddlewareSchema -- typed middleware declarations."""

from __future__ import annotations

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
