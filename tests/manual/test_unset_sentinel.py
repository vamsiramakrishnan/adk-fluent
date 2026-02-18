"""Tests for _UNSET sentinel handling."""
from adk_fluent._base import _UNSET


def test_unset_is_falsy():
    """_UNSET should be falsy for convenience."""
    assert not _UNSET


def test_unset_repr():
    """_UNSET should have a clear repr."""
    assert repr(_UNSET) == "_UNSET"


def test_unset_excluded_from_build_config():
    """_UNSET values should not appear in build config."""
    from adk_fluent import Agent
    a = Agent("test")
    a._config["model"] = _UNSET
    config = a._prepare_build_config()
    assert "model" not in config


def test_none_included_in_build_config():
    """None values should still appear in build config (they have meaning in ADK)."""
    from adk_fluent import Agent
    a = Agent("test")
    a._config["generate_content_config"] = None
    config = a._prepare_build_config()
    assert "generate_content_config" in config
    assert config["generate_content_config"] is None
