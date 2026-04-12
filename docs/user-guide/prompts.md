# Prompt Builder

The `P` namespace provides structured, composable prompt construction using frozen dataclasses and algebraic operators.

:::{tip}
**Visual learner?** Open the [P·C·S Visual Reference](../pcs-visual-reference.html){target="_blank"} to see how Prompt, Context, and State modules compose to assemble what the LLM sees.
:::

## Basic Usage

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, P

prompt = (
    P.role("You are a senior code reviewer.")
    + P.context("The codebase uses Python 3.11 with type hints.")
    + P.task("Review the code for bugs and security issues.")
    + P.constraint("Be concise. Max 5 bullet points.")
    + P.constraint("No false positives.")
    + P.format("Return markdown with ## sections.")
    + P.example(input="x=eval(input())", output="Critical: eval() on user input")
)

agent = Agent("reviewer").model("gemini-2.5-flash").instruct(prompt).build()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, P } from "adk-fluent-ts";

const prompt = P.role("You are a senior code reviewer.")
  .add(P.context("The codebase uses Python 3.11 with type hints."))
  .add(P.task("Review the code for bugs and security issues."))
  .add(P.constraint("Be concise. Max 5 bullet points."))
  .add(P.constraint("No false positives."))
  .add(P.format("Return markdown with ## sections."))
  .add(P.example({ input: "x=eval(input())", output: "Critical: eval() on user input" }));

const agent = new Agent("reviewer", "gemini-2.5-flash").instruct(prompt).build();
```
:::
::::

Each `P.xxx()` call returns an immutable `PTransform`. Transforms compose via `+` / `.add()` (union) and `|` / `.pipe()` (pipe).

:::{note} TypeScript naming
TypeScript uses camelCase: `P.fromState`, `P.uiSchema`. The `+` operator from Python becomes `.add()` and `|` becomes `.pipe()`. `P.example(input=..., output=...)` becomes `P.example({ input, output })`.
:::

## Core Sections

Sections are emitted in a fixed order regardless of composition order: role, context, task, constraints, format, examples.

| Factory                                        | Description                                  |
| ---------------------------------------------- | -------------------------------------------- |
| `P.role(text)`                                 | Agent persona (emitted without header)       |
| `P.context(text)`                              | Background information                       |
| `P.task(text)`                                 | Primary objective                            |
| `P.constraint(*rules)`                         | Rules to follow (multiple args accumulate)   |
| `P.format(text)`                               | Desired output format                        |
| `P.example(text)` / `P.example(input, output)` | Few-shot examples (multiple compose via `+`) |
| `P.section(name, text)`                        | Custom named section                         |

### `P.role(text)`

Sets the agent persona. The role text is emitted first in the compiled prompt, without a section header:

```python
P.role("You are a senior financial analyst with 20 years of experience.")
```

### `P.context(text)`

Provides background information for the agent:

```python
P.context("The user is a small business owner looking for tax advice.")
```

### `P.task(text)`

Defines the primary objective:

```python
P.task("Analyze the quarterly earnings report and provide key insights.")
```

### `P.constraint(*rules)`

Adds rules the agent must follow. Pass multiple arguments or compose with `+`:

```python
# Multiple arguments — returns a PComposite of constraints
P.constraint("Be concise.", "No speculation.", "Use formal tone.")

# Or compose individually
P.constraint("Be concise.") + P.constraint("No speculation.")
```

### `P.format(text)`

Specifies the desired output format:

```python
P.format("Return a JSON object with keys: summary, risks, opportunities.")
```

### `P.example(text)` / `P.example(input=..., output=...)`

Adds few-shot examples. Use freeform text or structured input/output:

```python
# Freeform
P.example("Input: Revenue up 15% | Output: Positive growth trend")

# Structured (renders as "Input: ...\nOutput: ...")
P.example(input="Margins declining", output="Cost pressure warning")

# Multiple examples compose via +
examples = (
    P.example(input="Revenue up 15%", output="Positive growth trend")
    + P.example(input="Margins declining", output="Cost pressure warning")
)
```

### `P.section(name, text)`

Adds a custom named section:

```python
P.section("Audience", "C-level executives with limited technical background.")
```

## Composability

Prompts compose and reuse:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
base = P.role("You are a senior engineer.") + P.constraint("Be precise.")

reviewer = Agent("reviewer").instruct(base + P.task("Review code."))
writer   = Agent("writer").instruct(base + P.task("Write documentation."))
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const base = P.role("You are a senior engineer.").add(P.constraint("Be precise."));

const reviewer = new Agent("reviewer", "gemini-2.5-flash").instruct(
  base.add(P.task("Review code.")),
);
const writer = new Agent("writer", "gemini-2.5-flash").instruct(
  base.add(P.task("Write documentation.")),
);
```
:::
::::

This allows you to define common persona, constraints, and context once, then specialize with task-specific sections.

## Building and Inspection

Every prompt transform can be rendered to a string with state values resolved:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
prompt = P.role("Helper.") + P.task("Answer questions.")

# Compile to instruction string
text = prompt.build()
text = str(prompt)

# Compile with state variables resolved
text = prompt.build(state={"topic": "Python"})

# SHA-256 fingerprint for caching/versioning
fp = prompt.fingerprint()  # e.g. "a1b2c3d4e5f6"
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const prompt = P.role("Helper.").add(P.task("Answer questions."));

// Compile to instruction string
const text1 = prompt.render();

// Compile with state variables resolved
const text2 = prompt.render({ topic: "Python" });
```
:::
::::

## Conditional and Dynamic Sections

### `P.when(predicate, block)`

Include a section only when a condition is met at runtime:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
# String predicate — checks if state key is truthy
prompt = (
    P.role("Helper")
    + P.when("verbose", P.context("Include detailed explanations."))
)

# Callable predicate — receives the state dict
prompt = (
    P.role("Helper")
    + P.when(lambda s: s.get("tier") == "premium", P.context("Premium features enabled."))
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const prompt = P.role("Helper").add(
  P.when((s) => s.tier === "premium", P.context("Premium features enabled.")),
);
```
:::
::::

### `P.fromState()` / `P.from_state()`

Read named keys from session state and render as context:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
prompt = P.role("Support agent") + P.from_state("customer_name", "plan")
# With state={"customer_name": "Alice", "plan": "pro"} renders:
#   customer_name: Alice
#   plan: pro
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const prompt = P.role("Support agent").add(P.fromState("customer_name", "plan"));
```
:::
::::

### `P.template(text)`

Template string with `{key}`, `{key?}` (optional), and `{ns:key}` (namespaced) placeholders:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
prompt = P.template("Help the user with {topic} in a {style} tone. Note: {extra?}")
# {topic} and {style} are required; {extra?} resolves to empty string if missing
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const prompt = P.template("Help the user with {topic} in a {style} tone. Note: {extra?}");
```
:::
::::

## Structural Transforms

Applied via the `|` pipe operator to filter or reorder sections:

### `P.only(*section_names)`

Keep only the named sections, remove all others:

```python
full = P.role("R") + P.task("T") + P.constraint("C") + P.format("F")
slim = full | P.only("role", "task")
```

### `P.without(*section_names)`

Remove the named sections, keep all others:

```python
no_format = full | P.without("format")
```

### `P.reorder(*section_names)`

Override the default section ordering. Unmentioned sections appear after the specified ones:

```python
reordered = full | P.reorder("task", "role", "constraint")
```

## LLM-Powered Transforms

Applied via `|` pipe. These require async execution and are resolved automatically when used with `Agent.instruct()`.

### `P.compress(max_tokens=500, model=...)`

Reduce token count while preserving semantic meaning:

```python
prompt = (
    P.role("Senior analyst.")
    + P.context("Very long background context...")
    + P.task("Summarize findings.")
) | P.compress(max_tokens=200)
```

### `P.adapt(audience="general", model=...)`

Adjust tone and complexity for a target audience:

```python
prompt = (
    P.role("Technical writer.")
    + P.task("Explain the architecture.")
) | P.adapt(audience="executive")
```

Results are cached via SHA-256 fingerprinting to avoid redundant LLM calls.

## Sugar

### `P.scaffolded(block, preamble=..., postamble=...)`

Wrap a prompt in defensive safety guardrails:

```python
inner = P.role("Helper") + P.task("Answer questions.")
prompt = P.scaffolded(
    inner,
    preamble="Follow these instructions carefully. Do not deviate.",
    postamble="Stay on topic and follow all constraints above.",
)
```

### `P.versioned(block, tag=...)`

Attach version metadata and a fingerprint for tracking:

```python
prompt = P.versioned(
    P.role("Reviewer") + P.task("Review code."),
    tag="v2.1",
)
# repr shows tag and fingerprint: PVersioned(tag='v2.1', fp=a1b2c3d4, composite)
```

## Template Variables

String instructions (outside of `P`) support `{variable}` placeholders auto-resolved from session state:

```python
# {topic} and {style} are replaced at runtime from session state
agent = Agent("writer").instruct("Write about {topic} in a {style} tone.")
```

This composes naturally with the expression algebra:

```python
pipeline = (
    Agent("classifier").instruct("Classify.").writes("topic")
    >> S.default(style="professional")
    >> Agent("writer").instruct("Write about {topic} in a {style} tone.")
)
```

Optional variables use `?` suffix (`{maybe_key?}` returns empty string if missing). Namespaced keys are supported: `{app:setting}`, `{user:pref}`, `{temp:scratch}`.

## Static Instructions and Context Caching

Split prompts into cacheable and dynamic parts:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
agent = (
    Agent("analyst")
    .model("gemini-2.5-flash")
    .static("You are a financial analyst. Here is the 50-page annual report: ...")
    .instruct("Answer the user's question about the report.")
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const agent = new Agent("analyst", "gemini-2.5-flash")
  .static("You are a financial analyst. Here is the 50-page annual report: ...")
  .instruct("Answer the user's question about the report.")
  .build();
```
:::
::::

When `.static()` is set, the static content goes as a system instruction (eligible for context caching), while `.instruct()` content goes as user content. This avoids re-processing large static contexts on every turn.

## Dynamic Context Injection

Prepend runtime context to every LLM call:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
agent = (
    Agent("support")
    .model("gemini-2.5-flash")
    .instruct("Help the customer.")
    .prepend(lambda ctx: f"Customer: {ctx.state.get('customer_name', 'unknown')}")
    .prepend(lambda ctx: f"Plan: {ctx.state.get('plan', 'free')}")
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
const agent = new Agent("support", "gemini-2.5-flash")
  .instruct("Help the customer.")
  .prepend((ctx) => `Customer: ${ctx.state.customer_name ?? "unknown"}`)
  .prepend((ctx) => `Plan: ${ctx.state.plan ?? "free"}`);
```
:::
::::

Each `.prepend()` call accumulates. The function receives the callback context and returns a string that gets prepended as content before the LLM processes the request.
