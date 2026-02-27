# Runnable Examples

adk-fluent ships with 49 standalone examples you can run directly with
`adk web`. Each example is a self-contained agent (or multi-agent system)
in its own directory under `examples/`.

## How to run

1. **Install dependencies:**

   ```bash
   pip install adk-fluent[examples]
   ```

2. **Configure your API key:**

   ```bash
   cp examples/.env.example examples/.env
   # Edit examples/.env and add your GOOGLE_API_KEY
   ```

3. **Launch any example:**

   ```bash
   cd examples
   adk web simple_agent
   ```

   This opens a local web UI where you can chat with the agent.

4. **Or run headless:**

   ```bash
   cd examples
   adk run simple_agent
   ```

## Example directory

Each example folder contains:

- `agent.py` — The agent definition (exports `root_agent`)
- `__init__.py` — Package marker
- Optional: `prompt.py`, `tools.py` — Helper modules for complex examples

## Simple examples

Standalone agents demonstrating individual features.

| Example | Description | Run command |
|---------|-------------|-------------|
| `simple_agent` | Minimal agent creation | `adk web simple_agent` |
| `agent_with_tools` | Attaching function tools | `adk web agent_with_tools` |
| `callbacks` | `before_model` / `after_model` callbacks | `adk web callbacks` |
| `sequential_pipeline` | Pipeline (SequentialAgent) | `adk web sequential_pipeline` |
| `parallel_fanout` | FanOut (ParallelAgent) | `adk web parallel_fanout` |
| `loop_agent` | Loop with max iterations | `adk web loop_agent` |
| `team_coordinator` | Coordinator with sub-agents | `adk web team_coordinator` |
| `one_shot_ask` | `.ask()` fire-and-forget | `adk web one_shot_ask` |
| `streaming` | `.stream()` token-by-token | `adk web streaming` |
| `cloning` | `.clone()` A/B testing | `adk web cloning` |
| `inline_testing` | `.test()` smoke tests | `adk web inline_testing` |
| `guardrails` | `.guardrail()` safety checks | `adk web guardrails` |
| `interactive_session` | `.session()` chat loop | `adk web interactive_session` |

## Operators & routing

Examples demonstrating the expression algebra and routing.

| Example | Description | Run command |
|---------|-------------|-------------|
| `operator_composition` | `>>`, `\|`, `*` operators | `adk web operator_composition` |
| `route_branching` | `Route` deterministic branching | `adk web route_branching` |
| `dict_routing` | `>> {"key": agent}` shorthand | `adk web dict_routing` |
| `conditional_gating` | `proceed_if` gates | `adk web conditional_gating` |
| `loop_until` | `loop_until` conditional exit | `adk web loop_until` |
| `until_operator` | `* until(pred)` operator | `adk web until_operator` |
| `dynamic_forwarding` | `__getattr__` field forwarding | `adk web dynamic_forwarding` |
| `fallback_operator` | `//` fallback chains | `adk web fallback_operator` |
| `full_algebra` | All operators combined | `adk web full_algebra` |

## Patterns & state

State management, presets, decorators, and serialization.

| Example | Description | Run command |
|---------|-------------|-------------|
| `state_transforms` | `S.*` factories | `adk web state_transforms` |
| `presets` | `Preset` reusable config | `adk web presets` |
| `with_variants` | `.with_()` immutable variants | `adk web with_variants` |
| `agent_decorator` | `@agent` decorator | `adk web agent_decorator` |
| `validate_explain` | `.validate()`, `.explain()` | `adk web validate_explain` |
| `serialization` | `to_dict`, `to_yaml` | `adk web serialization` |
| `delegate_pattern` | LLM-driven delegation | `adk web delegate_pattern` |
| `real_world_pipeline` | Full expression language | `adk web real_world_pipeline` |
| `function_steps` | `>> fn` plain functions | `adk web function_steps` |
| `typed_output` | `@ Schema` operator | `adk web typed_output` |

## Primitives

Advanced primitives for observation, testing, and control flow.

| Example | Description | Run command |
|---------|-------------|-------------|
| `tap_observation` | `tap` pure observation | `adk web tap_observation` |
| `expect_assertions` | `expect()` state contracts | `adk web expect_assertions` |
| `mock_testing` | `mock_backend()` testing | `adk web mock_testing` |
| `retry_if` | `retry_if` on failures | `adk web retry_if` |
| `map_over` | `map_over` batch iteration | `adk web map_over` |
| `timeout` | `timeout` deadlines | `adk web timeout` |
| `gate_approval` | `gate` human approval | `adk web gate_approval` |
| `race` | `race` first-to-finish | `adk web race` |
| `production_runtime` | `to_app()` + middleware | `adk web production_runtime` |

## Real-world ports

Multi-agent systems ported from [Google ADK Samples](https://github.com/google/adk-samples).

| Example | Description | Run command |
|---------|-------------|-------------|
| `brand_search` | Router with nested sub-agents | `adk web brand_search` |
| `deep_search` | Multi-stage research pipeline | `adk web deep_search` |
| `financial_advisor` | Multi-agent financial advisory | `adk web financial_advisor` |
| `llm_auditor` | Sequential pipeline with callbacks | `adk web llm_auditor` |
| `research_team` | Multi-agent research pipeline | `adk web research_team` |
| `short_movie` | Campfire story creator | `adk web short_movie` |
| `travel_concierge` | Multi-agent travel advisory | `adk web travel_concierge` |
| `weather_agent` | Weather lookup agent | `adk web weather_agent` |

## Cookbook examples

The `examples/cookbook/` directory contains 58 annotated examples that
appear in the {doc}`Cookbook </generated/cookbook/index>` documentation.
These are designed for reading and learning rather than interactive use.

Run the cookbook test suite:

```bash
pytest examples/cookbook/ -v
```
