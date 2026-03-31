"""Tests for collaboration mechanism primitives: notify, watch, C.shared_thread, group_chat."""

from __future__ import annotations

import pytest

from adk_fluent import Agent, Loop, Pipeline
from adk_fluent._context import C, CSharedThread
from adk_fluent._primitive_builders import (
    _NotifyBuilder,
    _WatchBuilder,
)
from adk_fluent.patterns import group_chat

# ======================================================================
# notify() tests
# ======================================================================


class TestNotify:
    def test_notify_creates_builder(self):
        from adk_fluent import notify

        a = Agent("logger").instruct("Log.")
        n = notify(a)
        assert isinstance(n, _NotifyBuilder)

    def test_notify_builds_dispatch_agent(self):
        from adk_fluent import notify

        a = Agent("logger").instruct("Log.")
        b = Agent("emailer").instruct("Email.")
        n = notify(a, b)
        built = n.build()
        assert built.name.startswith("notify_")
        assert len(built.sub_agents) == 2
        assert built.sub_agents[0].name == "logger"
        assert built.sub_agents[1].name == "emailer"

    def test_notify_in_pipeline(self):
        from adk_fluent import notify

        logger = Agent("logger").instruct("Log.")
        pipe = (
            Agent("worker").instruct("Work.")
            >> notify(logger)
            >> Agent("formatter").instruct("Format.")
        )
        assert isinstance(pipe, Pipeline)
        built = pipe.build()
        assert len(built.sub_agents) == 3

    def test_notify_task_names_from_agents(self):
        from adk_fluent import notify

        a = Agent("audit_log").instruct("Log.")
        n = notify(a)
        assert n._task_names == ("audit_log",)

    def test_notify_with_callbacks(self):
        from adk_fluent import notify

        called = []
        n = notify(
            Agent("a").instruct("A."),
            on_complete=lambda name, text: called.append(name),
        )
        assert n._on_complete is not None

    def test_notify_to_ir(self):
        from adk_fluent import notify
        from adk_fluent._ir import DispatchNode

        n = notify(Agent("a").instruct("A."))
        ir = n.to_ir()
        assert isinstance(ir, DispatchNode)


# ======================================================================
# watch() tests
# ======================================================================


class TestWatch:
    def test_watch_creates_builder(self):
        from adk_fluent import watch

        handler = Agent("notifier").instruct("Notify.")
        w = watch("draft", handler)
        assert isinstance(w, _WatchBuilder)
        assert w._key == "draft"

    def test_watch_builds_agent(self):
        from adk_fluent import watch

        handler = Agent("notifier").instruct("Notify.")
        w = watch("draft", handler)
        built = w.build()
        assert built.name.startswith("watch_draft_")
        assert len(built.sub_agents) == 1  # handler is a sub_agent

    def test_watch_with_function_handler(self):
        from adk_fluent import watch

        fn = lambda old, new, state: {"changed": True}  # noqa: E731
        w = watch("score", fn)
        built = w.build()
        assert built.name.startswith("watch_score_")
        assert len(built.sub_agents) == 0  # function handler, no sub_agents

    def test_watch_trigger_modes(self):
        from adk_fluent import watch

        w_change = watch("key", Agent("a").instruct("A."), trigger="change")
        assert w_change._trigger == "change"

        w_write = watch("key", Agent("a").instruct("A."), trigger="write")
        assert w_write._trigger == "write"

        w_truthy = watch("key", Agent("a").instruct("A."), trigger="truthy")
        assert w_truthy._trigger == "truthy"

    def test_watch_in_pipeline(self):
        from adk_fluent import watch

        pipe = (
            Agent("writer").instruct("Write.").writes("draft")
            >> watch("draft", Agent("notifier").instruct("Notify."))
            >> Agent("reviewer").instruct("Review.")
        )
        assert isinstance(pipe, Pipeline)
        built = pipe.build()
        assert len(built.sub_agents) == 3

    def test_watch_to_ir(self):
        from adk_fluent import watch
        from adk_fluent._ir import WatchNode

        w = watch("score", Agent("handler").instruct("Handle."))
        ir = w.to_ir()
        assert isinstance(ir, WatchNode)
        assert ir.key == "score"
        assert ir.trigger == "change"


# ======================================================================
# C.shared_thread() tests
# ======================================================================


class TestSharedThread:
    def test_shared_thread_creates_transform(self):
        st = C.shared_thread()
        assert isinstance(st, CSharedThread)
        assert st.include_contents == "none"

    def test_shared_thread_has_provider(self):
        st = C.shared_thread()
        assert st.instruction_provider is not None
        assert callable(st.instruction_provider)

    def test_shared_thread_composable(self):
        combined = C.shared_thread() + C.from_state("topic")
        assert combined is not None

    def test_shared_thread_on_agent(self):
        agent = (
            Agent("writer", "gemini-2.5-flash")
            .instruct("Write about the topic.")
            .context(C.shared_thread())
        )
        built = agent.build()
        # With shared_thread, include_contents should be "none"
        assert built.include_contents == "none"


# ======================================================================
# group_chat() tests
# ======================================================================


class TestGroupChat:
    def test_group_chat_creates_loop(self):
        result = group_chat(
            Agent("a").instruct("A."),
            Agent("b").instruct("B."),
            max_rounds=3,
        )
        assert isinstance(result, Loop)

    def test_group_chat_requires_two_agents(self):
        with pytest.raises(ValueError, match="at least 2"):
            group_chat(Agent("solo").instruct("Solo."))

    def test_group_chat_builds(self):
        result = group_chat(
            Agent("researcher").instruct("Research."),
            Agent("writer").instruct("Write."),
            Agent("critic").instruct("Critique."),
            max_rounds=4,
        )
        built = result.build()
        # Loop flattens: 3 agents + 1 _CheckpointAgent (until predicate)
        assert len(built.sub_agents) == 4
        agent_names = [a.name for a in built.sub_agents[:3]]
        assert agent_names == ["researcher", "writer", "critic"]

    def test_group_chat_custom_stop_key(self):
        result = group_chat(
            Agent("a").instruct("A."),
            Agent("b").instruct("B."),
            stop_key="consensus",
            max_rounds=5,
        )
        assert isinstance(result, Loop)

    def test_group_chat_applies_shared_thread(self):
        result = group_chat(
            Agent("a", "gemini-2.5-flash").instruct("A."),
            Agent("b", "gemini-2.5-flash").instruct("B."),
        )
        built = result.build()
        inner_pipeline = built.sub_agents[0]
        # All agents in the pipeline should have include_contents="none"
        # (set by C.shared_thread())
        for agent in inner_pipeline.sub_agents:
            assert agent.include_contents == "none"


# ======================================================================
# WatchAgent runtime tests
# ======================================================================


class TestWatchAgentRuntime:
    def test_watch_agent_import(self):
        from adk_fluent.backends.adk._primitives import WatchAgent

        assert WatchAgent is not None

    def test_watch_agent_construction(self):
        from adk_fluent.backends.adk._primitives import WatchAgent

        def handler(old, new, state):
            return {"changed": True}

        agent = WatchAgent(
            name="test_watch",
            watch_key="score",
            handler=handler,
            handler_is_agent=False,
            trigger="change",
        )
        assert agent.name == "test_watch"
