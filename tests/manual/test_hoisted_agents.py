"""Tests that inner agent classes are module-level and reuse type objects."""


def test_fn_agent_same_type_across_builds():
    """Two FnStep builds should produce agents of the same type."""
    from adk_fluent._base import _fn_step
    fn = lambda state: {"x": 1}
    a1 = _fn_step(fn).build()
    a2 = _fn_step(fn).build()
    assert type(a1) is type(a2)


def test_tap_agent_same_type_across_builds():
    """Two tap builds should produce agents of the same type."""
    from adk_fluent import tap
    fn = lambda state: None
    a1 = tap(fn).build()
    a2 = tap(fn).build()
    assert type(a1) is type(a2)


def test_fn_agent_is_importable():
    """Module-level agent classes should be importable."""
    from adk_fluent._base import FnAgent
    assert FnAgent is not None


def test_tap_agent_is_importable():
    from adk_fluent._base import TapAgent
    assert TapAgent is not None


def test_gate_agent_is_importable():
    from adk_fluent._base import GateAgent
    assert GateAgent is not None


def test_race_agent_is_importable():
    from adk_fluent._base import RaceAgent
    assert RaceAgent is not None


def test_fallback_agent_is_importable():
    from adk_fluent._base import FallbackAgent
    assert FallbackAgent is not None


def test_timeout_agent_is_importable():
    from adk_fluent._base import TimeoutAgent
    assert TimeoutAgent is not None


def test_map_over_agent_is_importable():
    from adk_fluent._base import MapOverAgent
    assert MapOverAgent is not None


def test_fallback_agent_same_type_across_builds():
    """Two fallback builds should produce agents of the same type."""
    from adk_fluent import Agent
    from adk_fluent._base import _FallbackBuilder

    child = Agent("c")
    a1 = _FallbackBuilder("fb1", [child]).build()
    a2 = _FallbackBuilder("fb2", [child]).build()
    assert type(a1) is type(a2)


def test_gate_agent_same_type_across_builds():
    """Two gate builds should produce agents of the same type."""
    from adk_fluent import gate

    a1 = gate(lambda s: True).build()
    a2 = gate(lambda s: True).build()
    assert type(a1) is type(a2)


def test_race_agent_same_type_across_builds():
    """Two race builds should produce agents of the same type."""
    from adk_fluent import Agent, race

    child = Agent("c")
    a1 = race(child).build()
    a2 = race(child).build()
    assert type(a1) is type(a2)


def test_timeout_agent_same_type_across_builds():
    """Two timeout builds should produce agents of the same type."""
    from adk_fluent import Agent
    from adk_fluent._base import _TimeoutBuilder

    child = Agent("c")
    a1 = _TimeoutBuilder("to1", child, 5.0).build()
    a2 = _TimeoutBuilder("to2", child, 5.0).build()
    assert type(a1) is type(a2)


def test_map_over_agent_same_type_across_builds():
    """Two map_over builds should produce agents of the same type."""
    from adk_fluent import Agent, map_over

    child = Agent("c")
    a1 = map_over("items", child).build()
    a2 = map_over("items", child).build()
    assert type(a1) is type(a2)
