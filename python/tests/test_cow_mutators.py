"""Copy-on-write regression tests for hand-written mutators.

These methods previously mutated frozen builders in place, violating the
documented invariant "All operators are immutable — sub-expressions can be
safely reused." Each is now decorated with ``@fluent`` so a frozen builder
forks before mutation. This test pins that contract so it cannot regress.
"""

import pytest
from pydantic import BaseModel

from adk_fluent import Agent


class _Out(BaseModel):
    findings: str


def _frozen_agent():
    """Return an agent that has been frozen by composition."""
    a = Agent("a", "gemini-2.5-flash").instruct("Do a thing.")
    _ = a >> Agent("b", "gemini-2.5-flash")  # freezes `a`
    assert a._frozen is True
    return a


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a.debug(True),
        lambda a: a.prepend(lambda ctx: "x"),
        lambda a: a.proceed_if(lambda s: True),
        lambda a: a.mock(["hi"]),
        lambda a: a.produces(_Out),
        lambda a: a.consumes(_Out),
        lambda a: a.strict(),
        lambda a: a.unchecked(),
        lambda a: a.checked(),
        lambda a: a.transparent(),
        lambda a: a.filtered(),
        lambda a: a.annotated(),
    ],
)
def test_mutator_forks_frozen_builder(mutate):
    a = _frozen_agent()
    result = mutate(a)
    # A frozen builder must fork: the result is a distinct, unfrozen object.
    assert result is not a, "mutator mutated a frozen builder in place"
    assert result._frozen is False
    # The original frozen builder must be untouched.
    assert a._frozen is True


def test_mock_dict_preserves_subagents_after_fork():
    """mock(dict) on a composed pipeline must not lose mocks to forked clones."""
    pipe = Agent("researcher", "gemini-2.5-flash") >> Agent("writer", "gemini-2.5-flash")
    mocked = pipe.mock({"researcher": "R", "writer": "W"})
    # Every named sub-agent should carry a before_model mock callback.
    names_with_mock = {
        sub._config.get("name")
        for sub in mocked._lists.get("sub_agents", [])
        if sub._callbacks.get("before_model_callback")
    }
    assert names_with_mock == {"researcher", "writer"}


def test_reactor_rules_survive_fork():
    """Forking a frozen builder must preserve .on() reactor rules."""
    from adk_fluent import R

    a = Agent("a", "gemini-2.5-flash").on(R.signal("temp", 0).changed)
    assert getattr(a, "_reactor_rules", None)
    a._freeze()
    forked = a.debug(True)  # any mutator triggers the fork
    assert forked is not a
    assert len(getattr(forked, "_reactor_rules", [])) == len(a._reactor_rules)


def test_proceed_if_propagates_predicate_errors():
    """A predicate error must surface, not be silently swallowed as 'skip'."""

    class _Ctx:
        state = {}  # noqa: RUF012

    agent = Agent("a", "gemini-2.5-flash").proceed_if(lambda s: s["missing_key"] == "x")
    gate = agent._callbacks["before_agent_callback"][-1]
    with pytest.raises(KeyError):
        gate(_Ctx())
