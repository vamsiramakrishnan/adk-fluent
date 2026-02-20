# Design: Ergonomic Depth Features + Auto-Generated Documentation

**Date**: 2026-02-17
**Status**: Approved
**Scope**: Phase 1 of the "Both Layers" approach

## Context

adk-fluent wraps 130+ ADK classes into fluent builders via a three-layer code-generation pipeline (scanner → seed → generator). The core machinery is solid. This design adds two capabilities:

1. **Ergonomic depth features** — runtime shortcuts that go beyond wrapping, making adk-fluent a superset of ADK's developer experience
1. **Auto-generated documentation** — API reference + cookbook examples + migration guide, produced by the same pipeline that generates code

**Audience**: Experienced ADK developers who want less boilerplate.
**Distribution**: PyPI package (`pip install adk-fluent`).

## Phase Strategy

- **Phase 1** (this design): Ergonomic depth + auto-docs
- **Phase 2** (future): Pattern library — presets (`RAGAgent`, `RouterAgent`), middleware chains (`.use()`)
- **Phase 3** (future): Declarative definitions — YAML agents, operator overloading

______________________________________________________________________

## Part 1: Ergonomic Depth Features

### 1.1 `.ask()` — One-Shot Agent Execution

Runs an agent with a single prompt and returns the text response. No Runner, no Session, no async ceremony.

```python
# Native ADK (15+ lines: imports, Runner, SessionService, Session, async run, event iteration)

# adk-fluent
result = Agent("q", "gemini-2.5-flash").instruct("Answer concisely.").ask("What is 2+2?")
```

**Implementation**: Terminal method that internally creates InMemoryRunner + session, sends the message, collects the final response, returns text. Handles async via `asyncio.run()` for sync contexts. Also provides `.ask_async()` for async contexts.

### 1.2 `.stream()` — Streaming Shorthand

```python
async for chunk in Agent("s", "gemini-2.5-flash").instruct("Tell stories.").stream("Once upon a time"):
    print(chunk, end="")
```

**Implementation**: Async generator terminal that yields text chunks from the runner's event stream.

### 1.3 `.clone()` / `.extend()` — Agent Inheritance

```python
base = Agent("base", "gemini-2.5-flash").instruct("You are helpful.").before_model(log_request)
math_agent = base.clone("math").instruct("You solve math problems.").tool(calculator)
code_agent = base.clone("code").instruct("You write Python code.").tool(code_executor)
```

**Implementation**: `.clone(new_name)` deep-copies `_config`, `_callbacks`, `_lists` dicts, sets new name, returns fresh builder. `.extend()` is an alias.

### 1.4 `.test()` — Inline Agent Testing

```python
Agent("qa", "gemini-2.5-flash") \
    .instruct("Answer math questions.") \
    .test("What is 2+2?", contains="4") \
    .test("What is 10*10?", contains="100") \
    .build()
```

**Implementation**: Calls `.ask()` internally, asserts output matches condition (`contains=`, `matches=` for regex, `equals=` for exact), returns `self` for chaining. No runtime overhead when not called.

### 1.5 Callback Combinators

```python
# Variadic: multiple callbacks in one call
agent = Agent("a").before_model(fn1, fn2, fn3)

# Conditional: only attach if condition is true
agent = Agent("a").before_model_if(is_production, audit_logger)

# Guardrail shorthand: registers as both before and after model callback
agent = Agent("a").guardrail(pii_filter)
```

**Implementation**:

- Variadic: callback alias methods accept `*fns` instead of single `fn`
- `_if` variants: generated for each callback, wraps in condition check
- `.guardrail()`: registers function as both `before_model_callback` and `after_model_callback`

### 1.6 `.session()` — Context Manager for Interactive Sessions

```python
async with Agent("chat", "gemini-2.5-flash").instruct("You are a tutor.").session() as chat:
    response1 = await chat.send("What is calculus?")
    response2 = await chat.send("Give me an example.")
    # Session automatically cleaned up on exit
```

**Implementation**: Returns async context manager that creates Runner + Session on enter, provides `.send()` method, cleans up on exit.

______________________________________________________________________

## Part 2: Auto-Generated Documentation System

### 2.1 Architecture

```
manifest.json + seed.toml + examples/cookbook/
        ↓
   generator.py (extended with --docs flags)
   doc_generator.py (cookbook processor)
        ↓
   docs/generated/
   ├── api/           (one .md per module — API reference)
   ├── cookbook/       (before/after examples — from annotated .py files)
   └── migration/     (native ADK → fluent mapping tables)
```

### 2.2 API Reference — Auto-Generated Per Builder

For each builder in seed.toml, the generator produces a Markdown file containing:

- Constructor signature with types and defaults (from manifest)
- All alias methods with types (from seed + manifest)
- All callback methods with additive semantics noted
- All extra methods (`.tool()`, `.step()`, `.branch()`, etc.)
- Terminal methods (`.build()`, `.ask()`, `.stream()`)
- Forwarded fields table (from manifest, minus aliased/skipped)

### 2.3 Cookbook — Before/After Examples

Annotated Python files in `examples/cookbook/` with markers:

```python
# examples/cookbook/01_simple_agent.py
"""Simple Agent Creation"""

# --- NATIVE ---
from google.adk.agents import LlmAgent
agent_native = LlmAgent(name="helper", model="gemini-2.5-flash", instruction="You are helpful.")

# --- FLUENT ---
from adk_fluent import Agent
agent_fluent = Agent("helper", "gemini-2.5-flash").instruct("You are helpful.").build()

# --- ASSERT ---
assert type(agent_native) == type(agent_fluent)
```

The doc generator splits on markers, produces Markdown with both versions side-by-side plus a "What changed" summary. The same files are collected by pytest as equivalence tests.

### 2.4 Cookbook Example List

| #   | Pattern             | Demonstrates                                          |
| --- | ------------------- | ----------------------------------------------------- |
| 01  | Simple agent        | Constructor → `.instruct().build()`                   |
| 02  | Agent with tools    | `tools=[]` → `.tool()` chaining                       |
| 03  | Callbacks           | `before_model_callback=` → `.before_model()` additive |
| 04  | Sequential pipeline | SequentialAgent → `Pipeline().step()`                 |
| 05  | Parallel fanout     | ParallelAgent → `FanOut().branch()`                   |
| 06  | Loop agent          | LoopAgent → `Loop().max_iterations()`                 |
| 07  | Team/coordinator    | LlmAgent + sub_agents → `Agent().member()`            |
| 08  | One-shot execution  | Runner ceremony → `.ask()`                            |
| 09  | Streaming           | Event iteration → `.stream()`                         |
| 10  | Agent cloning       | Copy boilerplate → `.clone()`                         |
| 11  | Inline testing      | Separate test file → `.test()`                        |
| 12  | Guardrails          | before+after callback → `.guardrail()`                |
| 13  | Interactive session | Runner lifecycle → `.session()`                       |
| 14  | MCP tools           | McpToolset → fluent equivalent                        |
| 15  | Production runtime  | Runner+services+plugins → `Runtime()`                 |

### 2.5 Migration Guide — Auto-Generated

Generated by walking every builder in seed.toml:

- Class mapping table (native → fluent)
- Field mapping table per builder (native field → fluent method + notes)

### 2.6 Justfile Updates

```just
docs:             just all docs regeneration
docs-api:         API reference only
docs-cookbook:     Cookbook from examples/cookbook/
docs-migration:   Migration guide

# Updated pipeline
all: scan generate docs test typecheck
```

______________________________________________________________________

## Part 3: Implementation Details

### 3.1 New/Modified Files

```
scripts/generator.py          # Extended: --docs flags, gen_doc_module()
scripts/doc_generator.py       # New: cookbook processor, migration generator
seeds/seed.toml                # Extended: new terminals + extras for Phase 1
src/adk_fluent/_helpers.py     # New: runtime implementations (ask, stream, clone, test, session)
src/adk_fluent/agent.py        # Regenerated with new terminals/extras
src/adk_fluent/agent.pyi       # Regenerated with new type signatures
examples/cookbook/              # New: 15 annotated before/after examples
docs/generated/                # New: auto-generated documentation output
justfile                       # Extended: docs targets
tests/manual/test_ask.py       # New: integration tests
tests/manual/test_stream.py    # New: integration tests
tests/manual/test_clone.py     # New: unit tests
tests/manual/test_session.py   # New: integration tests
```

### 3.2 Seed Extensions

New terminals on Agent builder:

- `ask` (returns `str`)
- `ask_async` (returns `str`)
- `stream` (returns `AsyncIterator[str]`)

New extras on Agent builder:

- `clone` — deep_copy behavior
- `test` — inline_test behavior
- `guardrail` — dual_callback behavior
- `session` — context_manager behavior

### 3.3 Runtime Helpers (`_helpers.py`)

Not generated — hand-written module containing:

- `run_one_shot(agent, prompt) -> str` — sync wrapper
- `run_one_shot_async(agent, prompt) -> str` — async implementation
- `run_stream(agent, prompt) -> AsyncIterator[str]` — streaming
- `deep_clone_builder(builder, new_name) -> Builder` — deep copy
- `run_inline_test(agent, prompt, **assertions) -> None` — test runner
- `ChatSession` class — context manager for interactive sessions

Generated builders import and delegate to these helpers.

### 3.4 What This Enables

The value proposition for experienced ADK developers:

> adk-fluent gives you the same ADK objects in fewer lines,
> plus `.ask()`, `.stream()`, `.clone()`, `.test()`, and `.session()`
> that ADK doesn't have at all.

This is no longer just a wrapper — it's a **superset** of ADK's developer experience.

______________________________________________________________________

## Future Work (Not In Scope)

- **Phase 2**: Pattern library — `RAGAgent`, `RouterAgent`, middleware chains (`.use()`)
- **Phase 3**: Declarative definitions — YAML agents, operator overloading (`>>`, `|`)
- Docs site hosting (ReadTheDocs/GitHub Pages)
- Interactive examples (Jupyter notebooks)
