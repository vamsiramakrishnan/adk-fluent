# Runnable Examples

adk-fluent ships with 49 standalone examples you can run directly with
`adk web`. Each example is a self-contained agent (or multi-agent system)
in its own directory under `examples/`.

## Copy-paste-run contract

Every example in this project follows a contract:

- **Interactive examples** (`examples/<name>/agent.py`): copy the directory,
  run `adk web <name>`, and it works. The only prerequisites are
  installing the package and setting up your `.env` file (see below).
- **Cookbook examples** (`examples/cookbook/NN_name.py`): these are
  **equivalence tests**, not standalone scripts. They prove that fluent
  builders produce identical ADK objects to native code. Run them with
  `pytest examples/cookbook/ -v` — no API key needed, no network calls.

If any example fails to meet this contract, please
[file an issue](https://github.com/vamsiramakrishnan/adk-fluent/issues).

## Prerequisites

Before running any interactive example, complete this one-time setup:

**1. Install the package with example dependencies:**

```bash
pip install adk-fluent[examples]
```

This installs `adk-fluent`, `google-adk`, and `python-dotenv`.

**2. Set up Google Cloud / Vertex AI credentials:**

```bash
cp examples/.env.example examples/.env
```

Edit `examples/.env` and fill in:

```bash
# Required: your Google Cloud project ID
GOOGLE_CLOUD_PROJECT=your-project-id

# Required: Vertex AI region
GOOGLE_CLOUD_LOCATION=us-central1

# Required: enable Vertex AI backend
GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

You also need `gcloud` authenticated:

```bash
gcloud auth application-default login
```

**3. Verify your setup works:**

```bash
cd examples
adk web simple_agent
```

If the web UI opens and the agent responds, you are ready.

## How to run

```bash
cd examples

# Interactive web UI
adk web simple_agent

# Headless CLI mode
adk run simple_agent

# Run all cookbook equivalence tests (no API key needed)
pytest cookbook/ -v
```

## Example directory

Each example folder contains:

- `agent.py` — The agent definition (exports `root_agent`)
- `__init__.py` — Package marker
- Optional: `prompt.py`, `tools.py` — Helper modules for complex examples

## Simple examples

Standalone agents demonstrating individual features.

| Example               | Description                              | Prerequisites | Run command                   |
| --------------------- | ---------------------------------------- | ------------- | ----------------------------- |
| `simple_agent`        | Minimal agent creation                   | .env          | `adk web simple_agent`        |
| `agent_with_tools`    | Attaching function tools                 | .env          | `adk web agent_with_tools`    |
| `callbacks`           | `before_model` / `after_model` callbacks | .env          | `adk web callbacks`           |
| `sequential_pipeline` | Pipeline (SequentialAgent)               | .env          | `adk web sequential_pipeline` |
| `parallel_fanout`     | FanOut (ParallelAgent)                   | .env          | `adk web parallel_fanout`     |
| `loop_agent`          | Loop with max iterations                 | .env          | `adk web loop_agent`          |
| `team_coordinator`    | Coordinator with sub-agents              | .env          | `adk web team_coordinator`    |
| `one_shot_ask`        | `.ask()` fire-and-forget                 | .env          | `adk web one_shot_ask`        |
| `streaming`           | `.stream()` token-by-token               | .env          | `adk web streaming`           |
| `cloning`             | `.clone()` A/B testing                   | .env          | `adk web cloning`             |
| `inline_testing`      | `.test()` smoke tests                    | .env          | `adk web inline_testing`      |
| `guardrails`          | `.guard()` safety checks                 | .env          | `adk web guardrails`          |
| `interactive_session` | `.session()` chat loop                   | .env          | `adk web interactive_session` |

## Operators & routing

Examples demonstrating the expression algebra and routing.

| Example                | Description                     | Prerequisites | Run command                    |
| ---------------------- | ------------------------------- | ------------- | ------------------------------ |
| `operator_composition` | `>>`, `\|`, `*` operators       | .env          | `adk web operator_composition` |
| `route_branching`      | `Route` deterministic branching | .env          | `adk web route_branching`      |
| `dict_routing`         | `>> {"key": agent}` shorthand   | .env          | `adk web dict_routing`         |
| `conditional_gating`   | `proceed_if` gates              | .env          | `adk web conditional_gating`   |
| `loop_until`           | `loop_until` conditional exit   | .env          | `adk web loop_until`           |
| `until_operator`       | `* until(pred)` operator        | .env          | `adk web until_operator`       |
| `dynamic_forwarding`   | `__getattr__` field forwarding  | .env          | `adk web dynamic_forwarding`   |
| `fallback_operator`    | `//` fallback chains            | .env          | `adk web fallback_operator`    |
| `full_algebra`         | All operators combined          | .env          | `adk web full_algebra`         |

## Patterns & state

State management, presets, decorators, and serialization.

| Example               | Description                   | Prerequisites | Run command                   |
| --------------------- | ----------------------------- | ------------- | ----------------------------- |
| `state_transforms`    | `S.*` factories               | .env          | `adk web state_transforms`    |
| `presets`             | `Preset` reusable config      | .env          | `adk web presets`             |
| `with_variants`       | `.with_()` immutable variants | .env          | `adk web with_variants`       |
| `agent_decorator`     | `@agent` decorator            | .env          | `adk web agent_decorator`     |
| `validate_explain`    | `.validate()`, `.explain()`   | .env          | `adk web validate_explain`    |
| `serialization`       | `to_dict`, `to_yaml`          | .env          | `adk web serialization`       |
| `delegate_pattern`    | LLM-driven agent_tool         | .env          | `adk web delegate_pattern`    |
| `real_world_pipeline` | Full expression language      | .env          | `adk web real_world_pipeline` |
| `function_steps`      | `>> fn` plain functions       | .env          | `adk web function_steps`      |
| `typed_output`        | `@ Schema` operator           | .env          | `adk web typed_output`        |

## Primitives

Advanced primitives for observation, testing, and control flow.

| Example              | Description                | Prerequisites | Run command                  |
| -------------------- | -------------------------- | ------------- | ---------------------------- |
| `tap_observation`    | `tap` pure observation     | .env          | `adk web tap_observation`    |
| `expect_assertions`  | `expect()` state contracts | .env          | `adk web expect_assertions`  |
| `mock_testing`       | `mock_backend()` testing   | .env          | `adk web mock_testing`       |
| `retry_if`           | `loop_while` on failures   | .env          | `adk web retry_if`           |
| `map_over`           | `map_over` batch iteration | .env          | `adk web map_over`           |
| `timeout`            | `timeout` deadlines        | .env          | `adk web timeout`            |
| `gate_approval`      | `gate` human approval      | .env          | `adk web gate_approval`      |
| `race`               | `race` first-to-finish     | .env          | `adk web race`               |
| `production_runtime` | `to_app()` + middleware    | .env          | `adk web production_runtime` |

## Real-world ports

Multi-agent systems ported from [Google ADK Samples](https://github.com/google/adk-samples).

| Example             | Description                        | Prerequisites | Run command                 |
| ------------------- | ---------------------------------- | ------------- | --------------------------- |
| `brand_search`      | Router with nested sub-agents      | .env          | `adk web brand_search`      |
| `deep_search`       | Multi-stage research pipeline      | .env          | `adk web deep_search`       |
| `financial_advisor` | Multi-agent financial advisory     | .env          | `adk web financial_advisor` |
| `llm_auditor`       | Sequential pipeline with callbacks | .env          | `adk web llm_auditor`       |
| `research_team`     | Multi-agent research pipeline      | .env          | `adk web research_team`     |
| `short_movie`       | Campfire story creator             | .env          | `adk web short_movie`       |
| `travel_concierge`  | Multi-agent travel advisory        | .env          | `adk web travel_concierge`  |
| `weather_agent`     | Weather lookup agent               | .env          | `adk web weather_agent`     |

## Cookbook examples

The `examples/cookbook/` directory contains 58 annotated examples that
appear in the {doc}`Cookbook </generated/cookbook/index>` documentation.

These are **equivalence tests** — they verify that fluent builders
produce identical ADK objects to native constructors. They do **not**
call any LLM APIs, so no API key or `.env` file is needed.

```bash
# Run all cookbook tests
pytest examples/cookbook/ -v

# Run a single example
pytest examples/cookbook/01_simple_agent.py -v
```
