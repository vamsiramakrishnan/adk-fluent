"""A2UI Pipeline — Sales Dashboard with Live Metrics

Real-world scenario: a multi-agent sales pipeline where one agent
calculates deal metrics, a state transform bridges the results to
a dashboard UI, and a renderer agent presents the formatted surface.

Key patterns:
  S.to_ui("revenue", "deals", surface="dashboard")  — agent state → UI data
  S.from_ui("selected_deal", surface="deals")        — UI data → agent state
  M.a2ui_log()  — log A2UI operations (renders, updates, interactions)
  C.with_ui()   — include UI surface state in agent context
"""

from adk_fluent import Agent, S
from adk_fluent._context import C
from adk_fluent._middleware import M
from adk_fluent._ui import UI

# --- 1. S.to_ui() creates a state transform ---
to_ui = S.to_ui("total", "count", surface="dashboard")
assert to_ui is not None
assert to_ui.__name__ == "to_ui_total_count"

# --- 2. S.from_ui() creates a state transform ---
from_ui = S.from_ui("name", "email", surface="form")
assert from_ui is not None
assert from_ui.__name__ == "from_ui_name_email"

# --- 3. S.to_ui() bridges data correctly ---
state = {"total": 42, "count": 10, "other": "ignored"}
result = to_ui._fn(state)
data = result.updates
assert "_a2ui_data_dashboard" in data
assert data["_a2ui_data_dashboard"]["total"] == 42
assert data["_a2ui_data_dashboard"]["count"] == 10
assert "other" not in data["_a2ui_data_dashboard"]

# --- 4. S.from_ui() bridges data back ---
ui_state = {"_a2ui_data_form": {"name": "Alice", "email": "alice@example.com", "extra": "x"}}
result2 = from_ui._fn(ui_state)
data2 = result2.updates
assert data2["name"] == "Alice"
assert data2["email"] == "alice@example.com"
assert "extra" not in data2  # Only requested keys

# --- 5. M.a2ui_log() middleware ---
log_mw = M.a2ui_log()
assert log_mw is not None

# --- 6. C.with_ui() context ---
ui_ctx = C.with_ui("dashboard")
assert ui_ctx is not None

# --- 7. Pipeline pattern with UI ---
calc_agent = Agent("calc", "gemini-2.5-flash").instruct("Calculate totals.").writes("total")

renderer = (
    Agent("renderer", "gemini-2.5-flash")
    .instruct("Display results.")
    .ui(UI.dashboard("Metrics", cards=[{"title": "Total", "bind": "/stats/total"}]))
)

# These are composable with >> operator
# pipeline = calc_agent >> S.to_ui("total", surface="metrics") >> renderer

# --- 8. Runnable agent: sales metrics reporter with LLM-driven dashboard ---
_sales_builder = (
    Agent("sales_reporter", "gemini-2.5-flash")
    .instruct(
        "You are a sales analytics agent. When asked about metrics, "
        "create an interactive dashboard showing revenue, deal count, "
        "and pipeline value. Use the A2UI tools to render charts and tables."
    )
    .ui(llm_guided=True)
)
try:
    root_agent = _sales_builder.build()
except Exception:
    root_agent = None
