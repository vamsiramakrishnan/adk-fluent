"""Tests for the ``adk_fluent._usage`` package.

Covers the per-turn record, cost table, tracker (with per-agent
breakdown), plugin wrapper, and the ``H.usage_plugin``/``H.cost_table``
factories. These tests are intentionally offline — they do not invoke a
real LLM; they shape fake objects that match the duck-typed
``llm_response.usage_metadata`` protocol the tracker expects.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from adk_fluent import (
    AgentUsage,
    CostTable,
    H,
    ModelRate,
    TurnUsage,
    UsagePlugin,
    UsageTracker,
)


def _fake_response(
    input_tokens: int, output_tokens: int, model: str = ""
) -> SimpleNamespace:
    return SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=input_tokens,
            candidates_token_count=output_tokens,
        ),
        model=model,
    )


class TestTurnUsage:
    def test_defaults(self):
        turn = TurnUsage()
        assert turn.input_tokens == 0
        assert turn.output_tokens == 0
        assert turn.total_tokens == 0
        assert turn.agent_name == ""

    def test_total_tokens(self):
        turn = TurnUsage(input_tokens=10, output_tokens=5)
        assert turn.total_tokens == 15

    def test_frozen(self):
        turn = TurnUsage(input_tokens=1)
        with pytest.raises(AttributeError):
            turn.input_tokens = 2  # type: ignore[misc]


class TestModelRate:
    def test_cost_for_zero(self):
        assert ModelRate().cost_for(1_000_000, 1_000_000) == 0.0

    def test_cost_for_basic(self):
        rate = ModelRate(input_per_million=1.0, output_per_million=2.0)
        # 1M input @ $1 + 1M output @ $2 = $3
        assert rate.cost_for(1_000_000, 1_000_000) == pytest.approx(3.0)

    def test_cost_for_fractional(self):
        rate = ModelRate(input_per_million=10.0, output_per_million=20.0)
        # 100k in @ $10/M = $1, 50k out @ $20/M = $1
        assert rate.cost_for(100_000, 50_000) == pytest.approx(2.0)


class TestCostTable:
    def test_empty_rate_for_returns_zero(self):
        table = CostTable()
        assert table.rate_for("any").cost_for(1_000_000, 1_000_000) == 0.0

    def test_flat_wildcard(self):
        table = CostTable.flat(1.0, 2.0)
        rate = table.rate_for("gemini-2.5-flash")
        assert rate.input_per_million == 1.0
        assert rate.output_per_million == 2.0

    def test_specific_model_wins_over_wildcard(self):
        table = CostTable(
            rates={
                "*": ModelRate(input_per_million=1.0, output_per_million=1.0),
                "gemini-2.5-pro": ModelRate(
                    input_per_million=3.5, output_per_million=10.5
                ),
            }
        )
        assert table.rate_for("gemini-2.5-pro").input_per_million == 3.5
        assert table.rate_for("unknown").input_per_million == 1.0

    def test_rates_is_immutable(self):
        table = CostTable.flat(1.0, 2.0)
        with pytest.raises(TypeError):
            table.rates["x"] = ModelRate()  # type: ignore[index]

    def test_with_rate_is_pure(self):
        base = CostTable()
        extended = base.with_rate(
            "gemini-2.5-flash", input_per_million=0.075, output_per_million=0.30
        )
        assert "gemini-2.5-flash" not in base.rates
        assert "gemini-2.5-flash" in extended.rates
        assert extended.rates["gemini-2.5-flash"].output_per_million == 0.30

    def test_cost_for_turn(self):
        table = CostTable.flat(1.0, 2.0)
        turn = TurnUsage(input_tokens=1_000_000, output_tokens=500_000)
        assert table.cost_for(turn) == pytest.approx(2.0)


class TestUsageTracker:
    def test_record_accumulates(self):
        tracker = UsageTracker()
        tracker.record(10, 5)
        tracker.record(20, 15)
        assert tracker.total_input_tokens == 30
        assert tracker.total_output_tokens == 20
        assert tracker.total_tokens == 50
        assert tracker.turn_count == 2

    def test_turns_is_defensive_copy(self):
        tracker = UsageTracker()
        tracker.record(1, 1)
        snapshot = tracker.turns
        snapshot.clear()
        assert tracker.turn_count == 1

    def test_callback_captures_usage(self):
        tracker = UsageTracker()
        cb = tracker.callback()
        ctx = SimpleNamespace(agent_name="researcher")
        cb(ctx, _fake_response(100, 50, "gemini-2.5-flash"))
        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 50
        assert tracker.turns[0].agent_name == "researcher"
        assert tracker.turns[0].model == "gemini-2.5-flash"

    def test_legacy_cost_args_build_flat_table(self):
        tracker = UsageTracker(
            cost_per_million_input=1.0, cost_per_million_output=2.0
        )
        assert tracker.cost_table is not None
        rate = tracker.cost_table.rate_for("*")
        assert rate.input_per_million == 1.0
        assert rate.output_per_million == 2.0

    def test_total_cost_usd_uses_table(self):
        table = CostTable.flat(10.0, 20.0)
        tracker = UsageTracker(cost_table=table)
        tracker.record(100_000, 50_000)  # $1 + $1 = $2
        assert tracker.total_cost_usd == pytest.approx(2.0)

    def test_total_cost_usd_without_table_is_zero(self):
        tracker = UsageTracker()
        tracker.record(1_000_000, 1_000_000)
        assert tracker.total_cost_usd == 0.0

    def test_by_agent_breakdown(self):
        tracker = UsageTracker()
        tracker.record(10, 5, agent_name="coordinator")
        tracker.record(20, 10, agent_name="researcher")
        tracker.record(30, 15, agent_name="researcher")
        by_agent = tracker.by_agent()
        assert set(by_agent) == {"coordinator", "researcher"}
        assert by_agent["coordinator"].input_tokens == 10
        assert by_agent["coordinator"].calls == 1
        assert by_agent["researcher"].input_tokens == 50
        assert by_agent["researcher"].output_tokens == 25
        assert by_agent["researcher"].calls == 2
        assert by_agent["researcher"].total_tokens == 75
        assert isinstance(by_agent["researcher"], AgentUsage)

    def test_reset_clears_turns(self):
        tracker = UsageTracker()
        tracker.record(1, 1)
        tracker.reset()
        assert tracker.turn_count == 0
        assert tracker.total_tokens == 0

    def test_summary_contains_totals(self):
        tracker = UsageTracker(cost_table=CostTable.flat(1.0, 2.0))
        tracker.record(1_000, 2_000)
        text = tracker.summary()
        assert "Turns: 1" in text
        assert "Input tokens: 1,000" in text
        assert "Output tokens: 2,000" in text
        assert "Estimated cost:" in text


class TestUsagePlugin:
    @pytest.mark.asyncio
    async def test_plugin_records_via_after_model_callback(self):
        plugin = UsagePlugin()
        ctx = SimpleNamespace(agent_name="writer")
        await plugin.after_model_callback(
            callback_context=ctx,
            llm_response=_fake_response(42, 21, "gemini-2.5-pro"),
        )
        assert plugin.tracker.total_input_tokens == 42
        assert plugin.tracker.total_output_tokens == 21
        assert plugin.tracker.turns[0].agent_name == "writer"
        assert plugin.tracker.turns[0].model == "gemini-2.5-pro"

    def test_plugin_accepts_pre_built_tracker(self):
        tracker = UsageTracker(cost_table=CostTable.flat(1.0, 2.0))
        plugin = UsagePlugin(tracker)
        assert plugin.tracker is tracker

    def test_plugin_is_base_plugin(self):
        from google.adk.plugins.base_plugin import BasePlugin

        assert isinstance(UsagePlugin(), BasePlugin)


class TestHNamespaceFactories:
    def test_usage_plugin_factory(self):
        plugin = H.usage_plugin()
        assert isinstance(plugin, UsagePlugin)
        assert isinstance(plugin.tracker, UsageTracker)

    def test_usage_plugin_factory_custom_name(self):
        plugin = H.usage_plugin(name="my_usage")
        # BasePlugin stores name
        assert plugin.name == "my_usage"

    def test_cost_table_factory_from_kwargs(self):
        table = H.cost_table(
            **{
                "gemini_2_5_flash": (0.075, 0.30),
                "gemini_2_5_pro": (3.5, 10.5),
            }
        )
        assert isinstance(table, CostTable)
        assert table.rate_for("gemini_2_5_flash").output_per_million == 0.30
        assert table.rate_for("gemini_2_5_pro").input_per_million == 3.5

    def test_cost_table_factory_empty(self):
        table = H.cost_table()
        assert isinstance(table, CostTable)
        assert table.rate_for("anything").input_per_million == 0.0
