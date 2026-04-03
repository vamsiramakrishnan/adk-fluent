# Code Quality Audit: adk-fluent

> Conducted 2026-04-03. Covers `src/adk_fluent/`.

---

## Executive Summary

The codebase is well-structured at a macro level — clear module boundaries, consistent
fluent API surface, good use of `@dataclass`, and pervasive type annotations. But
beneath the polished surface sit **45+ issues** across 6 categories that erode
confidence in internal consistency. The issues fall into a pattern: the *public API* is
meticulous while *internal implementation* drifts between conventions, as if authored by
multiple hands (or codegen passes) without a shared style contract.

**Severity distribution:**
- **CRITICAL** (contract violations): 2
- **HIGH** (consistency/duplication): 8
- **MEDIUM** (aesthetics/idiom): 20+
- **LOW** (nits): 15+

---

## 1. CRITICAL: Immutability Contract Violations

### 1.1 `BackgroundTask.max_tasks()` skips copy-on-write

**File:** `_primitive_builders.py:554-557`

```python
def max_tasks(self, n: int) -> Self:
    self._max_tasks = n   # MUTATES directly
    return self
```

Every other builder method in the entire codebase calls `self._maybe_fork_for_mutation()`
before touching state. This one doesn't. A frozen builder shared across two expressions
will silently share the mutation.

**Fix:** Add `self = self._maybe_fork_for_mutation()` as the first line.

### 1.2 `PrimitiveBuilderBase` uses `dict()` where `BuilderBase` uses `defaultdict(list)`

**File:** `_primitive_builders.py:67-68` vs `agent.py:33-36`

```python
# PrimitiveBuilderBase
self._callbacks: dict[str, list] = {}           # KeyError on missing key
self._lists: dict[str, list] = {}

# Agent (via BuilderBase pattern)
self._callbacks: dict[str, list[Callable]] = defaultdict(list)  # auto-creates
self._lists: dict[str, list] = defaultdict(list)
```

Accessing `self._callbacks["after_agent_callback"]` in a PrimitiveBuilder subclass
will raise `KeyError` instead of silently creating the list. This is a latent bug
for any PrimitiveBuilder that tries to use callback patterns from the main builder.

---

## 2. HIGH: Structural Duplication

### 2.1 Identical method bodies masquerading as semantic variants

Three pairs of methods have **character-for-character identical** implementations:

| Builder  | Method A      | Method B        | Both do                         |
|----------|---------------|-----------------|---------------------------------|
| Loop     | `.step()`     | `.sub_agent()`  | `self._lists["sub_agents"].append(value)` |
| FanOut   | `.branch()`   | `.sub_agent()`  | `self._lists["sub_agents"].append(value)` |
| Pipeline | `.step()`     | `.sub_agent()`  | `self._lists["sub_agents"].append(value)` |

**File:** `workflow.py:79-89, 223-232, 379-388`

The semantic aliases are fine for the public API, but internally they should delegate
to a single implementation:

```python
def step(self, value):
    return self.sub_agent(value)  # one source of truth
```

### 2.2 Seven copy-pasted `ATransform` constructors in `_artifacts.py`

`A.publish()`, `A.snapshot()`, `A.save()`, `A.load()`, `A.list()`, `A.version()`,
`A.delete()` — each constructs an `ATransform` with 17 keyword arguments and
`_fn=lambda state: None`. The real work happens at runtime, making the lambda a
dead parameter carried through every instance.

**Lines:** `_artifacts.py:428-624` (~200 lines of near-identical constructors)

**Fix:** Extract a `_make_artifact_op(op, **overrides)` factory.

### 2.3 `reads_keys()` / `writes_keys()` duplicated across schema modules

**Files:** `_predicate_schema.py:66-78` and `_tool_schema.py:53-70`

Identical loop-and-append pattern in both. Should be a shared mixin or utility.

---

## 3. HIGH: Type System Inconsistencies

### 3.1 `Any` used where specific types exist

```python
# agent.py — these accept rich types but annotate as Any
def tool(self, fn_or_tool: Any, ...) -> Self:
def tools(self, value: Any) -> Self:
def guard(self, value: Any) -> Self:
def context(self, spec: Any) -> Self:
def ui(self, spec: Any) -> Self:

# But this one is fully typed:
def instruct(self, value: str | Callable[[ReadonlyContext], str | Awaitable[str]]) -> Self:
```

The typed methods prove the team *can* type things — the `Any` methods look like TODO
markers that never got resolved. Union types like
`Callable | GGuard | GComposite` would make static analysis meaningful.

### 3.2 `to_ir()` returns `Any` on every builder

`agent.py:649`, `workflow.py:91,235,379` — all return `Any`. These should return
specific IR node types (`AgentNode`, `SequenceNode`, `ParallelNode`, `LoopNode`).

### 3.3 Parameter naming inconsistency

```python
def tool(self, fn_or_tool: Any, ...) -> Self:    # descriptive name
def tools(self, value: Any) -> Self:              # generic name
def guard(self, value: Any) -> Self:              # generic name
def context(self, spec: Any) -> Self:             # different generic name
```

Pick one convention and apply it everywhere.

---

## 4. HIGH: String-Based Type Dispatch (anti-`isinstance`)

### 4.1 `type(node).__name__ == "ClassName"` instead of `isinstance()`

**Files:** `compile/passes.py:39`, `testing/diagnosis.py:520,538,582`

```python
# This:
if type(node).__name__ == "RouteNode":

# Should be:
if isinstance(node, RouteNode):
```

String-based type checks defeat IDE navigation, refactoring tools, and type checkers.
They exist to avoid circular imports — but that's a symptom of the real problem
(see Section 7: File Size).

### 4.2 `isinstance` chains that should be `match` statements

**File:** `_transforms.py:281-294` — four-way isinstance dispatch on `(result1, result2)`
combining `StateDelta` and `StateReplacement`:

```python
if isinstance(result1, StateDelta) and isinstance(result2, StateDelta):
    return StateDelta({**result1.updates, **result2.updates})
if isinstance(result1, StateReplacement) and isinstance(result2, StateReplacement):
    return StateReplacement({**result1.new_state, **result2.new_state})
# ... two more branches
```

This is a textbook case for structural pattern matching:

```python
match (result1, result2):
    case (StateDelta(updates=a), StateDelta(updates=b)):
        return StateDelta({**a, **b})
    case (StateReplacement(new_state=a), StateReplacement(new_state=b)):
        return StateReplacement({**a, **b})
    case (StateReplacement(new_state=s), StateDelta(updates=d)):
        return StateReplacement({**s, **d})
    case (StateDelta(), StateReplacement() as r):
        return r
```

### 4.3 Massive isinstance chain in `viz.py:146-189`

A long if/elif chain dispatching on IR node types. Should be either:
- `functools.singledispatch` visitor, or
- `match` statement

---

## 5. MEDIUM: Namespace Module Inconsistencies

The 8 namespace modules (S, C, P, A, M, T, E, G) are the jewels of the API, but
internally they diverge on almost every structural decision:

### 5.1 Composition operators vary wildly

| Module | `+` (union) | `\|` (pipe) | `>>` (chain) |
|--------|-------------|-------------|--------------|
| S      | yes         | yes         | yes          |
| C      | yes         | yes         | yes          |
| P      | yes         | yes         | yes          |
| A      | no          | no          | yes          |
| M      | no          | yes         | no           |
| T      | no          | yes         | no           |
| E      | no          | yes         | no           |
| G      | no          | yes         | no           |

If `|` means "compose" everywhere, then `+` and `>>` should either be consistent
or explicitly documented as absent.

### 5.2 `_kind` discriminator: four different patterns

```python
# M/T: name-mangled instance attribute
self.__kind = kind            # _MComposite__kind

# E: class variable
class EComposite:
    _kind: str = "eval"

# G: @property
@property
def _kind(self) -> str:
    return "guard_chain"

# S: no _kind on composite at all
```

One concept, four implementations. This is the kind of inconsistency that erodes trust.

### 5.3 `__repr__` inconsistency

- **S**: includes contract metadata (`reads=`, `writes=`)
- **G**: includes discriminator (`_kind`)
- **M, T, E**: only shows class names of children — no metadata

### 5.4 Missing `__eq__`/`__hash__` on mutable composites

`MComposite`, `TComposite`, `EComposite`, `GComposite` — none implement `__eq__`.
Meanwhile `StateDelta` and `StateReplacement` implement `__hash__ = id(self)`,
which is unusual and breaks equality semantics (two deltas with identical updates
will not compare equal).

---

## 6. MEDIUM: Un-Pythonic Idioms

### 6.1 Manual `.append()` loops that should be comprehensions

**`_predicate_schema.py:66-71`**, **`_tool_schema.py:53-60`**, **`_context_providers.py:52-58,71-74`**

```python
# Current:
keys: list[str] = []
for f in cls._field_list:
    r = f.get_annotation(Reads)
    if r is not None:
        keys.append(_scoped_key(f.name, r.scope))
return frozenset(keys)

# Pythonic:
return frozenset(
    _scoped_key(f.name, r.scope)
    for f in cls._field_list
    if (r := f.get_annotation(Reads)) is not None
)
```

### 6.2 `len(x) == 0` / `len(x) > 0` instead of truthiness

```python
# _eval.py:1221
passed = len(failed) == 0          # should be: passed = not failed

# compute/_protocol.py:82
return len(self.tool_calls) > 0    # should be: return bool(self.tool_calls)

# _eval.py:1353
if isinstance(val, str) and len(val) > 0:  # should be: ... and val
```

### 6.3 Redundant `.get()` with `or` fallback

**`_skill_parser.py:143-152`**

```python
metadata = fm.get("metadata", {}) or {}    # {} or {} is always {}
agents_raw = fm.get("agents", {}) or {}
input_schema = fm.get("input", {}) or {}
output_schema = fm.get("output", {}) or {}
eval_cases = fm.get("eval", []) or []
```

The `or {}` is only needed if the value could be explicitly `None` in the dict.
If so, the default argument to `.get()` is pointless. Pick one pattern.

### 6.4 Missing context manager for temporary module injection

**`_eval.py:1280-1284`**

```python
mod = types.ModuleType(mod_name)
mod.root_agent = built_agent
sys.modules[mod_name] = mod
try:
    # ... use mod
finally:
    sys.modules.pop(mod_name, None)
```

This is a textbook `@contextmanager` extraction.

### 6.5 Bare `except Exception:` swallowing errors silently

**`_artifacts.py:195`**, **`_helpers.py:570`**, **`_schema_base.py:160`**,
**`backends/asyncio_backend.py:369,393`**, **`_skill_registry.py:51`**

Six locations catch `Exception` and silently continue. At minimum these should log
at `DEBUG` level. Silent swallowing makes debugging production issues a nightmare.

---

## 7. MEDIUM: File Size / God Modules

| File                     | Lines | Concern                                    |
|--------------------------|-------|--------------------------------------------|
| `_base.py`               | 2,940 | BuilderBase + all operators + data flow    |
| `tool.py`                | 2,320 | 51 tool builders (generated)               |
| `config.py`              | 2,241 | 38 config builders (generated)             |
| `middleware.py`           | 1,522 | Runtime middleware implementations         |
| `_context_providers.py`  | 1,421 | Context provider functions                 |
| `_eval.py`               | 1,419 | Evaluation framework                       |
| `testing/contracts.py`   | 1,329 | Contract validation                        |
| `_context.py`            | 1,294 | Context transforms                         |

`_base.py` at **2,940 lines** is the worst offender. It contains:
- `BuilderBase` class (the fluent chain machinery)
- All expression operators (`>>`, `|`, `*`, `//`, `@`)
- Data flow introspection
- IR conversion helpers

This should be at least 3 files: `_builder_base.py`, `_operators.py`, `_introspection.py`.

The generated files (`tool.py`, `config.py`) get a pass — they're machine output. But
`middleware.py`, `_context_providers.py`, and `_eval.py` are hand-written and would
benefit from splitting.

---

## 8. LOW: Inconsistent Error Strategy

### 8.1 Three different validation patterns coexist

```python
# Pattern A: Raise immediately (strict)
raise ValueError(f".writes() requires a non-empty string key, got {key!r}")

# Pattern B: Warn and proceed (permissive)
import warnings
warnings.warn(f".writes('{key}') overwrites existing...")

# Pattern C: Raise with usage hint
raise TypeError(
    f"agent @ X requires X to be a type, got {type(schema).__name__}. "
    "Usage: agent @ MySchema"
)
```

No consistent rule for when to warn vs raise, or whether to include usage hints.

### 8.2 Conditional `_if` methods only on callbacks

`after_agent_if()`, `before_agent_if()`, etc. exist — but `instruct_if()`,
`guard_if()`, `context_if()` don't. Either commit to the pattern or drop it.

---

## 9. LOW: Callback API Asymmetry

```python
# Variadic (accepts multiple):
agent.after_agent(fn1, fn2, fn3)

# Single only (must chain):
agent.guard(g1).guard(g2).guard(g3)
agent.tool(t1).tool(t2).tool(t3)
```

Neither is wrong, but the inconsistency means users have to remember which methods
accept varargs and which don't.

---

## Recommended Action Plan

### Phase 1 — Fix contract violations (CRITICAL)
1. Add `_maybe_fork_for_mutation()` to `BackgroundTask.max_tasks()`
2. Switch `PrimitiveBuilderBase` to `defaultdict(list)` for callbacks/lists

### Phase 2 — Eliminate structural duplication (HIGH)
3. Make `.step()` / `.branch()` delegate to `.sub_agent()`
4. Extract `_make_artifact_op()` factory in `_artifacts.py`
5. Extract shared `reads_keys()`/`writes_keys()` utility from schema modules

### Phase 3 — Type system consistency (HIGH)
6. Replace `Any` with union types on `tool()`, `guard()`, `context()`, `ui()`
7. Add specific return types to `to_ir()` methods
8. Standardize parameter naming (`value` vs `spec` vs `fn_or_tool`)

### Phase 4 — Pythonic idiom pass (MEDIUM)
9. Convert `.append()` loops to comprehensions (4 locations)
10. Fix truthiness checks (3 locations)
11. Replace `type().__name__ ==` with `isinstance()` (4 locations)
12. Add `match` statements for type dispatch (2 locations)
13. Extract context manager for temp module in `_eval.py`

### Phase 5 — Namespace consistency (MEDIUM)
14. Unify `_kind` discriminator pattern across M, T, E, G
15. Standardize `__repr__` to include metadata across all composites
16. Document operator support matrix (which modules support which operators)

### Phase 6 — Split god modules (MEDIUM)
17. Split `_base.py` into `_builder_base.py`, `_operators.py`, `_introspection.py`
18. Split `middleware.py` into `middleware/_core.py` and `middleware/_implementations.py`
