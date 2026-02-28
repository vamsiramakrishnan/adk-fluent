# Prompt Builder

The `P` namespace provides structured, composable prompt construction using frozen dataclasses and algebraic operators.

## Basic Usage

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

Each `P.xxx()` call returns an immutable `PTransform` dataclass. Transforms compose via `+` (union) and `|` (pipe).

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

## Composability with `+`

Prompts compose and reuse via the `+` operator:

```python
base = P.role("You are a senior engineer.") + P.constraint("Be precise.")

reviewer = Agent("reviewer").instruct(base + P.task("Review code."))
writer   = Agent("writer").instruct(base + P.task("Write documentation."))
```

This allows you to define common persona, constraints, and context once, then specialize with task-specific sections.

## Building and Inspection

Every `PTransform` supports `.build()`, `str()`, and `.fingerprint()`:

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

## Conditional and Dynamic Sections

### `P.when(predicate, block)`

Include a section only when a condition is met at runtime:

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

### `P.from_state(*keys)`

Read named keys from session state and render as context:

```python
prompt = P.role("Support agent") + P.from_state("customer_name", "plan")
# With state={"customer_name": "Alice", "plan": "pro"} renders:
#   customer_name: Alice
#   plan: pro
```

### `P.template(text)`

Template string with `{key}`, `{key?}` (optional), and `{ns:key}` (namespaced) placeholders:

```python
prompt = P.template("Help the user with {topic} in a {style} tone. Note: {extra?}")
# {topic} and {style} are required; {extra?} resolves to empty string if missing
```

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
    Agent("classifier").instruct("Classify.").save_as("topic")
    >> S.default(style="professional")
    >> Agent("writer").instruct("Write about {topic} in a {style} tone.")
)
```

Optional variables use `?` suffix (`{maybe_key?}` returns empty string if missing). Namespaced keys are supported: `{app:setting}`, `{user:pref}`, `{temp:scratch}`.

## Static Instructions and Context Caching

Split prompts into cacheable and dynamic parts:

```python
agent = (
    Agent("analyst")
    .model("gemini-2.5-flash")
    .static("You are a financial analyst. Here is the 50-page annual report: ...")
    .instruct("Answer the user's question about the report.")
    .build()
)
```

When `.static()` is set, the static content goes as a system instruction (eligible for context caching), while `.instruct()` content goes as user content. This avoids re-processing large static contexts on every turn.

## Dynamic Context Injection

Prepend runtime context to every LLM call:

```python
agent = (
    Agent("support")
    .model("gemini-2.5-flash")
    .instruct("Help the customer.")
    .inject_context(lambda ctx: f"Customer: {ctx.state.get('customer_name', 'unknown')}")
    .inject_context(lambda ctx: f"Plan: {ctx.state.get('plan', 'free')}")
)
```

Each `.inject_context()` call accumulates. The function receives the callback context and returns a string that gets prepended as content before the LLM processes the request.
