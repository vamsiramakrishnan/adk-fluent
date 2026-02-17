# adk-fluent

Fluent builder API for Google's [Agent Development Kit (ADK)](https://google.github.io/adk-docs/). Reduces agent creation from 22+ lines to 1-3 lines while maintaining full ADK compatibility.

## Install

```bash
pip install adk-fluent
```

## Quick Start

```python
from adk_fluent import Agent, Pipeline, FanOut

# Simple agent
agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.").build()

# Pipeline (sequential workflow)
pipeline = (
    Pipeline("research")
    .step(Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
    .build()
)

# Fan-out (parallel workflow)
fanout = (
    FanOut("parallel-research")
    .branch(Agent("analyst-1", "gemini-2.5-flash"))
    .branch(Agent("analyst-2", "gemini-2.5-flash"))
    .build()
)
```

## How It Works

adk-fluent is **auto-generated** from the installed ADK package:

1. **Scanner** introspects all ADK modules and produces `manifest.json`
2. **Seed Generator** classifies classes and produces `seed.toml`
3. **Code Generator** emits fluent builders, type stubs, and test scaffolds

This means adk-fluent automatically stays in sync with ADK updates.

```bash
# Regenerate after ADK upgrade
just all
```

## Features

- Fluent chaining: `.instruct()`, `.tool()`, `.before_model()`, etc.
- Full IDE autocomplete via `.pyi` type stubs
- Zero-maintenance `__getattr__` forwarding for any ADK field
- Callback accumulation (multiple `.before_model()` calls append, not replace)
- Builder renames for ergonomics: `Agent`, `Pipeline`, `FanOut`, `Loop`
- 130+ builders covering agents, tools, configs, services, plugins, planners, executors

## Development

```bash
# Setup
uv venv .venv && source .venv/bin/activate
uv pip install google-adk pytest pyright

# Full pipeline
just all

# Run tests
just test

# Type check
just typecheck
```

## License

MIT
