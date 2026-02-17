# ADK-FLUENT: Complete Specification v2

**Status:** Supersedes SPEC.md and SPEC_ADDENDUM.md  
**Architecture:** Scanner + Seed + Generator (codegen pipeline)  
**Position:** Community extension library for google-adk  

---

## 1. Executive Summary

adk-fluent is a fluent builder API for Google's Agent Development Kit that reduces agent creation from 22+ lines to 1-3 lines while maintaining 100% ADK CLI compatibility.

**What changed in v2:** The original spec described the API surface. The addendum solved the maintenance problem. This v2 spec adds the *machine* — a codegen pipeline that systematically scans ADK upstream and generates the entire fluent surface from two inputs:

```
seed.toml (human intent)  +  manifest.json (machine truth)  →  generated code
          ↑                         ↑                              ↓
   maintainer edits          scanner reads ADK           runtime .py + .pyi stubs + tests
   (~rarely)                 (~weekly, automated)         (zero manual effort)
```

**The maintenance cost of tracking ADK upstream: merge one auto-PR per release cycle.**

---

## 2. Architecture Overview

### 2.1 The Three-Layer System

```
┌─────────────────────────────────────────────────────────────────┐
│                        LAYER 1: TRUTH                           │
│                                                                 │
│  scanner.py reads installed google-adk via Pydantic             │
│  introspection (model_fields, get_type_hints, __mro__)          │
│                                                                 │
│  Output: manifest.json                                          │
│    - Every BaseModel class, field, type, default, validator     │
│    - Callback detection, list detection, inheritance chain      │
│    - Diff engine: detects added/removed fields between scans   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                        LAYER 2: INTENT                          │
│                                                                 │
│  seed.toml is the ONLY file a human edits                       │
│                                                                 │
│  Defines:                                                       │
│    - Which ADK classes get builders                              │
│    - Ergonomic aliases (instruction → instruct)                 │
│    - Field behaviors (set, append, extend, skip)                │
│    - Constructor signatures                                     │
│    - Terminal methods (build, ask, run)                          │
│    - Extra methods (step, branch, member, apply)                │
│    - Documentation overrides                                    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                       LAYER 3: CODEGEN                          │
│                                                                 │
│  generator.py merges manifest + seed → output                   │
│                                                                 │
│  Produces:                                                      │
│    - Runtime .py   (builders with __getattr__ forwarding)       │
│    - Type .pyi     (full IDE autocomplete, pyright-strict)      │
│    - Test scaffolds (equivalence tests per builder)             │
│    - __init__.py   (re-exports for clean public API)            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Why This Architecture

The fundamental problem: ADK ships bi-weekly. `LlmAgent` has ~25 Pydantic fields today. Each release can add fields. A manually-maintained wrapper library creates a perpetual treadmill — every upstream field addition creates a gap.

The solution exploits ADK's own architectural decision: **everything is Pydantic BaseModel**, which means `LlmAgent.model_fields` is a runtime-introspectable schema. The wrapper doesn't enumerate what it wraps — it delegates through introspection.

**Principle: the source of truth is the thing being wrapped, not the wrapper.**

This is the same pattern behind:
- SQLAlchemy: reads DB schema → generates accessors
- Django REST Framework: reads model fields → generates serializers
- numpy/pandas: C runtime + .pyi stubs for DX

### 2.3 What Humans Edit vs What Machines Generate

| Artifact | Created By | Edited By | When |
|---|---|---|---|
| `seed.toml` | Human (once) | Human (rarely) | When adding aliases, new builders, or behaviors |
| `manifest.json` | Scanner (automated) | Never | Every scan (weekly CI) |
| `src/adk_fluent/*.py` | Generator | Never | Every generation run |
| `src/adk_fluent/*.pyi` | Generator | Never | Every generation run |
| `tests/generated/*` | Generator | Never | Every generation run |
| `tests/manual/*` | Human | Human | For edge cases the generator can't cover |

---

## 3. The Scanner (`scripts/scanner.py`)

### 3.1 What It Does

Introspects the installed `google-adk` package and produces a `manifest.json` describing every Pydantic BaseModel class in the ADK public API.

### 3.2 Scan Targets

```python
SCAN_TARGETS = [
    ("google.adk.agents",    ["BaseAgent", "LlmAgent", "SequentialAgent",
                               "ParallelAgent", "LoopAgent", "RunConfig"]),
    ("google.adk.apps",      ["App", "ResumabilityConfig"]),
    ("google.adk.runners",   ["Runner"]),
    ("google.adk.artifacts", ["BaseArtifactService", "InMemoryArtifactService", ...]),
    ("google.adk.sessions",  ["InMemorySessionService"]),
    ("google.adk.tools.*",   ["BaseTool", "FunctionTool"]),
    ("google.adk.events",    ["Event"]),
]
```

### 3.3 Per-Class Extraction

For each class, the scanner extracts:

| Data | Source | Purpose |
|---|---|---|
| Field names | `cls.model_fields.keys()` | Method names for stubs |
| Field types | `get_type_hints(cls)` | Type annotations for stubs |
| Field defaults | `field_info.default` | Whether field is required |
| Field descriptions | `field_info.description` | Docstrings for generated methods |
| Is callback? | Heuristic: `Callable` in type | Identify additive fields |
| Is list? | Heuristic: `list[` prefix | Identify extend fields |
| Inherited from? | Walk `__mro__` | Track field origin |
| Validators | `__validators__` | Document constraints |
| Own vs inherited | Compare against parent `model_fields` | Minimize redundant generation |

### 3.4 Manifest Format

```json
{
  "adk_version": "1.25.0",
  "scan_timestamp": "2026-02-17T08:00:00Z",
  "python_version": "3.12.5",
  "total_classes": 12,
  "total_fields": 87,
  "total_callbacks": 14,
  "classes": [
    {
      "name": "LlmAgent",
      "qualname": "google.adk.agents.LlmAgent",
      "module": "google.adk.agents",
      "is_pydantic": true,
      "bases": ["BaseAgent"],
      "mro": ["LlmAgent", "BaseAgent", "BaseModel"],
      "fields": [
        {
          "name": "instruction",
          "type_str": "str | Callable",
          "default": "None",
          "required": false,
          "is_callback": false,
          "is_list": false,
          "description": "The agent instruction.",
          "inherited_from": null
        }
      ],
      "own_fields": ["model", "instruction", "tools", ...],
      "methods": ["canonical_instruction", "canonical_tools", ...]
    }
  ]
}
```

### 3.5 Diff Engine

```bash
# Compare current ADK against last known scan
python scripts/scanner.py --diff manifest.previous.json
```

Output:
```json
{
  "adk_version_old": "1.24.0",
  "adk_version_new": "1.25.0",
  "added_classes": [],
  "removed_classes": [],
  "field_changes": {
    "LlmAgent": {
      "added_fields": ["safety_config", "context_compression"],
      "removed_fields": []
    }
  },
  "breaking": false
}
```

---

## 4. The Seed (`seeds/seed.toml`)

### 4.1 Philosophy

The seed encodes **human ergonomic intent** — decisions a machine can't make:
- Should `instruction` be aliased to `instruct`? (Yes — better verb form)
- Should `before_model_callback` be additive or replace? (Additive — accumulate)
- Should `parent_agent` be exposed? (No — managed internally)
- What terminal methods should exist? (`build`, `ask`, `run`)

These are taste decisions. They change rarely. The seed is the only file a maintainer needs to touch.

### 4.2 Structure

```toml
[meta]
adk_package = "google-adk"
min_adk_version = "1.20.0"

[global]
# Fields NEVER exposed (across all builders)
skip_fields = ["parent_agent", "model_config", "model_fields"]

# Callback fields that use APPEND semantics
additive_fields = [
    "before_agent_callback", "after_agent_callback",
    "before_model_callback", "after_model_callback",
    "before_tool_callback", "after_tool_callback",
]

[builders.Agent]
source_class = "google.adk.agents.LlmAgent"
constructor_args = ["name", "model"]

[builders.Agent.aliases]
instruct = "instruction"       # .instruct() reads better than .instruction()
describe = "description"       # .describe() reads better than .description()

[builders.Agent.callback_aliases]
before_model = "before_model_callback"   # .before_model(fn) appends
after_model = "after_model_callback"

[[builders.Agent.terminals]]
name = "build"
returns = "LlmAgent"

[[builders.Agent.terminals]]
name = "ask"
signature = "(self, query: str, *, user_id: str = 'default') -> str"
```

### 4.3 Seed Modification Scenarios

| Scenario | Seed Change | Generator Impact |
|---|---|---|
| ADK adds `safety_config` field | **Nothing** — `__getattr__` handles it, stubs auto-regenerate | Auto-PR with updated `.pyi` |
| You want `.safe(config)` alias | Add `safe = "safety_config"` to `[builders.Agent.aliases]` | Regenerate: new explicit method + stub |
| ADK adds new callback field | Add to `[global] additive_fields` | Regenerate: proper append semantics |
| ADK adds new agent type `PlannerAgent` | Add new `[builders.Planner]` section | Regenerate: new builder class |
| ADK removes a field | **Nothing** — scanner detects, diff reports, tests fail naturally | Fix tests, release |
| ADK renames a field | Update alias if needed | Regenerate |

### 4.4 Builder Types

The seed supports four source types:

| Source Type | Example | Pydantic Introspection | `__getattr__` |
|---|---|---|---|
| ADK BaseModel | `google.adk.agents.LlmAgent` | Yes | Yes |
| `__composite__` | Runtime (Runner + services) | No | No |
| `__standalone__` | MiddlewareStack | No | No |

---

## 5. The Generator (`scripts/generator.py`)

### 5.1 What It Produces

For each builder defined in the seed:

**Runtime `.py` file:**
- Alias constants (`_ALIASES`, `_CALLBACK_ALIASES`, `_ADDITIVE_FIELDS`)
- Builder class with `__init__`, alias methods, callback methods, extra methods
- `__getattr__` forwarding validated against `SourceClass.model_fields`
- `build()` terminal that resolves to native ADK constructor

**Type stub `.pyi` file:**
- Full method signatures with proper types from manifest
- Covers aliases + callbacks + every non-skipped Pydantic field
- Enables IDE autocomplete and pyright/mypy strict mode

**Test scaffold `.py` file:**
- Equivalence tests: fluent chain produces same object as native construction
- Alias tests: `.instruct("x")` sets `instruction = "x"`
- `__getattr__` tests: forwarded fields work correctly
- Callback accumulation tests: multiple `.before_model()` calls stack
- Typo detection tests: misspelled methods raise clear `AttributeError`

### 5.2 Generated Runtime Pattern

```python
# AUTO-GENERATED — do not edit manually

from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable, Self
from google.adk.agents import LlmAgent

_ALIASES = {"instruct": "instruction", "describe": "description"}
_CALLBACK_ALIASES = {"before_model": "before_model_callback", ...}
_ADDITIVE_FIELDS = {"before_model_callback", "after_model_callback", ...}

class Agent:
    """Fluent builder for LlmAgent."""
    
    def __init__(self, name: str, model: str) -> None:
        self._config: dict[str, Any] = {"name": name, "model": model}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._lists: dict[str, list] = defaultdict(list)
    
    # --- Ergonomic aliases (generated from seed.toml) ---
    def instruct(self, value: str | Callable) -> Self:
        self._config["instruction"] = value
        return self
    
    # --- Callback methods (generated from seed.toml) ---
    def before_model(self, fn: Callable) -> Self:
        self._callbacks["before_model_callback"].append(fn)
        return self
    
    # --- Dynamic forwarding (generated, reads schema at runtime) ---
    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        field_name = _ALIASES.get(name, name)
        if field_name not in LlmAgent.model_fields:
            available = sorted(set(LlmAgent.model_fields.keys()) | ...)
            raise AttributeError(f"'{name}' is not a recognized field. Available: ...")
        def _setter(value: Any) -> Self:
            self._config[field_name] = value
            return self
        return _setter
    
    # --- Terminal (generated from seed.toml) ---
    def build(self) -> LlmAgent:
        config = {**self._config}
        for field, fns in self._callbacks.items():
            config[field] = fns if len(fns) > 1 else fns[0]
        for field, items in self._lists.items():
            config[field] = config.get(field, []) + items
        return LlmAgent(**config)
```

### 5.3 Generated Stub Pattern

```python
# AUTO-GENERATED — from google-adk 1.25.0
from typing import Any, Callable, Self
from google.adk.agents import LlmAgent

class Agent:
    def __init__(self, name: str, model: str) -> None: ...
    def instruct(self, value: str | Callable) -> Self: ...
    def describe(self, value: str) -> Self: ...
    def before_model(self, fn: Callable) -> Self: ...
    def after_model(self, fn: Callable) -> Self: ...
    # --- Every LlmAgent field, auto-generated from manifest ---
    def tools(self, value: list) -> Self: ...
    def output_key(self, value: str) -> Self: ...
    def output_schema(self, value: type) -> Self: ...
    def planner(self, value: BasePlanner) -> Self: ...
    def code_executor(self, value: BaseCodeExecutor) -> Self: ...
    def generate_content_config(self, value: GenerateContentConfig) -> Self: ...
    # ... every other field from manifest.json
    def build(self) -> LlmAgent: ...
    def ask(self, query: str, *, user_id: str = ...) -> str: ...
```

---

## 6. Fluent API Surface (Unchanged from v1)

The user-facing API is identical to the original spec. What changes is *how it's built*.

### Level 0 — One-Shot
```python
from adk_fluent import Agent
response = Agent("helper", "gemini-2.5-flash").ask("What is the capital of France?")
```

### Level 1 — Tools and Configuration
```python
agent = (
    Agent("assistant", "gemini-2.5-flash")
    .instruct("You help with weather and news.")
    .tools([get_weather, get_news])
    .output_key("response")
    .build()
)
```

### Level 2 — Composable Middleware
```python
agent = (
    Agent("secure_agent", MODEL)
    .before_model(log_request)
    .before_model(enforce_pii_guardrail)
    .after_tool(audit_tool_calls)
    .build()
)
```

### Level 3 — Workflow Composition
```python
pipeline = (
    Pipeline("CodePipeline")
    .step(Agent("Writer", MODEL).instruct("Write code").output_key("code"))
    .step(Agent("Reviewer", MODEL).instruct("Review {code}").output_key("review"))
    .step(Agent("Refactorer", MODEL).instruct("Fix {code} per {review}"))
    .build()
)
```

### Level 4 — Team Coordination
```python
helpdesk = (
    Team("HelpDesk", MODEL)
    .instruct("Route requests to specialists.")
    .member(Agent("Billing", MODEL).describe("Handles billing").tools([...]))
    .member(Agent("TechSupport", MODEL).describe("Handles tech").tools([...]))
    .build()
)
```

### Level 5 — Production Runtime
```python
app = (
    Runtime("my_app")
    .agent(helpdesk.build())
    .session_service(VertexAiSessionService(...))
    .memory_service(VertexAiMemoryBankService(...))
    .plugin(BigQueryAnalyticsPlugin(...))
    .build_app()
)
```

---

## 7. Development Workflow

### 7.1 Local Development

```bash
# First-time setup
pip install google-adk tomli pyright pytest
git clone <repo> && cd adk-fluent

# The full pipeline (30 seconds)
make all          # scan ADK → manifest.json → generate code + stubs + tests

# After editing seed.toml
make generate     # re-run generator with existing manifest
make test         # verify everything works
make typecheck    # verify stubs pass pyright

# Just regenerate stubs (fastest)
make stubs

# See what changed in ADK since last scan
make diff
```

### 7.2 CI/CD Pipeline

```
Monday 8:00 UTC (weekly cron)
    │
    ├─ Install latest google-adk
    ├─ Run scanner → manifest.json
    ├─ Diff against manifest.previous.json
    ├─ Run generator → code + stubs + tests
    ├─ Run pyright on stubs
    ├─ Run pytest (equivalence tests)
    │
    ├─ If stubs changed:
    │   └─ Create auto-PR: "chore: sync with google-adk X.Y.Z"
    │
    └─ If tests fail:
        └─ Create issue: "BREAKING: google-adk X.Y.Z changes detected"
```

### 7.3 Maintainer Decision Tree

```
ADK releases new version
    │
    ├─ Auto-PR created (stubs updated)
    │   ├─ Tests pass? → Merge (30 seconds of work)
    │   └─ Tests fail? → Investigate:
    │       ├─ Field removed? → Update seed.toml, remove references
    │       ├─ Field renamed? → Update alias in seed.toml
    │       ├─ Callback semantics changed? → Update additive_fields
    │       └─ New agent type? → Add new builder section to seed.toml
    │
    └─ No PR created → No changes needed (zero work)
```

---

## 8. Project Structure

```
adk-fluent/
├── seeds/
│   └── seed.toml                      # Human intent (THE file you edit)
│
├── scripts/
│   ├── scanner.py                     # Introspects ADK → manifest.json
│   └── generator.py                   # seed.toml + manifest.json → code
│
├── src/adk_fluent/                    # GENERATED — do not edit
│   ├── __init__.py                    # Re-exports all builders
│   ├── agent.py                       # Agent builder (wraps LlmAgent)
│   ├── agent.pyi                      # Type stubs for Agent
│   ├── workflow.py                    # Pipeline, FanOut, Loop builders
│   ├── workflow.pyi                   # Type stubs for workflows
│   ├── multi.py                       # Team builder
│   ├── multi.pyi                      # Type stubs for Team
│   ├── runtime.py                     # Runtime builder (hand-written)
│   ├── runtime.pyi                    # Type stubs for Runtime
│   └── middleware.py                  # MiddlewareStack (hand-written)
│
├── tests/
│   ├── generated/                     # GENERATED — equivalence tests
│   │   ├── test_agent_builder.py
│   │   ├── test_workflow_builder.py
│   │   └── test_multi_builder.py
│   └── manual/                        # Hand-written edge case tests
│       ├── test_ask_oneshot.py
│       ├── test_adk_cli_compat.py
│       └── test_native_mixing.py
│
├── manifest.json                      # Latest scan output (committed)
├── manifest.previous.json             # Previous scan (for diffing)
├── Makefile                           # Local dev commands
├── pyproject.toml                     # Package config
│
├── .github/workflows/
│   └── sync-adk.yml                   # Weekly scan + auto-PR
│
└── docs/
    └── SPEC_v2.md                     # This document
```

---

## 9. Maintenance Ledger

| Component | How Maintained | Effort per ADK Release |
|---|---|---|
| `seed.toml` | Human edits when taste changes | **Near zero** (stable) |
| `scanner.py` | Only if ADK changes introspection API | **Zero** (Pydantic is stable) |
| `generator.py` | Only if codegen templates need improvement | **Zero** (templates are stable) |
| `manifest.json` | Auto-generated weekly | **Zero** |
| `src/adk_fluent/*.py` | Auto-generated | **Zero** |
| `src/adk_fluent/*.pyi` | Auto-generated | **Zero** |
| `tests/generated/*` | Auto-generated | **Zero** |
| Overall per release | Merge one auto-PR | **~30 seconds** |

---

## 10. Design Decisions Log

### Why `__getattr__` + `.pyi` stubs (not metaclass, not explicit methods)?

- **`__getattr__`**: Zero-maintenance runtime. New ADK fields work instantly.
- **`.pyi` stubs**: Full IDE autocomplete and type-checker support.
- **Metaclass**: Generates real methods but still needs `.pyi` for full type annotations. Added complexity for marginal benefit.
- **Explicit methods**: The enumeration trap. O(N) maintenance cost per ADK release.

### Why TOML for the seed (not YAML, not Python)?

- TOML has typed values (strings, lists, tables) without YAML's implicit typing gotchas
- Python 3.11+ includes `tomllib` in stdlib — zero dependencies
- Simpler than a Python DSL — the seed should be declarative, not imperative

### Why not generate from ADK's JSON schema (model_json_schema)?

- JSON schema loses Python-specific type information (Callable types become `null`)
- `model_fields` + `get_type_hints` give richer data than JSON schema
- Direct Python introspection is more reliable than serialized schema

### Why commit manifest.json?

- Enables `make diff` without re-scanning
- Enables CI to detect changes between runs
- Provides a human-readable audit trail of what ADK looked like at each release

---

## 11. Success Metrics (Unchanged)

| Metric | Target |
|---|---|
| Lines-to-first-response | ≤ 3 lines (vs 22 today) |
| Time-to-first-demo | ≤ 5 minutes (vs 20 today) |
| ADK CLI compatibility | 100% |
| Type-check pass rate | 100% strict |
| Maintenance per ADK release | ≤ 1 auto-PR merge |
| Time from ADK release to stub update | ≤ 7 days (weekly CI) |

---

## 12. Versioning

| adk-fluent | google-adk | Notes |
|---|---|---|
| 0.1.x | >= 1.20.0 | Initial release, codegen pipeline |
| 0.2.x | >= 1.22.0 | Streaming support, live API |
| 1.0.0 | >= 2.0.0 | Stable API, post ADK 2.0 |

SemVer rules:
- **MAJOR**: Breaking changes to fluent API surface *or* seed.toml format
- **MINOR**: New builders, new seed features, new terminal methods
- **PATCH**: Stub regeneration, bug fixes, generator improvements
