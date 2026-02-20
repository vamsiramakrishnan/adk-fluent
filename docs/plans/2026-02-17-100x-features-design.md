# Phase 2: 100x Features Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Elevate adk-fluent from "nice builder" to "expression language" with 11 features that make it feel like FastAPI/Polars/Pydantic for agent development.

**Architecture:** All generated builders inherit from a hand-written `BuilderBase` mixin that provides operators, repr, validation, serialization, and composition. Runtime features (structured output, batch, retry, debug) extend `_helpers.py`. A decorator module provides `@agent` syntax.

**Tech Stack:** Python 3.11+, existing codegen pipeline, Pydantic for structured output, PyYAML (optional) for YAML serialization.

______________________________________________________________________

## Feature List

| #   | Feature                                      | Location                    | Type                     |
| --- | -------------------------------------------- | --------------------------- | ------------------------ |
| 1   | `__repr__`                                   | `_base.py` (BuilderBase)    | Builder mechanic         |
| 2   | `>>` / \`                                    | `/`\*\` operators           | `_base.py` (BuilderBase) |
| 3   | `.output(Model)` structured returns          | `_base.py` + `_helpers.py`  | Runtime                  |
| 4   | `.validate()` / `.explain()`                 | `_base.py` (BuilderBase)    | Builder mechanic         |
| 5   | `@agent` decorator                           | `decorators.py`             | Syntax sugar             |
| 6   | `.to_dict()` / `.from_dict()` / `.to_yaml()` | `_base.py` (BuilderBase)    | Builder mechanic         |
| 7   | `.with_()` immutable variants                | `_base.py` (BuilderBase)    | Builder mechanic         |
| 8   | `.map()` batch execution                     | `_helpers.py` + Agent extra | Runtime                  |
| 9   | Preset stacks (`.use()`)                     | `_base.py` + `presets.py`   | Builder mechanic         |
| 10  | `.debug()` trace mode                        | `_base.py` + `_helpers.py`  | Runtime                  |
| 11  | `.retry()` / `.fallback()`                   | Agent extra + `_helpers.py` | Runtime                  |

______________________________________________________________________

## 1. Foundation: BuilderBase Mixin

### File: `src/adk_fluent/_base.py` (new, hand-written)

All generated builders inherit from `BuilderBase`. The generator is modified to emit:

```python
from adk_fluent._base import BuilderBase

class Agent(BuilderBase):
    ...
```

`BuilderBase` declares the shared internal storage interface (`_config`, `_callbacks`, `_lists`, `_ALIASES`, `_CALLBACK_ALIASES`, `_ADDITIVE_FIELDS`) and adds all new methods. Generated code continues to define `__init__`, `__getattr__`, `build()`, aliases, callbacks, and extras as before — `BuilderBase` only adds NEW capabilities.

### Generator change (`scripts/generator.py`)

- Add `from adk_fluent._base import BuilderBase` to module-level imports
- Change class declaration from `class {Name}:` to `class {Name}(BuilderBase):`
- No other changes to generated code

______________________________________________________________________

## 2. `__repr__` — Readable Builder State

```python
def __repr__(self) -> str:
    cls_name = self.__class__.__name__
    name = self._config.get("name", "?")
    lines = [f'{cls_name}("{name}")']

    for k, v in self._config.items():
        if k == "name":
            continue
        # Resolve reverse alias for display
        display_key = self._reverse_alias(k)
        lines.append(f"  .{display_key}({self._format_value(v)})")

    for field, fns in self._callbacks.items():
        alias = next((a for a, f in self._CALLBACK_ALIASES.items() if f == field), field)
        for fn in fns:
            fn_name = getattr(fn, "__name__", repr(fn))
            lines.append(f"  .{alias}({fn_name})")

    for field, items in self._lists.items():
        for item in items:
            label = getattr(item, "name", repr(item))
            lines.append(f"  .{field}({label})")

    return "\n".join(lines)
```

Helper `_reverse_alias` checks `_ALIASES` dict to show `.instruct()` instead of `.instruction()`. Helper `_format_value` truncates long strings and shows callable names.

______________________________________________________________________

## 3. Operator Composition

### `>>` — Sequential (creates Pipeline)

```python
def __rshift__(self, other):
    if isinstance(self, Pipeline):
        return self.step(other)
    my_name = self._config.get("name", "a")
    other_name = other._config.get("name", "b")
    return Pipeline(f"{my_name}_then_{other_name}").step(self).step(other)
```

### `|` — Parallel (creates FanOut)

```python
def __or__(self, other):
    if isinstance(self, FanOut):
        return self.branch(other)
    my_name = self._config.get("name", "a")
    other_name = other._config.get("name", "b")
    return FanOut(f"{my_name}_and_{other_name}").branch(self).branch(other)
```

### `*` — Loop (creates Loop)

```python
def __mul__(self, iterations: int):
    name = self._config.get("name", "loop")
    loop = Loop(f"{name}_x{iterations}").max_iterations(iterations)
    if isinstance(self, Pipeline):
        for agent in self._lists.get("sub_agents", []):
            loop.step(agent)
    else:
        loop.step(self)
    return loop

def __rmul__(self, iterations: int):
    return self.__mul__(iterations)
```

### Chaining

```python
full = (web | db) >> writer >> (critic >> reviser) * 3 >> editor
```

**Import resolution:** `Pipeline`, `FanOut`, `Loop` are imported lazily inside operator methods to avoid circular imports, since those classes also inherit from `BuilderBase`.

______________________________________________________________________

## 4. `.validate()` / `.explain()`

```python
def validate(self) -> Self:
    """Try building; raise ValueError with clear message on failure."""
    try:
        self.build()
    except Exception as e:
        name = self._config.get("name", "?")
        raise ValueError(f"Builder '{name}' validation failed: {e}") from e
    return self

def explain(self) -> str:
    """Human-readable summary of builder state."""
    lines = [f"{self.__class__.__name__} '{self._config.get('name', '?')}':"]
    for k, v in self._config.items():
        if k == "name": continue
        lines.append(f"  {k}: {self._format_value(v)}")
    for field, fns in self._callbacks.items():
        lines.append(f"  {field}: {len(fns)} callback(s)")
    for field, items in self._lists.items():
        lines.append(f"  {field}: {len(items)} item(s)")
    return "\n".join(lines)
```

______________________________________________________________________

## 5. `@agent` Decorator

### File: `src/adk_fluent/decorators.py` (new)

```python
def agent(name: str, **kwargs):
    """Decorator to define an agent. Docstring becomes instruction."""
    def decorator(fn):
        from adk_fluent import Agent
        builder = Agent(name)
        if fn.__doc__:
            builder.instruct(fn.__doc__.strip())
        for k, v in kwargs.items():
            method = getattr(builder, k, None)
            if method and callable(method):
                method(v)
            else:
                builder._config[k] = v

        # Attach .tool decorator
        original_tool = builder.tool
        def tool_decorator(tool_fn):
            original_tool(tool_fn)
            return tool_fn
        builder.tool = tool_decorator

        # Attach .on(event_name) decorator
        def on(event_name):
            def event_decorator(callback_fn):
                cb_field = builder._CALLBACK_ALIASES.get(event_name, event_name)
                builder._callbacks[cb_field].append(callback_fn)
                return callback_fn
            return event_decorator
        builder.on = on

        return builder
    return decorator
```

Usage:

```python
@agent("math", model="gemini-2.5-flash")
def math_solver():
    """You are a math expert. Show your work step by step."""

@math_solver.tool
def calculator(expression: str) -> float:
    """Evaluate a math expression."""
    return eval(expression)

@math_solver.on("before_model")
def log_it(ctx):
    print(f"Calling model...")
```

______________________________________________________________________

## 6. Serialization

```python
def to_dict(self) -> dict:
    """Serialize builder state to dict. Callables stored as qualnames (informational)."""
    return {
        "_type": self.__class__.__name__,
        "config": {k: _serialize(v) for k, v in self._config.items()},
        "callbacks": {
            k: [fn.__qualname__ for fn in fns]
            for k, fns in self._callbacks.items() if fns
        },
        "lists": {
            k: [_serialize(item) for item in items]
            for k, items in self._lists.items() if items
        },
    }

@classmethod
def from_dict(cls, data: dict) -> Self:
    """Reconstruct from dict. Restores config fields only (not callables)."""
    builder = cls(data["config"]["name"])
    for k, v in data["config"].items():
        if k == "name": continue
        builder._config[k] = v
    return builder

def to_yaml(self) -> str:
    """Serialize to YAML. Requires PyYAML."""
    import yaml
    return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

@classmethod
def from_yaml(cls, yaml_str: str) -> Self:
    """Reconstruct from YAML string."""
    import yaml
    return cls.from_dict(yaml.safe_load(yaml_str))
```

**Trade-off:** Callbacks can't be deserialized from qualnames automatically. This is documented. `from_dict` is for config-driven setups where tools/callbacks are registered separately.

______________________________________________________________________

## 7. `.with_()` — Immutable Variants

```python
def with_(self, **overrides) -> Self:
    """Create a modified copy. Original unchanged."""
    new_name = overrides.pop("name", self._config.get("name", "?"))
    clone = self.clone(new_name)
    for key, value in overrides.items():
        resolved = clone._ALIASES.get(key, key)
        if resolved in clone._ADDITIVE_FIELDS:
            clone._callbacks[resolved].append(value)
        else:
            clone._config[resolved] = value
    return clone
```

______________________________________________________________________

## 8. `.map()` — Batch Execution

In `_helpers.py`:

```python
async def run_map_async(builder, prompts, concurrency=5):
    semaphore = asyncio.Semaphore(concurrency)
    async def _one(p):
        async with semaphore:
            return await run_one_shot_async(builder, p)
    return await asyncio.gather(*[_one(p) for p in prompts])

def run_map(builder, prompts, concurrency=5):
    """Sync wrapper."""
    # Same loop-detection logic as run_one_shot
    ...
```

Added as an Agent extra in `seed.toml`:

```toml
[[builders.Agent.extras]]
name = "map"
signature = "(self, prompts: list[str], *, concurrency: int = 5) -> list[str]"
doc = "Run agent against multiple prompts with bounded concurrency."
behavior = "runtime_helper"
helper_func = "run_map"
```

______________________________________________________________________

## 9. Presets (`.use()`)

### File: `src/adk_fluent/presets.py` (new)

```python
class Preset:
    """Reusable configuration bundle."""
    def __init__(self, **kwargs):
        self._fields = {}
        self._callbacks = {}
        for k, v in kwargs.items():
            if isinstance(v, list) and v and callable(v[0]):
                self._callbacks[k] = v
            elif callable(v) and k not in ("model",):
                self._callbacks[k] = [v]
            else:
                self._fields[k] = v
```

In `BuilderBase`:

```python
def use(self, preset) -> Self:
    """Apply a Preset configuration bundle."""
    for k, v in preset._fields.items():
        resolved = self._ALIASES.get(k, k)
        self._config[resolved] = v
    for k, fns in preset._callbacks.items():
        resolved = self._CALLBACK_ALIASES.get(k, k)
        for fn in fns:
            self._callbacks[resolved].append(fn)
    return self
```

The existing `.apply(MiddlewareStack)` extra on Agent is replaced — `.use(Preset)` is the implementation.

______________________________________________________________________

## 10. `.debug()` — Trace Mode

In `BuilderBase`:

```python
def debug(self, enabled: bool = True) -> Self:
    self._config["_debug"] = enabled
    return self
```

In `_helpers.py`, `run_one_shot_async` checks `builder._config.get("_debug")` and emits structured log output:

```
[agent_name] -> model: gemini-2.5-flash
[agent_name] -> prompt: "What is 2+2?" (5 tokens est.)
[agent_name] -> before_model: log_fn (0.2ms)
[agent_name] <- response: "4" (1 token, 230ms)
[agent_name] <- after_model: validate_fn (0.1ms)
[agent_name] = total: 231ms
```

Uses `time.perf_counter()` for timing. Output goes to `sys.stderr` (not stdout) to avoid polluting return values.

______________________________________________________________________

## 11. `.retry()` / `.fallback()`

On Agent builder (seed.toml extras):

```python
def retry(self, max_attempts=3, backoff=1.0) -> Self:
    self._config["_retry"] = {"max_attempts": max_attempts, "backoff": backoff}
    return self

def fallback(self, model: str) -> Self:
    self._config.setdefault("_fallbacks", []).append(model)
    return self
```

In `_helpers.py`, `run_one_shot_async` wraps execution:

1. Try primary model up to `max_attempts` times with exponential backoff
1. On exhaustion, try each fallback model in order
1. Raise original exception if all fail

______________________________________________________________________

## Testing Strategy

- **Pure builder mechanics** (repr, operators, validate, with\_, to_dict, presets): Unit tests with no LLM calls. Assert builder state, type of composed objects, serialization round-trips.
- **Runtime features** (structured output, map, retry, debug): Mock-based tests using patched `InMemoryRunner`. No real API calls.
- **Decorator**: Unit tests that verify builder state after decoration.
- **Cookbook examples**: Add examples 16-26 covering each new feature.

## Files Changed/Created

| File                           | Action                                                  |
| ------------------------------ | ------------------------------------------------------- |
| `src/adk_fluent/_base.py`      | CREATE — BuilderBase mixin                              |
| `src/adk_fluent/presets.py`    | CREATE — Preset class                                   |
| `src/adk_fluent/decorators.py` | CREATE — @agent decorator                               |
| `scripts/generator.py`         | MODIFY — emit BuilderBase inheritance                   |
| `seeds/seed.toml`              | MODIFY — add map, retry, fallback, output extras        |
| `src/adk_fluent/_helpers.py`   | MODIFY — structured output, map, retry, debug, fallback |
| `src/adk_fluent/agent.py`      | REGENERATE                                              |
| `src/adk_fluent/workflow.py`   | REGENERATE                                              |
| `src/adk_fluent/*.py`          | REGENERATE (all modules)                                |
| `src/adk_fluent/__init__.py`   | REGENERATE + add Preset, agent imports                  |
| `tests/manual/test_*.py`       | CREATE — tests for each feature                         |
| `examples/cookbook/16-26_*.py` | CREATE — cookbook examples                              |
