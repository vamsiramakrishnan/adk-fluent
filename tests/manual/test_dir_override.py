"""Issue #8 — __dir__ override for REPL autocomplete tests."""

from __future__ import annotations

from adk_fluent import Agent, FanOut, Loop, Pipeline


class TestDirAgent:
    """dir(Agent(...)) should include fluent method names."""

    def test_instruct_in_dir(self):
        assert "instruct" in dir(Agent("x"))

    def test_model_in_dir(self):
        assert "model" in dir(Agent("x"))

    def test_describe_in_dir(self):
        assert "describe" in dir(Agent("x"))

    def test_writes_in_dir(self):
        assert "writes" in dir(Agent("x"))

    def test_after_model_in_dir(self):
        assert "after_model" in dir(Agent("x"))

    def test_no_spurious_underscore_methods(self):
        d = dir(Agent("x"))
        # dir() should not include non-existent _-prefixed user methods
        # (class-level metadata like _ALIASES is expected from super().__dir__())
        assert "_nonexistent_method" not in d

    def test_dir_returns_sorted_list(self):
        d = dir(Agent("x"))
        assert d == sorted(d)


class TestDirComposite:
    """dir() should work for composite builders."""

    def test_pipeline_dir(self):
        d = dir(Pipeline("p"))
        assert isinstance(d, list)

    def test_fanout_dir(self):
        d = dir(FanOut("f"))
        assert isinstance(d, list)

    def test_loop_dir(self):
        d = dir(Loop("l"))
        assert isinstance(d, list)
