"""A2UI Dynamic — Data Explorer with LLM-Designed Visualizations

Real-world scenario: a data analyst agent that designs interactive
dashboards and forms on the fly. The user asks "show me Q4 revenue
by region" and the LLM generates a chart+table UI without any
pre-built Python surface — it uses the A2UI JSON schema directly.

``.ui(UI.auto())`` handles everything in one line:
  1. Injects the A2UI component catalog into the LLM's system prompt
  2. Gives the LLM a ``send_a2ui_json_to_client`` tool
  3. The LLM designs valid A2UI JSON surfaces based on user intent
  4. Domain tools (query_db, fetch_metrics) provide the data
"""

from adk_fluent import Agent
from adk_fluent._ui import UI

# --- 1. UI.auto() is the LLM-guided mode marker ---
auto = UI.auto()
assert auto.catalog == "basic"


# --- 2. Agent with .ui(UI.auto()) gets the toolset automatically ---
def get_data(query: str) -> str:
    """Get data for a query."""
    return f"Results for: {query}"


agent = (
    Agent("dynamic_ui", "gemini-2.5-flash")
    .instruct("Create interactive UIs based on user requests.")
    .tool(get_data)
    .ui(UI.auto())
)
built = agent.build()
assert built.name == "dynamic_ui"
# Has the domain tool + the A2UI toolset (when a2ui-agent is installed)
assert len(built.tools) >= 1

# --- 3. Declarative mode still works for static surfaces ---
form = UI.form("Bug Report", fields={"title": "text", "severity": ["Low", "Medium", "High"]})
form_agent = Agent("form_ui", "gemini-2.5-flash").instruct("Collect bug reports.").ui(form)
form_built = form_agent.build()
assert form_built.name == "form_ui"

# --- 4. P.ui_schema() gives lightweight component docs (safe for instruction) ---
from adk_fluent._prompt import P

schema_section = P.ui_schema()
text = schema_section.build()
assert "A2UI" in text
assert "Text" in text  # Component documented
# No JSON braces that would break ADK's {var} substitution

# --- 5. Compare: UI.auto() vs manual setup ---
# With adk-fluent (3 lines):
#   Agent("x", "gemini-2.5-flash").instruct("...").ui(UI.auto()).build()
#
# Without adk-fluent (~25 lines):
#   from a2ui.core.schema.constants import VERSION_0_9
#   from a2ui.core.schema.manager import A2uiSchemaManager
#   from a2ui.basic_catalog.provider import BasicCatalog
#   from a2ui.core.schema.common_modifiers import remove_strict_validation
#   from a2ui.adk.a2a_extension import SendA2uiToClientToolset
#   mgr = A2uiSchemaManager(VERSION_0_9, ...)
#   catalog = mgr.get_selected_catalog()
#   toolset = SendA2uiToClientToolset(a2ui_enabled=True, a2ui_catalog=catalog, ...)
#   LlmAgent(model=..., name=..., instruction=..., tools=[toolset, ...])

# --- Runnable agent: data explorer with LLM-designed visualizations ---
_explorer_builder = (
    Agent("data_explorer", "gemini-2.5-flash")
    .instruct(
        "You are a data exploration agent. Users ask questions about their "
        "data and you create interactive visualizations — dashboards, tables, "
        "charts, and forms. Use the A2UI tools to design the UI dynamically."
    )
    .tool(get_data)
    .ui(UI.auto())
)
try:
    root_agent = _explorer_builder.build()
except Exception:
    root_agent = None
