"""Tests for DevEx helper classes: StateKey, Artifact, events."""

import pytest

from adk_fluent._helpers import Artifact, StateKey, run_events

# ======================================================================
# StateKey Tests
# ======================================================================


class TestStateKey:
    """Tests for StateKey typed state descriptor."""

    def test_session_scope_no_prefix(self):
        """Session scope uses bare name as key."""
        key = StateKey("counter", scope="session", type=int, default=0)
        assert key.key == "counter"
        assert key.name == "counter"
        assert key.scope == "session"

    def test_temp_scope_prefix(self):
        """Temp scope adds temp: prefix."""
        key = StateKey("counter", scope="temp", type=int, default=0)
        assert key.key == "temp:counter"

    def test_user_scope_prefix(self):
        """User scope adds user: prefix."""
        key = StateKey("prefs", scope="user", type=dict)
        assert key.key == "user:prefs"

    def test_app_scope_prefix(self):
        """App scope adds app: prefix."""
        key = StateKey("config", scope="app", type=dict)
        assert key.key == "app:config"

    def test_invalid_scope_raises(self):
        """Invalid scope raises ValueError."""
        with pytest.raises(ValueError, match="Invalid scope"):
            StateKey("x", scope="invalid")

    def test_get_with_dict(self):
        """get() works with plain dict (for testing)."""
        key = StateKey("count", scope="session", type=int, default=0)
        state = {}
        assert key.get(state) == 0  # default
        state["count"] = 42
        assert key.get(state) == 42

    def test_set_with_dict(self):
        """set() works with plain dict."""
        key = StateKey("count", scope="session", type=int, default=0)
        state = {}
        key.set(state, 42)
        assert state["count"] == 42

    def test_get_set_with_mock_context(self):
        """get/set work with a mock context that has .state attribute."""
        key = StateKey("count", scope="temp", type=int, default=0)

        class MockCtx:
            def __init__(self):
                self.state = {}

        ctx = MockCtx()
        assert key.get(ctx) == 0
        key.set(ctx, 5)
        assert key.get(ctx) == 5
        assert ctx.state["temp:count"] == 5

    def test_increment(self):
        """increment() adds to numeric value."""
        key = StateKey("count", scope="session", type=int, default=0)
        state = {}
        result = key.increment(state)
        assert result == 1
        assert state["count"] == 1
        result = key.increment(state, 5)
        assert result == 6

    def test_append(self):
        """append() adds to list value."""
        key = StateKey("items", scope="session", type=list, default=None)
        state = {}
        key.append(state, "a")
        assert state["items"] == ["a"]
        key.append(state, "b")
        assert state["items"] == ["a", "b"]

    def test_repr(self):
        """repr is readable."""
        key = StateKey("count", scope="temp", type=int, default=0)
        assert repr(key) == "StateKey('count', scope='temp', type=int)"


# ======================================================================
# Artifact Tests
# ======================================================================


class TestArtifact:
    """Tests for Artifact fluent descriptor."""

    def test_filename(self):
        """filename property returns the name."""
        a = Artifact("report.txt")
        assert a.filename == "report.txt"

    def test_repr(self):
        """repr is readable."""
        a = Artifact("report.txt")
        assert repr(a) == "Artifact('report.txt')"

    def test_save_creates_text_part(self):
        """save() wraps text content in a Part."""
        import asyncio

        async def _test():
            a = Artifact("test.txt")
            saved_parts = []

            class MockCtx:
                async def save_artifact(self, filename, part):
                    saved_parts.append((filename, part))
                    return 1

            version = await a.save(MockCtx(), "hello")
            assert version == 1
            assert len(saved_parts) == 1
            assert saved_parts[0][0] == "test.txt"

        asyncio.run(_test())

    def test_load_returns_text(self):
        """load() extracts text from Part wrapper."""
        import asyncio

        async def _test():
            a = Artifact("test.txt")

            class MockPart:
                text = "hello world"

            class MockCtx:
                async def load_artifact(self, filename, version=None):
                    return MockPart()

            content = await a.load(MockCtx())
            assert content == "hello world"

        asyncio.run(_test())

    def test_load_returns_none_when_missing(self):
        """load() returns None when artifact doesn't exist."""
        import asyncio

        async def _test():
            a = Artifact("missing.txt")

            class MockCtx:
                async def load_artifact(self, filename, version=None):
                    return None

            content = await a.load(MockCtx())
            assert content is None

        asyncio.run(_test())


# ======================================================================
# Events Tests
# ======================================================================


class TestRunEvents:
    """Tests for run_events helper function existence."""

    def test_run_events_is_importable(self):
        """run_events function exists and is importable."""
        assert callable(run_events)

    def test_run_events_in_all(self):
        """run_events is in __all__."""
        from adk_fluent import _helpers

        assert "run_events" in _helpers.__all__

    def test_events_method_on_agent(self):
        """Agent builder has .events() method from seed extra."""
        from adk_fluent import Agent

        agent = Agent("test").model("gemini-2.5-flash")
        assert hasattr(agent, "events")
