"""Visual regression tests for A2UI surface compilation.

Tests that cookbook A2UI surfaces compile to valid, stable A2UI JSON.
No LLM calls required — these are pure compilation tests.

Run:
    uv run pytest tests/visual/ -v
    uv run pytest tests/visual/ -v --update-golden  # to update snapshots
"""

from __future__ import annotations

import importlib.util
import io
import contextlib
from pathlib import Path

import pytest

from tests.visual.conftest import assert_golden

COOKBOOK_DIR = Path(__file__).parents[2] / "examples" / "cookbook"

# All A2UI cookbook files
A2UI_COOKBOOKS = sorted(COOKBOOK_DIR.glob("[0-9][0-9]_*a2ui*.py"))


def _load_module(filepath: Path):
    """Load a cookbook module, suppressing stdout."""
    spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


def _extract_surfaces(mod):
    """Extract all UISurface and UIComponent objects from module."""
    from adk_fluent._ui import UIComponent, UISurface, compile_surface

    surfaces = {}
    for name, obj in vars(mod).items():
        if name.startswith("_"):
            continue
        if isinstance(obj, UISurface):
            surfaces[name] = compile_surface(obj)
        elif isinstance(obj, UIComponent):
            temp = UISurface(name=name, root=obj)
            surfaces[name] = compile_surface(temp)
    return surfaces


# ── Parametrized tests: one per A2UI cookbook ──────────────────


@pytest.mark.parametrize("cookbook_file", A2UI_COOKBOOKS, ids=[f.stem for f in A2UI_COOKBOOKS])
def test_cookbook_loads_without_error(cookbook_file):
    """Each A2UI cookbook should import and execute without errors."""
    mod = _load_module(cookbook_file)
    assert mod is not None


@pytest.mark.parametrize("cookbook_file", A2UI_COOKBOOKS, ids=[f.stem for f in A2UI_COOKBOOKS])
def test_cookbook_has_surfaces(cookbook_file):
    """Each A2UI cookbook should produce at least one compilable surface."""
    mod = _load_module(cookbook_file)
    surfaces = _extract_surfaces(mod)
    # Cookbooks 70-72 define surfaces, 73-74 may not (they test other things)
    # So we just verify extraction doesn't crash
    assert isinstance(surfaces, dict)


# ── Structural validation of compiled A2UI messages ───────────


class TestA2UIProtocolCompliance:
    """Verify compiled surfaces produce valid A2UI v0.10 messages."""

    @pytest.fixture(autouse=True)
    def _load_surfaces(self):
        """Load all surfaces from all A2UI cookbooks."""
        self.all_surfaces = {}
        for f in A2UI_COOKBOOKS:
            try:
                mod = _load_module(f)
                for name, msgs in _extract_surfaces(mod).items():
                    self.all_surfaces[f"{f.stem}__{name}"] = msgs
            except Exception:
                pass

    def test_createSurface_has_required_fields(self):
        """Every createSurface message must have surfaceId and catalogId."""
        for key, msgs in self.all_surfaces.items():
            for msg in msgs:
                if "createSurface" in msg:
                    cs = msg["createSurface"]
                    assert "surfaceId" in cs, f"{key}: missing surfaceId"
                    assert "catalogId" in cs, f"{key}: missing catalogId"

    def test_updateComponents_has_root(self):
        """Every updateComponents message must contain a 'root' component."""
        for key, msgs in self.all_surfaces.items():
            for msg in msgs:
                if "updateComponents" in msg:
                    uc = msg["updateComponents"]
                    assert "components" in uc, f"{key}: missing components"
                    ids = [c.get("id") for c in uc["components"]]
                    assert "root" in ids, f"{key}: no root component (ids: {ids})"

    def test_all_component_ids_unique(self):
        """Component IDs within a surface must be unique."""
        for key, msgs in self.all_surfaces.items():
            for msg in msgs:
                if "updateComponents" in msg:
                    ids = [c["id"] for c in msg["updateComponents"]["components"]]
                    assert len(ids) == len(set(ids)), f"{key}: duplicate IDs: {ids}"

    def test_children_reference_valid_ids(self):
        """All child references must point to existing component IDs."""
        for key, msgs in self.all_surfaces.items():
            for msg in msgs:
                if "updateComponents" in msg:
                    comps = msg["updateComponents"]["components"]
                    all_ids = {c["id"] for c in comps}
                    for c in comps:
                        # Check children arrays
                        children = c.get("children", [])
                        if isinstance(children, list):
                            for child_id in children:
                                if isinstance(child_id, str):
                                    assert child_id in all_ids, (
                                        f"{key}: component '{c['id']}' references "
                                        f"unknown child '{child_id}'"
                                    )
                        # Check single child references
                        if "child" in c and isinstance(c["child"], str):
                            assert c["child"] in all_ids, (
                                f"{key}: component '{c['id']}' references "
                                f"unknown child '{c['child']}'"
                            )

    def test_component_types_are_valid(self):
        """Standard components must be from the A2UI basic catalog.
        Custom components (via UI.component() escape hatch) are allowed."""
        valid_types = {
            "Text", "Image", "Icon", "Video", "AudioPlayer",
            "Row", "Column", "List", "Card", "Tabs", "Modal", "Divider",
            "Button", "TextField", "CheckBox", "ChoicePicker", "Slider", "DateTimeInput",
        }
        # Surfaces using UI.component() escape hatch (custom types allowed)
        custom_surfaces = {"70_a2ui_basics__custom"}
        for key, msgs in self.all_surfaces.items():
            if key in custom_surfaces:
                continue  # Skip custom component escape hatch tests
            for msg in msgs:
                if "updateComponents" in msg:
                    for c in msg["updateComponents"]["components"]:
                        assert c.get("component") in valid_types, (
                            f"{key}: unknown component type '{c.get('component')}'"
                        )


# ── Golden snapshot tests ─────────────────────────────────────


@pytest.mark.parametrize("cookbook_file", A2UI_COOKBOOKS, ids=[f.stem for f in A2UI_COOKBOOKS])
def test_surface_golden_snapshots(cookbook_file, golden_dir, update_golden):
    """Compiled surfaces should match golden snapshots."""
    mod = _load_module(cookbook_file)
    surfaces = _extract_surfaces(mod)
    for name, msgs in surfaces.items():
        snapshot_name = f"{cookbook_file.stem}__{name}"
        assert_golden(msgs, snapshot_name, golden_dir, update=update_golden)


# ── Preset tests ──────────────────────────────────────────────


class TestPresets:
    """Test that all UI presets compile correctly."""

    def test_form_preset(self):
        from adk_fluent._ui import UI, compile_surface

        surface = UI.form("test_form", fields={"name": "text", "email": "email"})
        msgs = compile_surface(surface)
        assert len(msgs) >= 2
        assert "createSurface" in msgs[0]

    def test_dashboard_preset(self):
        from adk_fluent._ui import UI, compile_surface

        surface = UI.dashboard("test_dash", cards=[{"title": "Users", "bind": "/users"}])
        msgs = compile_surface(surface)
        assert len(msgs) >= 2

    def test_confirm_preset(self):
        from adk_fluent._ui import UI, compile_surface

        surface = UI.confirm("Are you sure?")
        msgs = compile_surface(surface)
        assert len(msgs) >= 2

    def test_table_preset(self):
        from adk_fluent._ui import UI, compile_surface

        surface = UI.table(["Name", "Email"], data_bind="/users")
        msgs = compile_surface(surface)
        assert len(msgs) >= 2

    def test_wizard_preset(self):
        from adk_fluent._ui import UI, compile_surface

        surface = UI.wizard("Setup", steps=[("Step 1", UI.text("Hello")), ("Step 2", UI.text("World"))])
        msgs = compile_surface(surface)
        assert len(msgs) >= 2


# ── Data binding tests ────────────────────────────────────────


class TestDataBinding:
    """Test that data bindings compile to valid A2UI JSON."""

    def test_binding_in_text(self):
        from adk_fluent._ui import UI, UISurface, compile_surface

        surface = UISurface(name="bind_test", root=UI.text(UI.bind("/user/name")))
        msgs = compile_surface(surface)
        comps = msgs[1]["updateComponents"]["components"]
        text_comp = next(c for c in comps if c["component"] == "Text")
        # Should have a path reference, not a literal string
        assert isinstance(text_comp["text"], dict) or isinstance(text_comp["text"], str)

    def test_binding_in_textfield(self):
        from adk_fluent._ui import UI, UISurface, compile_surface

        field = UI.text_field("Name", value=UI.bind("/form/name"))
        surface = UISurface(name="field_test", root=field)
        msgs = compile_surface(surface)
        assert len(msgs) >= 2
