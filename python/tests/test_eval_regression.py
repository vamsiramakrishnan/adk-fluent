"""Tests for eval regression-gating (baseline comparison).

These tests construct EvalReport objects directly with synthetic scores —
no real LLM calls are made.
"""

from __future__ import annotations

import json

import pytest

from adk_fluent._eval import (
    EvalReport,
    MetricDelta,
    RegressionError,
    RegressionResult,
)


def _report(**scores: float) -> EvalReport:
    """Build a passing EvalReport from synthetic metric scores."""
    return EvalReport(
        scores=dict(scores),
        thresholds={k: 0.0 for k in scores},
        passed={k: True for k in scores},
    )


# ======================================================================
# Serialization / baseline round-trip
# ======================================================================


class TestSerialization:
    def test_to_dict_preserves_metrics(self):
        r = _report(response_match_score=0.9, tool_trajectory_avg_score=1.0)
        d = r.to_dict()
        assert d["scores"] == {"response_match_score": 0.9, "tool_trajectory_avg_score": 1.0}
        assert d["thresholds"] == {"response_match_score": 0.0, "tool_trajectory_avg_score": 0.0}
        assert d["passed"] == {"response_match_score": True, "tool_trajectory_avg_score": True}

    def test_from_dict_round_trip(self):
        r = _report(a=0.5, b=0.75)
        r2 = EvalReport.from_dict(r.to_dict())
        assert r2.scores == r.scores
        assert r2.thresholds == r.thresholds
        assert r2.passed == r.passed

    def test_details_coerced_to_str(self):
        r = EvalReport(scores={"a": 1.0}, passed={"a": True}, details=[ValueError("boom")])
        d = r.to_dict()
        assert d["details"] == ["boom"]
        # Round-trips through json without error.
        json.loads(json.dumps(d))

    def test_save_and_load_baseline(self, tmp_path):
        r = _report(response_match_score=0.85, safety_v1=1.0)
        path = str(tmp_path / "baseline.json")
        ret = r.save_baseline(path)
        assert ret is r  # chainable
        loaded = EvalReport.load_baseline(path)
        assert loaded.scores == r.scores

    def test_to_file_alias(self, tmp_path):
        r = _report(a=0.5)
        path = str(tmp_path / "b.json")
        r.to_file(path)
        assert EvalReport.load_baseline(path).scores == {"a": 0.5}


# ======================================================================
# compare_to_baseline
# ======================================================================


class TestCompareToBaseline:
    def test_identical_scores_no_regression(self):
        base = _report(a=0.9, b=1.0)
        cur = _report(a=0.9, b=1.0)
        result = cur.compare_to_baseline(base)
        assert isinstance(result, RegressionResult)
        assert result.ok
        assert bool(result) is True
        assert result.regressions == ()

    def test_drop_beyond_tolerance_regression(self):
        base = _report(a=0.9)
        cur = _report(a=0.5)
        result = cur.compare_to_baseline(base)  # tolerance=0.0
        assert not result.ok
        assert len(result.regressions) == 1
        d = result.regressions[0]
        assert d.metric == "a"
        assert d.baseline == 0.9
        assert d.current == 0.5
        assert d.delta == pytest.approx(-0.4)
        assert d.regressed

    def test_drop_within_tolerance_passes(self):
        base = _report(a=0.90)
        cur = _report(a=0.88)
        # 0.02 drop is within a 0.05 tolerance.
        result = cur.compare_to_baseline(base, tolerance=0.05)
        assert result.ok
        d = result.delta_for("a")
        assert d is not None
        assert not d.regressed
        assert d.delta == pytest.approx(-0.02)

    def test_drop_exactly_at_tolerance_passes(self):
        base = _report(a=0.90)
        cur = _report(a=0.85)
        # Drop of exactly 0.05 with tolerance 0.05 is allowed (not > tolerance).
        result = cur.compare_to_baseline(base, tolerance=0.05)
        assert result.ok

    def test_improved_metric_passes(self):
        base = _report(a=0.7)
        cur = _report(a=0.95)
        result = cur.compare_to_baseline(base)
        assert result.ok
        assert len(result.improvements) == 1
        assert result.improvements[0].metric == "a"
        assert result.delta_for("a").improved

    def test_missing_metric_is_regression(self):
        base = _report(a=0.9, b=0.9)
        cur = _report(a=0.9)  # b dropped entirely
        result = cur.compare_to_baseline(base)
        assert not result.ok
        d = result.delta_for("b")
        assert d is not None
        assert d.is_missing
        assert d.regressed
        assert d.delta is None

    def test_new_metric_is_not_regression(self):
        base = _report(a=0.9)
        cur = _report(a=0.9, c=0.5)  # new metric c
        result = cur.compare_to_baseline(base)
        assert result.ok
        d = result.delta_for("c")
        assert d is not None
        assert d.is_new
        assert not d.regressed

    def test_mixed_some_regress_some_improve(self):
        base = _report(a=0.9, b=0.5, c=0.8)
        cur = _report(a=0.6, b=0.9, c=0.8)  # a regresses, b improves, c stable
        result = cur.compare_to_baseline(base)
        assert not result.ok
        assert {d.metric for d in result.regressions} == {"a"}
        assert {d.metric for d in result.improvements} == {"b"}

    def test_negative_tolerance_rejected(self):
        base = _report(a=0.9)
        cur = _report(a=0.9)
        with pytest.raises(ValueError):
            cur.compare_to_baseline(base, tolerance=-0.1)


# ======================================================================
# Baseline argument coercion (EvalReport / dict / path)
# ======================================================================


class TestBaselineCoercion:
    def test_compare_against_dict(self):
        base = _report(a=0.9)
        cur = _report(a=0.5)
        result = cur.compare_to_baseline(base.to_dict())
        assert not result.ok

    def test_compare_against_path(self, tmp_path):
        base = _report(a=0.9)
        path = str(tmp_path / "base.json")
        base.save_baseline(path)
        cur = _report(a=0.95)
        result = cur.compare_to_baseline(path)
        assert result.ok

    def test_invalid_baseline_type(self):
        cur = _report(a=0.9)
        with pytest.raises(TypeError):
            cur.compare_to_baseline(123)  # type: ignore[arg-type]


# ======================================================================
# assert_no_regression — CI gate
# ======================================================================


class TestAssertNoRegression:
    def test_passes_when_identical(self):
        base = _report(a=0.9, b=1.0)
        cur = _report(a=0.9, b=1.0)
        result = cur.assert_no_regression(base)
        assert isinstance(result, RegressionResult)
        assert result.ok

    def test_raises_on_regression(self):
        base = _report(a=0.9)
        cur = _report(a=0.5)
        with pytest.raises(RegressionError) as exc_info:
            cur.assert_no_regression(base)
        # Structured result attached for CI inspection.
        assert isinstance(exc_info.value.result, RegressionResult)
        assert not exc_info.value.result.ok
        assert "REGRESSION DETECTED" in str(exc_info.value)

    def test_regression_error_is_assertion_error(self):
        # Integrates with pytest / assert-based CI tooling.
        assert issubclass(RegressionError, AssertionError)

    def test_passes_within_tolerance(self):
        base = _report(a=0.90)
        cur = _report(a=0.88)
        result = cur.assert_no_regression(base, tolerance=0.05)
        assert result.ok

    def test_improved_passes(self):
        base = _report(a=0.7)
        cur = _report(a=0.99)
        result = cur.assert_no_regression(base)
        assert result.ok

    def test_round_trip_saved_report_gates(self, tmp_path):
        # Save a report, reload as baseline, gate the same report -> no regression.
        original = _report(response_match_score=0.85, safety_v1=1.0)
        path = str(tmp_path / "golden.json")
        original.save_baseline(path)
        cur = EvalReport.from_dict(original.to_dict())
        cur.assert_no_regression(path)  # should not raise


# ======================================================================
# MetricDelta direct behaviour
# ======================================================================


class TestMetricDelta:
    def test_delta_none_when_missing(self):
        d = MetricDelta(metric="a", baseline=0.9, current=None)
        assert d.delta is None
        assert d.is_missing
        assert d.regressed

    def test_describe_strings(self):
        assert "regressed" in MetricDelta("a", 0.9, 0.5).describe()
        assert "improved" in MetricDelta("a", 0.5, 0.9).describe()
        assert "MISSING" in MetricDelta("a", 0.9, None).describe()
        assert "NEW" in MetricDelta("a", None, 0.5).describe()

    def test_summary_contains_metrics(self):
        base = _report(a=0.9)
        cur = _report(a=0.5)
        s = cur.compare_to_baseline(base).summary()
        assert "Regression Report" in s
        assert "a" in s
