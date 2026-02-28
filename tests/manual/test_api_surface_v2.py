"""Tests for API Surface v2: deprecations, new methods, and prelude exports."""

import warnings

from adk_fluent import Agent

# ======================================================================
# 1. Deprecation warning tests
# ======================================================================


class TestDeprecationWarnings:
    """Deprecated methods emit DeprecationWarning with the correct replacement."""

    def test_outputs_emits_deprecation(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("test").outputs("result")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert ".outputs()" in str(w[0].message)
        assert ".save_as()" in str(w[0].message)

    def test_history_emits_deprecation(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("test").history("none")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert ".history()" in str(w[0].message)
        assert ".context()" in str(w[0].message)

    def test_include_history_emits_deprecation(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("test").include_history("default")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert ".include_history()" in str(w[0].message)
        assert ".context()" in str(w[0].message)

    def test_static_instruct_emits_deprecation(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("test").static_instruct("You are a bot.")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert ".static_instruct()" in str(w[0].message)
        assert ".static()" in str(w[0].message)


# ======================================================================
# 2. New method tests: save_as, stay, no_peers, isolate
# ======================================================================


class TestSaveAs:
    """save_as() sets output_key without emitting any warning."""

    def test_save_as_sets_output_key(self):
        agent = Agent("test").save_as("key")
        assert agent._config["output_key"] == "key"

    def test_save_as_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Agent("test").save_as("key")
        deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecations) == 0

    def test_save_as_returns_self(self):
        agent = Agent("test")
        result = agent.save_as("key")
        assert result is agent

    def test_save_as_none_clears(self):
        agent = Agent("test").save_as("key").save_as(None)
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
            "C",
            "P",
            "S",
            "Route",
            # Tier 3: Expression primitives
            "until",
            "tap",
            "map_over",
            "gate",
            "race",
            "expect",
            "dispatch",
            "join",
            "STransform",
            # Tier 4: Patterns
            "review_loop",
            "cascade",
            "chain",
            "fan_out_merge",
            "map_reduce",
            "conditional",
            "supervised",
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
        }
        assert set(prelude.__all__) == expected

    def test_prelude_all_count(self):
        import adk_fluent.prelude as prelude

        assert len(prelude.__all__) == 31

    def test_prelude_names_are_importable(self):
        """Every name in __all__ is actually accessible on the module."""
        import adk_fluent.prelude as prelude

        for name in prelude.__all__:
            assert hasattr(prelude, name), f"{name} listed in __all__ but not importable"


# ======================================================================
# 4. Backward compatibility: deprecated methods still set correct config
# ======================================================================


class TestBackwardCompatibility:
    """Deprecated methods must still set the right config values."""

    def test_outputs_sets_output_key(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            agent = Agent("test").outputs("result")
        assert agent._config["output_key"] == "result"

    def test_history_sets_include_contents(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            agent = Agent("test").history("none")
        assert agent._config["include_contents"] == "none"

    def test_include_history_sets_include_contents(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            agent = Agent("test").include_history("default")
        assert agent._config["include_contents"] == "default"

    def test_static_instruct_sets_static_instruction(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            agent = Agent("test").static_instruct("System prompt.")
        assert agent._config["static_instruction"] == "System prompt."

    def test_deprecated_methods_are_chainable(self):
        """Deprecated methods still return self for chaining."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            agent = Agent("test")
            result = agent.outputs("key")
            assert result is agent

            result = agent.history("none")
            assert result is agent

            result = agent.include_history("default")
            assert result is agent

            result = agent.static_instruct("static text")
            assert result is agent
