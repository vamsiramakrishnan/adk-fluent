#!/usr/bin/env python3
"""
LLMs context generator for adk-fluent.

Reads manifest.json + seed.toml and produces:
  1. docs/llms.txt              — canonical LLM context file (served on GitHub Pages)
  2. CLAUDE.md                  — Claude Code project rules
  3. .cursor/rules/adk-fluent.mdc — Cursor project rules
  4. .github/instructions/adk-fluent.instructions.md — VS Code Copilot instructions
  5. .windsurfrules             — Windsurf project rules
  6. .clinerules/adk-fluent.md  — Cline project rules
  7. .zed/settings.json         — Zed context (prompt-instructions only)

All files are generated from the same canonical content so they never go stale.

Usage:
    python scripts/llms_generator.py manifest.json seeds/seed.toml
    python scripts/llms_generator.py manifest.json seeds/seed.toml --output-dir .
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Import BuilderSpec resolution from generator (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from generator import BuilderSpec, parse_manifest, parse_seed, resolve_builder_specs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _group_builders_by_module(specs: list[BuilderSpec]) -> dict[str, list[BuilderSpec]]:
    """Group builder specs by their output_module."""
    groups: dict[str, list[BuilderSpec]] = defaultdict(list)
    for spec in specs:
        groups[spec.output_module].append(spec)
    return dict(sorted(groups.items()))


def _count_fields(spec: BuilderSpec) -> int:
    """Count configurable fields for a builder."""
    return len([f for f in spec.fields if f["name"] not in spec.skip_fields])


def _format_builder_table(groups: dict[str, list[BuilderSpec]]) -> str:
    """Format a summary table of all builders by module."""
    lines = []
    total = 0
    for module, specs in groups.items():
        names = ", ".join(s.name for s in specs)
        lines.append(f"  {module:12s} ({len(specs):2d}): {names}")
        total += len(specs)
    lines.append(f"\n  Total: {total} builders")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Canonical content
# ---------------------------------------------------------------------------

_HEADER = """\
# adk-fluent — LLM Context

> Auto-generated from manifest.json. Do not edit manually.
> Docs: https://vamsiramakrishnan.github.io/adk-fluent/
> PyPI: https://pypi.org/project/adk-fluent/
> Repo: https://github.com/vamsiramakrishnan/adk-fluent

adk-fluent is a fluent builder API for Google's Agent Development Kit (ADK).
It reduces agent creation from 22+ lines to 1-3 lines while producing
identical native ADK objects. Every `.build()` returns a real ADK object —
fully compatible with `adk web`, `adk run`, and `adk deploy`.
"""

_INSTALL = """
## Install

    pip install adk-fluent
"""

_IMPORTS = """
## Imports

Always import from the top-level package:

    from adk_fluent import Agent, Pipeline, FanOut, Loop
    from adk_fluent import S, C, P, A, M, T

Never import from internal modules like `adk_fluent._base` or `adk_fluent.agent`.
"""

_CORE_PATTERNS = """
## Core API patterns

### Fluent builder pattern

Every builder takes a required `name` as the first positional argument.
Agent accepts an optional `model` as the second positional argument.
Methods are chainable and can be called in any order.
Call `.build()` to resolve into a native ADK object.

    agent = (
        Agent("helper", "gemini-2.5-flash")
        .instruct("You are a helpful assistant.")
        .tool(search_fn)
        .build()
    )

Sub-builders passed to workflow builders are auto-built — do not call
`.build()` on individual steps.

### Workflow builders

Pipeline (sequential):

    pipeline = (
        Pipeline("flow")
        .step(Agent("a", "gemini-2.5-flash").instruct("Step 1.").writes("result"))
        .step(Agent("b", "gemini-2.5-flash").instruct("Step 2 using {result}."))
        .build()
    )

FanOut (parallel):

    fanout = (
        FanOut("parallel")
        .branch(Agent("web", "gemini-2.5-flash").instruct("Search web."))
        .branch(Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
        .build()
    )

Loop:

    loop = (
        Loop("refine")
        .step(Agent("writer", "gemini-2.5-flash").instruct("Write."))
        .step(Agent("critic", "gemini-2.5-flash").instruct("Critique."))
        .max_iterations(3)
        .build()
    )

### Expression operators (alternative syntax)

All operators are immutable (copy-on-write). Sub-expressions can be reused.

    pipeline = Agent("a") >> Agent("b")          # Sequential (>>)
    fanout   = Agent("a") | Agent("b")           # Parallel (|)
    loop     = (Agent("a") >> Agent("b")) * 3    # Loop (*)

    # Conditional loop
    loop = (Agent("a") >> Agent("b")) * until(lambda s: s.get("done"), max=5)

    # Fallback chain
    result = Agent("fast", "gemini-2.5-flash") // Agent("strong", "gemini-2.5-pro")

    # Structured output
    agent = Agent("parser") @ MyPydanticSchema

    # Function steps (zero-cost, no LLM)
    pipeline = Agent("a") >> some_function >> Agent("b")

    # Deterministic routing
    router = Route("tier").eq("VIP", vip_agent).otherwise(standard_agent)
"""

_AGENT_METHODS = """
## Agent builder methods

Core configuration:
  .model(str)                  — set LLM model
  .instruct(str | PTransform)  — set instruction/system prompt
  .describe(str)               — set agent description
  .static(str)                 — set static instruction
  .global_instruct()           — set global instruction
  .generate_content_config()   — model-level config

Data flow:
  .writes(key)                 — store response in state[key]
  .reads(*keys)                — inject state keys into context
  .returns(Schema)             — constrain output to Pydantic model
  .accepts(Schema)             — define input schema for AgentTool usage
  .context(C.xxx())            — set context engineering spec
  .produces(Schema)            — contract annotation (no runtime effect)
  .consumes(Schema)            — contract annotation (no runtime effect)

Tools:
  .tool(fn)                    — add a single tool function
  .tools(list | TComposite)    — set multiple tools
  .agent_tool(agent)           — wrap another agent as a callable tool

Callbacks:
  .before_agent(fn)            — run before agent executes
  .after_agent(fn)             — run after agent executes
  .before_model(fn)            — run before LLM call
  .after_model(fn)             — run after LLM call
  .before_tool(fn)             — run before tool call
  .after_tool(fn)              — run after tool call
  .guard(fn)                   — attach as both before_model and after_model
  .on_model_error(fn)          — error callback for LLM failures
  .on_tool_error(fn)           — error callback for tool failures

Flow control:
  .loop_until(pred, max=10)    — loop while predicate is false
  .loop_while(pred, max=3)     — loop while predicate is true
  .until(pred)                 — alias for loop_until
  .proceed_if(pred)            — conditional execution
  .timeout(seconds)            — wrap with time limit (returns TimedAgent)
  .dispatch(name=, on_complete=) — background task (returns BackgroundTask)

Transfer control:
  .isolate()                   — prevent all transfers
  .stay()                      — prevent parent transfer
  .no_peers()                  — prevent sibling transfer

Memory:
  .memory(mode="preload")      — attach memory tools
  .memory_auto_save()          — auto-save to memory after execution

Visibility:
  .show()                      — include in topology
  .hide()                      — exclude from topology
  .transparent()               — transparent visibility mode
  .filtered()                  — filtered visibility mode
  .annotated()                 — annotated visibility mode

Configuration:
  .middleware(mw)              — attach middleware
  .inject(**resources)         — inject dependencies
  .use(preset)                 — apply preset configuration
  .native(fn)                  — apply native hook
  .debug(enabled=True)         — debug tracing to stderr
  .strict()                    — enable strict contract checking
  .unchecked()                 — bypass contract checking
  .prepend(fn)                 — prepend dynamic text to LLM

Schemas:
  .tool_schema(schema)         — attach tool schema
  .callback_schema(schema)     — attach callback schema
  .prompt_schema(schema)       — attach prompt schema
  .artifact_schema(schema)     — attach artifact schema
  .artifacts(*transforms)      — artifact operations

Execution:
  .build()                     — produce native ADK LlmAgent
  .ask(prompt)                 — one-shot sync execution
  .ask_async(prompt)           — async one-shot execution
  .stream(prompt)              — async streaming iterator
  .events(prompt)              — raw ADK Event streaming
  .session()                   — create interactive ChatSession
  .map(prompts, concurrency=5) — batch execution over multiple prompts
  .map_async(prompts)          — async batch execution
  .test(prompt, contains=)     — inline smoke test
  .mock(responses)             — replace LLM with canned responses
  .eval(prompt, expect=)       — inline evaluation
  .eval_suite()                — evaluation suite builder

Introspection:
  .explain()                   — print builder state
  .validate()                  — early error detection
  .clone(name)                 — deep copy with new name
  .with_(**overrides)          — immutable variant
  .to_ir()                     — convert to IR tree
  .to_mermaid()                — generate Mermaid diagram
  .diagnose()                  — structured IR diagnosis
  .doctor()                    — formatted diagnostic report
  .data_flow()                 — unified five-concern view
  .llm_anatomy()               — what the LLM sees
  .inspect()                   — plain-text state
  .to_dict() / .to_yaml()     — serialization
"""

_NAMESPACE_MODULES = """
## Namespace modules (S, C, P, A, M, T, E, G)

### S — State transforms

Used with `>>` operator. Compose with `>>` (chain) or `+` (combine).

  S.pick(*keys)                — keep only named keys
  S.drop(*keys)                — remove named keys
  S.rename(**mapping)          — rename keys
  S.merge(*keys, into=)        — combine keys
  S.transform(key, fn)         — apply function to value
  S.compute(**factories)       — derive new keys from state
  S.set(**kv)                  — set explicit key-value pairs
  S.default(**kv)              — fill missing keys with defaults
  S.guard(pred, msg=)          — assert state invariant
  S.when(pred, transform)      — conditional transform
  S.branch(key, **transforms)  — route to different transforms
  S.capture(*keys)             — capture function args into state
  S.identity()                 — pass-through (no-op)
  S.accumulate(key)            — append to list in state
  S.counter(key)               — increment counter in state
  S.history(key)               — maintain history list
  S.validate(**schemas)        — validate state keys against schemas
  S.require(*keys)             — assert keys exist
  S.flatten(key)               — flatten nested dict
  S.unflatten(key, sep=".")    — unflatten dotted keys
  S.zip(*keys, into=)          — zip parallel lists
  S.group_by(key, by=)         — group items by field
  S.log(*keys)                 — log state keys to stderr

### C — Context engineering

Used with `.context()`. Compose with `+` (union) or `|` (pipe).

  C.none()                     — suppress all history
  C.default()                  — default ADK behavior
  C.user_only()                — only user messages
  C.window(n=5)                — last N turn-pairs
  C.from_state(*keys)          — inject state keys as context
  C.from_agents(*names)        — user + named agent outputs
  C.from_agents_windowed(n=)   — windowed agent output filtering
  C.exclude_agents(*names)     — exclude named agents
  C.template(text)             — template with {key} placeholders
  C.select(*agent_names)       — select specific agents
  C.recent(n=)                 — recent messages only
  C.compact()                  — remove redundant messages
  C.dedup()                    — remove duplicate messages
  C.truncate(max_turns=)       — hard limit
  C.project(*fields)           — project specific fields
  C.budget(max_tokens=)        — token budget constraint
  C.priority(*keys)            — prioritize certain context
  C.fit(max_tokens=)           — fit within token limit
  C.fresh(max_age=)            — filter by recency
  C.redact(*patterns)          — redact sensitive content
  C.summarize(scope=)          — LLM-powered summarization
  C.relevant(query_key=)       — semantic relevance filtering
  C.extract(key=)              — extract structured data
  C.distill()                  — distill to key points
  C.validate()                 — validate context integrity
  C.notes()                    — attach notes
  C.write_notes()              — persist notes to state
  C.rolling(n=)                — rolling window with compaction
  C.user()                     — user messages only (alias)
  C.manus_cascade()            — Manus-style cascading context
  C.when(pred, transform)      — conditional context transform

### P — Prompt composition

Used with `.instruct()`. Compose with `+` (union) or `|` (pipe).
Section order: role → context → task → constraint → format → example.

  P.role(text)                 — agent persona
  P.context(text)              — background context
  P.task(text)                 — primary objective
  P.constraint(*rules)         — constraints/rules
  P.format(text)               — output format spec
  P.example(input=, output=)   — few-shot examples
  P.section(name, text)        — custom named section
  P.when(pred, block)          — conditional inclusion
  P.from_state(*keys)          — dynamic state injection
  P.template(text)             — {key}, {key?}, {ns:key} placeholders
  P.reorder(*sections)         — reorder sections
  P.only(*sections)            — include only named sections
  P.without(*sections)         — exclude named sections
  P.compress()                 — compress verbose prompts
  P.adapt(fn)                  — transform prompt dynamically
  P.scaffolded(structure)      — structured prompt scaffold
  P.versioned(v, text)         — versioned prompt variants

### A — Artifacts

Used with `.artifacts()` or `>>`. Compose with `>>` (chain).

  A.publish(filename, from_key=) — state → artifact
  A.snapshot(filename, into_key=) — artifact → state
  A.save(filename, content=)    — content → artifact
  A.load(filename)              — artifact → pipeline
  A.list()                      — list available artifacts
  A.version(filename)           — get artifact version
  A.delete(filename)            — delete artifact
  A.publish_many(**mapping)     — batch publish multiple artifacts
  A.snapshot_many(**mapping)    — batch snapshot multiple artifacts
  A.for_llm()                  — context transform for LLM-aware loading
  A.when(pred, transform)      — conditional artifact operation
  A.from_json() / A.from_csv() / A.from_markdown() — content transforms (pre-publish)
  A.as_json() / A.as_csv() / A.as_text() — content transforms (post-snapshot)

### M — Middleware

Used with `.middleware()`. Compose with `|` (chain).

  M.retry(max_attempts=)       — retry with exponential backoff
  M.log()                      — structured event logging
  M.cost()                     — token usage tracking
  M.latency()                  — per-agent latency tracking
  M.scope(agents, mw)          — restrict middleware to agents
  M.when(condition, mw)        — conditional middleware
  M.circuit_breaker(max_fails=) — circuit breaker pattern
  M.timeout(seconds)           — per-agent timeout
  M.cache(ttl=)                — response caching
  M.fallback_model(model)      — fallback to different model
  M.dedup()                    — deduplicate requests
  M.sample(rate=)              — probabilistic sampling
  M.trace()                    — distributed tracing
  M.metrics()                  — metrics collection
  M.before_agent(fn)           — pre-agent hook
  M.after_agent(fn)            — post-agent hook
  M.before_model(fn)           — pre-model hook
  M.after_model(fn)            — post-model hook
  M.on_loop(fn)                — loop iteration hook
  M.on_timeout(fn)             — timeout event hook
  M.on_route(fn)               — routing event hook
  M.on_fallback(fn)            — fallback event hook

### T — Tool composition

Used with `.tools()`. Compose with `|` (chain).

  T.fn(callable)               — wrap callable as FunctionTool
  T.agent(agent)               — wrap agent as AgentTool
  T.google_search()            — built-in Google Search
  T.search(registry)           — BM25-indexed dynamic loading
  T.toolset(toolset)           — wrap MCPToolset or similar
  T.schema(schema)             — attach ToolSchema
  T.mock(responses)            — mock tool for testing
  T.confirm(prompt=)           — human confirmation wrapper
  T.timeout(seconds)           — tool timeout wrapper
  T.cache(ttl=)                — tool response caching
  T.mcp(server)                — MCP server tool
  T.openapi(spec)              — OpenAPI spec tool
  T.transform(fn)              — transform tool output

### E — Evaluation

Used with `.eval()` and `.eval_suite()`. Build evaluation criteria and test suites.

  E.case(prompt, expect=)      — single evaluation case
  E.criterion(name, fn)        — custom evaluation criterion
  E.persona(name, style=)      — persona for evaluation
  EvalSuite                    — collection of eval cases
  EvalReport                   — evaluation results
  ComparisonReport             — compare multiple agents/models

### G — Guards

Used with `.guard()`. Build input/output validation guards.

  G.guard(fn)                  — custom guard function
  G.pii(detector=)             — PII detection guard
  G.toxicity(threshold=)       — toxicity detection guard
  G.length(max=)               — response length guard
  G.schema(model)              — schema validation guard
  GuardViolation               — raised when guard fails
  PIIDetector                  — PII detection provider
  ContentJudge                 — content judgment provider
"""

_EXPRESSION_PRIMITIVES = """
## Expression primitives

Function-level primitives for use with expression operators:

  until(pred, max=10)          — loop condition for * operator
  tap(fn)                      — inline transform (no LLM, zero cost)
  expect(fn)                   — alias for tap
  map_over(key)                — map agent over list items in state[key]
  gate(predicate)              — conditional execution (skip if false)
  race(*agents)                — first-to-complete wins
  dispatch(name=, on_complete=) — launch background task
  join()                       — wait for all background tasks

Routing:
  Route(key)                   — deterministic state-based routing
    .eq(value, agent)          — exact match
    .contains(sub, agent)      — substring match
    .gt(n, agent)              — greater than
    .lt(n, agent)              — less than
    .gte(n, agent) / .lte(n, agent) / .ne(value, agent)
    .when(pred, agent)         — custom predicate
    .otherwise(agent)          — default fallback

  Fallback(name)               — explicit fallback chain
    .attempt(agent)            — add fallback alternative
"""

_COMPOSITION_PATTERNS = """
## Composition patterns

Higher-order constructors that accept builders and return builders:

  review_loop(worker, reviewer, quality_key=, target=, max_rounds=)
  map_reduce(mapper, reducer, items_key=, result_key=)
  cascade(agent1, agent2, ...)    — fallback chain of models
  fan_out_merge(*agents, merge_key=) — parallel + merge
  chain(*agents)                  — sequential pipeline
  conditional(pred, then_agent, else_agent=)
  supervised(worker, supervisor)
"""

_BEST_PRACTICES = """
## Best practices

1. Use deterministic routing (Route) over LLM routing when the decision is rule-based
2. Use `.inject()` for infrastructure deps — never expose DB clients in tool schemas
3. Use S.transform() or plain functions for data transforms, not custom BaseAgent
4. Use C.none() to hide conversation history from background/utility agents
5. Use M.retry() middleware instead of retry logic inside tool functions
6. Use `.writes()` not deprecated `.output_key()` / `.outputs()`
7. Use `.returns()` not deprecated `.output_schema()`
8. Use `.context()` not deprecated `.history()` / `.include_history()`
9. Use `.agent_tool()` not deprecated `.delegate()`
10. Use `.guard()` not deprecated `.guardrail()`
11. Use `.loop_while()` not deprecated `.retry_if()`
12. Use `.prepend()` not deprecated `.inject_context()`
13. All operators are immutable — sub-expressions can be safely reused
14. Every `.build()` returns a real ADK object compatible with adk web/run/deploy
"""

_COMMANDS = """
## Development commands

    pip install adk-fluent                  # install
    uv run pytest tests/ -v --tb=short      # run tests
    uv run ruff check .                     # lint
    uv run ruff format .                    # format
    uv run sphinx-build -b html docs/ docs/_build/html  # build docs
"""


# ---------------------------------------------------------------------------
# Builder list (dynamic)
# ---------------------------------------------------------------------------


def _format_builder_section(groups: dict[str, list[BuilderSpec]]) -> str:
    """Generate the dynamic builder inventory section."""
    lines = ["\n## Builder inventory\n"]
    total = 0
    for module, specs in groups.items():
        total += len(specs)
        names = ", ".join(s.name for s in specs)
        lines.append(f"### {module} module ({len(specs)} builders)\n")
        lines.append(f"{names}\n")
    lines.insert(1, f"{total} builders across {len(groups)} modules.\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Assemble canonical content
# ---------------------------------------------------------------------------


def generate_llms_txt(specs: list[BuilderSpec]) -> str:
    """Generate the canonical llms.txt content."""
    groups = _group_builders_by_module(specs)

    sections = [
        _HEADER,
        _INSTALL,
        _IMPORTS,
        _CORE_PATTERNS,
        _AGENT_METHODS,
        _NAMESPACE_MODULES,
        _EXPRESSION_PRIMITIVES,
        _COMPOSITION_PATTERNS,
        _format_builder_section(groups),
        _BEST_PRACTICES,
        _COMMANDS,
    ]

    return "\n".join(s.strip() for s in sections) + "\n"


# ---------------------------------------------------------------------------
# Editor-specific wrappers
# ---------------------------------------------------------------------------

_CLAUDE_MD_HEADER = """\
# CLAUDE.md — adk-fluent project rules

> Auto-generated by `scripts/llms_generator.py`. Do not edit manually.
> Regenerate with: `just llms` or `python scripts/llms_generator.py manifest.json seeds/seed.toml`

"""

_CURSOR_HEADER = """\
---
description: adk-fluent project rules for AI code generation
globs: "**/*.py"
---

"""

_COPILOT_HEADER = """\
---
applyTo: "**/*.py"
---

"""


def _wrap_for_claude_md(content: str) -> str:
    """Wrap canonical content for CLAUDE.md."""
    return _CLAUDE_MD_HEADER + content


def _wrap_for_cursor(content: str) -> str:
    """Wrap canonical content for .cursor/rules/adk-fluent.mdc."""
    return _CURSOR_HEADER + content


def _wrap_for_copilot(content: str) -> str:
    """Wrap canonical content for .github/instructions/."""
    return _COPILOT_HEADER + content


def _wrap_for_zed(content: str) -> str:
    """Generate .zed/settings.json with prompt instructions."""
    # Zed uses a JSON settings file with context_servers
    escaped = content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return (
        json.dumps(
            {
                "context_servers": {
                    "adk-fluent": {
                        "settings": {
                            "prompt_instructions": escaped[:8000],  # Zed has limits
                        }
                    }
                }
            },
            indent=2,
        )
        + "\n"
    )


# ---------------------------------------------------------------------------
# Output targets
# ---------------------------------------------------------------------------

TARGETS: list[tuple[str, callable]] = [
    ("docs/llms.txt", lambda c: c),
    ("CLAUDE.md", _wrap_for_claude_md),
    (".cursor/rules/adk-fluent.mdc", _wrap_for_cursor),
    (".github/instructions/adk-fluent.instructions.md", _wrap_for_copilot),
    (".windsurfrules", lambda c: c),
    (".clinerules/adk-fluent.md", lambda c: c),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Generate llms.txt and editor rules files")
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("seed", help="Path to seed.toml")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Root directory for output (default: project root)",
    )
    parser.add_argument(
        "--llms-only",
        action="store_true",
        help="Only generate docs/llms.txt",
    )
    args = parser.parse_args()

    manifest = parse_manifest(args.manifest)
    seed = parse_seed(args.seed)
    specs = resolve_builder_specs(seed, manifest)

    content = generate_llms_txt(specs)
    root = Path(args.output_dir)

    targets = TARGETS[:1] if args.llms_only else TARGETS

    for relpath, wrapper in targets:
        outpath = root / relpath
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(wrapper(content))
        print(f"  Generated {relpath}")

    print(f"\nGenerated {len(targets)} file(s) from {len(specs)} builder specs.")


if __name__ == "__main__":
    main()
