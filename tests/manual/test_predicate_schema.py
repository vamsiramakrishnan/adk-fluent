"""Tests for PredicateSchema — typed predicate declarations."""

from __future__ import annotations

from typing import Annotated

import pytest

from adk_fluent._predicate_schema import PredicateSchema
from adk_fluent._schema_base import Reads


class QualityGate(PredicateSchema):
    score: Annotated[float, Reads()]
    threshold: Annotated[float, Reads()]

    @staticmethod
    def evaluate(score: float, threshold: float) -> bool:
        return score >= threshold


class SimpleCheck(PredicateSchema):
    active: Annotated[bool, Reads()]

    @staticmethod
    def evaluate(active: bool) -> bool:
        return active


class NoEvaluate(PredicateSchema):
    x: Annotated[str, Reads()]


class TestPredicateSchemaFields:
    def test_reads_keys(self):
        assert QualityGate.reads_keys() == frozenset({"score", "threshold"})

    def test_reads_keys_simple(self):
        assert SimpleCheck.reads_keys() == frozenset({"active"})


class TestPredicateSchemaCallable:
    def test_call_passes_state_keys(self):
        state = {"score": 0.9, "threshold": 0.7}
        assert QualityGate(state) is True

    def test_call_fails_state_keys(self):
        state = {"score": 0.3, "threshold": 0.7}
        assert QualityGate(state) is False

    def test_simple_check(self):
        assert SimpleCheck({"active": True}) is True
        assert SimpleCheck({"active": False}) is False

    def test_scoped_key_reads(self):
        class ScopedPred(PredicateSchema):
            tier: Annotated[str, Reads(scope="user")]

            @staticmethod
            def evaluate(tier: str) -> bool:
                return tier == "premium"

        assert ScopedPred.reads_keys() == frozenset({"user:tier"})
        assert ScopedPred({"user:tier": "premium"}) is True

    def test_missing_evaluate_raises(self):
        with pytest.raises(TypeError, match="evaluate"):
            NoEvaluate({"x": "hello"})


class TestPredicateSchemaRouting:
    def test_route_when_accepts_predicate_schema(self):
        from adk_fluent import Agent, Route

        a = Agent("hi").instruct("Hi")
        b = Agent("lo").instruct("Lo")

        route = Route("score").when(QualityGate, a).otherwise(b)
        ir = route.to_ir()
        # The predicate stored in IR should be callable
        pred, _ = ir.rules[0]
        assert pred({"score": 0.9, "threshold": 0.5}) is True
        assert pred({"score": 0.2, "threshold": 0.5}) is False
