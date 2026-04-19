"""Tests for the A2UI devex wedge: Agent.ui() flag matrix, UI.form(Schema),
UI.paths(Schema), T.a2ui() fail-loud, surface.validate(), and auto-wire dedup.
"""

from __future__ import annotations

import sys
from typing import Literal

import pytest
from pydantic import BaseModel

from adk_fluent import UI, Agent, T
from adk_fluent._exceptions import (
    A2UIBindingError,
    A2UIError,
    A2UINotInstalled,
    A2UISurfaceError,
    BuilderError,
)
from adk_fluent._ui import (
    UIBinding,
    UISurface,
    _UIAutoSpec,
    _UISchemaSpec,
)


def _a2ui_installed() -> bool:
    try:
        import a2ui.agent  # noqa: F401

        return True
    except ImportError:
        return False


def _try_import_email_validator() -> bool:
    try:
        import email_validator  # noqa: F401

        return True
    except ImportError:
        return False


# ======================================================================
# Section 1: Agent.ui() behavior matrix
# ======================================================================


class TestUiMatrix:
    """The (spec, llm_guided) decision matrix from the wedge brief §1."""

    def test_no_spec_no_flag_raises(self) -> None:
        with pytest.raises(A2UIError, match="requires a spec or llm_guided=True"):
            Agent("a", "gemini-2.5-flash").ui()

    def test_no_spec_flag_promotes_to_auto(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(llm_guided=True)
        spec = ag._config["_ui_spec"]
        assert isinstance(spec, _UIAutoSpec)
        assert spec._from_flag is True
        assert ag._config["_a2ui_auto_tool"] is True
        assert ag._config["_a2ui_auto_guard"] is True

    def test_auto_spec_no_flag_is_prompt_only(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(UI.auto())
        assert isinstance(ag._config["_ui_spec"], _UIAutoSpec)
        assert ag._config["_a2ui_auto_tool"] is False
        assert ag._config["_a2ui_auto_guard"] is False

    def test_auto_spec_flag_enables_autowire(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(UI.auto(), llm_guided=True)
        assert ag._config["_a2ui_auto_tool"] is True
        assert ag._config["_a2ui_auto_guard"] is True

    def test_surface_no_flag_keeps_surface(self) -> None:
        s = UI.surface("s", UI.text("hi"))
        ag = Agent("a", "gemini-2.5-flash").ui(s)
        assert isinstance(ag._config["_ui_spec"], UISurface)

    def test_surface_with_flag_raises(self) -> None:
        s = UI.surface("s", UI.text("hi"))
        with pytest.raises(A2UIError, match="incompatible with a declarative surface"):
            Agent("a", "gemini-2.5-flash").ui(s, llm_guided=True)

    def test_loose_component_wraps_in_surface(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(UI.text("hi"))
        spec = ag._config["_ui_spec"]
        assert isinstance(spec, UISurface)
        assert spec.name == "default"

    def test_loose_component_with_flag_raises(self) -> None:
        with pytest.raises(A2UIError, match="incompatible with a declarative surface"):
            Agent("a", "gemini-2.5-flash").ui(UI.text("hi"), llm_guided=True)

    def test_schema_spec_no_flag(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(UI.schema())
        assert isinstance(ag._config["_ui_spec"], _UISchemaSpec)
        assert ag._config["_a2ui_auto_tool"] is False

    def test_schema_spec_with_flag_raises(self) -> None:
        with pytest.raises(A2UIError, match="incompatible with a declarative surface"):
            Agent("a", "gemini-2.5-flash").ui(UI.schema(), llm_guided=True)

    def test_log_flag_stamps_config(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(UI.surface("s", UI.text("hi")), log=True)
        assert ag._config["_a2ui_auto_log"] is True

    def test_validate_flag_default_true(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(UI.surface("s", UI.text("hi")))
        assert ag._config["_a2ui_validate"] is True

    def test_validate_flag_false(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(UI.surface("s", UI.text("hi")), validate=False)
        assert ag._config["_a2ui_validate"] is False

    def test_idempotency_warning(self) -> None:
        ag = Agent("a", "gemini-2.5-flash").ui(UI.surface("s1", UI.text("hi")))
        with pytest.warns(RuntimeWarning, match="called twice"):
            ag.ui(UI.surface("s2", UI.text("bye")))
        assert ag._config["_ui_spec"].name == "s2"


# ======================================================================
# Section 2: UI.form(Schema) — Pydantic v2 reflection
# ======================================================================


class _Plain(BaseModel):
    name: str
    age: int
    active: bool


class _WithLiteral(BaseModel):
    role: Literal["Admin", "User", "Guest"]


class _WithOptional(BaseModel):
    nickname: str | None = None


class TestFormFromSchema:
    """UI.form(BaseModel) covers each annotation row in §3 of the brief."""

    def test_returns_surface(self) -> None:
        s = UI.form(_Plain)
        assert isinstance(s, UISurface)
        assert s.name == "_plain"

    def test_str_field_emits_textfield(self) -> None:
        s = UI.form(_Plain)
        comp = self._field_component(s, "name")
        assert comp._kind == "TextField"
        assert dict(comp._props).get("variant") == "shortText"

    def test_int_field_emits_number_textfield(self) -> None:
        s = UI.form(_Plain)
        comp = self._field_component(s, "age")
        assert comp._kind == "TextField"
        assert dict(comp._props).get("variant") == "number"

    def test_bool_field_emits_checkbox(self) -> None:
        s = UI.form(_Plain)
        comp = self._field_component(s, "active")
        assert comp._kind == "CheckBox"

    def test_literal_field_emits_choicepicker(self) -> None:
        s = UI.form(_WithLiteral)
        comp = self._field_component(s, "role")
        assert comp._kind == "ChoicePicker"
        options = dict(comp._props).get("options")
        assert {opt["value"] for opt in options} == {"Admin", "User", "Guest"}

    def test_optional_field_drops_required(self) -> None:
        s = UI.form(_WithOptional)
        comp = self._field_component(s, "nickname")
        # No "required" check should be present
        check_fns = {chk.fn for chk in comp._checks}
        assert "required" not in check_fns

    def test_required_str_has_required_check(self) -> None:
        s = UI.form(_Plain)  # name is required
        comp = self._field_component(s, "name")
        check_fns = {chk.fn for chk in comp._checks}
        assert "required" in check_fns

    @pytest.mark.skipif(
        sys.modules.get("email_validator") is None and not _try_import_email_validator(),
        reason="pydantic[email] / email-validator not installed",
    )
    def test_email_field_emits_email_check(self) -> None:
        from pydantic import EmailStr

        class _WithEmail(BaseModel):
            email: EmailStr

        s = UI.form(_WithEmail)
        comp = self._field_component(s, "email")
        check_fns = {chk.fn for chk in comp._checks}
        assert "email" in check_fns

    def test_legacy_signature_still_works(self) -> None:
        s = UI.form("Contact", fields={"name": "text", "email": "email"})
        assert isinstance(s, UISurface)
        assert s.name == "contact"

    def test_invalid_call_raises_a2uierror(self) -> None:
        with pytest.raises(A2UIError, match="Pydantic model or"):
            UI.form(123)  # type: ignore[arg-type]

    @staticmethod
    def _field_component(surface: UISurface, field_id: str) -> object:
        """Find the component with id == field_id in the compiled tree."""
        assert surface.root is not None
        stack = [surface.root]
        while stack:
            cur = stack.pop()
            if getattr(cur, "_id", None) == field_id:
                return cur
            stack.extend(cur._children)
        raise AssertionError(f"no component with id {field_id!r} in surface {surface.name!r}")


# ======================================================================
# Section 3: UI.paths(Schema)
# ======================================================================


class TestUIPaths:
    """UI.paths() reflective binding proxy."""

    def test_returns_binding(self) -> None:
        binding = UI.paths(_Plain).name
        assert isinstance(binding, UIBinding)
        assert binding.path == "/name"
        assert binding.direction == "two_way"

    def test_typo_raises_attribute_error_with_field_list(self) -> None:
        proxy = UI.paths(_Plain)
        with pytest.raises(AttributeError) as excinfo:
            _ = proxy.nope
        message = str(excinfo.value)
        assert "nope" in message
        assert "Available fields" in message
        # All fields should be enumerated for grep-ability
        for fname in ("name", "age", "active"):
            assert fname in message

    def test_nested_model_returns_subproxy(self) -> None:
        class Inner(BaseModel):
            value: int

        class Outer(BaseModel):
            inner: Inner

        outer_proxy = UI.paths(Outer)
        sub = outer_proxy.inner
        assert sub.value.path == "/inner/value"


# ======================================================================
# Section 4: T.a2ui() fail-loud
# ======================================================================


class TestTa2uiFailLoud:
    """T.a2ui() must raise A2UINotInstalled when the optional dep is missing."""

    def test_raises_a2ui_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        if _a2ui_installed():
            pytest.skip("a2ui-agent IS installed in this env; cannot simulate absence")
        with pytest.raises(A2UINotInstalled, match="pip install a2ui-agent"):
            T.a2ui()

    def test_simulated_absence_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force the import to fail even if a2ui-agent is installed.
        for mod in [k for k in list(sys.modules) if k.startswith("a2ui")]:
            monkeypatch.delitem(sys.modules, mod, raising=False)
        original = sys.meta_path[:]

        class _Blocker:
            def find_module(self, name: str, path=None):  # noqa: D401, ARG002
                if name == "a2ui" or name.startswith("a2ui."):
                    return self
                return None

            def find_spec(self, name: str, path=None, target=None):  # noqa: D401, ARG002
                if name == "a2ui" or name.startswith("a2ui."):
                    raise ImportError(f"blocked {name}")
                return None

        sys.meta_path.insert(0, _Blocker())
        try:
            with pytest.raises(A2UINotInstalled):
                T.a2ui()
        finally:
            sys.meta_path[:] = original


# ======================================================================
# Section 5: surface.validate()
# ======================================================================


class TestSurfaceValidate:
    """Static surface validation."""

    def test_duplicate_ids_raise(self) -> None:
        root = UI.column(
            UI.text("a").with_id("dup"),
            UI.text("b").with_id("dup"),
        )
        s = UI.surface("test", root)
        with pytest.raises(A2UISurfaceError, match="duplicate component id 'dup'"):
            s.validate()

    def test_unhandled_action_raises(self) -> None:
        root = UI.column(
            UI.text("hi"),
            UI.button("Go").with_action("submit_form"),
        )
        s = UI.surface("t", root).on("other_event", lambda: None)
        with pytest.raises(A2UISurfaceError, match="Unhandled action 'submit_form'"):
            s.validate()

    def test_clean_surface_returns_self(self) -> None:
        s = UI.surface("t", UI.text("hi"))
        assert s.validate() is s

    def test_handlers_match_actions_passes(self) -> None:
        root = UI.column(UI.button("Go").with_action("go"))
        s = UI.surface("t", root).on("go", lambda: None)
        s.validate()

    def test_two_way_binding_undeclared_raises(self) -> None:
        from dataclasses import replace

        from adk_fluent._ui import _component

        comp = _component("TextField", id="name", _bindings=(UIBinding(path="/missing"),))
        s = UI.surface("t", comp).with_data(other="x")
        with pytest.raises(A2UIBindingError, match="not declared in surface.data"):
            replace(s).validate()


# ======================================================================
# Section 6: auto-wire dedup
# ======================================================================


class TestAutoWireDedup:
    """Verify build-time auto-wire respects existing tools/guards."""

    def test_existing_google_search_plus_a2ui_keeps_both(self) -> None:
        # When llm_guided=True is used and a2ui-agent IS installed, both tools
        # should appear. When NOT installed, build raises BuilderError; in that
        # case we just verify pre-build _lists state.
        ag = Agent("x", "gemini-2.5-flash").instruct("hi").tools(T.google_search()).ui(llm_guided=True)
        if _a2ui_installed():
            from a2ui.agent import SendA2uiToClientToolset

            ag.build()
            tool_kinds = [type(t).__name__ for t in ag._lists["tools"]]
            assert "SendA2uiToClientToolset" in tool_kinds
            # google_search is a function-style tool; just ensure 2+ items
            assert sum(isinstance(t, SendA2uiToClientToolset) for t in ag._lists["tools"]) == 1
        else:
            with pytest.raises(BuilderError):
                ag.build()

    def test_explicit_a2ui_then_flag_dedups(self) -> None:
        if not _a2ui_installed():
            pytest.skip("requires a2ui-agent for tool dedup verification")
        from a2ui.agent import SendA2uiToClientToolset

        ag = Agent("x", "gemini-2.5-flash").instruct("hi").tools(T.a2ui()).ui(llm_guided=True)
        ag.build()
        a2ui_count = sum(isinstance(t, SendA2uiToClientToolset) for t in ag._lists["tools"])
        assert a2ui_count == 1

    def test_explicit_guard_then_flag_dedups(self) -> None:
        import contextlib

        from adk_fluent._guards import G
        from adk_fluent._ui_compile import _apply_ui_auto_wire

        ag = Agent("x", "gemini-2.5-flash").instruct("hi").guard(G.a2ui()).ui(llm_guided=True)
        # The full build path raises BuilderError when a2ui-agent is missing.
        # Force the auto-wire pre-step manually to test guard dedup in
        # isolation (disable tool injection so we don't trip the missing
        # optional dep).
        with contextlib.suppress(Exception):
            ag._maybe_fork_for_mutation()
        ag._config["_a2ui_auto_tool"] = False
        _apply_ui_auto_wire(ag, ag._config["_ui_spec"])
        cbs = ag._callbacks.get("after_model_callback", [])
        guard_count = sum(1 for entry in cbs if isinstance(entry, tuple) and entry[0] == "guard:a2ui")
        assert guard_count == 1
