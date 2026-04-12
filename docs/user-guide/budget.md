# Budget

The `adk_fluent._budget` package is adk-fluent's **cumulative token
budget** mechanism. It answers a question `C.budget()` and `C.rolling()`
cannot: *"Across the whole session, how much have I spent, and what
should I do when I cross a threshold?"*

`C.*` transforms compress context at instruction time — they shape what
the LLM sees on each turn. `_budget` operates one level up: it tracks
cumulative usage across turns and fires callbacks (warn, compress,
abort) when utilisation crosses configurable thresholds.

## The three pieces

| Type | Role | Mutable? |
| --- | --- | --- |
| `Threshold` | A checkpoint — percent + callback + recurring flag. | frozen |
| `BudgetPolicy` | Declarative bundle of `max_tokens` + thresholds. | frozen |
| `BudgetMonitor` | Live tracker. Records usage, fires thresholds. | mutable |
| `BudgetPlugin` | ADK `BasePlugin` that auto-records every LLM call. | wraps a monitor |

The split matters: a `BudgetPolicy` is a pure value you can ship via
YAML, hash, or hold as a module-level constant. Calling
`policy.build_monitor()` hands you a fresh tracker every time — two
sessions never share state by accident.

## Quick start

### Manual wiring (direct API)

```python
from adk_fluent import Agent, BudgetMonitor

monitor = BudgetMonitor(max_tokens=200_000)
monitor.on_threshold(
    0.8,
    lambda m: print(f"warn: {m.utilization:.0%} used"),
)
monitor.on_threshold(
    0.95,
    lambda m: compress_session_state(),
)

agent = (
    Agent("coder", "gemini-2.5-flash")
    .instruct("You are a senior engineer.")
    .after_model(monitor.after_model_hook())
)
```

### Policy + plugin (session-scoped)

For a whole agent tree — root agent, sub-agents, subagent specialists —
use a policy and install it as a plugin. The plugin fires
`after_model_callback` for every LLM call in the invocation tree, so
you never have to thread a monitor through each builder.

```python
from adk_fluent import Agent, H, Threshold

policy = (
    H.budget_policy(200_000)
    .with_threshold(0.8, lambda m: print("warn"))
    .with_threshold(0.95, compress_handler)
)

plugin = H.budget_plugin(policy)

app = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("...")
    .plugin(plugin)
    .build()
)

# Inspect usage at any time
print(plugin.monitor.summary())
```

## `Threshold`

A frozen dataclass:

```python
Threshold(
    percent: float,                 # 0.0 < percent <= 1.0
    callback: Callable[[monitor], Any],
    recurring: bool = False,        # fire on every record above threshold
)
```

- **Non-recurring** (default): the callback fires once per reset cycle.
- **Recurring**: fires on every record above the threshold — useful for
  metric streaming or watchdogs.

Invalid `percent` (≤ 0.0 or > 1.0) raises `ValueError` at construction
time.

## `BudgetPolicy`

```python
BudgetPolicy(
    max_tokens: int = 200_000,
    thresholds: tuple[Threshold, ...] = (),
)
```

Methods:

- `.build_monitor() -> BudgetMonitor` — materialise a fresh tracker.
- `.with_threshold(percent, callback, *, recurring=False)` — return a
  copy with an extra threshold appended. Pure; the original is
  unchanged.

Policies are frozen — you can hash them, diff them, and share them
across threads without worrying about accidental mutation.

## `BudgetMonitor`

The live tracker. Methods worth knowing:

| Method | Purpose |
| --- | --- |
| `.record_usage(input, output)` | Record one call's usage. Checks thresholds. |
| `.on_threshold(percent, cb, *, recurring=False)` | Chainable threshold registration. |
| `.add_threshold(Threshold)` | Chainable — for pre-built thresholds. |
| `.with_bus(bus)` | Emit `CompressionTriggered` via an EventBus. |
| `.after_model_hook()` | Returns an `after_model` callback for manual wiring. |
| `.reset()` | Clear cumulative count and re-arm all thresholds. |
| `.adjust(new_count)` | Set the count directly (e.g. after compression). Thresholds above the new level are re-armed. |

Properties:

- `max_tokens`, `current_tokens`, `remaining`
- `utilization` — fraction in `[0, 1]`
- `turn_count`, `avg_tokens_per_turn`, `estimated_turns_remaining`
- `thresholds` — immutable tuple view
- `thresholds_fired()` — how many thresholds have fired in this cycle
- `summary()` — dict snapshot

## `BudgetPlugin`

An ADK `BasePlugin` whose only job is to record usage after every model
call in the session:

```python
BudgetPlugin(
    policy_or_monitor: BudgetPolicy | BudgetMonitor,
    *,
    name: str = "adkf_budget_plugin",
)
```

It accepts either a policy (builds a fresh monitor) or an existing
monitor (useful when you want to share one tracker between a plugin and
other code, e.g. an event bus subscriber).

The live tracker is available at `plugin.monitor` for tests and runtime
introspection.

## Composition

Because `BudgetMonitor` is a plain Python object, it composes with every
other foundation package:

- **Event bus** — `monitor.with_bus(bus)` emits `CompressionTriggered`.
- **Compression** — the threshold callback can invoke a
  `ContextCompressor`, switch `C.window(n)` strategies, or trim
  state.
- **Permissions** — a threshold callback can flip `PermissionMode`
  to `plan` when the budget is almost out, forcing the agent to
  stop calling expensive tools.

## Testing

Monitors and plugins are easy to test because neither requires a live
model:

```python
from types import SimpleNamespace
import asyncio
from adk_fluent import BudgetPlugin, BudgetPolicy, Threshold

fired: list[float] = []
policy = BudgetPolicy(
    max_tokens=100,
    thresholds=(Threshold(percent=0.5, callback=lambda m: fired.append(m.utilization)),),
)
plugin = BudgetPlugin(policy)

asyncio.run(
    plugin.after_model_callback(
        callback_context=None,
        llm_response=SimpleNamespace(
            usage_metadata=SimpleNamespace(
                prompt_token_count=30,
                candidates_token_count=30,
            )
        ),
    )
)
assert fired == [0.6]
```

## Design notes

- Thresholds are **frozen** — they carry no mutable state. Firing state
  lives inside the tracker as a `set[int]` keyed by threshold position,
  so a single `Threshold` instance can be shared across many monitors
  without leaking state.
- `BudgetMonitor` swallows exceptions from threshold callbacks (via
  `contextlib.suppress`) so a faulty handler never crashes the agent.
- `BudgetPlugin` lives in `adk_fluent._budget` but is re-exported from
  `adk_fluent._harness` for compatibility with existing harness code.
