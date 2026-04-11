"""Tests for visibility inference and VisibilityPlugin."""

from adk_fluent._ir import CaptureNode, RouteNode, TapNode, TransformNode
from adk_fluent._ir_generated import (
    AgentNode,
    LoopNode,
    ParallelNode,
    SequenceNode,
)
from adk_fluent._visibility import VisibilityPlugin, infer_visibility

# ======================================================================
# Visibility inference: single agent
# ======================================================================


class TestSingleAgent:
    def test_single_agent_is_user(self):
        node = AgentNode(name="writer")
        result = infer_visibility(node)
        assert result["writer"] == "user"

    def test_single_agent_no_successor(self):
        node = AgentNode(name="reviewer")
        result = infer_visibility(node, has_successor=False)
        assert result["reviewer"] == "user"


# ======================================================================
# Visibility inference: sequences
# ======================================================================


class TestSequence:
    def test_sequence_two_agents(self):
        """Sequence [a -> b] => a=internal, b=user."""
        node = SequenceNode(
            name="pipeline",
            children=(
                AgentNode(name="a"),
                AgentNode(name="b"),
            ),
        )
        result = infer_visibility(node)
        assert result["a"] == "internal"
        assert result["b"] == "user"

    def test_sequence_three_agents(self):
        """Sequence [a -> b -> c] => a=internal, b=internal, c=user."""
        node = SequenceNode(
            name="pipeline",
            children=(
                AgentNode(name="a", output_key="out_a"),
                AgentNode(name="b", output_key="out_b"),
                AgentNode(name="c"),
            ),
        )
        result = infer_visibility(node)
        assert result["a"] == "internal"
        assert result["b"] == "internal"
        assert result["c"] == "user"

    def test_nested_sequence_propagates_successor(self):
        """Inner sequence in outer sequence propagates has_successor correctly."""
        inner = SequenceNode(
            name="inner",
            children=(
                AgentNode(name="a"),
                AgentNode(name="b"),
            ),
        )
        outer = SequenceNode(
            name="outer",
            children=(inner, AgentNode(name="c")),
        )
        result = infer_visibility(outer)
        # a and b are in inner which has successor c, so both are internal
        assert result["a"] == "internal"
        assert result["b"] == "internal"
        assert result["c"] == "user"


# ======================================================================
# Visibility inference: zero-cost types
# ======================================================================


class TestZeroCostTypes:
    def test_transform_node_zero_cost(self):
        node = TransformNode(name="trim", fn=lambda s: s)
        result = infer_visibility(node)
        assert result["trim"] == "zero_cost"

    def test_tap_node_zero_cost(self):
        node = TapNode(name="log_it", fn=lambda s: None)
        result = infer_visibility(node)
        assert result["log_it"] == "zero_cost"

    def test_route_node_zero_cost(self):
        node = RouteNode(name="router", key="quality")
        result = infer_visibility(node)
        assert result["router"] == "zero_cost"

    def test_capture_node_zero_cost(self):
        node = CaptureNode(name="capture_input", key="user_input")
        result = infer_visibility(node)
        assert result["capture_input"] == "zero_cost"

    def test_zero_cost_in_sequence(self):
        """Zero-cost nodes in a sequence are still zero_cost."""
        node = SequenceNode(
            name="pipeline",
            children=(
                TransformNode(name="trim", fn=lambda s: s),
                AgentNode(name="writer"),
            ),
        )
        result = infer_visibility(node)
        assert result["trim"] == "zero_cost"
        assert result["writer"] == "user"


# ======================================================================
# Visibility inference: RouteNode with branches
# ======================================================================


class TestRouteNodeBranches:
    def test_route_is_zero_cost_branches_are_user(self):
        """RouteNode itself is zero_cost, branches are user (no successor)."""
        node = RouteNode(
            name="router",
            key="quality",
            rules=(
                ("good", AgentNode(name="publisher")),
                ("bad", AgentNode(name="rewriter")),
            ),
            default=AgentNode(name="fallback_agent"),
        )
        result = infer_visibility(node)
        assert result["router"] == "zero_cost"
        assert result["publisher"] == "user"
        assert result["rewriter"] == "user"
        assert result["fallback_agent"] == "user"


# ======================================================================
# Visibility inference: LoopNode
# ======================================================================


class TestLoopNode:
    def test_loop_children_all_internal(self):
        """Loop body children always have has_successor=True, so all internal."""
        node = LoopNode(
            name="refine_loop",
            children=(
                AgentNode(name="writer"),
                AgentNode(name="reviewer"),
            ),
            max_iterations=3,
        )
        result = infer_visibility(node)
        assert result["writer"] == "internal"
        assert result["reviewer"] == "internal"


# ======================================================================
# Visibility inference: ParallelNode
# ======================================================================


class TestParallelNode:
    def test_parallel_no_successor_children_are_user(self):
        """ParallelNode children inherit parent's has_successor (False)."""
        node = ParallelNode(
            name="fanout",
            children=(
                AgentNode(name="fast"),
                AgentNode(name="slow"),
            ),
        )
        result = infer_visibility(node)
        assert result["fast"] == "user"
        assert result["slow"] == "user"

    def test_parallel_with_successor_children_are_internal(self):
        """ParallelNode in a sequence: children inherit has_successor=True."""
        parallel = ParallelNode(
            name="fanout",
            children=(
                AgentNode(name="fast"),
                AgentNode(name="slow"),
            ),
        )
        outer = SequenceNode(
            name="pipeline",
            children=(parallel, AgentNode(name="merger")),
        )
        result = infer_visibility(outer)
        assert result["fast"] == "internal"
        assert result["slow"] == "internal"
        assert result["merger"] == "user"


# ======================================================================
# Policy parameter
# ======================================================================


class TestPolicyParameter:
    def test_transparent_all_user(self):
        """policy='transparent' => all agents are 'user' (except zero_cost)."""
        node = SequenceNode(
            name="pipeline",
            children=(
                AgentNode(name="a"),
                AgentNode(name="b"),
                TransformNode(name="trim", fn=lambda s: s),
            ),
        )
        result = infer_visibility(node, policy="transparent")
        assert result["a"] == "user"
        assert result["b"] == "user"
        assert result["trim"] == "zero_cost"

    def test_filtered_is_default(self):
        """policy='filtered' => topology-inferred (default behavior)."""
        node = SequenceNode(
            name="pipeline",
            children=(
                AgentNode(name="a"),
                AgentNode(name="b"),
            ),
        )
        result = infer_visibility(node, policy="filtered")
        assert result["a"] == "internal"
        assert result["b"] == "user"

    def test_annotate_same_as_filtered(self):
        """policy='annotate' produces same map as filtered (mode differs on plugin)."""
        node = SequenceNode(
            name="pipeline",
            children=(
                AgentNode(name="a"),
                AgentNode(name="b"),
            ),
        )
        result = infer_visibility(node, policy="annotate")
        assert result["a"] == "internal"
        assert result["b"] == "user"


# ======================================================================
# VisibilityPlugin
# ======================================================================


class TestVisibilityPlugin:
    def test_plugin_creation(self):
        vis_map = {"writer": "internal", "reviewer": "user"}
        plugin = VisibilityPlugin(vis_map, mode="annotate")
        assert plugin.name == "adk_fluent_visibility"
        assert plugin._visibility == vis_map
        assert plugin._mode == "annotate"

    def test_plugin_default_mode(self):
        plugin = VisibilityPlugin({})
        assert plugin._mode == "annotate"

    def test_plugin_has_on_event_callback(self):
        plugin = VisibilityPlugin({})
        assert hasattr(plugin, "on_event_callback")
        assert callable(plugin.on_event_callback)

    def test_plugin_has_is_error_event(self):
        assert hasattr(VisibilityPlugin, "_is_error_event")
        assert callable(VisibilityPlugin._is_error_event)

    def test_plugin_has_strip_content(self):
        assert hasattr(VisibilityPlugin, "_strip_content")
        assert callable(VisibilityPlugin._strip_content)

    def test_is_error_event_false_for_normal(self):
        """Normal events are not error events."""

        class FakeEvent:
            pass

        assert not VisibilityPlugin._is_error_event(FakeEvent())

    def test_is_error_event_true_for_error_code(self):
        class FakeEvent:
            error_code = "INTERNAL_ERROR"

        assert VisibilityPlugin._is_error_event(FakeEvent())

    def test_is_error_event_true_for_escalate(self):
        class FakeActions:
            escalate = True

        class FakeEvent:
            error_code = None
            actions = FakeActions()

        assert VisibilityPlugin._is_error_event(FakeEvent())

    def test_is_error_event_false_for_no_escalate(self):
        class FakeActions:
            escalate = False

        class FakeEvent:
            error_code = None
            actions = FakeActions()

        assert not VisibilityPlugin._is_error_event(FakeEvent())

    def test_strip_content_removes_content(self):
        class FakeParts:
            pass

        class FakeContent:
            parts = [FakeParts()]

        class FakeEvent:
            content = FakeContent()

        event = FakeEvent()
        VisibilityPlugin._strip_content(event)
        assert event.content is None

    def test_strip_content_noop_when_no_content(self):
        class FakeEvent:
            content = None

        event = FakeEvent()
        VisibilityPlugin._strip_content(event)
        assert event.content is None

    def test_plugin_is_base_plugin(self):
        """VisibilityPlugin inherits from ADK BasePlugin."""
        from google.adk.plugins.base_plugin import BasePlugin

        plugin = VisibilityPlugin({})
        assert isinstance(plugin, BasePlugin)


# ======================================================================
# Plugin on_event_callback behavior (async)
# ======================================================================


class TestPluginOnEventCallback:
    def test_annotates_user_event(self):
        import asyncio

        vis_map = {"writer": "user"}
        plugin = VisibilityPlugin(vis_map, mode="annotate")

        class FakeEvent:
            author = "writer"
            custom_metadata = None
            error_code = None
            actions = None
            content = None

        event = FakeEvent()
        result = asyncio.run(plugin.on_event_callback(invocation_context=None, event=event))
        assert result is event
        assert event.custom_metadata["adk_fluent.visibility"] == "user"
        assert event.custom_metadata["adk_fluent.is_user_facing"] is True

    def test_annotates_internal_event(self):
        import asyncio

        vis_map = {"writer": "internal"}
        plugin = VisibilityPlugin(vis_map, mode="annotate")

        class FakeEvent:
            author = "writer"
            custom_metadata = None
            error_code = None
            actions = None
            content = None

        event = FakeEvent()
        result = asyncio.run(plugin.on_event_callback(invocation_context=None, event=event))
        assert result is event
        assert event.custom_metadata["adk_fluent.visibility"] == "internal"
        assert event.custom_metadata["adk_fluent.is_user_facing"] is False

    def test_unknown_author_defaults_to_user(self):
        import asyncio

        plugin = VisibilityPlugin({}, mode="annotate")

        class FakeEvent:
            author = "unknown_agent"
            custom_metadata = None
            error_code = None
            actions = None
            content = None

        event = FakeEvent()
        asyncio.run(plugin.on_event_callback(invocation_context=None, event=event))
        assert event.custom_metadata["adk_fluent.visibility"] == "user"
        assert event.custom_metadata["adk_fluent.is_user_facing"] is True

    def test_error_event_always_user_facing(self):
        import asyncio

        vis_map = {"writer": "internal"}
        plugin = VisibilityPlugin(vis_map, mode="annotate")

        class FakeActions:
            escalate = True

        class FakeEvent:
            author = "writer"
            custom_metadata = None
            error_code = None
            actions = FakeActions()
            content = None

        event = FakeEvent()
        asyncio.run(plugin.on_event_callback(invocation_context=None, event=event))
        assert event.custom_metadata["adk_fluent.visibility"] == "user"
        assert event.custom_metadata["adk_fluent.is_user_facing"] is True

    def test_filter_mode_strips_internal_content(self):
        import asyncio

        vis_map = {"writer": "internal"}
        plugin = VisibilityPlugin(vis_map, mode="filter")

        class FakePart:
            text = "Hello"

        class FakeContent:
            parts = [FakePart()]

        class FakeEvent:
            author = "writer"
            custom_metadata = None
            error_code = None
            actions = None
            content = FakeContent()

        event = FakeEvent()
        asyncio.run(plugin.on_event_callback(invocation_context=None, event=event))
        assert event.content is None

    def test_filter_mode_keeps_user_content(self):
        import asyncio

        vis_map = {"writer": "user"}
        plugin = VisibilityPlugin(vis_map, mode="filter")

        class FakePart:
            text = "Hello"

        class FakeContent:
            parts = [FakePart()]

        class FakeEvent:
            author = "writer"
            custom_metadata = None
            error_code = None
            actions = None
            content = FakeContent()

        event = FakeEvent()
        asyncio.run(plugin.on_event_callback(invocation_context=None, event=event))
        assert event.content is not None


# ======================================================================
# Show/hide overrides
# ======================================================================


class TestShowHideOverrides:
    def test_show_sets_visibility_override(self):
        from adk_fluent.agent import Agent

        a = Agent("writer")
        a.show()
        assert a._config.get("_visibility_override") == "user"

    def test_hide_sets_visibility_override(self):
        from adk_fluent.agent import Agent

        a = Agent("writer")
        a.hide()
        assert a._config.get("_visibility_override") == "internal"

    def test_show_returns_self(self):
        from adk_fluent.agent import Agent

        a = Agent("writer")
        result = a.show()
        assert result is a

    def test_hide_returns_self(self):
        from adk_fluent.agent import Agent

        a = Agent("writer")
        result = a.hide()
        assert result is a


# ======================================================================
# Pipeline-level policy methods
# ======================================================================


class TestPipelinePolicies:
    def test_transparent_method_exists(self):
        from adk_fluent.workflow import Pipeline

        p = Pipeline("test")
        assert hasattr(p, "transparent")
        assert callable(p.transparent)

    def test_filtered_method_exists(self):
        from adk_fluent.workflow import Pipeline

        p = Pipeline("test")
        assert hasattr(p, "filtered")
        assert callable(p.filtered)

    def test_annotated_method_exists(self):
        from adk_fluent.workflow import Pipeline

        p = Pipeline("test")
        assert hasattr(p, "annotated")
        assert callable(p.annotated)

    def test_transparent_sets_policy(self):
        from adk_fluent.workflow import Pipeline

        p = Pipeline("test")
        result = p.transparent()
        assert result is p
        assert p._config["_visibility_policy"] == "transparent"

    def test_filtered_sets_policy(self):
        from adk_fluent.workflow import Pipeline

        p = Pipeline("test")
        result = p.filtered()
        assert result is p
        assert p._config["_visibility_policy"] == "filtered"

    def test_annotated_sets_policy(self):
        from adk_fluent.workflow import Pipeline

        p = Pipeline("test")
        result = p.annotated()
        assert result is p
        assert p._config["_visibility_policy"] == "annotate"

    def test_policies_available_on_fanout(self):
        from adk_fluent.workflow import FanOut

        f = FanOut("test")
        f.transparent()
        assert f._config["_visibility_policy"] == "transparent"

    def test_policies_available_on_loop(self):
        from adk_fluent.workflow import Loop

        loop = Loop("test")
        loop.annotated()
        assert loop._config["_visibility_policy"] == "annotate"


# ======================================================================
# Module exports
# ======================================================================


class TestModuleExports:
    def test_infer_visibility_exported(self):
        from adk_fluent._visibility import __all__

        assert "infer_visibility" in __all__

    def test_visibility_plugin_exported(self):
        from adk_fluent._visibility import __all__

        assert "VisibilityPlugin" in __all__
