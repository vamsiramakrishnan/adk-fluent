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
