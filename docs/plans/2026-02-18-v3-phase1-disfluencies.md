# v3 Phase 1: Fix Disfluencies Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 8 structural issues in adk-fluent's codebase (identified in v3 spec §1) without breaking the public API, preparing the foundation for Phase 2's IR introduction.

**Architecture:** Each task is independent and non-breaking. The generated code pipeline (`scanner.py` → `seed_generator.py` → `generator.py`) must be updated in tandem with hand-written code so that regeneration never overwrites fixes. All 831+ existing tests must remain green throughout.

**Tech Stack:** Python 3.11+, google-adk ≥1.20.0, pytest, ruff

**Reference Specs:**
- `docs/other_specs/adk_fluent_v3_spec.docx` — v3 spec with ADK runtime analysis (event-stream fidelity, delta-based state, plugin-first callbacks)
- `docs/other_specs/adk_fluent_v4_suggestions.md` — v4 addendums (scope-aware transforms, middleware-as-plugin, seed-based IR)
- The v3 markdown spec pasted in conversation — §1 Disfluencies

**Key v4 corrections incorporated into this plan:**
- Task 2: Transforms are now scope-aware — `S.pick`/`S.drop`/`S.rename` ONLY affect session-scoped (unprefixed) keys, preserving `app:`, `user:`, `temp:` prefixed keys (v4 §2.1)
- Task 4: Callback composition follows ADK's first-non-None-wins pattern (v4 §2.2 plugin semantics)
- Tasks 1-8 are Phase 1 foundation; Phases 2-5 (IR, event protocol, middleware-as-plugin, seed-based IR) build on this

---

## Context: Key Files

| File | Lines | Role |
|------|-------|------|
| `src/adk_fluent/_base.py` | 1,176 | BuilderBase mixin, operators, 7 primitive builders |
| `src/adk_fluent/_transforms.py` | 152 | State transform factories (`S` class) |
| `src/adk_fluent/__init__.py` | 295 | 132 flat symbol exports |
| `src/adk_fluent/config.py` | 4,065 | 41 generated config builders |
| `src/adk_fluent/tool.py` | 5,001 | 61 generated tool builders |
| `src/adk_fluent/service.py` | 1,291 | 21 generated service builders |
| `src/adk_fluent/plugin.py` | 1,093 | 14 generated plugin builders |
| `src/adk_fluent/presets.py` | 38 | Preset class (no validation) |
| `src/adk_fluent/decorators.py` | 42 | @agent decorator |
| `scripts/generator.py` | ~900 | Code generator (emits builder .py files) |
| `scripts/seed_generator.py` | ~400 | Seed TOML generator |

## Codegen Pipeline Reminder

Every change to generated files (`agent.py`, `workflow.py`, `config.py`, `tool.py`, `service.py`, `plugin.py`, `executor.py`, `runtime.py`, `planner.py`) **must** also be reflected in `scripts/generator.py` so regeneration doesn't overwrite fixes. The pipeline is:

```
python scripts/scanner.py -o manifest.json
python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
```

After any generator change, verify with:
```bash
python scripts/generator.py seeds/seed.toml manifest.json --output-dir /tmp/regen-check --test-dir /tmp/regen-check-tests
diff -r src/adk_fluent /tmp/regen-check
```

---

### Task 1: Consolidate `__getattr__` into `BuilderBase`

**Problem:** 127 identical `__getattr__` methods across 9 generated files (~2,500 lines of duplicated code). Each differs only in the ADK target class used for field validation.

**Files:**
- Modify: `src/adk_fluent/_base.py` (add `_ADK_TARGET_CLASS` + shared `__getattr__`)
- Modify: `scripts/generator.py` (stop generating per-class `__getattr__`, emit `_ADK_TARGET_CLASS` instead)
- Regenerate: All generated files (`agent.py`, `workflow.py`, `config.py`, `tool.py`, etc.)
- Test: `tests/manual/test_builder_base.py` (new tests)
- Verify: `tests/generated/` (all existing tests must pass)

**Step 1: Write failing tests for shared `__getattr__`**

Add to `tests/manual/test_builder_base.py`:

```python
def test_getattr_resolves_known_pydantic_field():
    """BuilderBase.__getattr__ should resolve fields via _ADK_TARGET_CLASS.model_fields."""
    from adk_fluent import Agent
    a = Agent("test")
    # 'description' is a known LlmAgent field — should return a setter, not raise
    result = a.description("hello")
    assert result is a  # Chaining

def test_getattr_rejects_unknown_field():
    """BuilderBase.__getattr__ should raise AttributeError for unknown fields."""
    from adk_fluent import Agent
    a = Agent("test")
    import pytest
    with pytest.raises(AttributeError, match="not a recognized"):
        a.totally_fake_field

def test_getattr_resolves_callback_alias():
    """BuilderBase.__getattr__ should handle callback aliases."""
    from adk_fluent import Agent
    a = Agent("test")
    result = a.after_agent(lambda ctx: None)
    assert result is a

def test_getattr_handles_init_signature_mode():
    """Builders with inspection_mode='init_signature' use _KNOWN_PARAMS."""
    from adk_fluent import FunctionTool
    t = FunctionTool(lambda: None)
    import pytest
    with pytest.raises(AttributeError, match="not a recognized"):
        t.not_a_param
```

**Step 2: Run tests to verify they pass (they should already pass with current per-class __getattr__)**

Run: `pytest tests/manual/test_builder_base.py -v -k "test_getattr"`
Expected: PASS (current code already handles these cases per-class)

**Step 3: Add `_ADK_TARGET_CLASS` and shared `__getattr__` to `BuilderBase`**

In `src/adk_fluent/_base.py`, add to `BuilderBase`:

```python
class BuilderBase:
    _ALIASES: dict[str, str]
    _CALLBACK_ALIASES: dict[str, str]
    _ADDITIVE_FIELDS: set[str]
    _ADK_TARGET_CLASS: type | None = None  # Set by generated subclasses
    _KNOWN_PARAMS: set[str] | None = None  # For init_signature mode builders

    def __getattr__(self, name: str):
        """Forward unknown methods to ADK target class fields for zero-maintenance compatibility.

        Each generated builder sets _ADK_TARGET_CLASS to its ADK Pydantic class.
        This single implementation replaces 127 per-class copies.
        """
        if name.startswith("_"):
            raise AttributeError(name)

        _ALIASES = self.__class__._ALIASES
        _CALLBACK_ALIASES = self.__class__._CALLBACK_ALIASES
        _ADDITIVE_FIELDS = self.__class__._ADDITIVE_FIELDS

        field_name = _ALIASES.get(name, name)

        # Check if it's a callback alias
        if name in _CALLBACK_ALIASES:
            cb_field = _CALLBACK_ALIASES[name]
            def _cb_setter(fn: Callable) -> Self:
                self._callbacks[cb_field].append(fn)
                return self
            return _cb_setter

        # Validate against ADK target class
        target = self.__class__._ADK_TARGET_CLASS
        known_params = getattr(self.__class__, '_KNOWN_PARAMS', None)

        if known_params is not None:
            # init_signature mode (non-Pydantic classes)
            valid_fields = known_params
        elif target is not None and hasattr(target, 'model_fields'):
            # Pydantic mode
            valid_fields = target.model_fields
        else:
            # No target class (composite/standalone) — accept anything
            valid_fields = None

        if valid_fields is not None and field_name not in valid_fields:
            available = sorted(
                set(valid_fields if isinstance(valid_fields, set) else valid_fields.keys())
                | set(_ALIASES.keys())
                | set(_CALLBACK_ALIASES.keys())
            )
            target_name = target.__name__ if target else self.__class__.__name__
            raise AttributeError(
                f"'{name}' is not a recognized field on {target_name}. "
                f"Available: {', '.join(available)}"
            )

        # Return a setter that stores value and returns self for chaining
        def _setter(value: Any) -> Self:
            if field_name in _ADDITIVE_FIELDS:
                self._callbacks[field_name].append(value)
            else:
                self._config[field_name] = value
            return self

        return _setter
```

**Step 4: Update generator to emit `_ADK_TARGET_CLASS` instead of per-class `__getattr__`**

In `scripts/generator.py`:

1. Modify `gen_alias_maps()` to emit `_ADK_TARGET_CLASS = _ADK_ClassName` as a class attribute.
2. For `init_signature` mode builders, also emit `_KNOWN_PARAMS = {...}`.
3. Modify `gen_getattr_method()` to return an empty string (no longer generating per-class `__getattr__`).

```python
def gen_getattr_method(spec: BuilderSpec) -> str:
    """__getattr__ is now inherited from BuilderBase. Nothing to generate."""
    return ""
```

Update `gen_alias_maps()` to add `_ADK_TARGET_CLASS`:

```python
def gen_alias_maps(spec: BuilderSpec) -> str:
    # ... existing alias/callback/additive generation ...

    if not spec.is_composite and not spec.is_standalone:
        class_short = _adk_import_name(spec)
        lines.append(f"    _ADK_TARGET_CLASS = {class_short}")

        if spec.inspection_mode == "init_signature":
            params = spec.init_params or []
            param_names = {p['name'] for p in params}
            lines.append(f"    _KNOWN_PARAMS: set[str] = {repr(param_names)}")

    return "\n".join(lines)
```

**Step 5: Regenerate all builder files**

```bash
python scripts/scanner.py -o manifest.json
python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
```

**Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All 831+ tests PASS

**Step 7: Verify regeneration consistency**

```bash
python scripts/generator.py seeds/seed.toml manifest.json --output-dir /tmp/regen-check
diff -r src/adk_fluent /tmp/regen-check
```
Expected: No meaningful diff

**Step 8: Commit**

```bash
git add src/adk_fluent/_base.py scripts/generator.py src/adk_fluent/*.py tests/
git commit -m "refactor: consolidate 127 __getattr__ into BuilderBase._ADK_TARGET_CLASS"
```

---

### Task 2: Fix State Transform Semantics (Scope-Aware)

**Problem:** `S.pick()`, `S.drop()`, `S.rename()` don't work as documented. The `_FnAgent._run_async_impl` applies function results as additive merges (`state[k] = v`), so `S.pick("a")` returns `{"a": val}` which is merged back — but all other keys remain. `S.drop("x")` returns everything except "x" but "x" is still in state.

**Critical ADK constraints (from v3 docx §2.3 and v4 suggestions §2.1):**

1. ADK's `State` has NO `__delitem__`. Mutations are delta-based. Keys can only be overwritten, never truly deleted.
2. State keys have scope prefixes: `app:` (cross-session), `user:` (cross-session per user), `temp:` (ephemeral, never persisted), unprefixed (session-scoped, default).
3. `_session_util.extract_state_delta()` routes keys by prefix to separate storage tiers. `S.pick("a")` returning a `StateReplacement` that wipes all keys would **destroy** `app:*` and `user:*` state — catastrophic.
4. `S.pick()`/`S.drop()` must ONLY affect session-scoped (unprefixed) keys. `app:`, `user:`, `temp:` keys are preserved unconditionally.

**Approach:**
- `StateDelta`: additive merge (for `S.default`, `S.merge`, `S.transform`, `S.compute`, `S.set`)
- `StateReplacement`: replace session-scoped keys only (for `S.pick`, `S.drop`, `S.rename`). Nullifies removed unprefixed keys but never touches prefixed keys.
- Plain `dict` return: backward-compatible, treated as `StateDelta`

**Files:**
- Modify: `src/adk_fluent/_transforms.py`
- Modify: `src/adk_fluent/_base.py` (update `_FnAgent` to handle `StateDelta`/`StateReplacement`)
- Create: `tests/manual/test_transforms_v3.py`

**Step 1: Write failing tests for corrected transform semantics**

Create `tests/manual/test_transforms_v3.py`:

```python
"""Tests for v3-corrected state transform semantics with scope awareness."""
import pytest
from adk_fluent._transforms import S, StateDelta, StateReplacement

# --- Type discrimination ---

def test_pick_returns_state_replacement():
    """S.pick() should return a function that produces StateReplacement."""
    fn = S.pick("a", "b")
    result = fn({"a": 1, "b": 2, "c": 3})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"a": 1, "b": 2}

def test_drop_returns_state_replacement():
    """S.drop() should return a function that produces StateReplacement."""
    fn = S.drop("c")
    result = fn({"a": 1, "b": 2, "c": 3})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"a": 1, "b": 2}

def test_rename_returns_state_replacement():
    """S.rename() should return a function that produces StateReplacement."""
    fn = S.rename(a="alpha")
    result = fn({"a": 1, "b": 2})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"alpha": 1, "b": 2}

def test_default_returns_state_delta():
    """S.default() should return a function that produces StateDelta."""
    fn = S.default(x=10)
    result = fn({"a": 1})
    assert isinstance(result, StateDelta)
    assert result.updates == {"x": 10}

def test_merge_returns_state_delta():
    """S.merge() should return a function that produces StateDelta."""
    fn = S.merge("a", "b", into="combined")
    result = fn({"a": "hello", "b": "world"})
    assert isinstance(result, StateDelta)
    assert "combined" in result.updates

def test_transform_returns_state_delta():
    """S.transform() should return a function that produces StateDelta."""
    fn = S.transform("x", str.upper)
    result = fn({"x": "hello"})
    assert isinstance(result, StateDelta)
    assert result.updates == {"x": "HELLO"}

def test_compute_returns_state_delta():
    """S.compute() should return a function that produces StateDelta."""
    fn = S.compute(total=lambda s: s["a"] + s["b"])
    result = fn({"a": 1, "b": 2})
    assert isinstance(result, StateDelta)
    assert result.updates == {"total": 3}

def test_guard_returns_state_delta():
    """S.guard() returns empty StateDelta on success."""
    fn = S.guard(lambda s: "key" in s, "Missing key")
    result = fn({"key": "val"})
    assert isinstance(result, StateDelta)
    assert result.updates == {}

def test_log_returns_state_delta():
    """S.log() returns empty StateDelta."""
    fn = S.log("a")
    result = fn({"a": 1})
    assert isinstance(result, StateDelta)
    assert result.updates == {}

# --- Scope awareness ---

def test_pick_preserves_prefixed_keys_in_input():
    """S.pick() receives full state dict but replacement only targets session-scoped keys."""
    fn = S.pick("a")
    # The function receives all state, but StateReplacement only lists session keys to keep
    result = fn({"a": 1, "b": 2, "app:setting": "x", "user:pref": "y", "temp:scratch": "z"})
    assert isinstance(result, StateReplacement)
    # new_state contains only the picked session keys — the FnAgent preserves prefixed keys
    assert result.new_state == {"a": 1}

def test_drop_excludes_only_named_session_keys():
    """S.drop() should only drop session-scoped keys by name."""
    fn = S.drop("b")
    result = fn({"a": 1, "b": 2, "app:setting": "x"})
    assert isinstance(result, StateReplacement)
    # new_state contains session keys minus dropped ones — prefixed keys handled by FnAgent
    assert result.new_state == {"a": 1}

# --- Backward compat: dict return still works ---

def test_plain_dict_function_still_works():
    """A plain function returning a dict should still work as a StateDelta."""
    fn = lambda state: {"new_key": state["a"] + 1}
    result = fn({"a": 1})
    assert isinstance(result, dict)

# --- S.set() convenience (new) ---

def test_set_returns_state_delta():
    """S.set() produces a StateDelta with the given key-value pairs."""
    fn = S.set(x=10, y=20)
    result = fn({})
    assert isinstance(result, StateDelta)
    assert result.updates == {"x": 10, "y": 20}
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_transforms_v3.py -v
```
Expected: FAIL — `StateDelta` and `StateReplacement` don't exist yet

**Step 3: Implement `StateDelta` and `StateReplacement` types**

In `src/adk_fluent/_transforms.py`, add at the top:

```python
from dataclasses import dataclass

# ADK state scope prefixes (from google.adk.sessions.state.State)
_SCOPE_PREFIXES = ("app:", "user:", "temp:")

@dataclass(frozen=True, slots=True)
class StateDelta:
    """Additive: merge these keys into state. Existing keys not mentioned are untouched."""
    updates: dict[str, Any]

@dataclass(frozen=True, slots=True)
class StateReplacement:
    """Replace session-scoped keys. ONLY unprefixed keys are affected.

    ADK constraint: State has no __delitem__. The FnAgent implements
    replacement by setting removed unprefixed keys to None in state_delta.
    Keys with scope prefixes (app:, user:, temp:) are NEVER touched.
    """
    new_state: dict[str, Any]
```

**Step 4: Update all `S` methods to return typed results**

The key design: `S.pick()`/`S.drop()`/`S.rename()` filter the state dict they receive to only consider session-scoped (unprefixed) keys. Prefixed keys are invisible to these transforms — they're preserved by the `FnAgent` runtime.

```python
class S:
    @staticmethod
    def pick(*keys: str) -> Callable[[dict], StateReplacement]:
        """Keep only the specified session-scoped keys. app:/user:/temp: keys are always preserved."""
        def _pick(state: dict) -> StateReplacement:
            # Only pick from session-scoped (unprefixed) keys
            return StateReplacement({k: state[k] for k in keys
                                     if k in state and not k.startswith(_SCOPE_PREFIXES)})
        _pick.__name__ = f"pick_{'_'.join(keys)}"
        return _pick

    @staticmethod
    def drop(*keys: str) -> Callable[[dict], StateReplacement]:
        """Remove the specified session-scoped keys. app:/user:/temp: keys are never touched."""
        drop_set = set(keys)
        def _drop(state: dict) -> StateReplacement:
            # Keep all session-scoped keys EXCEPT those in drop_set
            return StateReplacement({k: v for k, v in state.items()
                                     if not k.startswith(_SCOPE_PREFIXES) and k not in drop_set})
        _drop.__name__ = f"drop_{'_'.join(keys)}"
        return _drop

    @staticmethod
    def rename(**mapping: str) -> Callable[[dict], StateReplacement]:
        """Rename session-scoped state keys. Old key names are removed. Prefixed keys untouched."""
        def _rename(state: dict) -> StateReplacement:
            out = {}
            for k, v in state.items():
                if k.startswith(_SCOPE_PREFIXES):
                    continue  # Skip prefixed — preserved by FnAgent
                new_key = mapping.get(k, k)
                out[new_key] = v
            return StateReplacement(out)
        _rename.__name__ = f"rename_{'_'.join(mapping.keys())}"
        return _rename

    @staticmethod
    def default(**defaults: Any) -> Callable[[dict], StateDelta]:
        """Fill missing keys with defaults. Existing keys not overwritten."""
        def _default(state: dict) -> StateDelta:
            return StateDelta({k: v for k, v in defaults.items() if k not in state})
        _default.__name__ = f"default_{'_'.join(defaults.keys())}"
        return _default

    @staticmethod
    def merge(*keys: str, into: str, fn: Callable | None = None) -> Callable[[dict], StateDelta]:
        """Combine multiple keys into one. Default join is newline concatenation."""
        def _merge(state: dict) -> StateDelta:
            values = [state[k] for k in keys if k in state]
            if fn is not None:
                merged = fn(*values)
            else:
                merged = "\n".join(str(v) for v in values)
            return StateDelta({into: merged})
        _merge.__name__ = f"merge_{'_'.join(keys)}_into_{into}"
        return _merge

    @staticmethod
    def transform(key: str, fn: Callable) -> Callable[[dict], StateDelta]:
        """Apply a function to a single state value."""
        fn_name = getattr(fn, "__name__", "fn")
        def _transform(state: dict) -> StateDelta:
            if key in state:
                return StateDelta({key: fn(state[key])})
            return StateDelta({})
        _transform.__name__ = f"transform_{key}_{fn_name}"
        return _transform

    @staticmethod
    def guard(predicate: Callable[[dict], bool], msg: str = "State guard failed") -> Callable[[dict], StateDelta]:
        """Assert a state invariant. Raises ValueError if predicate is falsy."""
        def _guard(state: dict) -> StateDelta:
            if not predicate(state):
                raise ValueError(msg)
            return StateDelta({})
        _guard.__name__ = "guard"
        return _guard

    @staticmethod
    def log(*keys: str, label: str = "") -> Callable[[dict], StateDelta]:
        """Debug-print selected keys (or all state if no keys given)."""
        def _log(state: dict) -> StateDelta:
            prefix = f"[{label}] " if label else ""
            if keys:
                subset = {k: state.get(k, "<missing>") for k in keys}
            else:
                subset = state
            print(f"{prefix}{subset}")
            return StateDelta({})
        _log.__name__ = f"log_{'_'.join(keys) if keys else 'all'}"
        return _log

    @staticmethod
    def compute(**factories: Callable) -> Callable[[dict], StateDelta]:
        """Derive new keys from the full state dict."""
        def _compute(state: dict) -> StateDelta:
            return StateDelta({k: fn(state) for k, fn in factories.items()})
        _compute.__name__ = f"compute_{'_'.join(factories.keys())}"
        return _compute

    @staticmethod
    def set(**values: Any) -> Callable[[dict], StateDelta]:
        """Set explicit key-value pairs in state."""
        def _set(state: dict) -> StateDelta:
            return StateDelta(dict(values))
        _set.__name__ = f"set_{'_'.join(values.keys())}"
        return _set
```

**Step 5: Update `_FnAgent._run_async_impl` to handle typed results (scope-aware)**

In `src/adk_fluent/_base.py`, modify the `_FnStepBuilder.build()` inner class:

```python
def build(self):
    from google.adk.agents.base_agent import BaseAgent
    from adk_fluent._transforms import StateDelta, StateReplacement, _SCOPE_PREFIXES

    fn_ref = self._fn

    class _FnAgent(BaseAgent):
        """Zero-cost function agent. No LLM call."""
        async def _run_async_impl(self, ctx):
            result = fn_ref(dict(ctx.session.state))
            if isinstance(result, StateReplacement):
                # Only affect session-scoped (unprefixed) keys
                # Prefixed keys (app:, user:, temp:) are NEVER touched
                current_session_keys = {
                    k for k in ctx.session.state
                    if not k.startswith(_SCOPE_PREFIXES)
                }
                new_keys = set(result.new_state.keys())
                # Set new values
                for k, v in result.new_state.items():
                    ctx.session.state[k] = v
                # Nullify removed session keys (ADK has no __delitem__)
                for k in current_session_keys - new_keys:
                    ctx.session.state[k] = None
            elif isinstance(result, StateDelta):
                for k, v in result.updates.items():
                    ctx.session.state[k] = v
            elif isinstance(result, dict):
                # Backward compat: plain dict treated as delta
                for k, v in result.items():
                    ctx.session.state[k] = v

    return _FnAgent(name=self._config["name"])
```

**Step 6: Update `__all__` exports**

In `src/adk_fluent/_transforms.py`:
```python
__all__ = ["S", "StateDelta", "StateReplacement"]
```

In `src/adk_fluent/__init__.py`, add:
```python
from ._transforms import StateDelta, StateReplacement
```

**Step 7: Run all tests**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests PASS (including the new ones and all existing transform tests)

**Step 8: Commit**

```bash
git add src/adk_fluent/_transforms.py src/adk_fluent/_base.py src/adk_fluent/__init__.py tests/manual/test_transforms_v3.py
git commit -m "fix: scope-aware S.pick/S.drop/S.rename — preserve app:/user:/temp: keys, use StateDelta/StateReplacement"
```

---

### Task 3: Hoist Inner Classes to Module Level

**Problem:** 7 agent classes are defined inside `build()` methods. Each `build()` call creates a new type object. This is a memory leak in loops and defeats `isinstance` checks.

**Files:**
- Modify: `src/adk_fluent/_base.py`
- Create: `tests/manual/test_hoisted_agents.py`

**Step 1: Write failing tests**

Create `tests/manual/test_hoisted_agents.py`:

```python
"""Tests that inner agent classes are module-level and reuse type objects."""
from adk_fluent._base import _fn_step, tap

def test_fn_agent_same_type_across_builds():
    """Two FnStep builds should produce agents of the same type."""
    fn = lambda state: {"x": 1}
    b1 = _fn_step(fn)
    b2 = _fn_step(fn)
    a1 = b1.build()
    a2 = b2.build()
    assert type(a1) is type(a2), f"Expected same type, got {type(a1)} vs {type(a2)}"

def test_tap_agent_same_type_across_builds():
    """Two tap builds should produce agents of the same type."""
    fn = lambda state: None
    b1 = tap(fn)
    b2 = tap(fn)
    a1 = b1.build()
    a2 = b2.build()
    assert type(a1) is type(a2)

def test_fn_agent_is_importable():
    """Module-level agent classes should be importable."""
    from adk_fluent._base import FnAgent
    assert FnAgent is not None

def test_tap_agent_is_importable():
    from adk_fluent._base import TapAgent
    assert TapAgent is not None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_hoisted_agents.py -v
```
Expected: FAIL — inner classes are recreated each build, and not importable

**Step 3: Hoist all 7 inner agent classes to module level**

Replace the inner class pattern in `_base.py`. Define classes at module level AFTER the imports section. Each class stores its behavioral parameters as instance attributes set via `__init__` kwargs or a custom factory method.

The 7 classes to hoist:
1. `_FnAgent` → `FnAgent`
2. `_FallbackAgent` → `FallbackAgent`
3. `_TapAgent` → `TapAgent`
4. `_MapOverAgent` → `MapOverAgent`
5. `_TimeoutAgent` → `TimeoutAgent`
6. `_GateAgent` → `GateAgent`
7. `_RaceAgent` → `RaceAgent`

**Pattern for each:**

```python
# At module level, after imports
class FnAgent(BaseAgent):
    """Zero-cost function agent. No LLM call."""

    def __init__(self, *, fn: Callable, **kwargs):
        super().__init__(**kwargs)
        self._fn_ref = fn

    async def _run_async_impl(self, ctx):
        from adk_fluent._transforms import StateDelta, StateReplacement
        result = self._fn_ref(dict(ctx.session.state))
        if isinstance(result, StateReplacement):
            current_keys = {k for k in ctx.session.state
                            if not k.startswith(('app:', 'user:', 'temp:'))}
            new_keys = set(result.new_state.keys())
            for k, v in result.new_state.items():
                ctx.session.state[k] = v
            for k in current_keys - new_keys:
                ctx.session.state[k] = None
        elif isinstance(result, StateDelta):
            for k, v in result.updates.items():
                ctx.session.state[k] = v
        elif isinstance(result, dict):
            for k, v in result.items():
                ctx.session.state[k] = v
```

Then update each builder's `build()` to use the module-level class:

```python
class _FnStepBuilder(BuilderBase):
    def build(self):
        return FnAgent(name=self._config["name"], fn=self._fn)
```

**Important:** `BaseAgent` is a Pydantic model with strict field validation. The `fn` kwarg is NOT a Pydantic field — it must be set via `model_config = ConfigDict(arbitrary_types_allowed=True)` or via `__init__` override. Test which approach works with the installed ADK version.

If Pydantic rejects the extra kwargs, use a post-init pattern:

```python
class FnAgent(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    _fn_ref: Callable = PrivateAttr()

    def __init__(self, *, fn: Callable, **kwargs):
        super().__init__(**kwargs)
        self._fn_ref = fn
```

Or use object.__setattr__ if PrivateAttr isn't available:

```python
class FnAgent(BaseAgent):
    def __init__(self, *, fn: Callable, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, '_fn_ref', fn)
```

Test each approach. The key constraint is that `BaseAgent.__init__` must not reject the `fn` kwarg.

**Step 4: Apply the same pattern to all 7 classes**

Each class follows the same transformation:
- Define at module level with behavioral params stored via `object.__setattr__`
- Update the corresponding builder's `build()` to instantiate with kwargs
- Keep the exact same `_run_async_impl` logic

**Step 5: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/adk_fluent/_base.py tests/manual/test_hoisted_agents.py
git commit -m "refactor: hoist 7 inner agent classes to module level for type stability"
```

---

### Task 4: Compose Callbacks into Single Callables

**Problem:** `_prepare_build_config()` at line 414-415 passes either a single callable or a list of callables depending on count. ADK's behavior with lists varies by field and version.

**Files:**
- Modify: `src/adk_fluent/_base.py` (in `_prepare_build_config`)
- Create: `tests/manual/test_callback_composition.py`

**Step 1: Write failing tests**

Create `tests/manual/test_callback_composition.py`:

```python
"""Tests for callback composition in build config."""
import pytest
from adk_fluent import Agent

def test_single_callback_passes_through():
    """A single callback should be passed as-is."""
    fn = lambda ctx: None
    a = Agent("test").after_model(fn)
    config = a._prepare_build_config()
    assert config.get("after_model_callback") is fn

def test_multiple_callbacks_composed_into_single():
    """Multiple callbacks should be composed into a single callable."""
    call_log = []
    def fn1(ctx): call_log.append("fn1")
    def fn2(ctx): call_log.append("fn2")

    a = Agent("test").after_model(fn1).after_model(fn2)
    config = a._prepare_build_config()

    cb = config.get("after_model_callback")
    # Must be a single callable, not a list
    assert callable(cb), f"Expected callable, got {type(cb)}"
    assert not isinstance(cb, list), "Should be a single composed callable, not a list"

def test_composed_callbacks_run_in_order():
    """Composed callbacks should execute in registration order."""
    import asyncio
    call_log = []

    async def fn1(*args, **kwargs): call_log.append("fn1")
    async def fn2(*args, **kwargs): call_log.append("fn2")
    async def fn3(*args, **kwargs): call_log.append("fn3")

    a = Agent("test").after_model(fn1).after_model(fn2).after_model(fn3)
    config = a._prepare_build_config()
    cb = config.get("after_model_callback")

    # Run the composed callback
    asyncio.run(cb())
    assert call_log == ["fn1", "fn2", "fn3"]

def test_composed_callback_first_non_none_wins():
    """In composed callbacks, first non-None return value wins."""
    import asyncio

    async def fn1(*args, **kwargs): return None
    async def fn2(*args, **kwargs): return "blocked"
    async def fn3(*args, **kwargs): return "should not reach"

    a = Agent("test").before_model(fn1).before_model(fn2).before_model(fn3)
    config = a._prepare_build_config()
    cb = config.get("before_model_callback")

    result = asyncio.run(cb())
    assert result == "blocked"
```

**Step 2: Run tests**

```bash
pytest tests/manual/test_callback_composition.py -v
```
Expected: Some FAIL (current code passes lists when multiple callbacks)

**Step 3: Add `_compose_callbacks` and update `_prepare_build_config`**

In `_base.py`:

```python
import asyncio as _asyncio

def _compose_callbacks(fns: list[Callable]) -> Callable:
    """Chain multiple callbacks into a single callable.

    Each runs in order. First non-None return value wins (short-circuit).
    Handles both sync and async callbacks.
    """
    if len(fns) == 1:
        return fns[0]

    async def _composed(*args, **kwargs):
        for fn in fns:
            result = fn(*args, **kwargs)
            if _asyncio.iscoroutine(result):
                result = await result
            if result is not None:
                return result
        return None

    _composed.__name__ = f"composed_{'_'.join(getattr(f, '__name__', '?') for f in fns)}"
    return _composed
```

Then in `_prepare_build_config()`, change line 414-415 from:

```python
config[field] = fns if len(fns) > 1 else fns[0]
```

to:

```python
config[field] = _compose_callbacks(list(fns))
```

**Step 4: Run all tests**

```bash
pytest tests/ -v --tb=short
```
Expected: All PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_base.py tests/manual/test_callback_composition.py
git commit -m "fix: compose multiple callbacks into single callable at build time"
```

---

### Task 5: Add `_UNSET` Sentinel

**Problem:** Missing config keys and `None` values are indistinguishable. `model=None` means "use default" while absent means "inherit from parent" in ADK.

**Files:**
- Modify: `src/adk_fluent/_base.py`
- Create: `tests/manual/test_unset_sentinel.py`

**Step 1: Write failing tests**

Create `tests/manual/test_unset_sentinel.py`:

```python
"""Tests for _UNSET sentinel handling."""
from adk_fluent._base import _UNSET

def test_unset_is_falsy():
    """_UNSET should be falsy for convenience."""
    assert not _UNSET

def test_unset_repr():
    """_UNSET should have a clear repr."""
    assert repr(_UNSET) == "_UNSET"

def test_unset_excluded_from_build_config():
    """_UNSET values should not appear in build config."""
    from adk_fluent import Agent
    a = Agent("test")
    a._config["model"] = _UNSET
    config = a._prepare_build_config()
    assert "model" not in config

def test_none_included_in_build_config():
    """None values should still appear in build config (they have meaning in ADK)."""
    from adk_fluent import Agent
    a = Agent("test")
    a._config["generate_content_config"] = None
    config = a._prepare_build_config()
    assert "generate_content_config" in config
    assert config["generate_content_config"] is None
```

**Step 2: Run tests**

```bash
pytest tests/manual/test_unset_sentinel.py -v
```
Expected: FAIL — `_UNSET` doesn't exist

**Step 3: Implement `_UNSET`**

In `_base.py`, near the top:

```python
class _UnsetType:
    """Sentinel for 'not set' — distinct from None."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self): return False
    def __repr__(self): return "_UNSET"

_UNSET = _UnsetType()
```

Update `_prepare_build_config()` to filter out `_UNSET`:

```python
config = {k: v for k, v in self._config.items()
          if not k.startswith("_") and v is not _UNSET}
```

**Step 4: Run all tests**

```bash
pytest tests/ -v --tb=short
```
Expected: All PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_base.py tests/manual/test_unset_sentinel.py
git commit -m "feat: add _UNSET sentinel to distinguish 'not set' from None"
```

---

### Task 6: Use Read-Only View in `tap()`

**Problem:** `tap()` creates a full `dict(ctx.session.state)` copy. Since tap is observation-only, a read-only view is sufficient and avoids O(n) copy.

**Files:**
- Modify: `src/adk_fluent/_base.py` (the `TapAgent` class)
- Create: `tests/manual/test_tap_readonly.py`

**Step 1: Write failing tests**

Create `tests/manual/test_tap_readonly.py`:

```python
"""Tests for tap read-only state view."""
import types
from adk_fluent import tap

def test_tap_receives_mapping_proxy():
    """Tap function should receive a read-only MappingProxyType."""
    received = {}
    def capture(state):
        received['type'] = type(state)
        received['state'] = dict(state)

    t = tap(capture)
    # We'll test this indirectly — the TapAgent should pass MappingProxyType
    # For unit testing, verify the agent class behavior directly
    from adk_fluent._base import TapAgent
    assert TapAgent is not None  # It exists at module level (from Task 3)

def test_tap_state_is_immutable():
    """Attempting to modify state in a tap should raise TypeError."""
    def bad_tap(state):
        state["new_key"] = "value"  # Should fail if read-only

    # This test validates the contract — actual enforcement happens at runtime
    # via MappingProxyType which raises TypeError on mutation
    proxy = types.MappingProxyType({"a": 1})
    import pytest
    with pytest.raises(TypeError):
        proxy["new_key"] = "value"
```

**Step 2: Implement read-only view in TapAgent**

In the `TapAgent` class (now at module level from Task 3):

```python
import types

class TapAgent(BaseAgent):
    """Zero-cost observation agent. No LLM call, no state mutation."""

    def __init__(self, *, fn: Callable, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, '_fn_ref', fn)

    async def _run_async_impl(self, ctx):
        # Pass read-only view — tap should never mutate state
        self._fn_ref(types.MappingProxyType(dict(ctx.session.state)))
```

Note: We still create `dict(ctx.session.state)` once (to snapshot the proxy), then wrap it in `MappingProxyType`. This is slightly cheaper than a full deep copy and enforces immutability.

**Step 3: Run all tests**

```bash
pytest tests/ -v --tb=short
```
Expected: All PASS

**Step 4: Commit**

```bash
git add src/adk_fluent/_base.py tests/manual/test_tap_readonly.py
git commit -m "fix: pass read-only MappingProxyType to tap() functions"
```

---

### Task 7: Validate `Preset` Fields

**Problem:** `Preset(**kwargs)` accepts arbitrary keyword arguments. Typos like `Preset(modle="gemini-2.5-flash")` silently do nothing.

**Files:**
- Modify: `src/adk_fluent/presets.py`
- Create: `tests/manual/test_preset_validation.py`

**Step 1: Write failing tests**

Create `tests/manual/test_preset_validation.py`:

```python
"""Tests for Preset field validation."""
import pytest
from adk_fluent import Preset

def test_preset_rejects_typo():
    """Preset should reject obviously misspelled fields."""
    with pytest.raises(ValueError, match="modle"):
        Preset(modle="gemini-2.5-flash")

def test_preset_accepts_known_fields():
    """Preset should accept all known config fields."""
    p = Preset(model="gemini-2.5-flash", instruction="Help.")
    assert p._fields["model"] == "gemini-2.5-flash"

def test_preset_accepts_callbacks():
    """Preset should accept callback-like fields."""
    fn = lambda ctx: None
    p = Preset(before_model_callback=fn)
    assert fn in p._callbacks["before_model_callback"]

def test_preset_suggests_correction():
    """Preset should suggest the closest valid field for typos."""
    with pytest.raises(ValueError, match="model"):
        Preset(modle="gemini-2.5-flash")
```

**Step 2: Implement validation**

In `src/adk_fluent/presets.py`:

```python
import difflib

_KNOWN_FIELDS = frozenset({
    # Agent config
    "model", "instruction", "description", "name", "output_key",
    "global_instruction", "include_contents", "generate_content_config",
    "output_format", "max_iterations", "planner", "code_executor",
    "output_schema", "disallow_transfer_to_parent", "disallow_transfer_to_peers",
    # Callbacks
    "before_agent_callback", "after_agent_callback",
    "before_model_callback", "after_model_callback",
    "before_tool_callback", "after_tool_callback",
    # Short callback aliases
    "before_agent", "after_agent", "before_model", "after_model",
    "before_tool", "after_tool",
})

class Preset:
    def __init__(self, **kwargs: Any) -> None:
        self._fields: dict[str, Any] = {}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)

        for key, value in kwargs.items():
            if key not in _KNOWN_FIELDS and key not in _KNOWN_VALUE_FIELDS:
                close = difflib.get_close_matches(key, _KNOWN_FIELDS, n=3, cutoff=0.6)
                hint = f" Did you mean: {', '.join(close)}?" if close else ""
                raise ValueError(
                    f"Unknown Preset field '{key}'.{hint}"
                )
            if key in _KNOWN_VALUE_FIELDS:
                self._fields[key] = value
            elif callable(value):
                self._callbacks[key].append(value)
            else:
                self._fields[key] = value
```

**Step 3: Run all tests**

```bash
pytest tests/ -v --tb=short
```
Expected: All PASS (check existing preset tests don't use unknown fields)

**Step 4: Commit**

```bash
git add src/adk_fluent/presets.py tests/manual/test_preset_validation.py
git commit -m "fix: validate Preset fields with typo suggestions"
```

---

### Task 8: Rename `_clone_shallow` for Clarity

**Problem:** `_clone_shallow()` and `clone()` have confusing names. `_clone_shallow` sounds like a less complete `clone`, but it's the correct implementation for operator immutability.

**Files:**
- Modify: `src/adk_fluent/_base.py`
- Test: Existing tests in `tests/manual/test_clone.py` + `tests/manual/test_algebra.py`

**Step 1: Rename `_clone_shallow` → `_fork_for_operator`**

In `src/adk_fluent/_base.py`, rename all occurrences:

```python
def _fork_for_operator(self) -> BuilderBase:
    """Create an operator-safe fork. Shares sub-builders (safe: operators never mutate children)."""
    import copy
    new = object.__new__(type(self))
    new._config = dict(self._config)
    new._callbacks = {k: list(v) for k, v in self._callbacks.items()}
    new._lists = {k: list(v) for k, v in self._lists.items()}
    return new
```

Update all callers in `_base.py`:
- `__rshift__` (line ~178): `clone = self._fork_for_operator()`
- `__or__` (line ~203): `clone = self._fork_for_operator()`
- `__matmul__` (line ~248): `clone = self._fork_for_operator()`

Also update all `_clone_shallow` overrides in the primitive builder classes:
- `_FnStepBuilder._clone_shallow` → `_fork_for_operator`
- `_FallbackBuilder._clone_shallow` → `_fork_for_operator`
- `_TapBuilder._clone_shallow` → `_fork_for_operator`
- `_MapOverBuilder._clone_shallow` → `_fork_for_operator`
- `_TimeoutBuilder._clone_shallow` → `_fork_for_operator`
- `_GateBuilder._clone_shallow` → `_fork_for_operator`
- `_RaceBuilder._clone_shallow` → `_fork_for_operator`

**Step 2: Run all tests**

```bash
pytest tests/ -v --tb=short
```
Expected: All PASS (no external code calls `_clone_shallow` — it's private)

**Step 3: Commit**

```bash
git add src/adk_fluent/_base.py
git commit -m "refactor: rename _clone_shallow → _fork_for_operator for clarity"
```

---

## Post-Implementation Verification

After all 8 tasks are complete:

1. **Full test suite:**
   ```bash
   pytest tests/ -v --tb=short --cov=src/adk_fluent --cov-report=term-missing
   ```
   Expected: All 831+ tests PASS

2. **Regeneration consistency:**
   ```bash
   python scripts/scanner.py -o manifest.json
   python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
   python scripts/generator.py seeds/seed.toml manifest.json --output-dir /tmp/final-regen
   diff -r src/adk_fluent /tmp/final-regen
   ```
   Expected: No diff (all changes flow through the generator)

3. **Lint:**
   ```bash
   ruff check . && ruff format --check .
   ```
   Expected: Clean

4. **Cookbook examples still work:**
   ```bash
   python -c "from adk_fluent import Agent, S, tap, until, gate, race, Pipeline"
   ```
   Expected: No import errors

5. **Version bump and tag:**
   - Bump `pyproject.toml` version to `0.5.0`
   - Tag `v0.5.0`
   - Create GitHub release

---

## Summary

| Task | What | Impact |
|------|------|--------|
| 1 | Consolidate `__getattr__` | -2,500 lines of duplicated code |
| 2 | Fix state transforms | Correct `S.pick`/`S.drop`/`S.rename` semantics |
| 3 | Hoist inner classes | Type stability, no memory leak in loops |
| 4 | Compose callbacks | Always single callable to ADK, version-safe |
| 5 | `_UNSET` sentinel | Distinguish "not set" from `None` |
| 6 | Read-only tap | Enforce observation contract, minor perf |
| 7 | Validate Preset | Catch typos at definition time |
| 8 | Rename `_clone_shallow` | Clear intent communication |
