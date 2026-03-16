# Module: transforms

> `from adk_fluent import S`

State transform factories. Each method returns an `STransform` for use with `>>`.

## Quick Reference

| Method                                         | Returns      | Description                                                       |
| ---------------------------------------------- | ------------ | ----------------------------------------------------------------- |
| `S.pick(*keys)`                                | `STransform` | Keep only the specified session-scoped keys.                      |
| `S.drop(*keys)`                                | `STransform` | Remove the specified keys from state.                             |
| `S.rename(**mapping)`                          | `STransform` | Rename state keys.                                                |
| `S.default(**defaults)`                        | `STransform` | Fill missing keys with default values.                            |
| `S.merge(*keys, into, fn=None)`                | `STransform` | Combine multiple keys into one.                                   |
| `S.transform(key, fn)`                         | `STransform` | Apply a function to a single state value                          |
| `S.guard(predicate, msg='State guard failed')` | `STransform` | Assert a state invariant.                                         |
| `S.log(*keys, label='')`                       | `STransform` | Debug-print selected keys (or all state if no keys given).        |
| `S.compute(**factories)`                       | `STransform` | Derive new keys from the full state dict                          |
| `S.set(**values)`                              | `STransform` | Set explicit key-value pairs in state (additive merge)            |
| `S.capture(key)`                               | `STransform` | Capture the most recent user message into state\[key\]            |
| `S.identity()`                                 | `STransform` | No-op transform.                                                  |
| `S.when(predicate, transform)`                 | `STransform` | Conditional transform.                                            |
| `S.branch(key, **transforms)`                  | `STransform` | Route to different transforms based on a state key value          |
| `S.accumulate(key, into=None)`                 | `STransform` | Append `state[key]` to a running list at `state[into]`            |
| `S.counter(key, step=1)`                       | `STransform` | Increment a numeric state value by *step* (default 1)             |
| `S.history(key, max_size=10)`                  | `STransform` | Keep a rolling window of past values at `state[f"{key}_history"]` |
| `S.validate(schema_cls, strict=False)`         | `STransform` | Validate state against a Pydantic model or dataclass              |
| `S.require(*keys)`                             | `STransform` | Assert that *keys* exist in state and are truthy                  |
| `S.flatten(key, separator='.')`                | `STransform` | Flatten nested dict at `state[key]` into dotted keys              |
| `S.unflatten(separator='.')`                   | `STransform` | Unflatten dotted keys back into nested dicts                      |
| `S.zip(*keys, into='zipped')`                  | `STransform` | Zip parallel lists into a list of tuples                          |
| `S.to_ui(*keys, surface='default')`            | `STransform` | Bridge state keys into the A2UI data model                        |
| `S.from_ui(*keys, surface='default')`          | `STransform` | Bridge A2UI data model values back into agent state               |
| `S.group_by(items_key, key_fn, into)`          | `STransform` | Group list items by a key function                                |

## Methods

### `S.pick(*keys: str) -> STransform`

Keep only the specified session-scoped keys. app:/user:/temp: keys are always preserved.

**Parameters:**

- `*keys` (*str*)

### `S.drop(*keys: str) -> STransform`

Remove the specified keys from state. Only session-scoped keys are affected.

**Parameters:**

- `*keys` (*str*)

### `S.rename(**mapping: str) -> STransform`

Rename state keys. Unmapped session-scoped keys pass through unchanged.
app:/user:/temp: keys are never touched.

**Parameters:**

- `**mapping` (*str*)

### `S.default(**defaults: Any) -> STransform`

Fill missing keys with default values. Existing keys are not overwritten.

**Parameters:**

- `**defaults` (*Any*)

### `S.merge(*keys: str, into: str, fn: Callable | None = None) -> STransform`

Combine multiple keys into one. Default join is newline concatenation.

**Parameters:**

- `*keys` (*str*)
- `into` (*str*)
- `fn` (*Callable | None*) — default: `None`

### `S.transform(key: str, fn: Callable) -> STransform`

Apply a function to a single state value.

**Parameters:**

- `key` (*str*)
- `fn` (*Callable*)

### `S.guard(predicate: Callable[[dict], bool], msg: str = State guard failed) -> STransform`

Assert a state invariant. Raises ValueError if predicate is falsy.

**Parameters:**

- `predicate` (*Callable\[\[dict\], bool\]*)
- `msg` (*str*) — default: `'State guard failed'`

### `S.log(*keys: str, label: str = ) -> STransform`

Debug-print selected keys (or all state if no keys given). Returns no updates.

**Parameters:**

- `*keys` (*str*)
- `label` (*str*) — default: `''`

### `S.compute(**factories: Callable) -> STransform`

Derive new keys from the full state dict.

**Parameters:**

- `**factories` (*Callable*)

### `S.set(**values: Any) -> STransform`

Set explicit key-value pairs in state (additive merge).

**Parameters:**

- `**values` (*Any*)

### `S.capture(key: str) -> STransform`

Capture the most recent user message into state\[key\].

The callable is a stub — real capture happens in CaptureAgent,
which is wired by the >> operator when _capture_key is detected.

**Parameters:**

- `key` (*str*)

### `S.identity() -> STransform`

No-op transform. Passes state through unchanged.

Useful as a neutral element for composition:
    transform = S.identity()
    if need_cleanup:
        transform = transform >> S.pick("a", "b")
    pipeline = agent >> transform >> next_agent

### `S.when(predicate: Callable[[dict], bool] | str, transform: STransform) -> STransform`

Conditional transform. Applies transform only if predicate(state) is truthy.

String predicate is a shortcut for state key check:
    S.when("verbose", S.log("score"))   # apply if state\["verbose"\] truthy
    S.when(lambda s: "draft" in s, S.rename(draft="input"))

**Parameters:**

- `predicate` (*Callable\[\[dict\], bool\] | str*)
- `transform` (*STransform*)

### `S.branch(key: str, **transforms: STransform) -> STransform`

Route to different transforms based on a state key value.

**Parameters:**

- `key` (*str*)
- `**transforms` (*STransform*)

### `S.accumulate(key: str, *, into: str | None = None) -> STransform`

Append `state[key]` to a running list at `state[into]`.

Defaults *into* to `f"{key}_all"`.

**Parameters:**

- `key` (*str*)
- `into` (*str | None*) — default: `None`

### `S.counter(key: str, step: int = 1) -> STransform`

Increment a numeric state value by *step* (default 1).

**Parameters:**

- `key` (*str*)
- `step` (*int*) — default: `1`

### `S.history(key: str, max_size: int = 10) -> STransform`

Keep a rolling window of past values at `state[f"{key}_history"]`.

**Parameters:**

- `key` (*str*)
- `max_size` (*int*) — default: `10`

### `S.validate(schema_cls: type, *, strict: bool = False) -> STransform`

Validate state against a Pydantic model or dataclass.

Raises `ValueError` on validation failure.

**Parameters:**

- `schema_cls` (*type*)
- `strict` (*bool*) — default: `False`

### `S.require(*keys: str) -> STransform`

Assert that *keys* exist in state and are truthy.

Unlike :meth:`guard`, this has precise `_reads_keys`.

**Parameters:**

- `*keys` (*str*)

### `S.flatten(key: str, separator: str = .) -> STransform`

Flatten nested dict at `state[key]` into dotted keys.

**Parameters:**

- `key` (*str*)
- `separator` (*str*) — default: `'.'`

### `S.unflatten(separator: str = .) -> STransform`

Unflatten dotted keys back into nested dicts.

**Parameters:**

- `separator` (*str*) — default: `'.'`

### `S.zip(*keys: str, into: str = zipped) -> STransform`

Zip parallel lists into a list of tuples.

**Parameters:**

- `*keys` (*str*)
- `into` (*str*) — default: `'zipped'`

### `S.to_ui(*keys: str, surface: str = default) -> STransform`

Bridge state keys into the A2UI data model.

Creates a transform that copies named state keys into the
A2UI surface's internal data model, enabling reactive UI updates
via data bindings.

**Args:**

  *keys: State keys to expose to the UI surface.
- **`surface`**: Target surface identifier (default `"default"`).

Usage:
    Agent("calc").writes("total") >> S.to_ui("total", surface="dash")

**Parameters:**

- `*keys` (*str*)
- `surface` (*str*) — default: `'default'`

### `S.from_ui(*keys: str, surface: str = default) -> STransform`

Bridge A2UI data model values back into agent state.

Reads values from the A2UI surface's data model and sets them
as state keys, enabling agents to consume user input from UI forms.

**Args:**

  *keys: Data model keys to import into state.
- **`surface`**: Source surface identifier (default `"default"`).

Usage:
    S.from_ui("name", "email", surface="contact") >> Agent("processor")

**Parameters:**

- `*keys` (*str*)
- `surface` (*str*) — default: `'default'`

### `S.group_by(items_key: str, key_fn: Callable[[Any], Any], into: str) -> STransform`

Group list items by a key function.

**Parameters:**

- `items_key` (*str*)
- `key_fn` (*Callable\[\[Any\], Any\]*)
- `into` (*str*)

## Composition Operators

### `>>` (chain)

Sequential — first runs, state updated, second runs on result

### `+` (combine)

Both run on original state, results merge

## Types

| Type               | Description                                                    |
| ------------------ | -------------------------------------------------------------- |
| `STransform`       | Composable state transform with metadata for contract checking |
| `StateDelta`       | Additive: merge these keys into state.                         |
| `StateReplacement` | Replace session-scoped keys.                                   |
