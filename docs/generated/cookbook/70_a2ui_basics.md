# A2UI Basics: Declarative Agent-to-UI Composition

Demonstrates the UI namespace for building rich agent UIs declaratively.

Key concepts:
  - UIComponent: frozen dataclass with composition operators
  - UI.text(), UI.button(), UI.text_field(): component factories
  - UI.bind(), UI.required(): data binding and validation
  - UI.surface(): named UI surface (compilation root)
  - compile_surface(): nested Python tree → flat A2UI JSON
  - Operators: | (Row), >> (Column), + (sibling group)

:::{tip} What you'll learn
How to use operator syntax for composing agents.
:::

_Source: `70_a2ui_basics.py`_
