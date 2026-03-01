# Module: transforms

> `from adk_fluent import S`

State transform factories. Each method returns an `STransform` for use with `>>`.

## Quick Reference

| Method                                         | Returns      | Description                                                |
| ---------------------------------------------- | ------------ | ---------------------------------------------------------- |
| `S.pick(*keys)`                                | `STransform` | Keep only the specified session-scoped keys.               |
| `S.drop(*keys)`                                | `STransform` | Remove the specified keys from state.                      |
| `S.rename(**mapping)`                          | `STransform` | Rename state keys.                                         |
| `S.default(**defaults)`                        | `STransform` | Fill missing keys with default values.                     |
| `S.merge(*keys, into, fn=None)`                | `STransform` | Combine multiple keys into one.                            |
| `S.transform(key, fn)`                         | `STransform` | Apply a function to a single state value                   |
| `S.guard(predicate, msg='State guard failed')` | `STransform` | Assert a state invariant.                                  |
| `S.log(*keys, label='')`                       | `STransform` | Debug-print selected keys (or all state if no keys given). |
| `S.compute(**factories)`                       | `STransform` | Derive new keys from the full state dict                   |
| `S.set(**values)`                              | `STransform` | Set explicit key-value pairs in state (additive merge)     |
| `S.capture(key)`                               | `STransform` | Capture the most recent user message into state\[key\]     |
| `S.identity()`                                 | `STransform` | No-op transform.                                           |
| `S.when(predicate, transform)`                 | `STransform` | Conditional transform.                                     |
| `S.branch(key, **transforms)`                  | `STransform` | Route to different transforms based on a state key value   |

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
which is wired by the >> operator when \_capture_key is detected.

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
S.when("verbose", S.log("score")) # apply if state\["verbose"\] truthy
S.when(lambda s: "draft" in s, S.rename(draft="input"))

**Parameters:**

- `predicate` (*Callable\[\[dict\], bool\] | str*)
- `transform` (*STransform*)

### `S.branch(key: str, **transforms: STransform) -> STransform`

Route to different transforms based on a state key value.

**Parameters:**

- `key` (*str*)
- `**transforms` (*STransform*)

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
