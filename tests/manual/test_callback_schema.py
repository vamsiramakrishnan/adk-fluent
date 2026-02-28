"""Tests for CallbackSchema -- typed callback declarations."""

from __future__ import annotations

from typing import Annotated

from adk_fluent._callback_schema import CallbackSchema
from adk_fluent._schema_base import Reads, Writes


class AuditCallbacks(CallbackSchema):
    user_tier: Annotated[str, Reads(scope="user")]
    intent: Annotated[str, Reads()]
    call_count: Annotated[int, Writes(scope="temp")]
    audit_log: Annotated[list, Writes()]


class EmptyCallbacks(CallbackSchema):
    pass


class TestCallbackSchemaFields:
    def test_reads_keys(self):
        assert AuditCallbacks.reads_keys() == frozenset({"user:user_tier", "intent"})

    def test_writes_keys(self):
        assert AuditCallbacks.writes_keys() == frozenset({"temp:call_count", "audit_log"})

    def test_empty_schema(self):
        assert EmptyCallbacks.reads_keys() == frozenset()
        assert EmptyCallbacks.writes_keys() == frozenset()

    def test_dir_includes_fields(self):
        d = dir(AuditCallbacks)
        assert "user_tier" in d
        assert "call_count" in d


class TestCallbackSchemaBuilderIntegration:
    def test_callback_schema_on_agent(self):
        from adk_fluent import Agent

        a = Agent("proc").callback_schema(AuditCallbacks).instruct("Process")
        ir = a.to_ir()
        assert ir.callback_schema is AuditCallbacks

    def test_callback_schema_adds_to_reads_keys(self):
        from adk_fluent import Agent

        a = Agent("proc").callback_schema(AuditCallbacks).instruct("Process")
        ir = a.to_ir()
        assert "intent" in ir.reads_keys
        assert "user:user_tier" in ir.reads_keys

    def test_callback_schema_adds_to_writes_keys(self):
        from adk_fluent import Agent

        a = Agent("proc").callback_schema(AuditCallbacks).instruct("Process")
        ir = a.to_ir()
        assert "audit_log" in ir.writes_keys
        assert "temp:call_count" in ir.writes_keys
