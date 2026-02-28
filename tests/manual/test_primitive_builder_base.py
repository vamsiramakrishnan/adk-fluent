"""Tests for PrimitiveBuilderBase DRY scaffolding."""

from adk_fluent._base import BuilderBase
from adk_fluent._primitive_builders import PrimitiveBuilderBase


class _TestBuilder(PrimitiveBuilderBase):
    """Minimal concrete builder for testing PrimitiveBuilderBase."""

    _CUSTOM_ATTRS = ("_alpha", "_beta", "_items")

    def build(self):
        return {"alpha": self._alpha, "beta": self._beta, "items": self._items}

    def to_ir(self):
        return None


class TestPrimitiveBuilderBase:
    def test_custom_attrs_set_on_init(self):
        b = _TestBuilder("test", _alpha=1, _beta="hello", _items=[1, 2, 3])
        assert b._alpha == 1
        assert b._beta == "hello"
        assert b._items == [1, 2, 3]

    def test_custom_attrs_default_to_none(self):
        b = _TestBuilder("test")
        assert b._alpha is None
        assert b._beta is None
        assert b._items is None

    def test_name_stored_in_config(self):
        b = _TestBuilder("my_builder")
        assert b._config["name"] == "my_builder"

    def test_is_builder_base(self):
        b = _TestBuilder("test")
        assert isinstance(b, BuilderBase)

    def test_fork_copies_custom_attrs(self):
        b = _TestBuilder("test", _alpha=42, _beta="world")
        clone = b._fork_for_operator()
        assert clone._alpha == 42
        assert clone._beta == "world"

    def test_fork_copies_lists(self):
        """List attrs are shallow-copied (not aliased)."""
        items = [1, 2, 3]
        b = _TestBuilder("test", _items=items)
        clone = b._fork_for_operator()
        assert clone._items == [1, 2, 3]
        assert clone._items is not b._items

    def test_fork_non_list_not_copied(self):
        """Non-list attrs are assigned directly (no copy needed)."""
        b = _TestBuilder("test", _alpha=42)
        clone = b._fork_for_operator()
        assert clone._alpha == 42

    def test_build_works(self):
        b = _TestBuilder("test", _alpha=1, _beta="x", _items=[])
        result = b.build()
        assert result == {"alpha": 1, "beta": "x", "items": []}
