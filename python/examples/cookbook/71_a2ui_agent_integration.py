"""A2UI Agent Integration: Wiring UI to Agents (the wedge devex)

Demonstrates the ergonomic ``Agent.ui()`` overload introduced in the A2UI
devex wedge:

- ``.ui(spec)``                — declarative surface (prompt-only, no tool wiring)
- ``.ui(llm_guided=True)``     — auto-wires ``T.a2ui()`` + ``G.a2ui()`` for you
- ``.ui(spec, log=True)``      — also auto-wires ``M.a2ui_log()``
- ``.ui(spec, validate=False)``— skip ``surface.validate()`` at build time

Plus the schema-driven helpers:

- ``UI.form(MyPydanticModel)`` — generate a typed form from a BaseModel
- ``UI.paths(MyPydanticModel)``— typed two-way binding proxy
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from adk_fluent import (
    A2UIError,
    A2UINotInstalled,
    Agent,
    BuilderError,
    G,
    T,
    UI,
    UIBinding,
    UISurface,
)
from adk_fluent._ui import _UIAutoSpec  # internal marker, used only for isinstance check

# ---------------------------------------------------------------------------
# 1. Declarative surface — old form-dict syntax still works.
# ---------------------------------------------------------------------------

agent = (
    Agent("support", "gemini-2.5-flash")
    .instruct("Help users.")
    .ui(UI.form("ticket", fields={"issue": "longText", "priority": "text"}))
)
assert isinstance(agent._config["_ui_spec"], UISurface)
assert agent._config["_a2ui_auto_tool"] is False  # prompt-only
assert agent._config["_a2ui_auto_guard"] is False
assert agent._config["_a2ui_validate"] is True  # default

# ---------------------------------------------------------------------------
# 2. Schema-driven form (the wedge headline feature).
# ---------------------------------------------------------------------------


class TicketForm(BaseModel):
    title: str
    priority: Literal["low", "med", "high"]
    description: str | None = None
    notify: bool = True


schema_surface = UI.form(TicketForm)
assert isinstance(schema_surface, UISurface)
assert schema_surface.name == "ticketform"
# Five components: title, priority, description, notify + Text("Title") header + Submit
# Just sanity check the root has children
assert schema_surface.root is not None and len(schema_surface.root._children) >= 5

ticket_agent = (
    Agent("ticket", "gemini-2.5-flash").instruct("Collect ticket info.").ui(schema_surface)
)
assert isinstance(ticket_agent._config["_ui_spec"], UISurface)

# ---------------------------------------------------------------------------
# 3. Reflective binding paths — typo-proof field references.
# ---------------------------------------------------------------------------

paths = UI.paths(TicketForm)
binding = paths.title
assert isinstance(binding, UIBinding)
assert binding.path == "/title"

try:
    _ = paths.titel  # typo
except AttributeError as exc:
    assert "Available fields" in str(exc)
else:
    raise AssertionError("UI.paths should reject unknown attributes")

# ---------------------------------------------------------------------------
# 4. LLM-guided mode — auto-wires T.a2ui() + G.a2ui() at build time.
#    When 'a2ui-agent' is not installed, .build() raises BuilderError
#    (chained from A2UINotInstalled). This is the fail-loud contract.
# ---------------------------------------------------------------------------

creative = Agent("creative", "gemini-2.5-flash").instruct("Build UIs.").ui(llm_guided=True)
spec = creative._config["_ui_spec"]
assert isinstance(spec, _UIAutoSpec)
assert spec._from_flag is True
assert creative._config["_a2ui_auto_tool"] is True
assert creative._config["_a2ui_auto_guard"] is True

try:
    import a2ui.agent  # type: ignore[import-not-found]  # noqa: F401

    creative.build()  # succeeds when the optional dep is present
except ImportError:
    try:
        creative.build()
    except BuilderError as exc:
        assert isinstance(exc.__cause__, A2UINotInstalled)
    else:
        raise AssertionError("expected BuilderError when a2ui-agent is missing")

# ---------------------------------------------------------------------------
# 5. Mixing flags: declarative surface + log=True.
# ---------------------------------------------------------------------------

logged = (
    Agent("logged", "gemini-2.5-flash")
    .instruct("Show a confirm dialog.")
    .ui(UI.confirm("Delete?"), log=True)
)
assert logged._config["_a2ui_auto_log"] is True
assert getattr(logged, "_middlewares", None) is None  # log middleware applies at build

# Building wires the M.a2ui_log middleware onto the builder.
logged.build()
assert any(getattr(mw, "_hook_name", None) == "after_model_callback" for mw in logged._middlewares)

# ---------------------------------------------------------------------------
# 6. Incompatible combinations raise A2UIError early.
# ---------------------------------------------------------------------------

try:
    Agent("bad", "gemini-2.5-flash").ui(UI.surface("x", UI.text("hi")), llm_guided=True)
except A2UIError as exc:
    assert "incompatible" in str(exc)
else:
    raise AssertionError("declarative surface + llm_guided=True should raise")

try:
    Agent("bad", "gemini-2.5-flash").ui()
except A2UIError as exc:
    assert "requires a spec or llm_guided=True" in str(exc)
else:
    raise AssertionError(".ui() with no args and no flag should raise")

# ---------------------------------------------------------------------------
# 7. surface.validate() — opt-in static checks.
# ---------------------------------------------------------------------------

clean = UI.surface("clean", UI.text("Hi"))
assert clean.validate() is clean  # no-op for clean surfaces

# ---------------------------------------------------------------------------
# 8. Cross-namespace integration — manual wiring still composes cleanly.
# ---------------------------------------------------------------------------

guard_chain = G.pii() | G.a2ui()  # G.a2ui works without a2ui-agent
assert guard_chain is not None

print("All A2UI agent integration assertions passed!")
