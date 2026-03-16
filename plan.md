# A2UI Integration Plan for adk-fluent

## Research Summary

### What is A2UI?

A2UI (Agent-to-UI) is Google's open-source declarative UI protocol (Apache 2.0) that lets AI agents generate rich, interactive UIs without sending executable code. Instead of returning plain text, agents emit structured JSON describing UI components; client apps render them using native widgets.

**Key architecture:**
1. **Component Tree** — flat adjacency list of abstract components (not nested)
2. **Data Model** — JSON state that components bind to via JSON Pointer paths
3. **Widget Catalog** — client-defined mapping of component types to native widgets

**Spec versions:** v0.8 (stable), v0.9 (closed), v0.10 (active draft)

**Protocol messages (server→client):**
- `createSurface` — initialize a UI surface with catalog and theme
- `updateComponents` — flat list of component definitions with IDs
- `updateDataModel` — modify state via JSON Pointer paths
- `deleteSurface` — remove a surface

**Client→server:**
- `action` — user interaction (button click, form submit)
- `error` — client-side validation failures

**18 basic catalog components:**
- **Layout:** Row, Column, List, Card, Tabs, Modal, Divider
- **Content:** Text, Image, Icon, Video, AudioPlayer
- **Interactive:** Button, CheckBox, TextField, DateTimeInput, ChoicePicker, Slider

**Data binding:** Components connect to state via DynamicString/Number/Boolean types using JSON Pointer paths (`/user/name`). Two-way binding on inputs.

**Transport:** A2A (primary), AG-UI, MCP, SSE, WebSockets, REST. Messages travel as A2A `DataPart` with `mimeType: "application/json+a2ui"`.

**Python SDK exists** at `agent_sdks/python/` with: `A2uiSchemaManager`, `BasicCatalog`, validator, and `SendA2uiToClientToolset` for ADK integration.

---

## Integration Design

### Design Philosophy

A2UI integration should follow the same patterns as the existing adk-fluent namespaces. The core insight: **A2UI is fundamentally about prompt engineering + output validation**. The agent's LLM generates the A2UI JSON — we need to:

1. Inject the right schema/instructions into the prompt
2. Validate/fix the LLM output
3. Transport it to the client

This maps perfectly to adk-fluent's existing concerns:
- **P namespace** (prompt composition) → inject A2UI schema into prompts
- **G namespace** (guards) → validate A2UI output
- **T namespace** (tools) → `SendA2uiToClientToolset`
- **New UI namespace** → compose A2UI component trees declaratively

### What We Add

#### 1. `UI` Namespace — Declarative Component Composition

A new namespace `UI` (like S, C, P, A, M, T, E, G) for building A2UI component trees in Python. This is the centerpiece — users define UI structure fluently, and the system compiles it to A2UI JSON schema + prompt instructions.

```python
from adk_fluent import UI

# Define a contact form
form = (
    UI.surface("contact_form")
    .theme(primary_color="#00BFFF", agent_name="Assistant")
    .column(
        UI.text("Welcome!", variant="h2"),
        UI.text_field("name", label="Your Name", required=True),
        UI.text_field("email", label="Email", checks=[UI.check.email()]),
        UI.choice_picker("topic", options=["Sales", "Support", "Other"]),
        UI.text_field("message", variant="longText", label="Message"),
        UI.button("submit", label="Send", variant="primary", action="submit_form"),
    )
)

# Use with an agent
agent = (
    Agent("support", "gemini-2.5-flash")
    .instruct("Help users with support requests.")
    .ui(form)                          # Injects A2UI schema + instructions
    .build()
)
```

**Component factories (mirrors the 18 basic catalog components):**

```python
# Content
UI.text(content, variant="body")          # Text with h1-h5, caption, body
UI.image(url, alt=, fit=, size=)          # Image display
UI.icon(name)                             # Predefined or custom icon
UI.video(url)                             # Video player
UI.audio(url, description=)              # Audio player
UI.divider(direction="horizontal")        # Visual separator

# Layout
UI.row(*children, justify=, align=)       # Horizontal layout
UI.column(*children, justify=, align=)    # Vertical layout
UI.list(*children, direction="vertical")  # List layout
UI.card(child)                            # Card container
UI.tabs(**named_children)                 # Tabbed interface
UI.modal(trigger, content)                # Modal overlay

# Interactive
UI.button(id, label=, variant=, action=)          # Action button
UI.text_field(id, label=, variant=, required=)     # Text input
UI.checkbox(id, label=)                            # Boolean toggle
UI.choice_picker(id, options=, multi=)             # Selection
UI.slider(id, min=, max=, step=)                   # Range input
UI.date_time(id, format=)                          # Date/time picker
```

**Data binding:**
```python
# Bind to data model paths
UI.text(UI.bind("/user/name"))                     # Read from data model
UI.text_field("name", value=UI.bind("/form/name")) # Two-way binding

# Dynamic content with format strings
UI.text(UI.fmt("Hello ${/user/name}! You have ${/messages/count} messages."))
```

**Validation functions:**
```python
UI.check.required()
UI.check.email()
UI.check.regex(pattern)
UI.check.length(min=, max=)
UI.check.numeric(min=, max=)
```

**Surface management:**
```python
# Full surface definition
surface = (
    UI.surface("dashboard")
    .catalog("basic")                    # or custom catalog URI
    .theme(primary_color="#1a73e8")
    .root(
        UI.column(
            UI.text("Dashboard", variant="h1"),
            UI.row(
                UI.card(UI.text(UI.bind("/stats/users"), variant="h3")),
                UI.card(UI.text(UI.bind("/stats/revenue"), variant="h3")),
            ),
        )
    )
    .data({"/stats/users": "0", "/stats/revenue": "$0"})  # Initial data model
)
```

#### 2. `.ui()` Builder Method on Agent

New method on the Agent builder that wires up A2UI:

```python
agent = (
    Agent("assistant", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .ui(surface)                    # Full surface definition
    # OR
    .ui(UI.auto())                  # Auto-mode: inject schema, let LLM decide UI
    # OR
    .ui(UI.catalog("basic"))        # Just provide catalog, LLM has full freedom
    .build()
)
```

Under the hood, `.ui()` does three things:
1. **Prompt injection** — Appends A2UI schema, component catalog, and examples to the agent's instruction (via `A2uiSchemaManager.generate_system_prompt()`)
2. **Tool attachment** — Adds `SendA2uiToClientToolset` so the agent can emit A2UI messages
3. **Output guard** — Optionally adds a guard that validates A2UI JSON output

#### 3. `.ui()` on A2AServer — Declare A2UI Capabilities

```python
server = (
    A2AServer(agent)
    .port(8001)
    .ui(catalogs=["basic"], inline=True)    # Declare A2UI extension in AgentCard
    .build()
)
```

This adds the A2UI extension to the AgentCard's `capabilities.extensions` with `supportedCatalogIds`.

#### 4. UI Presets — Common UI Patterns

```python
from adk_fluent import UI

# Pre-built surface patterns
form = UI.preset.form(
    fields={"name": "text", "email": "email", "message": "longText"},
    submit_action="submit",
    title="Contact Us"
)

table = UI.preset.table(
    columns=["Name", "Email", "Status"],
    data_path="/users",
    actions=["edit", "delete"]
)

dashboard = UI.preset.dashboard(
    cards=[
        {"title": "Users", "value_path": "/stats/users"},
        {"title": "Revenue", "value_path": "/stats/revenue"},
    ]
)
```

#### 5. Expression Operator: `Agent ^ UI.surface()`

A dedicated operator or chaining for UI attachment:

```python
# Option A: dedicated method (recommended)
agent = Agent("a").instruct("...").ui(surface).build()

# Option B: P namespace integration
agent = (
    Agent("a")
    .instruct(
        P.role("Customer support agent.")
        + P.task("Help customers with orders.")
        + UI.prompt_section()     # Injects A2UI instructions as a P section
    )
    .tools(UI.toolset())          # Just the toolset
    .build()
)
```

#### 6. Integration with Existing Namespaces

**P (Prompt) integration:**
```python
# UI instructions as a prompt section
UI.prompt_section(catalog="basic", examples=True)  # Returns PTransform
```

**T (Tools) integration:**
```python
# A2UI toolset for explicit tool control
T.a2ui(catalog="basic")  # Returns TComposite wrapping SendA2uiToClientToolset
```

**G (Guards) integration:**
```python
# Validate A2UI output
G.a2ui(catalog="basic")  # Returns GComposite that validates A2UI JSON
```

**M (Middleware) integration:**
```python
# Log A2UI messages
M.a2ui_log()  # Log all A2UI surface updates
```

**S (State) integration:**
```python
# A2UI data model ↔ agent state bridge
S.to_data_model(surface_id="form", mapping={"/name": "user_name"})
S.from_data_model(surface_id="form", mapping={"/name": "user_name"})
```

---

## Implementation Plan

### Phase 1: Core UI Namespace (`_ui.py`)

**New file:** `src/adk_fluent/_ui.py`

- `UISurface` — surface builder (surfaceId, catalogId, theme, root component)
- `UIComponent` — base component dataclass (id, component type, properties)
- Component factories: `UI.text()`, `UI.button()`, `UI.column()`, etc.
- `UI.bind()` — data binding helper
- `UI.check.*` — validation function factories
- `UI.fmt()` — format string helper
- Compilation: `surface.to_a2ui()` → list of A2UI JSON messages

### Phase 2: Agent Integration

**Edit:** `src/adk_fluent/_base.py`

- Add `.ui(surface_or_config)` method to BuilderBase
- Wire up prompt injection, toolset, and guard at build time
- Handle `UI.auto()` mode for schema-only injection

### Phase 3: Namespace Cross-Integrations

- `T.a2ui()` in `_tools.py`
- `G.a2ui()` in `_guards.py`
- `P` integration via `UI.prompt_section()` returning PTransform
- `S` transforms for data model bridging

### Phase 4: A2AServer Extension

**Edit:** `src/adk_fluent/a2a.py`

- Add `.ui()` method to A2AServer
- Wire A2UI extension into AgentCard capabilities

### Phase 5: Presets & Patterns

- `UI.preset.form()`, `UI.preset.table()`, `UI.preset.dashboard()`
- Common A2UI surface patterns as reusable templates

### Phase 6: Tests & Documentation

- Unit tests in `tests/manual/test_ui.py`
- Cookbook example in `cookbooks/`
- Update CLAUDE.md with UI namespace docs

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `src/adk_fluent/_ui.py` | **CREATE** | Core UI namespace — components, surfaces, data binding |
| `src/adk_fluent/_base.py` | EDIT | Add `.ui()` builder method |
| `src/adk_fluent/_tools.py` | EDIT | Add `T.a2ui()` factory |
| `src/adk_fluent/_guards.py` | EDIT | Add `G.a2ui()` factory |
| `src/adk_fluent/a2a.py` | EDIT | Add `.ui()` to A2AServer |
| `src/adk_fluent/__init__.py` | EDIT | Export UI namespace |
| `src/adk_fluent/prelude.py` | EDIT | Export UI in prelude |
| `tests/manual/test_ui.py` | **CREATE** | UI namespace tests |

---

## Key Design Decisions

1. **UI as namespace, not builder** — Like S, C, P, UI is a namespace of static factory methods that return composable dataclasses. This is consistent with the existing API.

2. **Flat component model** — Matches A2UI's flat adjacency list design. Components reference children by ID, not nesting. But we provide Pythonic nesting in the API that compiles to flat format.

3. **Dependency on `a2ui` package** — Optional. The UI namespace works standalone for JSON generation. Full integration (schema validation, prompt generation) requires `pip install a2ui`.

4. **Version targeting** — Target v0.10 (active draft) with v0.8 compatibility.

5. **LLM-generated vs declarative** — Two modes:
   - **Declarative:** User defines exact UI structure → compiled to A2UI JSON (no LLM needed)
   - **LLM-guided:** User provides catalog/schema → LLM generates UI dynamically
   Both are first-class.
