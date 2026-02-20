# adk-fluent

Fluent builder API for Google's [Agent Development Kit (ADK)](https://google.github.io/adk-docs/). Reduces agent creation from 22+ lines to 1-3 lines while producing identical native ADK objects.

[![CI](https://github.com/vamsiramakrishnan/adk-fluent/actions/workflows/ci.yml/badge.svg)](https://github.com/vamsiramakrishnan/adk-fluent/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/adk-fluent)](https://pypi.org/project/adk-fluent/)
[![Downloads](https://img.shields.io/pypi/dm/adk-fluent)](https://pypi.org/project/adk-fluent/)
[![Python](https://img.shields.io/pypi/pyversions/adk-fluent)](https://pypi.org/project/adk-fluent/)
[![License](https://img.shields.io/pypi/l/adk-fluent)](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/LICENSE)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://vamsiramakrishnan.github.io/adk-fluent/)
[![Wiki](https://img.shields.io/badge/wiki-GitHub-green)](https://github.com/vamsiramakrishnan/adk-fluent/wiki)
[![Typed](https://img.shields.io/badge/typing-typed-blue)](https://peps.python.org/pep-0561/)
[![ADK](https://img.shields.io/badge/google--adk-%E2%89%A51.20-orange)](https://google.github.io/adk-docs/)

## Table of Contents
- [Install](#install)
- [Quick Start](#quick-start)
- [Expression Language](#expression-language)
- [Context Engineering (C Module)](#context-engineering-c-module)
- [Fluent API Reference](#fluent-api-reference)
- [Run with adk web](#run-with-adk-web)
- [Cookbook](#cookbook)
- [How It Works](#how-it-works)
- [Features](#features)
- [Development](#development)

## Install

```bash
pip install adk-fluent
```

Autocomplete works immediately -- the package ships with `.pyi` type stubs for every builder. Type `Agent("name").` and your IDE shows all available methods with type hints.

### IDE Setup

**VS Code** -- install the [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) extension (included in the Python extension pack). Autocomplete and type checking work out of the box.

**PyCharm** -- works automatically. The `.pyi` stubs are bundled in the package and PyCharm discovers them on install.

**Neovim (LSP)** -- use [pyright](https://github.com/microsoft/pyright) as your language server. Stubs are picked up automatically.

### Discover the API

```python
from adk_fluent import Agent

agent = Agent("demo")
agent.  # <- autocomplete shows: .model(), .instruct(), .tool(), .build(), ...

# Typos are caught at definition time, not runtime:
agent.instuction("oops")  # -> AttributeError: 'instuction' is not a recognized field.
                          #    Did you mean: 'instruction'?

# Inspect any builder's current state:
print(agent.model("gemini-2.5-flash").instruct("Help.").explain())
# Agent: demo
#   Config fields: model, instruction

# See everything available:
print(dir(agent))  # All methods including forwarded ADK fields
```

## Quick Start

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop

# Simple agent — model as optional second arg or via .model()
agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.").build()

# Pipeline — build with .step() or >> operator
pipeline = (
    Pipeline("research")
    .step(Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
    .build()
)

# Fan-out — build with .branch() or | operator
fanout = (
    FanOut("parallel_research")
    .branch(Agent("web", "gemini-2.5-flash").instruct("Search the web."))
    .branch(Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
    .build()
)

# Loop — build with .step() + .max_iterations() or * operator
loop = (
    Loop("refine")
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write draft."))
    .step(Agent("critic", "gemini-2.5-flash").instruct("Critique."))
    .max_iterations(3)
    .build()
)
```

Every `.build()` returns a real ADK object (`LlmAgent`, `SequentialAgent`, etc.). Fully compatible with `adk web`, `adk run`, and `adk deploy`.

### Two Styles, Same Result

Every workflow can be expressed two ways -- the explicit builder API or the expression operators. Both produce identical ADK objects:

```python
# Explicit builder style — readable, IDE-friendly
pipeline = (
    Pipeline("research")
    .step(Agent("web", "gemini-2.5-flash").instruct("Search web.").outputs("web_data"))
    .step(Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}."))
    .build()
)

# Operator style — compact, composable
pipeline = (
    Agent("web", "gemini-2.5-flash").instruct("Search web.").outputs("web_data")
    >> Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}.")
).build()
```

The builder style shines for complex multi-step workflows where each step is configured with callbacks, tools, and context. The operator style excels at composing reusable sub-expressions:

```python
# Complex builder-style pipeline with tools and callbacks
pipeline = (
    Pipeline("customer_support")
    .step(
        Agent("classifier", "gemini-2.5-flash")
        .instruct("Classify the customer's intent.")
        .outputs("intent")
        .before_model(log_fn)
    )
    .step(
        Agent("resolver", "gemini-2.5-flash")
        .instruct("Resolve the {intent} issue.")
        .tool(lookup_customer)
        .tool(create_ticket)
        .history("none")
    )
    .step(
        Agent("responder", "gemini-2.5-flash")
        .instruct("Draft a response to the customer.")
        .after_model(audit_fn)
    )
    .build()
)

# Same complexity, composed from reusable parts with operators
classify = Agent("classifier", "gemini-2.5-flash").instruct("Classify intent.").outputs("intent")
resolve = Agent("resolver", "gemini-2.5-flash").instruct("Resolve {intent}.").tool(lookup_customer)
respond = Agent("responder", "gemini-2.5-flash").instruct("Draft response.")

support_pipeline = classify >> resolve >> respond
# Reuse sub-expressions in different pipelines
escalation_pipeline = classify >> Agent("escalate", "gemini-2.5-flash").instruct("Escalate.")
```

<!-- INJECT_MERMAID_DIAGRAM -->

## Expression Language

Nine operators compose any agent topology:

| Operator                       | Meaning            | ADK Type                 |
| ------------------------------ | ------------------ | ------------------------ |
| `a >> b`                       | Sequence           | `SequentialAgent`        |
| `a >> fn`                      | Function step      | Zero-cost transform      |
| `a \| b`                       | Parallel           | `ParallelAgent`          |
| `a * 3`                        | Loop (fixed)       | `LoopAgent`              |
| `a * until(pred)`              | Loop (conditional) | `LoopAgent` + checkpoint |
| `a @ Schema`                   | Typed output       | `output_schema`          |
| `a // b`                       | Fallback           | First-success chain      |
| `Route("key").eq(...)`         | Branch             | Deterministic routing    |
| `S.pick(...)`, `S.rename(...)` | State transforms   | Dict operations via `>>` |
| `C.user_only()`, `C.none()`    | Context engineering| Selective Turn History   |

Eight control loop primitives for agent orchestration:

| Primitive              | Purpose                        | ADK Mechanism                           |
| ---------------------- | ------------------------------ | --------------------------------------- |
| `tap(fn)`              | Observe state without mutating | Custom `BaseAgent` (no LLM)             |
| `expect(pred, msg)`    | Assert state contract          | Raises `ValueError` on failure          |
| `.mock(responses)`     | Bypass LLM for testing         | `before_model_callback` → `LlmResponse` |
| `.retry_if(pred)`      | Retry while condition holds    | `LoopAgent` + checkpoint escalate       |
| `map_over(key, agent)` | Iterate agent over list        | Custom `BaseAgent` loop                 |
| `.timeout(seconds)`    | Time-bound execution           | `asyncio` deadline + cancel             |
| `gate(pred, msg)`      | Human-in-the-loop approval     | `EventActions(escalate=True)`           |
| `race(a, b, ...)`      | First-to-finish wins           | `asyncio.wait(FIRST_COMPLETED)`         |

All operators are **immutable** -- sub-expressions can be safely reused:

```python
review = agent_a >> agent_b
pipeline_1 = review >> agent_c  # Independent
pipeline_2 = review >> agent_d  # Independent
```

### Function Steps

Plain Python functions compose with `>>` as zero-cost workflow nodes (no LLM call):

```python
def merge_research(state):
    return {"research": state["web"] + "\n" + state["papers"]}

pipeline = web_agent >> merge_research >> writer_agent
```

### Typed Output

`@` binds a Pydantic schema as the agent's output contract:

```python
from pydantic import BaseModel

class Report(BaseModel):
    title: str
    body: str

agent = Agent("writer").model("gemini-2.5-flash").instruct("Write.") @ Report
```

### Fallback Chains

`//` tries each agent in order -- first success wins:

```python
answer = (
    Agent("fast").model("gemini-2.0-flash").instruct("Quick answer.")
    // Agent("thorough").model("gemini-2.5-pro").instruct("Detailed answer.")
)
```

### Conditional Loops

`* until(pred)` loops until a predicate on session state is satisfied:

```python
from adk_fluent import until

loop = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write.").outputs("quality")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review.")
) * until(lambda s: s.get("quality") == "good", max=5)
```

### State Transforms

`S` factories return dict transforms that compose with `>>`:

```python
from adk_fluent import S

pipeline = (
    (web_agent | scholar_agent)
    >> S.merge("web", "scholar", into="research")
    >> S.default(confidence=0.0)
    >> S.rename(research="input")
    >> writer_agent
)
```

| Factory                 | Purpose                  |
| ----------------------- | ------------------------ |
| `S.pick(*keys) `        | Keep only specified keys |
| `S.drop(*keys)`         | Remove specified keys    |
| `S.rename(**kw)`        | Rename keys              |
| `S.default(**kw)`       | Fill missing keys        |
| `S.merge(*keys, into=)` | Combine keys             |
| `S.transform(key, fn)`  | Map a single value       |
| `S.compute(**fns)`      | Derive new keys          |
| `S.guard(pred)`         | Assert invariant         |
| `S.log(*keys)`          | Debug-print              |

### Context Engineering (C Module)

Control exactly what conversation history each agent sees. Prevents prompt pollution in complex DAGs:

```python
from adk_fluent import C

pipeline = (
    Agent("classifier").outputs("intent")
    >> Agent("booker")
        .instruct("Process {intent}")
        .context(C.user_only()) # Booker sees user prompt + {intent}, but NOT classifier text
)
```

| Transform | Purpose |
| --- | --- |
| `C.user_only()` | Include only original user messages |
| `C.none()` | No turn history (stateless prompt) |
| `C.window(n=5)` | Sliding window of last N turns |
| `C.from_agents("a", "b")` | Include user + named agent outputs |
| `C.capture("key")` | Snapshot user message into state |

### IR, Backends, and Middleware (v4)

Builders can compile to an intermediate representation (IR) for inspection, testing, and alternative backends:

```python
from adk_fluent import Agent, ExecutionConfig, CompactionConfig

# IR: inspect the agent tree without building
pipeline = Agent("a") >> Agent("b") >> Agent("c")
ir = pipeline.to_ir()  # Returns frozen dataclass tree

# to_app(): compile through IR to a native ADK App
app = pipeline.to_app(config=ExecutionConfig(
    app_name="my_app",
    resumable=True,
    compaction=CompactionConfig(interval=10),
))

# Middleware: app-global cross-cutting behavior
from adk_fluent import Middleware, RetryMiddleware, StructuredLogMiddleware

app = (
    Agent("a") >> Agent("b")
).middleware(RetryMiddleware(max_retries=3)).to_app()

# Data contracts: verify pipeline wiring at build time
from pydantic import BaseModel
from adk_fluent.testing import check_contracts

class Intent(BaseModel):
    category: str
    confidence: float

pipeline = Agent("classifier").produces(Intent) >> Agent("resolver").consumes(Intent)
issues = check_contracts(pipeline.to_ir())  # [] = all good

# Deterministic testing without LLM calls
from adk_fluent.testing import mock_backend, AgentHarness

harness = AgentHarness(pipeline, backend=mock_backend({
    "classifier": {"category": "billing", "confidence": 0.9},
    "resolver": "Ticket #1234 created.",
}))

# Graph visualization
print(pipeline.to_mermaid())  # Mermaid diagram source
```

```python
# Tool confirmation (human-in-the-loop approval)
agent = Agent("ops").tool(deploy_fn, require_confirmation=True)

# Resource DI (hide infra params from LLM)
agent = Agent("lookup").tool(search_db).inject(db=my_database)
```

### Deterministic Routing

Route on session state without LLM calls:

```python
from adk_fluent import Agent
from adk_fluent._routing import Route

classifier = Agent("classify").model("gemini-2.5-flash").instruct("Classify intent.").outputs("intent")
booker = Agent("booker").model("gemini-2.5-flash").instruct("Book flights.")
info = Agent("info").model("gemini-2.5-flash").instruct("Provide info.")

# Route on exact match — zero LLM calls for routing
pipeline = classifier >> Route("intent").eq("booking", booker).eq("info", info)

# Dict shorthand
pipeline = classifier >> {"booking": booker, "info": info}
```

### Conditional Gating

```python
# Only runs if predicate(state) is truthy
enricher = (
    Agent("enricher")
    .model("gemini-2.5-flash")
    .instruct("Enrich the data.")
    .proceed_if(lambda s: s.get("valid") == "yes")
)
```

### Tap (Observe Without Mutating)

`tap(fn)` creates a zero-cost observation step. It reads state but never writes back -- perfect for logging, metrics, and debugging:

```python
from adk_fluent import tap

pipeline = (
    writer
    >> tap(lambda s: print("Draft:", s.get("draft", "")[:50]))
    >> reviewer
)

# Also available as a method
pipeline = writer.tap(lambda s: log_metrics(s)) >> reviewer
```

### Expect (State Assertions)

`expect(pred, msg)` asserts a state contract at a pipeline step. Raises `ValueError` if the predicate fails:

```python
from adk_fluent import expect

pipeline = (
    writer
    >> expect(lambda s: "draft" in s, "Writer must produce a draft")
    >> reviewer
)
```

### Mock (Testing Without LLM)

`.mock(responses)` bypasses LLM calls with canned responses. Uses the same `before_model_callback` mechanism as ADK's `ReplayPlugin`, but scoped to a single agent:

```python
# List of responses (cycles when exhausted)
agent = Agent("writer").model("gemini-2.5-flash").instruct("Write.").mock(["Draft 1", "Draft 2"])

# Callable for dynamic mocking
agent = Agent("echo").model("gemini-2.5-flash").mock(lambda req: "Mocked response")
```

### Retry If

`.retry_if(pred)` retries agent execution while the predicate returns True. Thin wrapper over `loop_until` with inverted logic:

```python
agent = (
    Agent("writer").model("gemini-2.5-flash")
    .instruct("Write a high-quality draft.").outputs("quality")
    .retry_if(lambda s: s.get("quality") != "good", max_retries=3)
)
```

### Map Over

`map_over(key, agent)` iterates an agent over each item in a state list:

```python
from adk_fluent import map_over

pipeline = (
    fetcher
    >> map_over("documents", summarizer, output_key="summaries")
    >> compiler
)
```

### Timeout

`.timeout(seconds)` wraps an agent with a time limit. Raises `asyncio.TimeoutError` if exceeded:

```python
agent = Agent("researcher").model("gemini-2.5-pro").instruct("Deep research.").timeout(60)
```

### Gate (Human-in-the-Loop)

`gate(pred, msg)` pauses the pipeline for human approval when the condition is met. Uses ADK's `escalate` mechanism:

```python
from adk_fluent import gate

pipeline = (
    analyzer
    >> gate(lambda s: s.get("risk") == "high", message="Approve high-risk action?")
    >> executor
)
```

### Race (First-to-Finish)

`race(a, b, ...)` runs agents concurrently and keeps only the first to finish:

```python
from adk_fluent import race

winner = race(
    Agent("fast").model("gemini-2.0-flash").instruct("Quick answer."),
    Agent("thorough").model("gemini-2.5-pro").instruct("Detailed answer."),
)
```

### Full Composition

All operators compose into a single expression:

```python
from pydantic import BaseModel
from adk_fluent import Agent, S, until

class Report(BaseModel):
    title: str
    body: str
    confidence: float

pipeline = (
    (   Agent("web").model("gemini-2.5-flash").instruct("Search web.")
      | Agent("scholar").model("gemini-2.5-flash").instruct("Search papers.")
    )
    >> S.merge("web", "scholar", into="research")
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write.") @ Report
       // Agent("writer_b").model("gemini-2.5-pro").instruct("Write.") @ Report
    >> (
        Agent("critic").model("gemini-2.5-flash").instruct("Score.").outputs("confidence")
        >> Agent("reviser").model("gemini-2.5-flash").instruct("Improve.")
    ) * until(lambda s: s.get("confidence", 0) >= 0.85, max=4)
)
```

## Fluent API Reference

### Agent Builder

The `Agent` builder wraps ADK's `LlmAgent`. Every method returns `self` for chaining.

#### Core Configuration

| Method                  | Alias for     | Description                                                                |
| ----------------------- | ------------- | -------------------------------------------------------------------------- |
| `.model(name)`          | `model`       | LLM model identifier (`"gemini-2.5-flash"`, `"gemini-2.5-pro"`, etc.)      |
| `.instruct(text_or_fn)` | `instruction` | System instruction. Accepts a string or `Callable[[ReadonlyContext], str]` |
| `.describe(text)`       | `description` | Agent description (used in delegation and tool descriptions)               |
| `.outputs(key)`         | `output_key`  | Store the agent's final response in session state under this key           |
| `.tool(fn)`             | —             | Add a tool function or `BaseTool` instance. Multiple calls accumulate      |
| `.build()`              | —             | Resolve into a native ADK `LlmAgent`                                       |

#### Prompt & Context Control

| Method                   | Alias for            | Description                                                                                                   |
| ------------------------ | -------------------- | ------------------------------------------------------------------------------------------------------------- |
| `.instruct(text)`        | `instruction`        | Dynamic instruction. Supports `{variable}` placeholders auto-resolved from session state                      |
| `.instruct(fn)`          | `instruction`        | Callable receiving `ReadonlyContext`, returns string. Full programmatic control                               |
| `.static(content)`       | `static_instruction` | Cacheable instruction that never changes. Sent as system instruction for context caching                      |
| `.history("none")`       | `include_contents`   | Control conversation history: `"default"` (full history) or `"none"` (stateless)                              |
| `.global_instruct(text)` | `global_instruction` | Instruction inherited by all sub-agents                                                                       |
| `.inject_context(fn)`    | —                    | Prepend dynamic context via `before_model_callback`. The function receives callback context, returns a string |

Template variables in string instructions are auto-resolved from session state:

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

Optional variables use `?` suffix (`{maybe_key?}` returns empty string if missing). Namespaced keys: `{app:setting}`, `{user:pref}`, `{temp:scratch}`.

#### Prompt Builder

For multi-section prompts, the `Prompt` builder provides structured composition:

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

Sections are emitted in a fixed order (role, context, task, constraints, format, examples) regardless of call order. Prompts are composable and reusable:

```python
base_prompt = Prompt().role("You are a senior engineer.").constraint("Be precise.")

reviewer = Agent("reviewer").instruct(base_prompt + Prompt().task("Review code."))
writer   = Agent("writer").instruct(base_prompt + Prompt().task("Write documentation."))
```

| Method                 | Description                                   |
| ---------------------- | --------------------------------------------- |
| `.role(text)`          | Agent persona (emitted without header)        |
| `.context(text)`       | Background information                        |
| `.task(text)`          | Primary objective                             |
| `.constraint(text)`    | Rules to follow (multiple calls accumulate)   |
| `.format(text)`        | Desired output format                         |
| `.example(text)`       | Few-shot examples (multiple calls accumulate) |
| `.section(name, text)` | Custom named section                          |
| `.merge(other)` / `+`  | Combine two Prompts                           |
| `.build()` / `str()`   | Compile to instruction string                 |

#### Static Instructions & Context Caching

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

#### Dynamic Context Injection

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

#### Callbacks

All callback methods are **additive** -- multiple calls accumulate handlers, never replace:

| Method                | Alias for                 | Description                                                           |
| --------------------- | ------------------------- | --------------------------------------------------------------------- |
| `.before_model(fn)`   | `before_model_callback`   | Runs before each LLM call. Receives `(callback_context, llm_request)` |
| `.after_model(fn)`    | `after_model_callback`    | Runs after each LLM call. Receives `(callback_context, llm_response)` |
| `.before_agent(fn)`   | `before_agent_callback`   | Runs before agent execution                                           |
| `.after_agent(fn)`    | `after_agent_callback`    | Runs after agent execution                                            |
| `.before_tool(fn)`    | `before_tool_callback`    | Runs before each tool call                                            |
| `.after_tool(fn)`     | `after_tool_callback`     | Runs after each tool call                                             |
| `.on_model_error(fn)` | `on_model_error_callback` | Handles LLM errors                                                    |
| `.on_tool_error(fn)`  | `on_tool_error_callback`  | Handles tool errors                                                   |
| `.guardrail(fn)`      | —                         | Registers `fn` as both `before_model` and `after_model`               |

Conditional variants append only when the condition is true:

```python
agent = (
    Agent("service")
    .before_model_if(debug_mode, log_fn)
    .after_model_if(audit_enabled, audit_fn)
)
```

#### Control Flow

| Method                                | Description                                                                  |
| ------------------------------------- | ---------------------------------------------------------------------------- |
| `.proceed_if(pred)`                   | Only run this agent if `pred(state)` is truthy. Uses `before_agent_callback` |
| `.loop_until(pred, max_iterations=N)` | Wrap in a loop that exits when `pred(state)` is satisfied                    |
| `.retry_if(pred, max_retries=3)`      | Retry while `pred(state)` returns True. Inverse of `loop_until`              |
| `.mock(responses)`                    | Bypass LLM with canned responses (list or callable). For testing             |
| `.tap(fn)`                            | Append observation step: `self >> tap(fn)`. Returns Pipeline                 |
| `.timeout(seconds)`                   | Wrap with time limit. Raises `asyncio.TimeoutError` on expiry                |

#### Delegation (LLM-Driven Routing)

```python
# The coordinator's LLM decides when to delegate
coordinator = (
    Agent("coordinator")
    .model("gemini-2.5-flash")
    .instruct("Route tasks to the right specialist.")
    .delegate(Agent("math").model("gemini-2.5-flash").instruct("Solve math."))
    .delegate(Agent("code").model("gemini-2.5-flash").instruct("Write code."))
    .build()
)
```

`.delegate(agent)` wraps the sub-agent in an `AgentTool` so the coordinator's LLM can invoke it by name.

#### One-Shot Execution

| Method                                        | Description                                                     |
| --------------------------------------------- | --------------------------------------------------------------- |
| `.ask(prompt)`                                | Send a prompt, get response text. No Runner/Session boilerplate |
| `.ask_async(prompt)`                          | Async version of `.ask()`                                       |
| `.stream(prompt)`                             | Async generator yielding response text chunks                   |
| `.events(prompt)`                             | Async generator yielding raw ADK `Event` objects                |
| `.map(prompts, concurrency=5)`                | Batch execution against multiple prompts                        |
| `.map_async(prompts, concurrency=5)`          | Async batch execution                                           |
| `.session()`                                  | Create an interactive `async with` session context manager      |
| `.test(prompt, contains=, matches=, equals=)` | Smoke test: calls `.ask()` and asserts output                   |

#### Cloning and Variants

```python
base = Agent("base").model("gemini-2.5-flash").instruct("Be helpful.")

# Clone — independent deep copy with new name
math_agent = base.clone("math").instruct("Solve math.")

# with_() — immutable variant (original unchanged)
creative = base.with_(name="creative", model="gemini-2.5-pro")
```

#### Validation and Introspection

| Method                      | Description                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------- |
| `.validate()`               | Try `.build()` and raise `ValueError` with clear message on failure. Returns `self` |
| `.explain()`                | Multi-line summary of builder state (config fields, callbacks, lists)               |
| `.to_dict()` / `.to_yaml()` | Serialize builder state (inspection only, no round-trip)                            |

#### Dynamic Field Forwarding

Any ADK `LlmAgent` field can be set through `__getattr__`, even without an explicit method:

```python
agent = Agent("x").generate_content_config(my_config)  # Works via forwarding
```

Misspelled names raise `AttributeError` with the closest match suggestion.

### Workflow Builders

All workflow builders accept both built ADK agents and fluent builders as arguments. Builders are auto-built at `.build()` time, enabling safe sub-expression reuse.

#### Pipeline (Sequential)

```python
from adk_fluent import Pipeline, Agent

# Builder style — full control over each step
pipeline = (
    Pipeline("data_processing")
    .step(Agent("extractor", "gemini-2.5-flash").instruct("Extract entities.").outputs("entities"))
    .step(Agent("enricher", "gemini-2.5-flash").instruct("Enrich {entities}.").tool(lookup_db))
    .step(Agent("formatter", "gemini-2.5-flash").instruct("Format output.").history("none"))
    .build()
)

# Operator style — same result
pipeline = (
    Agent("extractor", "gemini-2.5-flash").instruct("Extract entities.").outputs("entities")
    >> Agent("enricher", "gemini-2.5-flash").instruct("Enrich {entities}.").tool(lookup_db)
    >> Agent("formatter", "gemini-2.5-flash").instruct("Format output.").history("none")
).build()
```

| Method         | Description                                                        |
| -------------- | ------------------------------------------------------------------ |
| `.step(agent)` | Append an agent as the next step. Lazy -- built at `.build()` time |
| `.build()`     | Resolve into a native ADK `SequentialAgent`                        |

#### FanOut (Parallel)

```python
from adk_fluent import FanOut, Agent

# Builder style — named branches with different models
fanout = (
    FanOut("research")
    .branch(Agent("web", "gemini-2.5-flash").instruct("Search the web.").outputs("web_results"))
    .branch(Agent("papers", "gemini-2.5-pro").instruct("Search academic papers.").outputs("paper_results"))
    .branch(Agent("internal", "gemini-2.5-flash").instruct("Search internal docs.").outputs("internal_results"))
    .build()
)

# Operator style
fanout = (
    Agent("web", "gemini-2.5-flash").instruct("Search web.").outputs("web_results")
    | Agent("papers", "gemini-2.5-pro").instruct("Search papers.").outputs("paper_results")
    | Agent("internal", "gemini-2.5-flash").instruct("Search internal docs.").outputs("internal_results")
).build()
```

| Method           | Description                                                   |
| ---------------- | ------------------------------------------------------------- |
| `.branch(agent)` | Add a parallel branch agent. Lazy -- built at `.build()` time |
| `.build()`       | Resolve into a native ADK `ParallelAgent`                     |

#### Loop

```python
from adk_fluent import Loop, Agent, until

# Builder style — explicit loop configuration
loop = (
    Loop("quality_loop")
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write draft.").outputs("quality"))
    .step(Agent("reviewer", "gemini-2.5-flash").instruct("Review and score."))
    .max_iterations(5)
    .until(lambda s: s.get("quality") == "good")
    .build()
)

# Operator style
loop = (
    Agent("writer", "gemini-2.5-flash").instruct("Write draft.").outputs("quality")
    >> Agent("reviewer", "gemini-2.5-flash").instruct("Review and score.")
) * until(lambda s: s.get("quality") == "good", max=5)
```

| Method               | Description                                            |
| -------------------- | ------------------------------------------------------ |
| `.step(agent)`       | Append a step agent. Lazy -- built at `.build()` time  |
| `.max_iterations(n)` | Set maximum loop iterations                            |
| `.until(pred)`       | Set exit predicate. Exits when `pred(state)` is truthy |
| `.build()`           | Resolve into a native ADK `LoopAgent`                  |

#### Combining Builder and Operator Styles

The styles mix freely. Use builders for complex individual steps and operators for composition:

```python
from adk_fluent import Agent, Pipeline, FanOut, S, until, Prompt

# Define reusable agents with full builder configuration
researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct(Prompt().role("You are a research analyst.").task("Find relevant information."))
    .tool(search_tool)
    .before_model(log_fn)
    .outputs("findings")
)

writer = (
    Agent("writer", "gemini-2.5-pro")
    .instruct("Write a report about {findings}.")
    .static("Company style guide: use formal tone, cite sources...")
    .outputs("draft")
)

reviewer = (
    Agent("reviewer", "gemini-2.5-flash")
    .instruct("Score the draft 1-10 for quality.")
    .outputs("quality_score")
)

# Compose with operators — each sub-expression is reusable
research_phase = (
    FanOut("gather")
    .branch(researcher.clone("web").tool(web_search))
    .branch(researcher.clone("papers").tool(paper_search))
)

pipeline = (
    research_phase
    >> S.merge("web", "papers", into="findings")
    >> writer
    >> (reviewer >> writer) * until(lambda s: int(s.get("quality_score", 0)) >= 8, max=3)
)
```

### Presets

Reusable configuration bundles:

```python
from adk_fluent.presets import Preset

production = Preset(model="gemini-2.5-flash", before_model=log_fn, after_model=audit_fn)

agent = Agent("service").instruct("Handle requests.").use(production).build()
```

### @agent Decorator

```python
from adk_fluent.decorators import agent

@agent("weather_bot", model="gemini-2.5-flash")
def weather_bot():
    """You help with weather queries."""

@weather_bot.tool
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

built = weather_bot.build()
```

### Typed State Keys

```python
from adk_fluent import StateKey

call_count = StateKey("call_count", scope="session", type=int, default=0)

# In callbacks/tools:
current = call_count.get(ctx)
call_count.increment(ctx)
```

## Run with `adk web`

### Environment Setup

Before running any example, copy the `.env.example` and fill in your Google Cloud credentials:

```bash
cd examples
cp .env.example .env
# Edit .env with your values:
#   GOOGLE_CLOUD_PROJECT=your-project-id
#   GOOGLE_CLOUD_LOCATION=us-central1
#   GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

Every agent loads these variables automatically via `load_dotenv()`.

### Run an Example

```bash
cd examples
adk web simple_agent          # Basic agent
adk web weather_agent         # Agent with tools
adk web research_team         # Multi-agent pipeline
adk web real_world_pipeline   # Full expression language
adk web route_branching       # Deterministic routing
adk web delegate_pattern      # LLM-driven delegation
adk web operator_composition  # >> | * operators
adk web function_steps        # >> fn (function nodes)
adk web until_operator        # * until(pred)
adk web typed_output          # @ Schema
adk web fallback_operator     # // fallback
adk web state_transforms      # S.pick, S.rename, ...
adk web full_algebra          # All operators together
adk web tap_observation       # tap() observation steps
adk web mock_testing          # .mock() for testing
adk web race                  # race() first-to-finish
```

43 runnable examples covering all features. See [`examples/`](examples/) for the full list.

## Cookbook

43 annotated examples in [`examples/cookbook/`](examples/cookbook/) with side-by-side Native ADK vs Fluent comparisons. Each file is also a runnable test:

```bash
pytest examples/cookbook/ -v
```

| #   | Example              | Feature                              |
| --- | -------------------- | ------------------------------------ |
| 01  | Simple Agent         | Basic agent creation                 |
| 02  | Agent with Tools     | Tool registration                    |
| 03  | Callbacks            | Additive callback accumulation       |
| 04  | Sequential Pipeline  | Pipeline builder                     |
| 05  | Parallel FanOut      | FanOut builder                       |
| 06  | Loop Agent           | Loop builder                         |
| 07  | Team Coordinator     | Sub-agent delegation                 |
| 08  | One-Shot Ask         | `.ask()` execution                   |
| 09  | Streaming            | `.stream()` execution                |
| 10  | Cloning              | `.clone()` deep copy                 |
| 11  | Inline Testing       | `.test()` smoke tests                |
| 12  | Guardrails           | `.guardrail()` shorthand             |
| 13  | Interactive Session  | `.session()` context manager         |
| 14  | Dynamic Forwarding   | `__getattr__` field access           |
| 15  | Production Runtime   | Full agent setup                     |
| 16  | Operator Composition | `>>` `\|` `*` operators              |
| 17  | Route Branching      | Deterministic `Route`                |
| 18  | Dict Routing         | `>>` dict shorthand                  |
| 19  | Conditional Gating   | `.proceed_if()`                      |
| 20  | Loop Until           | `.loop_until()`                      |
| 21  | StateKey             | Typed state descriptors              |
| 22  | Presets              | `Preset` + `.use()`                  |
| 23  | With Variants        | `.with_()` immutable copy            |
| 24  | @agent Decorator     | Decorator syntax                     |
| 25  | Validate & Explain   | `.validate()` `.explain()`           |
| 26  | Serialization        | `to_dict` / `to_yaml`                |
| 27  | Delegate Pattern     | `.delegate()`                        |
| 28  | Real-World Pipeline  | Full composition                     |
| 29  | Function Steps       | `>> fn` zero-cost transforms         |
| 30  | Until Operator       | `* until(pred)` conditional loops    |
| 31  | Typed Output         | `@ Schema` output contracts          |
| 32  | Fallback Operator    | `//` first-success chains            |
| 33  | State Transforms     | `S.pick`, `S.rename`, `S.merge`, ... |
| 34  | Full Algebra         | All operators composed together      |
| 35  | Tap Observation      | `tap()` pure observation steps       |
| 36  | Expect Assertions    | `expect()` state contract checks     |
| 37  | Mock Testing         | `.mock()` bypass LLM for tests       |
| 38  | Retry If             | `.retry_if()` conditional retry      |
| 39  | Map Over             | `map_over()` iterate agent over list |
| 40  | Timeout              | `.timeout()` time-bound execution    |
| 41  | Gate Approval        | `gate()` human-in-the-loop           |
| 42  | Race                 | `race()` first-to-finish wins        |

## How It Works

adk-fluent is **auto-generated** from the installed ADK package:

```
scanner.py ──> manifest.json ──> seed_generator.py ──> seed.toml ──> generator.py ──> Python code
                                      ^
                              seed.manual.toml
                              (hand-crafted extras)
```

1. **Scanner** introspects all ADK modules and produces `manifest.json`
1. **Seed Generator** classifies classes and produces `seed.toml` (merged with manual extras)
1. **Code Generator** emits fluent builders, `.pyi` type stubs, and test scaffolds

This means adk-fluent automatically stays in sync with ADK updates:

```bash
pip install --upgrade google-adk
just all   # Regenerate everything
just test  # Verify
```

## API Reference

Generated API docs are in [`docs/generated/api/`](docs/generated/api/):

- [`agent.md`](docs/generated/api/agent.md) -- Agent, BaseAgent builders
- [`workflow.md`](docs/generated/api/workflow.md) -- Pipeline, FanOut, Loop
- [`tool.md`](docs/generated/api/tool.md) -- 40+ tool builders
- [`service.md`](docs/generated/api/service.md) -- Session, artifact, memory services
- [`config.md`](docs/generated/api/config.md) -- Configuration builders
- [`plugin.md`](docs/generated/api/plugin.md) -- Plugin builders
- [`runtime.md`](docs/generated/api/runtime.md) -- Runner, App builders

Migration guide: [`docs/generated/migration/from-native-adk.md`](docs/generated/migration/from-native-adk.md)

## Features

- **130+ builders** covering agents, tools, configs, services, plugins, planners, executors
- **Expression algebra**: `>>` (sequence), `|` (parallel), `*` (loop), `@` (typed output), `//` (fallback), `>> fn` (transforms), `S` (state ops), `Route` (branch)
- **Prompt builder**: structured multi-section prompt composition via `Prompt`
- **Template variables**: `{key}` in instructions auto-resolved from session state
- **Context control**: `.static()` for cacheable context, `.history("none")` for stateless agents, `.inject_context()` for dynamic preambles
- **State transforms**: `S.pick`, `S.drop`, `S.rename`, `S.default`, `S.merge`, `S.transform`, `S.compute`, `S.guard`
- **Full IDE autocomplete** via `.pyi` type stubs
- **Zero-maintenance** `__getattr__` forwarding for any ADK field
- **Callback accumulation**: multiple `.before_model()` calls append, not replace
- **Typo detection**: misspelled methods raise `AttributeError` with suggestions
- **Deterministic routing**: `Route` evaluates predicates against session state (zero LLM calls)
- **One-shot execution**: `.ask()`, `.stream()`, `.session()`, `.map()` without Runner boilerplate
- **Presets**: reusable config bundles via `Preset` + `.use()`
- **Cloning**: `.clone()` and `.with_()` for independent variants
- **Validation**: `.validate()` catches config errors at definition time
- **Serialization**: `to_dict()`, `to_yaml()`, `from_dict()`, `from_yaml()`
- **@agent decorator**: FastAPI-style agent definition
- **Typed state**: `StateKey` with scope, type, and default

## Development

```bash
# Setup
uv venv .venv && source .venv/bin/activate
uv pip install google-adk pytest pyright

# Full pipeline: scan -> seed -> generate -> docs
just all

# Run tests (780+ tests)
just test

# Type check generated stubs
just typecheck

# Generate cookbook stubs for new builders
just cookbook-gen

# Convert cookbook to adk-web agent folders
just agents
```

## Publishing

Releases are published automatically to PyPI when a version tag is pushed:

```bash
# 1. Bump version in pyproject.toml
# 2. Commit and tag
git tag v0.2.0
git push origin v0.2.0
# 3. CI runs tests -> builds -> publishes to PyPI automatically
```

TestPyPI publishing is available manually via the GitLab CI web interface.

## License

MIT
