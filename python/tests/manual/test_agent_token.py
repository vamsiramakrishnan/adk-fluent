"""Tests for Phase G: AgentToken + TokenRegistry."""

from __future__ import annotations

import pytest

from adk_fluent import AgentToken, TokenRegistry


class TestAgentToken:
    def test_default_armed(self):
        token = AgentToken("writer")
        assert token.is_cancelled is False
        assert token.agent_name == "writer"
        assert token.resume_cursor == 0

    def test_cancel_sets_state(self):
        token = AgentToken("writer")
        token.cancel()
        assert token.is_cancelled is True

    def test_cancel_with_cursor_records_resume(self):
        token = AgentToken("writer")
        token.cancel_with_cursor(42)
        assert token.is_cancelled is True
        assert token.resume_cursor == 42

    def test_reset_clears_state(self):
        token = AgentToken("writer")
        token.cancel_with_cursor(10)
        token.reset()
        assert token.is_cancelled is False

    def test_repr(self):
        token = AgentToken("writer")
        assert "writer" in repr(token)
        assert "armed" in repr(token)
        token.cancel()
        assert "cancelled" in repr(token)


class TestTokenRegistry:
    def test_get_or_create_is_idempotent(self):
        reg = TokenRegistry()
        a = reg.get_or_create("writer")
        b = reg.get_or_create("writer")
        assert a is b

    def test_get_returns_none_for_unknown(self):
        reg = TokenRegistry()
        assert reg.get("nobody") is None

    def test_cancel_returns_false_for_unknown(self):
        reg = TokenRegistry()
        assert reg.cancel("nobody") is False

    def test_cancel_applies_cursor(self):
        reg = TokenRegistry()
        token = reg.get_or_create("writer")
        assert reg.cancel("writer", resume_cursor=17) is True
        assert token.is_cancelled is True
        assert token.resume_cursor == 17

    def test_cancel_is_targeted(self):
        reg = TokenRegistry()
        writer = reg.get_or_create("writer")
        critic = reg.get_or_create("critic")
        reg.cancel("writer")
        assert writer.is_cancelled is True
        assert critic.is_cancelled is False

    def test_reset_one(self):
        reg = TokenRegistry()
        token = reg.get_or_create("w")
        reg.cancel("w")
        reg.reset("w")
        assert token.is_cancelled is False

    def test_reset_all(self):
        reg = TokenRegistry()
        a = reg.get_or_create("a")
        b = reg.get_or_create("b")
        reg.cancel("a")
        reg.cancel("b")
        reg.reset_all()
        assert a.is_cancelled is False
        assert b.is_cancelled is False

    def test_contains_and_len(self):
        reg = TokenRegistry()
        assert "writer" not in reg
        assert len(reg) == 0
        reg.get_or_create("writer")
        assert "writer" in reg
        assert len(reg) == 1

    def test_names_snapshot(self):
        reg = TokenRegistry()
        reg.get_or_create("a")
        reg.get_or_create("b")
        assert set(reg.names()) == {"a", "b"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
