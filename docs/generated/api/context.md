# Module: context

> `from adk_fluent import C`

The `C` namespace provides declarative context transforms that control what conversation history each agent sees. All transforms are frozen dataclasses implementing the `CTransform` protocol.

## C Namespace

### `C.none() -> CTransform`

Suppress all conversation history. Sets `include_contents="none"` with no instruction provider.

### `C.default() -> CTransform`

Keep default conversation history. Sets `include_contents="default"` (pass-through).

### `C.user_only() -> CUserOnly`

Include only user messages from conversation history. Creates an instruction provider that filters events to user content parts.

### `C.from_state(*keys) -> CFromState`

Read named keys from session state and inject them into the agent's instruction. Keys are available as `{key}` template variables.

**Parameters:**
- `*keys` — State key names to read

### `C.from_agents(*names) -> CFromAgents`

Include user messages plus outputs from named agents. Creates an instruction provider that filters events by agent name.

**Parameters:**
- `*names` — Agent names whose outputs to include

### `C.exclude_agents(*names) -> CExcludeAgents`

Exclude outputs from named agents. Inverse of `from_agents`.

**Parameters:**
- `*names` — Agent names whose outputs to exclude

### `C.window(n) -> CWindow`

Include only the last N turn-pairs from conversation history.

**Parameters:**
- `n` — Number of turn-pairs to include

**Alias:** `C.last_n_turns(n)` is equivalent.

### `C.template(template) -> CTemplate`

Render a template string with `{key}` placeholders filled from session state. Sets `include_contents="none"` — all context comes from the rendered template.

**Parameters:**
- `template` — Template string with `{key}` placeholders

### `C.capture(key) -> Callable`

Capture the user's most recent message into session state under the given key. Delegates to `S.capture(key)`.

**Parameters:**
- `key` — State key to store the captured message

### `C.budget(max_tokens=8000, overflow="truncate_oldest") -> CBudget`

Declare a token budget constraint for context.

**Parameters:**
- `max_tokens` — Maximum token budget (default: 8000)
- `overflow` — Strategy when budget exceeded (default: "truncate_oldest")

### `C.priority(tier=2) -> CPriority`

Assign a priority tier for context ordering.

**Parameters:**
- `tier` — Priority tier (0 = highest, default: 2)

## Composition Operators

### `+` (Union)

Combine two transforms into a `CComposite`. Both transforms apply.

```python
ctx = C.window(n=3) + C.from_state("topic")
```

### `|` (Pipe)

Pipe output of one transform into another, creating a `CPipe`.

```python
ctx = C.window(n=5) | C.from_state("summary")
```

## Types

| Type | Description |
|------|-------------|
| `CTransform` | Base protocol for all context transforms |
| `CComposite` | Union of multiple transforms (via `+`) |
| `CPipe` | Piped transforms (via `\|`) |
| `CFromState` | State key reader |
| `CWindow` | Turn-pair windowing |
| `CUserOnly` | User message filter |
| `CFromAgents` | Agent output selector |
| `CExcludeAgents` | Agent output excluder |
| `CTemplate` | Template renderer |
| `CBudget` | Token budget constraint |
| `CPriority` | Priority tier |

## Internal

### `_compile_context_spec(instruction, spec) -> dict`

Lower a `CTransform` + instruction string to ADK config dict with `include_contents` and `instruction` keys. Called internally by `Agent.build()`.
