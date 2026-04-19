# A2UI LLM-Guided Mode: Let the LLM Design the UI

Demonstrates LLM-guided UI mode where the agent has full control
over the A2UI surface via toolset + catalog schema injection.

Key concepts:
  - UI.auto(): LLM-guided mode marker
  - P.ui_schema(): inject catalog schema into prompt
  - T.a2ui(): A2UI toolset for LLM-controlled UI
  - G.a2ui(): guard to validate LLM-generated UI output

:::{tip} What you'll learn
How to attach tools to an agent using the fluent API.
:::

_Source: `73_a2ui_llm_guided.py`_

```python
from adk_fluent import Agent, T
from adk_fluent._guards import G
from adk_fluent._prompt import P
from adk_fluent._ui import UI, _UIAutoSpec

# --- 1. Basic LLM-guided agent ---
auto_agent = Agent("creative", "gemini-2.5-flash").instruct("Build beautiful UIs.").ui(UI.auto())
assert isinstance(auto_agent._config["_ui_spec"], _UIAutoSpec)

# --- 2. LLM-guided with catalog schema in prompt ---
guided = (
    Agent("designer", "gemini-2.5-flash")
    .instruct(P.role("UI designer") + P.ui_schema() + P.task("Build a dashboard"))
    .ui(UI.auto())
)
assert guided._config.get("_ui_spec") is not None

# --- 3. Full namespace symphony ---
full_agent = (
    Agent("support", "gemini-2.5-flash")
    .instruct(P.role("Support agent") + P.ui_schema() + P.task("Help customers"))
    .tools(T.google_search() | T.a2ui())
    .guard(G.pii() | G.a2ui(max_components=30))
    .ui(UI.auto())
)
assert full_agent._config.get("_ui_spec") is not None

# --- 4. UI.auto() with custom catalog ---
custom = UI.auto(catalog="extended")
assert custom.catalog == "extended"

# --- 5. P.ui_schema() produces content ---
schema_section = P.ui_schema()
assert schema_section.name == "ui_schema"
assert len(schema_section.content) > 0

print("All A2UI LLM-guided assertions passed!")
```
