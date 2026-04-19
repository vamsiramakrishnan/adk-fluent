# A2UI Dynamic: LLM-Driven UI Generation

Demonstrates the core A2UI value proposition: the LLM itself designs
interactive UI surfaces based on user intent. .ui(UI.auto()) handles
everything — it attaches the SendA2uiToClientToolset which injects
the full A2UI JSON Schema at LLM request time and gives the LLM a
send_a2ui_json_to_client tool.

Key concepts:
  - .ui(UI.auto()): one-line A2UI setup (schema + toolset)
  - SendA2uiToClientToolset injects schema via process_llm_request
  - The LLM generates valid A2UI JSON — no Python UI construction
  - Domain tools provide data, the LLM designs the presentation

:::{tip} What you'll learn
How to attach tools to an agent using the fluent API.
:::

_Source: `77_a2ui_dynamic.py`_

```python
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

print("OK — 77_a2ui_dynamic")
```
