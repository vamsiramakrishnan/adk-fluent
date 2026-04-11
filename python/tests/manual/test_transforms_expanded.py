"""Tests for S.accumulate, counter, history, validate, require,
flatten, unflatten, zip, group_by."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from adk_fluent._transforms import S, StateDelta, StateReplacement

# ---------------------------------------------------------------------------
# Task 1: S.accumulate
# ---------------------------------------------------------------------------


class TestAccumulate:
    def test_appends_to_existing_list(self):
        t = S.accumulate("score")
        result = t({"score": 42, "score_all": [10, 20]})
        assert isinstance(result, StateDelta)
        assert result.updates["score_all"] == [10, 20, 42]

    def test_creates_list_when_missing(self):
        t = S.accumulate("score")
        result = t({"score": 42})
        assert result.updates["score_all"] == [42]

    def test_skips_none(self):
        t = S.accumulate("score")
        result = t({"score_all": [1, 2]})
        assert result.updates["score_all"] == [1, 2]

    def test_default_into_name(self):
        t = S.accumulate("val")
        assert "val_all" in t({"val": 1}).updates

    def test_custom_into(self):
        t = S.accumulate("val", into="history")
        result = t({"val": 5})
        assert result.updates["history"] == [5]

    def test_reads_keys(self):
        t = S.accumulate("x")
        assert t._reads_keys == frozenset({"x", "x_all"})

    def test_writes_keys(self):
        t = S.accumulate("x")
        assert t._writes_keys == frozenset({"x_all"})


# ---------------------------------------------------------------------------
# Task 1: S.counter
# ---------------------------------------------------------------------------


class TestCounter:
    def test_increments(self):
        t = S.counter("n")
        result = t({"n": 5})
        assert result.updates["n"] == 6

    def test_starts_at_zero(self):
        t = S.counter("n")
        result = t({})
        assert result.updates["n"] == 1

    def test_custom_step(self):
        t = S.counter("n", step=3)
        result = t({"n": 10})
        assert result.updates["n"] == 13

    def test_negative_step(self):
        t = S.counter("n", step=-1)
        result = t({"n": 5})
        assert result.updates["n"] == 4

    def test_reads_keys(self):
        t = S.counter("x")
        assert t._reads_keys == frozenset({"x"})

    def test_writes_keys(self):
        t = S.counter("x")
        assert t._writes_keys == frozenset({"x"})


# ---------------------------------------------------------------------------
# Task 2: S.history
# ---------------------------------------------------------------------------


class TestHistory:
    def test_appends_value(self):
        t = S.history("val")
        result = t({"val": 42, "val_history": [1, 2]})
        assert result.updates["val_history"] == [1, 2, 42]

    def test_creates_list_when_missing(self):
        t = S.history("val")
        result = t({"val": "hello"})
        assert result.updates["val_history"] == ["hello"]

    def test_respects_max_size(self):
        t = S.history("val", max_size=3)
        result = t({"val": 4, "val_history": [1, 2, 3]})
        assert result.updates["val_history"] == [2, 3, 4]

    def test_skips_missing(self):
        t = S.history("val")
        result = t({"val_history": [1, 2]})
        assert result.updates["val_history"] == [1, 2]

    def test_reads_keys(self):
        t = S.history("x")
        assert t._reads_keys == frozenset({"x", "x_history"})

    def test_writes_keys(self):
        t = S.history("x")
        assert t._writes_keys == frozenset({"x_history"})


# ---------------------------------------------------------------------------
# Task 3: S.validate
# ---------------------------------------------------------------------------


@dataclass
class SampleSchema:
    name: str
    age: int


class TestValidate:
    def test_passes_valid(self):
        t = S.validate(SampleSchema)
        result = t({"name": "Alice", "age": 30})
        assert isinstance(result, StateDelta)
        assert result.updates == {}

    def test_raises_on_invalid(self):
        t = S.validate(SampleSchema)
        with pytest.raises(ValueError, match="State validation failed"):
            t({"name": "Alice"})  # missing 'age'

    def test_reads_keys_none(self):
        t = S.validate(SampleSchema)
        assert t._reads_keys is None

    def test_writes_keys_empty(self):
        t = S.validate(SampleSchema)
        assert t._writes_keys == frozenset()

    def test_name(self):
        t = S.validate(SampleSchema)
        assert "SampleSchema" in t.__name__


# ---------------------------------------------------------------------------
# Task 3: S.require
# ---------------------------------------------------------------------------


class TestRequire:
    def test_passes_when_present(self):
        t = S.require("a", "b")
        result = t({"a": 1, "b": "yes"})
        assert isinstance(result, StateDelta)
        assert result.updates == {}

    def test_raises_missing(self):
        t = S.require("a", "b")
        with pytest.raises(ValueError, match="Required state keys missing"):
            t({"a": 1})

    def test_raises_falsy(self):
        t = S.require("a")
        with pytest.raises(ValueError, match="Required state keys missing"):
            t({"a": 0})

    def test_reads_keys(self):
        t = S.require("x", "y")
        assert t._reads_keys == frozenset({"x", "y"})

    def test_writes_keys(self):
        t = S.require("x")
        assert t._writes_keys == frozenset()


# ---------------------------------------------------------------------------
# Task 4: S.flatten
# ---------------------------------------------------------------------------


class TestFlatten:
    def test_flattens_nested(self):
        t = S.flatten("cfg")
        result = t({"cfg": {"a": {"b": 1, "c": 2}, "d": 3}})
        assert result.updates["a.b"] == 1
        assert result.updates["a.c"] == 2
        assert result.updates["d"] == 3

    def test_custom_separator(self):
        t = S.flatten("cfg", separator="_")
        result = t({"cfg": {"a": {"b": 1}}})
        assert result.updates["a_b"] == 1

    def test_empty_dict(self):
        t = S.flatten("cfg")
        result = t({"cfg": {}})
        assert result.updates == {}

    def test_missing_key(self):
        t = S.flatten("cfg")
        result = t({})
        assert result.updates == {}

    def test_reads_keys(self):
        t = S.flatten("cfg")
        assert t._reads_keys == frozenset({"cfg"})

    def test_writes_keys_none(self):
        t = S.flatten("cfg")
        assert t._writes_keys is None


# ---------------------------------------------------------------------------
# Task 4: S.unflatten
# ---------------------------------------------------------------------------


class TestUnflatten:
    def test_unflattens_dotted(self):
        t = S.unflatten()
        result = t({"a.b": 1, "a.c": 2, "d": 3})
        assert isinstance(result, StateReplacement)
        assert result.new_state["a"] == {"b": 1, "c": 2}
        assert result.new_state["d"] == 3

    def test_custom_separator(self):
        t = S.unflatten(separator="_")
        result = t({"a_b": 1})
        assert result.new_state["a"] == {"b": 1}

    def test_passthrough_non_dotted(self):
        t = S.unflatten()
        result = t({"simple": 42})
        assert result.new_state["simple"] == 42

    def test_reads_writes_none(self):
        t = S.unflatten()
        assert t._reads_keys is None
        assert t._writes_keys is None


# ---------------------------------------------------------------------------
# Task 4: S.zip
# ---------------------------------------------------------------------------


class TestZip:
    def test_zips_parallel_lists(self):
        t = S.zip("names", "scores")
        result = t({"names": ["a", "b"], "scores": [1, 2]})
        assert result.updates["zipped"] == [("a", 1), ("b", 2)]

    def test_custom_into(self):
        t = S.zip("x", "y", into="pairs")
        result = t({"x": [1, 2], "y": [3, 4]})
        assert result.updates["pairs"] == [(1, 3), (2, 4)]

    def test_unequal_lengths(self):
        t = S.zip("a", "b")
        result = t({"a": [1, 2, 3], "b": [10, 20]})
        assert result.updates["zipped"] == [(1, 10), (2, 20)]

    def test_reads_keys(self):
        t = S.zip("a", "b", "c")
        assert t._reads_keys == frozenset({"a", "b", "c"})

    def test_writes_keys(self):
        t = S.zip("a", "b", into="out")
        assert t._writes_keys == frozenset({"out"})


# ---------------------------------------------------------------------------
# Task 4: S.group_by
# ---------------------------------------------------------------------------


class TestGroupBy:
    def test_groups_by_key_fn(self):
        t = S.group_by("items", key_fn=lambda x: x["type"], into="grouped")
        result = t(
            {
                "items": [
                    {"type": "a", "v": 1},
                    {"type": "b", "v": 2},
                    {"type": "a", "v": 3},
                ]
            }
        )
        assert result.updates["grouped"] == {
            "a": [{"type": "a", "v": 1}, {"type": "a", "v": 3}],
            "b": [{"type": "b", "v": 2}],
        }

    def test_empty_list(self):
        t = S.group_by("items", key_fn=lambda x: x, into="grouped")
        result = t({"items": []})
        assert result.updates["grouped"] == {}

    def test_reads_keys(self):
        t = S.group_by("data", key_fn=str, into="out")
        assert t._reads_keys == frozenset({"data"})

    def test_writes_keys(self):
        t = S.group_by("data", key_fn=str, into="out")
        assert t._writes_keys == frozenset({"out"})
