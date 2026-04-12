# A2UI Operators: UI Composition with |, >>, +

Demonstrates declarative UI layout using Python operators.

Key concepts:
  - | operator: horizontal Row layout
  - >> operator: vertical Column layout
  - + operator: sibling group (UIGroup)
  - Nesting: combine operators for complex layouts
  - compile_surface(): nested tree → flat A2UI JSON

:::{tip} What you'll learn
How to use operator syntax for composing agents.
:::

_Source: `72_a2ui_operators.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent._ui import UI, UIComponent, UISurface, compile_surface

# --- 1. Row operator (|) ---
row = UI.text("Left") | UI.text("Right")
assert row._kind == "Row"
assert len(row._children) == 2

# --- 2. Column operator (>>) ---
col = UI.text("Top") >> UI.text("Bottom")
assert col._kind == "Column"
assert len(col._children) == 2

# --- 3. Nested layout ---
# Header row above a footer
layout = (UI.text("Logo") | UI.text("Nav")) >> UI.text("Footer")
assert layout._kind == "Column"

# --- 4. Complex form layout ---
form_layout = (
    UI.text("Sign Up", variant="h1")
    >> (UI.text_field("First Name") | UI.text_field("Last Name"))
    >> UI.text_field("Email")
    >> (UI.button("Submit") | UI.button("Cancel"))
)
assert form_layout._kind == "Column"

# --- 5. Surface compilation ---
surface = UI.surface("signup", form_layout)
assert isinstance(surface, UISurface)

msgs = compile_surface(surface)
assert len(msgs) == 2  # createSurface + updateComponents
assert "createSurface" in msgs[0]
assert "updateComponents" in msgs[1]

# Verify components are flattened
components = msgs[1]["updateComponents"]["components"]
assert len(components) >= 5  # Multiple components from nested tree

# --- 6. Component IDs are stable ---
msgs2 = compile_surface(surface)
ids1 = [c["id"] for c in msgs[1]["updateComponents"]["components"]]
ids2 = [c["id"] for c in msgs2[1]["updateComponents"]["components"]]
assert ids1 == ids2

# --- 7. Three-column grid ---
grid_row = UI.text("A") | UI.text("B") | UI.text("C")
# Note: | is left-associative, so this is Row(Row(A, B), C)
assert grid_row._kind == "Row"

print("All A2UI operator assertions passed!")
```
:::
::::
