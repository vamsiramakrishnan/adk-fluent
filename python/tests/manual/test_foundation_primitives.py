"""Tests for the 4 foundational primitives.

Covers:
    1. EventBus — session-scoped typed event backbone
    2. ToolPolicy — per-tool error recovery policies
    3. BudgetMonitor — token lifecycle with threshold triggers
    4. TaskLedger — dispatch/join bridge with tool interface

Also tests backward-compatible bridges from legacy modules.
"""

from unittest.mock import MagicMock

import pytest

from adk_fluent import H
from adk_fluent._budget import BudgetMonitor
from adk_fluent._harness._event_bus import EventBus
from adk_fluent._harness._events import (
    TextChunk,
    ToolCallStart,
)
from adk_fluent._harness._task_ledger import TaskLedger
from adk_fluent._harness._tool_policy import ToolPolicy

# ======================================================================
# 1. EventBus
# ======================================================================


class TestEventBus:
    def test_subscribe_all(self):
        bus = EventBus()
        received = []
        bus.subscribe(lambda e: received.append(e))

        bus.emit(TextChunk(text="hello"))
        bus.emit(ToolCallStart(tool_name="bash"))

        assert len(received) == 2
        assert received[0].text == "hello"

    def test_subscribe_by_kind(self):
        bus = EventBus()
        text_events = []
        tool_events = []

        bus.on("text", lambda e: text_events.append(e))
        bus.on("tool_call_start", lambda e: tool_events.append(e))

        bus.emit(TextChunk(text="hi"))
        bus.emit(ToolCallStart(tool_name="bash"))
        bus.emit(TextChunk(text="bye"))

        assert len(text_events) == 2
        assert len(tool_events) == 1

    def test_off_removes_handler(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe(handler)

        bus.emit(TextChunk(text="a"))
        bus.off(handler)
        bus.emit(TextChunk(text="b"))

        assert len(received) == 1

    def test_error_isolation(self):
        bus = EventBus()
        received = []

        def bad_handler(e):
            raise RuntimeError("boom")

        bus.subscribe(bad_handler)
        bus.subscribe(lambda e: received.append(e))

        bus.emit(TextChunk(text="test"))
        assert len(received) == 1  # second handler still runs

    def test_buffer(self):
        bus = EventBus(max_buffer=3)
        for i in range(5):
            bus.emit(TextChunk(text=str(i)))

        assert len(bus.buffer) == 3
        assert bus.buffer[0].text == "2"

    def test_subscriber_count(self):
        bus = EventBus()
        bus.subscribe(lambda e: None)
        bus.on("text", lambda e: None)
        bus.on("text", lambda e: None)

        assert bus.subscriber_count == 3

    def test_tape_factory(self):
        bus = EventBus()
        tape = bus.tape()

        bus.emit(TextChunk(text="hello"))
        bus.emit(ToolCallStart(tool_name="bash"))

        assert tape.size == 2

    def test_before_tool_hook(self):
        bus = EventBus()
        received = []
        bus.on("tool_call_start", lambda e: received.append(e))

        hook = bus.before_tool_hook()
        mock_tool = MagicMock()
        mock_tool.name = "read_file"

        result = hook(tool=mock_tool, args={"path": "x.py"}, tool_context=MagicMock())
        assert result is None  # allows execution
        assert len(received) == 1
        assert received[0].tool_name == "read_file"

    def test_after_tool_hook(self):
        bus = EventBus()
        received = []
        bus.on("tool_call_end", lambda e: received.append(e))

        hook = bus.after_tool_hook()
        mock_tool = MagicMock()
        mock_tool.name = "bash"

        result = hook(tool=mock_tool, args={}, tool_context=MagicMock(), tool_response="output text")
        assert result == "output text"
        assert len(received) == 1
        assert received[0].tool_name == "bash"

    def test_after_tool_emits_error_on_failure(self):
        bus = EventBus()
        errors = []
        bus.on("error", lambda e: errors.append(e))

        hook = bus.after_tool_hook()
        mock_tool = MagicMock()
        mock_tool.name = "bash"

        hook(tool=mock_tool, args={}, tool_context=MagicMock(), tool_response="Error: command failed")
        assert len(errors) == 1

    def test_h_event_bus_factory(self):
        bus = H.event_bus()
        assert isinstance(bus, EventBus)

    def test_chaining(self):
        bus = EventBus()
        result = bus.on("text", lambda e: None).subscribe(lambda e: None)
        assert result is bus


# ======================================================================
# 2. ToolPolicy
# ======================================================================


class TestToolPolicy:
    def test_retry_rule(self):
        policy = ToolPolicy().retry("bash", max_attempts=3, backoff=0.5)
        rule = policy.rule_for("bash")
        assert rule.action == "retry"
        assert rule.max_attempts == 3
        assert rule.backoff == 0.5

    def test_skip_rule(self):
        policy = ToolPolicy().skip("glob_search", fallback="No results.")
        rule = policy.rule_for("glob_search")
        assert rule.action == "skip"
        assert rule.fallback == "No results."

    def test_ask_rule(self):
        handler = lambda name, args, err: True
        policy = ToolPolicy().ask("edit_file", handler=handler)
        rule = policy.rule_for("edit_file")
        assert rule.action == "ask"
        assert rule.handler is handler

    def test_propagate_rule(self):
        policy = ToolPolicy().propagate("dangerous_tool")
        rule = policy.rule_for("dangerous_tool")
        assert rule.action == "propagate"

    def test_default_rule(self):
        policy = ToolPolicy(default="skip")
        rule = policy.rule_for("unknown_tool")
        assert rule.action == "skip"

    def test_after_tool_hook_allows_success(self):
        policy = ToolPolicy().retry("bash")
        hook = policy.after_tool_hook()

        mock_tool = MagicMock()
        mock_tool.name = "bash"
        result = hook(tool=mock_tool, args={}, tool_context=MagicMock(), tool_response="success output")
        assert result == "success output"

    def test_after_tool_hook_skips_on_error(self):
        policy = ToolPolicy().skip("glob", fallback="Skipped.")
        hook = policy.after_tool_hook()

        mock_tool = MagicMock()
        mock_tool.name = "glob"
        result = hook(tool=mock_tool, args={}, tool_context=MagicMock(), tool_response="Error: not found")
        assert result == {"result": "Skipped."}

    def test_after_tool_hook_retries_on_error(self):
        policy = ToolPolicy().retry("bash", max_attempts=2)
        hook = policy.after_tool_hook()

        mock_tool = MagicMock()
        mock_tool.name = "bash"

        # First failure — should propagate for LLM retry
        r1 = hook(tool=mock_tool, args={"cmd": "ls"}, tool_context=MagicMock(), tool_response="Error: fail")
        assert "Error" in str(r1)

        # Second failure — still retrying
        r2 = hook(tool=mock_tool, args={"cmd": "ls"}, tool_context=MagicMock(), tool_response="Error: fail")
        assert "Error" in str(r2)

    def test_after_tool_hook_ask_with_handler(self):
        handler = MagicMock(return_value=False)  # user says skip
        policy = ToolPolicy().ask("edit", handler=handler)
        hook = policy.after_tool_hook()

        mock_tool = MagicMock()
        mock_tool.name = "edit"
        result = hook(tool=mock_tool, args={}, tool_context=MagicMock(), tool_response="Error: permission denied")
        assert "skip" in str(result).lower() or "failed" in str(result).lower()

    def test_merge(self):
        a = ToolPolicy().retry("bash").skip("glob")
        b = ToolPolicy().retry("web").skip("bash")  # override bash

        merged = a.merge(b)
        assert merged.rule_for("bash").action == "skip"  # b wins
        assert merged.rule_for("glob").action == "skip"
        assert merged.rule_for("web").action == "retry"

    def test_with_event_bus(self):
        bus = EventBus()
        errors = []
        bus.on("error", lambda e: errors.append(e))

        policy = ToolPolicy().skip("bash").with_bus(bus)
        hook = policy.after_tool_hook()

        mock_tool = MagicMock()
        mock_tool.name = "bash"
        hook(tool=mock_tool, args={}, tool_context=MagicMock(), tool_response="Error: fail")

        assert len(errors) == 1

    def test_from_error_strategy(self):
        from adk_fluent._harness._error_strategy import ErrorStrategy

        strategy = ErrorStrategy(
            retry=frozenset({"bash"}),
            skip=frozenset({"glob"}),
            ask=frozenset({"edit"}),
        )
        policy = ToolPolicy.from_strategy(strategy)
        assert policy.rule_for("bash").action == "retry"
        assert policy.rule_for("glob").action == "skip"
        assert policy.rule_for("edit").action == "ask"

    def test_error_strategy_to_policy_bridge(self):
        from adk_fluent._harness._error_strategy import ErrorStrategy

        strategy = ErrorStrategy(retry=frozenset({"bash"}))
        policy = strategy.to_policy()
        assert policy.rule_for("bash").action == "retry"

    def test_h_tool_policy_factory(self):
        policy = H.tool_policy()
        assert isinstance(policy, ToolPolicy)

    def test_size(self):
        policy = ToolPolicy().retry("a").skip("b").ask("c")
        assert policy.size == 3


# ======================================================================
# 3. BudgetMonitor
# ======================================================================


class TestBudgetMonitor:
    def test_record_usage(self):
        monitor = BudgetMonitor(max_tokens=100_000)
        monitor.record_usage(5000, 2000)

        assert monitor.current_tokens == 7000
        assert monitor.turn_count == 1

    def test_utilization(self):
        monitor = BudgetMonitor(max_tokens=100_000)
        monitor.record_usage(80_000, 0)

        assert monitor.utilization == 0.8

    def test_remaining(self):
        monitor = BudgetMonitor(max_tokens=100_000)
        monitor.record_usage(60_000, 0)

        assert monitor.remaining == 40_000

    def test_threshold_fires(self):
        fired = []
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.8, lambda m: fired.append(m.utilization))

        monitor.record_usage(70, 0)  # 70% — no fire
        assert len(fired) == 0

        monitor.record_usage(15, 0)  # 85% — fires
        assert len(fired) == 1
        assert fired[0] >= 0.8

    def test_threshold_fires_once_by_default(self):
        count = [0]
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.5, lambda m: count.__setitem__(0, count[0] + 1))

        monitor.record_usage(60, 0)  # fires
        monitor.record_usage(10, 0)  # should NOT fire again
        assert count[0] == 1

    def test_threshold_recurring(self):
        count = [0]
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.5, lambda m: count.__setitem__(0, count[0] + 1), recurring=True)

        monitor.record_usage(60, 0)
        monitor.record_usage(10, 0)
        assert count[0] == 2

    def test_multiple_thresholds_in_order(self):
        fired = []
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.5, lambda m: fired.append("50%"))
        monitor.on_threshold(0.9, lambda m: fired.append("90%"))

        monitor.record_usage(95, 0)
        assert fired == ["50%", "90%"]

    def test_reset(self):
        monitor = BudgetMonitor(max_tokens=100)
        monitor.on_threshold(0.5, lambda m: None)
        monitor.record_usage(60, 0)

        monitor.reset()
        assert monitor.current_tokens == 0
        assert monitor.turn_count == 0

    def test_adjust(self):
        monitor = BudgetMonitor(max_tokens=100)
        fired = []
        monitor.on_threshold(0.8, lambda m: fired.append(True))
        monitor.record_usage(90, 0)
        assert len(fired) == 1

        monitor.adjust(30)
        assert monitor.current_tokens == 30
        monitor.record_usage(55, 0)
        assert len(fired) == 2

    def test_after_model_hook(self):
        monitor = BudgetMonitor(max_tokens=100_000)
        hook = monitor.after_model_hook()

        mock_response = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 5000
        mock_response.usage_metadata.candidates_token_count = 2000

        result = hook(callback_context=MagicMock(), llm_response=mock_response)
        assert result is mock_response
        assert monitor.current_tokens == 7000

    def test_with_event_bus(self):
        bus = EventBus()
        events = []
        bus.on("compression_triggered", lambda e: events.append(e))

        monitor = BudgetMonitor(max_tokens=100)
        monitor.with_bus(bus)
        monitor.on_threshold(0.5, lambda m: None)
        monitor.record_usage(60, 0)

        assert len(events) == 1
        assert events[0].token_count == 60

    def test_summary(self):
        monitor = BudgetMonitor(max_tokens=100_000)
        monitor.record_usage(5000, 2000)
        monitor.record_usage(3000, 1000)

        s = monitor.summary()
        assert s["turns"] == 2
        assert s["current_tokens"] == 11_000

    def test_estimated_turns_remaining(self):
        monitor = BudgetMonitor(max_tokens=100_000)
        monitor.record_usage(5000, 5000)

        assert monitor.estimated_turns_remaining == 9

    def test_h_budget_monitor_factory(self):
        monitor = H.budget_monitor(150_000)
        assert isinstance(monitor, BudgetMonitor)
        assert monitor.max_tokens == 150_000

    def test_compressor_bridge(self):
        from adk_fluent._compression import ContextCompressor

        compressor = ContextCompressor(threshold=100_000)
        monitor = compressor.to_monitor()
        assert isinstance(monitor, BudgetMonitor)
        assert monitor.max_tokens == 100_000


# ======================================================================
# 4. TaskLedger
# ======================================================================


class TestTaskLedger:
    def test_register_and_get(self):
        ledger = TaskLedger()
        task = ledger.register("build", "Run the build")

        assert task["name"] == "build"
        assert task["status"] == "pending"

        assert ledger.get("build") is not None

    def test_lifecycle(self):
        ledger = TaskLedger()
        ledger.register("test")
        ledger.start("test")
        assert ledger.get("test")["status"] == "running"

        ledger.complete("test", "All passed")
        assert ledger.get("test")["status"] == "complete"
        assert ledger.get("test")["result"] == "All passed"

    def test_fail(self):
        ledger = TaskLedger()
        ledger.register("deploy")
        ledger.fail("deploy", "Timeout")
        assert ledger.get("deploy")["status"] == "failed"

    def test_cancel(self):
        ledger = TaskLedger()
        ledger.register("long_task")
        ledger.start("long_task")
        assert ledger.cancel("long_task")
        assert ledger.get("long_task")["status"] == "cancelled"

    def test_cancel_completed_returns_false(self):
        ledger = TaskLedger()
        ledger.register("done")
        ledger.complete("done")
        assert not ledger.cancel("done")

    def test_max_tasks(self):
        ledger = TaskLedger(max_tasks=2)
        ledger.register("a")
        ledger.register("b")
        with pytest.raises(ValueError, match="Maximum"):
            ledger.register("c")

    def test_duplicate_active_task(self):
        ledger = TaskLedger()
        ledger.register("build")
        with pytest.raises(ValueError, match="already"):
            ledger.register("build")

    def test_reregister_completed_task(self):
        ledger = TaskLedger()
        ledger.register("build")
        ledger.complete("build")
        task = ledger.register("build")
        assert task["status"] == "pending"

    def test_active_count(self):
        ledger = TaskLedger()
        ledger.register("a")
        ledger.register("b")
        ledger.start("a")
        ledger.complete("b")
        assert ledger.active_count == 1

    def test_tools_launch(self):
        ledger = TaskLedger()
        tools = ledger.tools()
        result = tools[0]("build", "Run pytest")
        assert "registered" in result

    def test_tools_check(self):
        ledger = TaskLedger()
        ledger.register("build")
        ledger.complete("build", "OK")
        tools = ledger.tools()
        result = tools[1]("build")
        assert "complete" in result

    def test_tools_list(self):
        ledger = TaskLedger()
        ledger.register("a")
        ledger.register("b")
        tools = ledger.tools()
        result = tools[2]()
        assert "a:" in result

    def test_tools_cancel(self):
        ledger = TaskLedger()
        ledger.register("build")
        tools = ledger.tools()
        result = tools[3]("build")
        assert "cancelled" in result.lower()

    def test_with_event_bus(self):
        bus = EventBus()
        events = []
        bus.on("task_event", lambda e: events.append(e))

        ledger = TaskLedger().with_bus(bus)
        ledger.register("build")
        ledger.start("build")
        ledger.complete("build")

        assert len(events) == 3
        assert events[0].status == "pending"
        assert events[2].status == "complete"

    def test_task_registry_bridge(self):
        from adk_fluent._harness._tasks import TaskRegistry

        registry = TaskRegistry()
        registry.register("old_task", "legacy")
        registry.complete("old_task", "done")

        ledger = registry.to_ledger()
        assert isinstance(ledger, TaskLedger)
        assert ledger.size == 1

    def test_h_task_ledger_factory(self):
        ledger = H.task_ledger()
        assert isinstance(ledger, TaskLedger)


# ======================================================================
# Integration: Foundations compose together
# ======================================================================


class TestFoundationComposition:
    def test_event_bus_with_tool_policy(self):
        bus = EventBus()
        errors = []
        bus.on("error", lambda e: errors.append(e))

        policy = ToolPolicy().skip("bash").with_bus(bus)
        hook = policy.after_tool_hook()

        mock_tool = MagicMock()
        mock_tool.name = "bash"
        hook(tool=mock_tool, args={}, tool_context=MagicMock(), tool_response="Error: failed")

        assert len(errors) == 1
        assert errors[0].tool_name == "bash"

    def test_event_bus_with_budget_monitor(self):
        bus = EventBus()
        triggered = []
        bus.on("compression_triggered", lambda e: triggered.append(e))

        monitor = BudgetMonitor(max_tokens=100).with_bus(bus)
        monitor.on_threshold(0.8, lambda m: None)
        monitor.record_usage(85, 0)

        assert len(triggered) == 1

    def test_event_bus_with_task_ledger(self):
        bus = EventBus()
        tape = bus.tape()

        ledger = TaskLedger().with_bus(bus)
        ledger.register("build")
        ledger.complete("build", "OK")

        assert tape.size == 2

    def test_full_stack(self):
        """All 4 foundations wired together through one bus."""
        bus = EventBus()
        tape = bus.tape()

        policy = ToolPolicy().skip("glob").with_bus(bus)
        monitor = BudgetMonitor(max_tokens=100_000).with_bus(bus)
        monitor.on_threshold(0.9, lambda m: None)
        ledger = TaskLedger().with_bus(bus)

        # tool error
        hook = policy.after_tool_hook()
        mock_tool = MagicMock()
        mock_tool.name = "glob"
        hook(tool=mock_tool, args={}, tool_context=MagicMock(), tool_response="Error: fail")

        # token usage crossing threshold
        monitor.record_usage(95_000, 0)

        # task lifecycle
        ledger.register("deploy")
        ledger.complete("deploy", "done")

        assert tape.size >= 4  # error + compression + 2 task events

    def test_dispatcher_delegates_to_bus(self):
        from adk_fluent._harness._dispatcher import EventDispatcher

        bus = EventBus()
        dispatcher = EventDispatcher(bus=bus)

        received = []
        dispatcher.on("text", lambda e: received.append(e))
        dispatcher.emit(TextChunk(text="hello"))

        assert len(received) == 1
        assert dispatcher.bus is bus

    def test_h_factories_all_exist(self):
        assert callable(H.event_bus)
        assert callable(H.tool_policy)
        assert callable(H.budget_monitor)
        assert callable(H.task_ledger)
