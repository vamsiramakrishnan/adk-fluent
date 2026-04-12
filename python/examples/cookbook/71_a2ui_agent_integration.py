"""A2UI Agent Integration: Wiring UI to Agents

Demonstrates attaching UI surfaces to agents and cross-namespace integration.

Key concepts:
  - Agent.ui(): attach declarative or LLM-guided UI
  - UI.auto(): LLM-guided mode
  - T.a2ui(): A2UI toolset in tool composition
  - G.a2ui(): guard for LLM-generated UI validation
  - P.ui_schema(): inject catalog schema into prompt
  - ui_form_agent(): pattern helper
"""

from adk_fluent import Agent, T, UI
from adk_fluent._guards import G
from adk_fluent._prompt import P
from adk_fluent._ui import UISurface, _UIAutoSpec
from adk_fluent.patterns import ui_dashboard_agent, ui_form_agent

# --- 1. Agent.ui() with declarative surface ---
agent = (
    Agent("support", "gemini-2.5-flash")
    .instruct("Help users.")
    .ui(UI.form("ticket", fields={"issue": "longText", "priority": "text"}))
)
assert isinstance(agent._config["_ui_spec"], UISurface)

# --- 2. Agent.ui() with LLM-guided mode ---
creative = Agent("creative", "gemini-2.5-flash").instruct("Build UIs.").ui(UI.auto())
assert isinstance(creative._config["_ui_spec"], _UIAutoSpec)

# --- 3. Agent.ui() with component tree ---
form_agent = Agent("form", "gemini-2.5-flash").ui(
    UI.text("Sign Up") >> (UI.text_field("Email") | UI.text_field("Password")) >> UI.button("Submit")
)
assert form_agent._config["_ui_spec"] is not None

# --- 4. T.a2ui() tool composition ---
tc = T.a2ui()
assert tc._kind == "a2ui"

composed = T.google_search() | T.a2ui()
assert len(composed) >= 1

# --- 5. G.a2ui() guard ---
gc = G.a2ui(max_components=30)
assert gc is not None

composed_guard = G.pii() | G.a2ui()
assert composed_guard is not None

# --- 6. P.ui_schema() prompt injection ---
ps = P.ui_schema()
assert ps.name == "ui_schema"
assert len(ps.content) > 0

# Compose with other prompt sections
full_prompt = P.role("UI designer") + P.ui_schema() + P.task("Build a dashboard")
assert full_prompt is not None

# --- 7. .explain() includes UI info ---
info = agent._explain_json()
assert "ui" in info
assert info["ui"]["mode"] == "declarative"

# --- 8. Pattern helpers ---
intake = ui_form_agent(
    "intake",
    "gemini-2.5-flash",
    fields={"name": "text", "email": "email"},
    instruction="Collect user info.",
)
assert intake._config.get("_ui_spec") is not None
assert intake._config.get("instruction") == "Collect user info."

dash = ui_dashboard_agent(
    "metrics",
    "gemini-2.5-flash",
    cards=[{"title": "Users", "bind": "/users"}, {"title": "Revenue", "bind": "/revenue"}],
)
assert dash._config.get("_ui_spec") is not None

print("All A2UI agent integration assertions passed!")
