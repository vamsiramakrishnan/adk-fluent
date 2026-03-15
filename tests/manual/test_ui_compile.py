"""Tests for UI surface compilation: compile_surface, flatten_tree, ID generation."""

from adk_fluent._ui import UI, UIBinding, UICheck, UISurface, compile_surface


class TestCompileSurface:
    """compile_surface → flat A2UI JSON messages."""

    def test_basic_surface(self):
        s = UI.surface("test", UI.text("Hello"))
        msgs = compile_surface(s)
        assert len(msgs) == 2  # createSurface + updateComponents

    def test_create_surface_message(self):
        s = UI.surface("test", UI.text("Hello"))
        msgs = compile_surface(s)
        create = msgs[0]
        assert "createSurface" in create
        assert create["createSurface"]["surfaceId"] == "test"

    def test_update_components_message(self):
        s = UI.surface("test", UI.text("Hello"))
        msgs = compile_surface(s)
        update = msgs[1]
        assert "updateComponents" in update
        components = update["updateComponents"]["components"]
        assert len(components) >= 1

    def test_nested_components_flatten(self):
        root = UI.text("a") >> UI.text("b")  # Column with 2 children
        s = UI.surface("test", root)
        msgs = compile_surface(s)
        components = msgs[1]["updateComponents"]["components"]
        # Should have Column + 2 Text = 3 components
        assert len(components) == 3

    def test_component_ids_are_stable(self):
        s = UI.surface("test", UI.text("Hello"))
        msgs1 = compile_surface(s)
        msgs2 = compile_surface(s)
        ids1 = [c["id"] for c in msgs1[1]["updateComponents"]["components"]]
        ids2 = [c["id"] for c in msgs2[1]["updateComponents"]["components"]]
        assert ids1 == ids2

    def test_component_ids_are_unique(self):
        root = UI.text("a") >> UI.text("b") >> UI.text("c")
        s = UI.surface("test", root)
        msgs = compile_surface(s)
        ids = [c["id"] for c in msgs[1]["updateComponents"]["components"]]
        assert len(ids) == len(set(ids))

    def test_parent_references_children(self):
        root = UI.text("a") | UI.text("b")  # Row
        s = UI.surface("test", root)
        msgs = compile_surface(s)
        components = msgs[1]["updateComponents"]["components"]
        # Find the Row component
        row = [c for c in components if c["component"] == "Row"][0]
        assert "children" in row
        assert len(row["children"]) == 2

    def test_text_component_props(self):
        s = UI.surface("test", UI.text("Hello", variant="h1"))
        msgs = compile_surface(s)
        components = msgs[1]["updateComponents"]["components"]
        text_comp = [c for c in components if c["component"] == "Text"][0]
        assert text_comp["text"] == "Hello"
        assert text_comp["variant"] == "h1"

    def test_empty_surface(self):
        s = UI.surface("test")
        msgs = compile_surface(s)
        assert len(msgs) == 1  # Only createSurface, no updateComponents

    def test_surface_with_catalog(self):
        s = UI.surface("test", UI.text("Hi"))
        msgs = compile_surface(s)
        create = msgs[0]["createSurface"]
        assert "catalogId" in create

    def test_deep_nesting(self):
        inner_row = UI.text("a") | UI.text("b")
        outer_col = inner_row >> UI.text("c")
        s = UI.surface("test", outer_col)
        msgs = compile_surface(s)
        components = msgs[1]["updateComponents"]["components"]
        # Column(Row(a,b), c) = Column + Row + 2 Text + Text = 5
        assert len(components) == 5

    def test_surface_with_theme(self):
        s = UI.surface("test", UI.text("Hi")).with_theme(primaryColor="#ff0000")
        msgs = compile_surface(s)
        create = msgs[0]["createSurface"]
        assert "theme" in create
        assert create["theme"]["primaryColor"] == "#ff0000"

    def test_surface_with_data(self):
        s = UI.surface("test", UI.text("Hi")).with_data(count=0, name="")
        msgs = compile_surface(s)
        # createSurface + updateComponents + one updateDataModel per key
        assert len(msgs) == 4
        data_msgs = [m for m in msgs if "updateDataModel" in m]
        assert len(data_msgs) == 2
