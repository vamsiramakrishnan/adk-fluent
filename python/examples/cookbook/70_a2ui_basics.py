"""A2UI Basics: Declarative Agent-to-UI Composition

Demonstrates the UI namespace for building rich agent UIs declaratively.

Key concepts:
  - UIComponent: frozen dataclass with composition operators
  - UI.text(), UI.button(), UI.text_field(): component factories
  - UI.bind(), UI.required(): data binding and validation
  - UI.surface(): named UI surface (compilation root)
  - compile_surface(): nested Python tree → flat A2UI JSON
  - Operators: | (Row), >> (Column), + (sibling group)
"""

from adk_fluent._ui import (
    UI,
    UIBinding,
    UICheck,
    UIComponent,
    UISurface,
    compile_surface,
)

# --- 1. Component creation ---
text = UI.text("Hello, World!")
assert text._kind == "Text"

button = UI.button("Click Me")
assert button._kind == "Button"

field = UI.text_field("Name")
assert field._kind == "TextField"

# --- 2. Composition operators ---

# | creates a Row (horizontal layout)
row = UI.text("Left") | UI.text("Right")
assert row._kind == "Row"
assert len(row._children) == 2

# >> creates a Column (vertical layout)
col = UI.text("Top") >> UI.text("Bottom")
assert col._kind == "Column"
assert len(col._children) == 2

# Nest them
layout = (UI.text("A") | UI.text("B")) >> UI.text("Footer")
assert layout._kind == "Column"

# --- 3. Data binding ---
binding = UI.bind("/user/name")
assert isinstance(binding, UIBinding)
assert binding.path == "/user/name"

# --- 4. Validation ---
check = UI.required("Name is required")
assert isinstance(check, UICheck)
assert check.fn == "required"

email_check = UI.email("Invalid email")
assert email_check.fn == "email"

# --- 5. Surfaces ---
surface = UI.surface("contact_form", UI.text("Contact Us") >> UI.text_field("Name"))
assert isinstance(surface, UISurface)
assert surface.name == "contact_form"

# Surface with theme
themed = surface.with_theme(primaryColor="#3b82f6")
assert len(themed.theme) == 1

# Surface with initial data
with_data = surface.with_data(name="")
assert len(with_data.data) == 1

# --- 6. Compilation ---
msgs = compile_surface(surface)
assert len(msgs) == 2  # createSurface + updateComponents

create_msg = msgs[0]
assert "createSurface" in create_msg
assert create_msg["createSurface"]["surfaceId"] == "contact_form"

update_msg = msgs[1]
assert "updateComponents" in update_msg
components = update_msg["updateComponents"]["components"]
assert len(components) >= 2  # Column + TextField (+ Text)

# --- 7. Generic component (escape hatch) ---
custom = UI.component("BarChart", data="test", x="date", y="value")
assert custom._kind == "BarChart"

# --- 8. Presets ---
form = UI.form("Feedback", fields={"name": "text", "email": "email", "message": "longText"})
assert isinstance(form, UISurface)

dashboard = UI.dashboard("Metrics", cards=[{"title": "Users", "bind": "/users"}])
assert isinstance(dashboard, UISurface)

confirm = UI.confirm("Delete this item?")
assert isinstance(confirm, UISurface)

table = UI.table(["Name", "Email"], data_bind="/users")
assert isinstance(table, UISurface)

wizard = UI.wizard("Setup", steps=[("Welcome", UI.text("Hi")), ("Done", UI.text("Bye"))])
assert isinstance(wizard, UISurface)

print("All A2UI basics assertions passed!")
