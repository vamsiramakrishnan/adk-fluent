"""Issue #7 — Copy-on-Write frozen builders tests."""

from __future__ import annotations

from adk_fluent import Agent


class TestUnfrozenMutateInPlace:
    """Unfrozen builders should still mutate in place (backwards compatible)."""

    def test_simple_chain_mutates(self):
        a = Agent("x")
        b = a.model("gemini-2.0-flash")
        assert a is b  # same object — unfrozen chain

    def test_chained_calls_return_same(self):
        a = Agent("x").model("gemini-2.0-flash").instruct("hi")
        # All calls on unfrozen builder return the same instance
        assert a._config.get("name") == "x"
        assert a._config.get("instruction") == "hi"


class TestFrozenAfterOperator:
    """After composition operators, original builder should be frozen."""

    def test_rshift_freezes(self):
        a = Agent("x").model("gemini-2.0-flash")
        _ = a >> Agent("y")
        assert a._frozen is True

    def test_frozen_mutation_forks(self):
        a = Agent("x").model("gemini-2.0-flash")
        _ = a >> Agent("y")
        c = a.instruct("test")
        assert a is not c  # c is a clone
        assert c._config.get("instruction") == "test"
        assert "instruction" not in a._config  # original unchanged

    def test_clone_has_independent_config(self):
        base = Agent("x").model("gemini-2.0-flash")
        _ = base >> Agent("y")
        c1 = base.instruct("A")
        c2 = base.instruct("B")
        assert c1 is not c2
        assert c1._config.get("instruction") == "A"
        assert c2._config.get("instruction") == "B"

    def test_or_freezes(self):
        a = Agent("x").model("gemini-2.0-flash")
        _ = a | Agent("y")
        assert a._frozen is True
        c = a.instruct("test")
        assert a is not c

    def test_mul_freezes(self):
        a = Agent("x").model("gemini-2.0-flash")
        _ = a * 3
        assert a._frozen is True
        c = a.instruct("test")
        assert a is not c

    def test_matmul_freezes(self):
        from pydantic import BaseModel

        class Out(BaseModel):
            result: str

        a = Agent("x").model("gemini-2.0-flash")
        _ = a @ Out
        assert a._frozen is True

    def test_floordiv_freezes(self):
        a = Agent("x").model("gemini-2.0-flash")
        b = Agent("y").model("gemini-2.0-flash")
        _ = a // b
        assert a._frozen is True

    def test_to_app_freezes(self):
        a = Agent("x").model("gemini-2.0-flash").instruct("do stuff")
        _ = a.to_app()
        assert a._frozen is True


class TestGeneratedMethodsFork:
    """Generated methods should also fork when builder is frozen."""

    def test_generated_alias_forks(self):
        a = Agent("x").model("gemini-2.0-flash")
        _ = a >> Agent("y")
        b = a.describe("description text")
        assert a is not b
        assert b._config.get("description") == "description text"
        assert "description" not in a._config

    def test_generated_callback_forks(self):
        a = Agent("x").model("gemini-2.0-flash")
        _ = a >> Agent("y")
        fn = lambda ctx: None
        b = a.before_model(fn)
        assert a is not b
