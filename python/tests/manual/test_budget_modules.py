"""Dedicated tests for ``adk_fluent._budget`` — tracker + policy + plugin.

The legacy ``BudgetMonitor`` tests live in ``test_foundation_primitives.py``.
This module tests the Phase 5 additions:

- Frozen :class:`Threshold` validation
- Frozen :class:`BudgetPolicy` + ``build_monitor()`` + ``with_threshold()``
- :class:`BudgetPlugin` (BasePlugin) after_model_callback wiring
- ``H.budget_policy`` / ``H.budget_plugin`` factories
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from adk_fluent import BudgetMonitor, BudgetPlugin, BudgetPolicy, H, Threshold

# ======================================================================
# Threshold (frozen)
# ======================================================================


class TestThreshold:
    def test_happy_path(self):
        fired = []
        t = Threshold(percent=0.8, callback=lambda m: fired.append(m))
        assert t.percent == 0.8
        assert t.recurring is False
        assert callable(t.callback)

    def test_recurring_flag(self):
        t = Threshold(percent=0.5, callback=lambda m: None, recurring=True)
        assert t.recurring is True

    def test_is_frozen(self):
        t = Threshold(percent=0.5, callback=lambda m: None)
        with pytest.raises(FrozenInstanceError):
            t.percent = 0.9  # type: ignore[misc]

    def test_percent_out_of_range_rejected(self):
        for bad in (-0.1, 0.0, 1.1, 2.0):
            with pytest.raises(ValueError):
                Threshold(percent=bad, callback=lambda m: None)


# ======================================================================
# BudgetPolicy (frozen)
# ======================================================================


class TestBudgetPolicy:
    def test_default_policy(self):
        p = BudgetPolicy()
        assert p.max_tokens == 200_000
        assert p.thresholds == ()

    def test_policy_is_frozen(self):
        p = BudgetPolicy(max_tokens=10_000)
        with pytest.raises(FrozenInstanceError):
            p.max_tokens = 20_000  # type: ignore[misc]

    def test_rejects_non_positive_budget(self):
        with pytest.raises(ValueError):
            BudgetPolicy(max_tokens=0)
        with pytest.raises(ValueError):
            BudgetPolicy(max_tokens=-5)

    def test_build_monitor_is_fresh_each_call(self):
        policy = BudgetPolicy(
            max_tokens=1_000,
            thresholds=(Threshold(percent=0.5, callback=lambda m: None),),
        )
        m1 = policy.build_monitor()
        m2 = policy.build_monitor()
        assert m1 is not m2
        assert m1.max_tokens == m2.max_tokens == 1_000
        assert len(m1.thresholds) == 1
        assert len(m2.thresholds) == 1

    def test_with_threshold_is_pure(self):
        base = BudgetPolicy(max_tokens=1_000)
        extended = base.with_threshold(0.9, lambda m: None)
        assert base.thresholds == ()  # unchanged
        assert len(extended.thresholds) == 1
        assert extended.thresholds[0].percent == 0.9

    def test_with_threshold_preserves_max(self):
        base = BudgetPolicy(max_tokens=5_000)
        extended = base.with_threshold(0.5, lambda m: None, recurring=True)
        assert extended.max_tokens == 5_000
        assert extended.thresholds[0].recurring is True

    def test_build_monitor_installs_thresholds_in_order(self):
        captured: list[float] = []
        policy = BudgetPolicy(
            max_tokens=100,
            thresholds=(
                Threshold(percent=0.9, callback=lambda m: captured.append(0.9)),
                Threshold(percent=0.5, callback=lambda m: captured.append(0.5)),
            ),
        )
        monitor = policy.build_monitor()
        monitor.record_usage(95, 0)  # crosses both thresholds
        # Thresholds are sorted ascending inside the monitor, so 0.5 fires first.
        assert captured == [0.5, 0.9]


# ======================================================================
# BudgetPlugin
# ======================================================================


class TestBudgetPlugin:
    def _usage(self, inp: int, out: int) -> SimpleNamespace:
        return SimpleNamespace(
            usage_metadata=SimpleNamespace(
                prompt_token_count=inp,
                candidates_token_count=out,
            )
        )

    def test_builds_from_policy(self):
        plugin = BudgetPlugin(BudgetPolicy(max_tokens=1_000))
        assert plugin.monitor.max_tokens == 1_000
        assert plugin.monitor.current_tokens == 0

    def test_builds_from_monitor(self):
        monitor = BudgetMonitor(max_tokens=500)
        plugin = BudgetPlugin(monitor)
        assert plugin.monitor is monitor

    def test_rejects_junk_argument(self):
        with pytest.raises(TypeError):
            BudgetPlugin("not a policy")  # type: ignore[arg-type]

    def test_after_model_callback_records_usage(self):
        plugin = BudgetPlugin(BudgetPolicy(max_tokens=1_000))
        llm_response = self._usage(inp=100, out=50)

        asyncio.run(
            plugin.after_model_callback(
                callback_context=None, llm_response=llm_response
            )
        )
        assert plugin.monitor.current_tokens == 150
        assert plugin.monitor.turn_count == 1

    def test_after_model_callback_ignores_missing_usage(self):
        plugin = BudgetPlugin(BudgetPolicy(max_tokens=1_000))
        asyncio.run(
            plugin.after_model_callback(
                callback_context=None,
                llm_response=SimpleNamespace(usage_metadata=None),
            )
        )
        assert plugin.monitor.current_tokens == 0
        assert plugin.monitor.turn_count == 0

    def test_plugin_fires_policy_thresholds(self):
        fired: list[float] = []
        policy = BudgetPolicy(
            max_tokens=100,
            thresholds=(
                Threshold(
                    percent=0.5, callback=lambda m: fired.append(m.utilization)
                ),
            ),
        )
        plugin = BudgetPlugin(policy)

        asyncio.run(
            plugin.after_model_callback(
                callback_context=None, llm_response=self._usage(30, 30)
            )
        )
        assert len(fired) == 1
        assert fired[0] == pytest.approx(0.6)

    def test_plugin_custom_name(self):
        plugin = BudgetPlugin(BudgetPolicy(), name="custom-budget")
        assert plugin.name == "custom-budget"


# ======================================================================
# Tracker — Phase 5 additions (frozen threshold storage, etc.)
# ======================================================================


class TestTrackerAdditions:
    def test_add_threshold_accepts_frozen_value(self):
        monitor = BudgetMonitor(max_tokens=100)
        t = Threshold(percent=0.7, callback=lambda m: None)
        monitor.add_threshold(t)
        assert monitor.thresholds == (t,)

    def test_thresholds_property_is_tuple(self):
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.4, lambda m: None)
        monitor.on_threshold(0.8, lambda m: None)
        assert isinstance(monitor.thresholds, tuple)
        assert len(monitor.thresholds) == 2
        assert [t.percent for t in monitor.thresholds] == [0.4, 0.8]

    def test_thresholds_fired_count_starts_zero(self):
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.5, lambda m: None)
        assert monitor.thresholds_fired() == 0
        monitor.record_usage(30, 30)
        assert monitor.thresholds_fired() == 1

    def test_reset_clears_fired_state(self):
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.5, lambda m: None)
        monitor.record_usage(30, 30)
        assert monitor.thresholds_fired() == 1
        monitor.reset()
        assert monitor.thresholds_fired() == 0
        assert monitor.current_tokens == 0

    def test_adjust_rearms_threshold_when_below(self):
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.8, lambda m: None)
        monitor.record_usage(90, 0)
        assert monitor.thresholds_fired() == 1
        monitor.adjust(10)  # drop well below 80%
        assert monitor.thresholds_fired() == 0


# ======================================================================
# H namespace sugar
# ======================================================================


class TestHNamespaceBudget:
    def test_budget_policy_factory(self):
        p = H.budget_policy(50_000)
        assert isinstance(p, BudgetPolicy)
        assert p.max_tokens == 50_000

    def test_budget_policy_with_thresholds(self):
        t = Threshold(percent=0.9, callback=lambda m: None)
        p = H.budget_policy(50_000, thresholds=(t,))
        assert len(p.thresholds) == 1

    def test_budget_plugin_factory_from_policy(self):
        plugin = H.budget_plugin(H.budget_policy(10_000))
        assert isinstance(plugin, BudgetPlugin)
        assert plugin.monitor.max_tokens == 10_000

    def test_budget_plugin_factory_from_monitor(self):
        monitor = H.budget_monitor(10_000)
        plugin = H.budget_plugin(monitor)
        assert plugin.monitor is monitor
