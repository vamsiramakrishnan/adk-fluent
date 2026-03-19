# Dependency Bloat Analysis: adk-fluent

**Author:** Performance Engineering
**Date:** 2026-03-16
**Scope:** Production install path (`pip install adk-fluent`) — dev/docs extras excluded
**Tools used:** memray 1.19.2, tracemalloc (stdlib), `python3 -X importtime`

___

## Executive Summary

A single `pip install adk-fluent` pulls in **122 packages totaling 431 MB on disk**.
Importing the library allocates **181 MB peak RAM** and loads **3,140 Python modules**.
For a user building a simple Gemini agent, **94% of that is waste** — they need 25 MB
across 22 packages but pay for 431 MB across 122.

This is both a **storage problem** (container images, CI caches, lambda layers) and a
**memory problem** (cold start latency, serverless per-instance cost, OOM on small VMs).
The import alone consumes **47% of a Cloud Run cold start budget** (4.7s of ~10s).

The bloat is not caused by adk-fluent. It is caused by `google-adk` shipping every GCP
service client, every observability exporter, and `pyarrow` as **hard dependencies**
instead of optional extras. adk-fluent amplifies the problem by eagerly importing all 51
tool builders, all 38 config builders, and all 15 service builders at module level —
each of which triggers the full upstream import chain.

___

## 1. The Measured Reality

### 1.1 Disk Footprint (production install only)

| Package | Size | % | Cumulative | Used by simple agent? |
|---|--:|--:|--:|---|
| pyarrow | 142.6 MB | 33.1% | 33% | No |
| google-api-python-client | 91.4 MB | 21.2% | 54% | No |
| google-cloud-aiplatform | 77.7 MB | 18.1% | 72% | No |
| google-cloud-discoveryengine | 19.2 MB | 4.5% | 77% | No |
| grpcio | 16.0 MB | 3.7% | 81% | No |
| cryptography | 12.7 MB | 2.9% | 84% | No |
| SQLAlchemy | 12.5 MB | 2.9% | 86% | No |
| google-adk | 7.8 MB | 1.8% | 88% | Partially |
| 10 GCP service clients | 22.3 MB | 5.2% | 93% | No |
| Everything else (82 pkgs) | 26.8 MB | 6.2% | 100% | Mostly yes |

**The top 3 packages are 72% of the install.** None of them are used by a typical agent.

`google-api-python-client` is 91 MB because it ships **575 JSON service discovery files**
for every Google API (Drive, Gmail, YouTube, Maps, etc.). ADK uses a fraction of one.

### 1.2 Memory Footprint

```
Benchmark: `import adk_fluent`

  Peak heap:         181 MB
  Modules loaded:    3,140
  Wall-clock time:   4.71s (cold, no .pyc cache: 25s)
  Total allocated:   1.326 GB (507,656 allocations, most freed)
```

**Top allocators by size (memray):**

| Location | Allocated |
|---|--:|
| `importlib.get_data` (reading .pyc files) | 104 MB |
| `importlib._compile_bytecode` | 91 MB |
| `email.feedparser._parsegen` (parsing package metadata) | 81 MB |
| `dataclasses._create_fn` (protobuf/pydantic models) | 60 MB |
| `email.parser.parsestr` | 59 MB |

**Top allocators by count:**

| Location | Allocations |
|---|--:|
| Pydantic `create_schema_validator` | 68,854 |
| `importlib._compile_bytecode` | 40,012 |
| `dataclasses._create_fn` | 32,257 |
| Pydantic `complete_model_class` | 28,408 |

### 1.3 Module Loading by Category

| Namespace | Modules loaded | Avoidable? |
|---|--:|---|
| google.* (total) | 1,401 | Mostly yes |
| google.adk | 355 | Partially |
| google.cloud.discoveryengine | 239 | Entirely |
| sqlalchemy | 170 | Entirely |
| google.genai | 160 | No (core) |
| google.cloud.bigtable | 120 | Entirely |
| google.cloud.spanner | 90 | Entirely |
| google.cloud.monitoring | 86 | Entirely |
| opentelemetry | 84 | Entirely |
| pydantic | 76 | No (core) |
| adk_fluent | 70 | No (core) |
| google.cloud.bigquery | 57 | Entirely |
| google.cloud.pubsub | 35 | Entirely |
| grpc | 33 | Entirely |
| google.cloud.storage | 27 | Entirely |

**1,034 modules (33%) are GCP service clients that could be entirely deferred.**

### 1.4 The Import Chain Root Cause

```
import adk_fluent
  -> __init__.py imports agent.py, tool.py, config.py, service.py, ...
    -> tool.py has 51 top-level `from google.adk.tools.* import *`
    -> config.py has 38 top-level `from google.adk.agents.* import *`
    -> service.py imports google.adk.cli.utils.local_storage
    -> plugin.py imports google.adk.cli.plugins.recordings_plugin
    -> executor.py imports google.adk.code_executors.*
      -> google.adk.agents.base_agent imports 1,468 modules on its own
        -> pulls in ALL of: google.genai, fastapi, mcp, authlib, cryptography,
           requests, httpx, websockets, rich, yaml
      -> adk_fluent.tool adds 1,617 MORE modules
        -> google.cloud.discoveryengine (239), bigtable (120), spanner (55),
           monitoring (86), pubsub (35), bigquery (57), storage (27)
```

**Critical finding:** `from google.adk.agents.base_agent import BaseAgent` alone loads
1,468 modules and costs ~90 MB. This is the **unavoidable floor** for any code that
subclasses `BaseAgent`. The remaining ~90 MB comes from the generated builder modules
(`tool.py`, `service.py`, etc.) eagerly importing every ADK tool and service class.

### 1.5 Per-Builder-Module Cost (isolated subprocess measurement)

| Module | Time | Peak RAM | Modules |
|---|--:|--:|--:|
| adk_fluent._base | 25.0s | 158 MB | 3,142 |
| adk_fluent.agent | 25.0s | 158 MB | 3,142 |
| adk_fluent.tool | 24.8s | 158 MB | 3,142 |
| adk_fluent.config | 25.0s | 158 MB | 3,142 |
| adk_fluent.service | 25.6s | 158 MB | 3,142 |
| adk_fluent.plugin | 25.3s | 158 MB | 3,142 |
| adk_fluent.executor | 25.1s | 158 MB | 3,142 |
| adk_fluent.planner | 25.1s | 158 MB | 3,142 |

Every module costs the same because they all depend on `_base.py`, which depends on
`_primitives.py`, which does `from google.adk.agents.base_agent import BaseAgent` at
module level. **There is no cheap import path today.** Even importing just `_base.py`
triggers the full 3,142-module chain.

### 1.6 Downstream Impact

| Scenario | Impact |
|---|---|
| Container image (python:3.11-slim + adk-fluent) | 481 MB vs 75 MB theoretical minimum |
| Cloud Run cold start | 4.71s import / ~10s budget = 47% consumed |
| Lambda/Cloud Functions | Often exceeds 250 MB unzipped layer limit |
| CI install step | 431 MB download per job, every run |
| Dev machine (10 projects) | 4.3 GB just for adk-fluent deps |
| Low-memory VM (512 MB) | 181 MB import = 35% of total RAM before any work |

___

## 2. Root Cause Taxonomy

### 2.1 Upstream: google-adk's Monolithic Dependency Strategy

`google-adk` declares **43 hard dependencies** (non-extra). This includes:

- **10 GCP service clients** most users never touch (Spanner, Bigtable, Speech,
  Discovery Engine, PubSub, Secret Manager, BigQuery, BigQuery Storage, Storage,
  Cloud AI Platform)
- **7 OpenTelemetry packages** (API, SDK, 4 GCP exporters, 1 OTLP exporter, 1 resource
  detector)
- **pyarrow** (142 MB) — only needed for BigQuery Storage API
- **sqlalchemy + sqlalchemy-spanner + alembic** — only needed for DatabaseSessionService
- **graphviz** — only needed for agent graph visualization

None of these are behind extras. `pip install google-adk` = get everything.

### 2.2 Upstream: google-adk's Eager Import Architecture

`google.adk.agents.base_agent` (the one class every agent needs) transitively imports:
- The entire `google.genai` SDK (160 modules)
- `fastapi` + `starlette` (60 modules) — needed for `adk web`, not for `adk run`
- `mcp` server framework (82 modules) — needed only if using MCP tools
- `authlib` + `cryptography` (172 modules) — needed only for OAuth tool auth
- `rich` (60 modules) — needed only for CLI pretty-printing

### 2.3 Internal: adk-fluent's Eager Re-export Pattern

`adk_fluent/__init__.py` imports every builder module. Each generated builder module
(e.g., `tool.py`) imports every ADK class it wraps at module level.

```
# tool.py — 51 top-level imports like:
from google.adk.tools.bigquery.bigquery_toolset import BigQueryToolset
from google.adk.tools.bigtable.bigtable_toolset import BigtableToolset
from google.adk.tools.discovery_engine_search_tool import DiscoveryEngineSearchTool
...
```

A user who writes `from adk_fluent import Agent` pays the cost of all 51 tool builders,
all 38 config builders, all 15 service builders, even though they use exactly one class.

### 2.4 Internal: Unavoidable BaseAgent Dependency

`_primitives.py` subclasses `google.adk.agents.base_agent.BaseAgent` to implement
custom agent types (FnAgent, TapAgent, etc.). This is architecturally necessary —
these are real ADK agents. But it means the BaseAgent import (1,468 modules, ~90 MB)
is the **hard floor** that cannot be eliminated without a major redesign.

___

## 3. Top 10 Mechanisms to Prevent and Reduce Bloat

### Mechanism 1: Lazy `__init__.py` via `__getattr__` + `__dir__`

**What:** Replace eager imports in `adk_fluent/__init__.py` with a `__getattr__`
dispatcher that loads builder modules on first access.

**Why it works:** A user doing `from adk_fluent import Agent` only loads `agent.py`.
The 51 tool builders, 38 config builders, and 15 service builders stay unloaded until
someone actually references `BigQueryToolset`.

**Implementation:**

```python
# adk_fluent/__init__.py
_LAZY_MODULES = {
    "Agent": "agent", "Pipeline": "workflow", "FanOut": "workflow", "Loop": "workflow",
    "BigQueryToolset": "tool", "BigtableToolset": "tool", ...
    "DatabaseSessionService": "service", ...
}

def __getattr__(name):
    if name in _LAZY_MODULES:
        import importlib
        mod = importlib.import_module(f".{_LAZY_MODULES[name]}", __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    return list(__all__)  # preserves autocomplete
```

**Estimated savings:** ~40-60 MB RAM for users who only import Agent/Pipeline/FanOut.
Does not help if they import a tool or service builder (which pulls the rest).

**Tradeoff:** Slightly slower first access to lazy names. Autocomplete still works via
`__dir__`. Type checkers use `.pyi` stubs so no impact on static analysis.

**Risk:** Low. `numpy`, `scipy`, `pandas` all use this pattern.

---

### Mechanism 2: Deferred ADK Imports in Generated Builders

**What:** Move the `from google.adk.tools.X import X` lines from module level into
each builder's `build()` method or a `_resolve_adk_class()` classmethod.

**Why it works:** The ADK class is only needed at build time, not at definition time.
The builder is just collecting config until `.build()` is called.

**Implementation in code generator:**

```python
# Instead of:
from google.adk.tools.bigquery.bigquery_toolset import BigQueryToolset

class BigQueryToolsetBuilder(BuilderBase):
    _adk_cls = BigQueryToolset  # triggers import at module load
    ...

# Generate:
class BigQueryToolsetBuilder(BuilderBase):
    @staticmethod
    def _adk_cls():
        from google.adk.tools.bigquery.bigquery_toolset import BigQueryToolset
        return BigQueryToolset
    ...
```

**Estimated savings:** ~1,617 modules and ~60-80 MB if tool.py, service.py, config.py,
plugin.py, executor.py, planner.py all defer their imports.

**Tradeoff:** Small overhead on first `.build()` call (~200ms). Type stubs (`.pyi`) must
still declare the return types. Code generator needs modification.

**Risk:** Low. This is the standard pattern for optional heavy deps.

---

### Mechanism 3: Split `_primitives.py` into Base and ADK Layers

**What:** Separate the protocol/interface definitions (which don't need BaseAgent) from
the ADK-coupled implementations (which do).

**Why it works:** Today, `_base.py` -> `_primitives.py` -> `BaseAgent` is an unbreakable
chain. If builder definitions only depend on protocols, the BaseAgent import moves to
build time.

**Implementation:**

```
_primitives_protocol.py   # Protocol classes, no google imports
_primitives.py            # BaseAgent subclasses (imported at build time only)
_base.py                  # imports _primitives_protocol, not _primitives
```

**Estimated savings:** Potentially reduces the hard floor from ~90 MB to ~20 MB for
import-only scenarios.

**Tradeoff:** Architectural change. Requires careful interface extraction. Risk of
runtime errors if protocols diverge from implementations.

**Risk:** Medium. Needs thorough testing.

---

### Mechanism 4: Import Budget CI Gate

**What:** Add a CI check that fails if `import adk_fluent` exceeds a memory or module
count budget.

**Why it works:** Prevents regressions. Every new eager import is caught before merge.

**Implementation:**

```python
# tests/test_import_budget.py
import subprocess, sys

def test_import_module_budget():
    """Import adk_fluent must not load more than N modules."""
    result = subprocess.run([
        sys.executable, "-c",
        "import sys; import adk_fluent; print(len(sys.modules))"
    ], capture_output=True, text=True)
    count = int(result.stdout.strip())
    assert count < 500, f"Import loaded {count} modules (budget: 500)"

def test_import_memory_budget():
    """Import adk_fluent must not exceed N MB peak."""
    result = subprocess.run([
        sys.executable, "-c",
        "import tracemalloc; tracemalloc.start(); import adk_fluent; "
        "print(tracemalloc.get_traced_memory()[1] // (1024*1024))"
    ], capture_output=True, text=True)
    peak_mb = int(result.stdout.strip())
    assert peak_mb < 50, f"Import peak {peak_mb} MB (budget: 50 MB)"
```

**Estimated savings:** Zero directly. Prevents future regressions.

**Tradeoff:** May block PRs that add legitimate new imports. Budget numbers need
periodic review.

**Risk:** Low. Standard practice at companies that care about startup time.

---

### Mechanism 5: `importlib.util.LazyLoader` for Upstream Modules

**What:** Pre-register heavy upstream modules as lazy before they can be eagerly
imported by ADK internals.

**Why it works:** If `google.cloud.bigquery` is registered as lazy in `sys.modules`
before ADK tries to import it, the actual module loading is deferred until first
attribute access. Since most users never touch BigQuery, the load never happens.

**Implementation:**

```python
# adk_fluent/_lazy_guard.py — imported before anything else
import importlib.util, sys

_DEFERRABLE = [
    "google.cloud.bigquery", "google.cloud.bigquery_storage_v1",
    "google.cloud.bigtable", "google.cloud.spanner_v1",
    "google.cloud.discoveryengine", "google.cloud.speech",
    "google.cloud.pubsub_v1", "google.cloud.monitoring_v3",
    "numpy", "pyarrow", "sqlalchemy",
]

def install_lazy_guards():
    for name in _DEFERRABLE:
        if name not in sys.modules:
            spec = importlib.util.find_spec(name)
            if spec and spec.loader:
                lazy = importlib.util.LazyLoader(spec.loader)
                spec.loader = lazy
                mod = importlib.util.module_from_spec(spec)
                sys.modules[name] = mod
                lazy.exec_module(mod)
```

**Estimated savings:** Up to 80 MB if the deferred modules are never actually accessed.

**Tradeoff:** Dangerous. If ADK accesses an attribute of a lazily loaded module during
import, the lazy load triggers anyway — and now it happens at an unpredictable point.
Can cause subtle ordering bugs.

**Risk:** High. This is a sharp tool. Must be tested against every ADK code path.
Consider this a last resort if Mechanisms 1-3 are insufficient.

---

### Mechanism 6: Upstream Advocacy — ADK Optional Extras RFC

**What:** File a feature request / RFC with the google-adk team proposing:

```text
# Proposed google-adk extras
[project.optional-dependencies]
bigquery = ["google-cloud-bigquery", "google-cloud-bigquery-storage", "pyarrow"]
spanner  = ["google-cloud-spanner", "sqlalchemy-spanner"]
bigtable = ["google-cloud-bigtable"]
speech   = ["google-cloud-speech"]
pubsub   = ["google-cloud-pubsub"]
search   = ["google-cloud-discoveryengine"]
secrets  = ["google-cloud-secret-manager"]
storage  = ["google-cloud-storage"]
otel     = ["opentelemetry-api", "opentelemetry-sdk", ...]
all      = ["google-adk[bigquery,spanner,bigtable,speech,pubsub,search,secrets,storage,otel]"]
```

**Why it works:** This is the correct fix at the correct layer. Most Python libraries
with large optional dependency surfaces use extras (FastAPI, LangChain, Airflow).

**Estimated savings:** ~350 MB disk, ~100 MB RAM for users who don't opt in to GCP
services.

**Tradeoff:** Upstream team must maintain extra groups. Users who need everything must
`pip install google-adk[all]`.

**Risk:** Low technical risk, high coordination risk (external team).

---

### Mechanism 7: Dependency-Free Core Mode

**What:** Allow `adk_fluent` to operate in a "builder-only" mode where it constructs
builder objects without importing any ADK classes. The ADK import happens only on
`.build()`.

**Why it works:** Most of the fluent API is just accumulating config in dicts. The ADK
dependency is only needed at the `.build()` boundary.

**Implementation:**

```python
class BuilderBase:
    def build(self):
        # Only now do we need ADK
        from adk_fluent.backends.adk import compile_builder
        return compile_builder(self)
```

**Estimated savings:** Near-zero import cost. Full cost deferred to first `.build()`.

**Tradeoff:** Major refactor. Would separate "builder construction" from "ADK
compilation" into two distinct phases. Type hints on `.build()` return type need a
protocol or stub.

**Risk:** Medium-high. Fundamental architectural change. But aligns with the existing
`backends/` directory structure, which suggests this was anticipated.

---

### Mechanism 8: Dependency Inventory Audit in CI

**What:** Automated check that lists all transitive production dependencies with sizes,
diffs against baseline on every PR.

**Implementation:**

```bash
# scripts/dep-audit.sh
pip install adk-fluent --dry-run --report report.json
python3 -c "
import json
with open('report.json') as f:
    data = json.load(f)
for pkg in sorted(data['install'], key=lambda x: -x['download_info']['size']):
    name = pkg['metadata']['name']
    size = pkg['download_info']['size'] / 1024 / 1024
    print(f'{name:45s} {size:8.1f} MB')
"
```

**Estimated savings:** Awareness. Prevents adding deps without understanding cost.

**Tradeoff:** Minor CI time increase.

**Risk:** None.

---

### Mechanism 9: `memray` Integration in Test Suite

**What:** Add memory profiling as a pytest plugin for regression detection.

**Implementation:**

```python
# conftest.py
import pytest, tracemalloc

@pytest.fixture(autouse=True, scope="session")
def _memory_baseline():
    tracemalloc.start()
    yield
    current, peak = tracemalloc.get_traced_memory()
    print(f"\nSession peak memory: {peak / 1024 / 1024:.0f} MB")
    tracemalloc.stop()

# For detailed profiling:
# pytest --memray --most-allocations=20
```

Add to CI:

```yaml
- name: Memory regression check
  run: |
    pip install pytest-memray
    pytest tests/ --memray --most-allocations=10 -x
```

**Estimated savings:** Prevents regressions. Gives data for optimization decisions.

**Tradeoff:** Adds ~2s to test suite. memray output can be noisy.

**Risk:** None.

---

### Mechanism 10: Conditional Heavyweight Module Registration

**What:** In the code generator, emit builder classes for heavyweight tools
(BigQuery, Spanner, Bigtable, etc.) into separate submodules that are only loaded
when explicitly requested.

**Implementation:**

```
adk_fluent/
  tool.py           # Core tools only (FunctionTool, AgentTool, etc.)
  tool_gcp.py       # BigQuery, Bigtable, Spanner, PubSub, etc. (auto-generated)
  tool_google.py    # Calendar, Gmail, Sheets, etc. (auto-generated)
  __init__.py       # Lazy-loads tool_gcp and tool_google via __getattr__
```

**Why it works:** Users who `from adk_fluent import FunctionTool` don't load Spanner.
Users who need `from adk_fluent import SpannerToolset` pay only for that submodule.

**Estimated savings:** 40-80 MB for users who use only core tools.

**Tradeoff:** Code generator must categorize builders by weight class. More files to
maintain. Import paths in docs must be updated.

**Risk:** Low-medium. Purely additive — no existing imports break.

___

## 4. Recommended Execution Order

```
Phase 1 — Quick wins, no architecture changes (1-2 days)
  [Mechanism 4]  Import budget CI gate          — prevents regressions from day 1
  [Mechanism 8]  Dependency inventory audit     — visibility into what every PR costs
  [Mechanism 9]  memray in test suite           — regression detection with data

Phase 2 — Internal lazy loading (3-5 days)
  [Mechanism 1]  Lazy __init__.py               — biggest single win for typical users
  [Mechanism 2]  Deferred imports in generators — eliminates GCP service client loading
  [Mechanism 10] Split heavyweight builders     — isolates GCP tool cost

Phase 3 — Architectural (1-2 weeks)
  [Mechanism 3]  Split _primitives.py           — reduces hard floor from 90 to ~20 MB
  [Mechanism 7]  Dependency-free core mode      — near-zero import cost

Phase 4 — Upstream (ongoing)
  [Mechanism 6]  ADK optional extras RFC        — correct fix at correct layer

Skip unless desperate:
  [Mechanism 5]  LazyLoader for upstream        — too risky for the benefit
```

___

## 5. Projected Outcomes

| Metric | Current | After Phase 1 | After Phase 2 | After Phase 3 |
|---|--:|--:|--:|--:|
| Import peak RAM | 181 MB | 181 MB | ~90 MB | ~20 MB |
| Modules loaded | 3,140 | 3,140 | ~1,500 | ~300 |
| Import time (warm) | 4.7s | 4.7s | ~2.5s | ~0.5s |
| Container image | 481 MB | 481 MB | 481 MB | 481 MB |
| Cold start budget consumed | 47% | 47% | ~25% | ~5% |

Note: disk footprint does not improve until upstream (Phase 4) is resolved. Mechanisms
1-3 only reduce **runtime** cost — the packages are still installed, just not loaded.

___

## 6. Measurement Playbook

Commands for anyone to reproduce these numbers:

```bash
# Quick: import cost (RAM + modules)
python3 -c "
import tracemalloc, sys; tracemalloc.start()
import adk_fluent
print(f'Peak: {tracemalloc.get_traced_memory()[1]/1024/1024:.0f} MB')
print(f'Modules: {len(sys.modules)}')
"

# Deep: allocation flamegraph
memray run -o profile.bin -c "import adk_fluent"
memray flamegraph profile.bin -o flamegraph.html

# Import time ranking
python3 -X importtime -c "import adk_fluent" 2>&1 | sort -t'|' -k1 -rn | head -20

# Disk footprint
python3 -c "
import importlib.metadata as meta, pathlib
sizes = []
for d in meta.distributions():
    total = sum(
        pathlib.Path(d._path.parent / f).stat().st_size
        for f in (d.files or [])
        if pathlib.Path(d._path.parent / f).exists()
    )
    sizes.append((total, d.metadata['Name']))
sizes.sort(reverse=True)
for s, n in sizes[:20]:
    print(f'{n:45s} {s/1024/1024:8.1f} MB')
"

# Per-module isolation test
for mod in agent tool config service plugin executor planner; do
  python3 -c "
import tracemalloc, sys, time; tracemalloc.start(); t=time.perf_counter()
import adk_fluent.$mod
print(f'adk_fluent.$mod: {tracemalloc.get_traced_memory()[1]/1024/1024:.0f} MB, {len(sys.modules)} mods, {time.perf_counter()-t:.1f}s')
"
done
```

___

## Appendix A: Full Dependency Tree (Production)

122 packages. Sorted by disk size. GCP service clients highlighted.

```
 142.6 MB  pyarrow                          # BigQuery Storage only
  91.4 MB  google-api-python-client         # 575 JSON discovery files
  77.7 MB  google-cloud-aiplatform          # Vertex AI (Agent Engine)
  19.2 MB  google-cloud-discoveryengine     # Enterprise Search
  16.0 MB  grpcio                           # gRPC runtime
  12.7 MB  cryptography                     # TLS / OAuth
  12.5 MB  SQLAlchemy                       # DatabaseSessionService
   7.8 MB  google-adk                       # ADK core
   3.5 MB  google-cloud-bigtable            # Bigtable tools
   3.3 MB  google-cloud-spanner             # Spanner tools
   3.3 MB  google-genai                     # Gemini SDK (core)
   2.7 MB  PyYAML                           # YAML parsing
   2.6 MB  google-cloud-iam                 # IAM (transitive)
   2.3 MB  google-cloud-resource-manager    # (transitive)
   2.3 MB  google-cloud-speech              # Speech-to-text
   1.9 MB  google-cloud-monitoring          # (transitive from otel)
   1.9 MB  greenlet                         # SQLAlchemy async
   1.8 MB  google-cloud-pubsub              # Pub/Sub tools
   1.8 MB  pydantic                         # Data validation (core)
   1.7 MB  google-cloud-secret-manager      # Secret Manager
   1.6 MB  google-cloud-storage             # GCS
   ... 101 more packages under 1.5 MB each
```

## Appendix B: What `google.adk.agents.base_agent.BaseAgent` Imports

1,468 modules. This is the hard floor — every ADK agent inherits from it.

Top namespaces:
```
  google.genai._interactions     128 modules
  rich                            59 modules
  google.adk.tools                38 modules
  cryptography.hazmat             30 modules
  pydantic                        23 modules
  fastapi                         22 modules
  google.adk.agents               21 modules
  mcp.server                      19 modules
  authlib.oauth2                  19 modules
  google.adk.flows                19 modules
```
