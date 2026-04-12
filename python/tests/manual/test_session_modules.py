"""Tests for the ``adk_fluent._session`` package.

Covers SessionTape (recording/filter/summary/save/load), ForkManager
(via SessionStore wrappers), SessionSnapshot (serialization +
round-trip), SessionStore (component access, snapshot/from_snapshot,
callbacks), and SessionPlugin (after_agent auto-fork).
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from adk_fluent import (
    ForkManager,
    H,
    SessionPlugin,
    SessionSnapshot,
    SessionStore,
    SessionTape,
)
from adk_fluent._harness._events import HarnessEvent


@dataclass(frozen=True)
class _FakeEvent(HarnessEvent):
    kind: str = "fake"
    payload: str = ""


class TestSessionTape:
    def test_record_and_events(self):
        tape = SessionTape()
        tape.record(_FakeEvent(payload="hi"))
        tape.record(_FakeEvent(payload="there"))
        assert tape.size == 2
        assert tape.events[0]["kind"] == "fake"
        assert tape.events[0]["payload"] == "hi"

    def test_events_is_defensive_copy(self):
        tape = SessionTape()
        tape.record(_FakeEvent(payload="x"))
        snapshot = tape.events
        snapshot.clear()
        assert tape.size == 1

    def test_filter_by_kind(self):
        tape = SessionTape()
        tape.record(_FakeEvent(kind="a", payload="1"))
        tape.record(_FakeEvent(kind="b", payload="2"))
        tape.record(_FakeEvent(kind="a", payload="3"))
        matches = tape.filter("a")
        assert len(matches) == 2
        assert {m["payload"] for m in matches} == {"1", "3"}

    def test_max_events_evicts_oldest(self):
        tape = SessionTape(max_events=2)
        for i in range(5):
            tape.record(_FakeEvent(payload=str(i)))
        assert tape.size == 2
        assert tape.events[0]["payload"] == "3"
        assert tape.events[1]["payload"] == "4"

    def test_clear(self):
        tape = SessionTape()
        tape.record(_FakeEvent(payload="x"))
        tape.clear()
        assert tape.size == 0

    def test_save_and_load_round_trip(self, tmp_path: Path):
        tape = SessionTape()
        tape.record(_FakeEvent(payload="alpha"))
        tape.record(_FakeEvent(payload="beta"))
        out = tmp_path / "tape.jsonl"
        tape.save(out)
        loaded = SessionTape.load(out)
        assert loaded.size == 2
        assert loaded.events[0]["payload"] == "alpha"

    def test_summary_contains_counts(self):
        tape = SessionTape()
        tape.record(_FakeEvent(kind="a", payload="1"))
        tape.record(_FakeEvent(kind="a", payload="2"))
        tape.record(_FakeEvent(kind="b", payload="3"))
        summary = tape.summary()
        assert summary["total_events"] == 3
        assert summary["event_counts"] == {"a": 2, "b": 1}


class TestForkManager:
    def test_fork_and_switch(self):
        forks = ForkManager()
        forks.fork("base", {"x": 1})
        assert forks.active == "base"
        state = forks.switch("base")
        assert state == {"x": 1}

    def test_switch_returns_deep_copy(self):
        forks = ForkManager()
        forks.fork("base", {"data": [1, 2, 3]})
        restored = forks.switch("base")
        restored["data"].append(99)
        assert forks.get("base").state["data"] == [1, 2, 3]

    def test_switch_missing_raises(self):
        forks = ForkManager()
        with pytest.raises(KeyError):
            forks.switch("nope")

    def test_max_branches_evicts_oldest(self):
        forks = ForkManager(max_branches=2)
        forks.fork("a", {"n": 1})
        forks.fork("b", {"n": 2})
        forks.fork("c", {"n": 3})
        names = {b["name"] for b in forks.list_branches()}
        assert names == {"b", "c"}

    def test_merge_union(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1, "y": 2})
        forks.fork("b", {"y": 20, "z": 3})
        merged = forks.merge("a", "b", strategy="union")
        assert merged == {"x": 1, "y": 20, "z": 3}

    def test_merge_intersection(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1, "y": 2})
        forks.fork("b", {"y": 20, "z": 3})
        merged = forks.merge("a", "b", strategy="intersection")
        assert merged == {"y": 20}

    def test_merge_prefer(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1, "y": 2})
        forks.fork("b", {"x": 99, "z": 3})
        merged = forks.merge("a", "b", strategy="prefer", prefer="a")
        assert merged["x"] == 1
        assert merged["z"] == 3

    def test_diff(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1, "y": 2, "both": "same"})
        forks.fork("b", {"y": 22, "z": 3, "both": "same"})
        d = forks.diff("a", "b")
        assert d["only_a"] == {"x": 1}
        assert d["only_b"] == {"z": 3}
        assert d["different"] == {"y": {"a": 2, "b": 22}}
        assert d["same"] == {"both"}

    def test_delete(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1})
        forks.delete("a")
        assert forks.size == 0
        assert forks.active is None


class TestSessionSnapshot:
    def test_empty_snapshot_defaults(self):
        snap = SessionSnapshot()
        assert snap.event_count == 0
        assert snap.branch_count == 0
        assert snap.active_branch is None
        assert snap.version == 1

    def test_snapshot_is_frozen(self):
        snap = SessionSnapshot()
        with pytest.raises(FrozenInstanceError):
            snap.version = 2  # type: ignore[misc]

    def test_to_dict_deep_copies_events(self):
        snap = SessionSnapshot(events=({"a": 1},))
        d = snap.to_dict()
        d["events"][0]["a"] = 999
        assert snap.events[0]["a"] == 1

    def test_from_dict_round_trip(self):
        original = SessionSnapshot(
            events=({"kind": "x", "t": 0.1},),
            branches={"main": {"name": "main", "state": {"k": 1}}},
            active_branch="main",
        )
        rebuilt = SessionSnapshot.from_dict(original.to_dict())
        assert rebuilt.event_count == 1
        assert rebuilt.branch_count == 1
        assert rebuilt.active_branch == "main"

    def test_save_and_load(self, tmp_path: Path):
        snap = SessionSnapshot(
            events=({"kind": "x", "t": 0.1},),
            branches={"b": {"name": "b", "state": {"k": 1}}},
            active_branch="b",
        )
        out = tmp_path / "snap.json"
        snap.save(out)
        raw = json.loads(out.read_text())
        assert raw["version"] == 1
        loaded = SessionSnapshot.load(out)
        assert loaded.active_branch == "b"
        assert loaded.event_count == 1


class TestSessionStore:
    def test_components_default_to_fresh(self):
        store = SessionStore()
        assert isinstance(store.tape, SessionTape)
        assert isinstance(store.forks, ForkManager)

    def test_record_event_passes_through(self):
        store = SessionStore()
        store.record_event(_FakeEvent(payload="x"))
        assert store.tape.size == 1

    def test_fork_and_switch(self):
        store = SessionStore()
        store.fork("main", {"x": 1})
        store.fork("alt", {"x": 2})
        assert store.forks.active == "alt"
        assert store.switch("main")["x"] == 1

    def test_snapshot_captures_everything(self):
        store = SessionStore()
        store.record_event(_FakeEvent(payload="e1"))
        store.fork("base", {"x": 1})
        store.fork("alt", {"x": 2, "y": 3})
        snap = store.snapshot()
        assert snap.event_count == 1
        assert snap.branch_count == 2
        assert snap.active_branch == "alt"
        assert snap.branches["base"]["state"] == {"x": 1}

    def test_snapshot_round_trip(self):
        original = SessionStore()
        original.record_event(_FakeEvent(payload="e1"))
        original.fork("a", {"x": 1})
        original.fork("b", {"x": 2})
        snap = original.snapshot()

        restored = SessionStore.from_snapshot(snap)
        assert restored.tape.size == 1
        assert restored.forks.size == 2
        assert restored.forks.active == "b"
        assert restored.forks.get("a").state == {"x": 1}

    def test_auto_fork_callback_saves_state(self):
        store = SessionStore()
        cb = store.auto_fork("post_step")
        ctx = SimpleNamespace(state={"x": 42})
        cb(ctx)
        assert "post_step" in {b["name"] for b in store.forks.list_branches()}
        assert store.forks.get("post_step").state == {"x": 42}

    def test_auto_restore_callback_updates_state(self):
        store = SessionStore()
        store.fork("saved", {"x": 10})
        cb = store.auto_restore("saved")
        state = {"x": 0}
        ctx = SimpleNamespace(state=state)
        cb(ctx)
        assert state == {"x": 10}

    def test_summary_exposes_tape_and_branches(self):
        store = SessionStore()
        store.fork("a", {"x": 1})
        summary = store.summary()
        assert summary["branches"] == 1
        assert summary["active_branch"] == "a"
        assert "tape" in summary

    def test_clear_wipes_everything(self):
        store = SessionStore()
        store.record_event(_FakeEvent(payload="x"))
        store.fork("a", {"x": 1})
        store.clear()
        assert store.tape.size == 0
        assert store.forks.size == 0


class TestSessionPlugin:
    @pytest.mark.asyncio
    async def test_auto_fork_after_agent(self):
        plugin = SessionPlugin()
        ctx = SimpleNamespace(agent_name="writer", state={"draft": "v1"})
        await plugin.after_agent_callback(callback_context=ctx)
        names = {b["name"] for b in plugin.store.forks.list_branches()}
        assert "auto:writer" in names
        assert plugin.store.forks.get("auto:writer").state == {"draft": "v1"}

    @pytest.mark.asyncio
    async def test_auto_fork_disabled(self):
        plugin = SessionPlugin(auto_fork=False)
        ctx = SimpleNamespace(agent_name="writer", state={"draft": "v1"})
        await plugin.after_agent_callback(callback_context=ctx)
        assert plugin.store.forks.size == 0

    @pytest.mark.asyncio
    async def test_custom_fork_prefix(self):
        plugin = SessionPlugin(fork_prefix="snap")
        ctx = SimpleNamespace(agent_name="critic", state={"score": 0.9})
        await plugin.after_agent_callback(callback_context=ctx)
        names = {b["name"] for b in plugin.store.forks.list_branches()}
        assert "snap:critic" in names

    @pytest.mark.asyncio
    async def test_missing_state_is_graceful(self):
        plugin = SessionPlugin()
        ctx = SimpleNamespace(agent_name="a", state=None)
        # Should not raise
        result = await plugin.after_agent_callback(callback_context=ctx)
        assert result is None
        assert plugin.store.forks.size == 0

    def test_plugin_accepts_pre_built_store(self):
        store = SessionStore()
        plugin = SessionPlugin(store)
        assert plugin.store is store

    def test_plugin_is_base_plugin(self):
        from google.adk.plugins.base_plugin import BasePlugin

        assert isinstance(SessionPlugin(), BasePlugin)


class TestHNamespaceFactories:
    def test_session_store_factory(self):
        store = H.session_store()
        assert isinstance(store, SessionStore)

    def test_session_store_factory_with_caps(self):
        store = H.session_store(max_events=5, max_branches=3)
        store.fork("a", {})
        store.fork("b", {})
        store.fork("c", {})
        store.fork("d", {})  # Exceeds cap
        assert store.forks.size == 3

    def test_session_plugin_factory(self):
        plugin = H.session_plugin()
        assert isinstance(plugin, SessionPlugin)
        assert isinstance(plugin.store, SessionStore)

    def test_session_plugin_factory_custom_name(self):
        plugin = H.session_plugin(name="my_session")
        assert plugin.name == "my_session"
