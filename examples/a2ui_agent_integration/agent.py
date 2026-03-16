"""
A2UI Agent Integration: Wiring UI to Agents

Demonstrates attaching UI surfaces to agents and cross-namespace integration.

Key concepts:
  - Agent.ui(): attach declarative or LLM-guided UI
  - UI.auto(): LLM-guided mode
  - T.a2ui(): A2UI toolset in tool composition
  - G.a2ui(): guard for LLM-generated UI validation
  - P.ui_schema(): inject catalog schema into prompt
  - ui_form_agent(): pattern helper

Converted from cookbook example: 71_a2ui_agent_integration.py

Usage:
    cd examples
    adk web a2ui_agent_integration
"""

from adk_fluent import Agent, T, UI
from adk_fluent._guards import G
from adk_fluent._prompt import P
from adk_fluent._ui import UISurface, _UIAutoSpec
from adk_fluent.patterns import ui_dashboard_agent, ui_form_agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# --- 1. Agent.ui() with declarative surface ---
agent = (
    Agent("support", "gemini-2.5-flash")
    .instruct("Help users.")
    .ui(UI.form("ticket", fields={"issue": "longText", "priority": "text"}))
)

# --- 2. Agent.ui() with LLM-guided mode ---
creative = Agent("creative", "gemini-2.5-flash").instruct("Build UIs.").ui(UI.auto())

# --- 3. Agent.ui() with component tree ---
form_agent = Agent("form", "gemini-2.5-flash").ui(
    UI.text("Sign Up") >> (UI.text_field("Email") | UI.text_field("Password")) >> UI.button("Submit")
)

# --- 4. T.a2ui() tool composition ---
tc = T.a2ui()

composed = T.google_search() | T.a2ui()

# --- 5. G.a2ui() guard ---
gc = G.a2ui(max_components=30)

composed_guard = G.pii() | G.a2ui()

# --- 6. P.ui_schema() prompt injection ---
ps = P.ui_schema()

# Compose with other prompt sections
full_prompt = P.role("UI designer") + P.ui_schema() + P.task("Build a dashboard")

# --- 7. .explain() includes UI info ---
info = agent._explain_json()

# --- 8. Pattern helpers ---
intake = ui_form_agent(
    "intake",
    "gemini-2.5-flash",
    fields={"name": "text", "email": "email"},
    instruction="Collect user info.",
)

dash = ui_dashboard_agent(
    "metrics",
    "gemini-2.5-flash",
    cards=[{"title": "Users", "bind": "/users"}, {"title": "Revenue", "bind": "/revenue"}],
)

root_agent = dash.build()
