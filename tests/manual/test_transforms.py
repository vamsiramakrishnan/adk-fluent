"""Tests for S — state transform factories that compose with >>."""
import pytest
from adk_fluent import S, Agent
from adk_fluent._transforms import StateDelta, StateReplacement
from adk_fluent.workflow import Pipeline


# ======================================================================
# Unit tests — each factory in isolation (pure dict -> dict)
# ======================================================================

class TestPick:
    def test_keeps_specified_keys(self):
        fn = S.pick("a", "b")
        result = fn({"a": 1, "b": 2, "c": 3})
        assert isinstance(result, StateReplacement)
        assert result.new_state == {"a": 1, "b": 2}

    def test_missing_keys_skipped(self):
        fn = S.pick("a", "z")
        result = fn({"a": 1, "b": 2})
        assert isinstance(result, StateReplacement)
        assert result.new_state == {"a": 1}

    def test_empty_state(self):
        fn = S.pick("a")
        result = fn({})
        assert isinstance(result, StateReplacement)
        assert result.new_state == {}

    def test_name(self):
        fn = S.pick("x", "y")
        assert fn.__name__ == "pick_x_y"


class TestDrop:
    def test_removes_specified_keys(self):
        fn = S.drop("secret")
        result = fn({"a": 1, "secret": "x", "b": 2})
        assert isinstance(result, StateReplacement)
        assert result.new_state == {"a": 1, "b": 2}

    def test_missing_keys_no_error(self):
        fn = S.drop("z")
        result = fn({"a": 1})
        assert isinstance(result, StateReplacement)
        assert result.new_state == {"a": 1}

    def test_name(self):
        fn = S.drop("x", "y")
        assert fn.__name__ == "drop_x_y"


class TestRename:
    def test_renames_keys(self):
        fn = S.rename(result="input")
        result = fn({"result": 42, "other": 7})
        assert isinstance(result, StateReplacement)
        assert result.new_state == {"input": 42, "other": 7}

    def test_multiple_renames(self):
        fn = S.rename(a="x", b="y")
        result = fn({"a": 1, "b": 2, "c": 3})
        assert isinstance(result, StateReplacement)
        assert result.new_state == {"x": 1, "y": 2, "c": 3}

    def test_unmapped_keys_pass_through(self):
        fn = S.rename(a="x")
        result = fn({"a": 1, "b": 2})
        assert "b" in result.new_state

    def test_name(self):
        fn = S.rename(old="new")
        assert fn.__name__ == "rename_old"


class TestDefault:
    def test_fills_missing(self):
        fn = S.default(score=0.5)
        result = fn({"name": "test"})
        assert isinstance(result, StateDelta)
        assert result.updates == {"score": 0.5}

    def test_does_not_overwrite_existing(self):
        fn = S.default(score=0.5)
        result = fn({"score": 0.9})
        assert isinstance(result, StateDelta)
        assert result.updates == {}

    def test_name(self):
        fn = S.default(a=1, b=2)
        assert fn.__name__ == "default_a_b"


class TestMerge:
    def test_default_join(self):
        fn = S.merge("a", "b", into="combined")
        result = fn({"a": "hello", "b": "world"})
        assert isinstance(result, StateDelta)
        assert result.updates == {"combined": "hello\nworld"}

    def test_custom_fn(self):
        fn = S.merge("x", "y", into="total", fn=lambda x, y: x + y)
        result = fn({"x": 10, "y": 20})
        assert isinstance(result, StateDelta)
        assert result.updates == {"total": 30}

    def test_missing_key_skipped(self):
        fn = S.merge("a", "b", into="c")
        result = fn({"a": "only"})
        assert isinstance(result, StateDelta)
        assert result.updates == {"c": "only"}

    def test_name(self):
        fn = S.merge("a", "b", into="c")
        assert fn.__name__ == "merge_a_b_into_c"


class TestTransform:
    def test_applies_function(self):
        fn = S.transform("text", str.upper)
        result = fn({"text": "hello"})
        assert isinstance(result, StateDelta)
        assert result.updates == {"text": "HELLO"}

    def test_missing_key_returns_empty(self):
        fn = S.transform("text", str.upper)
        result = fn({"other": 1})
        assert isinstance(result, StateDelta)
        assert result.updates == {}

    def test_name(self):
        fn = S.transform("x", abs)
        assert fn.__name__ == "transform_x_abs"


class TestGuard:
    def test_passes_on_true(self):
        fn = S.guard(lambda s: "key" in s)
        result = fn({"key": 1})
        assert isinstance(result, StateDelta)
        assert result.updates == {}

    def test_raises_on_false(self):
        fn = S.guard(lambda s: "key" in s, msg="Missing key")
        with pytest.raises(ValueError, match="Missing key"):
            fn({"other": 1})


class TestLog:
    def test_returns_empty_delta(self, capsys):
        fn = S.log("a")
        result = fn({"a": 1, "b": 2})
        assert isinstance(result, StateDelta)
        assert result.updates == {}

    def test_prints_selected_keys(self, capsys):
        fn = S.log("a", label="test")
        fn({"a": 1, "b": 2})
        captured = capsys.readouterr()
        assert "[test]" in captured.out
        assert "'a': 1" in captured.out

    def test_name(self):
        fn = S.log("x", "y")
        assert fn.__name__ == "log_x_y"


class TestCompute:
    def test_derives_new_keys(self):
        fn = S.compute(
            summary=lambda s: s["text"][:5],
            length=lambda s: len(s["text"]),
        )
        result = fn({"text": "hello world"})
        assert isinstance(result, StateDelta)
        assert result.updates == {"summary": "hello", "length": 11}

    def test_name(self):
        fn = S.compute(a=lambda s: 1)
        assert fn.__name__ == "compute_a"


# ======================================================================
# Integration tests — S factories compose with >> in pipelines
# ======================================================================

class TestCompositionWithPipeline:
    def test_pick_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a >> S.pick("x") >> b
        assert isinstance(p, Pipeline)
        built = p.build()
        assert len(built.sub_agents) == 3

    def test_rename_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a >> S.rename(result="input") >> b
        assert isinstance(p, Pipeline)

    def test_chain_multiple_transforms(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = (
            a
            >> S.pick("findings", "sources")
            >> S.rename(findings="research")
            >> S.default(confidence=0.5)
            >> b
        )
        built = p.build()
        assert len(built.sub_agents) == 5  # a, pick, rename, default, b

    def test_transform_names_are_valid_identifiers(self):
        """All S factories produce valid agent names."""
        fns = [
            S.pick("a", "b"),
            S.drop("x"),
            S.rename(a="b"),
            S.default(x=1),
            S.merge("a", "b", into="c"),
            S.transform("x", abs),
            S.guard(lambda s: True),
            S.log("x"),
            S.compute(y=lambda s: 1),
        ]
        a = Agent("a").model("gemini-2.5-flash")
        for fn in fns:
            p = a >> fn
            built = p.build()
            name = built.sub_agents[1].name
            assert name.isidentifier(), f"Invalid name: {name}"

    def test_full_expression_with_transforms(self):
        """S transforms compose with all algebra operators."""
        from adk_fluent._base import until

        pipeline = (
            (   Agent("web").model("gemini-2.5-flash").instruct("Search.")
              | Agent("scholar").model("gemini-2.5-flash").instruct("Search.")
            )
            >> S.merge("web", "scholar", into="research")
            >> S.default(confidence=0.0)
            >> Agent("writer").model("gemini-2.5-flash").instruct("Write.")
            >> (
                Agent("critic").model("gemini-2.5-flash").instruct("Score.")
                >> Agent("reviser").model("gemini-2.5-flash").instruct("Revise.")
            ) * until(lambda s: s.get("confidence", 0) > 0.8, max=3)
        )
        assert isinstance(pipeline, Pipeline)
        built = pipeline.build()
        assert len(built.sub_agents) == 5  # fanout, merge, default, writer, loop
