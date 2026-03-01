# Module: context

> `from adk_fluent import C`

Context engineering namespace. Each method returns a frozen CTransform descriptor.

## Quick Reference

| Method                                                                         | Returns               | Description                                                                 |
| ------------------------------------------------------------------------------ | --------------------- | --------------------------------------------------------------------------- |
| `C.none()`                                                                     | `CTransform`          | Suppress all conversation history                                           |
| `C.default()`                                                                  | `CTransform`          | Keep default conversation history (pass-through)                            |
| `C.user_only()`                                                                | `CUserOnly`           | Include only user messages                                                  |
| `C.from_agents(*names)`                                                        | `CFromAgents`         | Include user messages + outputs from named agents                           |
| `C.exclude_agents(*names)`                                                     | `CExcludeAgents`      | Exclude outputs from named agents                                           |
| `C.window(n=5)`                                                                | `CWindow`             | Include last N turn-pairs from conversation history                         |
| `C.last_n_turns(n)`                                                            | `CWindow`             | Alias for C.window(n=n)                                                     |
| `C.from_state(*keys)`                                                          | `CFromState`          | Read named keys from session state as context                               |
| `C.template(text)`                                                             | `CTemplate`           | Render a template string with \{key} and {key?} state placeholders          |
| `C.when(predicate, block)`                                                     | `CWhen`               | Include block only if predicate is truthy at runtime                        |
| `C.select(author=None, type=None, tag=None)`                                   | `CSelect`             | Filter events by metadata: author, type, and/or tag                         |
| `C.recent(decay='exponential', half_life=10, min_weight=0.1)`                  | `CRecent`             | Importance-weighted selection based on recency with exponential decay       |
| `C.compact(strategy='tool_calls')`                                             | `CCompact`            | Structural compaction — merge sequential same-author messages or tool calls |
| `C.dedup(strategy='exact', model='gemini-2.5-flash')`                          | `CDedup`              | Remove duplicate or redundant events.                                       |
| `C.truncate(max_turns=None, max_tokens=None, strategy='tail')`                 | `CTruncate`           | Hard limit on context by turn count or estimated tokens                     |
| `C.project(*fields)`                                                           | `CProject`            | Keep only specified fields from event content                               |
| `C.budget(max_tokens=8000, overflow='truncate_oldest')`                        | `CBudget`             | Set token budget constraint for context                                     |
| `C.priority(tier=2)`                                                           | `CPriority`           | Set priority tier for context ordering                                      |
| `C.fit(max_tokens=4000, strategy='strict', model='gemini-2.5-flash')`          | `CFit`                | Aggressive pruning to fit a hard token limit.                               |
| `C.fresh(max_age=3600.0, stale_action='drop')`                                 | `CFresh`              | Prune stale context based on event timestamp                                |
| `C.redact(*patterns, replacement='[REDACTED]')`                                | `CRedact`             | Remove PII or sensitive patterns from context via regex                     |
| `C.summarize(scope='all', model='gemini-2.5-flash', prompt=None, schema=None)` | `CSummarize`          | Summarize context via LLM.                                                  |
| `C.relevant(query_key=None, query=None, top_k=5, model='gemini-2.5-flash')`    | `CRelevant`           | Select events by semantic relevance to a query via LLM scoring              |
| `C.extract(schema=None, key='extracted', model='gemini-2.5-flash')`            | `CExtract`            | Extract structured data from conversation via LLM                           |
| `C.distill(key='facts', model='gemini-2.5-flash')`                             | `CDistill`            | Extract atomic facts from conversation via LLM                              |
| `C.validate(*checks, model='gemini-2.5-flash')`                                | `CValidate`           | Validate context quality.                                                   |
| `C.notes(key='default', format='plain')`                                       | `CNotes`              | Read structured notes from scratchpad at `state["_notes_{key}"]`            |
| `C.write_notes(key='default', strategy='append', source_key=None)`             | `CWriteNotes`         | Write to scratchpad after agent execution                                   |
| `C.rolling(n=5, summarize=False, model='gemini-2.5-flash')`                    | `CRolling`            | Rolling window with optional summarization of older turns                   |
| `C.from_agents_windowed(**agent_windows)`                                      | `CFromAgentsWindowed` | Per-agent selective windowing                                               |
| `C.user(strategy='all')`                                                       | `CUser`               | Select user messages with a strategy                                        |
| `C.manus_cascade(budget=8000, model='gemini-2.5-flash')`                       | `CManusCascade`       | Manus-inspired progressive compression cascade                              |

## Methods

### `C.none() -> CTransform`

Suppress all conversation history.

### `C.default() -> CTransform`

Keep default conversation history (pass-through).

### `C.user_only() -> CUserOnly`

Include only user messages.

### `C.from_agents(*names: str) -> CFromAgents`

Include user messages + outputs from named agents.

**Parameters:**

- `*names` (*str*)

### `C.exclude_agents(*names: str) -> CExcludeAgents`

Exclude outputs from named agents.

**Parameters:**

- `*names` (*str*)

### `C.window(*, n: int = 5) -> CWindow`

Include last N turn-pairs from conversation history.

**Parameters:**

- `n` (*int*) — default: `5`

### `C.last_n_turns(n: int) -> CWindow`

Alias for C.window(n=n).

**Parameters:**

- `n` (*int*)

### `C.from_state(*keys: str) -> CFromState`

Read named keys from session state as context.

**Parameters:**

- `*keys` (*str*)

### `C.template(text: str) -> CTemplate`

Render a template string with \{key} and {key?} state placeholders.

**Parameters:**

- `text` (*str*)

### `C.when(predicate: Callable | str, block: CTransform) -> CWhen`

Include block only if predicate is truthy at runtime.

String predicate is a shortcut for state key check:
C.when("has_history", C.rolling("conversation"))
C.when(lambda s: s.get("debug"), C.notes("debug_scratchpad"))

**Parameters:**

- `predicate` (*Callable | str*)
- `block` (*CTransform*)

### `C.select(*, author: str | tuple[str, ...] | None = None, type: str | tuple[str, ...] | None = None, tag: str | tuple[str, ...] | None = None) -> CSelect`

Filter events by metadata: author, type, and/or tag.

**Parameters:**

- `author` (*str | tuple[str, ...] | None*) — default: `None`
- `type` (*str | tuple[str, ...] | None*) — default: `None`
- `tag` (*str | tuple[str, ...] | None*) — default: `None`

### `C.recent(*, decay: str = exponential, half_life: int = 10, min_weight: float = 0.1) -> CRecent`

Importance-weighted selection based on recency with exponential decay.

**Parameters:**

- `decay` (*str*) — default: `'exponential'`
- `half_life` (*int*) — default: `10`
- `min_weight` (*float*) — default: `0.1`

### `C.compact(*, strategy: str = tool_calls) -> CCompact`

Structural compaction — merge sequential same-author messages or tool calls.

**Parameters:**

- `strategy` (*str*) — default: `'tool_calls'`

### `C.dedup(*, strategy: str = exact, model: str = gemini-2.5-flash) -> CDedup`

Remove duplicate or redundant events. strategy='semantic' uses LLM.

**Parameters:**

- `strategy` (*str*) — default: `'exact'`
- `model` (*str*) — default: `'gemini-2.5-flash'`

### `C.truncate(*, max_turns: int | None = None, max_tokens: int | None = None, strategy: str = tail) -> CTruncate`

Hard limit on context by turn count or estimated tokens.

**Parameters:**

- `max_turns` (*int | None*) — default: `None`
- `max_tokens` (*int | None*) — default: `None`
- `strategy` (*str*) — default: `'tail'`

### `C.project(*fields: str) -> CProject`

Keep only specified fields from event content.

**Parameters:**

- `*fields` (*str*)

### `C.budget(*, max_tokens: int = 8000, overflow: str = truncate_oldest) -> CBudget`

Set token budget constraint for context.

**Parameters:**

- `max_tokens` (*int*) — default: `8000`
- `overflow` (*str*) — default: `'truncate_oldest'`

### `C.priority(*, tier: int = 2) -> CPriority`

Set priority tier for context ordering.

**Parameters:**

- `tier` (*int*) — default: `2`

### `C.fit(*, max_tokens: int = 4000, strategy: str = strict, model: str = gemini-2.5-flash) -> CFit`

Aggressive pruning to fit a hard token limit. strategy='cascade' uses LLM.

**Parameters:**

- `max_tokens` (*int*) — default: `4000`
- `strategy` (*str*) — default: `'strict'`
- `model` (*str*) — default: `'gemini-2.5-flash'`

### `C.fresh(*, max_age: float = 3600.0, stale_action: str = drop) -> CFresh`

Prune stale context based on event timestamp.

**Parameters:**

- `max_age` (*float*) — default: `3600.0`
- `stale_action` (*str*) — default: `'drop'`

### `C.redact(*patterns: str, replacement: str = [REDACTED]) -> CRedact`

Remove PII or sensitive patterns from context via regex.

**Parameters:**

- `*patterns` (*str*)
- `replacement` (*str*) — default: `'[REDACTED]'`

## LLM-powered methods

### `C.summarize(*, scope: str = all, model: str = gemini-2.5-flash, prompt: str | None = None, schema: dict | None = None) -> CSummarize`

Summarize context via LLM. Scope: 'all', 'before_window', 'tool_results'.

**Parameters:**

- `scope` (*str*) — default: `'all'`
- `model` (*str*) — default: `'gemini-2.5-flash'`
- `prompt` (*str | None*) — default: `None`
- `schema` (*dict | None*) — default: `None`

### `C.relevant(*, query_key: str | None = None, query: str | None = None, top_k: int = 5, model: str = gemini-2.5-flash) -> CRelevant`

Select events by semantic relevance to a query via LLM scoring.

**Parameters:**

- `query_key` (*str | None*) — default: `None`
- `query` (*str | None*) — default: `None`
- `top_k` (*int*) — default: `5`
- `model` (*str*) — default: `'gemini-2.5-flash'`

### `C.extract(*, schema: dict | None = None, key: str = extracted, model: str = gemini-2.5-flash) -> CExtract`

Extract structured data from conversation via LLM.

**Parameters:**

- `schema` (*dict | None*) — default: `None`
- `key` (*str*) — default: `'extracted'`
- `model` (*str*) — default: `'gemini-2.5-flash'`

### `C.distill(*, key: str = facts, model: str = gemini-2.5-flash) -> CDistill`

Extract atomic facts from conversation via LLM.

**Parameters:**

- `key` (*str*) — default: `'facts'`
- `model` (*str*) — default: `'gemini-2.5-flash'`

### `C.validate(*checks: str, model: str = gemini-2.5-flash) -> CValidate`

Validate context quality. Checks: 'contradictions', 'completeness', 'freshness', 'token_efficiency'.

**Parameters:**

- `*checks` (*str*)
- `model` (*str*) — default: `'gemini-2.5-flash'`

## Scratchpads + Sugar

### `C.notes(key: str = default, *, format: str = plain) -> CNotes`

Read structured notes from scratchpad at `state["_notes_{key}"]`.

**Parameters:**

- `key` (*str*) — default: `'default'`
- `format` (*str*) — default: `'plain'`

### `C.write_notes(key: str = default, *, strategy: str = append, source_key: str | None = None) -> CWriteNotes`

Write to scratchpad after agent execution.

Strategies: 'append', 'replace', 'merge', 'prepend'.

**Parameters:**

- `key` (*str*) — default: `'default'`
- `strategy` (*str*) — default: `'append'`
- `source_key` (*str | None*) — default: `None`

### `C.rolling(n: int = 5, *, summarize: bool = False, model: str = gemini-2.5-flash) -> CRolling`

Rolling window with optional summarization of older turns.

When `summarize=True`, events before the window are
summarized via LLM.

**Parameters:**

- `n` (*int*) — default: `5`
- `summarize` (*bool*) — default: `False`
- `model` (*str*) — default: `'gemini-2.5-flash'`

### `C.from_agents_windowed(**agent_windows: int) -> CFromAgentsWindowed`

Per-agent selective windowing.

Example:
C.from_agents_windowed(researcher=1, critic=3)

**Parameters:**

- `**agent_windows` (*int*)

### `C.user(*, strategy: str = all) -> CUser`

Select user messages with a strategy.

Strategies: 'all', 'first', 'last', 'bookend'.

**Parameters:**

- `strategy` (*str*) — default: `'all'`

### `C.manus_cascade(*, budget: int = 8000, model: str = gemini-2.5-flash) -> CManusCascade`

Manus-inspired progressive compression cascade.

Applies: compact → dedup → summarize → truncate.

**Parameters:**

- `budget` (*int*) — default: `8000`
- `model` (*str*) — default: `'gemini-2.5-flash'`

## Composition Operators

### `+` (union (CComposite))

Combine context transforms

### `|` (pipe (CPipe))

Chain context processing

## Types

| Type                  | Description                                                                 |
| --------------------- | --------------------------------------------------------------------------- |
| `CTransform`          | Base context transform descriptor                                           |
| `CComposite`          | Union of multiple context blocks (via + operator)                           |
| `CPipe`               | Pipe transform: source feeds into transform (via                            |
| `CFromState`          | Read named keys from session state and format as context                    |
| `CWindow`             | Include only the last N turn-pairs from conversation history                |
| `CUserOnly`           | Include only user messages from conversation history                        |
| `CFromAgents`         | Include user messages + outputs from named agents                           |
| `CExcludeAgents`      | Exclude outputs from named agents                                           |
| `CTemplate`           | Render a template string with \{key} and {key?} placeholders from state     |
| `CSelect`             | Filter events by metadata: author, type, and/or tag                         |
| `CRecent`             | Importance-weighted selection based on recency with exponential decay       |
| `CCompact`            | Structural compaction — merge sequential same-author messages or tool calls |
| `CDedup`              | Remove duplicate or redundant events                                        |
| `CTruncate`           | Hard limit on context size by turn count or estimated tokens                |
| `CProject`            | Keep only specific fields from event content                                |
| `CBudget`             | Token budget constraint for context                                         |
| `CPriority`           | Priority tier for context ordering (lower = higher priority)                |
| `CFit`                | Aggressive pruning to fit a hard token limit                                |
| `CFresh`              | Prune stale context based on event timestamp                                |
| `CRedact`             | Remove PII or sensitive patterns from context via regex                     |
| `CSummarize`          | Lossy compression via LLM summarization                                     |
| `CRelevant`           | Semantic relevance selection via LLM scoring                                |
| `CExtract`            | Structured extraction from conversation via LLM                             |
| `CDistill`            | Fact distillation from conversation via LLM                                 |
| `CValidate`           | Context quality validation                                                  |
| `CNotes`              | Read from an agent's structured scratchpad stored in session state          |
| `CWriteNotes`         | Write to an agent's structured scratchpad after agent execution             |
| `CRolling`            | Rolling window with optional summarization of older turns                   |
| `CFromAgentsWindowed` | Per-agent selective windowing                                               |
| `CUser`               | User message strategies                                                     |
| `CManusCascade`       | Manus-inspired progressive compression cascade                              |
| `CWhen`               | Conditional context inclusion                                               |
