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

### Optional extras

    pip install adk-fluent[a2a]            # A2A remote agent-to-agent communication
    pip install adk-fluent[yaml]           # .to_yaml() / .from_yaml() serialization
    pip install adk-fluent[rich]           # Rich terminal output for .explain()
    pip install adk-fluent[search]         # BM25-indexed tool discovery (T.search)
    pip install adk-fluent[pii]            # PII detection guard (G.pii with Cloud DLP)
    pip install adk-fluent[observability]  # OpenTelemetry tracing and metrics

Combine extras: ``pip install adk-fluent[a2a,yaml,rich]``

A2UI (Agent-to-UI): The UI namespace ships with the core package.
The full A2UI toolset will be available via ``pip install adk-fluent[a2ui]``
when the ``a2ui-agent`` package is published.
"""

_IMPORTS = """
## Imports

Always import from the top-level package:

    from adk_fluent import Agent, Pipeline, FanOut, Loop
    from adk_fluent import S, C, P, A, M, T, E, G, UI
    from adk_fluent import H  # harness namespace (hooks, permissions, plan mode, …)

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

### Core configuration

  .model(str)                  — set LLM model
  .instruct(str | PTransform)  — set the main instruction / system prompt. This is what
                                 the LLM is told to do. Accepts plain text, a callable,
                                 or a P module composition (P.role() + P.task() + ...).
  .describe(str)               — set agent description (metadata for transfer routing
                                 and topology — NOT sent to the LLM as instruction)
  .static(str)                 — set cached instruction. When set, .instruct() text moves
                                 from system to user content, enabling context caching.
                                 Use for large, stable prompt sections.
  .global_instruct(str)        — set instruction shared by ALL agents in a workflow.
                                 Only meaningful on the root agent. Prepended to every
                                 agent's system prompt.
  .generate_content_config()   — model-level config (temperature, top_p, etc.)

### Data flow (five orthogonal concerns)

Each method controls exactly one concern. See `data_flow()` for a snapshot.

  .reads(*keys)                — CONTEXT: inject state[key] values into agent's prompt.
                                 Side-effect: sets include_contents="none" (suppresses
                                 full conversation history; current turn is still visible).
  .context(C.xxx())            — CONTEXT: fine-grained control over what the agent sees.
                                 Pass a C transform (C.window(5), C.user_only(), etc.).
  .accepts(Schema)             — INPUT: validate input when this agent is invoked as a
                                 tool via .agent_tool(). No effect for top-level agents.
  .returns(Schema)             — OUTPUT: constrain LLM response to structured JSON
                                 matching a Pydantic model. HAS runtime effect.
  .writes(key)                 — STORAGE: store the agent's text response in state[key]
                                 after execution.
  .produces(Schema)            — CONTRACT: static annotation only — documents what state
                                 keys this agent writes. NO runtime effect.
  .consumes(Schema)            — CONTRACT: static annotation only — documents what state
                                 keys this agent needs. NO runtime effect.

### Tools

  .tool(fn)                    — add a single tool (appends to existing tools)
  .tools(list | TComposite)    — set / replace all tools at once
  .agent_tool(agent)           — wrap another agent as a callable AgentTool. The parent
                                 LLM invokes the child like any other tool and stays in
                                 control. Compare with .sub_agent() which fully transfers
                                 control to the child.

### Callbacks

  .before_agent(fn)            — run before agent executes
  .after_agent(fn)             — run after agent executes
  .before_model(fn)            — run before LLM call
  .after_model(fn)             — run after LLM call
  .before_tool(fn)             — run before tool call
  .after_tool(fn)              — run after tool call
  .guard(fn | G.xxx())         — output validation guard. Accepts a G composite
                                 (G.pii() | G.length(max=500)) or a plain callable.
                                 Guards run as after_model callbacks and validate/transform
                                 the LLM response before it is returned.
  .on_model_error(fn)          — error callback for LLM failures
  .on_tool_error(fn)           — error callback for tool failures

### Flow control

  .loop_until(pred, max=10)    — loop while predicate is false
  .loop_while(pred, max=3)     — loop while predicate is true
  .until(pred)                 — alias for loop_until
  .proceed_if(pred)            — conditional execution
  .timeout(seconds)            — wrap with time limit (returns TimedAgent)
  .dispatch(name=, on_complete=) — fire-and-forget background task (non-blocking)

### Transfer control (multi-agent routing)

  .sub_agent(agent)            — add child agent as a transfer target. The LLM decides
                                 when to hand off via the transfer_to_agent tool.
  .isolate()                   — prevent transfers to parent AND peers. Agent completes
                                 its task, then control auto-returns to parent.
                                 Most common pattern for specialist agents.
  .stay()                      — prevent transfer to parent only (can still transfer to
                                 sibling peers). Equivalent to
                                 .disallow_transfer_to_parent(True).
  .no_peers()                  — prevent transfer to siblings only (can still return to
                                 parent). Equivalent to
                                 .disallow_transfer_to_peers(True).

### Memory

  .memory(mode="preload")      — attach memory tools
  .memory_auto_save()          — auto-save to memory after execution

### Visibility

  .show()                      — include in topology
  .hide()                      — exclude from topology
  .transparent()               — transparent visibility mode
  .filtered()                  — filtered visibility mode
  .annotated()                 — annotated visibility mode

### Configuration

  .middleware(mw)              — attach middleware
  .inject(**resources)         — inject named resources into tool function parameters.
                                 Matched by parameter name at build time. Injected params
                                 are hidden from the LLM tool schema. Use for DB clients,
                                 API keys, config objects.
  .use(preset)                 — apply a Preset object that bundles multiple builder
                                 settings (model, instruction, tools, callbacks, etc.)
  .native(fn)                  — post-build hook: fn receives the raw ADK object for
                                 direct manipulation. Escape hatch for ADK features not
                                 yet exposed by the fluent API.
  .debug(enabled=True)         — debug tracing to stderr
  .strict()                    — enable strict contract checking
  .unchecked()                 — bypass contract checking
  .prepend(fn)                 — prepend dynamic text to the LLM's input via
                                 before_model_callback. fn(ctx) → str is injected before
                                 the main instruction each turn.

### Schemas

  .tool_schema(schema)         — attach tool schema
  .callback_schema(schema)     — attach callback schema
  .prompt_schema(schema)       — attach prompt schema
  .artifact_schema(schema)     — attach artifact schema
  .artifacts(*transforms)      — artifact operations

### Execution

Sync methods (.ask, .map) raise RuntimeError inside an async event loop
(Jupyter, FastAPI, etc.). Use the async variants instead.

  .build()                     — produce native ADK LlmAgent
  .ask(prompt)                 — one-shot SYNC execution (blocking)
  .ask_async(prompt)           — one-shot ASYNC execution (await)
  .stream(prompt)              — ASYNC streaming iterator (yields text chunks)
  .events(prompt)              — ASYNC raw ADK Event stream
  .session()                   — ASYNC context manager for multi-turn chat
  .map(prompts, concurrency=5) — batch SYNC execution (blocking)
  .map_async(prompts)          — batch ASYNC execution (await)
  .test(prompt, contains=)     — inline smoke test (sync, blocking)
  .mock(responses)             — replace LLM with canned responses
  .eval(prompt, expect=)       — inline evaluation
  .eval_suite()                — evaluation suite builder

### Introspection

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

### G — Guards (output validation)

Used with `.guard()`. Guards validate/transform the LLM response (after_model).
Compose with `|` (chain). Raise GuardViolation on failure.

  G.guard(fn)                  — custom guard function (fn receives llm_response)
  G.pii(detector=)             — detect and block/redact PII in output
  G.toxicity(threshold=)       — block toxic content above threshold
  G.length(max=)               — enforce max response length
  G.schema(model)              — validate output against Pydantic model
  GuardViolation               — raised when a guard check fails
  PIIDetector                  — PII detection provider
  ContentJudge                 — content judgment provider

### UI — Agent-to-UI composition (A2UI)

Declarative UI composition for agents. Compose with `|` (Row), `>>` (Column).
Import: ``from adk_fluent import UI`` or ``from adk_fluent._ui import UI``.

Component factories:
  UI.text(content, variant=)   — text content (h1-h5, caption, body)
  UI.button(label, action=)    — clickable button
  UI.text_field(label, bind=)  — text input with optional data binding
  UI.image(src, alt=, fit=)    — display an image
  UI.row(*children)            — horizontal layout
  UI.column(*children)         — vertical layout
  UI.component(kind, **props)  — generic escape hatch

Data binding & validation:
  UI.bind(path)                — create data binding to JSON Pointer path
  UI.required(msg=)            — required field validation
  UI.email(msg=)               — email format validation

Surface lifecycle:
  UI.surface(name, *children)  — create named surface (compilation root)
  UI.auto(catalog=)            — LLM-guided mode (agent decides UI)

Presets:
  UI.form(title, fields=)      — form surface from field spec
  UI.dashboard(title, cards=)  — dashboard with metric cards
  UI.wizard(title, steps=)     — multi-step wizard
  UI.confirm(message)          — confirmation dialog
  UI.table(columns, data_bind=) — data table

Agent integration:
  Agent.ui(spec)               — attach UI surface to agent
  T.a2ui()                     — A2UI toolset for LLM-guided mode
  G.a2ui(max_components=)      — validate LLM-generated UI
  P.ui_schema()                — inject catalog schema into prompt
  S.to_ui(*keys, surface=)     — bridge state → A2UI data model
  S.from_ui(*keys, surface=)   — bridge A2UI data model → state
  M.a2ui_log(level=)           — log A2UI surface operations
  C.with_ui(surface_id=)       — include UI state in context
"""

_HARNESS_PACKAGES = """
## Harness sub-packages (H namespace building blocks)

The ``H`` namespace is a thin façade over ten focused sub-packages that
implement the AI-coding harness runtime (hooks, permissions, plan mode,
session tape, reactor, subagents, usage, budget, compression, fs). Every
type is re-exported at the top level::

    from adk_fluent import (
        H,                                              # façade
        HookEvent, HookDecision, HookRegistry,          # _hooks
        PermissionMode, PermissionPolicy, PermissionPlugin,  # _permissions
        PlanMode, PlanModePolicy, PlanModePlugin,       # _plan_mode (see _harness)
        SessionTape, SessionStore, SessionSnapshot, SessionPlugin, ForkManager, Branch,
        EventRecord, Cursor, TapeBackend,
        InMemoryBackend, JsonlBackend, NullBackend, ChainBackend,  # _session
        Signal, SignalPredicate, Reactor, ReactorRule, # _reactor
        AgentToken, TokenRegistry, WorkflowLifecyclePlugin,  # _harness
        SubagentSpec, SubagentRegistry, SubagentResult,
        SubagentRunner, FakeSubagentRunner, make_task_tool,  # _subagents
        TurnUsage, AgentUsage, UsageTracker, UsagePlugin,
        CostTable, ModelRate,                           # _usage
        BudgetMonitor, BudgetPolicy, BudgetPlugin, Threshold,  # _budget
        CompressionStrategy, ContextCompressor,         # _compression
        FsBackend, FsStat, FsEntry,
        LocalBackend, MemoryBackend, SandboxedBackend, SandboxViolation,
        workspace_tools_with_backend,                   # _fs
    )

### _hooks — unified hook foundation

Session-scoped, subagent-inherited hook layer mirroring Claude Agent SDK's
hook surface. Install via ``H.hooks()`` and plug into the runner::

    registry = H.hooks(workspace="/project")
    registry.on(HookEvent.PRE_TOOL_USE, lambda ctx: HookDecision.deny("blocked"))
    app = App("coder").plugin(registry.plugin()).build()

  HookEvent                    — 12-value event enum (PreToolUse, PostToolUse,
                                 PreModel, PostModel, PreCompact, UserPrompt,
                                 Stop, SubagentStart, SubagentStop, Notification,
                                 SessionStart, SessionEnd)
  HookContext                  — normalized context (event, tool_name, args,
                                 state, extra) passed to every callable
  HookDecision                 — structured return protocol
    .allow() / .deny(reason=) / .modify(patch=) / .replace(output=)
    .ask(prompt=) / .inject(message=)
  HookMatcher                  — event + tool-name regex + arg-glob filter
  HookRegistry                 — user-facing registry of hook callables and
                                 shell commands; ``.on(event, fn)`` /
                                 ``.command(event, cmd)`` / ``.plugin()``
  HookPlugin                   — ADK ``BasePlugin`` that dispatches 12 callbacks
  SystemMessageChannel         — transient system-message queue drained before
                                 every LLM call (SYSTEM_MESSAGE_STATE_KEY)

### _permissions — decision-based permission layer

Mirrors Claude Agent SDK's ``canUseTool`` surface and the five permission
modes. Session-scoped via an ADK plugin::

    policy = H.auto_allow("read_file").merge(H.ask_before("bash"))
    plugin = H.permission_plugin(policy=policy, handler=my_handler)

  PermissionMode               — default / accept_edits / plan / bypass / dont_ask
  PermissionDecision           — allow(updated_input=) / deny(reason=)
                                 / ask(message=) structured returns
  PermissionBehavior           — enum for the three decision branches
  PermissionPolicy             — declarative allow/deny/ask sets + patterns;
                                 .check(tool_name, args=) → PermissionDecision;
                                 .merge(other) for composition
  PermissionPlugin             — ADK plugin that enforces the policy
  PermissionHandler            — protocol for interactive approval flows
  ApprovalMemory               — session-scoped record of interactive approvals
  DEFAULT_MUTATING_TOOLS       — frozenset used by Plan Mode

### _plan_mode — plan-then-execute latch

Three-state latch (``off`` / ``planning`` / ``executing``) paired with a
policy wrapper and ADK plugin. Exported from ``adk_fluent._harness``::

    from adk_fluent._harness import PlanMode, PlanModePolicy, PlanModePlugin
    latch = H.plan_mode()
    policy = H.plan_mode_policy(base_policy, latch=latch)
    plugin = H.plan_mode_plugin(latch=latch)

  PlanMode                     — runtime latch with subscription API.
                                 .current, .enter(), .exit(plan=),
                                 .reset(), .subscribe(fn) → unsubscribe
                                 .is_planning, .is_executing
  PlanModePolicy               — frozen wrapper around PermissionPolicy.
                                 Denies mutating tools while planning;
                                 exposes .mode reflecting latch state.
  PlanModePlugin               — ADK plugin that owns a latch and installs
                                 a before_tool_callback rejecting mutating
                                 tools during planning.
  plan_mode_tools(latch)       — returns (enter_plan_mode, exit_plan_mode)
                                 tool pair for registration with Agent.tools()
  MUTATING_TOOLS               — frozenset of tool names classified as mutating
                                 (write_file, edit_file, bash, run_code, …)

### _session — tape + fork + store (durable event log)

Session-scoped event recording plus named state branches. Every recorded
entry carries a monotonic ``seq``; consumers read with ``since(n)`` or
follow live writes with async ``tail(from_seq=...)``. See the
reactor + durable-events section below for the full surface::

    store = H.session_store(max_events=100, max_branches=10)
    plugin = H.session_plugin(store)
    store.fork("before-refactor", {"draft": "v1"})

  SessionTape                  — durable event recorder/replayer.
                                 .record(event) → stamps seq; .head,
                                 .since(from_seq=0), async .tail(from_seq=0),
                                 .filter(kind), .save(path), .load(path),
                                 .summary(), .size, .clear().
                                 Optional ``backend=`` kwarg mirrors writes
                                 to a pluggable TapeBackend.
  EventRecord / Cursor         — typed aliases for tape entries and seq ints
  TapeBackend                  — Protocol: append(entry). Persistence adapter
                                 layer. Exceptions never block the tape.
  InMemoryBackend              — deque mirror for tests / replay parity
  JsonlBackend(path=, truncate=) — one-event-per-line JSONL file
  NullBackend                  — /dev/null; drops every write
  ChainBackend([a, b, ...])    — fan out to multiple backends
  Branch                       — immutable record of a named state snapshot
  ForkManager                  — named-branch manager with merge + diff.
                                 .fork(name, state), .switch(name) → deep copy,
                                 .merge(a, b, strategy="union"|"intersection"|"prefer"),
                                 .diff(a, b), .delete(name), .list_branches()
  SessionStore                 — bundles a tape + fork manager.
                                 .record_event, .fork, .switch, .snapshot(),
                                 .from_snapshot(snap), .auto_fork(name),
                                 .auto_restore(name), .summary(), .clear()
  SessionSnapshot              — frozen serialisable view of events + branches.
                                 .to_dict() / .from_dict(), .save() / .load()
  SessionPlugin                — ADK plugin that auto-forks after every agent
                                 via after_agent_callback (``auto:<name>``)

### _reactor — reactive signals over the durable tape

Turns the durable tape into something agents can collaborate on: typed
state cells (signals), declarative triggers (predicates), priority
scheduling, and cooperative interrupts with a resume cursor::

    from adk_fluent import Signal, Reactor
    temp = Signal("temp", 72.0).attach(bus)
    r = Reactor()
    r.when(temp.rising.where(lambda v: v > 90), alert_ops, priority=10)
    r.start()

  Signal                       — typed state cell. .get() / .set(v, force=)
                                 / .update(fn) / .version / .subscribe(fn)
                                 / .attach(bus) — equal-to-current writes
                                 are no-ops unless ``force=True``.
  SignalPredicate              — declarative trigger. signal.changed /
                                 .rising / .falling / .is_(value). Compose
                                 with ``a & b``, ``a | b``, ``~a``,
                                 ``.where(fn)``, ``.debounce(ms)``,
                                 ``.throttle(ms)``.
  Reactor                      — scheduler of (predicate, handler, options)
                                 rules. .when(pred, fn, priority=, preemptive=,
                                 agent_name=) / .start() / .stop().
                                 Rules ordered by priority (lower wins).
  ReactorRule                  — frozen rule record returned by .when().
  AgentToken                   — per-agent cancellation token extending
                                 CancellationToken with ``agent_name`` and
                                 ``resume_cursor``; cancel_with_cursor(c)
                                 atomic cancel + resume record.
  TokenRegistry                — keyed container of AgentTokens; install()
                                 swaps live tokens while preserving in-flight
                                 closures, .cancel(name, resume_cursor=),
                                 .reset(name) / .reset_all().
  WorkflowLifecyclePlugin      — ADK plugin that emits StepStarted/Completed,
                                 IterationStarted/Completed, BranchStarted/
                                 Completed, SubagentStarted/Completed, and
                                 AttemptFailed events for Pipeline/Loop/FanOut
                                 nodes — the tape-visible counterpart to the
                                 callback hooks.

### durable events (cross-cutting)

The same tape powers streaming replay, multi-consumer fanout, and
crash-safe audit. These entry points live on ``adk_fluent`` directly
(not in a single sub-package) because they span ``_session`` +
``_helpers`` + ``_harness._events``::

    async for chunk in run_stream_from(agent, cursor=42):
        print(chunk)

  run_stream_from(builder, cursor=)
                               — replay ``tape.since(cursor)`` text chunks
                                 then switch to live ``tape.tail()``.
                                 Lets a dropped SSE connection pick up
                                 where it left off without re-running the
                                 LLM.
  HarnessEvent subtypes         — SignalChanged, Interrupted, StepStarted,
                                 StepCompleted, IterationStarted,
                                 IterationCompleted, BranchStarted,
                                 BranchCompleted, SubagentStarted,
                                 SubagentCompleted, AttemptFailed. Every
                                 frozen-slotted; recorded onto the tape
                                 via the event bus when plugins are wired.

### _subagents — dynamic spawner + task tool

Runtime-decided specialist dispatch — the missing piece between
``.sub_agent()`` (compile-time transfer) and ``.agent_tool()`` (static tool)::

    registry = H.subagent_registry([
        H.subagent_spec("researcher", "Find three papers.",
                        description="Deep research"),
        H.subagent_spec("reviewer", "Critique the draft."),
    ])
    runner = FakeSubagentRunner()           # or a real runner
    task   = H.task_tool(registry, runner)  # parent-agent tool

  SubagentSpec                 — frozen role description (role, instruction,
                                 description, model, tool_names,
                                 permission_mode, max_tokens, metadata)
  SubagentRegistry             — dict-like keyed by role. .register / .unregister
                                 / .replace / .get / .require / .roles() /
                                 .roster() / iteration support
  SubagentResult               — structured output (role, output, is_error,
                                 error, usage, metadata, artifacts);
                                 .to_tool_output() → ``[role] text``
  SubagentRunner               — Protocol: ``run(spec, prompt, ctx) → SubagentResult``
  FakeSubagentRunner           — test double with responder callable,
                                 error_for_role override, usage injection,
                                 and a .calls audit log
  SubagentRunnerError          — raised when runner wiring fails
  make_task_tool(registry, runner, *, context_provider=, tool_name="task")
                               — factory. Returns a callable whose docstring
                                 is rewritten to enumerate registered roles
                                 so the parent LLM picks the right specialist.

### _usage — cumulative token + cost tracking

Session-scoped usage accounting with per-agent breakdown and USD cost via a
frozen cost table::

    table = H.cost_table(**{"gemini-2.5-pro": {"in": 1.25, "out": 5.00}})
    tracker = H.usage(cost_table=table)
    plugin  = H.usage_plugin(tracker)

  TurnUsage                    — frozen per-call record (agent, model,
                                 input_tokens, output_tokens, cached_tokens,
                                 cost_usd, timestamp)
  AgentUsage                   — frozen cumulative view for one agent
  ModelRate                    — frozen per-model pricing ({input, output, cached})
  CostTable                    — frozen dict of model → ModelRate with
                                 .estimate(model, in_tokens, out_tokens)
  UsageTracker                 — mutable aggregator. .record(turn),
                                 .callback() for after_model wiring,
                                 .by_agent() breakdown, .summary(),
                                 cumulative properties
  UsagePlugin                  — ADK plugin that captures every LLM call in
                                 the invocation tree via after_model_callback

### _budget — cumulative token budget + thresholds

Enforces a session-wide token ceiling and fires callbacks at percent
checkpoints. Designed to pair with ``ContextCompressor`` via
``compressor.to_monitor()``::

    budget = H.budget_policy(max_tokens=200_000)
        .add_threshold(percent=80, on_trigger=lambda m: print("80%!"))
        .add_threshold(percent=95, on_trigger=compact_now)
    monitor = H.budget_monitor(budget)
    plugin  = H.budget_plugin(monitor)

  Threshold                    — frozen {percent, on_trigger} checkpoint
  BudgetPolicy                 — frozen {max_tokens, thresholds}. Immutable.
                                 .add_threshold(percent, on_trigger)
  BudgetMonitor                — mutable tracker. .record_usage(in, out),
                                 .utilisation, .remaining, .is_over_budget,
                                 .summary(), .reset()
  BudgetPlugin                 — ADK plugin auto-wiring every LLM call to
                                 .record_usage()

### _compression — message-level compression with pre_compact hook

The message-rewriting half of context management. ``C.*`` transforms shape
what the LLM sees on a single turn; ``ContextCompressor`` rewrites the
persistent message history when it exceeds a threshold::

    strategy = CompressionStrategy.keep_recent(n=8)
    compressor = H.compressor(threshold=100_000, strategy=strategy)
    compressor = compressor.with_hooks(hook_registry)  # pre_compact wired

  CompressionStrategy          — frozen description of *how* to compress.
                                 .drop_old(keep_turns=) / .keep_recent(n=)
                                 / .summarize(model=)
  ContextCompressor            — the machine.
                                 .should_compress(tokens) / .compress_messages
                                 / .compress_messages_async(msgs, summarizer=)
                                 / .with_hooks(registry) / .to_monitor()
                                 pre_compact hook: allow / deny / replace / modify

### _fs — pluggable filesystem backend

Factors the workspace tools' ``pathlib`` calls behind a small Protocol so
tools can be unit-tested without a real disk and re-targeted at in-memory
or remote storage. See the [fs](user-guide/fs.md) user-guide page for the
full cookbook::

    backend = SandboxedBackend(MemoryBackend(), H.workspace_only("/tmp/ws"))
    tools   = workspace_tools_with_backend(backend, read_only=False)

  FsBackend                    — runtime-checkable Protocol: exists, stat,
                                 read_text, read_bytes, write_text,
                                 write_bytes, delete, mkdir, list_dir,
                                 iter_files, glob
  FsStat                       — frozen dataclass: path, size, is_dir,
                                 is_file, mtime
  FsEntry                      — frozen dataclass: name, path, is_dir,
                                 is_file (one per ``list_dir`` result)
  LocalBackend                 — real on-disk I/O via pathlib
  MemoryBackend(files=None)    — dict-backed fake for tests and ephemeral
                                 scratch workspaces; POSIX semantics on
                                 every host.
  SandboxedBackend(inner, sandbox)
                               — decorator wrapping any backend with a
                                 SandboxPolicy; refuses operations that
                                 escape the allowed paths.
  SandboxViolation             — PermissionError raised when a path is
                                 rejected; tool shims translate into a
                                 user-facing "Error: path '...' is outside
                                 the allowed workspace." string.
  workspace_tools_with_backend(backend, *, read_only=False)
                               — factory returning the full workspace tool
                                 set (read_file / edit_file / write_file /
                                 list_dir / glob_search / grep_search)
                                 routed through ``backend``.
"""

_EXPRESSION_PRIMITIVES = """
## Expression operators explained

    A >> B           # Sequential: A runs, then B. Returns a Pipeline.
    A | B            # Parallel: A and B run concurrently. Returns a FanOut.
    (A >> B) * 3     # Loop: repeat the pipeline 3 times. Returns a Loop.
    (A >> B) * until(pred, max=5)  # Conditional loop: repeat until pred(state) is true.
    A // B           # Fallback: try A first. If A fails (exception), try B.
    A @ Schema       # Structured output: constrain A's response to a Pydantic model.
                     # Equivalent to A.returns(Schema).

## Expression primitives

Function-level primitives for use with expression operators:

  until(pred, max=10)          — loop condition for * operator
  tap(fn)                      — inline observation step (no LLM, zero cost). Reads
                                 state, runs side-effect, never mutates state.
  expect(pred, msg=)           — inline state assertion. Raises ValueError if pred(state)
                                 is false. Unlike tap(), this is a contract check, not a
                                 side-effect observer.
  map_over(key)                — map agent over list items in state[key]
  gate(predicate)              — conditional execution (skip if false)
  race(*agents)                — first-to-complete wins
  dispatch(name=, on_complete=) — launch background task (non-blocking)
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

A2A patterns (remote agent-to-agent):

  a2a_cascade(*endpoints, names=, timeout=)   — fallback chain across remote agents
  a2a_fanout(*endpoints, names=, timeout=)    — parallel fan-out to remote agents
  a2a_delegate(coordinator, **remotes)        — coordinator with named remote specialists
"""

_A2A_SECTION = """
## A2A (Agent-to-Agent) remote communication

Experimental support for the A2A protocol. Requires `pip install google-adk[a2a]`.

### RemoteAgent — consume a remote A2A agent

    from adk_fluent import RemoteAgent

    remote = (
        RemoteAgent("researcher", agent_card="http://researcher:8001/.well-known/agent.json")
        .describe("Remote research specialist")
        .timeout(30)
        .sends("query")           # serialize state keys into A2A message
        .receives("findings")     # deserialize A2A response back into state
        .persistent_context()     # maintain contextId across calls in same session
    )

RemoteAgent extends BuilderBase — all operators (>>, |, //, *) work:

    pipeline = Agent("writer") >> remote >> Agent("reviewer")
    fallback = remote // Agent("local-fallback", "gemini-2.5-flash")

### A2AServer — publish a local agent via A2A

    from adk_fluent import A2AServer

    server = (
        A2AServer(my_agent)
        .port(8001)
        .version("1.0.0")
        .provider("Acme Corp", "https://acme.com")
        .skill("research", "Academic Research",
               description="Deep research with citations",
               tags=["research", "citations"])
        .health_check()
        .graceful_shutdown(timeout=30)
    )

### A2A middleware (M namespace)

    M.a2a_retry(max_attempts=3, backoff=2.0)   — retry with exponential backoff
    M.a2a_circuit_breaker(threshold=5, reset_after=60)  — circuit breaker
    M.a2a_timeout(seconds=30)                  — per-agent timeout

### A2A tool composition (T namespace)

    T.a2a(agent_card_url, name=, description=, timeout=)  — wrap remote agent as tool

### Discovery

    RemoteAgent.discover("research-agent.agents.acme.com")  — DNS well-known discovery
    AgentRegistry("http://registry:9000").find(name="research")  — registry-based
    RemoteAgent("code", env="CODE_AGENT_URL")  — environment variable configuration
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
15. Use `.sub_agent()` for transfer-based delegation (LLM decides routing);
    use `.agent_tool()` for tool-based invocation (parent stays in control)
16. Use `.isolate()` on specialist agents by default — it is the most predictable pattern
17. Always set `.describe()` on sub-agents — the description helps the coordinator LLM
    pick the right specialist during transfer routing
18. Use `.ask_async()` and `.map_async()` in async contexts (Jupyter, FastAPI).
    The sync variants (.ask, .map) raise RuntimeError inside running event loops.
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
        _HARNESS_PACKAGES,
        _EXPRESSION_PRIMITIVES,
        _COMPOSITION_PATTERNS,
        _A2A_SECTION,
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
# TypeScript-flavored content
# ---------------------------------------------------------------------------

_TS_HEADER = """\
# adk-fluent-ts — LLM Context

> Auto-generated from manifest.json. Do not edit manually.
> Repo: https://github.com/vamsiramakrishnan/adk-fluent
> Package directory: ts/

adk-fluent-ts is the TypeScript port of adk-fluent — a fluent builder API
that wraps Google's Agent Development Kit. The TS package mirrors the Python
API surface but uses TypeScript idioms (immutable clones, method-chained
operators, camelCase).
"""

_TS_INSTALL = """\
## Install (TypeScript)

    cd ts
    npm install
    npm run build

The package targets ``@google/adk`` (the JavaScript port of Google ADK).
"""

_TS_IMPORTS = """\
## Imports (TypeScript)

    import { Agent, Pipeline, FanOut, Loop, Fallback } from "adk-fluent-ts";
    import { S, C, P, T, G, M, A, E, UI } from "adk-fluent-ts";
    import { tap, expect, gate, race, dispatch, join, Route } from "adk-fluent-ts";
    import { reviewLoop, mapReduce, cascade, chain, conditional } from "adk-fluent-ts";
    import { RemoteAgent, A2AServer, AgentRegistry } from "adk-fluent-ts";
"""

_TS_OPERATORS = """\
## Operators → method chains

JavaScript has no operator overloading, so adk-fluent-ts uses method calls:

  Python      TypeScript                 Returns
  --------    -----------------------    --------
  a >> b      a.then(b)                  Pipeline
  a | b       a.parallel(b)              FanOut
  a * 3       a.times(3)                 Loop
  a * until   a.timesUntil(pred,{max})   Loop
  a // b      a.fallback(b)              Fallback
  a @ Schema  a.outputAs(Schema)         Agent

Sub-builders passed to workflow builders are auto-built — do not call
``.build()`` on individual steps.
"""

_TS_EXAMPLE = """\
## Example (TypeScript)

    import { Agent, Pipeline } from "adk-fluent-ts";

    const writer = new Agent("writer", "gemini-2.5-flash")
      .instruct("Write a draft about {topic}.")
      .writes("draft");

    const reviewer = new Agent("reviewer", "gemini-2.5-flash")
      .instruct("Review the draft: {draft}")
      .writes("feedback");

    const pipeline = new Pipeline("review_flow")
      .step(writer)
      .step(reviewer)
      .build();

    // Equivalent with method-chained operators:
    const pipeline2 = writer.then(reviewer).times(3).build();
"""

_TS_COMMANDS = """\
## Development commands (TypeScript)

    cd ts
    npm install                              # install
    npm test                                 # run vitest
    npm run typecheck                        # tsc --noEmit
    npm run build                            # tsc -> dist/
    just ts-generate                         # regenerate builders from seed
    just ts-test                             # run tests via just
"""

# TypeScript-flavored namespace reference.  The TS package mirrors the Python
# API but uses camelCase identifiers (e.g. ``C.fromState`` not
# ``C.from_state``) and method-chain composition (``.pipe()`` / ``.add()``)
# instead of the Python ``|`` / ``+`` operators.  JS reserved words like
# ``default`` require a trailing underscore (``S.default_``, ``C.default_``).
_TS_NAMESPACE_MODULES = """
## Namespace modules (S, C, P, A, M, T, E, G)

All namespaces mirror the Python API with TypeScript idioms: camelCase
method names, method-chained composition via ``.pipe()`` / ``.add()``, and
options-object arguments instead of keyword arguments.  JavaScript reserved
words (``default``) use a trailing underscore (``S.default_``, ``C.default_``).

### S — State transforms

Used in pipelines via ``.then()``.  Compose with ``.pipe()`` (chain) or
``.add()`` (combine).

  S.pick(...keys)              — keep only named keys
  S.drop(...keys)              — remove named keys
  S.rename({old: "new"})       — rename keys
  S.merge_([keys], "into")     — combine keys (note trailing underscore)
  S.transform(key, fn)         — apply function to value
  S.compute({key: fn, ...})    — derive new keys from state
  S.set({k: v})                — set explicit key-value pairs
  S.default_({k: v})           — fill missing keys with defaults
  S.guard(pred, msg?)          — assert state invariant
  S.when(pred, transform)      — conditional transform
  S.branch(key, {match: tr})   — route to different transforms
  S.capture(...keys)           — capture function args into state
  S.identity()                 — pass-through (no-op)
  S.accumulate(key)            — append to list in state
  S.counter(key)               — increment counter in state
  S.history(key)               — maintain history list
  S.validate({k: schema})      — validate state keys against schemas
  S.require(...keys)           — assert keys exist
  S.flatten(key)               — flatten nested dict
  S.unflatten(key, {sep})      — unflatten dotted keys
  S.zip(...keys, "into")       — zip parallel lists
  S.groupBy(key, {by})         — group items by field
  S.log(...keys)               — log state keys

### C — Context engineering

Used with ``.context()``.  Compose with ``.add()`` (union) or ``.pipe()``.

  C.none()                     — suppress all history
  C.default_()                 — default ADK behavior
  C.userOnly()                 — only user messages
  C.window(n)                  — last N turn-pairs
  C.fromState(...keys)         — inject state keys as context
  C.fromAgents(...names)       — user + named agent outputs
  C.fromAgentsWindowed({n})    — windowed agent output filtering
  C.excludeAgents(...names)    — exclude named agents
  C.template(text)             — template with {key} placeholders
  C.select(...agentNames)      — select specific agents
  C.recent({n})                — recent messages only
  C.compact()                  — remove redundant messages
  C.dedup()                    — remove duplicate messages
  C.truncate({maxTurns})       — hard limit
  C.project(...fields)         — project specific fields
  C.budget({maxTokens})        — token budget constraint
  C.priority(...keys)          — prioritize certain context
  C.fit({maxTokens})           — fit within token limit
  C.fresh({maxAge})            — filter by recency
  C.redact(...patterns)        — redact sensitive content
  C.summarize({scope})         — LLM-powered summarization
  C.relevant({queryKey})       — semantic relevance filtering
  C.extract({key})             — extract structured data
  C.distill()                  — distill to key points
  C.validate()                 — validate context integrity
  C.notes()                    — attach notes
  C.writeNotes()               — persist notes to state
  C.rolling({n})               — rolling window with compaction
  C.user()                     — user messages only (alias)
  C.manusCascade()             — Manus-style cascading context
  C.when(pred, transform)      — conditional context transform

### P — Prompt composition

Used with ``.instruct()``.  Compose with ``.add()`` (union) or ``.pipe()``.
Section order: role → context → task → constraint → format → example.

  P.role(text)                 — agent persona
  P.context(text)              — background context
  P.task(text)                 — primary objective
  P.constraint(...rules)       — constraints/rules
  P.format(text)               — output format spec
  P.example({input, output})   — few-shot examples (options object)
  P.section(name, text)        — custom named section
  P.when(pred, block)          — conditional inclusion
  P.fromState(...keys)         — dynamic state injection
  P.template(text)             — {key}, {key?}, {ns:key} placeholders
  P.reorder(...sections)       — reorder sections
  P.only(...sections)          — include only named sections
  P.without(...sections)       — exclude named sections
  P.compress()                 — compress verbose prompts
  P.adapt(fn)                  — transform prompt dynamically
  P.scaffolded(structure)      — structured prompt scaffold
  P.versioned(v, text)         — versioned prompt variants

### A — Artifacts

Used with ``.artifacts()`` or ``.then()``.  Compose with ``.pipe()``.

  A.publish(filename, {fromKey}) — state → artifact
  A.snapshot(filename, {intoKey}) — artifact → state
  A.save(filename, {content})   — content → artifact
  A.load(filename)              — artifact → pipeline
  A.list()                      — list available artifacts
  A.version(filename)           — get artifact version
  A.delete_(filename)           — delete artifact (reserved word)
  A.publishMany({mapping})      — batch publish multiple artifacts
  A.snapshotMany({mapping})     — batch snapshot multiple artifacts
  A.forLlm()                    — context transform for LLM-aware loading
  A.when(pred, transform)       — conditional artifact operation
  A.fromJson() / A.fromCsv() / A.fromMarkdown() — content transforms (pre-publish)
  A.asJson() / A.asCsv() / A.asText() — content transforms (post-snapshot)

### M — Middleware

Used with ``.middleware()``.  Compose with ``.pipe()`` (chain).
Most factories take an options object.

  M.retry({maxAttempts})       — retry with exponential backoff
  M.log()                      — structured event logging
  M.cost()                     — token usage tracking
  M.latency()                  — per-agent latency tracking
  M.scope([agents], mw)        — restrict middleware to agents
  M.when(condition, mw)        — conditional middleware
  M.circuitBreaker({maxFails}) — circuit breaker pattern
  M.timeout({seconds})         — per-agent timeout
  M.cache({ttl})               — response caching
  M.fallbackModel(model)       — fallback to different model
  M.dedup()                    — deduplicate requests
  M.sample({rate})             — probabilistic sampling
  M.trace()                    — distributed tracing
  M.metrics()                  — metrics collection
  M.beforeAgent(fn)            — pre-agent hook
  M.afterAgent(fn)             — post-agent hook
  M.beforeModel(fn)            — pre-model hook
  M.afterModel(fn)             — post-model hook
  M.onLoop(fn)                 — loop iteration hook
  M.onTimeout(fn)              — timeout event hook
  M.onRoute(fn)                — routing event hook
  M.onFallback(fn)             — fallback event hook

### T — Tool composition

Used with ``.tools()``.  Compose with ``.pipe()`` (chain).

  T.fn(callable)               — wrap callable as FunctionTool
  T.agent(agent)               — wrap agent as AgentTool
  T.googleSearch()             — built-in Google Search
  T.search(registry)           — BM25-indexed dynamic loading
  T.toolset(toolset)           — wrap MCPToolset or similar
  T.schema(schema)             — attach ToolSchema
  T.mock(responses)            — mock tool for testing
  T.confirm({prompt})          — human confirmation wrapper
  T.timeout({seconds})         — tool timeout wrapper
  T.cache({ttl})               — tool response caching
  T.mcp(server)                — MCP server tool
  T.openapi(spec)              — OpenAPI spec tool
  T.transform(fn)              — transform tool output

### E — Evaluation

Used with ``.eval()`` / ``.evalSuite()``.  Build evaluation criteria and
test suites.

  E.case(prompt, {expect})     — single evaluation case
  E.criterion(name, fn)        — custom evaluation criterion
  E.persona(name, {style})     — persona for evaluation
  EvalSuite                    — collection of eval cases
  EvalReport                   — evaluation results
  ComparisonReport             — compare multiple agents/models

### G — Guards (output validation)

Used with ``.guard()``.  Guards validate/transform the LLM response
(afterModel).  Compose with ``.pipe()`` (chain).  Throws ``GuardViolation``
on failure.

  G.guard(fn)                  — custom guard function
  G.pii({action, detector})    — detect and block/redact PII in output
  G.toxicity({threshold, judge}) — block toxic content above threshold
  G.length({min, max})         — enforce length bounds
  G.regex(pattern, {action})   — block or redact pattern matches
  G.schema(schema)             — validate output against schema
  G.output(schema)             — post-model schema validation
  G.input(schema)              — pre-model input schema validation
  G.budget({maxTokens})        — token budget constraint
  G.rateLimit({rpm})           — requests-per-minute limit
  G.maxTurns(n)                — cap conversation turns
  G.topic({deny})              — block specific topics
  G.grounded({sourcesKey})     — verify output is grounded in sources
  G.hallucination({threshold}) — detect hallucinated content
  G.when(pred, guard)          — conditional guard
  G.dlp({project, infoTypes, location}) — Google Cloud DLP detector
  G.regexDetector([patterns])  — lightweight regex-based PII detector
  G.multi(...detectors)        — union of multiple detectors
  GuardViolation               — raised when a guard check fails
  PIIDetector                  — PII detection provider type
  ContentJudge                 — content judgment provider type

### UI — Agent-to-UI composition (A2UI)

Declarative UI composition for agents.  Compose with ``.pipe()`` / ``.add()``.
Import: ``import { UI } from "adk-fluent-ts";``

Component factories:
  UI.text(content, {variant})  — text content (h1-h5, caption, body)
  UI.button(label, {action})   — clickable button
  UI.textField(label, {bind})  — text input with optional data binding
  UI.image(src, {alt, fit})    — display an image
  UI.row(...children)          — horizontal layout
  UI.column(...children)       — vertical layout
  UI.component(kind, props)    — generic escape hatch

Data binding & validation:
  UI.bind(path)                — create data binding to JSON Pointer path
  UI.required({msg})           — required field validation
  UI.email({msg})              — email format validation

Surface lifecycle:
  UI.surface(name, ...children) — create named surface (compilation root)
  UI.auto({catalog})           — LLM-guided mode (agent decides UI)

Presets:
  UI.form(title, {fields})     — form surface from field spec
  UI.dashboard(title, {cards}) — dashboard with metric cards
  UI.wizard(title, {steps})    — multi-step wizard
  UI.confirm(message)          — confirmation dialog
  UI.table({columns, dataBind}) — data table

Agent integration:
  Agent.ui(spec)               — attach UI surface to agent
  T.a2ui()                     — A2UI toolset for LLM-guided mode
  G.a2ui({maxComponents})      — validate LLM-generated UI
  P.uiSchema()                 — inject catalog schema into prompt
  S.toUi(...keys, {surface})   — bridge state → A2UI data model
  S.fromUi(...keys, {surface}) — bridge A2UI data model → state
  M.a2uiLog({level})           — log A2UI surface operations
  C.withUi({surfaceId})        — include UI state in context
"""

# TypeScript-flavored harness sub-packages reference.  Mirrors
# ``_HARNESS_PACKAGES`` but uses camelCase identifiers, options-object
# arguments, and method-chain composition.
_TS_HARNESS_PACKAGES = """
## Harness sub-packages (H namespace building blocks)

The ``H`` namespace is a thin façade over ten focused sub-packages that
implement the AI-coding harness runtime (hooks, permissions, plan mode,
session tape, reactor, subagents, usage, budget, compression, fs).
Every type is re-exported at the package root::

    import {
      H,                                                  // façade
      HookEvent, HookDecision, HookRegistry,              // hooks
      PermissionMode, PermissionPolicy, PermissionPlugin, // permissions
      PlanMode, PlanModePolicy, PlanModePlugin,           // planMode
      SessionTape, SessionStore, SessionSnapshot,
      SessionPlugin, ForkManager, Branch,
      EventRecord, Cursor, TapeBackend,
      InMemoryBackend, JsonlBackend, NullBackend, ChainBackend, // session
      Signal, SignalPredicate, Reactor, ReactorRule,      // reactor
      AgentToken, TokenRegistry, WorkflowLifecyclePlugin, // harness
      SubagentSpec, SubagentRegistry, SubagentResult,
      SubagentRunner, FakeSubagentRunner, makeTaskTool,   // subagents
      TurnUsage, AgentUsage, UsageTracker, UsagePlugin,
      CostTable, ModelRate,                               // usage
      BudgetMonitor, BudgetPolicy, BudgetPlugin, Threshold, // budget
      CompressionStrategy, ContextCompressor,             // compression
      FsBackend, FsStat, FsEntry,
      LocalBackend, MemoryBackend, SandboxedBackend, SandboxViolation, // fs
    } from "adk-fluent-ts";

### hooks — unified hook foundation

Session-scoped, subagent-inherited hook layer mirroring Claude Agent
SDK's hook surface.  Install via ``H.hooks()`` and plug into the
runner::

    const registry = H.hooks({ workspace: "/project" });
    registry.on(HookEvent.PreToolUse, (ctx) =>
      HookDecision.deny("blocked"),
    );
    const app = new App("coder").plugin(registry.plugin()).build();

  HookEvent                    — 12-value event enum (PreToolUse,
                                 PostToolUse, PreModel, PostModel,
                                 PreCompact, UserPrompt, Stop,
                                 SubagentStart, SubagentStop,
                                 Notification, SessionStart, SessionEnd)
  HookContext                  — normalized context (event, toolName,
                                 toolInput, state, extra) passed to
                                 every callable
  HookDecision                 — structured return protocol
    .allow() / .deny({reason}) / .modify({toolInput})
    .replace({output}) / .ask({prompt}) / .inject({systemMessage})
  HookMatcher                  — event + toolName regex + arg-glob filter
    HookMatcher.forTool(event, toolName, {argGlob})
  HookRegistry                 — ``.on(event, fn, {match})`` /
                                 ``.shell(event, cmd, {match})`` /
                                 ``.merge(other)`` / ``.asPlugin({name})``
  HookPlugin                   — ADK ``BasePlugin`` dispatching 12 callbacks

### permissions — decision-based permission layer

Mirrors Claude Agent SDK's ``canUseTool`` surface and the five
permission modes.  Session-scoped via an ADK plugin::

    const policy = H.autoAllow("read_file")
      .merge(H.askBefore("bash"));
    const plugin = H.permissionPlugin({ policy, handler: myHandler });

  PermissionMode               — Default / AcceptEdits / Plan / Bypass / DontAsk
  PermissionDecision           — .allow({updatedInput}) / .deny({reason})
                                 / .ask({prompt}) structured returns;
                                 predicates .isAllow / .isDeny / .isAsk
  PermissionPolicy             — declarative allow/deny/ask sets + patterns.
                                 .check(toolName, toolInput?) → PermissionDecision
                                 .merge(other) / .withMode(mode) / .isMutating(tool)
  PermissionPlugin             — ADK plugin that enforces the policy
  ApprovalMemory               — session-scoped record of interactive approvals.
                                 .rememberSpecific / .rememberTool / .recall / .clear

  H.permissions({mode, allow, deny, ask, …})  — factory
  H.permissionsPlan({allow})                  — plan-mode defaults
  H.permissionsBypass() / H.permissionsAcceptEdits({ask})
  H.permissionsDontAsk({allow})
  H.askBefore(...tools) / H.autoAllow(...tools) / H.deny(...tools)
  H.allowPatterns(...patterns) / H.denyPatterns(...patterns)
  H.permissionPlugin({policy, handler, memory})

### planMode — plan-then-execute latch

Three-state latch (``off`` / ``planning`` / ``executing``) paired with
a policy wrapper and ADK plugin::

    const latch  = H.planMode();
    const policy = H.planModePolicy(basePolicy, latch);
    const plugin = H.planModePlugin({ latch });

  PlanMode                     — runtime latch with subscription API.
                                 .current / .enter() / .exit({plan})
                                 .reset() / .subscribe(fn) → unsubscribe
                                 .isPlanning / .isExecuting
  PlanModePolicy               — frozen wrapper around PermissionPolicy;
                                 denies mutating tools while planning
  PlanModePlugin               — ADK plugin owning a latch + before_tool
                                 callback rejecting mutations in planning
  planModeTools(latch)         — returns {enterPlanMode, exitPlanMode}
                                 tool pair for ``.tools()`` registration
  MUTATING_TOOLS               — frozen set of tool names classified as
                                 mutating (writeFile, editFile, bash, …)

### session — tape + fork + store (durable event log)

Session-scoped event recording plus named state branches. Every entry
carries a monotonic ``seq``; consumers read with ``since(n)`` or follow
live writes with async ``tail(fromSeq)``::

    const store  = H.sessionStore({ maxEvents: 100, maxBranches: 10 });
    const plugin = H.sessionPlugin(store);
    store.fork("before-refactor", { draft: "v1" });

  SessionTape                  — durable event recorder/replayer.
                                 .record(event) → stamps seq; .head,
                                 .since({fromSeq}), async ``tail({fromSeq})``
                                 (async iterator), .filter(kind)
                                 .save(path) / .load(path) / .summary().
                                 Optional ``backend`` option mirrors writes
                                 to a pluggable TapeBackend.
  EventRecord / Cursor         — typed aliases for tape entries and seq ints
  TapeBackend                  — Protocol: append(entry). Persistence
                                 adapter layer; exceptions never block the
                                 tape.
  InMemoryBackend              — deque mirror for tests / replay parity
  JsonlBackend({path, truncate}) — one-event-per-line JSONL file
  NullBackend                  — drops every write (``/dev/null``)
  ChainBackend([a, b, …])      — fan out to multiple backends
  Branch                       — immutable record of a named snapshot
  ForkManager                  — named branches with merge + diff.
                                 .fork(name, state) / .switch(name)
                                 .merge(a, b, {strategy}) / .diff(a, b)
                                 .delete(name) / .listBranches()
  SessionStore                 — bundles a tape + fork manager.
                                 .recordEvent / .fork / .switch
                                 .snapshot() / .fromSnapshot(snap)
                                 .autoFork(name) / .autoRestore(name)
  SessionSnapshot              — frozen serialisable view of events +
                                 branches.  .toDict / .fromDict
                                 .save(path) / .load(path)
  SessionPlugin                — ADK plugin that auto-forks after every
                                 agent via afterAgent callback

### reactor — reactive signals over the durable tape

Turns the durable tape into something agents can collaborate on: typed
state cells (signals), declarative triggers (predicates), priority
scheduling, and cooperative interrupts with a resume cursor::

    import { Signal, Reactor } from "adk-fluent-ts";
    const temp = new Signal("temp", 72.0).attach(bus);
    const r = new Reactor();
    r.when(temp.rising.where((v) => (v as number) > 90),
           alertOps, { priority: 10 });
    r.start();

  Signal                       — typed state cell. .get() / .set(v, {force})
                                 / .update(fn) / .version /
                                 .subscribe(fn) → unsubscribe /
                                 .attach(bus). Equal-to-current writes
                                 are no-ops unless ``force: true``.
  SignalPredicate              — declarative trigger. signal.changed /
                                 .rising / .falling / .is(value). Compose
                                 with ``a.and(b)``, ``a.or(b)``, ``a.not()``,
                                 ``.where(fn)``, ``.debounce(ms)``,
                                 ``.throttle(ms)``.
  Reactor                      — scheduler of (predicate, handler, options)
                                 rules. .when(pred, fn, {priority,
                                 preemptive, agentName}) / .start() /
                                 .stop(). Rules ordered by priority
                                 (lower wins).
  ReactorRule                  — frozen rule record returned by .when().
  AgentToken                   — per-agent cancellation token extending
                                 CancellationToken with ``agentName`` and
                                 ``resumeCursor``; cancelWithCursor(c)
                                 atomic cancel + resume record.
  TokenRegistry                — keyed container of AgentTokens; install()
                                 swaps live tokens while preserving in-flight
                                 closures; .cancel(name, {resumeCursor}),
                                 .reset(name) / .resetAll().
  WorkflowLifecyclePlugin      — ADK plugin that emits StepStarted/Completed,
                                 IterationStarted/Completed, BranchStarted/
                                 Completed, SubagentStarted/Completed, and
                                 AttemptFailed events for Pipeline/Loop/FanOut
                                 nodes.

### durable events (cross-cutting)

The same tape powers streaming replay, multi-consumer fanout, and
crash-safe audit. These entry points live on ``adk-fluent-ts`` directly
because they span session + helpers + harness events::

    for await (const chunk of streamFromCursor(builder, { cursor: 42 })) {
      console.log(chunk);
    }

  streamFromCursor(builder, {cursor})
                               — replay ``tape.since(cursor)`` text chunks
                                 then switch to live ``tape.tail()``. Lets
                                 a dropped SSE connection pick up where it
                                 left off without re-running the LLM.
  HarnessEvent subtypes         — SignalChanged, Interrupted, StepStarted,
                                 StepCompleted, IterationStarted,
                                 IterationCompleted, BranchStarted,
                                 BranchCompleted, SubagentStarted,
                                 SubagentCompleted, AttemptFailed. All
                                 frozen, recorded onto the tape via the
                                 event bus when plugins are wired.

### subagents — dynamic spawner + task tool

Runtime-decided specialist dispatch — the missing piece between
``.subAgent()`` (compile-time transfer) and ``.agentTool()`` (static
tool)::

    const registry = H.subagentRegistry([
      H.subagentSpec({
        role: "researcher",
        instruction: "Find three papers.",
        description: "Deep research",
      }),
      H.subagentSpec({
        role: "reviewer",
        instruction: "Critique the draft.",
      }),
    ]);
    const runner = new FakeSubagentRunner();
    const task   = H.taskTool(registry, runner);

  SubagentSpec                 — frozen role description (role,
                                 instruction, description, model,
                                 toolNames, permissionMode, maxTokens,
                                 metadata)
  SubagentRegistry             — dict-like keyed by role.
                                 .register / .unregister / .replace
                                 .get / .require / .roles() / .roster()
  SubagentResult               — structured output (role, output,
                                 isError, error, usage, metadata,
                                 artifacts); .toToolOutput()
  SubagentRunner               — Protocol: ``run(spec, prompt, ctx?)``
  FakeSubagentRunner           — test double with responder, error
                                 overrides, and a .calls audit log
  H.taskTool(registry, runner, {contextProvider, toolName})

### usage — cumulative token + cost tracking

Session-scoped usage accounting with per-agent breakdown and USD cost
via a frozen cost table::

    const table = H.costTable({ "gemini-2.5-pro": { input: 1.25, output: 5.00 } });
    const tracker = H.usage({ costTable: table });
    const plugin  = H.usagePlugin(tracker);

  TurnUsage                    — frozen per-call record (agent, model,
                                 inputTokens, outputTokens, cachedTokens,
                                 costUsd, timestamp)
  AgentUsage                   — frozen cumulative view for one agent
  ModelRate                    — frozen per-model pricing
  CostTable                    — frozen model → ModelRate lookup with
                                 .estimate(model, inTokens, outTokens)
  UsageTracker                 — mutable aggregator.
                                 .record(turn) / .callback() /
                                 .byAgent() / .summary()
  UsagePlugin                  — ADK plugin capturing every LLM call

### budget — cumulative token budget + thresholds

Enforces a session-wide token ceiling and fires callbacks at percent
checkpoints.  Designed to pair with ``ContextCompressor`` via
``compressor.toMonitor()``::

    const budget = H.budgetPolicy({ maxTokens: 200_000 })
      .addThreshold({ percent: 80, onTrigger: (m) => console.log("80%") })
      .addThreshold({ percent: 95, onTrigger: compactNow });
    const monitor = H.budgetMonitor(budget);
    const plugin  = H.budgetPlugin(monitor);

  Threshold                    — frozen {percent, onTrigger} checkpoint
  BudgetPolicy                 — frozen {maxTokens, thresholds}.
                                 .addThreshold({percent, onTrigger})
  BudgetMonitor                — mutable tracker.
                                 .recordUsage({input, output}) /
                                 .utilisation / .remaining /
                                 .isOverBudget / .summary() / .reset()
  BudgetPlugin                 — ADK plugin auto-wiring every LLM call

### compression — message-level compression with pre_compact hook

The message-rewriting half of context management.  ``C.*`` transforms
shape what the LLM sees on a single turn; ``ContextCompressor``
rewrites the persistent message history when it crosses a threshold::

    const strategy = CompressionStrategy.keepRecent({ n: 8 });
    let compressor = H.compressor({ threshold: 100_000, strategy });
    compressor = compressor.withHooks(hookRegistry); // pre_compact wired

  CompressionStrategy          — frozen description of *how* to compress.
                                 .dropOld({keepTurns}) / .keepRecent({n})
                                 .summarize({model})
  ContextCompressor            — the machine.
                                 .shouldCompress({currentTokens}) /
                                 .compressMessages(messages) /
                                 .compressMessagesAsync(msgs, {summarizer}) /
                                 .withHooks(registry) / .toMonitor()
                                 pre_compact hook: allow/deny/replace/modify

### fs — pluggable filesystem backend

Factors the workspace tools' filesystem calls behind a small Protocol
so tools can be unit-tested without a real disk and re-targeted at
in-memory or remote storage. See the
[fs](user-guide/fs.md) user-guide page for the full cookbook::

    const backend = new SandboxedBackend(new MemoryBackend(), sandbox);
    const tools   = workspaceTools({ sandbox, backend });

  FsBackend                    — interface: exists, stat, readText,
                                 readBytes, writeText, writeBytes,
                                 delete_, mkdir, listDir, iterFiles, glob
  FsStat                       — { path, size, isDir, isFile, mtime }
  FsEntry                      — { name, path, isDir, isFile } (per
                                 ``listDir`` result)
  LocalBackend                 — real on-disk I/O via Node ``fs``
  MemoryBackend(files?)        — dict-backed fake for tests + ephemeral
                                 scratch workspaces; POSIX semantics
                                 regardless of host OS.
  SandboxedBackend(inner, policy)
                               — decorator wrapping any backend with a
                                 SandboxPolicy; refuses escapes.
  SandboxViolation             — Error subclass raised when a path is
                                 rejected; workspace tool shims surface
                                 it as a "path outside workspace" string.
"""


# TypeScript-flavored best practices.  Mirrors ``_BEST_PRACTICES`` but uses
# camelCase method names where they differ from Python (e.g. ``subAgent``,
# ``agentTool``, ``loopWhile``, ``askAsync``/``mapAsync``).
_TS_BEST_PRACTICES = """
## Best practices

1. Use deterministic routing (Route) over LLM routing when the decision is rule-based
2. Use ``.inject()`` for infrastructure deps — never expose DB clients in tool schemas
3. Use S.transform() or plain functions for data transforms, not custom BaseAgent
4. Use C.none() to hide conversation history from background/utility agents
5. Use M.retry() middleware instead of retry logic inside tool functions
6. Use ``.writes()`` not deprecated ``.outputKey()`` / ``.outputs()``
7. Use ``.outputAs()`` not deprecated ``.outputSchema()``
8. Use ``.context()`` not deprecated ``.history()`` / ``.includeHistory()``
9. Use ``.agentTool()`` not deprecated ``.delegate()``
10. Use ``.guard()`` not deprecated ``.guardrail()``
11. Use ``.loopWhile()`` not deprecated ``.retryIf()``
12. Use ``.prepend()`` not deprecated ``.injectContext()``
13. All builders are immutable — sub-expressions can be safely reused
14. Workflow sub-builders passed to ``.then()`` / ``.parallel()`` / ``.step()``
    are auto-built; do not call ``.build()`` on individual steps
15. Use ``.subAgent()`` for transfer-based delegation (LLM decides routing);
    use ``.agentTool()`` for tool-based invocation (parent stays in control)
16. Use ``.isolate()`` on specialist agents by default — it is the most predictable pattern
17. Always set ``.describe()`` on sub-agents — the description helps the coordinator LLM
    pick the right specialist during transfer routing
18. Use ``.askAsync()`` / ``.mapAsync()`` in async code paths;
    the sync ``.ask()`` / ``.map()`` variants throw inside running event loops
"""


def generate_llms_txt_ts(specs: list[BuilderSpec]) -> str:
    """Generate the TypeScript-flavored llms.txt content."""
    groups = _group_builders_by_module(specs)

    sections = [
        _TS_HEADER,
        _TS_INSTALL,
        _TS_IMPORTS,
        _TS_OPERATORS,
        _TS_EXAMPLE,
        _TS_NAMESPACE_MODULES,
        _TS_HARNESS_PACKAGES,
        _format_builder_section(groups),
        _TS_BEST_PRACTICES,
        _TS_COMMANDS,
    ]
    return "\n".join(s.strip() for s in sections) + "\n"


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

# Targets written when ``--ts`` is supplied. The TypeScript llms.txt lives
# alongside the Python one but with a distinct filename so editors and
# documentation sites can offer them as separate language entry points.
TS_TARGETS: list[tuple[str, callable]] = [
    ("docs/llms-ts.txt", lambda c: c),
    ("ts/CLAUDE.md", _wrap_for_claude_md),
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
    parser.add_argument(
        "--ts",
        action="store_true",
        help="Also emit TypeScript-flavored llms.txt (docs/llms-ts.txt + ts/CLAUDE.md)",
    )
    parser.add_argument(
        "--ts-only",
        action="store_true",
        help="Only emit TypeScript-flavored llms.txt (skips Python targets)",
    )
    args = parser.parse_args()

    manifest = parse_manifest(args.manifest)
    seed = parse_seed(args.seed)
    specs = resolve_builder_specs(seed, manifest)

    content = generate_llms_txt(specs)
    root = Path(args.output_dir)

    written = 0
    if not args.ts_only:
        targets = TARGETS[:1] if args.llms_only else TARGETS
        for relpath, wrapper in targets:
            outpath = root / relpath
            outpath.parent.mkdir(parents=True, exist_ok=True)
            outpath.write_text(wrapper(content))
            print(f"  Generated {relpath}")
            written += 1

    if args.ts or args.ts_only:
        ts_content = generate_llms_txt_ts(specs)
        for relpath, wrapper in TS_TARGETS:
            outpath = root / relpath
            outpath.parent.mkdir(parents=True, exist_ok=True)
            outpath.write_text(wrapper(ts_content))
            print(f"  Generated {relpath}")
            written += 1

    print(f"\nGenerated {written} file(s) from {len(specs)} builder specs.")


if __name__ == "__main__":
    main()
