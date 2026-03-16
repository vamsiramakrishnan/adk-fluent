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
