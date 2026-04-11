"""Tests for Preset field validation."""

import pytest

from adk_fluent import Preset


def test_preset_rejects_typo():
    """Preset should reject obviously misspelled fields."""
    with pytest.raises(ValueError, match="modle"):
        Preset(modle="gemini-2.5-flash")


def test_preset_accepts_known_fields():
    """Preset should accept all known config fields."""
    p = Preset(model="gemini-2.5-flash", instruction="Help.")
    assert p._fields["model"] == "gemini-2.5-flash"
    assert p._fields["instruction"] == "Help."


def test_preset_accepts_callbacks():
    """Preset should accept callback-like fields."""
    fn = lambda ctx: None
    p = Preset(before_model_callback=fn)
    assert fn in p._callbacks["before_model_callback"]


def test_preset_suggests_correction():
    """Preset should suggest the closest valid field for typos."""
    with pytest.raises(ValueError, match="model"):
        Preset(modle="gemini-2.5-flash")


def test_preset_accepts_all_callback_aliases():
    """Preset should accept short callback aliases."""
    fn = lambda ctx: None
    for alias in [
        "before_agent",
        "after_agent",
        "before_model",
        "after_model",
        "before_tool",
        "after_tool",
        "on_model_error",
        "on_tool_error",
    ]:
        p = Preset(**{alias: fn})
        assert fn in p._callbacks[alias]


def test_preset_accepts_full_callback_names():
    """Preset should accept full callback field names."""
    fn = lambda ctx: None
    for name in [
        "before_agent_callback",
        "after_agent_callback",
        "before_model_callback",
        "after_model_callback",
        "before_tool_callback",
        "after_tool_callback",
        "on_model_error_callback",
        "on_tool_error_callback",
    ]:
        p = Preset(**{name: fn})
        assert fn in p._callbacks[name]


def test_preset_accepts_other_known_fields():
    """Preset should accept other known ADK fields like output_schema, planner, etc."""
    # These are non-callable, so they go into _fields
    p = Preset(disallow_transfer_to_parent=True)
    assert p._fields["disallow_transfer_to_parent"] is True


def test_preset_error_message_format():
    """Error message should include the unknown field name and a suggestion."""
    with pytest.raises(ValueError, match=r"Unknown Preset field 'modle'.*Did you mean.*model"):
        Preset(modle="gemini-2.5-flash")


def test_preset_rejects_completely_unknown_field():
    """Preset should reject a field that has no close match."""
    with pytest.raises(ValueError, match="Unknown Preset field 'xyz_nonsense'"):
        Preset(xyz_nonsense="value")
