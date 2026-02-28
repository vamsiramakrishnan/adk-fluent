"""Cross-module uniformity tests for .when() conditionality.

Verifies that the same predicate (callable and string) works identically
across P.when, S.when, and C.when.
"""

import asyncio
import concurrent.futures

from adk_fluent._context import C
from adk_fluent._predicate_utils import evaluate_predicate
from adk_fluent._prompt import P
from adk_fluent._transforms import S, StateDelta


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class _MockState(dict):
    pass


class _MockSession:
    def __init__(self):
        self.events = []


class _MockCtx:
    def __init__(self, state=None):
        self.session = _MockSession()
        self.state = _MockState(state or {})


# ======================================================================
# Shared evaluator
# ======================================================================


class TestEvaluatePredicate:
    def test_none_is_false(self):
        assert evaluate_predicate(None, {"x": 1}) is False

    def test_string_key_truthy(self):
        assert evaluate_predicate("x", {"x": 1}) is True

    def test_string_key_falsy(self):
        assert evaluate_predicate("x", {"x": 0}) is False

    def test_string_key_missing(self):
        assert evaluate_predicate("x", {}) is False

    def test_callable_receives_state(self):
        assert evaluate_predicate(lambda s: s.get("x") == 42, {"x": 42}) is True

    def test_callable_exception_is_false(self):
        assert evaluate_predicate(lambda s: s["missing"], {}) is False


# ======================================================================
# Uniform string predicate across P, S, C
# ======================================================================


class TestStringPredicateUniformity:
    """Same string predicate should gate identically across all modules."""

    def test_p_when_string_truthy(self):
        prompt = P.section("info", "details")
        t = P.when("show", prompt)
        result = t.build(state={"show": True})
        assert "details" in result

    def test_p_when_string_falsy(self):
        prompt = P.section("info", "details")
        t = P.when("show", prompt)
        result = t.build(state={"show": False})
        assert "details" not in result

    def test_s_when_string_truthy(self):
        t = S.when("show", S.set(done=True))
        result = t({"show": True})
        assert result.updates == {"done": True}

    def test_s_when_string_falsy(self):
        t = S.when("show", S.set(done=True))
        result = t({"show": False})
        assert result.updates == {}

    def test_c_when_string_truthy(self):
        t = C.when("show", C.from_state("topic"))
        ctx = _MockCtx(state={"show": True, "topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert "AI" in result

    def test_c_when_string_falsy(self):
        t = C.when("show", C.from_state("topic"))
        ctx = _MockCtx(state={"show": False, "topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# Uniform callable predicate across P, S, C
# ======================================================================


class TestCallablePredicateUniformity:
    """Same callable predicate should gate identically across all modules."""

    pred = staticmethod(lambda s: s.get("score", 0) > 5)

    def test_p_when_callable_true(self):
        t = P.when(self.pred, P.section("info", "details"))
        result = t.build(state={"score": 10})
        assert "details" in result

    def test_p_when_callable_false(self):
        t = P.when(self.pred, P.section("info", "details"))
        result = t.build(state={"score": 2})
        assert "details" not in result

    def test_s_when_callable_true(self):
        t = S.when(self.pred, S.set(done=True))
        result = t({"score": 10})
        assert result.updates == {"done": True}

    def test_s_when_callable_false(self):
        t = S.when(self.pred, S.set(done=True))
        result = t({"score": 2})
        assert result.updates == {}

    def test_c_when_callable_true(self):
        t = C.when(self.pred, C.from_state("topic"))
        ctx = _MockCtx(state={"score": 10, "topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert "AI" in result

    def test_c_when_callable_false(self):
        t = C.when(self.pred, C.from_state("topic"))
        ctx = _MockCtx(state={"score": 2, "topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# Exception safety across all modules
# ======================================================================


class TestExceptionSafetyUniformity:
    """Exception in predicate should be treated as False across all modules."""

    bad_pred = staticmethod(lambda s: s["nonexistent"]["deep"])

    def test_p_when_exception(self):
        t = P.when(self.bad_pred, P.section("info", "details"))
        result = t.build(state={})
        assert "details" not in result

    def test_s_when_exception(self):
        t = S.when(self.bad_pred, S.set(done=True))
        result = t({})
        assert isinstance(result, StateDelta)
        assert result.updates == {}

    def test_c_when_exception(self):
        t = C.when(self.bad_pred, C.from_state("topic"))
        ctx = _MockCtx(state={"topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert result == ""
