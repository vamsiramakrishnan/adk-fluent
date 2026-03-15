"""Tests for UI presets: form, dashboard, wizard, confirm, table."""

from adk_fluent._ui import UI, UISurface


class TestFormPreset:
    """UI.form() preset."""

    def test_form_returns_surface(self):
        s = UI.form("Contact", fields={"name": "text", "email": "email"})
        assert isinstance(s, UISurface)

    def test_form_name(self):
        s = UI.form("Contact", fields={"name": "text"})
        # Presets lowercase the surface name
        assert s.name == "contact"

    def test_form_has_root(self):
        s = UI.form("Contact", fields={"name": "text"})
        assert s.root is not None

    def test_form_custom_submit(self):
        s = UI.form("Contact", fields={"name": "text"}, submit="Send")
        assert s.root is not None


class TestDashboardPreset:
    """UI.dashboard() preset."""

    def test_dashboard_returns_surface(self):
        s = UI.dashboard("Metrics", cards=[{"title": "Users", "bind": "/users"}])
        assert isinstance(s, UISurface)

    def test_dashboard_name(self):
        s = UI.dashboard("Metrics", cards=[{"title": "Users", "bind": "/users"}])
        assert s.name == "metrics"

    def test_dashboard_multiple_cards(self):
        s = UI.dashboard(
            "Stats",
            cards=[
                {"title": "Users", "bind": "/users"},
                {"title": "Revenue", "bind": "/revenue"},
            ],
        )
        assert s.root is not None


class TestWizardPreset:
    """UI.wizard() preset."""

    def test_wizard_returns_surface(self):
        s = UI.wizard(
            "Onboarding",
            steps=[
                ("Welcome", UI.text("Welcome!")),
                ("Profile", UI.text_field("Name")),
            ],
        )
        assert isinstance(s, UISurface)

    def test_wizard_name(self):
        s = UI.wizard("Setup", steps=[("Step 1", UI.text("Hi"))])
        assert s.name == "setup"


class TestConfirmPreset:
    """UI.confirm() preset."""

    def test_confirm_returns_surface(self):
        s = UI.confirm("Delete this?")
        assert isinstance(s, UISurface)

    def test_confirm_custom_labels(self):
        s = UI.confirm("Delete?", yes="Delete", no="Cancel")
        assert s.root is not None


class TestTablePreset:
    """UI.table() preset."""

    def test_table_returns_surface(self):
        s = UI.table(["Name", "Email"], data_bind="/users")
        assert isinstance(s, UISurface)

    def test_table_columns(self):
        s = UI.table(["Name", "Email", "Role"], data_bind="/users")
        assert s.root is not None
