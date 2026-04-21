# Verb Harmonization: Elegant API Surface Redesign

## Context

A full verb audit of adk-fluent's API surface revealed systemic naming issues: 4 aliases for one concept, near-homonym pairs with different semantics, singular/plural methods with opposite behaviors, and missing operator/builder equivalence. These aren't bugs — they're accumulated design debt from rapid feature growth.

This redesign applies three principles distilled from studying Stripe, Rails, Swift, Kotlin/Compose, and SQLAlchemy — the APIs developers describe as "it just makes sense."

## Governing Principles

### Principle 1: One Concept, One Name (The Stripe Rule)

Every concept gets exactly one method. No aliases, no synonyms. Stripe has `retrieve`, never `get`. Rails has `where`, never `filter`. We will have `.writes()`, never `.save_as()` / `.output_key()` / `.outputs()`.

### Principle 2: Bare Verb Appends (The Rails Rule)

Calling `.tool(fn)` appends. Calling `.tools(list)` appends all. Plural = batch singular, not replace. Rails established this: bare verb = append, `re-` prefix = replace. We don't need replace semantics — append-only is simpler and sufficient.

### Principle 3: Grammar Encodes Semantics (The Swift Rule)

Imperative verbs = runtime effect (`.instruct()`, `.writes()`, `.reads()`). Declarative nouns/adjectives = metadata/annotation (`.strict()`, `.transparent()`). Methods that change builder type are documented honestly in return types.

______________________________________________________________________

## Change 1: Data Flow — One Name Per Concept

### Before (10 methods, 4 aliases for `output_key`)

```
.writes("key")        ─┐
.save_as("key")        ├── All set output_key
.output_key("key")     │
.outputs("key")        ─┘

.returns(Model)        ── Sets output_schema
.output_schema(Model)  ── Same thing

.accepts(Model)        ── Sets input_schema
.input_schema(Model)   ── Same thing

.reads("k1", "k2")    ── Injects state keys into context
.consumes(Model)       ── Contract annotation only

.produces(Model)       ── Contract annotation only
```

### After (7 methods, zero aliases)

| Canonical                      | What It Does                   | Removed Aliases                                         |
| ------------------------------ | ------------------------------ | ------------------------------------------------------- |
| `.writes("key")`               | Store response in state        | ~~`.save_as()`~~, ~~`.output_key()`~~, ~~`.outputs()`~~ |
| `.reads("k1", "k2")`           | Inject state keys into context | —                                                       |
| `.returns(Model)` or `@ Model` | Force JSON output shape        | ~~`.output_schema()`~~                                  |
| `.accepts(Model)`              | Validate tool-mode input       | ~~`.input_schema()`~~                                   |
| `.produces(Model)`             | Contract annotation: writes    | — (keep, improve docstring)                             |
| `.consumes(Model)`             | Contract annotation: reads     | — (keep, improve docstring)                             |

### Implementation

- Remove `save_as` from `seed.manual.toml` `[builders.Agent.manual_aliases]`
- Remove `outputs` from `seed.manual.toml` `[builders.Agent.deprecated_aliases]`
- Add `output_key`, `output_schema`, `input_schema` to `[builders.Agent.deprecated_aliases]` pointing to `writes`, `returns`, `accepts` respectively
- Update all cookbooks, tests, examples to use canonical names
- Update docstring on `.produces()` / `.consumes()` to emphasize "contract-only, no runtime effect"

______________________________________________________________________

## Change 2: Singular/Plural — Always Append

### Before

| Singular                | Plural                         | Mismatch                 |
| ----------------------- | ------------------------------ | ------------------------ |
| `.tool(fn)` appends     | `.tools(list)` replaces        | Plural != batch singular |
| `.transfer_to(a)` appends | `.sub_agents([list])` replaces | Same                     |

### After

| Singular                    | Plural                                 | Rule                  |
| --------------------------- | -------------------------------------- | --------------------- |
| `.tool(fn)` appends one     | `.tools(list\|TComposite)` appends all | Plural = batch append |
| `.transfer_to(a)` appends one | `.sub_agents([list])` appends all      | Same                  |

### Implementation

- Modify `_add_tools()` in `_helpers.py`: change list case from `_config["tools"] = list` to `_lists["tools"].extend(list)`
- Modify `sub_agents` setter: change from replace to extend

______________________________________________________________________

## Change 3: Retry/Fallback — Remove Model-Level Convenience Wrappers

### The Problem

`.retry()` was model-level (retry the LLM HTTP call). `.retry_if()` was pipeline-level (loop until condition). Same word, different mechanisms.

### The Solution: Remove Model-Level Shortcuts

| Current                  | Action                           | Rationale                                       |
| ------------------------ | -------------------------------- | ----------------------------------------------- |
| `.retry(3, backoff=1.0)` | **Remove**                       | Model config — use `.generate_content_config()` |
| `.fallback("gpt-4")`     | **Remove**                       | Model config — use `.generate_content_config()` |
| `.retry_if(pred)`        | **Rename → `.loop_while(pred)`** | It was always a loop, never a retry             |

### After: Every Level Has Clean Names

| Level                        | Retry                                 | Fallback                           |
| ---------------------------- | ------------------------------------- | ---------------------------------- |
| **Model** (LLM call)         | `.generate_content_config(...)`       | `.generate_content_config(...)`    |
| **Agent** (execution)        | `.loop_while(pred)` / `* until(pred)` | `//` operator / `Fallback` builder |
| **Middleware** (observation) | `M.retry()`                           | `M.on_fallback(fn)`                |

______________________________________________________________________

## Change 4: Operator ↔ Builder Complete Equivalence

### Gap Found

`//` (fallback) had no builder equivalent. All other operators had builders.

### New: `Fallback` Builder

```python
from adk_fluent import Fallback

# These are equivalent:
pipeline_a = agent_a // agent_b // agent_c
pipeline_b = Fallback("recovery").attempt(agent_a).attempt(agent_b).attempt(agent_c)
```

### Complete Equivalence Table

| Concept       | Operator          | Builder                                                 |
| ------------- | ----------------- | ------------------------------------------------------- |
| Sequence      | `a >> b >> c`     | `Pipeline("p").step(a).step(b).step(c)`                 |
| Parallel      | `a \| b \| c`     | `FanOut("f").branch(a).branch(b).branch(c)`             |
| Loop (N)      | `a * 3`           | `Loop("l").step(a).max_iterations(3)`                   |
| Loop (until)  | `a * until(pred)` | `a.loop_until(pred)` or `Loop("l").step(a).until(pred)` |
| Output schema | `a @ Model`       | `a.returns(Model)`                                      |
| Fallback      | `a // b // c`     | `Fallback("f").attempt(a).attempt(b).attempt(c)`        |

______________________________________________________________________

## Change 5: Rename Misleading Verbs

| Current               | New                  | Rationale                                                                  |
| --------------------- | -------------------- | -------------------------------------------------------------------------- |
| `.delegate(agent)`    | `.delegate_to(agent)` | "delegate" sounds like "hand off work." It wraps agent as a callable tool. |
| `.inject_context(fn)` | `.prepend(fn)`       | Says what it does — prepends text to the LLM prompt.                       |
| `.guardrail(fn)`      | `.guard(fn)`         | Shorter, consistent with `S.guard()`.                                      |
| `.retry_if(pred)`     | `.loop_while(pred)`  | It was always a loop. Natural pair with `.loop_until()`.                   |

______________________________________________________________________

## Change 6: Type-Changing Methods — Honest Return Types

Methods that return a different builder type get self-documenting internal type names:

| Method                | Current Return                    | New Return Type Name                |
| --------------------- | --------------------------------- | ----------------------------------- |
| `.tap(fn)`            | `BuilderBase` (actually Pipeline) | `Pipeline` (honest type annotation) |
| `.timeout(30)`        | `_TimeoutBuilder`                 | `TimedAgent`                        |
| `.dispatch(name="x")` | `_DispatchBuilder`                | `BackgroundTask`                    |
| `.loop_while(pred)`   | `BuilderBase` (actually Loop)     | `Loop` (honest type annotation)     |

______________________________________________________________________

## Change 7: Cross-Module Cleanup

| Item                                    | Change                                                       |
| --------------------------------------- | ------------------------------------------------------------ |
| `C.capture("key")`                      | **Remove** — state mutation belongs in `S.capture()`         |
| `C.template(template_str=...)`          | **Rename param** to `text` to match `P.template(text=...)`   |
| `Route().gt()` exists, `.gte()` missing | **Add** `.gte()`, `.lte()`, `.ne()` to complete operator set |

______________________________________________________________________

## Change 8: Builder vs Module Guidance (Docstring-Only)

No code changes. Add guidance to docstrings:

| Use Case            | Canonical Idiom                               |
| ------------------- | --------------------------------------------- |
| One tool            | `.tool(fn)`                                   |
| Multiple tools      | `.tools(T.fn(a) \| T.fn(b))`                  |
| Simple context      | `.reads("key")`                               |
| Complex context     | `.context(C.window(3) + C.from_state("key"))` |
| One middleware      | `.middleware(RetryMiddleware())`              |
| Composed middleware | `.middleware(M.retry(3) \| M.log())`          |

______________________________________________________________________

## Error Message in Removed Method Stubs

When a removed method is called (e.g., `.save_as()`, `.retry()`, `.fallback()`), the error message should guide users to the canonical replacement:

```python
def save_as(self, *args, **kwargs):
    raise AttributeError(
        ".save_as() was removed in v0.10.0. Use .writes('key') instead."
    )
```

These stubs live as `[builders.Agent.removed_methods]` entries in `seed.manual.toml` (new generator feature).

______________________________________________________________________

## Files Modified

| File                            | Changes                                                                                                                                                                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `seeds/seed.manual.toml`        | Remove `save_as` alias, remove `outputs` deprecated alias, add deprecated aliases for `output_key`/`output_schema`/`input_schema`, add removed method stubs, add Fallback builder                                               |
| `src/adk_fluent/_base.py`       | Remove `.retry()`, `.fallback()`, rename `.retry_if()` → `.loop_while()`, rename `.inject_context()` → `.prepend()`, rename `.guardrail()` → `.guard()`, rename `.delegate()` → `.delegate_to()`, update return type annotations |
| `src/adk_fluent/_helpers.py`    | Modify `_add_tools()` to always append (no replace), rename `_add_tool_delegate` → `_add_agent_tool`                                                                                                                            |
| `src/adk_fluent/_primitives.py` | Rename `_TimeoutBuilder` → `TimedAgent`, `_DispatchBuilder` → `BackgroundTask`                                                                                                                                                  |
| `src/adk_fluent/_routing.py`    | Add `Fallback` builder with `.attempt()`, add `Route.gte()`, `.lte()`, `.ne()`                                                                                                                                                  |
| `src/adk_fluent/_context.py`    | Remove `C.capture()`, rename `template_str` param → `text`                                                                                                                                                                      |
| `src/adk_fluent/workflow.py`    | Regenerate with Fallback builder                                                                                                                                                                                                |
| `src/adk_fluent/prelude.py`     | Export `Fallback`, remove `save_as` if re-exported                                                                                                                                                                              |
| `src/adk_fluent/__init__.py`    | Regenerate                                                                                                                                                                                                                      |
| `scripts/generator.py`          | Support `[builders.X.removed_methods]` for helpful error stubs                                                                                                                                                                  |
| `examples/cookbook/*.py`        | Update all references to renamed/removed methods                                                                                                                                                                                |
| `tests/**`                      | Update all references, add tests for new Fallback builder and Route operators                                                                                                                                                   |
| `docs/**`                       | Update user guides with canonical idioms                                                                                                                                                                                        |

______________________________________________________________________

## Migration Guide (ships with v0.10.0)

```
BREAKING CHANGES in v0.10.0 — Verb Harmonization

RENAMED:
  .save_as("key")        → .writes("key")
  .output_key("key")     → .writes("key")
  .outputs("key")        → .writes("key")
  .output_schema(Model)  → .returns(Model) or @ Model
  .input_schema(Model)   → .accepts(Model)
  .retry_if(pred)        → .loop_while(pred)
  .inject_context(fn)    → .prepend(fn)
  .guardrail(fn)         → .guard(fn)
  .delegate(agent)       → .delegate_to(agent)

REMOVED (use generate_content_config for model-level settings):
  .retry(max, backoff)   → removed (model config)
  .fallback("model")     → removed (model config)

ADDED:
  Fallback("f").attempt(a).attempt(b)  — builder for //
  Route().gte(n, agent)                — greater-than-or-equal
  Route().lte(n, agent)                — less-than-or-equal
  Route().ne(val, agent)               — not-equal

BEHAVIOR CHANGE:
  .tools([list])         — now appends (was replace)
  .sub_agents([list])    — now appends (was replace)
```

______________________________________________________________________

## Verification

1. `just test` — all tests pass (after test updates)
1. `just typecheck-core` — 0 errors
1. `just preflight` — clean
1. `just check-gen` — idempotent
1. All 66+ cookbooks pass
1. No method in the API has more than one name
1. Every operator has a builder equivalent
1. Every builder has an operator equivalent (where operators make sense)
1. `grep -r "save_as\|output_key\|outputs\|output_schema\|input_schema\|retry_if\|inject_context\|guardrail\|delegate" src/` returns only the error stubs
