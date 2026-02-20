# Full Auto-Pipeline Seed Generator — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a mechanism that systematically parses ALL google-adk modules and generates a complete seed.toml automatically — no human review step.

**Architecture:** Three-stage pipeline: enhanced scanner (walks all ADK modules, introspects Pydantic + non-Pydantic classes) → seed generator (classifies classes, applies field policies, generates aliases, emits seed.toml) → existing generator (produces .py, .pyi, tests from seed + manifest).

**Tech Stack:** Python 3.11+, pydantic introspection, inspect module, tomllib/tomli, pkgutil

**Working directory:** `/home/user/adk-fluent`
**Virtual env:** `source .venv/bin/activate` before ALL python/pytest commands
**Current file locations:** scanner.py, generator.py, seed.toml are at project root (not in scripts/ subdirectory)

______________________________________________________________________

## Task 1: Reorganize project to match SPEC structure

The SPEC says scripts go in `scripts/`, seed in `seeds/`. Current files are at root. Fix this first so all subsequent work uses the canonical paths.

**Files:**

- Move: `scanner.py` → `scripts/scanner.py`
- Move: `generator.py` → `scripts/generator.py`
- Move: `seed.toml` → `seeds/seed.toml`
- Modify: `Makefile` (already references `scripts/` paths, verify)

**Step 1: Create directories and move files**

```bash
mkdir -p scripts seeds
mv scanner.py scripts/scanner.py
mv generator.py scripts/generator.py
mv seed.toml seeds/seed.toml
```

**Step 2: Verify Makefile paths match**

The Makefile already references `scripts/scanner.py`, `scripts/generator.py`, and `seeds/seed.toml`. Verify no path mismatches exist.

**Step 3: Verify scanner runs from new location**

```bash
source .venv/bin/activate && python scripts/scanner.py --summary
```

Expected: Scanner runs, prints class summary (no import errors for core modules).

______________________________________________________________________

## Task 2: Enhanced scanner — auto-discovery module walker

Replace the hardcoded `SCAN_TARGETS` list with automatic package walking. The scanner should discover ALL modules in `google.adk` and find ALL classes automatically.

**Files:**

- Modify: `scripts/scanner.py`
- Create: `tests/test_scanner.py`

**Step 1: Write test for module discovery**

Create `tests/test_scanner.py`:

```python
"""Tests for the enhanced scanner."""
import pytest


def test_discover_modules_finds_core_packages():
    """Auto-discovery must find the known core ADK modules."""
    from scripts.scanner import discover_modules

    modules = discover_modules()
    module_names = {m for m in modules}

    # These must always be found
    assert "google.adk.agents" in module_names or any(
        m.startswith("google.adk.agents") for m in module_names
    )
    assert any(m.startswith("google.adk.events") for m in module_names)
    assert any(m.startswith("google.adk.sessions") for m in module_names)
    assert any(m.startswith("google.adk.tools") for m in module_names)
    assert any(m.startswith("google.adk.runners") for m in module_names)
    assert any(m.startswith("google.adk.apps") for m in module_names)

    # Should find many modules (ADK has 400+)
    assert len(modules) > 50


def test_discover_modules_skips_broken_imports():
    """Modules with missing optional deps (a2a, docker, etc.) should not crash."""
    from scripts.scanner import discover_modules

    # Should not raise even though some modules need optional deps
    modules = discover_modules()
    assert isinstance(modules, list)
```

**Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/test_scanner.py::test_discover_modules_finds_core_packages -v
```

Expected: FAIL — `discover_modules` doesn't exist yet.

**Step 3: Implement `discover_modules` in scanner.py**

Add this function to `scripts/scanner.py`, replacing the `SCAN_TARGETS` approach:

```python
def discover_modules() -> list[str]:
    """Walk the google.adk package tree and return all importable module paths."""
    import google.adk

    discovered = []
    for importer, modname, ispkg in pkgutil.walk_packages(
        google.adk.__path__, prefix="google.adk."
    ):
        discovered.append(modname)
    return sorted(discovered)


def discover_classes(modules: list[str]) -> list[tuple[type, str]]:
    """Import each module and extract all public classes.

    Returns list of (class, module_path) tuples.
    Skips modules that fail to import (missing optional deps).
    """
    from pydantic import BaseModel as PydanticBase

    seen_qualnames: set[str] = set()
    results: list[tuple[type, str]] = []

    for modname in modules:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue

        for name in dir(mod):
            if name.startswith("_"):
                continue
            obj = getattr(mod, name, None)
            if not isinstance(obj, type):
                continue
            # Only include classes defined in this module (avoid re-export dupes)
            if getattr(obj, "__module__", None) != modname:
                continue

            qualname = f"{obj.__module__}.{obj.__name__}"
            if qualname in seen_qualnames:
                continue
            seen_qualnames.add(qualname)

            results.append((obj, modname))

    return results
```

**Step 4: Run test to verify it passes**

```bash
source .venv/bin/activate && python -m pytest tests/test_scanner.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add scripts/scanner.py tests/test_scanner.py
git commit -m "feat(scanner): add auto-discovery of all ADK modules"
```

______________________________________________________________________

## Task 3: Enhanced scanner — dual-mode introspection

Add `inspect.signature()` support for non-Pydantic classes alongside the existing `model_fields` introspection for Pydantic classes.

**Files:**

- Modify: `scripts/scanner.py`
- Modify: `tests/test_scanner.py`

**Step 1: Write tests for dual-mode introspection**

Add to `tests/test_scanner.py`:

```python
def test_scan_class_pydantic():
    """Pydantic classes should use model_fields introspection."""
    from google.adk.agents import LlmAgent
    from scripts.scanner import scan_class

    info = scan_class(LlmAgent)
    assert info.is_pydantic is True
    assert info.inspection_mode == "pydantic"
    assert len(info.fields) > 10  # LlmAgent has ~26 fields
    assert any(f.name == "instruction" for f in info.fields)
    assert any(f.name == "model" for f in info.fields)
    assert any(f.name == "tools" for f in info.fields)


def test_scan_class_non_pydantic():
    """Non-Pydantic classes should use inspect.signature introspection."""
    from google.adk.runners import Runner
    from scripts.scanner import scan_class

    info = scan_class(Runner)
    assert info.is_pydantic is False
    assert info.inspection_mode == "init_signature"
    assert len(info.init_params) > 0
    # Runner.__init__ takes agent, app_name, etc.
    param_names = [p.name for p in info.init_params]
    assert "agent" in param_names or "app_name" in param_names


def test_scan_class_preserves_existing_pydantic_fields():
    """Existing field extraction for Pydantic classes must still work."""
    from google.adk.agents import LlmAgent
    from scripts.scanner import scan_class

    info = scan_class(LlmAgent)
    instruction_field = next(f for f in info.fields if f.name == "instruction")
    assert "str" in instruction_field.type_str or "Callable" in instruction_field.type_str
    assert instruction_field.is_callback is False or "Callable" in instruction_field.type_str
```

**Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_scanner.py::test_scan_class_non_pydantic -v
```

Expected: FAIL — `inspection_mode` and `init_params` don't exist on ClassInfo.

**Step 3: Extend data structures and scan_class**

Modify `scripts/scanner.py`:

Add `InitParam` dataclass:

```python
@dataclass
class InitParam:
    """Describes a parameter from __init__ (for non-Pydantic classes)."""
    name: str
    type_str: str
    default: str | None  # None means required
    required: bool
    position: int  # 0-indexed, excluding self
```

Add fields to `ClassInfo`:

```python
@dataclass
class ClassInfo:
    # ... existing fields ...
    inspection_mode: str = "pydantic"  # "pydantic" or "init_signature"
    init_params: list[InitParam] = field(default_factory=list)
```

Add `_scan_init_signature` function:

```python
def _scan_init_signature(cls) -> list[InitParam]:
    """Extract __init__ parameters via inspect.signature."""
    try:
        sig = inspect.signature(cls.__init__)
    except (ValueError, TypeError):
        return []

    params = []
    for i, (pname, param) in enumerate(sig.parameters.items()):
        if pname == "self":
            continue
        if pname.startswith("_"):
            continue

        type_hint = param.annotation
        type_str = _type_to_str(type_hint) if type_hint is not inspect.Parameter.empty else "Any"

        if param.default is inspect.Parameter.empty:
            default_repr = None
            required = True
        else:
            default_repr = repr(param.default)
            required = False

        params.append(InitParam(
            name=pname,
            type_str=type_str,
            default=default_repr,
            required=required,
            position=i,
        ))

    return params
```

Update `scan_class` to set `inspection_mode` and `init_params`:

```python
def scan_class(cls) -> ClassInfo:
    # ... existing code ...
    # After is_pydantic check:
    if is_pydantic:
        inspection_mode = "pydantic"
        init_params = []
    else:
        inspection_mode = "init_signature"
        init_params = _scan_init_signature(cls)

    return ClassInfo(
        # ... existing fields ...
        inspection_mode=inspection_mode,
        init_params=init_params,
    )
```

**Step 4: Run all tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_scanner.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add scripts/scanner.py tests/test_scanner.py
git commit -m "feat(scanner): dual-mode introspection for Pydantic and non-Pydantic classes"
```

______________________________________________________________________

## Task 4: Enhanced scanner — replace scan_all with auto-discovery

Replace the `scan_all()` function that uses hardcoded `SCAN_TARGETS` with one that uses `discover_modules()` + `discover_classes()`.

**Files:**

- Modify: `scripts/scanner.py`
- Modify: `tests/test_scanner.py`

**Step 1: Write test for new scan_all**

Add to `tests/test_scanner.py`:

```python
def test_scan_all_finds_more_classes_than_old_targets():
    """Auto-discovery should find significantly more classes than the old hardcoded list."""
    from scripts.scanner import scan_all

    manifest = scan_all()
    # Old scanner found ~12 classes. New should find many more.
    assert manifest.total_classes > 30
    # Must still find the core classes
    class_names = {c.name for c in manifest.classes}
    assert "LlmAgent" in class_names
    assert "BaseAgent" in class_names
    assert "SequentialAgent" in class_names
    assert "Event" in class_names


def test_scan_all_includes_non_pydantic():
    """Manifest should include non-Pydantic classes like Runner."""
    from scripts.scanner import scan_all

    manifest = scan_all()
    class_names = {c.name for c in manifest.classes}
    # Runner is non-Pydantic but should be discovered
    assert "Runner" in class_names

    runner_info = next(c for c in manifest.classes if c.name == "Runner")
    assert runner_info.inspection_mode == "init_signature"


def test_manifest_json_serialization():
    """Manifest with new fields must serialize to JSON without errors."""
    import json
    from scripts.scanner import scan_all, manifest_to_dict

    manifest = scan_all()
    data = manifest_to_dict(manifest)
    # Must not raise
    json_str = json.dumps(data, indent=2, default=str)
    assert len(json_str) > 1000

    # Round-trip: parse it back
    parsed = json.loads(json_str)
    assert parsed["total_classes"] == manifest.total_classes
```

**Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_scanner.py::test_scan_all_finds_more_classes_than_old_targets -v
```

Expected: FAIL (old scan_all uses SCAN_TARGETS, finds ~12 classes, not >30).

**Step 3: Rewrite scan_all**

Replace the `scan_all()` function in `scripts/scanner.py`:

```python
def scan_all() -> Manifest:
    """Scan all ADK modules automatically and produce a Manifest."""
    modules = discover_modules()
    class_tuples = discover_classes(modules)

    classes = []
    for cls, modpath in class_tuples:
        try:
            info = scan_class(cls)
            classes.append(info)
        except Exception as e:
            print(f"WARNING: Failed to scan {cls.__name__} from {modpath}: {e}", file=sys.stderr)

    # Get ADK version
    try:
        from importlib.metadata import version
        adk_version = version("google-adk")
    except Exception:
        adk_version = "unknown"

    total_fields = sum(len(c.fields) for c in classes)
    total_callbacks = sum(
        sum(1 for f in c.fields if f.is_callback) for c in classes
    )

    return Manifest(
        adk_version=adk_version,
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        classes=classes,
        total_classes=len(classes),
        total_fields=total_fields,
        total_callbacks=total_callbacks,
    )
```

Also update `manifest_to_dict` to include new fields (`inspection_mode`, `init_params`).

**Step 4: Run all scanner tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_scanner.py -v
```

Expected: ALL PASS

**Step 5: Run scanner end-to-end and save manifest**

```bash
source .venv/bin/activate && python scripts/scanner.py --summary
source .venv/bin/activate && python scripts/scanner.py -o manifest.json
```

Expected: Summary shows >100 classes scanned. manifest.json written.

**Step 6: Commit**

```bash
git add scripts/scanner.py tests/test_scanner.py
git commit -m "feat(scanner): auto-discover all ADK modules, replace hardcoded SCAN_TARGETS"
```

______________________________________________________________________

## Task 5: Seed generator — classification engine

Build the classification engine that tags each class from the manifest.

**Files:**

- Create: `scripts/seed_generator.py`
- Create: `tests/test_seed_generator.py`

**Step 1: Write classification tests**

Create `tests/test_seed_generator.py`:

```python
"""Tests for the seed generator."""
import pytest


def test_classify_agent():
    from scripts.seed_generator import classify_class
    assert classify_class("LlmAgent", "google.adk.agents.llm_agent", ["BaseAgent", "BaseModel"]) == "agent"
    assert classify_class("SequentialAgent", "google.adk.agents.sequential_agent", ["BaseAgent"]) == "agent"
    assert classify_class("BaseAgent", "google.adk.agents.base_agent", ["BaseModel"]) == "agent"


def test_classify_service():
    from scripts.seed_generator import classify_class
    assert classify_class("InMemorySessionService", "google.adk.sessions.in_memory_session_service", ["BaseSessionService"]) == "service"
    assert classify_class("GcsArtifactService", "google.adk.artifacts.gcs_artifact_service", ["BaseArtifactService"]) == "service"


def test_classify_config():
    from scripts.seed_generator import classify_class
    assert classify_class("RunConfig", "google.adk.agents.run_config", ["BaseModel"]) == "config"
    assert classify_class("ResumabilityConfig", "google.adk.apps.app", ["BaseModel"]) == "config"


def test_classify_tool():
    from scripts.seed_generator import classify_class
    assert classify_class("FunctionTool", "google.adk.tools.function_tool", ["BaseTool"]) == "tool"
    assert classify_class("McpToolset", "google.adk.tools.mcp_tool.mcp_toolset", ["BaseToolset"]) == "tool"


def test_classify_runtime():
    from scripts.seed_generator import classify_class
    assert classify_class("App", "google.adk.apps.app", ["BaseModel"]) == "runtime"
    assert classify_class("Runner", "google.adk.runners", ["object"]) == "runtime"


def test_classify_plugin():
    from scripts.seed_generator import classify_class
    assert classify_class("LoggingPlugin", "google.adk.plugins.logging_plugin", ["BasePlugin"]) == "plugin"


def test_classify_planner():
    from scripts.seed_generator import classify_class
    assert classify_class("PlanReActPlanner", "google.adk.planners.plan_re_act_planner", ["BasePlanner"]) == "planner"


def test_classify_executor():
    from scripts.seed_generator import classify_class
    assert classify_class("BuiltInCodeExecutor", "google.adk.code_executors.built_in_code_executor", ["BaseCodeExecutor"]) == "executor"


def test_classify_eval():
    from scripts.seed_generator import classify_class
    assert classify_class("EvalCase", "google.adk.evaluation.eval_case", ["BaseModel"]) == "eval"


def test_classify_auth():
    from scripts.seed_generator import classify_class
    assert classify_class("AuthCredential", "google.adk.auth.auth_credential", ["BaseModel"]) == "auth"


def test_classify_data():
    from scripts.seed_generator import classify_class
    assert classify_class("Session", "google.adk.sessions.session", ["BaseModel"]) == "data"
    assert classify_class("Event", "google.adk.events.event", ["LlmResponse"]) == "data"


def test_is_builder_worthy():
    from scripts.seed_generator import is_builder_worthy
    assert is_builder_worthy("agent") is True
    assert is_builder_worthy("config") is True
    assert is_builder_worthy("runtime") is True
    assert is_builder_worthy("executor") is True
    assert is_builder_worthy("planner") is True
    assert is_builder_worthy("service") is True
    assert is_builder_worthy("plugin") is True
    assert is_builder_worthy("tool") is True
    assert is_builder_worthy("eval") is False
    assert is_builder_worthy("auth") is False
    assert is_builder_worthy("data") is False
```

**Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py -v
```

Expected: FAIL — module doesn't exist.

**Step 3: Implement classification engine**

Create `scripts/seed_generator.py`:

```python
#!/usr/bin/env python3
"""
ADK-FLUENT SEED GENERATOR
==========================
Reads manifest.json (from scanner) and produces a complete seed.toml
automatically. No human review needed.

Pipeline position:
    scanner → manifest.json → seed_generator → seed.toml → generator → code

Usage:
    python scripts/seed_generator.py manifest.json -o seeds/seed.toml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# CLASSIFICATION ENGINE
# ---------------------------------------------------------------------------

# Checked in order — first match wins
_CLASSIFICATION_RULES: list[tuple[str, callable]] = []


def classify_class(name: str, module: str, bases: list[str]) -> str:
    """Classify an ADK class into a category based on mechanical rules.

    Rules are checked in order. First match wins.
    """
    bases_set = set(bases)
    mro_has_agent = "BaseAgent" in bases_set

    # Rule 1: Agent subclasses
    if mro_has_agent or name == "BaseAgent":
        return "agent"

    # Rule 2: Runtime singletons
    if name in ("App", "Runner", "InMemoryRunner"):
        return "runtime"

    # Rule 3: Evaluation module
    if "evaluation" in module or "eval" in module.split(".")[-1]:
        return "eval"

    # Rule 4: Auth module
    if ".auth" in module or ".auth." in module:
        return "auth"

    # Rule 5: Service classes
    if name.endswith("Service"):
        return "service"

    # Rule 6: Config classes
    if name.endswith("Config"):
        return "config"

    # Rule 7: Tool and Toolset classes
    if name.endswith("Tool") or name.endswith("Toolset"):
        return "tool"

    # Rule 8: Plugin classes
    if name.endswith("Plugin"):
        return "plugin"

    # Rule 9: Planner classes
    if name.endswith("Planner"):
        return "planner"

    # Rule 10: Executor classes
    if name.endswith("Executor"):
        return "executor"

    # Default: data
    return "data"


# Tags that get builders
_BUILDER_WORTHY_TAGS = frozenset({
    "agent", "config", "runtime", "executor", "planner",
    "service", "plugin", "tool",
})


def is_builder_worthy(tag: str) -> bool:
    """Whether a class with this tag should get a fluent builder."""
    return tag in _BUILDER_WORTHY_TAGS
```

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(seed_generator): classification engine for ADK classes"
```

______________________________________________________________________

## Task 6: Seed generator — field policy engine

Build the engine that determines skip, additive, and list_extend policies for each field.

**Files:**

- Modify: `scripts/seed_generator.py`
- Modify: `tests/test_seed_generator.py`

**Step 1: Write field policy tests**

Add to `tests/test_seed_generator.py`:

```python
def test_field_policy_skip_internal():
    from scripts.seed_generator import get_field_policy
    assert get_field_policy("parent_agent", "Optional[BaseAgent]", False) == "skip"
    assert get_field_policy("model_config", "ConfigDict", False) == "skip"
    assert get_field_policy("model_fields", "dict", False) == "skip"
    assert get_field_policy("model_computed_fields", "dict", False) == "skip"
    assert get_field_policy("_private", "str", False) == "skip"


def test_field_policy_additive_callbacks():
    from scripts.seed_generator import get_field_policy
    assert get_field_policy("before_model_callback", "Union[Callable, list[Callable], None]", True) == "additive"
    assert get_field_policy("after_agent_callback", "Union[Callable, None]", True) == "additive"
    assert get_field_policy("on_model_error_callback", "Callable", True) == "additive"


def test_field_policy_list_extend():
    from scripts.seed_generator import get_field_policy
    assert get_field_policy("tools", "list[BaseTool]", False) == "list_extend"
    assert get_field_policy("sub_agents", "list[BaseAgent]", False) == "list_extend"
    assert get_field_policy("plugins", "list[BasePlugin]", False) == "list_extend"


def test_field_policy_normal():
    from scripts.seed_generator import get_field_policy
    assert get_field_policy("instruction", "str | Callable", False) == "normal"
    assert get_field_policy("model", "str", False) == "normal"
    assert get_field_policy("output_key", "Optional[str]", False) == "normal"
```

**Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py::test_field_policy_skip_internal -v
```

Expected: FAIL

**Step 3: Implement field policy engine**

Add to `scripts/seed_generator.py`:

```python
# ---------------------------------------------------------------------------
# FIELD POLICY ENGINE
# ---------------------------------------------------------------------------

_ALWAYS_SKIP = frozenset({
    "parent_agent", "model_config", "model_fields",
    "model_computed_fields", "model_post_init",
})

_LIST_EXTEND_FIELDS = frozenset({
    "tools", "sub_agents", "plugins",
})


def get_field_policy(field_name: str, type_str: str, is_callback: bool) -> str:
    """Determine the policy for a field: skip, additive, list_extend, or normal."""
    # Skip internal/private fields
    if field_name.startswith("_"):
        return "skip"
    if field_name in _ALWAYS_SKIP:
        return "skip"

    # Additive callback fields
    if is_callback and "callback" in field_name:
        return "additive"

    # List extend fields
    if field_name in _LIST_EXTEND_FIELDS:
        return "list_extend"

    return "normal"
```

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(seed_generator): field policy engine for skip/additive/list_extend"
```

______________________________________________________________________

## Task 7: Seed generator — alias engine

Build the mechanical alias generation for field names and callback shorthands.

**Files:**

- Modify: `scripts/seed_generator.py`
- Modify: `tests/test_seed_generator.py`

**Step 1: Write alias tests**

Add to `tests/test_seed_generator.py`:

```python
def test_generate_aliases():
    from scripts.seed_generator import generate_aliases
    fields = ["instruction", "description", "global_instruction", "model", "tools", "output_key"]
    aliases = generate_aliases(fields)
    assert aliases == {
        "instruct": "instruction",
        "describe": "description",
        "global_instruct": "global_instruction",
    }


def test_generate_aliases_no_match():
    from scripts.seed_generator import generate_aliases
    fields = ["model", "tools", "output_key"]
    aliases = generate_aliases(fields)
    assert aliases == {}


def test_generate_callback_aliases():
    from scripts.seed_generator import generate_callback_aliases
    callbacks = [
        "before_agent_callback",
        "after_agent_callback",
        "before_model_callback",
        "after_model_callback",
        "on_model_error_callback",
        "before_tool_callback",
        "after_tool_callback",
        "on_tool_error_callback",
    ]
    aliases = generate_callback_aliases(callbacks)
    assert aliases == {
        "before_agent": "before_agent_callback",
        "after_agent": "after_agent_callback",
        "before_model": "before_model_callback",
        "after_model": "after_model_callback",
        "on_model_error": "on_model_error_callback",
        "before_tool": "before_tool_callback",
        "after_tool": "after_tool_callback",
        "on_tool_error": "on_tool_error_callback",
    }


def test_generate_callback_aliases_empty():
    from scripts.seed_generator import generate_callback_aliases
    assert generate_callback_aliases([]) == {}
```

**Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py::test_generate_aliases -v
```

Expected: FAIL

**Step 3: Implement alias engine**

Add to `scripts/seed_generator.py`:

```python
# ---------------------------------------------------------------------------
# ALIAS ENGINE
# ---------------------------------------------------------------------------

# Lookup table: field_name → alias
# Only exact matches get aliases. No heuristics.
_FIELD_ALIAS_TABLE: dict[str, str] = {
    "instruction": "instruct",
    "description": "describe",
    "global_instruction": "global_instruct",
}


def generate_aliases(field_names: list[str]) -> dict[str, str]:
    """Generate ergonomic aliases for fields using the lookup table.

    Returns {alias: field_name} mapping.
    """
    result = {}
    for fname in field_names:
        if fname in _FIELD_ALIAS_TABLE:
            result[_FIELD_ALIAS_TABLE[fname]] = fname
    return result


def generate_callback_aliases(callback_field_names: list[str]) -> dict[str, str]:
    """Generate short aliases for callback fields by stripping '_callback' suffix.

    Returns {short_name: full_field_name} mapping.
    """
    result = {}
    for fname in callback_field_names:
        if fname.endswith("_callback"):
            short = fname[: -len("_callback")]
            result[short] = fname
    return result
```

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(seed_generator): alias engine for fields and callbacks"
```

______________________________________________________________________

## Task 8: Seed generator — constructor arg detection

Build the logic that determines which fields should be constructor arguments.

**Files:**

- Modify: `scripts/seed_generator.py`
- Modify: `tests/test_seed_generator.py`

**Step 1: Write constructor arg tests**

Add to `tests/test_seed_generator.py`:

```python
def test_detect_constructor_args_pydantic():
    """Required Pydantic fields become constructor args, capped at 3."""
    from scripts.seed_generator import detect_constructor_args

    fields = [
        {"name": "name", "required": True, "type_str": "str"},
        {"name": "model", "required": True, "type_str": "str"},
        {"name": "instruction", "required": False, "type_str": "str"},
        {"name": "tools", "required": False, "type_str": "list"},
    ]
    args = detect_constructor_args(fields, inspection_mode="pydantic", init_params=[])
    assert args == ["name", "model"]


def test_detect_constructor_args_caps_at_3():
    from scripts.seed_generator import detect_constructor_args

    fields = [
        {"name": "a", "required": True, "type_str": "str"},
        {"name": "b", "required": True, "type_str": "str"},
        {"name": "c", "required": True, "type_str": "str"},
        {"name": "d", "required": True, "type_str": "str"},
    ]
    args = detect_constructor_args(fields, inspection_mode="pydantic", init_params=[])
    assert len(args) <= 3


def test_detect_constructor_args_init_signature():
    """Non-Pydantic classes use init_params."""
    from scripts.seed_generator import detect_constructor_args

    init_params = [
        {"name": "agent", "required": True, "type_str": "BaseAgent", "position": 0},
        {"name": "app_name", "required": True, "type_str": "str", "position": 1},
        {"name": "session_service", "required": False, "type_str": "BaseSessionService", "position": 2},
    ]
    args = detect_constructor_args([], inspection_mode="init_signature", init_params=init_params)
    assert args == ["agent", "app_name"]
```

**Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py::test_detect_constructor_args_pydantic -v
```

Expected: FAIL

**Step 3: Implement constructor arg detection**

Add to `scripts/seed_generator.py`:

```python
# ---------------------------------------------------------------------------
# CONSTRUCTOR ARG DETECTION
# ---------------------------------------------------------------------------

_MAX_CONSTRUCTOR_ARGS = 3


def detect_constructor_args(
    fields: list[dict],
    inspection_mode: str,
    init_params: list[dict],
) -> list[str]:
    """Determine which fields should be constructor arguments.

    Pydantic: required fields (no default), capped at MAX_CONSTRUCTOR_ARGS.
    Non-Pydantic: required __init__ params, capped at MAX_CONSTRUCTOR_ARGS.
    """
    if inspection_mode == "init_signature":
        required = [
            p["name"] for p in init_params
            if p.get("required", False)
        ]
        return required[:_MAX_CONSTRUCTOR_ARGS]

    # Pydantic mode
    required = [
        f["name"] for f in fields
        if f.get("required", False)
    ]
    return required[:_MAX_CONSTRUCTOR_ARGS]
```

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(seed_generator): constructor arg detection for Pydantic and non-Pydantic"
```

______________________________________________________________________

## Task 9: Seed generator — output module grouping

Build the logic that groups classes into output modules.

**Files:**

- Modify: `scripts/seed_generator.py`
- Modify: `tests/test_seed_generator.py`

**Step 1: Write module grouping tests**

Add to `tests/test_seed_generator.py`:

```python
def test_determine_output_module_agents():
    from scripts.seed_generator import determine_output_module
    assert determine_output_module("LlmAgent", "agent", "google.adk.agents.llm_agent") == "agent"
    assert determine_output_module("SequentialAgent", "agent", "google.adk.agents.sequential_agent") == "workflow"
    assert determine_output_module("ParallelAgent", "agent", "google.adk.agents.parallel_agent") == "workflow"
    assert determine_output_module("LoopAgent", "agent", "google.adk.agents.loop_agent") == "workflow"
    assert determine_output_module("BaseAgent", "agent", "google.adk.agents.base_agent") == "agent"


def test_determine_output_module_by_tag():
    from scripts.seed_generator import determine_output_module
    assert determine_output_module("RunConfig", "config", "google.adk.agents.run_config") == "config"
    assert determine_output_module("App", "runtime", "google.adk.apps.app") == "runtime"
    assert determine_output_module("Runner", "runtime", "google.adk.runners") == "runtime"
    assert determine_output_module("BuiltInCodeExecutor", "executor", "google.adk.code_executors") == "executor"
    assert determine_output_module("PlanReActPlanner", "planner", "google.adk.planners") == "planner"
```

**Step 2: Implement**

Add to `scripts/seed_generator.py`:

```python
# ---------------------------------------------------------------------------
# OUTPUT MODULE GROUPING
# ---------------------------------------------------------------------------

_WORKFLOW_AGENTS = frozenset({"SequentialAgent", "ParallelAgent", "LoopAgent"})

_TAG_TO_MODULE: dict[str, str] = {
    "agent": "agent",
    "config": "config",
    "runtime": "runtime",
    "executor": "executor",
    "planner": "planner",
    "service": "service",
    "plugin": "plugin",
    "tool": "tool",
}


def determine_output_module(class_name: str, tag: str, module: str) -> str:
    """Determine which output module a builder should be placed in."""
    # Special case: workflow agents go to workflow module
    if class_name in _WORKFLOW_AGENTS:
        return "workflow"

    return _TAG_TO_MODULE.get(tag, tag)
```

**Step 3: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py -v
```

Expected: ALL PASS

**Step 4: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(seed_generator): output module grouping logic"
```

______________________________________________________________________

## Task 10: Seed generator — extra methods engine

Build the logic that generates extra methods (step, branch, member, tool, apply) based on class type.

**Files:**

- Modify: `scripts/seed_generator.py`
- Modify: `tests/test_seed_generator.py`

**Step 1: Write extra method tests**

Add to `tests/test_seed_generator.py`:

```python
def test_generate_extras_sequential_agent():
    from scripts.seed_generator import generate_extras
    extras = generate_extras("SequentialAgent", "agent", "google.adk.agents.SequentialAgent")
    names = [e["name"] for e in extras]
    assert "step" in names


def test_generate_extras_parallel_agent():
    from scripts.seed_generator import generate_extras
    extras = generate_extras("ParallelAgent", "agent", "google.adk.agents.ParallelAgent")
    names = [e["name"] for e in extras]
    assert "branch" in names


def test_generate_extras_llm_agent():
    from scripts.seed_generator import generate_extras
    extras = generate_extras("LlmAgent", "agent", "google.adk.agents.LlmAgent")
    names = [e["name"] for e in extras]
    assert "tool" in names
    assert "apply" in names


def test_generate_extras_non_agent():
    from scripts.seed_generator import generate_extras
    extras = generate_extras("RunConfig", "config", "google.adk.agents.RunConfig")
    assert extras == []
```

**Step 2: Implement**

Add to `scripts/seed_generator.py`:

```python
# ---------------------------------------------------------------------------
# EXTRA METHODS ENGINE
# ---------------------------------------------------------------------------

def generate_extras(class_name: str, tag: str, source_class: str) -> list[dict]:
    """Generate extra methods based on class type. Mechanical rules only."""
    extras = []

    if tag != "agent":
        return extras

    # Workflow agents: step/branch for sub_agents
    if class_name in ("SequentialAgent", "LoopAgent"):
        extras.append({
            "name": "step",
            "signature": "(self, agent: BaseAgent) -> Self",
            "doc": f"Append an agent as the next step.",
            "behavior": "list_append",
            "target_field": "sub_agents",
        })
    elif class_name == "ParallelAgent":
        extras.append({
            "name": "branch",
            "signature": "(self, agent: BaseAgent) -> Self",
            "doc": "Add a parallel branch agent.",
            "behavior": "list_append",
            "target_field": "sub_agents",
        })
    elif class_name == "LlmAgent":
        # Single tool append
        extras.append({
            "name": "tool",
            "signature": "(self, fn_or_tool: Callable | BaseTool) -> Self",
            "doc": "Add a single tool.",
            "behavior": "list_append",
            "target_field": "tools",
        })
        # Middleware apply
        extras.append({
            "name": "apply",
            "signature": "(self, stack: MiddlewareStack) -> Self",
            "doc": "Apply a reusable middleware stack.",
        })
        # Member (for Team/coordinator pattern — LlmAgent with sub_agents)
        extras.append({
            "name": "member",
            "signature": "(self, agent: BaseAgent) -> Self",
            "doc": "Add a member agent for delegation.",
            "behavior": "list_append",
            "target_field": "sub_agents",
        })

    return extras
```

**Step 3: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py -v
```

Expected: ALL PASS

**Step 4: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(seed_generator): extra methods engine for step/branch/tool/apply"
```

______________________________________________________________________

## Task 11: Seed generator — TOML emission

Build the function that takes all the computed data and emits a valid seed.toml file.

**Files:**

- Modify: `scripts/seed_generator.py`
- Modify: `tests/test_seed_generator.py`

**Step 1: Write TOML emission test**

Add to `tests/test_seed_generator.py`:

```python
def test_emit_seed_toml_structure():
    """Emitted TOML must be parseable and contain expected sections."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    from scripts.seed_generator import emit_seed_toml

    # Minimal builder data
    builders = [
        {
            "name": "Agent",
            "source_class": "google.adk.agents.LlmAgent",
            "output_module": "agent",
            "doc": "Fluent builder for LlmAgent.",
            "constructor_args": ["name", "model"],
            "aliases": {"instruct": "instruction"},
            "callback_aliases": {"before_model": "before_model_callback"},
            "extra_skip_fields": [],
            "terminals": [{"name": "build", "returns": "LlmAgent"}],
            "extras": [],
            "tag": "agent",
        }
    ]
    global_config = {
        "skip_fields": ["parent_agent", "model_config"],
        "additive_fields": ["before_model_callback"],
        "list_extend_fields": ["tools"],
    }

    toml_str = emit_seed_toml(builders, global_config, adk_version="1.25.0")

    # Must be parseable TOML
    parsed = tomllib.loads(toml_str)

    assert "meta" in parsed
    assert "global" in parsed
    assert "builders" in parsed
    assert "Agent" in parsed["builders"]
    assert parsed["builders"]["Agent"]["source_class"] == "google.adk.agents.LlmAgent"
    assert parsed["builders"]["Agent"]["constructor_args"] == ["name", "model"]
    assert parsed["builders"]["Agent"]["aliases"]["instruct"] == "instruction"


def test_emit_seed_toml_multiple_builders():
    """Multiple builders in the same TOML file."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    from scripts.seed_generator import emit_seed_toml

    builders = [
        {
            "name": "Agent",
            "source_class": "google.adk.agents.LlmAgent",
            "output_module": "agent",
            "doc": "Builder for LlmAgent.",
            "constructor_args": ["name", "model"],
            "aliases": {},
            "callback_aliases": {},
            "extra_skip_fields": [],
            "terminals": [{"name": "build", "returns": "LlmAgent"}],
            "extras": [],
            "tag": "agent",
        },
        {
            "name": "Pipeline",
            "source_class": "google.adk.agents.SequentialAgent",
            "output_module": "workflow",
            "doc": "Builder for SequentialAgent.",
            "constructor_args": ["name"],
            "aliases": {},
            "callback_aliases": {},
            "extra_skip_fields": [],
            "terminals": [{"name": "build", "returns": "SequentialAgent"}],
            "extras": [{"name": "step", "signature": "(self, agent) -> Self", "doc": "Add step.", "behavior": "list_append", "target_field": "sub_agents"}],
            "tag": "agent",
        },
    ]
    global_config = {
        "skip_fields": ["parent_agent"],
        "additive_fields": [],
        "list_extend_fields": [],
    }

    toml_str = emit_seed_toml(builders, global_config, adk_version="1.25.0")
    parsed = tomllib.loads(toml_str)

    assert "Agent" in parsed["builders"]
    assert "Pipeline" in parsed["builders"]
    assert parsed["builders"]["Pipeline"]["terminals"][0]["name"] == "build"
```

**Step 2: Implement TOML emission**

Add to `scripts/seed_generator.py`:

```python
# ---------------------------------------------------------------------------
# TOML EMISSION
# ---------------------------------------------------------------------------

def _toml_value(val) -> str:
    """Format a Python value as a TOML literal."""
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, list):
        if not val:
            return "[]"
        if all(isinstance(v, str) for v in val):
            items = ", ".join(f'"{v}"' for v in val)
            return f"[{items}]"
        return repr(val)
    return repr(val)


def emit_seed_toml(
    builders: list[dict],
    global_config: dict,
    adk_version: str = "unknown",
) -> str:
    """Emit a complete seed.toml string from computed builder data."""
    lines = []

    # Header
    lines.append("# AUTO-GENERATED by seed_generator.py — regenerate with: make seed")
    lines.append("")

    # [meta]
    lines.append("[meta]")
    lines.append(f'adk_package = "google-adk"')
    lines.append(f'min_adk_version = "{adk_version}"')
    lines.append(f'min_python = "3.11"')
    lines.append(f'output_package = "adk_fluent"')
    lines.append(f'output_dir = "src/adk_fluent"')
    lines.append("")

    # [global]
    lines.append("[global]")
    lines.append(f"skip_fields = {_toml_value(global_config.get('skip_fields', []))}")
    lines.append(f"additive_fields = {_toml_value(global_config.get('additive_fields', []))}")
    lines.append(f"list_extend_fields = {_toml_value(global_config.get('list_extend_fields', []))}")
    lines.append("")

    # Each builder
    for builder in builders:
        name = builder["name"]
        lines.append(f"# {'=' * 60}")
        lines.append(f"# BUILDER: {name}")
        lines.append(f"# {'=' * 60}")

        lines.append(f"[builders.{name}]")
        lines.append(f'source_class = "{builder["source_class"]}"')
        lines.append(f'output_module = "{builder["output_module"]}"')
        lines.append(f'doc = "{builder["doc"]}"')
        lines.append(f'auto_tag = "{builder.get("tag", "")}"')
        lines.append(f"constructor_args = {_toml_value(builder['constructor_args'])}")
        lines.append(f"extra_skip_fields = {_toml_value(builder.get('extra_skip_fields', []))}")
        lines.append("")

        # Aliases
        aliases = builder.get("aliases", {})
        if aliases:
            lines.append(f"[builders.{name}.aliases]")
            for alias, field in sorted(aliases.items()):
                lines.append(f'{alias} = "{field}"')
            lines.append("")

        # Callback aliases
        cb_aliases = builder.get("callback_aliases", {})
        if cb_aliases:
            lines.append(f"[builders.{name}.callback_aliases]")
            for alias, field in sorted(cb_aliases.items()):
                lines.append(f'{alias} = "{field}"')
            lines.append("")

        # Terminals
        for terminal in builder.get("terminals", []):
            lines.append(f"[[builders.{name}.terminals]]")
            lines.append(f'name = "{terminal["name"]}"')
            if "returns" in terminal:
                lines.append(f'returns = "{terminal["returns"]}"')
            if "signature" in terminal:
                lines.append(f'signature = "{terminal["signature"]}"')
            if "doc" in terminal:
                lines.append(f'doc = "{terminal["doc"]}"')
            lines.append("")

        # Extras
        for extra in builder.get("extras", []):
            lines.append(f"[[builders.{name}.extras]]")
            lines.append(f'name = "{extra["name"]}"')
            if "signature" in extra:
                lines.append(f'signature = "{extra["signature"]}"')
            if "doc" in extra:
                lines.append(f'doc = "{extra["doc"]}"')
            if "behavior" in extra:
                lines.append(f'behavior = "{extra["behavior"]}"')
            if "target_field" in extra:
                lines.append(f'target_field = "{extra["target_field"]}"')
            lines.append("")

    return "\n".join(lines)
```

**Step 3: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py -v
```

Expected: ALL PASS

**Step 4: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(seed_generator): TOML emission engine"
```

______________________________________________________________________

## Task 12: Seed generator — main orchestrator and CLI

Wire everything together: read manifest.json, classify all classes, compute field policies / aliases / constructor args / extras, and emit seed.toml.

**Files:**

- Modify: `scripts/seed_generator.py`
- Modify: `tests/test_seed_generator.py`

**Step 1: Write integration test**

Add to `tests/test_seed_generator.py`:

```python
def test_generate_seed_from_manifest_end_to_end(tmp_path):
    """Full pipeline: manifest.json → seed.toml with real ADK data."""
    import json
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    from scripts.scanner import scan_all, manifest_to_dict
    from scripts.seed_generator import generate_seed_from_manifest

    # Step 1: Scan ADK
    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)

    # Step 2: Generate seed
    toml_str = generate_seed_from_manifest(manifest_dict)

    # Step 3: Parse the result
    parsed = tomllib.loads(toml_str)

    # Must have meta and global
    assert "meta" in parsed
    assert "global" in parsed
    assert "builders" in parsed

    # Must have LlmAgent builder
    builder_names = list(parsed["builders"].keys())
    # Check at least some core builders exist
    source_classes = {
        b.get("source_class", "") for b in parsed["builders"].values()
    }
    assert "google.adk.agents.llm_agent.LlmAgent" in source_classes or \
           any("LlmAgent" in sc for sc in source_classes)

    # Must have more than the original 7 hand-written builders
    assert len(builder_names) > 7, f"Only found {len(builder_names)} builders: {builder_names}"

    # Global policies must be populated
    assert len(parsed["global"]["skip_fields"]) > 0
    assert len(parsed["global"]["additive_fields"]) > 0
```

**Step 2: Implement the orchestrator**

Add to `scripts/seed_generator.py`:

```python
# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------

def _builder_name_for_class(class_name: str, tag: str) -> str:
    """Determine the builder name for a class.

    Most classes keep their original name. Some get ergonomic renames.
    """
    _RENAMES = {
        "LlmAgent": "Agent",
        "SequentialAgent": "Pipeline",
        "ParallelAgent": "FanOut",
        "LoopAgent": "Loop",
    }
    return _RENAMES.get(class_name, class_name)


def generate_seed_from_manifest(manifest: dict) -> str:
    """Main entry point: read a manifest dict and produce seed.toml content."""
    adk_version = manifest.get("adk_version", "unknown")
    classes = manifest.get("classes", [])

    # Collect global policies across all classes
    all_skip_fields = set(_ALWAYS_SKIP)
    all_additive_fields = set()
    all_list_extend_fields = set(_LIST_EXTEND_FIELDS)

    builders = []

    for cls_data in classes:
        name = cls_data["name"]
        module = cls_data.get("module", "")
        bases = cls_data.get("bases", [])
        mro = cls_data.get("mro", [])
        fields = cls_data.get("fields", [])
        inspection_mode = cls_data.get("inspection_mode", "pydantic")
        init_params = cls_data.get("init_params", [])
        qualname = cls_data.get("qualname", f"{module}.{name}")

        # Step 1: Classify
        tag = classify_class(name, module, mro)

        # Step 2: Filter — only builder-worthy classes
        if not is_builder_worthy(tag):
            continue

        # Step 3: Determine constructor args
        constructor_args = detect_constructor_args(fields, inspection_mode, init_params)

        # Step 4: Compute field policies
        normal_fields = []
        additive_fields = []
        skip_fields = []
        list_extend_fields = []

        for f in fields:
            policy = get_field_policy(
                f["name"],
                f.get("type_str", "Any"),
                f.get("is_callback", False),
            )
            if policy == "skip":
                skip_fields.append(f["name"])
            elif policy == "additive":
                additive_fields.append(f["name"])
                all_additive_fields.add(f["name"])
            elif policy == "list_extend":
                list_extend_fields.append(f["name"])
            else:
                normal_fields.append(f["name"])

        # Step 5: Generate aliases
        aliases = generate_aliases(normal_fields)
        callback_aliases = generate_callback_aliases(additive_fields)

        # Step 6: Determine output module
        output_module = determine_output_module(name, tag, module)

        # Step 7: Generate extras
        extras = generate_extras(name, tag, qualname)

        # Step 8: Builder name
        builder_name = _builder_name_for_class(name, tag)

        # Step 9: Determine source class
        source_class = qualname

        # Step 10: Terminal method — always build()
        source_short = name
        terminals = [{"name": "build", "returns": source_short, "doc": f"Resolve into a native ADK {source_short}."}]

        # Step 11: Extra skip (constructor args are also skipped as fluent methods)
        extra_skip = [f for f in constructor_args if f not in list(_ALWAYS_SKIP)]

        builders.append({
            "name": builder_name,
            "source_class": source_class,
            "output_module": output_module,
            "doc": f"Fluent builder for {source_short}.",
            "constructor_args": constructor_args,
            "aliases": aliases,
            "callback_aliases": callback_aliases,
            "extra_skip_fields": extra_skip,
            "terminals": terminals,
            "extras": extras,
            "tag": tag,
        })

    global_config = {
        "skip_fields": sorted(all_skip_fields),
        "additive_fields": sorted(all_additive_fields),
        "list_extend_fields": sorted(all_list_extend_fields),
    }

    return emit_seed_toml(builders, global_config, adk_version=adk_version)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate seed.toml from manifest.json"
    )
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    with open(args.manifest) as f:
        manifest = json.load(f)

    toml_str = generate_seed_from_manifest(manifest)

    if args.output:
        Path(args.output).write_text(toml_str)
        print(f"Seed written to {args.output}", file=sys.stderr)
    else:
        print(toml_str)


if __name__ == "__main__":
    main()
```

**Step 3: Run integration test**

```bash
source .venv/bin/activate && python -m pytest tests/test_seed_generator.py::test_generate_seed_from_manifest_end_to_end -v
```

Expected: PASS

**Step 4: Run end-to-end manually**

```bash
source .venv/bin/activate && python scripts/scanner.py -o manifest.json
source .venv/bin/activate && python scripts/seed_generator.py manifest.json -o seeds/seed.toml
```

Expected: Both commands succeed. Inspect `seeds/seed.toml` to verify it has many builder sections.

**Step 5: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(seed_generator): complete orchestrator and CLI"
```

______________________________________________________________________

## Task 13: Update Makefile

Add the `seed` target and update `all` to include it.

**Files:**

- Modify: `Makefile`

**Step 1: Update Makefile**

Update the `all` target and add `seed`:

```makefile
all: scan seed generate

seed: $(MANIFEST)
	@echo "Generating seed.toml from manifest..."
	@python $(SEED_GEN) $(MANIFEST) -o $(SEED)
```

Add the `SEED_GEN` variable:

```makefile
SEED_GEN      := scripts/seed_generator.py
```

**Step 2: Verify the pipeline runs**

```bash
source .venv/bin/activate && make all
```

Expected: scan → seed → generate all succeed in sequence.

**Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add seed target to Makefile, wire full auto-pipeline"
```

______________________________________________________________________

## Task 14: Generator updates — handle init_signature mode

Update the generator to handle non-Pydantic classes (where `__getattr__` validates against `init_params` instead of `model_fields`).

**Files:**

- Modify: `scripts/generator.py`

**Step 1: Update gen_getattr_method**

The `__getattr__` method for non-Pydantic classes should validate against a static set of known parameter names (from the manifest) instead of `SourceClass.model_fields`.

Add a branch in `gen_getattr_method`:

For `inspection_mode == "init_signature"`, generate:

```python
_KNOWN_PARAMS: set[str] = {"agent", "app_name", "session_service", ...}

def __getattr__(self, name: str):
    if name.startswith("_"):
        raise AttributeError(name)
    field_name = _ALIASES.get(name, name)
    if field_name not in _KNOWN_PARAMS:
        raise AttributeError(f"'{name}' is not a recognized parameter. Available: ...")
    def _setter(value):
        self._config[field_name] = value
        return self
    return _setter
```

This requires the `BuilderSpec` to carry an `inspection_mode` and the `gen_runtime_module` to emit a `_KNOWN_PARAMS` set.

**Step 2: Update gen_build_method for non-Pydantic**

For non-Pydantic classes, `build()` constructs via `SourceClass(**config)` but there's no `model_fields` at runtime. The build method stays the same — `SourceClass(**config)` works for both.

**Step 3: Test end-to-end**

```bash
source .venv/bin/activate && make all
```

Expected: Full pipeline runs, generates code for both Pydantic and non-Pydantic builders.

**Step 4: Commit**

```bash
git add scripts/generator.py
git commit -m "feat(generator): handle init_signature mode for non-Pydantic builders"
```

______________________________________________________________________

## Task 15: Full pipeline verification

Run the entire pipeline end-to-end and verify the output.

**Files:**

- None modified — verification only

**Step 1: Run full pipeline**

```bash
source .venv/bin/activate && make all
```

**Step 2: Inspect generated seed.toml**

```bash
wc -l seeds/seed.toml
head -100 seeds/seed.toml
```

Expected: seed.toml has many more sections than the original 7 builders.

**Step 3: Inspect generated code**

```bash
ls -la src/adk_fluent/
wc -l src/adk_fluent/*.py src/adk_fluent/*.pyi 2>/dev/null
```

Expected: Multiple .py and .pyi files generated.

**Step 4: Count builders**

```bash
source .venv/bin/activate && python -c "
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open('seeds/seed.toml', 'rb') as f:
    seed = tomllib.load(f)
builders = seed.get('builders', {})
print(f'Total builders: {len(builders)}')
for name, cfg in sorted(builders.items()):
    tag = cfg.get('auto_tag', '?')
    src = cfg.get('source_class', '?')
    print(f'  {name:30s} [{tag:10s}] → {src}')
"
```

Expected: Shows all generated builders with their tags and source classes.

**Step 5: Run all tests**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

Expected: All scanner and seed generator tests pass.

**Step 6: Commit everything**

```bash
git add -A
git commit -m "feat: complete full auto-pipeline — scanner → seed_generator → generator"
```

______________________________________________________________________

## Task 16: Package setup — pyproject.toml

Set up the project as a proper installable Python package with pyproject.toml.

**Files:**

- Create: `pyproject.toml`
- Create: `src/adk_fluent/__init__.py` (if not already generated)
- Create: `README.md` (minimal, required by PyPI)
- Create: `LICENSE` (MIT)

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "adk-fluent"
version = "0.1.0"
description = "Fluent builder API for Google's Agent Development Kit (ADK)"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "adk-fluent contributors" },
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Typing :: Typed",
]
keywords = ["adk", "google", "agents", "fluent", "builder", "llm"]

dependencies = [
    "google-adk>=1.20.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pyright>=1.1",
    "tomli>=2.0; python_version < '3.11'",
]

[project.urls]
Homepage = "https://github.com/YOUR_ORG/adk-fluent"
Repository = "https://github.com/YOUR_ORG/adk-fluent"
Issues = "https://github.com/YOUR_ORG/adk-fluent/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/adk_fluent"]

[tool.pyright]
include = ["src"]
pythonVersion = "3.11"
typeCheckingMode = "strict"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

**Step 2: Create minimal README.md**

```markdown
# adk-fluent

Fluent builder API for Google's Agent Development Kit (ADK). Reduces agent creation from 22+ lines to 1-3 lines while maintaining 100% ADK CLI compatibility.

## Install

pip install adk-fluent

## Quick Start

from adk_fluent import Agent

response = Agent("helper", "gemini-2.5-flash").ask("What is the capital of France?")
```

**Step 3: Create LICENSE file**

MIT license.

**Step 4: Verify the package builds**

```bash
source .venv/bin/activate && uv pip install hatch
source .venv/bin/activate && hatch build
```

Expected: Creates `dist/adk_fluent-0.1.0-py3-none-any.whl` and `dist/adk_fluent-0.1.0.tar.gz`.

**Step 5: Verify the package installs locally**

```bash
source .venv/bin/activate && uv pip install dist/adk_fluent-0.1.0-py3-none-any.whl
source .venv/bin/activate && python -c "from adk_fluent import Agent; print('Import OK')"
```

Expected: Import succeeds.

**Step 6: Commit**

```bash
git add pyproject.toml README.md LICENSE
git commit -m "chore: add pyproject.toml for pip packaging"
```

______________________________________________________________________

## Task 17: PyPI publication setup

Set up the tooling to publish to PyPI (both TestPyPI for testing and real PyPI for release).

**Files:**

- Create: `.github/workflows/publish.yml`
- Modify: `Makefile` (add publish targets)

**Step 1: Create GitHub Actions publish workflow**

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

permissions:
  id-token: write  # Required for trusted publishing

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install google-adk hatch
          pip install -e ".[dev]"

      - name: Run full pipeline
        run: |
          python scripts/scanner.py -o manifest.json
          python scripts/seed_generator.py manifest.json -o seeds/seed.toml
          python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated

      - name: Run tests
        run: pytest tests/ -v

      - name: Build package
        run: hatch build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # Uses trusted publishing — configure at pypi.org/manage/project/adk-fluent/settings/publishing/

  test-publish:
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install and build
        run: |
          pip install google-adk hatch
          python scripts/scanner.py -o manifest.json
          python scripts/seed_generator.py manifest.json -o seeds/seed.toml
          python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent
          hatch build

      - name: Publish to TestPyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
```

**Step 2: Add Makefile publish targets**

Add to `Makefile`:

```makefile
# --- Package build ---
build: all
	@echo "Building package..."
	@hatch build

# --- Publish to TestPyPI ---
publish-test: build
	@echo "Publishing to TestPyPI..."
	@hatch publish -r test

# --- Publish to PyPI ---
publish: build
	@echo "Publishing to PyPI..."
	@hatch publish
```

**Step 3: Document the publication process**

The publication workflow:

1. Developer runs `make all` locally to verify pipeline
1. Developer runs `make test` to verify tests pass
1. Developer bumps version in `pyproject.toml`
1. Developer creates a GitHub release (tag: `v0.1.0`)
1. GitHub Actions automatically: runs pipeline → tests → builds → publishes to PyPI

For first-time PyPI setup:

1. Create account at pypi.org
1. Create project `adk-fluent`
1. Configure trusted publishing: Settings → Publishing → Add GitHub Actions publisher
1. Set repository owner, name, workflow filename (`publish.yml`)

**Step 4: Commit**

```bash
git add .github/workflows/publish.yml Makefile
git commit -m "chore: add PyPI publication workflow and Makefile targets"
```

______________________________________________________________________

## Task 18: ADK ecosystem registration

Make adk-fluent discoverable as an ADK community extension.

**Files:**

- Modify: `pyproject.toml` (entry points)
- Modify: `README.md` (badges, usage examples)

**Step 1: Add entry points for discoverability**

Add to `pyproject.toml`:

```toml
[project.entry-points."adk_extensions"]
fluent = "adk_fluent"
```

This is a standard setuptools entry point pattern. If the ADK ecosystem adopts a plugin registry, this makes adk-fluent auto-discoverable. Even without a registry, `pip show adk-fluent` and `importlib.metadata.entry_points(group="adk_extensions")` will find it.

**Step 2: Add PyPI classifiers and metadata**

Ensure `pyproject.toml` has:

```toml
classifiers = [
    # ... existing ...
    "Framework :: Pydantic",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]
```

**Step 3: Verify package metadata**

```bash
source .venv/bin/activate && uv pip install -e ".[dev]"
source .venv/bin/activate && python -c "
from importlib.metadata import metadata
m = metadata('adk-fluent')
print(f'Name: {m[\"Name\"]}')
print(f'Version: {m[\"Version\"]}')
print(f'Summary: {m[\"Summary\"]}')
print(f'Requires: {m.get_all(\"Requires-Dist\")}')
"
```

Expected: Correct metadata displayed.

**Step 4: Commit**

```bash
git add pyproject.toml README.md
git commit -m "chore: add ADK ecosystem entry points and metadata"
```
