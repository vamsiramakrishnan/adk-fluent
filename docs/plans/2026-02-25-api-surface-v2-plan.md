# Implementation Plan: API Surface v2 — Fluent DX Refinements

**Design doc:** `docs/plans/2026-02-25-api-surface-v2-design.md`
**Target version:** 0.8.0

## Phase 1: Codegen — `deprecated_aliases` support

**Goal:** Teach the generator to emit deprecation warnings for aliases.

### Task 1.1: Add `deprecated_aliases` to `BuilderSpec`

**File:** `scripts/generator.py`

1. Add `deprecated_aliases: dict[str, dict[str, str]]` field to `BuilderSpec` dataclass (~line 96)

   - Format: `{ "fluent_name": { "field": "pydantic_field", "use": "replacement" } }`

1. In `_load_specs()` (~line 177), parse `deprecated_aliases` from builder config:

   ```python
   deprecated_aliases = {}
   for name, val in builder_config.get("deprecated_aliases", {}).items():
       if isinstance(val, dict):
           deprecated_aliases[name] = val
       else:
           # Simple form: deprecated_name = "replacement"
           deprecated_aliases[name] = {"use": val}
   ```

### Task 1.2: Generate deprecated alias methods

**File:** `scripts/generator.py`

1. Add `_ir_deprecated_alias_methods(spec)` function after `_ir_alias_methods()`:

   ```python
   def _ir_deprecated_alias_methods(spec: BuilderSpec) -> list[MethodNode]:
       methods = []
       for fluent_name, config in spec.deprecated_aliases.items():
           field_name = config.get("field", spec.aliases.get(fluent_name, fluent_name))
           use_instead = config.get("use", "")
           field_info = next((f for f in spec.fields if f["name"] == field_name), None)
           type_hint = field_info["type_str"] if field_info else "Any"

           msg = f".{fluent_name}() is deprecated, use .{use_instead}() instead"
           doc = f"Deprecated: use ``.{use_instead}()`` instead."

           methods.append(MethodNode(
               name=fluent_name,
               params=[Param("self"), Param("value", type=type_hint)],
               returns="Self",
               doc=doc,
               body=[
                   RawStmt(
                       f"import warnings\n"
                       f"warnings.warn(\n"
                       f'    "{msg}",\n'
                       f"    DeprecationWarning,\n"
                       f"    stacklevel=2,\n"
                       f")"
                   ),
                   SubscriptAssign("self._config", field_name, "value"),
                   ReturnStmt("self"),
               ],
           ))
       return methods
   ```

1. Call it from `_ir_class_node()` alongside `_ir_alias_methods()`:

   ```python
   methods.extend(_ir_deprecated_alias_methods(spec))
   ```

1. Update `_ir_alias_methods()` to skip names that are in `deprecated_aliases` (they're handled separately)

1. Update `_ir_field_methods()` covered-set to include deprecated alias names

### Task 1.3: Update `.pyi` stub generation

**File:** `scripts/generator.py` in `gen_stub_class()` (~line 645)

Ensure deprecated aliases appear in stubs with deprecation note in docstring.

### Task 1.4: Merge support in seed_generator

**File:** `scripts/seed_generator.py`

In `merge_manual_seed()`, add handling for `deprecated_aliases`:

```python
# Merge deprecated_aliases (manual overrides)
for builder_name in manual.get("builders", {}):
    manual_depr = manual["builders"][builder_name].get("deprecated_aliases", {})
    if manual_depr:
        auto_builder = auto["builders"].setdefault(builder_name, {})
        auto_depr = auto_builder.setdefault("deprecated_aliases", {})
        auto_depr.update(manual_depr)
```

### Verify Phase 1

```bash
just seed && just generate
python -m pytest tests/ -q --tb=short
ruff check src/
```

______________________________________________________________________

## Phase 2: Seed changes — Aliases + Deprecations

**Goal:** Wire up all new aliases and deprecations in seed.manual.toml.

### Task 2.1: Add `save_as` alias and deprecate `outputs`

**File:** `seeds/seed.manual.toml`

```toml
# In [builders.Agent] section, add:
[builders.Agent.deprecated_aliases]
outputs = { field = "output_key", use = "save_as" }
history = { field = "include_contents", use = "context" }
include_history = { field = "include_contents", use = "context" }
static_instruct = { field = "static_instruction", use = "static" }
```

**File:** `seeds/seed.manual.toml` — remove `outputs`, `history`, `include_history`, `static_instruct` from `[builders.Agent.aliases]` since they move to deprecated_aliases.

**File:** `seeds/seed.manual.toml` — add `save_as` to aliases (or let it be auto-inferred, depends on how aliases work — if not auto-inferred, add to aliases section).

Actually, aliases are in seed.toml (auto-generated), not seed.manual.toml. The manual file overrides/extends via merge. So:

1. The merge process needs to:

   - Remove deprecated aliases from `[builders.Agent.aliases]` in the merged seed
   - Add `save_as = "output_key"` to `[builders.Agent.aliases]`

1. Add to `seeds/seed.manual.toml`:

   ```toml
   # New aliases (added during merge)
   [builders.Agent.manual_aliases]
   save_as = "output_key"

   # Deprecated aliases (moved from aliases during merge)
   [builders.Agent.deprecated_aliases]
   outputs = { field = "output_key", use = "save_as" }
   history = { field = "include_contents", use = "context" }
   include_history = { field = "include_contents", use = "context" }
   static_instruct = { field = "static_instruction", use = "static" }
   ```

1. Update `merge_manual_seed()` in seed_generator.py to:

   - Merge `manual_aliases` into `aliases`
   - Remove deprecated alias names from `aliases` (they get their own methods)

### Task 2.2: Add field_docs for `save_as`

**File:** `seeds/seed.manual.toml`

```toml
[field_docs]
save_as = "Session state key where the agent's response text is stored. Downstream agents and state transforms can read this key. Alias for ``output_key``."
```

### Verify Phase 2

```bash
just seed && just generate
python -m pytest tests/ -q --tb=short
# Check generated agent.py has save_as() method and outputs() with warning
grep -n "save_as\|DeprecationWarning" src/adk_fluent/agent.py
```

______________________________________________________________________

## Phase 3: Helper methods — `stay()` + `no_peers()`

### Task 3.1: Add helper functions

**File:** `src/adk_fluent/_helpers.py`

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

Add `"_stay_agent"` and `"_no_peers_agent"` to `__all__`.

### Task 3.2: Add seed extras

**File:** `seeds/seed.manual.toml`

```toml
[[builders.Agent.extras]]
name = "stay"
signature = "(self) -> Self"
doc = "Prevent this agent from transferring back to its parent. Use for agents that should complete their work before returning."
behavior = "runtime_helper"
helper_func = "_stay_agent"
example = '''
specialist = (
    Agent("invoice_parser", "gemini-2.5-flash")
    .instruct("Parse the invoice.")
    .stay()  # Must finish before returning to coordinator
    .build()
)
'''
see_also = ["Agent.isolate", "Agent.no_peers"]

[[builders.Agent.extras]]
name = "no_peers"
signature = "(self) -> Self"
doc = "Prevent this agent from transferring to sibling agents. The agent can still return to its parent."
behavior = "runtime_helper"
helper_func = "_no_peers_agent"
example = '''
focused = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic thoroughly.")
    .no_peers()  # Don't hand off to sibling agents
    .build()
)
'''
see_also = ["Agent.isolate", "Agent.stay"]
```

### Task 3.3: Regenerate and verify

```bash
just seed && just generate
python -m pytest tests/ -q --tb=short
# Verify methods exist
python -c "from adk_fluent import Agent; a = Agent('t').stay(); print(a._config)"
python -c "from adk_fluent import Agent; a = Agent('t').no_peers(); print(a._config)"
```

______________________________________________________________________

## Phase 4: Namespace tiering

### Task 4.1: Create `prelude.py`

**File:** `src/adk_fluent/prelude.py` (new)

```python
"""Minimal imports for most adk-fluent projects.

Usage::

    from adk_fluent.prelude import *

Exports Tier 1 (builders) and Tier 2 (composition) names only.
"""
from adk_fluent import Agent, Pipeline, FanOut, Loop
from adk_fluent import C, S, Route, Prompt

__all__ = ["Agent", "Pipeline", "FanOut", "Loop", "C", "S", "Route", "Prompt"]
```

### Task 4.2: Organize `__all__` in `__init__.py` template

**File:** `scripts/generator.py` — in the `__init__.py` generation code

Add tier comments to the generated `__all__`. The generator's `gen_init_py()` function needs to:

1. Split generated builder exports into tiers based on a tier mapping
1. Emit `__all__` with tier section comments

Tier mapping (in generator or seed):

```python
TIER_1 = {"Agent", "Pipeline", "FanOut", "Loop"}
TIER_2 = {"C", "S", "Route", "Prompt", "Preset", "StateKey",
          "until", "tap", "expect", "gate", "race", "map_over"}
TIER_3_RUNTIME = {"App", "Runner", "InMemoryRunner", "Backend", "ADKBackend"}
# Everything else is Tier 4 (configs, tools, services, plugins)
```

### Task 4.3: Add prelude to manual_exports

**File:** `seeds/seed.manual.toml` — no change needed since prelude.py is a separate module, not re-exported.

### Verify Phase 4

```bash
just generate
python -c "from adk_fluent.prelude import *; print(Agent, Pipeline, C, S)"
python -m pytest tests/ -q --tb=short
```

______________________________________________________________________

## Phase 5: Documentation updates

### Task 5.1: Update transfer-control user guide

**File:** `docs/user-guide/transfer-control.md`

- Add "Choosing the right method" table (Pipeline.step, FanOut.branch, Loop.step, Agent.sub_agent, Agent.delegate)
- Add `.stay()` and `.no_peers()` to the control methods section
- Add "Topology naming" section explaining why each builder has its own method name

### Task 5.2: Update structured-data user guide

**File:** `docs/user-guide/structured-data.md`

- Replace `.outputs()` references with `.save_as()`
- Add migration note about `.outputs()` deprecation

### Task 5.3: Add "Pipeline readability" section

**File:** `docs/user-guide/context-engineering.md` or new section in an existing guide

- "Name your pipelines" pattern
- Before/after examples with complex operator expressions

### Task 5.4: Update cookbook examples

Update existing cookbooks that use deprecated methods:

- `outputs()` → `save_as()`
- `include_history()` → `context()`
- `static_instruct()` → `static()`

Only update the FLUENT sections, leave NATIVE sections as-is.

### Verify Phase 5

```bash
python -m pytest examples/cookbook/ -q --tb=short
```

______________________________________________________________________

## Phase 6: Tests

### Task 6.1: Deprecation warning tests

**File:** `tests/manual/test_deprecations.py` (new)

```python
import warnings
import pytest
from adk_fluent import Agent

def test_outputs_warns():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Agent("t").outputs("key")
        assert len(w) == 1
        assert "save_as" in str(w[0].message)
        assert issubclass(w[0].category, DeprecationWarning)

def test_save_as_no_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Agent("t").save_as("key")
        assert len(w) == 0

def test_history_warns():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Agent("t").history("none")
        assert len(w) == 1
        assert "context" in str(w[0].message)

def test_static_instruct_warns():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Agent("t").static_instruct("cached content")
        assert len(w) == 1
        assert "static" in str(w[0].message)
```

### Task 6.2: New method tests

**File:** `tests/manual/test_transfer_helpers.py` (update existing or new)

```python
from adk_fluent import Agent

def test_stay():
    a = Agent("t").stay()
    assert a._config["disallow_transfer_to_parent"] is True
    assert a._config.get("disallow_transfer_to_peers") is not True

def test_no_peers():
    a = Agent("t").no_peers()
    assert a._config.get("disallow_transfer_to_parent") is not True
    assert a._config["disallow_transfer_to_peers"] is True

def test_isolate_sets_both():
    a = Agent("t").isolate()
    assert a._config["disallow_transfer_to_parent"] is True
    assert a._config["disallow_transfer_to_peers"] is True
```

### Task 6.3: Prelude import test

**File:** `tests/manual/test_prelude.py` (new)

```python
def test_prelude_imports():
    from adk_fluent.prelude import Agent, Pipeline, FanOut, Loop, C, S, Route, Prompt
    assert Agent is not None

def test_prelude_star():
    import importlib
    mod = importlib.import_module("adk_fluent.prelude")
    assert set(mod.__all__) == {"Agent", "Pipeline", "FanOut", "Loop", "C", "S", "Route", "Prompt"}
```

### Verify Phase 6

```bash
python -m pytest tests/ -q --tb=short
python -m pytest examples/cookbook/ -q --tb=short
```

______________________________________________________________________

## Phase 7: Version bump + CHANGELOG

### Task 7.1: Version bump

**File:** `pyproject.toml` — bump version to `0.8.0`

### Task 7.2: CHANGELOG entry

**File:** `CHANGELOG.md`

```markdown
## [0.8.0] - 2026-02-25

### Added

- **`.save_as(key)` method**: Clearer name for storing agent response in session state (replaces `.outputs()`)
- **`.stay()` method**: Prevent agent from transferring back to parent (positive alternative to `.disallow_transfer_to_parent(True)`)
- **`.no_peers()` method**: Prevent agent from transferring to siblings (positive alternative to `.disallow_transfer_to_peers(True)`)
- **`adk_fluent.prelude` module**: Minimal imports for most projects (`Agent, Pipeline, FanOut, Loop, C, S, Route, Prompt`)
- **Tiered `__all__`**: Namespace organized into Tier 1 (core), Tier 2 (composition), Tier 3 (runtime), Tier 4 (everything else)

### Deprecated

- **`.outputs(key)`** — use `.save_as(key)` instead
- **`.history()`** — use `.context()` with C module instead
- **`.include_history()`** — use `.context()` with C module instead
- **`.static_instruct()`** — use `.static()` instead
```

______________________________________________________________________

## Dependency Graph

```
Phase 1 (codegen: deprecated_aliases) ──┐
                                         ├── Phase 2 (seed changes)
Phase 3 (helpers: stay/no_peers) ────────┤
                                         ├── Phase 4 (namespace)
                                         ├── Phase 5 (docs)
                                         └── Phase 6 (tests)
                                                    │
                                              Phase 7 (release)
```

Phase 1 must come first (codegen support). Phases 2-4 depend on Phase 1. Phase 3 is independent of Phase 2. Phase 5 and 6 can run after 2-4. Phase 7 is last.

______________________________________________________________________

## Verification Checklist

After all phases:

1. `just seed` — seeds merge correctly, deprecated_aliases present
1. `just generate` — .py and .pyi files regenerated with new + deprecated methods
1. `python -m pytest tests/ -q --tb=short` — all tests pass
1. `python -m pytest examples/cookbook/ -q --tb=short` — all cookbooks pass
1. `ruff check src/` — no lint errors
1. `python -c "from adk_fluent import Agent; Agent('t').save_as('k')"` — works without warning
1. `python -c "import warnings; warnings.simplefilter('always'); from adk_fluent import Agent; Agent('t').outputs('k')"` — warns
1. `python -c "from adk_fluent.prelude import *; print(Agent)"` — works
