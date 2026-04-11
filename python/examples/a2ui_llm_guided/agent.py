"""
A2UI LLM-Guided Mode: Let the LLM Design the UI

Demonstrates LLM-guided UI mode where the agent has full control
over the A2UI surface via toolset + catalog schema injection.

Key concepts:
  - UI.auto(): LLM-guided mode marker
  - P.ui_schema(): inject catalog schema into prompt
  - T.a2ui(): A2UI toolset for LLM-controlled UI
  - G.a2ui(): guard to validate LLM-generated UI output

Converted from cookbook example: 73_a2ui_llm_guided.py

Usage:
    cd examples
    adk web a2ui_llm_guided
"""

from adk_fluent import Agent, T
from adk_fluent._guards import G
from adk_fluent._prompt import P
from adk_fluent._ui import UI, _UIAutoSpec
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# --- 1. Basic LLM-guided agent ---
auto_agent = Agent("creative", "gemini-2.5-flash").instruct("Build beautiful UIs.").ui(UI.auto())

# --- 2. LLM-guided with catalog schema in prompt ---
guided = (
    Agent("designer", "gemini-2.5-flash")
    .instruct(P.role("UI designer") + P.ui_schema() + P.task("Build a dashboard"))
    .ui(UI.auto())
)

# --- 3. Full namespace symphony ---
full_agent = (
    Agent("support", "gemini-2.5-flash")
    .instruct(P.role("Support agent") + P.ui_schema() + P.task("Help customers"))
    .tools(T.google_search() | T.a2ui())
    .guard(G.pii() | G.a2ui(max_components=30))
    .ui(UI.auto())
)

# --- 4. UI.auto() with custom catalog ---
custom = UI.auto(catalog="extended")

# --- 5. P.ui_schema() produces content ---
schema_section = P.ui_schema()

root_agent = schema_section.build()
