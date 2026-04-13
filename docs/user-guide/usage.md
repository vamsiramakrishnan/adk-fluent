# Usage tracking

The `adk_fluent._usage` package is adk-fluent's **session-scoped LLM
usage tracker**. It answers three questions that come up once an agent
tree gets non-trivial:

1. How many tokens did the whole session consume?
2. How much did each agent in the tree contribute?
3. Given the model mix, what did it actually cost?

`_usage` is a peer of `_budget`. `_budget` is the *enforcement* layer —
thresholds, hard caps, abort callbacks. `_usage` is the *accounting*
layer — every call, every agent, every dollar, persisted in one place
you can query at the end of the session (or mid-run).

## The four pieces

| Type | Role | Mutable? |
| --- | --- | --- |
| `TurnUsage` | Frozen record of one LLM call (tokens, model, agent, duration). | frozen |
| `ModelRate` | USD rates per million tokens for one model. | frozen |
| `CostTable` | Frozen mapping `{model → ModelRate}` with `"*"` wildcard fallback. | frozen |
| `UsageTracker` | Mutable aggregator. Owns the list of turns, exposes cumulative totals + per-agent breakdown. | mutable |
| `UsagePlugin` | ADK `BasePlugin` that auto-records every LLM call in the invocation tree. | wraps a tracker |

The split follows the same principle as the rest of adk-fluent: the
*decision* pieces (`TurnUsage`, `ModelRate`, `CostTable`) are frozen
value objects you can ship via config, and the *state* (`UsageTracker`)
is separated from them so two sessions never share history by accident.

## Quick start

### Per-agent callback

If you only want to track one agent, attach `tracker.callback()` to its
`after_model` hook directly:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, UsageTracker

tracker = UsageTracker()

agent = (
    Agent("writer", "gemini-2.5-flash")
    .instruct("Draft a blog post about AI agents.")
    .after_model(tracker.callback())
    .build()
)

await agent.ask_async("Write about context engineering")

print(tracker.summary())
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, UsageTracker } from "adk-fluent-ts";

const tracker = new UsageTracker();

const agent = new Agent("writer", "gemini-2.5-flash")
  .instruct("Draft a blog post about AI agents.")
  .afterModel(tracker.callback())
  .build();

await agent.askAsync("Write about context engineering");

console.log(tracker.summary());
```
:::
::::

### Session-wide plugin (recommended)

For a multi-agent app, install the plugin on the root runtime. ADK
`BasePlugin` instances are session-scoped and inherited across
sub-agents, so a single install captures the root agent, transfer
targets, and every subagent specialist spawned via the `Task` tool.

```python
from adk_fluent import H, Runner, App

plugin = H.usage_plugin()

runner = (
    Runner()
    .app(
        App("research-agent")
        .root(my_agent)
        .plugin(plugin)
    )
    .build()
)

await runner.run_async("What's new in agent frameworks?")

# Inspect after the run:
print(plugin.tracker.summary())
for name, usage in plugin.tracker.by_agent().items():
    print(f"{name:20s}  in={usage.input_tokens:>7}  out={usage.output_tokens:>7}  calls={usage.calls}")
```

`H.usage_plugin()` accepts an optional pre-built tracker (so you can
share it with a `UsageTracker` callback on a specific agent) and a
custom `name` for the ADK plugin registry.

## Cost tables

`UsageTracker` on its own only counts tokens. Feed it a `CostTable` to
get a USD estimate.

### Flat table (one model or uniform rate)

```python
from adk_fluent import CostTable, UsageTracker

tracker = UsageTracker(cost_table=CostTable.flat(0.075, 0.30))
```

### Per-model rates

```python
from adk_fluent import CostTable, ModelRate

table = CostTable(
    rates={
        "gemini-2.5-flash": ModelRate(input_per_million=0.075, output_per_million=0.30),
        "gemini-2.5-pro":   ModelRate(input_per_million=3.50,  output_per_million=10.50),
        "*":                ModelRate(input_per_million=1.00,  output_per_million=3.00),
    }
)
```

The `"*"` entry is the default for any model not listed explicitly.

### Via the H namespace

`H.cost_table(**rates)` takes keyword arguments whose values are
`(input_per_million, output_per_million)` tuples. Because Python
keyword names cannot contain dots, use underscores or build the table
manually for models whose IDs include special characters:

```python
from adk_fluent import H

table = H.cost_table(
    **{
        "gemini_2_5_flash": (0.075, 0.30),
        "gemini_2_5_pro":   (3.50, 10.50),
    }
)
```

### Immutability

`CostTable` wraps its `rates` in a `MappingProxyType`, so the table is
genuinely frozen:

```python
table = CostTable.flat(1.0, 2.0)
table.rates["new_model"] = ModelRate(...)  # TypeError
```

Use `table.with_rate(model, input_per_million=..., output_per_million=...)`
to get a new table with an extra rate without mutating the original.

## Per-agent breakdown

The tracker records the `agent_name` on every turn (extracted from
`callback_context.agent_name` by `tracker.callback()` and
`UsagePlugin.after_model_callback`). Call `tracker.by_agent()` to split
usage by agent:

```python
tracker = plugin.tracker
by_agent = tracker.by_agent()

for name, usage in sorted(by_agent.items(), key=lambda kv: -kv[1].total_tokens):
    print(f"{name:30s}  tokens={usage.total_tokens:>8}  calls={usage.calls}")
```

Each value is a frozen `AgentUsage(agent_name, input_tokens,
output_tokens, calls)`. Turns recorded without an agent name are
grouped under the empty-string key `""`.

## Interaction with `_budget`

`_budget` and `_usage` are orthogonal. You typically want both:

```python
from adk_fluent import BudgetPolicy, H, Threshold

budget = BudgetPolicy(
    max_tokens=200_000,
    thresholds=(
        Threshold(percent=0.80, callback=lambda **_: print("warn: 80%")),
    ),
)

app = (
    App("multi-agent")
    .root(my_agent)
    .plugin(H.budget_plugin(budget))     # enforcement
    .plugin(H.usage_plugin())            # accounting
)
```

The budget plugin decides *whether* to keep going; the usage plugin
records *what* actually happened. They share the same LLM callback
surface but maintain independent state.

## Manual records

You do not have to go through the ADK callback surface. The tracker has
a public `record()` method that you can call from a custom backend,
replay harness, or unit test:

```python
tracker = UsageTracker()
tracker.record(
    input_tokens=1234,
    output_tokens=567,
    model="gemini-2.5-flash",
    agent_name="coordinator",
    duration_ms=842.3,
)
```

This is how the test suite drives the tracker in isolation — no ADK
runtime required.
