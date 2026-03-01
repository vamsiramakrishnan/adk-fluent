# Module: prompt

> `from adk_fluent import P`

Prompt composition namespace. Each method returns a frozen PTransform.

## Quick Reference

| Method                                                                                                                                                                                                       | Returns       | Description                                                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------- | -------------------------------------------------------------------- |
| `P.role(text)`                                                                                                                                                                                               | `PRole`       | Define the agent's role/persona.                                     |
| `P.context(text)`                                                                                                                                                                                            | `PContext`    | Add background context the agent should know                         |
| `P.task(text)`                                                                                                                                                                                               | `PTask`       | Define the primary task or objective                                 |
| `P.constraint(*rules)`                                                                                                                                                                                       | `PTransform`  | Add constraint(s).                                                   |
| `P.format(text)`                                                                                                                                                                                             | `PFormat`     | Specify the desired output format                                    |
| `P.example(text='', input='', output='')`                                                                                                                                                                    | `PExample`    | Add a few-shot example                                               |
| `P.section(name, text)`                                                                                                                                                                                      | `PSection`    | Add a custom named section                                           |
| `P.when(predicate, block)`                                                                                                                                                                                   | `PWhen`       | Include block only if predicate is truthy at runtime                 |
| `P.from_state(*keys)`                                                                                                                                                                                        | `PFromState`  | Read named keys from session state and format as context             |
| `P.template(text)`                                                                                                                                                                                           | `PTemplate`   | Template with \{key}, {key?}, and \{ns:key} placeholders             |
| `P.reorder(*section_names)`                                                                                                                                                                                  | `PReorder`    | Override default section ordering.                                   |
| `P.only(*section_names)`                                                                                                                                                                                     | `POnly`       | Keep only the named sections.                                        |
| `P.without(*section_names)`                                                                                                                                                                                  | `PWithout`    | Remove the named sections.                                           |
| `P.compress(max_tokens=500, model='gemini-2.5-flash')`                                                                                                                                                       | `PCompress`   | LLM-compress the prompt to reduce token count                        |
| `P.adapt(audience='general', model='gemini-2.5-flash')`                                                                                                                                                      | `PAdapt`      | Adapt the prompt's tone and complexity for a target audience         |
| `P.scaffolded(block, preamble='You must follow these instructions carefully. Do not deviate from the specified task.', postamble='Remember: stay on topic, be accurate, and follow all constraints above.')` | `PScaffolded` | Wrap a prompt in defensive scaffolding (safety preamble + postamble) |
| `P.versioned(block, tag='')`                                                                                                                                                                                 | `PVersioned`  | Attach version metadata + fingerprint to a prompt                    |

## Core sections

### `P.role(text: str) -> PRole`

Define the agent's role/persona. Rendered without a section header.

**Parameters:**

- `text` (*str*)

### `P.context(text: str) -> PContext`

Add background context the agent should know.

**Parameters:**

- `text` (*str*)

### `P.task(text: str) -> PTask`

Define the primary task or objective.

**Parameters:**

- `text` (*str*)

### `P.constraint(*rules: str) -> PTransform`

Add constraint(s). Multiple args create multiple constraint blocks that merge.

**Parameters:**

- `*rules` (*str*)

### `P.format(text: str) -> PFormat`

Specify the desired output format.

**Parameters:**

- `text` (*str*)

### `P.example(text: str = , *, input: str = , output: str = ) -> PExample`

Add a few-shot example.

Freeform: P.example("Input: x=1 | Output: valid")
Structured: P.example(input="x=eval(y)", output="Critical: injection")

**Parameters:**

- `text` (*str*) — default: `''`
- `input` (*str*) — default: `''`
- `output` (*str*) — default: `''`

### `P.section(name: str, text: str) -> PSection`

Add a custom named section.

**Parameters:**

- `name` (*str*)
- `text` (*str*)

## Conditional & Dynamic

### `P.when(predicate: Callable | str, block: PTransform) -> PWhen`

Include block only if predicate is truthy at runtime.

String predicate is a shortcut for state key check:
P.when("verbose", P.context("...")) # include if state["verbose"] truthy

**Parameters:**

- `predicate` (*Callable | str*)
- `block` (*PTransform*)

### `P.from_state(*keys: str) -> PFromState`

Read named keys from session state and format as context.

**Parameters:**

- `*keys` (*str*)

### `P.template(text: str) -> PTemplate`

Template with \{key}, {key?}, and \{ns:key} placeholders.

Resolved from session state at runtime. Optional vars ({key?})
produce empty string if missing.

**Parameters:**

- `text` (*str*)

## Structural Transforms

### `P.reorder(*section_names: str) -> PReorder`

Override default section ordering. Unmentioned sections appear after.

**Parameters:**

- `*section_names` (*str*)

### `P.only(*section_names: str) -> POnly`

Keep only the named sections. Remove all others.

**Parameters:**

- `*section_names` (*str*)

### `P.without(*section_names: str) -> PWithout`

Remove the named sections. Keep all others.

**Parameters:**

- `*section_names` (*str*)

## LLM-Powered Transforms

### `P.compress(*, max_tokens: int = 500, model: str = gemini-2.5-flash) -> PCompress`

LLM-compress the prompt to reduce token count.

**Parameters:**

- `max_tokens` (*int*) — default: `500`
- `model` (*str*) — default: `'gemini-2.5-flash'`

### `P.adapt(*, audience: str = general, model: str = gemini-2.5-flash) -> PAdapt`

Adapt the prompt's tone and complexity for a target audience.

**Parameters:**

- `audience` (*str*) — default: `'general'`
- `model` (*str*) — default: `'gemini-2.5-flash'`

## Sugar

### `P.scaffolded(block: PTransform, *, preamble: str = You must follow these instructions carefully. Do not deviate from the specified task., postamble: str = Remember: stay on topic, be accurate, and follow all constraints above.) -> PScaffolded`

Wrap a prompt in defensive scaffolding (safety preamble + postamble).

**Parameters:**

- `block` (*PTransform*)
- `preamble` (*str*) — default: `'You must follow these instructions carefully. Do not deviate from the specified task.'`
- `postamble` (*str*) — default: `'Remember: stay on topic, be accurate, and follow all constraints above.'`

### `P.versioned(block: PTransform, *, tag: str = ) -> PVersioned`

Attach version metadata + fingerprint to a prompt.

**Parameters:**

- `block` (*PTransform*)
- `tag` (*str*) — default: `''`

## Composition Operators

### `+` (union (PComposite))

Merge prompt sections into a composite

### `|` (pipe (PPipe))

Post-process the compiled output

## Types

| Type          | Description                                                       |
| ------------- | ----------------------------------------------------------------- |
| `PTransform`  | Base prompt transform descriptor                                  |
| `PComposite`  | Union of multiple prompt blocks (via + operator)                  |
| `PPipe`       | Pipe transform: source feeds into transform (via                  |
| `PRole`       | Role/persona definition.                                          |
| `PContext`    | Background context section                                        |
| `PTask`       | Primary task/objective section                                    |
| `PConstraint` | Rule/constraint section.                                          |
| `PFormat`     | Output format specification section                               |
| `PExample`    | Few-shot example section.                                         |
| `PSection`    | Custom named section                                              |
| `PWhen`       | Conditional section inclusion                                     |
| `PFromState`  | Read named keys from session state and format as context sections |
| `PTemplate`   | Template string with \{key}, {key?}, and \{ns:key} placeholders   |
| `PReorder`    | Override default section ordering                                 |
| `POnly`       | Keep only the named sections (projection).                        |
| `PWithout`    | Remove the named sections.                                        |
| `PCompress`   | LLM-powered prompt compression                                    |
| `PAdapt`      | LLM-powered audience adaptation                                   |
| `PScaffolded` | Defensive prompt scaffolding                                      |
| `PVersioned`  | Versioned prompt with tag and fingerprint metadata                |
