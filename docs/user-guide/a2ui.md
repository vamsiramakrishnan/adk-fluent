# A2UI -- Agent-to-UI Composition

:::{admonition} At a Glance
:class: tip

- UI module provides declarative UI composition for agents
- Compose with `|` (row) and `>>` (column), attach with `.ui(spec)`
- Three modes: declarative (you define), LLM-guided (agent decides), hybrid
:::

The **UI namespace** lets agents define rich, interactive user interfaces declaratively. Agents emit [A2UI protocol](https://github.com/google/A2UI) JSON that clients render as native widgets -- no frontend code required from the agent developer.

:::{admonition} Install
:class: tip

The UI namespace ships with the core package -- no extra install needed:

```bash
pip install adk-fluent
```

The full A2UI toolset (`SendA2uiToClientToolset`) will be available via `pip install adk-fluent[a2ui]` when the `a2ui-agent` package is published. Until then, all composition, compilation, and presets work out of the box.
:::

## Architecture

```
Python (adk-fluent)                          Client (Flutter/React/Angular)
┌─────────────────────┐                      ┌───────────────────────────┐
│ UI.text("Hello")    │                      │                           │
│   >> UI.text_field() │  compile_surface()  │  createSurface            │
│   >> UI.button()     │ ─────────────────►  │  updateComponents         │
│                     │     A2UI JSON        │  updateDataModel          │
│ UISurface           │                      │  → Native Widgets         │
└─────────────────────┘                      └───────────────────────────┘
```

**Three layers of support:**

| Layer | What it provides | Extra install? |
|-------|-----------------|----------------|
| **Core UI** | `UIComponent`, operators, `compile_surface()`, presets | None |
| **Agent integration** | `.ui()`, prompt augmentation, JSON compilation | None |
| **Full A2UI toolset** | `SendA2uiToClientToolset`, schema validation | `adk-fluent[a2ui]` (coming soon) |

## Quick Start

### Declarative Surface

```python
from adk_fluent import Agent, UI

agent = (
    Agent("signup", "gemini-2.5-flash")
    .instruct("Help users sign up.")
    .ui(
        UI.text("Create Account", variant="h1")
        >> (UI.text_field("First Name") | UI.text_field("Last Name"))
        >> UI.text_field("Email")
        >> UI.button("Sign Up")
    )
)
```

### LLM-Guided Mode

```python
from adk_fluent import Agent, T, UI
from adk_fluent._prompt import P

agent = (
    Agent("creative", "gemini-2.5-pro")
    .instruct(P.role("UI designer") + P.ui_schema() + P.task("Build a dashboard"))
    .tools(T.google_search() | T.a2ui())
    .ui(UI.auto())
)
```

## Component Factories

Every A2UI component has a typed factory on `UI`:

```python
from adk_fluent import UI

# Content
UI.text("Hello, World!", variant="h1")     # Text (h1-h5, caption, body)
UI.image("photo.jpg", alt="Photo")         # Image
UI.button("Click Me")                      # Button

# Input
UI.text_field("Name", bind="/user/name")   # TextField with data binding
UI.text_field("Bio", variant="longText")   # Long text variant

# Generic escape hatch (any A2UI component)
UI.component("BarChart", data="/data", x="date", y="value")
```

## Layout Operators

Python operators compose components into layouts:

| Operator | Layout | Example |
|----------|--------|---------|
| `\|` | **Row** (horizontal) | `UI.text("A") \| UI.text("B")` |
| `>>` | **Column** (vertical) | `UI.text("Top") >> UI.text("Bottom")` |

Nest them for complex layouts:

```python
layout = (
    UI.text("Header", variant="h1")
    >> (UI.text_field("Email") | UI.text_field("Password"))
    >> (UI.button("Submit") | UI.button("Cancel"))
)
```

## Data Binding and Validation

```python
# Two-way data binding
field = UI.text_field("Email", bind="/user/email")

# Standalone binding object
binding = UI.bind("/user/name")

# Validation checks
UI.required("Name is required")
UI.email("Invalid email address")
```

## Surfaces

A `UISurface` is the compilation root -- a named UI that gets sent to the client:

```python
surface = UI.surface("contact", UI.text("Contact Us") >> UI.text_field("Name"))

# Theme customization
surface = surface.with_theme(primaryColor="#3b82f6")

# Initial data model
surface = surface.with_data(name="", email="")
```

### Compilation

`compile_surface()` converts the nested Python tree into flat A2UI JSON messages:

```python
from adk_fluent._ui import compile_surface

msgs = compile_surface(surface)
# msgs[0] = {"createSurface": {"surfaceId": "contact", ...}}
# msgs[1] = {"updateComponents": {"components": [...]}}
```

## Presets

High-level factories for common UI patterns:

```python
# Form with typed fields
UI.form("Contact", fields={"name": "text", "email": "email", "bio": "longText"})

# Dashboard with metric cards
UI.dashboard("Metrics", cards=[
    {"title": "Users", "bind": "/users"},
    {"title": "Revenue", "bind": "/revenue"},
])

# Multi-step wizard
UI.wizard("Onboarding", steps=[
    ("Welcome", UI.text("Welcome!")),
    ("Profile", UI.text_field("Name")),
])

# Confirmation dialog
UI.confirm("Delete this item?", yes="Delete", no="Cancel")

# Data table
UI.table(["Name", "Email", "Role"], data_bind="/users")
```

## Cross-Namespace Integration

The UI namespace integrates with every other adk-fluent namespace:

### T.a2ui() -- Tool Composition

```python
from adk_fluent import T

# Give the agent full A2UI toolset for LLM-guided UI
agent.tools(T.google_search() | T.a2ui())
```

### G.a2ui() -- Output Guard

```python
from adk_fluent._guards import G

# Validate LLM-generated UI output
agent.guard(G.pii() | G.a2ui(max_components=30))
```

### P.ui_schema() -- Prompt Injection

```python
from adk_fluent._prompt import P

# Inject A2UI catalog schema into the prompt
agent.instruct(P.role("UI designer") + P.ui_schema() + P.task("Build a form"))
```

### S.to_ui() / S.from_ui() -- State Bridges

```python
from adk_fluent import S

# Bridge agent state → A2UI data model
pipeline = Agent("calc").writes("total") >> S.to_ui("total", surface="dash")

# Bridge A2UI data model → agent state
pipeline = S.from_ui("name", "email", surface="form") >> Agent("processor")
```

### M.a2ui_log() -- Middleware

```python
from adk_fluent._middleware import M

# Log A2UI surface operations
agent.middleware(M.a2ui_log(level="debug"))
```

### C.with_ui() -- Context

```python
from adk_fluent._context import C

# Include UI surface state in agent context
agent.context(C.with_ui("dashboard"))
```

## Agent Integration

### .ui() Builder Method

Attach a UI surface to any agent:

```python
# Declarative surface
agent = Agent("support").ui(UI.form("ticket", fields={"issue": "longText"}))

# LLM-guided mode
agent = Agent("creative").ui(UI.auto())

# Component tree
agent = Agent("form").ui(
    UI.text("Sign Up") >> UI.text_field("Email") >> UI.button("Submit")
)
```

### Pattern Helpers

```python
from adk_fluent.patterns import ui_form_agent, ui_dashboard_agent

# Pre-configured form agent
intake = ui_form_agent(
    "intake", "gemini-2.5-flash",
    fields={"name": "text", "email": "email"},
    instruction="Collect user info.",
)

# Pre-configured dashboard agent
dash = ui_dashboard_agent(
    "metrics", "gemini-2.5-flash",
    cards=[{"title": "Users", "bind": "/users"}],
)
```

## Introspection

```python
# .explain() shows UI surface info
agent.explain()
# => ui: {mode: declarative, surface: ticket, components: 3}

# .data_flow() includes UI concern
flow = agent.data_flow()
print(flow)
# => ui: declarative surface 'ticket'

# .doctor() warns about unbound input fields
agent.doctor()
# => [INFO] support: UI input 'Email' has no data binding
#    Hint: Add bind='/path' to connect this field to the data model.
```

## A2UI Protocol Version

adk-fluent bundles the [A2UI v0.10 specification](https://github.com/google/A2UI) JSON schemas. The upstream A2UI project is at v0.8 Public Preview. Our bundled schemas are forward-compatible and will be updated as the spec evolves. Run `just a2ui-scan` to re-scan against newer spec versions.

## Cookbook Examples

| # | Example | What you'll learn |
|---|---------|-------------------|
| 70 | [A2UI Basics](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/examples/cookbook/70_a2ui_basics.py) | Components, operators, binding, surfaces, compilation |
| 71 | [Agent Integration](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/examples/cookbook/71_a2ui_agent_integration.py) | `.ui()`, `T.a2ui()`, `G.a2ui()`, `P.ui_schema()` |
| 72 | [Operators](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/examples/cookbook/72_a2ui_operators.py) | `\|` (Row), `>>` (Column) layout composition |
| 73 | [LLM-Guided](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/examples/cookbook/73_a2ui_llm_guided.py) | `UI.auto()`, `P.ui_schema()`, full namespace symphony |
| 74 | [Pipeline](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/examples/cookbook/74_a2ui_pipeline.py) | `S.to_ui()`, `S.from_ui()`, data bridges |
