# Namespace & Telemetry Architecture Document

> Principal Systems Architecture Audit — adk-fluent v0.x
> Date: 2026-03-15

---

## Executive Summary

After a line-by-line cross-examination of both the Google ADK source
(`google.adk.telemetry.*`, `google.adk.plugins.*`) and the adk-fluent
wrapper (`_middleware.py`, `middleware.py`, `_eval.py`, `_guards.py`,
plugin.py, and all 8 namespace modules), this document delivers three
definitive architectural positions:

1. **Observability: DO NOT build a namespace.** Get out of the way.
2. **Namespace taxonomy: 6 of 8 letter-namespaces are well-placed.** Two need attention.
3. **Sleeping giants: E (Evals) and G (Guards) are the highest-ROI expansion targets.** M (Middleware) is mature.

---

## Phase 1: The Observability Verdict

### How ADK Handles Telemetry Natively

ADK has a **deeply integrated, production-grade OpenTelemetry stack** in
`google.adk.telemetry`. Key facts:

| Mechanism | Location | What It Does |
|-----------|----------|--------------|
| `telemetry.tracing` | `google.adk.telemetry.tracing` | Full OTel span creation for agent invocations, LLM calls, tool calls. Uses semantic conventions (`gen_ai.*`, `gcp.vertex.agent.*`). |
| `telemetry.setup` | `google.adk.telemetry.setup` | `maybe_set_otel_providers()` — auto-configures TracerProvider, MeterProvider, LoggerProvider from `OTEL_EXPORTER_OTLP_*` env vars. |
| `telemetry.google_cloud` | `google.adk.telemetry.google_cloud` | `get_gcp_exporters()` — one-call setup for Cloud Trace, Cloud Monitoring, Cloud Logging with GCP credentials. |
| Plugin system | `google.adk.plugins.base_plugin` | 12 lifecycle callbacks (before/after agent/model/tool, on_event, before/after run, on_model_error, on_tool_error). Plugins run globally across all agents. |
| Built-in plugins | `debug_logging_plugin`, `logging_plugin`, `bigquery_agent_analytics_plugin` | Production logging, BQ analytics, debug capture — all plugin-based. |
| Env var controls | `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS`, `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | PII-safe span content elision, standard OTel env vars for exporter endpoints. |
| 3P integration | `opentelemetry-instrumentation-google-genai` | ADK auto-detects if this package wraps `Models.generate_content` and delegates span creation. |

**The critical insight:** ADK's telemetry is **not** configured through
constructor arguments or method chains. It uses:

1. **Global OTel provider setup** (env vars or one-time `maybe_set_otel_providers()` call)
2. **Plugin registration on the Runner** (`Runner(plugins=[...])`)
3. **Automatic span creation** inside `base_agent.py` and `base_llm_flow.py`

### The Decision: adk-fluent Should Do (Almost) Nothing

**Recommendation: NO dedicated observability namespace.** No `O` module. No
`adk_fluent.observability` package.

**Rationale:**

1. **Wrapping creates friction, not value.** ADK's telemetry is environment-level
   configuration. A fluent chain like `.observe_with(arize)` would need to
   somehow inject itself into global OTel providers — the exact anti-pattern
   that fluent APIs shouldn't touch. The user would still need to understand
   OTel providers, exporters, and the ADK plugin lifecycle.

2. **The 50-line test fails.** Setting up GCP observability in raw ADK:

   ```python
   from google.adk.telemetry.google_cloud import get_gcp_exporters
   from google.adk.telemetry.setup import maybe_set_otel_providers

   maybe_set_otel_providers([get_gcp_exporters(
       enable_cloud_tracing=True,
       enable_cloud_metrics=True,
   )])
   ```

   That's 5 lines. A fluent wrapper cannot meaningfully compress this.
   For OTLP exporters, it's literally `OTEL_EXPORTER_OTLP_ENDPOINT=http://...`
   — a single env var.

3. **ADK's plugin system is already the observability surface.** The
   `BasePlugin` callbacks (`before_agent_callback`, `after_model_callback`,
   etc.) are the correct integration points for Arize, LangSmith, etc.
   These belong on the Runner, not on individual agents.

### What adk-fluent SHOULD Keep

The existing `M.trace()`, `M.log()`, `M.cost()`, `M.latency()` middleware
is **correctly scoped** and should stay. These are:

- **Agent-level** observability (per-agent latency, per-agent cost)
- **Composable** via the `|` operator
- **Scoped** via `M.scope("agent_name", M.cost())`
- **Lightweight** — they don't replace ADK's global telemetry; they augment it

### Recommended User Experience

```python
# ---- Global telemetry: use ADK directly (one-time setup) ----
from google.adk.telemetry.google_cloud import get_gcp_exporters
from google.adk.telemetry.setup import maybe_set_otel_providers

maybe_set_otel_providers([get_gcp_exporters(enable_cloud_tracing=True)])

# ---- Agent-level observability: use M namespace ----
from adk_fluent import Agent, Pipeline, M

pipeline = (
    Pipeline("flow")
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write."))
    .step(Agent("reviewer", "gemini-2.5-flash").instruct("Review."))
    .middleware(M.cost() | M.latency() | M.log())
    .build()
)

# ---- Runner-level plugins: use ADK's plugin system ----
from google.adk.plugins.logging_plugin import LoggingPlugin
from adk_fluent import Runner

runner = (
    Runner(session_service)
    .agent(pipeline)
    .plugins([LoggingPlugin()])
    .build()
)
```

**The rule:** adk-fluent wraps what lives on the agent/pipeline. ADK
handles what lives on the runtime/environment. The boundary is clean.

---

## Phase 2: The Namespace Purge & Promotion

### Current Namespace Map

| Namespace | Module | Lines | Status | Verdict |
|-----------|--------|-------|--------|---------|
| **S** — State transforms | `_transforms.py` | 795 | Mature | KEEP |
| **C** — Context engineering | `_context.py` + `_context_providers.py` | 2,532 | Mature | KEEP |
| **P** — Prompt composition | `_prompt.py` | 1,127 | Mature | KEEP |
| **A** — Artifacts | `_artifacts.py` | 795 | Mature | KEEP |
| **M** — Middleware | `_middleware.py` + `middleware.py` | 1,590 | Mature | KEEP |
| **T** — Tool composition | `_tools.py` | 410 | Lean but complete | KEEP |
| **E** — Evaluation | `_eval.py` | 1,263 | Substantial, real ADK integration | PROMOTE (sleeping giant) |
| **G** — Guards | `_guards.py` | 667 | Well-designed, partially wired | PROMOTE (sleeping giant) |

### What SHOULD NOT become a namespace

| Candidate | Why Not |
|-----------|---------|
| Observability / Telemetry | Global config, not agent-level composition (see Phase 1) |
| Memory | Already covered by `.memory()` agent method + service builders. Not a composition domain. |
| Routing | `Route` is an expression primitive, not a composition namespace. It's correctly placed in `_routing.py`. |
| Configuration | `config.py` is auto-generated builders for ADK config dataclasses. It's a reference API, not a DSL. |
| Plugins | `plugin.py` is auto-generated builders. Plugins go on the Runner, not a composition chain. |

### What IS misplaced

1. **`testing/` should be importable as `adk_fluent.testing`** — it already
   is, but it's not documented in CLAUDE.md or the namespace table. The
   `contracts`, `diagnosis`, `harness`, and `mock_backend` modules are
   substantial (1,558 lines total) and represent a distinct testing domain.

2. **`_helpers.py` (804 lines) contains execution methods** (`.ask()`,
   `.stream()`, `.session()`, `.mock()`, `.test()`, `.eval()`, `.map()`) that
   are mixed into the Agent builder via `_HelpersMixin`. This is correct
   architecturally — they're builder methods, not a separate namespace.

### Proposed Directory Tree (No Changes Needed)

```
src/adk_fluent/
├── __init__.py              # Public API surface (804 lines)
├── agent.py                 # Agent builder (auto-generated + hand-mixed)
├── _base.py                 # BuilderBase, callback composition
├── _transforms.py           # S namespace
├── _context.py              # C namespace (spec layer)
├── _context_providers.py    # C namespace (provider implementations)
├── _prompt.py               # P namespace
├── _artifacts.py            # A namespace
├── _middleware.py            # M namespace (surface)
├── middleware.py             # M namespace (implementations)
├── _tools.py                # T namespace
├── _eval.py                 # E namespace
├── _guards.py               # G namespace
├── _primitives.py           # Expression primitives (tap, gate, race, etc.)
├── _routing.py              # Route builder
├── _ir.py / _ir_generated.py  # Intermediate representation
├── backends/                # ADK backend compiler
├── testing/                 # Test harness, contracts, diagnosis, mocks
├── config.py                # Auto-generated config builders
├── plugin.py                # Auto-generated plugin builders
├── runtime.py               # Auto-generated runtime builders (App, Runner)
├── service.py               # Auto-generated service builders
├── tool.py                  # Auto-generated tool builders
├── workflow.py              # Auto-generated workflow builders (Pipeline, FanOut, Loop)
├── patterns.py              # Higher-order composition patterns
├── presets.py               # Preset configurations
├── stream.py                # Streaming utilities
├── viz.py                   # Mermaid visualization
├── di.py                    # Dependency injection
├── decorators.py            # @agent decorator
├── prelude.py               # Convenience re-exports
├── cli.py                   # CLI entry point
└── source.py                # Source utilities
```

**Verdict: The current structure is sound.** The 8 letter-namespaces
(S, C, P, A, M, T, E, G) each represent a distinct composition domain.
No namespace needs to be added, removed, or merged.

---

## Phase 3: The Sleeping Giants

### Giant #1: E (Evaluation) — The Quality Assurance Engine

**Current state:** 1,263 lines of real, working code with deep ADK integration.
Already implements:

- `E.trajectory()`, `E.response_match()`, `E.semantic_match()`,
  `E.hallucination()`, `E.safety()`, `E.rubric()`, `E.tool_rubric()`,
  `E.custom()` — criteria composition with `|`
- `E.suite(agent).case(...).criteria(...).run()` — full eval suite runner
- `E.compare(agent_a, agent_b)` — side-by-side model comparison
- `E.persona.expert()` / `.novice()` / `.evaluator()` — user simulation
- `E.scenario()` — conversation scenario builder
- `E.gate()` — quality gates for pipelines (`agent >> E.gate(...) >> next`)
- `E.from_file()` / `E.from_dir()` — file-based eval loading

**What makes this a sleeping giant:** The fluent API is already there. What's
missing is **awareness and integration depth**. Two specific expansion points:

#### 1. Agent-level `.eval()` method that returns structured results

Currently `.eval()` exists on the agent builder but its integration with
the E namespace could be tighter. The magic:

```python
# Today: separate suite construction
report = await (
    E.suite(agent)
    .case("What is 2+2?", expect="4")
    .case("Search for news", tools=[("google_search", {"query": "news"})])
    .criteria(E.trajectory() | E.response_match(0.8))
    .run()
)
assert report.ok

# The magic already exists but few users know about it:
report = await (
    E.compare(
        Agent("fast", "gemini-2.5-flash").instruct("Answer concisely."),
        Agent("smart", "gemini-2.5-pro").instruct("Answer thoroughly."),
    )
    .case("Explain quantum computing", expect="superposition and entanglement")
    .criteria(E.semantic_match() | E.hallucination())
    .run()
)
print(report.summary())     # Formatted comparison table
print(report.winner)        # "smart"
best_agents = report.ranked()  # Sorted by composite score
```

#### 2. Pipeline quality gates (already implemented!)

```python
# Quality gate in a pipeline — blocks propagation if quality drops
pipeline = (
    Agent("writer", "gemini-2.5-flash").instruct("Write an article.")
    >> E.gate(E.hallucination(0.8))  # Must be 80% grounded
    >> Agent("editor", "gemini-2.5-flash").instruct("Polish the article.")
)
```

**ROI assessment:** E is 90% built. The remaining 10% is documentation,
cookbook examples, and making `E.gate()` actually enforce the quality
threshold at runtime (currently it sets state flags but doesn't block).

---

### Giant #2: G (Guards) — The Safety Rail System

**Current state:** 667 lines with a well-designed composition model.
Implements:

- **Structural guards:** `G.json()`, `G.length(min=, max=)`, `G.regex()`,
  `G.output(Schema)`, `G.input(Schema)`
- **Policy guards:** `G.budget(max_tokens)`, `G.rate_limit(rpm)`, `G.max_turns(n)`
- **Content safety:** `G.pii("redact")`, `G.toxicity()`, `G.topic(deny=[...])`,
  `G.grounded()`, `G.hallucination()`
- **Providers:** `G.dlp(project)` (Google Cloud DLP), `G.regex_detector()`,
  `G.multi(*detectors)`, `G.custom(fn)`
- **Conditional:** `G.when(predicate, guard)`
- **Composition:** `G.pii("redact") | G.budget(5000) | G.output(Schema)`

**What makes this a sleeping giant:** The guard specs compile into callback
tuples on the agent builder, but the **runtime enforcement layer** is
thin. The `_LLMJudge` for toxicity and hallucination is a placeholder
(`always passes`). The PII regex detector works. The structural guards
(json, length, regex) work through callback registration.

#### The magic that's waiting to happen:

```python
from adk_fluent import Agent, G

# Production safety rails in one chain
agent = (
    Agent("customer_support", "gemini-2.5-flash")
    .instruct("Help customers with their orders.")
    .guard(
        G.pii("redact", detector=G.dlp("my-gcp-project"))
        | G.toxicity(0.8)
        | G.budget(10_000)
        | G.max_turns(20)
        | G.topic(deny=["competitor_products", "internal_pricing"])
    )
    .build()
)

# Conditional guards based on user tier
agent = (
    Agent("advisor", "gemini-2.5-pro")
    .instruct("Provide financial advice.")
    .guard(
        G.pii("redact")
        | G.when(
            lambda state: state.get("user_tier") == "free",
            G.budget(1_000) | G.max_turns(5)
        )
    )
    .build()
)
```

**ROI assessment:** G is 70% built. The remaining 30% is:

1. Wire `_LLMJudge` to actually call Gemini for toxicity/hallucination scoring
2. Runtime enforcement in the ADK backend (currently guards compile to callback
   tuples but the backend doesn't fully resolve them into ADK callbacks)
3. Guard violation reporting (the `GuardViolation` exception exists but
   the reporting chain needs completion)

---

### Honorable Mention: M (Middleware) — Already Mature

M is not a sleeping giant — it's awake and working. 1,590 lines across
two files with 15+ built-in middleware types, scoping, conditional
application, and a full plugin bridge to ADK's runtime. The composition
model (`M.retry(3) | M.log() | M.cost()`) is the template that E and G
should aspire to match in runtime completeness.

---

## Summary of Recommendations

| Decision | Recommendation | Action Required |
|----------|---------------|-----------------|
| Observability namespace | **DO NOT BUILD** | None — keep M.trace/log/cost/latency as-is |
| Namespace taxonomy | **No changes needed** | Document `testing/` in CLAUDE.md |
| E (Evaluation) | **Promote to first-class** | Complete E.gate() runtime enforcement, add cookbook examples |
| G (Guards) | **Promote to first-class** | Wire LLMJudge, complete backend compilation, add cookbook examples |
| New namespaces | **None** | The 8-letter taxonomy (S,C,P,A,M,T,E,G) is complete |

### The One Rule

> **If the user needs to understand ADK internals to use the wrapper,
> the wrapper has failed. If the wrapper hides ADK capabilities the user
> needs, the wrapper has also failed.**

Observability lives in the second failure mode — wrapping it would hide
the power of ADK's native OTel integration. E and G live in the first
success mode — they compress 50+ lines of ADK evaluation/guard boilerplate
into composable one-liners that produce real ADK objects.
