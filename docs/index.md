# adk-fluent

Fluent builder API for Google's [Agent Development Kit (ADK)](https://google.github.io/adk-docs/).
Reduces agent creation from 22+ lines to 1-3 lines while producing identical native ADK objects.

## Install

```bash
pip install adk-fluent
```

## Quick Example

```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are helpful.").build()
```

Every `.build()` returns a real ADK object — fully compatible with `adk web`, `adk run`, and `adk deploy`.

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} 🚀 Getting Started
:link: getting-started
:link-type: doc
Learn the core concepts and build your first fluent agent in 5 minutes.
:::

:::{grid-item-card} 📘 User Guide
:link: user-guide/index
:link-type: doc
Deep dive into builders, operators, prompts, and callbacks.
:::

:::{grid-item-card} 🍳 Cookbook
:link: generated/cookbook/index
:link-type: doc
34+ copy-pasteable recipes and side-by-side native ADK comparisons.
:::

:::{grid-item-card} 📚 API Reference
:link: generated/api/index
:link-type: doc
Complete method reference for all 130+ builders.
:::
::::

```{toctree}
---
maxdepth: 2
caption: Getting Started
---
getting-started
```

```{toctree}
---
maxdepth: 2
caption: User Guide
---
user-guide/index
```

```{toctree}
---
maxdepth: 2
caption: API Reference
---
generated/api/index
```

```{toctree}
---
maxdepth: 2
caption: Cookbook
---
generated/cookbook/index
```

```{toctree}
---
maxdepth: 2
caption: Examples
---
runnable-examples
```

```{toctree}
---
maxdepth: 1
caption: Migration
---
generated/migration/from-native-adk
```

```{toctree}
---
maxdepth: 2
caption: Contributing
---
contributing/index
```

```{toctree}
---
maxdepth: 1
caption: Project
---
changelog
```
