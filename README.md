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

Nine operators compose any agent topology:

| Operator | Meaning | ADK Type |
|----------|---------|----------|
| `a >> b` | Sequence | `SequentialAgent` |
| `a >> fn` | Function step | Zero-cost transform |
| `a \| b` | Parallel | `ParallelAgent` |
| `a * 3` | Loop (fixed) | `LoopAgent` |
| `a * until(pred)` | Loop (conditional) | `LoopAgent` + checkpoint |
| `a @ Schema` | Typed output | `output_schema` |
| `a // b` | Fallback | First-success chain |
| `Route("key").eq(...)` | Branch | Deterministic routing |
| `S.pick(...)`, `S.rename(...)` | State transforms | Dict operations via `>>` |

All operators are **immutable** -- sub-expressions can be safely reused:

```python
review = agent_a >> agent_b
pipeline_1 = review >> agent_c  # Independent
pipeline_2 = review >> agent_d  # Independent
```

### Function Steps

Plain Python functions compose with `>>` as zero-cost workflow nodes (no LLM call):

```python
def merge_research(state):
    return {"research": state["web"] + "\n" + state["papers"]}

pipeline = web_agent >> merge_research >> writer_agent
```

### Typed Output

`@` binds a Pydantic schema as the agent's output contract:

```python
from pydantic import BaseModel

class Report(BaseModel):
    title: str
    body: str

agent = Agent("writer").model("gemini-2.5-flash").instruct("Write.") @ Report
```

### Fallback Chains

`//` tries each agent in order -- first success wins:

```python
answer = (
    Agent("fast").model("gemini-2.0-flash").instruct("Quick answer.")
    // Agent("thorough").model("gemini-2.5-pro").instruct("Detailed answer.")
)
```

### Conditional Loops

`* until(pred)` loops until a predicate on session state is satisfied:

```python
from adk_fluent import until

loop = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write.").outputs("quality")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review.")
) * until(lambda s: s.get("quality") == "good", max=5)
```

### State Transforms

`S` factories return dict transforms that compose with `>>`:

```python
from adk_fluent import S

pipeline = (
    (web_agent | scholar_agent)
    >> S.merge("web", "scholar", into="research")
    >> S.default(confidence=0.0)
    >> S.rename(research="input")
    >> writer_agent
)
```

| Factory | Purpose |
|---------|---------|
| `S.pick(*keys)` | Keep only specified keys |
| `S.drop(*keys)` | Remove specified keys |
| `S.rename(**kw)` | Rename keys |
| `S.default(**kw)` | Fill missing keys |
| `S.merge(*keys, into=)` | Combine keys |
| `S.transform(key, fn)` | Map a single value |
| `S.compute(**fns)` | Derive new keys |
| `S.guard(pred)` | Assert invariant |
| `S.log(*keys)` | Debug-print |

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

### Full Composition

All operators compose into a single expression:

```python
from pydantic import BaseModel
from adk_fluent import Agent, S, until

class Report(BaseModel):
    title: str
    body: str
    confidence: float

pipeline = (
    (   Agent("web").model("gemini-2.5-flash").instruct("Search web.")
      | Agent("scholar").model("gemini-2.5-flash").instruct("Search papers.")
    )
    >> S.merge("web", "scholar", into="research")
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write.") @ Report
       // Agent("writer_b").model("gemini-2.5-pro").instruct("Write.") @ Report
    >> (
        Agent("critic").model("gemini-2.5-flash").instruct("Score.").outputs("confidence")
        >> Agent("reviser").model("gemini-2.5-flash").instruct("Improve.")
    ) * until(lambda s: s.get("confidence", 0) >= 0.85, max=4)
)
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
adk web function_steps        # >> fn (function nodes)
adk web until_operator        # * until(pred)
adk web typed_output          # @ Schema
adk web fallback_operator     # // fallback
adk web state_transforms      # S.pick, S.rename, ...
adk web full_algebra          # All operators together
```

35 runnable examples covering all features. See [`examples/`](examples/) for the full list.

## Cookbook

34 annotated examples in [`examples/cookbook/`](examples/cookbook/) with side-by-side Native ADK vs Fluent comparisons. Each file is also a runnable test:

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
| 29 | Function Steps | `>> fn` zero-cost transforms |
| 30 | Until Operator | `* until(pred)` conditional loops |
| 31 | Typed Output | `@ Schema` output contracts |
| 32 | Fallback Operator | `//` first-success chains |
| 33 | State Transforms | `S.pick`, `S.rename`, `S.merge`, ... |
| 34 | Full Algebra | All operators composed together |

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
- **Expression algebra**: `>>` (sequence), `|` (parallel), `*` (loop), `@` (typed output), `//` (fallback), `>> fn` (transforms), `S` (state ops), `Route` (branch)
- **State transforms**: `S.pick`, `S.drop`, `S.rename`, `S.default`, `S.merge`, `S.transform`, `S.compute`, `S.guard`
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

# Run tests (750+ tests)
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
