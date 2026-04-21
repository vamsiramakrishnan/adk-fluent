# Design: API Surface v2 — Fluent DX Refinements

> **Status: COMPLETE** (2026-02-27 audit) — All refinements shipped in v0.8.0.

**Date:** 2026-02-25
**Version:** 0.8.0 (all changes non-breaking)
**Principle:** Name things for what they DO, one obvious way, progressive disclosure.

## Philosophy

Three rules borrowed from the best Python APIs (requests, click, pydantic):

1. **Verbs reveal intent** — `save_as("key")` not `outputs("key")`, `stay()` not `disallow_transfer_to_parent(True)`
1. **One way per concept** — deprecate redundant paths, don't add more
1. **Progressive disclosure** — Tier 1 imports for 90% of users, Tier 2/3 for power users

**Strategy:** Surgical aliases + deprecations. Zero breaking changes. Add the better name, deprecate the old one, remove in v1.0. All changes flow through the seed → codegen pipeline since builders are generated.

______________________________________________________________________

## Fix 1: `outputs("key")` → `save_as("key")`

### Problem

`.outputs("key")` sounds like "what shape comes out" — users conflate it with `output_schema`. It actually means "store my response text in `state[key]`."

### Solution

```python
# Before — ambiguous
agent.outputs("summary")

# After — verb reveals intent
agent.save_as("summary")
```

### Mechanism

Add `save_as` as a new alias for `output_key` in the seed. Move `outputs` to `deprecated_aliases`.

```toml
# seed.manual.toml additions
[builders.Agent.aliases]
save_as = "output_key"

[builders.Agent.deprecated_aliases]
outputs = { field = "output_key", use = "save_as" }
```

### Field docs

```toml
[field_docs]
save_as = "Session state key where the agent's response text is stored. Downstream agents and state transforms can read this key via ``state['key']``. Alias for ``output_key``."
```

### Generated code

```python
# New method
def save_as(self, value: str | None) -> Self:
    """Session state key where the agent's response text is stored..."""
    self._config["output_key"] = value
    return self

# Deprecated method (still works, warns)
def outputs(self, value: str | None) -> Self:
    """Deprecated: use .save_as() instead."""
    import warnings
    warnings.warn(
        ".outputs() is deprecated, use .save_as() instead",
        DeprecationWarning, stacklevel=2,
    )
    self._config["output_key"] = value
    return self
```

### @ operator clarity

With this rename, the operator/method distinction becomes self-documenting:

```python
agent @ Invoice           # "agent outputs Invoice-shaped data" (schema)
agent.save_as("result")   # "save the response as 'result' in state" (storage)
agent @ Invoice.save_as("parsed")  # both — crystal clear
```

______________________________________________________________________

## Fix 2: `history()` / `include_history()` → `context()`

### Problem

Three ways to control conversation context:

- `.history(n)` — limits turn count
- `.include_history(False)` — boolean toggle
- `.context(C.none())` — full context control via C module

### Solution

The `C` module is the right abstraction. It already exists, composes, and is more powerful than the others.

```python
# Before — which do I use?
agent.history(5)
agent.include_history(False)
agent.context(C.none())

# After — one obvious way
agent.context(C.last(5))       # replaces history(5)
agent.context(C.none())        # replaces include_history(False)
agent.context(C.user_only())   # new capability, same API
```

### Mechanism

Move `history` and `include_history` to `deprecated_aliases` in the seed.

```toml
[builders.Agent.deprecated_aliases]
history = { field = "include_contents", use = "context" }
include_history = { field = "include_contents", use = "context" }
```

### Generated code

```python
def history(self, value) -> Self:
    """Deprecated: use .context() instead. See the C module for context transforms."""
    import warnings
    warnings.warn(
        ".history() is deprecated, use .context() instead",
        DeprecationWarning, stacklevel=2,
    )
    self._config["include_contents"] = value
    return self
```

______________________________________________________________________

## Fix 3: `disallow_transfer_to_*` → `stay()` / `no_peers()`

### Problem

`disallow_transfer_to_parent(True)` is a double-negative boolean. Cognitive load to parse.

### Solution

```python
# Before — double negative
agent.disallow_transfer_to_parent(True)
agent.disallow_transfer_to_peers(True)

# After — reads like English
agent.isolate()    # both flags (already shipped v0.7.0 ✓)
agent.stay()       # just parent direction
agent.no_peers()   # just peer direction
```

### Mechanism

Add `stay` and `no_peers` extras in seed.manual.toml, wired to helpers.

```toml
[[builders.Agent.extras]]
name = "stay"
signature = "(self) -> Self"
doc = "Prevent this agent from transferring back to its parent. Use for agents that should complete their work before returning."
behavior = "runtime_helper"
helper_func = "_stay_agent"
see_also = ["Agent.isolate", "Agent.no_peers"]

[[builders.Agent.extras]]
name = "no_peers"
signature = "(self) -> Self"
doc = "Prevent this agent from transferring to sibling agents. The agent can still return to its parent."
behavior = "runtime_helper"
helper_func = "_no_peers_agent"
see_also = ["Agent.isolate", "Agent.stay"]
```

### Helper functions (`_helpers.py`)

```python
def _stay_agent(builder):
    """Prevent this agent from transferring back to its parent."""
    builder._config["disallow_transfer_to_parent"] = True
    return builder

def _no_peers_agent(builder):
    """Prevent this agent from transferring to sibling agents."""
    builder._config["disallow_transfer_to_peers"] = True
    return builder
```

______________________________________________________________________

## Fix 4: `static_instruct()` → deprecate

### Problem

`static()` and `static_instruct()` do the same thing. Redundant.

### Solution

Keep `.static()`, deprecate `.static_instruct()`.

```toml
[builders.Agent.deprecated_aliases]
static_instruct = { field = "static_instruction", use = "static" }
```

Remove `static_instruct` from `[builders.Agent.aliases]`.

______________________________________________________________________

## Fix 5: `_if` callbacks — Docs, not API change

### Problem

16 `_if` variants seem like bloat. But they're auto-generated, standard in fluent builders, and useful.

### Solution

No API change. Improve docs:

- Enrich `.pyi` stub docstrings for `_if` variants via `field_docs`
- Add cookbook example showing conditional callbacks

### Field docs addition

```toml
[field_docs]
# Callback _if variants get a shared doc pattern:
# The generator already produces docs like "Append callback to X only if condition is True."
# No change needed — current docs are adequate.
```

______________________________________________________________________

## Fix 6: Topology naming — Document, don't change

### Problem

`sub_agent`, `step`, `branch` seem redundant.

### Audit result

- `Pipeline.step()` — exists, correct metaphor ✓
- `Loop.step()` — exists, correct metaphor ✓
- `FanOut.branch()` — exists, correct metaphor ✓
- `FanOut.step()` — does NOT exist (good) ✓
- `Agent.transfer_to()` — universal low-level method ✓
- `Agent.delegate()` — different mechanism (AgentTool wrapping) ✓

### Solution

Current state is correct. No code change. Add a "Choosing the right method" table to the transfer control user guide.

| Builder  | Method              | Metaphor                        |
| -------- | ------------------- | ------------------------------- |
| Pipeline | `.step(agent)`      | Sequential step in a chain      |
| FanOut   | `.branch(agent)`    | Parallel branch                 |
| Loop     | `.step(agent)`      | Step that repeats               |
| Agent    | `.transfer_to(agent)` | Generic child agent             |
| Agent    | `.delegate(agent)`  | Tool-wrapped agent (LLM routes) |

______________________________________________________________________

## Fix 7: Expression readability — Convention, not API

### Problem

Complex operator expressions like `(a >> b >> c) | (d >> e) * until(done)` become hard to parse.

### Solution

No API change. Document the "name your pipelines" pattern:

```python
# ❌ Wall of operators
flow = (researcher >> analyst >> writer) | (fact_checker >> editor) * until(approved)

# ✅ Named sub-expressions
research = researcher >> analyst >> writer
review = (fact_checker >> editor) * until(approved)
flow = research | review
```

Add "Pipeline Readability" section to the user guide.

______________________________________________________________________

## Fix 8: `Agent.route()` factory

### Problem

`Route` requires a separate import and construction. Not discoverable from the `Agent` class.

### Solution

Add `route` as a classmethod-like extra on Agent that returns a Route instance:

```python
# Before
from adk_fluent import Route
router = Route("dispatch").when("status == 'urgent'", urgent).default(normal)

# After — discoverable
from adk_fluent import Agent
router = Agent.route("dispatch").when("status == 'urgent'", urgent).default(normal)
```

### Mechanism

Add a `route` extra with `behavior = "runtime_helper"` that creates and returns a Route.

```toml
[[builders.Agent.extras]]
name = "route"
signature = "(self, name: str | None = None) -> Any"
doc = "Create a Route builder for deterministic state-based branching. Returns a Route instance."
behavior = "runtime_helper"
helper_func = "_create_route"
```

Wait — this should be a classmethod/staticmethod, not an instance method. The pattern is `Agent.route("name")`, not `Agent("name").route()`. Since the codegen doesn't support classmethods, we handle this differently: add it as a hand-written `@staticmethod` directly on the `Agent` class via post-generation patching.

**Alternative approach:** Since `Route` is already importable from `adk_fluent`, and adding a classmethod requires hand-written post-gen code, the simpler fix is:

1. Keep `Route` as a standalone import (it IS a standalone concept)
1. Ensure `Route` is in Tier 1 imports
1. Document the pattern clearly

**Decision:** Skip the classmethod. `Route` is a first-class builder, not a factory of Agent. It belongs as a standalone import. Fix this with namespace tiering (Fix 9) and documentation.

______________________________________________________________________

## Fix 9: Namespace tiering

### Problem

`from adk_fluent import *` dumps 218 names. Users can't discover what matters.

### Solution

Restructure `__all__` into commented tiers. Add `adk_fluent.prelude` module for clean star-imports.

### `__init__.py` changes

Organize `__all__` with tier comments:

```python
__all__ = [
    # --- Tier 1: Core builders (what 90% of users need) ---
    "Agent", "Pipeline", "FanOut", "Loop",

    # --- Tier 2: Composition & control ---
    "C", "S", "Route", "Prompt", "Preset", "StateKey",
    "until", "tap", "expect", "gate", "race", "map_over",

    # --- Tier 3: Runtime & testing ---
    "App", "Runner", "InMemoryRunner",
    "Backend", "ADKBackend", "Middleware",
    "check_contracts", "mock_backend", "AgentHarness",
    ...
]
```

### `adk_fluent/prelude.py` (new module)

```python
"""Minimal imports for most adk-fluent projects.

Usage:
    from adk_fluent.prelude import *
    # Gives you: Agent, Pipeline, FanOut, Loop, C, S, Route, Prompt
"""
from adk_fluent import Agent, Pipeline, FanOut, Loop
from adk_fluent import C, S, Route, Prompt

__all__ = ["Agent", "Pipeline", "FanOut", "Loop", "C", "S", "Route", "Prompt"]
```

______________________________________________________________________

## Summary Matrix

| #   | Fix                                   | Type              | Breaking? | Files changed                              |
| --- | ------------------------------------- | ----------------- | --------- | ------------------------------------------ |
| 1   | `save_as` alias                       | Seed + codegen    | No        | seed.manual.toml, generator.py, field_docs |
| 2   | Deprecate `history`/`include_history` | Seed + codegen    | No        | seed.manual.toml, generator.py             |
| 3   | `stay()` / `no_peers()` helpers       | Seed + helpers    | No        | seed.manual.toml, \_helpers.py             |
| 4   | Deprecate `static_instruct`           | Seed + codegen    | No        | seed.manual.toml                           |
| 5   | `_if` docs                            | Docs only         | No        | cookbook, user guide                       |
| 6   | Topology docs                         | Docs only         | No        | user guide                                 |
| 7   | Readability guide                     | Docs only         | No        | user guide                                 |
| 8   | Route stays standalone                | Docs + tier       | No        | prelude.py, user guide                     |
| 9   | Namespace tiering                     | Init + new module | No        | __init__.py template, prelude.py           |

**All 9 fixes are non-breaking.** Ship in v0.8.0.
