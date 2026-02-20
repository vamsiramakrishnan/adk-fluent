# Prompt Builder

The `Prompt` class provides structured, composable prompt construction for multi-section instructions.

## Basic Usage

```python
from adk_fluent import Prompt

prompt = (
    Prompt()
    .role("You are a senior code reviewer.")
    .context("The codebase uses Python 3.11 with type hints.")
    .task("Review the code for bugs and security issues.")
    .constraint("Be concise. Max 5 bullet points.")
    .constraint("No false positives.")
    .format("Return markdown with ## sections.")
    .example("Input: x=eval(input()) | Output: - **Critical**: eval() on user input")
)

agent = Agent("reviewer").model("gemini-2.5-flash").instruct(prompt).build()
```

## Sections

Sections are emitted in a fixed order regardless of call order: role, context, task, constraints, format, examples.

| Method                 | Description                                   |
| ---------------------- | --------------------------------------------- |
| `.role(text)`          | Agent persona (emitted without header)        |
| `.context(text)`       | Background information                        |
| `.task(text)`          | Primary objective                             |
| `.constraint(text)`    | Rules to follow (multiple calls accumulate)   |
| `.format(text)`        | Desired output format                         |
| `.example(text)`       | Few-shot examples (multiple calls accumulate) |
| `.section(name, text)` | Custom named section                          |
| `.build()` / `str()`   | Compile to instruction string                 |

### `.role(text)`

Sets the agent persona. The role text is emitted first in the compiled prompt, without a section header:

```python
prompt = Prompt().role("You are a senior financial analyst with 20 years of experience.")
```

### `.context(text)`

Provides background information for the agent:

```python
prompt = Prompt().context("The user is a small business owner looking for tax advice.")
```

### `.task(text)`

Defines the primary objective:

```python
prompt = Prompt().task("Analyze the quarterly earnings report and provide key insights.")
```

### `.constraint(text)`

Adds rules the agent must follow. Multiple calls accumulate constraints:

```python
prompt = (
    Prompt()
    .constraint("Be concise. Max 5 bullet points.")
    .constraint("No speculation -- cite sources.")
    .constraint("Use formal tone.")
)
```

### `.format(text)`

Specifies the desired output format:

```python
prompt = Prompt().format("Return a JSON object with keys: summary, risks, opportunities.")
```

### `.example(text)`

Adds few-shot examples. Multiple calls accumulate:

```python
prompt = (
    Prompt()
    .example("Input: Revenue up 15% | Output: Positive growth trend")
    .example("Input: Margins declining | Output: Cost pressure warning")
)
```

### `.section(name, text)`

Adds a custom named section:

```python
prompt = Prompt().section("Audience", "C-level executives with limited technical background.")
```

## Composability with `+`

Prompts are composable and reusable via the `+` operator (or `.merge()`):

```python
base_prompt = Prompt().role("You are a senior engineer.").constraint("Be precise.")

reviewer = Agent("reviewer").instruct(base_prompt + Prompt().task("Review code."))
writer   = Agent("writer").instruct(base_prompt + Prompt().task("Write documentation."))
```

This allows you to define common persona, constraints, and context once, then specialize with task-specific sections.

## Template Variables

String instructions support `{variable}` placeholders auto-resolved from session state:

```python
# {topic} and {style} are replaced at runtime from session state
agent = Agent("writer").instruct("Write about {topic} in a {style} tone.")
```

This composes naturally with the expression algebra:

```python
pipeline = (
    Agent("classifier").instruct("Classify.").outputs("topic")
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
