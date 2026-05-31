# a2ui-agent

A2UI (Agent-to-UI) protocol toolset for Google's Agent Development Kit (ADK).

This package provides the runtime pieces needed for **LLM-guided** A2UI:

- `a2ui.schema` — protocol version constants (`VERSION_0_9`, `VERSION_0_10`),
  the `A2uiSchemaManager` catalog merger, and config modifiers
  (`remove_strict_validation`).
- `a2ui.basic_catalog` — the `BasicCatalog` provider exposing the basic A2UI
  component set (Text, Button, TextField, Image, Row, Column, Card, ...).
- `a2ui.adk` — `SendA2uiToClientToolset`, an ADK `BaseToolset` whose
  `send_a2ui_to_client` tool lets a model emit an A2UI surface
  (`createSurface` + `updateComponents`) to a connected client.

## Install

```bash
pip install a2ui-agent
```

## Usage with adk-fluent

```python
from adk_fluent import Agent, T

agent = (
    Agent("designer", "gemini-2.5-flash")
    .instruct("Build a UI for the user.")
    .tools(T.a2ui(catalog="basic"))
    .build()
)
```

## Direct usage

```python
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.constants import VERSION_0_9
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.adk.send_a2ui_to_client_toolset import SendA2uiToClientToolset

config = BasicCatalog().get_config(VERSION_0_9)
mgr = A2uiSchemaManager(VERSION_0_9, [config], [remove_strict_validation])
catalog = mgr.get_selected_catalog()
examples = mgr.load_examples(catalog, validate=True)
```

## License

MIT
