"""Tests for API Surface v2: removed zombies, new methods, and prelude exports."""

import warnings

import pytest

from adk_fluent import Agent

# ======================================================================
# 1. Removed zombies (0.18.0) — verify they stay gone
# ======================================================================


class TestRemovedZombies:
    """Deprecation shims removed in 0.18.0 must NOT come back."""

    @pytest.mark.parametrize(
        "method,successor",
        [
            ("outputs", "writes"),
            ("save_as", "writes"),
            ("history", "context"),
            ("include_history", "context"),
            ("guardrail", "guard"),
            ("delegate", "agent_tool"),
            ("retry_if", "loop_while"),
            ("inject_context", "prepend"),
        ],
    )
    def test_zombie_method_not_present(self, method: str, successor: str) -> None:
        agent = Agent("test")
        assert not hasattr(agent, method), (
            f"Agent.{method}() was removed in 0.18.0 — use .{successor}() instead"
        )


# ======================================================================
# 2. New method tests: writes, stay, no_peers, isolate
# ======================================================================


class TestSaveAs:
    """writes() sets output_key without emitting any warning."""

    def test_save_as_sets_output_key(self):
        agent = Agent("test").writes("key")
        assert agent._config["output_key"] == "key"

    def test_save_as_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("test").writes("key")
        deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecations) == 0

    def test_save_as_returns_self(self):
        agent = Agent("test")
        result = agent.writes("key")
        assert result is agent

    def test_save_as_none_clears(self):
        agent = Agent("test").writes("key").writes(None)
        assert agent._config["output_key"] is None


class TestStay:
    """stay() sets disallow_transfer_to_parent only."""

    def test_stay_sets_parent_flag(self):
        agent = Agent("test").stay()
        assert agent._config["disallow_transfer_to_parent"] is True

    def test_stay_does_not_set_peers_flag(self):
        agent = Agent("test").stay()
        assert agent._config.get("disallow_transfer_to_peers") is not True

    def test_stay_returns_self(self):
        agent = Agent("test")
        result = agent.stay()
        assert result is agent


class TestNoPeers:
    """no_peers() sets disallow_transfer_to_peers only."""

    def test_no_peers_sets_peers_flag(self):
        agent = Agent("test").no_peers()
        assert agent._config["disallow_transfer_to_peers"] is True

    def test_no_peers_does_not_set_parent_flag(self):
        agent = Agent("test").no_peers()
        assert agent._config.get("disallow_transfer_to_parent") is not True

    def test_no_peers_returns_self(self):
        agent = Agent("test")
        result = agent.no_peers()
        assert result is agent


class TestIsolate:
    """isolate() sets both disallow flags."""

    def test_isolate_sets_both_flags(self):
        agent = Agent("test").isolate()
        assert agent._config["disallow_transfer_to_parent"] is True
        assert agent._config["disallow_transfer_to_peers"] is True

    def test_isolate_returns_self(self):
        agent = Agent("test")
        result = agent.isolate()
        assert result is agent


# ======================================================================
# 3. Prelude import test
# ======================================================================


class TestPrelude:
    """from adk_fluent.prelude import * gives exactly the expected names."""

    def test_prelude_all_contents(self):
        import adk_fluent.prelude as prelude

        expected = {
            # Tier 1: Core builders
            "Agent",
            "Pipeline",
            "FanOut",
            "Loop",
            # Tier 2: Composition namespaces
            "A",
            "ATransform",
            "C",
            "E",
            "EComposite",
            "ECase",
            "ECriterion",
            "EvalSuite",
            "EvalReport",
            "ComparisonReport",
            "ComparisonSuite",
            "EPersona",
            "P",
            "S",
            "M",
            "T",
            "TComposite",
            "G",
            "GComposite",
            "GuardViolation",
            "Route",
            # Tier 2b: Expression builders
            "Fallback",
            # Tier 3: Expression primitives
            "until",
            "tap",
            "map_over",
            "gate",
            "race",
            "expect",
            "dispatch",
            "join",
            "notify",
            "watch",
            "STransform",
            # Tier 4: Patterns
            "review_loop",
            "cascade",
            "chain",
            "fan_out_merge",
            "map_reduce",
            "conditional",
            "supervised",
            "group_chat",
            # Tier 5: Stream execution
            "Source",
            "Inbox",
            "StreamRunner",
            # Tier 6: Observability
            "DispatchLogMiddleware",
            "get_execution_mode",
            # Tier 7: Enums
            "SessionStrategy",
            "ExecutionMode",
            # Tier 8: Schemas
            "MiddlewareSchema",
            "ArtifactSchema",
            "Produces",
            "Consumes",
            # Tier 9: Tool registry
            "ToolRegistry",
            "SearchToolset",
            "search_aware_after_tool",
            # Tier 0: A2A protocol
            "RemoteAgent",
            "A2AServer",
            "AgentRegistry",
            # A2A patterns
            "a2a_cascade",
            "a2a_fanout",
            "a2a_delegate",
            # Tier 10: UI (A2UI)
            "UI",
            "UIBinding",
            "UICheck",
            "UIComponent",
            "UISurface",
        }
        assert set(prelude.__all__) == expected

    def test_prelude_all_count(self):
        import adk_fluent.prelude as prelude

        assert len(prelude.__all__) == 70

    def test_prelude_names_are_importable(self):
        """Every name in __all__ is actually accessible on the module."""
        import adk_fluent.prelude as prelude

        for name in prelude.__all__:
            assert hasattr(prelude, name), f"{name} listed in __all__ but not importable"


