# DevEx Gaps Design

## Problem

10 developer experience gaps identified that slow adoption and reduce trust:

1. No coverage/status badges
1. No zero-to-running quickstart (missing `.ask()` output, GCP-only auth path)
1. ADK version coupling invisible
1. No error gallery in README
1. No visual mental model for operator algebra
1. `.ask()` buried below pages of operator docs
1. "Zero-cost" claims without evidence
1. 66 cookbook entries with no tiering
1. No guidance on when NOT to use adk-fluent
1. Sparse changelog visibility from README

## Scope

All changes target `README.template.md` (the source for generated `README.md`), plus two new files: `quickstart.py` and `scripts/benchmark.py`. No docs site restructuring.

## Changes

### 1. Badges (line 5-13 of template)

Add two badges after existing ones:

- **Coverage**: `[![Coverage](https://codecov.io/gh/vamsiramakrishnan/adk-fluent/branch/master/graph/badge.svg)](https://codecov.io/gh/vamsiramakrishnan/adk-fluent)` -- CI already uploads to Codecov
- **Status**: `[![Status](https://img.shields.io/badge/status-beta-yellow)]` -- honest expectation-setting

### 2. Quick Start rewrite

Replace current Quick Start (lines 65-99) which ends at `.build()` with a version that leads with `.ask()` and shows output:

```python
from adk_fluent import Agent

# One line to create, one line to run
agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")
response = agent.ask("What is the capital of France?")
print(response)
# => The capital of France is Paris.
```

Then show `.build()` for ADK integration, pipelines, etc. as secondary examples.

### 3. Zero to Running section

New section after Quick Start with two auth paths:

**Fastest (AI Studio)**:

```bash
pip install adk-fluent
export GOOGLE_API_KEY="your-key-from-aistudio.google.com"
python quickstart.py
```

**Production (Vertex AI)**:

```bash
pip install adk-fluent
export GOOGLE_CLOUD_PROJECT="your-project"
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_GENAI_USE_VERTEXAI="TRUE"
python quickstart.py
```

### 4. quickstart.py

New file at repo root -- single-file runnable:

```python
"""adk-fluent quickstart -- copy, set one env var, run."""
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")
print(agent.ask("Summarize the benefits of Python in one sentence."))
```

### 5. ADK Compatibility section

New section before "How It Works":

| adk-fluent   | google-adk | Tested in CI | Notes            |
| ------------ | ---------- | ------------ | ---------------- |
| 0.11.x       | 1.25.0     | Yes          | Current          |
| 0.9.x-0.10.x | 1.25.0     | Yes          |                  |
| 0.1.x-0.8.x  | 1.20.0+    | Yes          | Initial releases |

Plus note: "CI pins `google-adk==1.25.0`. The `>=1.20.0` floor means newer ADK versions should work, but only the pinned version is tested."

### 6. Common Errors section

New section after Expression Language with 4 examples:

**Missing model**:

```python
Agent("x").instruct("Hi").build()
# => BuilderError: Agent 'x' is missing required field 'model'
```

**Typo in method**:

```python
Agent("x").modle("gemini-2.5-flash")
# => AttributeError: 'modle' is not a recognized field. Did you mean: 'model'?
```

**Missing template variable**:

```python
Agent("x", "gemini-2.5-flash").instruct("Summarize {data}").ask("hello")
# Template variable {data} resolves from session state at runtime.
# If missing, the literal "{data}" appears in the prompt.
```

**Invalid operator combination**:

```python
Agent("a") | "not an agent"
# => TypeError: unsupported operand type(s) for |: 'Agent' and 'str'
```

Link: "Full error reference: [Error Reference](https://vamsiramakrishnan.github.io/adk-fluent/user-guide/error-reference/)"

### 7. Operator algebra ASCII visualization

After the operator table, add:

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

And a second example:

```
Expression:   a >> fn >> Route("key").eq("x", b).eq("y", c).default(d)

Agent tree:
  SequentialAgent
  +-- a (LlmAgent)
  +-- fn (FunctionAgent)
  +-- RoutingAgent
      +-- "x" -> b (LlmAgent)
      +-- "y" -> c (LlmAgent)
      +-- default -> d (LlmAgent)
```

### 8. Cookbook tiering

Replace the flat 42-row table with three tiers:

**Start Here** (3 examples):

| #   | Example             | Feature              |
| --- | ------------------- | -------------------- |
| 01  | Simple Agent        | Basic agent creation |
| 08  | One-Shot Ask        | `.ask()` execution   |
| 04  | Sequential Pipeline | Pipeline builder     |

**Core Patterns** (10 examples):

| #   | Example              | Feature                        |
| --- | -------------------- | ------------------------------ |
| 02  | Agent with Tools     | Tool registration              |
| 03  | Callbacks            | Additive callback accumulation |
| 05  | Parallel FanOut      | FanOut builder                 |
| 16  | Operator Composition | `>>` \`                        |
| 17  | Route Branching      | Deterministic routing          |
| 33  | State Transforms     | S module                       |
| 07  | Team Coordinator     | Sub-agent delegation           |
| 37  | Mock Testing         | `.mock()` for tests            |
| 11  | Inline Testing       | `.test()` smoke tests          |
| 31  | Typed Output         | `@ Schema`                     |

**All Examples** (collapsed or linked):
Full list of 66 examples with link to `examples/cookbook/`.

### 9. When to Use / When Not to Use

New section:

**Use adk-fluent when:**

- You want concise agent definitions without boilerplate
- You need to compose agent topologies (pipelines, fan-out, routing, loops)
- You value IDE autocomplete and type checking during development
- You want to test agents with `.mock()` and `.test()` without API calls

**Use raw ADK when:**

- You need custom `BaseAgent` subclasses with non-standard `_run_async_impl`
- You're integrating with ADK internals that the builder doesn't expose
- You need granular control over the Runner/Session lifecycle beyond what `.session()` provides
- You're building framework-level tooling that wraps ADK itself

### 10. Performance section

New section:

**Build-time only.** adk-fluent is a build-time layer. Calling `.build()` produces a native ADK object -- the same `LlmAgent`, `SequentialAgent`, `ParallelAgent`, or `LoopAgent` you'd construct manually. After `.build()`, adk-fluent is not in the execution path. There is no runtime wrapper, proxy, or middleware injected by the builder itself.

**Overhead:** Builder construction (`Agent("x").model(...).instruct(...).build()`) adds microseconds of Python dict manipulation. For context, a single LLM API call takes 500ms-30s.

**Verify yourself:**

```bash
python scripts/benchmark.py
```

### 11. scripts/benchmark.py

New file:

```python
"""Measure adk-fluent build overhead vs native ADK construction."""
import timeit
from adk_fluent import Agent
from google.adk.agents import LlmAgent

def fluent_build():
    Agent("bench", "gemini-2.5-flash").instruct("You are helpful.").build()

def native_build():
    LlmAgent(name="bench", model="gemini-2.5-flash", instruction="You are helpful.")

N = 10_000
fluent_time = timeit.timeit(fluent_build, number=N)
native_time = timeit.timeit(native_build, number=N)

print(f"Native ADK:  {native_time:.4f}s for {N} builds ({native_time/N*1e6:.1f} us/build)")
print(f"adk-fluent:  {fluent_time:.4f}s for {N} builds ({fluent_time/N*1e6:.1f} us/build)")
print(f"Overhead:    {(fluent_time - native_time)/N*1e6:.1f} us/build")
print(f"Ratio:       {fluent_time/native_time:.2f}x")
```

### 12. Changelog visibility

Add "Latest Release" mini-section near the bottom linking to CHANGELOG.md with 3-4 bullet highlights from the most recent version.

### 13. Development section fixes

- Add: "**Requires:** Python 3.11+, [just](https://github.com/casey/just#installation), [uv](https://docs.astral.sh/uv/)"
- Add: "**Container:** Open in VS Code with the Dev Container for a pre-configured environment."

### 14. Table of Contents update

Update ToC to include new sections:

- Zero to Running
- Common Errors
- When to Use
- ADK Compatibility
- Performance

## Files Changed

| File                          | Action                                                      |
| ----------------------------- | ----------------------------------------------------------- |
| `README.template.md`          | Edit: badges, quickstart rewrite, new sections              |
| `quickstart.py`               | Create: standalone runnable example                         |
| `scripts/benchmark.py`        | Create: build overhead benchmark                            |
| `scripts/readme_generator.py` | No change needed (template still uses same injection point) |

## Out of Scope

- Docs site restructuring (existing pages are good, just need README links)
- GitHub Discussions / Discord setup (community infrastructure decision)
- Docker instructions (devcontainer is sufficient)
- `seeds/` directory documentation (contributor-facing, covered in CONTRIBUTING.md)
