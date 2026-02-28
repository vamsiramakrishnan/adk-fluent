"""Tests for Phase D — Scratchpads + Molecule Sugar.

Tests CNotes, CWriteNotes, CRolling, CFromAgentsWindowed, CUser,
CManusCascade, note lifecycle management (consolidate_notes, clear_notes),
and the make_write_notes_callback factory.
"""

import asyncio
import json

from adk_fluent._context import (
    C,
    CFromAgentsWindowed,
    CManusCascade,
    CNotes,
    CRolling,
    CUser,
    CWriteNotes,
    _compile_context_spec,
    clear_notes,
    consolidate_notes,
    make_write_notes_callback,
)

# ======================================================================
# Mock helpers (same pattern as test_c_phase_b.py)
# ======================================================================


class _MockPart:
    def __init__(self, text=None):
        self.text = text


class _MockContent:
    def __init__(self, parts):
        self.parts = parts


class _MockEvent:
    def __init__(self, author, text):
        self.author = author
        self.content = _MockContent([_MockPart(text=text)])


class _MockSession:
    def __init__(self, events):
        self.events = events


class _MockState(dict):
    pass


class _MockCtx:
    def __init__(self, events=None, state=None):
        self.session = _MockSession(events or [])
        self.state = _MockState(state or {})


def _run(coro):
    """Run async provider in sync test."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ======================================================================
# CNotes — Read scratchpad
# ======================================================================


class TestCNotes:
    """C.notes() reads structured notes from session state."""

    def test_factory_returns_cnotes(self):
        spec = C.notes("observations")
        assert isinstance(spec, CNotes)
        assert spec.key == "observations"
        assert spec._kind == "notes"

    def test_notes_empty_state(self):
        ctx = _MockCtx()
        spec = C.notes("observations")
        result = _run(spec.instruction_provider(ctx))
        assert result == ""

    def test_notes_plain_format(self):
        ctx = _MockCtx(state={"_notes_observations": json.dumps(["fact 1", "fact 2"])})
        spec = C.notes("observations")
        result = _run(spec.instruction_provider(ctx))
        assert "[Notes: observations]" in result
        assert "fact 1" in result
        assert "fact 2" in result

    def test_notes_checklist_format(self):
        ctx = _MockCtx(state={"_notes_tasks": json.dumps(["do X", "do Y"])})
        spec = C.notes("tasks", format="checklist")
        result = _run(spec.instruction_provider(ctx))
        assert "- [ ] do X" in result
        assert "- [ ] do Y" in result

    def test_notes_numbered_format(self):
        ctx = _MockCtx(state={"_notes_steps": json.dumps(["step A", "step B"])})
        spec = C.notes("steps", format="numbered")
        result = _run(spec.instruction_provider(ctx))
        assert "1. step A" in result
        assert "2. step B" in result

    def test_notes_raw_string(self):
        ctx = _MockCtx(state={"_notes_log": "plain text note"})
        spec = C.notes("log")
        result = _run(spec.instruction_provider(ctx))
        assert "plain text note" in result

    def test_notes_list_direct(self):
        ctx = _MockCtx(state={"_notes_items": ["a", "b", "c"]})
        spec = C.notes("items")
        result = _run(spec.instruction_provider(ctx))
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_notes_include_contents_none(self):
        spec = C.notes("x")
        assert spec.include_contents == "none"

    def test_notes_compose_with_plus(self):
        combined = C.notes("obs") + C.from_state("intent")
        assert hasattr(combined, "blocks")

    def test_notes_compose_with_pipe(self):
        piped = C.notes("obs") | C.relevant(query="test")
        assert hasattr(piped, "source")
        assert hasattr(piped, "transform")


# ======================================================================
# CWriteNotes — Write scratchpad
# ======================================================================


class TestCWriteNotes:
    """C.write_notes() declares scratchpad writes."""

    def test_factory_returns_cwritenotes(self):
        spec = C.write_notes("observations", strategy="append")
        assert isinstance(spec, CWriteNotes)
        assert spec.key == "observations"
        assert spec.strategy == "append"
        assert spec._kind == "write_notes"

    def test_write_notes_no_provider(self):
        spec = C.write_notes("x")
        # CWriteNotes has no instruction_provider
        assert spec.instruction_provider is None

    def test_write_notes_strategies(self):
        for strategy in ("append", "replace", "merge", "prepend"):
            spec = C.write_notes("x", strategy=strategy)
            assert spec.strategy == strategy

    def test_write_notes_with_source_key(self):
        spec = C.write_notes("log", source_key="findings")
        assert spec.source_key == "findings"


# ======================================================================
# make_write_notes_callback — runtime callback
# ======================================================================


class TestWriteNotesCallback:
    """make_write_notes_callback creates a proper after_agent callback."""

    def test_append_creates_list(self):
        cb = make_write_notes_callback("obs", "append", None)
        state = _MockState()
        events = [_MockEvent("agent_a", "finding 1")]
        ctx = type("Ctx", (), {"state": state, "session": _MockSession(events)})()
        _run(cb(ctx))
        assert "_notes_obs" in state
        entries = json.loads(state["_notes_obs"])
        assert "finding 1" in entries

    def test_append_accumulates(self):
        state = _MockState({"_notes_obs": json.dumps(["old note"])})
        events = [_MockEvent("agent_a", "new note")]
        ctx = type("Ctx", (), {"state": state, "session": _MockSession(events)})()
        cb = make_write_notes_callback("obs", "append", None)
        _run(cb(ctx))
        entries = json.loads(state["_notes_obs"])
        assert "old note" in entries
        assert "new note" in entries

    def test_replace_overwrites(self):
        state = _MockState({"_notes_obs": json.dumps(["old"])})
        events = [_MockEvent("agent_a", "new")]
        ctx = type("Ctx", (), {"state": state, "session": _MockSession(events)})()
        cb = make_write_notes_callback("obs", "replace", None)
        _run(cb(ctx))
        entries = json.loads(state["_notes_obs"])
        assert entries == ["new"]

    def test_prepend_inserts_at_front(self):
        state = _MockState({"_notes_obs": json.dumps(["second"])})
        events = [_MockEvent("agent_a", "first")]
        ctx = type("Ctx", (), {"state": state, "session": _MockSession(events)})()
        cb = make_write_notes_callback("obs", "prepend", None)
        _run(cb(ctx))
        entries = json.loads(state["_notes_obs"])
        assert entries[0] == "first"
        assert entries[1] == "second"

    def test_merge_deduplicates(self):
        state = _MockState({"_notes_obs": json.dumps(["existing"])})
        events = [_MockEvent("agent_a", "existing")]
        ctx = type("Ctx", (), {"state": state, "session": _MockSession(events)})()
        cb = make_write_notes_callback("obs", "merge", None)
        _run(cb(ctx))
        entries = json.loads(state["_notes_obs"])
        assert entries.count("existing") == 1

    def test_source_key(self):
        state = _MockState({"findings": "from source"})
        ctx = type("Ctx", (), {"state": state, "session": _MockSession([])})()
        cb = make_write_notes_callback("obs", "append", "findings")
        _run(cb(ctx))
        entries = json.loads(state["_notes_obs"])
        assert "from source" in entries


# ======================================================================
# Note lifecycle
# ======================================================================


class TestNoteLifecycle:
    """consolidate_notes and clear_notes manage note entries."""

    def test_consolidate_deduplicates(self):
        state = _MockState({"_notes_x": json.dumps(["a", "b", "a", "c", "b"])})
        consolidate_notes(state, "x")
        entries = json.loads(state["_notes_x"])
        assert entries == ["a", "b", "c"]

    def test_consolidate_caps_entries(self):
        state = _MockState({"_notes_x": json.dumps(["a", "b", "c", "d", "e"])})
        consolidate_notes(state, "x", max_entries=3)
        entries = json.loads(state["_notes_x"])
        assert len(entries) == 3
        assert entries == ["c", "d", "e"]

    def test_clear_notes(self):
        state = _MockState({"_notes_x": json.dumps(["a", "b"])})
        clear_notes(state, "x")
        entries = json.loads(state["_notes_x"])
        assert entries == []

    def test_consolidate_empty(self):
        state = _MockState()
        consolidate_notes(state, "x")
        entries = json.loads(state["_notes_x"])
        assert entries == []


# ======================================================================
# CRolling — Rolling window with optional summarization
# ======================================================================


class TestCRolling:
    """C.rolling() provides a rolling window with summarization."""

    def test_factory(self):
        spec = C.rolling(5)
        assert isinstance(spec, CRolling)
        assert spec.n == 5
        assert spec._kind == "rolling"

    def test_rolling_basic_window(self):
        events = [
            _MockEvent("user", "q1"),
            _MockEvent("agent", "a1"),
            _MockEvent("user", "q2"),
            _MockEvent("agent", "a2"),
            _MockEvent("user", "q3"),
            _MockEvent("agent", "a3"),
        ]
        ctx = _MockCtx(events=events)
        spec = C.rolling(2, summarize=False)
        result = _run(spec.instruction_provider(ctx))
        # Should include last 2 user turns
        assert "q2" in result
        assert "q3" in result

    def test_rolling_without_summarize(self):
        events = [
            _MockEvent("user", "q1"),
            _MockEvent("agent", "a1"),
        ]
        ctx = _MockCtx(events=events)
        spec = C.rolling(5, summarize=False)
        result = _run(spec.instruction_provider(ctx))
        assert "q1" in result

    def test_rolling_compose(self):
        combined = C.rolling(3) + C.from_state("intent")
        assert hasattr(combined, "blocks")


# ======================================================================
# CFromAgentsWindowed — Per-agent windowing
# ======================================================================


class TestCFromAgentsWindowed:
    """C.from_agents_windowed() windows each agent independently."""

    def test_factory(self):
        spec = C.from_agents_windowed(researcher=1, critic=3)
        assert isinstance(spec, CFromAgentsWindowed)
        assert spec._kind == "from_agents_windowed"
        assert ("researcher", 1) in spec.agent_windows

    def test_per_agent_windowing(self):
        events = [
            _MockEvent("user", "question"),
            _MockEvent("researcher", "finding 1"),
            _MockEvent("researcher", "finding 2"),
            _MockEvent("researcher", "finding 3"),
            _MockEvent("critic", "critique 1"),
            _MockEvent("critic", "critique 2"),
        ]
        ctx = _MockCtx(events=events)
        spec = C.from_agents_windowed(researcher=1, critic=2)
        result = _run(spec.instruction_provider(ctx))
        # researcher: last 1 event
        assert "finding 3" in result
        assert "finding 1" not in result
        # critic: last 2 events
        assert "critique 1" in result
        assert "critique 2" in result
        # user messages included
        assert "question" in result

    def test_empty_events(self):
        ctx = _MockCtx()
        spec = C.from_agents_windowed(researcher=1)
        result = _run(spec.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# CUser — User message strategies
# ======================================================================


class TestCUser:
    """C.user() selects user messages with strategies."""

    def test_factory(self):
        spec = C.user(strategy="bookend")
        assert isinstance(spec, CUser)
        assert spec.strategy == "bookend"
        assert spec._kind == "user_strategy"

    def test_all_strategy(self):
        events = [
            _MockEvent("user", "q1"),
            _MockEvent("agent", "a1"),
            _MockEvent("user", "q2"),
            _MockEvent("agent", "a2"),
            _MockEvent("user", "q3"),
        ]
        ctx = _MockCtx(events=events)
        result = _run(C.user(strategy="all").instruction_provider(ctx))
        assert "q1" in result
        assert "q2" in result
        assert "q3" in result

    def test_first_strategy(self):
        events = [
            _MockEvent("user", "q1"),
            _MockEvent("agent", "a1"),
            _MockEvent("user", "q2"),
        ]
        ctx = _MockCtx(events=events)
        result = _run(C.user(strategy="first").instruction_provider(ctx))
        assert "q1" in result
        assert "q2" not in result

    def test_last_strategy(self):
        events = [
            _MockEvent("user", "q1"),
            _MockEvent("agent", "a1"),
            _MockEvent("user", "q2"),
        ]
        ctx = _MockCtx(events=events)
        result = _run(C.user(strategy="last").instruction_provider(ctx))
        assert "q2" in result
        assert "q1" not in result

    def test_bookend_strategy(self):
        events = [
            _MockEvent("user", "q1"),
            _MockEvent("agent", "a1"),
            _MockEvent("user", "q2"),
            _MockEvent("agent", "a2"),
            _MockEvent("user", "q3"),
        ]
        ctx = _MockCtx(events=events)
        result = _run(C.user(strategy="bookend").instruction_provider(ctx))
        assert "q1" in result
        assert "q3" in result
        assert "q2" not in result

    def test_bookend_two_messages(self):
        events = [
            _MockEvent("user", "q1"),
            _MockEvent("user", "q2"),
        ]
        ctx = _MockCtx(events=events)
        result = _run(C.user(strategy="bookend").instruction_provider(ctx))
        assert "q1" in result
        assert "q2" in result

    def test_empty_events(self):
        ctx = _MockCtx()
        result = _run(C.user(strategy="all").instruction_provider(ctx))
        assert result == ""


# ======================================================================
# CManusCascade — Progressive compression
# ======================================================================


class TestCManusCascade:
    """C.manus_cascade() provides progressive compression."""

    def test_factory(self):
        spec = C.manus_cascade(budget=4000)
        assert isinstance(spec, CManusCascade)
        assert spec.budget == 4000
        assert spec._kind == "manus_cascade"

    def test_within_budget(self):
        events = [_MockEvent("user", "short message")]
        ctx = _MockCtx(events=events)
        spec = C.manus_cascade(budget=8000)
        result = _run(spec.instruction_provider(ctx))
        assert "short message" in result


# ======================================================================
# Compile context spec integration
# ======================================================================


class TestCompileContextSpec:
    """Phase D transforms compile correctly."""

    def test_notes_compile(self):
        compiled = _compile_context_spec("Do the task.", C.notes("obs"))
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])

    def test_rolling_compile(self):
        compiled = _compile_context_spec("Summarize.", C.rolling(3))
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])

    def test_user_compile(self):
        compiled = _compile_context_spec("Answer.", C.user(strategy="last"))
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])

    def test_notes_plus_state(self):
        combined = C.notes("obs") + C.from_state("intent")
        compiled = _compile_context_spec("Handle.", combined)
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])
