# adk-fluent

Fluent builder API for Google's [Agent Development Kit (ADK)](https://google.github.io/adk-docs/). Reduces agent creation from 22+ lines to 1-3 lines while producing identical native ADK objects.

[![PyPI](https://img.shields.io/pypi/v/adk-fluent)](https://pypi.org/project/adk-fluent/)
[![Python](https://img.shields.io/pypi/pyversions/adk-fluent)](https://pypi.org/project/adk-fluent/)
[![License](https://img.shields.io/pypi/l/adk-fluent)](https://gitlab.com/google-cloud-ce/googlers/vamramak/adk-fluent/-/blob/master/LICENSE)

## Install

```bash
pip install adk-fluent
```

Autocomplete works immediately -- the package ships with `.pyi` type stubs for every builder. Type `Agent("name").` and your IDE shows all available methods with type hints.

### IDE Setup

**VS Code** -- install the [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) extension (included in the Python extension pack). Autocomplete and type checking work out of the box.

**PyCharm** -- works automatically. The `.pyi` stubs are bundled in the package and PyCharm discovers them on install.

**Neovim (LSP)** -- use [pyright](https://github.com/microsoft/pyright) as your language server. Stubs are picked up automatically.

### Discover the API

```python
from adk_fluent import Agent

agent = Agent("demo")
agent.  # <- autocomplete shows: .model(), .instruct(), .tool(), .build(), ...

# Typos are caught at definition time, not runtime:
agent.instuction("oops")  # -> AttributeError: 'instuction' is not a recognized field.
                          #    Did you mean: 'instruction'?

# Inspect any builder's current state:
print(agent.model("gemini-2.5-flash").instruct("Help.").explain())
# Agent: demo
#   Config fields: model, instruction

# See everything available:
print(dir(agent))  # All methods including forwarded ADK fields
```

## Quick Start

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop

# Simple agent — builds to a real LlmAgent
agent = (
    Agent("helper")
    .model("gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .build()
)

# Pipeline — sequential workflow
pipeline = (
    Agent("researcher").model("gemini-2.5-flash").instruct("Research the topic.")
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write a summary.")
)

# Parallel — fan-out workflow
parallel = (
    Agent("web").model("gemini-2.5-flash").instruct("Search the web.")
    | Agent("db").model("gemini-2.5-flash").instruct("Search the database.")
)

# Loop — iterative refinement
loop = (
    Agent("critic").model("gemini-2.5-flash").instruct("Critique.")
    >> Agent("reviser").model("gemini-2.5-flash").instruct("Revise.")
) * 3
```

Every `.build()` returns a real ADK object (`LlmAgent`, `SequentialAgent`, etc.). Fully compatible with `adk web`, `adk run`, and `adk deploy`.

## Expression Language

Five operators compose any agent topology:

| Operator | Meaning | ADK Type |
|----------|---------|----------|
| `a >> b` | Sequence | `SequentialAgent` |
| `a \| b` | Parallel | `ParallelAgent` |
| `a * 3` | Loop | `LoopAgent` |
| `Route("key").eq(...)` | Branch | Deterministic routing |
| `.proceed_if(...)` | Gate | Conditional skip |

### Deterministic Routing

Route on session state without LLM calls:

```python
from adk_fluent import Agent
from adk_fluent._routing import Route

classifier = Agent("classify").model("gemini-2.5-flash").instruct("Classify intent.").outputs("intent")
booker = Agent("booker").model("gemini-2.5-flash").instruct("Book flights.")
info = Agent("info").model("gemini-2.5-flash").instruct("Provide info.")

# Route on exact match — zero LLM calls for routing
pipeline = classifier >> Route("intent").eq("booking", booker).eq("info", info)

# Dict shorthand
pipeline = classifier >> {"booking": booker, "info": info}
```

### Conditional Gating

```python
# Only runs if predicate(state) is truthy
enricher = (
    Agent("enricher")
    .model("gemini-2.5-flash")
    .instruct("Enrich the data.")
    .proceed_if(lambda s: s.get("valid") == "yes")
)
```

### Conditional Loop Exit

```python
# Loop exits when predicate is satisfied
refinement = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write.").outputs("quality")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review.")
).loop_until(lambda s: s.get("quality") == "good", max_iterations=5)
```

## Fluent API

### Agent Configuration

```python
agent = (
    Agent("assistant")
    .model("gemini-2.5-flash")           # LLM model
    .instruct("You are helpful.")         # System instruction
    .describe("A helper agent")           # Description
    .tool(my_function)                    # Add tools (auto-wrapped)
    .before_model(log_fn)                 # Callbacks (additive)
    .after_model(audit_fn)
    .guardrail(safety_fn)                 # Registers both before+after
    .output_key("result")                 # Store output in state
    .outputs("result")                    # Alias for output_key
    .history("none")                      # Alias for include_contents
    .build()                              # -> LlmAgent
)
```

### Delegation (LLM-Driven Routing)

```python
# The coordinator's LLM decides when to delegate
coordinator = (
    Agent("coordinator")
    .model("gemini-2.5-flash")
    .instruct("Route tasks to the right specialist.")
    .delegate(Agent("math").model("gemini-2.5-flash").instruct("Solve math."))
    .delegate(Agent("code").model("gemini-2.5-flash").instruct("Write code."))
    .build()
)
```

### Cloning and Variants

```python
base = Agent("base").model("gemini-2.5-flash").instruct("Be helpful.")

# Clone — independent copy
math_agent = base.clone("math").instruct("Solve math.")

# with_() — immutable variant
creative = base.with_(name="creative", model="gemini-2.5-pro")
```

### Presets

```python
from adk_fluent.presets import Preset

production = Preset(model="gemini-2.5-flash", before_model=log_fn, after_model=audit_fn)

agent = Agent("service").instruct("Handle requests.").use(production).build()
```

### @agent Decorator

```python
from adk_fluent.decorators import agent

@agent("weather_bot", model="gemini-2.5-flash")
def weather_bot():
    """You help with weather queries."""

@weather_bot.tool
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

built = weather_bot.build()
```

### Typed State Keys

```python
from adk_fluent import StateKey

call_count = StateKey("call_count", scope="session", type=int, default=0)

# In callbacks/tools:
current = call_count.get(ctx)
call_count.increment(ctx)
```

### One-Shot Execution

```python
# Ask and get response (no Runner/Session boilerplate)
response = Agent("q").model("gemini-2.5-flash").instruct("Answer concisely.").ask("What is 2+2?")

# Batch execution
results = Agent("q").model("gemini-2.5-flash").instruct("Translate.").map(["Hello", "Goodbye"])
```

### Validation and Introspection

```python
agent = Agent("x").model("gemini-2.5-flash").instruct("Test.").validate()  # Catches errors early
print(agent.explain())  # Multi-line builder state summary
print(agent.to_yaml())  # Serialize to YAML
```

## Run with `adk web`

### Environment Setup

Before running any example, copy the `.env.example` and fill in your Google Cloud credentials:

```bash
cd examples
cp .env.example .env
# Edit .env with your values:
#   GOOGLE_CLOUD_PROJECT=your-project-id
#   GOOGLE_CLOUD_LOCATION=us-central1
#   GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

Every agent loads these variables automatically via `load_dotenv()`.

### Run an Example

```bash
cd examples
adk web simple_agent          # Basic agent
adk web weather_agent         # Agent with tools
adk web research_team         # Multi-agent pipeline
adk web real_world_pipeline   # Full expression language
adk web route_branching       # Deterministic routing
adk web delegate_pattern      # LLM-driven delegation
adk web operator_composition  # >> | * operators
```

29 runnable examples covering all features. See [`examples/`](examples/) for the full list.

## Cookbook

28 annotated examples in [`examples/cookbook/`](examples/cookbook/) with side-by-side Native ADK vs Fluent comparisons. Each file is also a runnable test:

```bash
pytest examples/cookbook/ -v
```

| # | Example | Feature |
|---|---------|---------|
| 01 | Simple Agent | Basic agent creation |
| 02 | Agent with Tools | Tool registration |
| 03 | Callbacks | Additive callback accumulation |
| 04 | Sequential Pipeline | Pipeline builder |
| 05 | Parallel FanOut | FanOut builder |
| 06 | Loop Agent | Loop builder |
| 07 | Team Coordinator | Sub-agent delegation |
| 08 | One-Shot Ask | `.ask()` execution |
| 09 | Streaming | `.stream()` execution |
| 10 | Cloning | `.clone()` deep copy |
| 11 | Inline Testing | `.test()` smoke tests |
| 12 | Guardrails | `.guardrail()` shorthand |
| 13 | Interactive Session | `.session()` context manager |
| 14 | Dynamic Forwarding | `__getattr__` field access |
| 15 | Production Runtime | Full agent setup |
| 16 | Operator Composition | `>>` `\|` `*` operators |
| 17 | Route Branching | Deterministic `Route` |
| 18 | Dict Routing | `>>` dict shorthand |
| 19 | Conditional Gating | `.proceed_if()` |
| 20 | Loop Until | `.loop_until()` |
| 21 | StateKey | Typed state descriptors |
| 22 | Presets | `Preset` + `.use()` |
| 23 | With Variants | `.with_()` immutable copy |
| 24 | @agent Decorator | Decorator syntax |
| 25 | Validate & Explain | `.validate()` `.explain()` |
| 26 | Serialization | `to_dict` / `to_yaml` |
| 27 | Delegate Pattern | `.delegate()` |
| 28 | Real-World Pipeline | Full composition |

## How It Works

adk-fluent is **auto-generated** from the installed ADK package:

```
scanner.py ──> manifest.json ──> seed_generator.py ──> seed.toml ──> generator.py ──> Python code
                                      ↑
                              seed.manual.toml
                              (hand-crafted extras)
```

1. **Scanner** introspects all ADK modules and produces `manifest.json`
2. **Seed Generator** classifies classes and produces `seed.toml` (merged with manual extras)
3. **Code Generator** emits fluent builders, `.pyi` type stubs, and test scaffolds

This means adk-fluent automatically stays in sync with ADK updates:

```bash
pip install --upgrade google-adk
just all   # Regenerate everything
just test  # Verify
```

## API Reference

Generated API docs are in [`docs/generated/api/`](docs/generated/api/):

- [`agent.md`](docs/generated/api/agent.md) — Agent, BaseAgent builders
- [`workflow.md`](docs/generated/api/workflow.md) — Pipeline, FanOut, Loop
- [`tool.md`](docs/generated/api/tool.md) — 40+ tool builders
- [`service.md`](docs/generated/api/service.md) — Session, artifact, memory services
- [`config.md`](docs/generated/api/config.md) — Configuration builders
- [`plugin.md`](docs/generated/api/plugin.md) — Plugin builders
- [`runtime.md`](docs/generated/api/runtime.md) — Runner, App builders

Migration guide: [`docs/generated/migration/from-native-adk.md`](docs/generated/migration/from-native-adk.md)

## Features

- **130+ builders** covering agents, tools, configs, services, plugins, planners, executors
- **Expression language**: `>>` (sequence), `|` (parallel), `*` (loop), `Route` (branch), `proceed_if` (gate)
- **Full IDE autocomplete** via `.pyi` type stubs
- **Zero-maintenance** `__getattr__` forwarding for any ADK field
- **Callback accumulation**: multiple `.before_model()` calls append, not replace
- **Typo detection**: misspelled methods raise `AttributeError` with suggestions
- **Deterministic routing**: `Route` evaluates predicates against session state (zero LLM calls)
- **One-shot execution**: `.ask()`, `.stream()`, `.session()`, `.map()` without Runner boilerplate
- **Presets**: reusable config bundles via `Preset` + `.use()`
- **Cloning**: `.clone()` and `.with_()` for independent variants
- **Validation**: `.validate()` catches config errors at definition time
- **Serialization**: `to_dict()`, `to_yaml()`, `from_dict()`, `from_yaml()`
- **@agent decorator**: FastAPI-style agent definition
- **Typed state**: `StateKey` with scope, type, and default

## Development

```bash
# Setup
uv venv .venv && source .venv/bin/activate
uv pip install google-adk pytest pyright

# Full pipeline: scan -> seed -> generate -> docs
just all

# Run tests (700+ tests)
just test

# Type check generated stubs
just typecheck

# Generate cookbook stubs for new builders
just cookbook-gen

# Convert cookbook to adk-web agent folders
just agents
```

## Publishing

Releases are published automatically to PyPI when a version tag is pushed:

```bash
# 1. Bump version in pyproject.toml
# 2. Commit and tag
git tag v0.2.0
git push origin v0.2.0
# 3. CI runs tests -> builds -> publishes to PyPI automatically
```

TestPyPI publishing is available manually via the GitLab CI web interface.

## License

MIT
