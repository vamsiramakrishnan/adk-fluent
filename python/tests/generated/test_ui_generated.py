"""
AUTO-GENERATED tests for UI namespace factories.
Regenerate with: just a2ui-generate
"""

from __future__ import annotations

from adk_fluent._ui import UI, UIBinding, UICheck, UIComponent, UISurface

# === Component factory tests ===


def test_ui_text_creates_component():
    c = UI.text(text="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "Text"


def test_ui_image_creates_component():
    c = UI.image(url="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "Image"


def test_ui_icon_creates_component():
    c = UI.icon(name="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "Icon"


def test_ui_video_creates_component():
    c = UI.video(url="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "Video"


def test_ui_audio_creates_component():
    c = UI.audio(url="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "AudioPlayer"


def test_ui_row_creates_component():
    c = UI.row(UI.text("child"))
    assert isinstance(c, UIComponent)
    assert c._kind == "Row"


def test_ui_column_creates_component():
    c = UI.column(UI.text("child"))
    assert isinstance(c, UIComponent)
    assert c._kind == "Column"


def test_ui_list__creates_component():
    c = UI.list_(UI.text("child"))
    assert isinstance(c, UIComponent)
    assert c._kind == "List"


def test_ui_card_creates_component():
    c = UI.card()
    assert isinstance(c, UIComponent)
    assert c._kind == "Card"


def test_ui_tabs_creates_component():
    c = UI.tabs()
    assert isinstance(c, UIComponent)
    assert c._kind == "Tabs"


def test_ui_modal_creates_component():
    c = UI.modal()
    assert isinstance(c, UIComponent)
    assert c._kind == "Modal"


def test_ui_divider_creates_component():
    c = UI.divider()
    assert isinstance(c, UIComponent)
    assert c._kind == "Divider"


def test_ui_button_creates_component():
    c = UI.button()
    assert isinstance(c, UIComponent)
    assert c._kind == "Button"


def test_ui_button_with_checks():
    c = UI.button(checks=[UI.required()])
    assert len(c._checks) == 1
    assert c._checks[0].fn == "required"


def test_ui_text_field_creates_component():
    c = UI.text_field(label="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "TextField"


def test_ui_text_field_with_bind():
    c = UI.text_field(label="test", bind="/test/path")
    assert len(c._bindings) == 1
    assert c._bindings[0].path == "/test/path"


def test_ui_text_field_with_checks():
    c = UI.text_field(label="test", checks=[UI.required()])
    assert len(c._checks) == 1
    assert c._checks[0].fn == "required"


def test_ui_checkbox_creates_component():
    c = UI.checkbox(label="test", value="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "CheckBox"


def test_ui_checkbox_with_bind():
    c = UI.checkbox(label="test", value="test", bind="/test/path")
    assert len(c._bindings) == 1
    assert c._bindings[0].path == "/test/path"


def test_ui_checkbox_with_checks():
    c = UI.checkbox(label="test", value="test", checks=[UI.required()])
    assert len(c._checks) == 1
    assert c._checks[0].fn == "required"


def test_ui_choice_creates_component():
    c = UI.choice(options="test", value="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "ChoicePicker"


def test_ui_choice_with_bind():
    c = UI.choice(options="test", value="test", bind="/test/path")
    assert len(c._bindings) == 1
    assert c._bindings[0].path == "/test/path"


def test_ui_choice_with_checks():
    c = UI.choice(options="test", value="test", checks=[UI.required()])
    assert len(c._checks) == 1
    assert c._checks[0].fn == "required"


def test_ui_slider_creates_component():
    c = UI.slider(max=0, value="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "Slider"


def test_ui_slider_with_bind():
    c = UI.slider(max=0, value="test", bind="/test/path")
    assert len(c._bindings) == 1
    assert c._bindings[0].path == "/test/path"


def test_ui_slider_with_checks():
    c = UI.slider(max=0, value="test", checks=[UI.required()])
    assert len(c._checks) == 1
    assert c._checks[0].fn == "required"


def test_ui_date_time_creates_component():
    c = UI.date_time(value="test")
    assert isinstance(c, UIComponent)
    assert c._kind == "DateTimeInput"


def test_ui_date_time_with_bind():
    c = UI.date_time(value="test", bind="/test/path")
    assert len(c._bindings) == 1
    assert c._bindings[0].path == "/test/path"


def test_ui_date_time_with_checks():
    c = UI.date_time(value="test", checks=[UI.required()])
    assert len(c._checks) == 1
    assert c._checks[0].fn == "required"


# === Function factory tests ===


def test_ui_required_check():
    c = UI.required()
    assert isinstance(c, UICheck)
    assert c.fn == "required"


def test_ui_regex_check():
    c = UI.regex(pattern="test")
    assert isinstance(c, UICheck)
    assert c.fn == "regex"


def test_ui_length_check():
    c = UI.length()
    assert isinstance(c, UICheck)
    assert c.fn == "length"


def test_ui_numeric_check():
    c = UI.numeric()
    assert isinstance(c, UICheck)
    assert c.fn == "numeric"


def test_ui_email_check():
    c = UI.email()
    assert isinstance(c, UICheck)
    assert c.fn == "email"


def test_ui_heading_alias():
    c = UI.heading("test")
    assert c._kind == "Text"
    assert dict(c._props).get("variant") == "h1"


def test_ui_h1_alias():
    c = UI.h1("test")
    assert c._kind == "Text"
    assert dict(c._props).get("variant") == "h1"


def test_ui_h2_alias():
    c = UI.h2("test")
    assert c._kind == "Text"
    assert dict(c._props).get("variant") == "h2"


def test_ui_h3_alias():
    c = UI.h3("test")
    assert c._kind == "Text"
    assert dict(c._props).get("variant") == "h3"


def test_ui_h4_alias():
    c = UI.h4("test")
    assert c._kind == "Text"
    assert dict(c._props).get("variant") == "h4"


def test_ui_h5_alias():
    c = UI.h5("test")
    assert c._kind == "Text"
    assert dict(c._props).get("variant") == "h5"


def test_ui_caption_alias():
    c = UI.caption("test")
    assert c._kind == "Text"
    assert dict(c._props).get("variant") == "caption"


def test_ui_paragraph_alias():
    c = UI.paragraph("test")
    assert c._kind == "Text"
    assert dict(c._props).get("variant") == "body"


# === Surface and preset tests ===


def test_ui_surface_creates_surface():
    s = UI.surface("test")
    assert isinstance(s, UISurface)
    assert s.name == "test"


def test_ui_bind_creates_binding():
    b = UI.bind("/user/name")
    assert isinstance(b, UIBinding)
    assert b.path == "/user/name"


def test_ui_form_preset():
    s = UI.form("Contact", fields={"name": "text", "email": "email"})
    assert isinstance(s, UISurface)
    assert s.root is not None
    assert s.name == "contact"


def test_ui_dashboard_preset():
    s = UI.dashboard("Metrics", cards=[{"title": "Users", "bind": "/users"}])
    assert isinstance(s, UISurface)
    assert s.root is not None


def test_ui_confirm_preset():
    s = UI.confirm("Are you sure?")
    assert isinstance(s, UISurface)
    assert s.root is not None


def test_surface_compile():
    s = UI.surface("test", UI.text("Hello"))
    msgs = s.compile()
    assert len(msgs) >= 2
    assert "createSurface" in msgs[0]
    assert "updateComponents" in msgs[1]


def test_component_operators():
    a = UI.text("A")
    b = UI.text("B")
    row = a | b
    assert row._kind == "Row"
    col = a >> b
    assert col._kind == "Column"
