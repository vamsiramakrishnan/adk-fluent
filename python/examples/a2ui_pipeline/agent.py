"""
A2UI Pipeline: UI in Multi-Agent Pipelines

Demonstrates using S.to_ui() and S.from_ui() to bridge state data
between agents and A2UI surfaces.

Key concepts:
  - S.to_ui(): bridge agent state → A2UI data model
  - S.from_ui(): bridge A2UI data model → agent state
  - M.a2ui_log(): log A2UI surface operations
  - C.with_ui(): include UI surface state in context

Converted from cookbook example: 74_a2ui_pipeline.py

Usage:
    cd examples
    adk web a2ui_pipeline
"""

from adk_fluent import Agent, S
from adk_fluent._context import C
from adk_fluent._middleware import M
from adk_fluent._ui import UI
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# --- 1. S.to_ui() creates a state transform ---
to_ui = S.to_ui("total", "count", surface="dashboard")

# --- 2. S.from_ui() creates a state transform ---
from_ui = S.from_ui("name", "email", surface="form")

# --- 3. S.to_ui() bridges data correctly ---
state = {"total": 42, "count": 10, "other": "ignored"}
result = to_ui._fn(state)
data = result.updates

# --- 4. S.from_ui() bridges data back ---
ui_state = {"_a2ui_data_form": {"name": "Alice", "email": "alice@example.com", "extra": "x"}}
result2 = from_ui._fn(ui_state)
data2 = result2.updates

# --- 5. M.a2ui_log() middleware ---
log_mw = M.a2ui_log()

# --- 6. C.with_ui() context ---
ui_ctx = C.with_ui("dashboard")

# --- 7. Pipeline pattern with UI ---
calc_agent = Agent("calc", "gemini-2.5-flash").instruct("Calculate totals.").writes("total")

renderer = (
    Agent("renderer", "gemini-2.5-flash")
    .instruct("Display results.")
    .ui(UI.dashboard("Metrics", cards=[{"title": "Total", "bind": "/stats/total"}]))
)

# These are composable with >> operator
# pipeline = calc_agent >> S.to_ui("total", surface="metrics") >> renderer

root_agent = renderer.build()
