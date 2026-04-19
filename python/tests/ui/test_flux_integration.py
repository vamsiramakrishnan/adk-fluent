"""W4 — Fluent integration tests for the flux catalog.

Covers:
  - ``UI.theme("flux-dark")`` attaches a theme id to the surface.
  - ``UI.with_catalog("flux")`` flips factory dispatch and restores on exit.
  - The default catalog is ``"basic"`` (pre-existing behaviour).
  - Unknown catalogs raise ``ValueError``.
  - Nested catalog scopes stack.
  - ``T.a2ui(catalog="flux")`` produces a toolset whose description and
    metadata expose the flux component surface.
  - Every ``flux_*`` factory in ``_flux_gen`` emits a dict whose
    ``component`` key matches the spec name.
"""

from __future__ import annotations

import pytest

from adk_fluent import UI, T
from adk_fluent._ui import KNOWN_CATALOGS, _active_catalog

# ---------------------------------------------------------------------------
# UI.theme
# ---------------------------------------------------------------------------


class TestTheme:
    def test_theme_attaches_to_surface(self):
        """Theme id lives at ``surface.theme`` → ``createSurface.theme.name``."""
        surface = UI.surface(
            "flux_demo",
            UI.theme("flux-dark"),
            UI.column(UI.text("hi")),
        )
        # theme tuple carries ("name", "flux-dark")
        assert ("name", "flux-dark") in surface.theme

        # Compiled output: createSurface.theme = {"name": "flux-dark"}
        msgs = surface.compile()
        create = msgs[0]["createSurface"]
        assert create["theme"] == {"name": "flux-dark"}

    def test_theme_marker_can_precede_or_follow_root(self):
        a = UI.surface("a", UI.theme("flux-light"), UI.text("x"))
        b = UI.surface("b", UI.text("x"), UI.theme("flux-light"))
        assert a.theme == b.theme == (("name", "flux-light"),)

    def test_surface_without_theme_has_empty_theme_tuple(self):
        s = UI.surface("no-theme", UI.text("hi"))
        assert s.theme == ()


# ---------------------------------------------------------------------------
# Catalog dispatch
# ---------------------------------------------------------------------------


class TestCatalogDispatch:
    def test_default_catalog_is_basic(self):
        """Without ``with_catalog`` ``UI.button`` emits a basic ``Button``."""
        assert _active_catalog() == "basic"
        comp = UI.button("Go", action="go")
        assert comp._kind == "Button"

    def test_with_catalog_flux_emits_flux_button(self):
        with UI.with_catalog("flux"):
            comp = UI.button("Go", tone="primary", action="go")
        assert comp._kind == "FluxButton"
        props = dict(comp._props)
        assert props["tone"] == "primary"
        assert props["label"] == "Go"
        assert props["action"] == {"event": "go"}

    def test_with_catalog_restores_on_exit(self):
        with UI.with_catalog("flux"):
            assert _active_catalog() == "flux"
        assert _active_catalog() == "basic"
        assert UI.button("Hi", action="hi")._kind == "Button"

    def test_unknown_catalog_raises(self):
        with pytest.raises(ValueError) as exc:
            UI.with_catalog("nope")
        # Error message lists known catalogs so users can fix the typo.
        assert "nope" in str(exc.value)
        for known in KNOWN_CATALOGS:
            assert known in str(exc.value)

    def test_nested_catalogs_stack(self):
        with UI.with_catalog("flux"):
            outer = UI.button("outer", action="a")
            with UI.with_catalog("flux"):
                inner = UI.button("inner", action="b")
            # Exiting inner keeps us in flux.
            still = UI.button("still", action="c")
        assert outer._kind == inner._kind == still._kind == "FluxButton"
        assert _active_catalog() == "basic"

    def test_nested_mixed_catalogs(self):
        with UI.with_catalog("flux"):
            assert _active_catalog() == "flux"
            with UI.with_catalog("basic"):
                assert _active_catalog() == "basic"
                assert UI.button("x", action="x")._kind == "Button"
            assert _active_catalog() == "flux"

    def test_flux_overloads_for_each_component(self):
        """Every overloaded factory emits its flux equivalent inside the scope."""
        with UI.with_catalog("flux"):
            assert UI.button("b", action="go")._kind == "FluxButton"
            assert UI.text_field("Email")._kind == "FluxTextField"
            assert UI.badge("new")._kind == "FluxBadge"
            assert UI.progress(value=50)._kind == "FluxProgress"
            assert UI.skeleton()._kind == "FluxSkeleton"
            assert UI.markdown("# hi")._kind == "FluxMarkdown"
            assert UI.link("docs", href="https://x")._kind == "FluxLink"
            assert UI.banner(title="heads up", message="note")._kind == "FluxBanner"
            assert UI.card(body="body text")._kind == "FluxCard"
            assert UI.stack()._kind == "FluxStack"


# ---------------------------------------------------------------------------
# T.a2ui(catalog="flux")
# ---------------------------------------------------------------------------


class TestTAAtUIFlux:
    def test_t_a2ui_flux_toolset(self):
        """``T.a2ui(catalog="flux")`` exposes ≥3 flux components in its metadata."""
        comp = T.a2ui(catalog="flux")
        items = comp._items
        assert len(items) == 1
        toolset = items[0]
        # Description enumerates the flux component surface.
        desc = toolset.description
        assert "FluxButton" in desc
        # At least three flux components should be advertised.
        flux_names = [n for n in toolset.components if n.startswith("Flux")]
        assert len(flux_names) >= 3
        # llm metadata is attached.
        assert "FluxButton" in toolset.llm_metadata

    def test_t_a2ui_unknown_catalog_raises(self):
        with pytest.raises(ValueError):
            T.a2ui(catalog="nope")


# ---------------------------------------------------------------------------
# flux factory signatures
# ---------------------------------------------------------------------------


class TestFluxFactorySignatures:
    """Call every ``flux_*`` function in ``_flux_gen`` with minimal args and
    assert the dict's ``component`` key matches the expected spec name."""

    MINIMAL_ARGS: dict[str, dict] = {
        "flux_badge": {
            "id": "b1",
            "label": "new",
            "tone": "neutral",
            "variant": "subtle",
            "size": "sm",
        },
        "flux_banner": {
            "id": "ban1",
            "title": "heads up",
            "message": "something changed",
            "tone": "info",
        },
        "flux_button": {
            "id": "btn1",
            "tone": "primary",
            "size": "md",
            "emphasis": "solid",
            "action": {"event": "go"},
            "accessibility": {"label": "Go"},
        },
        "flux_card": {
            "id": "c1",
            "emphasis": "subtle",
            "padding": "md",
            "body": "hi",
        },
        "flux_link": {
            "id": "l1",
            "label": "docs",
            "tone": "default",
            "underline": "hover",
            "href": "https://example.com",
        },
        "flux_markdown": {
            "id": "m1",
            "source": "# hi",
            "size": "md",
            "proseStyle": "default",
        },
        "flux_progress": {
            "id": "p1",
            "value": 50.0,
            "determinate": True,
            "tone": "default",
            "size": "md",
            "accessibility": {"label": "loading"},
        },
        "flux_skeleton": {
            "id": "s1",
            "shape": "text",
            "size": "md",
        },
        "flux_stack": {
            "id": "st1",
            "direction": "vertical",
            "gap": "2",
            "align": "stretch",
            "justify": "start",
        },
        "flux_text_field": {
            "id": "t1",
            "type": "text",
            "size": "md",
            "state": "default",
            "accessibility": {"label": "Name"},
        },
    }

    def test_flux_factory_signatures_match_spec(self):
        from adk_fluent import _flux_gen

        factory_names = [
            name for name in dir(_flux_gen) if name.startswith("flux_") and callable(getattr(_flux_gen, name))
        ]
        assert factory_names, "no flux_* factories found in _flux_gen"
        for name in factory_names:
            args = self.MINIMAL_ARGS.get(name)
            assert args is not None, f"missing MINIMAL_ARGS for {name}"
            fn = getattr(_flux_gen, name)
            node = fn(**args)
            expected = "Flux" + "".join(part.title() for part in name[len("flux_") :].split("_"))
            assert node["component"] == expected, f"{name} emitted {node['component']!r}, expected {expected!r}"
            assert node["id"] == args["id"]
