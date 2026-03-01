"""Tests for contract checker passes on ToolSchema/CallbackSchema/PredicateSchema."""

from __future__ import annotations

from typing import Annotated

from adk_fluent import Agent, Route
from adk_fluent._callback_schema import CallbackSchema
from adk_fluent._predicate_schema import PredicateSchema
from adk_fluent._schema_base import Reads, Writes
from adk_fluent._tool_schema import ToolSchema
from adk_fluent.testing.contracts import check_contracts


class ProducerTools(ToolSchema):
    query: Annotated[str, Reads()]
    results: Annotated[list, Writes()]


class ConsumerCallbacks(CallbackSchema):
    results: Annotated[list, Reads()]
    log_entry: Annotated[str, Writes()]


class MissingKeyTools(ToolSchema):
    nonexistent: Annotated[str, Reads()]


class GatePred(PredicateSchema):
    score: Annotated[float, Reads()]

    @staticmethod
    def evaluate(score: float) -> bool:
        return score > 0.5


class TestToolSchemaContracts:
    def test_tool_reads_satisfied(self):
        pipeline = Agent("a").instruct("produce query").writes("query") >> Agent("b").instruct("search").tool_schema(
            ProducerTools
        )
        issues = check_contracts(pipeline.to_ir())
        tool_issues = [i for i in issues if isinstance(i, dict) and "nonexistent" in i.get("message", "")]
        assert len(tool_issues) == 0

    def test_tool_reads_missing(self):
        pipeline = Agent("a").instruct("do nothing") >> Agent("b").instruct("search").tool_schema(MissingKeyTools)
        issues = check_contracts(pipeline.to_ir())
        missing = [i for i in issues if isinstance(i, dict) and "nonexistent" in i.get("message", "")]
        assert len(missing) >= 1


class TestCallbackSchemaContracts:
    def test_callback_reads_satisfied(self):
        pipeline = Agent("a").instruct("produce").tool_schema(ProducerTools) >> Agent("b").instruct(
            "consume"
        ).callback_schema(ConsumerCallbacks)
        issues = check_contracts(pipeline.to_ir())
        cb_issues = [
            i
            for i in issues
            if isinstance(i, dict) and "results" in i.get("message", "") and "not produced" in i.get("message", "")
        ]
        assert len(cb_issues) == 0


class TestPredicateSchemaContracts:
    def test_predicate_reads_missing(self):
        a = Agent("hi").instruct("Hi")
        b = Agent("lo").instruct("Lo")
        pipeline = Agent("start").instruct("start") >> Route().when(GatePred, a).otherwise(b)
        issues = check_contracts(pipeline.to_ir())
        pred_issues = [i for i in issues if isinstance(i, dict) and "score" in i.get("message", "")]
        assert len(pred_issues) >= 1
