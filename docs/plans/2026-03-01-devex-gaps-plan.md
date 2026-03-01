# DevEx Gaps Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address 10 developer experience gaps in the README to accelerate adoption and build trust, plus integrate the ADK sync workflow properly.

**Architecture:** All README content lives in `README.template.md`, processed by `scripts/readme_generator.py` (which injects a Mermaid diagram at `<!-- INJECT_MERMAID_DIAGRAM -->`). Edits go to the template; `just readme` regenerates `README.md`. New standalone files: `quickstart.py`, `scripts/benchmark.py`. The existing `sync-adk.yml` in repo root gets moved to `.github/workflows/` for proper integration.

**Tech Stack:** Markdown, Python, just (task runner), GitHub Actions

______________________________________________________________________

### Task 1: Create quickstart.py

**Files:**

- Create: `quickstart.py`

**Step 1: Create the file**

```python
"""adk-fluent quickstart -- copy this file, set one env var, run."""

from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct(
    "You are a helpful assistant. Be concise."
)

print(agent.ask("Summarize the benefits of Python in one sentence."))
```

**Step 2: Verify it's syntactically valid**

Run: `python -c "import ast; ast.parse(open('quickstart.py').read()); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add quickstart.py
git commit -m "docs: add standalone quickstart.py for zero-to-running onboarding"
```

______________________________________________________________________

### Task 2: Create scripts/benchmark.py

**Files:**

- Create: `scripts/benchmark.py`

**Step 1: Create the benchmark script**

```python
#!/usr/bin/env python3
"""Measure adk-fluent build overhead vs native ADK construction.

Usage:
    python scripts/benchmark.py
"""

from __future__ import annotations

import sys
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adk_fluent import Agent  # noqa: E402
from google.adk.agents import LlmAgent  # noqa: E402


def fluent_build():
    Agent("bench", "gemini-2.5-flash").instruct("You are helpful.").build()


def native_build():
    LlmAgent(name="bench", model="gemini-2.5-flash", instruction="You are helpful.")


def main():
    n = 10_000
    native_time = timeit.timeit(native_build, number=n)
    fluent_time = timeit.timeit(fluent_build, number=n)

    print(f"Native ADK:  {native_time:.4f}s for {n:,} builds ({native_time / n * 1e6:.1f} \u00b5s/build)")
    print(f"adk-fluent:  {fluent_time:.4f}s for {n:,} builds ({fluent_time / n * 1e6:.1f} \u00b5s/build)")
    print(f"Overhead:    {(fluent_time - native_time) / n * 1e6:.1f} \u00b5s/build")
    print(f"Ratio:       {fluent_time / native_time:.2f}x")


if __name__ == "__main__":
    main()
```

**Step 2: Verify it parses**

Run: `python -c "import ast; ast.parse(open('scripts/benchmark.py').read()); print('OK')"`
Expected: `OK`

**Step 3: Run the benchmark**

Run: `cd /home/user/adk-fluent && uv run python scripts/benchmark.py`
Expected: Output showing microsecond-level overhead per build.

**Step 4: Commit**

```bash
git add scripts/benchmark.py
git commit -m "feat: add build overhead benchmark script"
```

______________________________________________________________________

### Task 3: Update badges in README.template.md

**Files:**

- Modify: `README.template.md:5-13`

**Step 1: Add coverage and status badges**

After line 13 (`[![ADK]...`), add two new badges:

```markdown
[![Coverage](https://codecov.io/gh/vamsiramakrishnan/adk-fluent/branch/master/graph/badge.svg)](https://codecov.io/gh/vamsiramakrishnan/adk-fluent)
[![Status](https://img.shields.io/badge/status-beta-yellow)](https://github.com/vamsiramakrishnan/adk-fluent)
```

**Step 2: Verify badges render correctly in template**

Run: `head -16 README.template.md`
Expected: 11 badge lines total (9 existing + 2 new).

**Step 3: Commit**

```bash
git add README.template.md
git commit -m "docs: add coverage and beta status badges"
```

______________________________________________________________________

### Task 4: Rewrite Quick Start to lead with .ask()

**Files:**

- Modify: `README.template.md:15-99`

**Step 1: Update the Table of Contents**

Replace lines 15-26 with:

```markdown
## Table of Contents

- [Install](#install)
- [Quick Start](#quick-start)
- [Zero to Running](#zero-to-running)
- [Expression Language](#expression-language)
- [Context Engineering (C Module)](#context-engineering-c-module)
- [Common Errors](#common-errors)
- [Fluent API Reference](#fluent-api-reference)
- [When to Use adk-fluent](#when-to-use-adk-fluent)
- [Run with adk web](#run-with-adk-web)
- [Cookbook](#cookbook)
- [Performance](#performance)
- [ADK Compatibility](#adk-compatibility)
- [How It Works](#how-it-works)
- [Features](#features)
- [Development](#development)
```

**Step 2: Rewrite the Quick Start section**

Replace lines 65-97 (the existing Quick Start code block) with:

````markdown
## Quick Start

```python
from adk_fluent import Agent

# Create an agent and get a response -- no Runner, no Session, no boilerplate
agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")
print(agent.ask("What is the capital of France?"))
# => The capital of France is Paris.
````

`.ask()` handles Runner, Session, and cleanup internally. One line to define, one line to run.

For ADK integration, `.build()` returns the native ADK object:

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop

# Simple agent -- returns a native LlmAgent
agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.").build()

# Pipeline -- sequential agents
pipeline = (
    Pipeline("research")
    .step(Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
    .build()
)

# Fan-out -- parallel agents
fanout = (
    FanOut("parallel_research")
    .branch(Agent("web", "gemini-2.5-flash").instruct("Search the web."))
    .branch(Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
    .build()
)

# Loop -- iterative refinement
loop = (
    Loop("refine")
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write draft."))
    .step(Agent("critic", "gemini-2.5-flash").instruct("Critique."))
    .max_iterations(3)
    .build()
)
```

Every `.build()` returns a real ADK object (`LlmAgent`, `SequentialAgent`, etc.). Fully compatible with `adk web`, `adk run`, and `adk deploy`.

````

Note: Keep lines 99-158 (Two Styles, Same Result + complex example + INJECT_MERMAID_DIAGRAM) unchanged.

**Step 3: Commit**

```bash
git add README.template.md
git commit -m "docs: rewrite Quick Start to lead with .ask() and visible output"
````

______________________________________________________________________

### Task 5: Add Zero to Running section

**Files:**

- Modify: `README.template.md` -- insert after the `<!-- INJECT_MERMAID_DIAGRAM -->` line (line 158) and before `## Expression Language` (line 160)

**Step 1: Insert the new section**

Insert between `<!-- INJECT_MERMAID_DIAGRAM -->` and `## Expression Language`:

````markdown
## Zero to Running

### Fastest: Google AI Studio (free tier)

```bash
pip install adk-fluent
export GOOGLE_API_KEY="your-key-from-aistudio.google.com"
python quickstart.py
````

Get a free API key at [aistudio.google.com](https://aistudio.google.com/apikey).

### Production: Vertex AI

```bash
pip install adk-fluent
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_GENAI_USE_VERTEXAI="TRUE"
python quickstart.py
```

Requires a GCP project with the Vertex AI API enabled. See [Vertex AI setup](https://cloud.google.com/vertex-ai/docs/start/introduction-unified-platform).

Both paths produce the same result -- the [`quickstart.py`](quickstart.py) file works with either configuration.

````

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: add Zero to Running section with AI Studio and Vertex AI paths"
````

______________________________________________________________________

### Task 6: Add ASCII operator algebra visualizations

**Files:**

- Modify: `README.template.md` -- insert after the operator tables (after line ~196 "pipeline_2 = review >> agent_d  # Independent") and before `### Function Steps`

**Step 1: Insert ASCII visualizations**

Insert after the immutability example (`pipeline_2 = review >> agent_d`) and before `### Function Steps`:

```markdown
### How Operators Map to Agent Trees

```

Expression:   a >> (b | c) * 3

Agent tree:
SequentialAgent
+-- a (LlmAgent)
+-- LoopAgent (max_iterations=3)
+-- ParallelAgent
+-- b (LlmAgent)
+-- c (LlmAgent)

```

```

Expression:   a >> fn >> Route("key").eq("x", b).eq("y", c)

Agent tree:
SequentialAgent
+-- a (LlmAgent)
+-- fn (FunctionAgent)
+-- RoutingAgent
+-- "x" -> b (LlmAgent)
+-- "y" -> c (LlmAgent)

```

```

Expression:   (a | b) >> merge_fn >> writer @ Report // fallback_writer @ Report

Agent tree:
SequentialAgent
+-- ParallelAgent
|   +-- a (LlmAgent)
|   +-- b (LlmAgent)
+-- merge_fn (FunctionAgent)
+-- FallbackAgent
+-- writer (LlmAgent, output_schema=Report)
+-- fallback_writer (LlmAgent, output_schema=Report)

```
```

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: add ASCII operator-to-agent-tree visualizations"
```

______________________________________________________________________

### Task 7: Add Common Errors section

**Files:**

- Modify: `README.template.md` -- insert after the Context Engineering section (after line ~296) and before `### IR, Backends, and Middleware`

**Step 1: Insert Common Errors section**

Insert before `### IR, Backends, and Middleware (v4)`:

````markdown
### Common Errors

**Missing required field:**

```python
Agent("x").instruct("Hi").build()
# BuilderError: Agent 'x' is missing required field 'model'
#   model: required (not set)
````

Fix: add `.model("gemini-2.5-flash")` before `.build()`.

**Typo in method name:**

```python
Agent("x").modle("gemini-2.5-flash")
# AttributeError: 'modle' is not a recognized field. Did you mean: 'model'?
```

The typo detector suggests the closest valid field name.

**Invalid operator operand:**

```python
Agent("a") | "not an agent"
# TypeError: unsupported operand type(s) for |: 'AgentBuilder' and 'str'
```

Operators work with `Agent`, `Pipeline`, `FanOut`, `Loop` builders, callables, and built ADK agents.

**Template variable at runtime:**

```python
# {topic} resolves from session state at runtime, not at definition time
agent = Agent("writer", "gemini-2.5-flash").instruct("Write about {topic}.")
agent.ask("hello")  # {topic} appears literally if not in state
```

Use `.outputs("topic")` on a prior agent, or pass initial state via `.session()`.

Full error reference: [Error Reference](https://vamsiramakrishnan.github.io/adk-fluent/user-guide/error-reference/)

````

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: add Common Errors section with 4 examples and fixes"
````

______________________________________________________________________

### Task 8: Add When to Use section

**Files:**

- Modify: `README.template.md` -- insert before `## Run with adk web` (line ~904)

**Step 1: Insert the section**

Insert before `## Run with adk web`:

```markdown
## When to Use adk-fluent

**Use adk-fluent when you want to:**

- Define agents in 1-3 lines instead of 22+
- Compose pipelines, fan-out, loops, and routing with operators (`>>`, `|`, `*`, `//`)
- Get IDE autocomplete and type checking during development
- Test agents deterministically with `.mock()` and `.test()` (no API calls)
- Iterate quickly with `.ask()` and `.stream()` (no Runner/Session boilerplate)

**Use raw ADK directly when you need to:**

- Subclass `BaseAgent` with custom `_run_async_impl` logic
- Access ADK internals not exposed through the builder API
- Build framework-level tooling that wraps ADK itself
- Manage Runner/Session lifecycle with fine-grained control beyond `.session()`

adk-fluent produces native ADK objects. You can mix fluent-built agents with hand-built agents in the same pipeline -- they're the same types.
```

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: add When to Use / When Not to Use section"
```

______________________________________________________________________

### Task 9: Restructure Cookbook with tiering

**Files:**

- Modify: `README.template.md:945-996` (the Cookbook section)

**Step 1: Replace the flat cookbook table**

Replace the Cookbook section (from `## Cookbook` through the end of the 42-row table) with:

```markdown
## Cookbook

66 annotated examples in [`examples/cookbook/`](examples/cookbook/) with side-by-side Native ADK vs Fluent comparisons. Each file is also a runnable test: `pytest examples/cookbook/ -v`

### Start Here

| #   | Example          | What You'll Learn                    |
| --- | ---------------- | ------------------------------------ |
| 01  | Simple Agent     | Create and build your first agent    |
| 08  | One-Shot Ask     | Run an agent with `.ask()` -- no boilerplate |
| 04  | Sequential Pipeline | Chain agents with `Pipeline` or `>>` |

### Core Patterns

| #   | Example              | What You'll Learn                       |
| --- | -------------------- | --------------------------------------- |
| 02  | Agent with Tools     | Attach tool functions                   |
| 03  | Callbacks            | `before_model`, `after_model` hooks     |
| 05  | Parallel FanOut      | Run agents in parallel with `FanOut` or `\|` |
| 07  | Team Coordinator     | LLM-driven delegation with `.delegate()`|
| 16  | Operator Composition | `>>` `\|` `*` operators together        |
| 17  | Route Branching      | Deterministic routing with `Route`      |
| 33  | State Transforms     | `S.pick`, `S.rename`, `S.merge`         |
| 37  | Mock Testing         | Test without LLM calls using `.mock()`  |
| 31  | Typed Output         | Pydantic schemas with `@ Schema`        |
| 11  | Inline Testing       | Smoke tests with `.test()`              |

### All Examples

<details>
<summary>Full list (66 examples)</summary>

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
| 43+ | Advanced             | Middleware, DI, schemas, contracts   |

</details>

Browse by use case on the [docs site](https://vamsiramakrishnan.github.io/adk-fluent/generated/cookbook/recipes-by-use-case/).
```

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: restructure cookbook with Start Here / Core / All tiering"
```

______________________________________________________________________

### Task 10: Add Performance section

**Files:**

- Modify: `README.template.md` -- insert before `## How It Works`

**Step 1: Insert the section**

Insert before `## How It Works`:

````markdown
## Performance

adk-fluent is a **build-time layer**. Calling `.build()` produces a native ADK object -- the same `LlmAgent`, `SequentialAgent`, or `ParallelAgent` you'd construct manually. After `.build()`, adk-fluent is not in the execution path. There is no runtime wrapper, proxy, or middleware layer injected by the builder itself.

**Build overhead:** Builder construction adds microseconds of Python dict manipulation per agent. For context, a single Gemini API call takes 500ms-30s.

Verify yourself:

```bash
python scripts/benchmark.py
````

````

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: add Performance section explaining zero-cost build pattern"
````

______________________________________________________________________

### Task 11: Add ADK Compatibility section

**Files:**

- Modify: `README.template.md` -- insert after `## Performance` and before `## How It Works`

**Step 1: Insert the section**

```markdown
## ADK Compatibility

| adk-fluent | google-adk | Tested in CI | Notes           |
| ---------- | ---------- | ------------ | --------------- |
| 0.11.x     | 1.25.0     | Yes          | Current release |
| 0.9.x      | 1.25.0     | Yes          |                 |
| 0.1-0.8    | 1.20.0+    | Yes          | Initial series  |

CI pins `google-adk==1.25.0` for hermetic builds. The `>=1.20.0` floor in `pyproject.toml` means newer ADK versions should work, but only the pinned version is tested.

A [weekly sync workflow](.github/workflows/sync-adk.yml) scans for new ADK releases every Monday, regenerates code, runs tests, and opens a PR automatically. If you hit an incompatibility, [open an issue](https://github.com/vamsiramakrishnan/adk-fluent/issues).
```

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: add ADK Compatibility version matrix"
```

______________________________________________________________________

### Task 12: Update Development section and add changelog visibility

**Files:**

- Modify: `README.template.md:1056-1095` (Development and Publishing sections)

**Step 1: Update the Development section**

Replace the Development section with:

````markdown
## Development

**Requires:** Python 3.11+, [just](https://github.com/casey/just#installation), [uv](https://docs.astral.sh/uv/)

**Container:** Open in VS Code or GitHub Codespaces with the included Dev Container for a pre-configured environment.

```bash
# Setup
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Full pipeline: scan -> seed -> generate -> docs
just all

# Run tests (780+ tests)
just test

# Type check hand-written code
just typecheck-core

# Local CI (lint + check-gen + test)
just ci
````

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide.

## Latest Changes

See [CHANGELOG.md](CHANGELOG.md) for the full release history. Recent highlights:

- **v0.9.6** -- `T` module for tool composition, `ToolRegistry` with BM25-indexed discovery
- **v0.9.5** -- Middleware v2 (`TraceContext`, per-agent scoping, topology hooks), `M` module, `P` module, `MiddlewareSchema`
- **v0.9.3** -- Error reference page, recipes-by-use-case index
- **v0.9.1** -- Copy-on-write frozen builders, `.explain()` rich output, CLI (`adk-fluent visualize`)

````

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: update Development section and add Latest Changes"
````

______________________________________________________________________

### Task 13: Update Features section

**Files:**

- Modify: `README.template.md:1035-1054` (Features section)

**Step 1: Add py.typed mention to Features**

Add to the features list after `**Full IDE autocomplete** via .pyi type stubs`:

```markdown
- **PEP 561 `py.typed`** marker included -- type checkers recognize the package natively
```

**Step 2: Commit**

```bash
git add README.template.md
git commit -m "docs: mention py.typed marker in Features section"
```

______________________________________________________________________

### Task 14: Regenerate README and verify

**Files:**

- Generate: `README.md` (from template)

**Step 1: Regenerate README**

Run: `cd /home/user/adk-fluent && just readme`
Expected: "README.md successfully generated with dynamic content."

**Step 2: Run preflight to fix formatting**

Run: `cd /home/user/adk-fluent && just preflight`
Expected: mdformat may reformat some markdown. If it modifies files, stage them.

**Step 3: If preflight modified files, re-run until idempotent**

Run: `cd /home/user/adk-fluent && just preflight`
Expected: All hooks pass with no modifications.

**Step 4: Verify key sections exist in generated README**

Run: `grep -n "## Quick Start\|## Zero to Running\|## Common Errors\|## When to Use\|## Performance\|## ADK Compatibility\|## Latest Changes\|### Start Here\|### Core Patterns" README.md`
Expected: All 9 section headers found.

**Step 5: Commit the regenerated README**

```bash
git add README.md README.template.md
git commit -m "docs: regenerate README with all DevEx gap improvements"
```

______________________________________________________________________

### Task 15: Move sync-adk.yml to .github/workflows/

**Files:**

- Move: `sync-adk.yml` -> `.github/workflows/sync-adk.yml`

The `sync-adk.yml` workflow exists in the repo root but is not in `.github/workflows/`, so GitHub Actions doesn't run it. It's a fully written workflow that scans ADK upstream weekly, regenerates code, runs tests, and auto-creates PRs.

**Step 1: Move the workflow file**

Run: `mv sync-adk.yml .github/workflows/sync-adk.yml`

**Step 2: Verify it's in the right place**

Run: `ls .github/workflows/sync-adk.yml`
Expected: File exists.

**Step 3: Commit**

```bash
git add sync-adk.yml .github/workflows/sync-adk.yml
git commit -m "ci: move sync-adk workflow to .github/workflows/ for activation"
```

______________________________________________________________________

### Task 16: Final verification

**Step 1: Run full test suite**

Run: `cd /home/user/adk-fluent && uv run pytest tests/ -x --tb=short -q`
Expected: All tests pass (no test changes were made, but verify nothing broke).

**Step 2: Run benchmark to confirm it works**

Run: `cd /home/user/adk-fluent && uv run python scripts/benchmark.py`
Expected: Output showing build times and overhead ratio.

**Step 3: Verify quickstart.py syntax**

Run: `cd /home/user/adk-fluent && python -c "import ast; ast.parse(open('quickstart.py').read()); print('OK')"`
Expected: `OK`
