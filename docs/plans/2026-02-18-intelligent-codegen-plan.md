# Intelligent Codegen Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the codegen pipeline from hard-coded lookup tables + string concatenation into an inference engine + structured IR + reactive pipeline — so upstream ADK changes are handled automatically and the manual override surface shrinks to genuine exceptions only.

**Architecture:** Three phases, each independently valuable. Phase A replaces the seed generator's hard-coded dictionaries with type-driven inference rules that derive field policies, aliases, and extras from manifest type information. Phase B replaces generator.py's f-string emission with a structured Code IR that validates before emitting and supports multiple output targets from one representation. Phase C adds content-addressed caching and dependency tracking so only changed builders are regenerated.

**Tech Stack:** Python 3.11+, dataclasses for IR nodes, `ast` module for validation, hashlib for content addressing. No new dependencies.

---

## Phase A: Inference Engine

**Thesis:** Most of what lives in `_ALWAYS_SKIP`, `_LIST_EXTEND_FIELDS`, `_FIELD_ALIAS_TABLE`, and `generate_extras()` can be derived from the manifest's type information. The manual override file should shrink from 179 lines to ~40 lines (only runtime helpers and genuine human preferences).

### Task A1: Type-Driven Field Policy Inference

**Files:**
- Modify: `scripts/seed_generator.py:92-122` (field policy engine)
- Modify: `tests/test_seed_generator.py:104-128` (field policy tests)

**Step 1: Write failing tests for type-based inference**

Add tests that prove field policy can be derived from `type_str` alone, without hard-coded field name sets:

```python
# tests/test_seed_generator.py — append after existing tests

# --- Type-Driven Field Policies ---
def test_field_policy_infers_list_extend_from_type():
    """Any list[X] field should get list_extend policy, not just hard-coded names."""
    from scripts.seed_generator import infer_field_policy

    # Known list fields
    assert infer_field_policy("tools", "list[BaseTool]", False) == "list_extend"
    assert infer_field_policy("sub_agents", "list[BaseAgent]", False) == "list_extend"
    # NEW list field that doesn't exist yet — should still be inferred
    assert infer_field_policy("artifacts", "list[Artifact]", False) == "list_extend"
    assert infer_field_policy("examples", "list[Example]", False) == "list_extend"


def test_field_policy_infers_additive_from_callback():
    """Any Callable field with _callback suffix should be additive."""
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("before_model_callback", "Callable | None", True) == "additive"
    # NEW callback that doesn't exist yet
    assert infer_field_policy("on_error_callback", "Callable | None", True) == "additive"


def test_field_policy_infers_skip_from_internals():
    """Pydantic internals and private fields are skipped by structure, not name."""
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("model_config", "ConfigDict", False) == "skip"
    assert infer_field_policy("model_fields", "dict", False) == "skip"
    assert infer_field_policy("_private", "str", False) == "skip"
    assert infer_field_policy("parent_agent", "BaseAgent | None", False, is_parent_ref=True) == "skip"


def test_field_policy_normal_fallback():
    """Non-list, non-callback, non-internal fields are normal."""
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("instruction", "str | None", False) == "normal"
    assert infer_field_policy("temperature", "float", False) == "normal"


def test_field_policy_list_of_primitives_is_normal():
    """list[str] should be normal (not list_extend) — no singular adder needed."""
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("tags", "list[str]", False) == "normal"
    assert infer_field_policy("names", "list[int]", False) == "normal"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_seed_generator.py::test_field_policy_infers_list_extend_from_type -v`
Expected: FAIL — `infer_field_policy` does not exist

**Step 3: Implement `infer_field_policy`**

Replace the hard-coded `get_field_policy` with a type-driven version in `scripts/seed_generator.py`:

```python
# Pydantic model internals — always skip regardless of name
_PYDANTIC_INTERNALS = frozenset({
    "model_config", "model_fields", "model_computed_fields",
    "model_post_init", "model_validators",
})

# Primitive types that don't need singular adders even in lists
_PRIMITIVE_TYPES = frozenset({"str", "int", "float", "bool", "bytes"})


def _is_list_of_complex_type(type_str: str) -> bool:
    """Return True if type_str is list[X] where X is not a primitive."""
    ts = type_str.strip()
    if not ts.startswith("list["):
        return False
    inner = ts[5:].rstrip("]").strip()
    # Strip Optional/Union wrappers
    inner = inner.split("|")[0].strip()
    return inner.lower() not in _PRIMITIVE_TYPES


def infer_field_policy(
    field_name: str,
    type_str: str,
    is_callback: bool,
    *,
    is_parent_ref: bool = False,
) -> str:
    """Infer field policy from type information, not hard-coded name sets.

    Rules (checked in order):
    1. Private fields (starts with _) → skip
    2. Pydantic internals (model_config, etc.) → skip
    3. Parent references → skip
    4. Callable with _callback suffix → additive
    5. list[ComplexType] → list_extend
    6. Everything else → normal
    """
    # Rule 1: Private
    if field_name.startswith("_"):
        return "skip"
    # Rule 2: Pydantic internals
    if field_name in _PYDANTIC_INTERNALS:
        return "skip"
    # Rule 3: Parent references (detected from MRO, not name)
    if is_parent_ref:
        return "skip"
    # Rule 4: Callbacks
    if is_callback and "_callback" in field_name:
        return "additive"
    # Rule 5: Lists of complex types
    if _is_list_of_complex_type(type_str):
        return "list_extend"
    # Rule 6: Default
    return "normal"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_seed_generator.py -k "infer_field_policy" -v`
Expected: All PASS

**Step 5: Wire `infer_field_policy` into the orchestrator**

Replace the call to `get_field_policy` in `generate_seed_from_manifest()` (line ~500) with `infer_field_policy`. Detect `is_parent_ref` by checking if field type references a class in the builder's own MRO:

```python
# In generate_seed_from_manifest(), replace the field policy loop:
for f in fields:
    fname = f["name"]
    ftype = f.get("type_str", "")
    is_cb = f.get("is_callback", False)
    # Detect parent references: field type contains a class from our MRO
    is_parent = fname == "parent_agent"  # Known parent ref pattern
    policy = infer_field_policy(fname, ftype, is_cb, is_parent_ref=is_parent)
    # ... rest unchanged
```

**Step 6: Run full test suite**

Run: `uv run pytest tests/test_seed_generator.py -v`
Expected: All existing tests still pass + new tests pass

**Step 7: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(codegen): replace hard-coded field policies with type-driven inference"
```

---

### Task A2: Morphological Alias Derivation

**Files:**
- Modify: `scripts/seed_generator.py:126-159` (alias engine)
- Modify: `tests/test_seed_generator.py:131-143` (alias tests)

**Step 1: Write failing tests for morphological aliases**

```python
# tests/test_seed_generator.py — append

# --- Morphological Alias Derivation ---
def test_derive_alias_strips_tion_suffix():
    """instruction → instruct, description → describe via suffix rules."""
    from scripts.seed_generator import derive_alias

    assert derive_alias("instruction") == "instruct"
    assert derive_alias("description") == "describe"
    assert derive_alias("configuration") == "configure"
    assert derive_alias("execution") == "execute"


def test_derive_alias_strips_ment_suffix():
    """deployment → deploy, assignment → assign via suffix rules."""
    from scripts.seed_generator import derive_alias

    assert derive_alias("deployment") == "deploy"
    assert derive_alias("assignment") == "assign"


def test_derive_alias_returns_none_for_short_names():
    """Short field names (model, name, tools) shouldn't be aliased."""
    from scripts.seed_generator import derive_alias

    assert derive_alias("model") is None
    assert derive_alias("name") is None
    assert derive_alias("tools") is None


def test_derive_alias_returns_none_for_no_pattern():
    """Fields that don't match any suffix pattern return None."""
    from scripts.seed_generator import derive_alias

    assert derive_alias("temperature") is None
    assert derive_alias("max_tokens") is None


def test_derive_aliases_batch():
    """Batch derivation matches existing alias table output."""
    from scripts.seed_generator import derive_aliases

    fields = ["instruction", "description", "model", "tools", "temperature"]
    aliases = derive_aliases(fields)
    assert aliases == {"instruct": "instruction", "describe": "description"}


def test_derive_alias_with_overrides():
    """Explicit overrides take precedence over derivation."""
    from scripts.seed_generator import derive_aliases

    fields = ["instruction", "output_key", "include_contents"]
    overrides = {"outputs": "output_key", "history": "include_contents"}
    aliases = derive_aliases(fields, overrides=overrides)
    assert aliases["instruct"] == "instruction"  # Derived
    assert aliases["outputs"] == "output_key"  # Override
    assert aliases["history"] == "include_contents"  # Override
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_seed_generator.py::test_derive_alias_strips_tion_suffix -v`
Expected: FAIL — `derive_alias` does not exist

**Step 3: Implement morphological alias derivation**

```python
# Suffix-stripping rules: (suffix_to_remove, replacement_suffix)
# Ordered by specificity — first match wins
_ALIAS_SUFFIX_RULES: list[tuple[str, str]] = [
    ("ription", "ribe"),       # description → describe
    ("ruction", "ruct"),       # instruction → instruct, construction → construct
    ("ution", "ute"),          # execution → execute, resolution → resolve
    ("ation", "ate"),          # configuration → configure, validation → validate
    ("tion", "t"),             # completion → complet (fallback, less common)
    ("ment", ""),              # deployment → deploy, assignment → assign
    ("ness", ""),              # readiness → readi (rare, usually not aliased)
]

# Minimum field name length to consider for aliasing
_MIN_ALIAS_SOURCE_LEN = 8


def derive_alias(field_name: str) -> str | None:
    """Derive a short alias from a field name using morphological suffix rules.

    Returns the alias string, or None if no rule matches or the name is too short.
    """
    if len(field_name) < _MIN_ALIAS_SOURCE_LEN:
        return None

    for suffix, replacement in _ALIAS_SUFFIX_RULES:
        if field_name.endswith(suffix):
            candidate = field_name[: -len(suffix)] + replacement
            # Sanity: alias must be shorter than original and non-empty
            if candidate and len(candidate) < len(field_name):
                return candidate

    return None


def derive_aliases(
    field_names: list[str],
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Derive aliases for a list of field names.

    Morphological rules produce candidates, explicit overrides take precedence.

    Returns: {alias: field_name}
    """
    aliases: dict[str, str] = {}

    # Apply morphological derivation
    for name in field_names:
        alias = derive_alias(name)
        if alias:
            aliases[alias] = name

    # Apply overrides (add or replace)
    if overrides:
        for alias, field_name in overrides.items():
            if field_name in field_names:
                aliases[alias] = field_name

    return aliases
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_seed_generator.py -k "derive_alias" -v`
Expected: All PASS

**Step 5: Wire into orchestrator**

Replace `generate_aliases()` call in `generate_seed_from_manifest()` with `derive_aliases()`. Keep `_EXTRA_ALIASES` as the override dict:

```python
# In generate_seed_from_manifest():
aliases = derive_aliases(all_field_names, overrides=_EXTRA_ALIASES)
```

**Step 6: Run full suite and verify seed.toml output is equivalent**

Run: `uv run pytest tests/test_seed_generator.py -v`
Run: `uv run python scripts/seed_generator.py manifest.json --merge seeds/seed.manual.toml | diff - seeds/seed.toml`
Expected: All pass. Seed output should be identical or differ only in newly-derived aliases.

**Step 7: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(codegen): derive aliases morphologically instead of lookup table"
```

---

### Task A3: Type-Driven Extras Inference

**Files:**
- Modify: `scripts/seed_generator.py:222-305` (extras engine)
- Modify: `tests/test_seed_generator.py:178-197` (extras tests)

**Step 1: Write failing tests**

```python
# tests/test_seed_generator.py — append

# --- Type-Driven Extras ---
def test_infer_extras_singular_adder_for_list_field():
    """Any list[X] field gets a singular .x() adder inferred automatically."""
    from scripts.seed_generator import infer_extras

    fields = [
        {"name": "tools", "type_str": "list[BaseTool]", "is_callback": False},
        {"name": "sub_agents", "type_str": "list[BaseAgent]", "is_callback": False},
    ]
    extras = infer_extras("SomeAgent", "agent", fields)

    tool_extra = next((e for e in extras if e["name"] == "tool"), None)
    assert tool_extra is not None
    assert tool_extra["behavior"] == "list_append"
    assert tool_extra["target_field"] == "tools"

    sub_agent_extra = next((e for e in extras if e["name"] == "sub_agent"), None)
    assert sub_agent_extra is not None
    assert sub_agent_extra["behavior"] == "list_append"
    assert sub_agent_extra["target_field"] == "sub_agents"


def test_infer_extras_step_for_sub_agents_in_sequential():
    """Sequential/Loop agents get .step() as an alias for sub_agents list append."""
    from scripts.seed_generator import infer_extras

    fields = [{"name": "sub_agents", "type_str": "list[BaseAgent]", "is_callback": False}]
    extras = infer_extras("SequentialAgent", "agent", fields)

    step = next((e for e in extras if e["name"] == "step"), None)
    assert step is not None
    assert step["target_field"] == "sub_agents"


def test_infer_extras_branch_for_parallel():
    """ParallelAgent gets .branch() for sub_agents."""
    from scripts.seed_generator import infer_extras

    fields = [{"name": "sub_agents", "type_str": "list[BaseAgent]", "is_callback": False}]
    extras = infer_extras("ParallelAgent", "agent", fields)

    branch = next((e for e in extras if e["name"] == "branch"), None)
    assert branch is not None


def test_infer_extras_no_duplicates_with_manual():
    """Manual extras override inferred ones — no duplicates."""
    from scripts.seed_generator import merge_extras

    inferred = [
        {"name": "tool", "behavior": "list_append", "target_field": "tools"},
    ]
    manual = [
        {"name": "tool", "behavior": "runtime_helper", "helper_func": "_add_tool",
         "signature": "(self, fn_or_tool, *, require_confirmation: bool = False) -> Self"},
    ]
    merged = merge_extras(inferred, manual)
    # Manual wins
    assert len([e for e in merged if e["name"] == "tool"]) == 1
    assert merged[0]["behavior"] == "runtime_helper"


def test_infer_extras_unknown_class_gets_generic_adders():
    """A brand-new ADK class with list fields gets adders without hard-coding."""
    from scripts.seed_generator import infer_extras

    fields = [
        {"name": "evaluators", "type_str": "list[BaseEvaluator]", "is_callback": False},
    ]
    extras = infer_extras("EvalSuite", "eval", fields)

    evaluator_extra = next((e for e in extras if e["name"] == "evaluator"), None)
    assert evaluator_extra is not None
    assert evaluator_extra["target_field"] == "evaluators"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_seed_generator.py::test_infer_extras_singular_adder_for_list_field -v`
Expected: FAIL — `infer_extras` does not exist

**Step 3: Implement type-driven extras inference**

```python
def _singular_name(plural_field: str) -> str:
    """Derive singular form: tools→tool, sub_agents→sub_agent, plugins→plugin."""
    if plural_field.endswith("s") and not plural_field.endswith("ss"):
        return plural_field[:-1]
    return plural_field


def _inner_type_name(type_str: str) -> str:
    """Extract inner type: list[BaseTool] → BaseTool."""
    if type_str.startswith("list["):
        return type_str[5:].rstrip("]").strip().split("|")[0].strip()
    return type_str


# Semantic naming overrides for well-known container patterns
_CONTAINER_ALIASES: dict[str, dict[str, str]] = {
    # class_name → {extra_name: "alias_name"}
    "SequentialAgent": {"sub_agent": "step"},
    "LoopAgent": {"sub_agent": "step"},
    "ParallelAgent": {"sub_agent": "branch"},
}


def infer_extras(
    class_name: str,
    tag: str,
    fields: list[dict],
) -> list[dict]:
    """Infer extra methods from field types.

    Rules:
    1. Any list[ComplexType] field → singular adder method
    2. Well-known container patterns get semantic aliases (step, branch)
    """
    extras: list[dict] = []
    seen_names: set[str] = set()

    for f in fields:
        fname = f["name"]
        ftype = f.get("type_str", "")

        if not _is_list_of_complex_type(ftype):
            continue

        singular = _singular_name(fname)
        inner_type = _inner_type_name(ftype)

        # Check for semantic alias
        aliases_for_class = _CONTAINER_ALIASES.get(class_name, {})
        method_name = aliases_for_class.get(singular, singular)

        if method_name not in seen_names:
            extras.append({
                "name": method_name,
                "signature": f"(self, item: {inner_type}) -> Self",
                "doc": f"Append to `{fname}` (lazy — resolved at .build() time).",
                "behavior": "list_append",
                "target_field": fname,
            })
            seen_names.add(method_name)

        # If alias differs from singular, also add singular as alias
        if method_name != singular and singular not in seen_names:
            extras.append({
                "name": singular,
                "signature": f"(self, item: {inner_type}) -> Self",
                "doc": f"Alias for .{method_name}() — append to `{fname}`.",
                "behavior": "list_append",
                "target_field": fname,
            })
            seen_names.add(singular)

    return extras


def merge_extras(inferred: list[dict], manual: list[dict]) -> list[dict]:
    """Merge inferred and manual extras. Manual wins on name conflicts."""
    manual_names = {e["name"] for e in manual}
    merged = [e for e in inferred if e["name"] not in manual_names]
    merged.extend(manual)
    return merged
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_seed_generator.py -k "infer_extras" -v`
Expected: All PASS

**Step 5: Wire into orchestrator**

Replace `generate_extras()` call with `infer_extras()` + `merge_extras()` for manual overlay:

```python
# In generate_seed_from_manifest():
inferred_extras = infer_extras(name, tag, fields)
extras = inferred_extras  # Manual merge happens in merge_manual_seed()
```

**Step 6: Run full suite + verify seed output**

Run: `uv run pytest tests/test_seed_generator.py -v`
Run: `uv run python scripts/seed_generator.py manifest.json -o /tmp/test_seed.toml --merge seeds/seed.manual.toml`
Expected: All pass. Output should be equivalent to current seed.toml with additional auto-inferred extras for classes that previously had none.

**Step 7: Commit**

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(codegen): infer extras from list field types instead of class-name switch"
```

---

### Task A4: Shrink seed.manual.toml to True Exceptions

**Files:**
- Modify: `seeds/seed.manual.toml`
- Modify: `scripts/seed_generator.py` (override format)
- Create: `tests/test_inference_coverage.py`

**Step 1: Write a coverage test that audits what's left in manual**

```python
# tests/test_inference_coverage.py

"""Verify that seed.manual.toml only contains true exceptions — things
that genuinely cannot be inferred from type information."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from pathlib import Path


def test_manual_seed_only_contains_non_inferrable_extras():
    """Every extra in seed.manual.toml should be a runtime_helper, dual_callback,
    deep_copy, deprecation_alias, or have a custom signature — i.e., things
    that need human judgment, not things derivable from types."""
    manual_path = Path("seeds/seed.manual.toml")
    with open(manual_path, "rb") as f:
        manual = tomllib.load(f)

    INFERRABLE_BEHAVIORS = {"list_append", "field_set"}

    for builder_name, config in manual.get("builders", {}).items():
        for extra in config.get("extras", []):
            behavior = extra.get("behavior", "custom")
            if behavior in INFERRABLE_BEHAVIORS:
                # These should have been removed — they're auto-inferred now
                assert False, (
                    f"seed.manual.toml[{builder_name}].extras has inferrable "
                    f"extra '{extra['name']}' with behavior '{behavior}'. "
                    f"This should be auto-inferred, not manually specified."
                )


def test_manual_seed_overrides_have_reasons():
    """Future: every manual override should document WHY it exists."""
    # This is aspirational — add 'reason' field to manual extras
    pass
```

**Step 2: Run test to see what needs removing**

Run: `uv run pytest tests/test_inference_coverage.py -v`
Expected: FAIL — identifies `list_append` and `field_set` extras in manual that are now inferrable.

**Step 3: Remove inferrable entries from seed.manual.toml**

Remove these entries from `seeds/seed.manual.toml` since they're now auto-inferred by `infer_extras`:
- `[[builders.Agent.extras]]` with `behavior = "list_append"` (tool as list_append, sub_agent as list_append)
- `[[builders.Pipeline.extras]]` step entries
- `[[builders.FanOut.extras]]` branch/step entries
- `[[builders.Loop.extras]]` step entries

Keep only runtime helpers, dual_callback, deep_copy, deprecation_alias, and field_set entries that have custom logic (context, show, hide, memory, etc.)

**Step 4: Run full test suite**

Run: `uv run pytest tests/ -v`
Run: `uv run python scripts/seed_generator.py manifest.json -o /tmp/test_seed.toml --merge seeds/seed.manual.toml && diff /tmp/test_seed.toml seeds/seed.toml`
Expected: All pass. Generated seed should be functionally identical (inferred extras replace manual ones).

**Step 5: Commit**

```bash
git add seeds/seed.manual.toml scripts/seed_generator.py tests/test_inference_coverage.py
git commit -m "refactor(codegen): remove inferrable extras from manual seed — now auto-derived"
```

---

### Task A5: Parent Reference Detection from MRO

**Files:**
- Modify: `scripts/seed_generator.py` (detect parent refs from MRO, not field name)
- Modify: `tests/test_seed_generator.py`

**Step 1: Write failing test**

```python
def test_detect_parent_ref_from_mro():
    """Fields whose type appears in the class's own MRO chain are parent refs."""
    from scripts.seed_generator import is_parent_reference

    mro = ["LlmAgent", "BaseAgent", "BaseModel"]
    assert is_parent_reference("parent_agent", "BaseAgent | None", mro) is True
    assert is_parent_reference("delegate", "BaseAgent | None", mro) is False  # name doesn't match
    assert is_parent_reference("model", "str", mro) is False
```

**Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_seed_generator.py::test_detect_parent_ref_from_mro -v`

**Step 3: Implement**

```python
def is_parent_reference(field_name: str, type_str: str, mro_chain: list[str]) -> bool:
    """Detect if a field is a parent/back-reference by checking if its type
    appears in the class's MRO and the field name suggests parentage."""
    parent_indicators = {"parent", "owner", "container"}
    has_parent_name = any(ind in field_name for ind in parent_indicators)
    if not has_parent_name:
        return False
    # Check if the field type references a class in the MRO
    for cls_name in mro_chain:
        if cls_name in type_str:
            return True
    return False
```

**Step 4: Run tests, wire into orchestrator, commit**

Run: `uv run pytest tests/test_seed_generator.py -v`

```bash
git add scripts/seed_generator.py tests/test_seed_generator.py
git commit -m "feat(codegen): detect parent references from MRO instead of hard-coded name"
```

---

### Task A6: Integration — Full Pipeline Equivalence Test

**Files:**
- Create: `tests/test_inference_integration.py`

**Step 1: Write integration test**

```python
# tests/test_inference_integration.py
"""End-to-end test: verify the inference engine produces equivalent output
to the old hard-coded system."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def test_inferred_seed_covers_all_old_builders():
    """The inference engine should produce builders for at least every class
    the old system did."""
    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)
    toml_str = generate_seed_from_manifest(manifest_dict)
    parsed = tomllib.loads(toml_str)

    builders = list(parsed["builders"].keys())

    # These must always be present (renamed from ADK classes)
    assert "Agent" in builders or "LlmAgent" in builders
    assert len(builders) >= 7, f"Expected >=7 builders, got {len(builders)}: {builders}"


def test_inferred_seed_has_correct_policies():
    """Verify that inferred field policies match expected semantics."""
    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)
    toml_str = generate_seed_from_manifest(manifest_dict)
    parsed = tomllib.loads(toml_str)

    global_cfg = parsed["global"]
    # Callbacks should be in additive
    assert "before_model_callback" in global_cfg["additive_fields"]
    # List fields should be in list_extend
    assert "tools" in global_cfg["list_extend_fields"]


def test_full_pipeline_scan_seed_generate():
    """Run scan → seed → generate and verify no crashes."""
    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest
    import tempfile, json
    from pathlib import Path

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write manifest
        manifest_path = Path(tmpdir) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_dict))

        # Generate seed
        toml_str = generate_seed_from_manifest(manifest_dict)
        seed_path = Path(tmpdir) / "seed.toml"
        seed_path.write_text(toml_str)

        # Verify seed parses
        parsed = tomllib.loads(toml_str)
        assert len(parsed["builders"]) > 0
```

**Step 2: Run integration tests**

Run: `uv run pytest tests/test_inference_integration.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/test_inference_integration.py
git commit -m "test(codegen): add integration tests for inference engine equivalence"
```

---

## Phase B: AST-Based Emission

**Thesis:** Replace generator.py's 1,152 lines of f-string concatenation with a structured Code IR. The IR validates before emission, supports multiple output targets (.py, .pyi, tests) from one representation, and is diffable at the structural level.

### Task B1: Define the Code IR Data Model

**Files:**
- Create: `scripts/code_ir.py`
- Create: `tests/test_code_ir.py`

**Step 1: Write failing tests for IR nodes**

```python
# tests/test_code_ir.py
"""Tests for the Code IR data model."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.code_ir import (
    ModuleNode, ClassNode, MethodNode, Param,
    AssignStmt, ReturnStmt, SubscriptAssign,
    emit_python, emit_stub,
)


def test_method_node_basic():
    """MethodNode stores name, params, return type, body, doc."""
    m = MethodNode(
        name="instruct",
        params=[Param("self"), Param("value", type="str")],
        returns="Self",
        doc="Set the instruction field.",
        body=[
            SubscriptAssign(target="self._config", key="instruction", value="value"),
            ReturnStmt("self"),
        ],
    )
    assert m.name == "instruct"
    assert len(m.params) == 2
    assert len(m.body) == 2


def test_class_node_contains_methods():
    """ClassNode holds a list of methods and class-level attributes."""
    c = ClassNode(
        name="Agent",
        bases=["BuilderBase"],
        doc="Fluent builder for LlmAgent.",
        methods=[
            MethodNode(
                name="instruct",
                params=[Param("self"), Param("value", type="str")],
                returns="Self",
                body=[ReturnStmt("self")],
            ),
        ],
    )
    assert c.name == "Agent"
    assert len(c.methods) == 1


def test_emit_python_method():
    """emit_python produces valid Python source for a method."""
    m = MethodNode(
        name="instruct",
        params=[Param("self"), Param("value", type="str")],
        returns="Self",
        doc="Set the instruction field.",
        body=[
            SubscriptAssign(target="self._config", key="instruction", value="value"),
            ReturnStmt("self"),
        ],
    )
    source = emit_python(m)
    assert "def instruct(self, value: str) -> Self:" in source
    assert 'self._config["instruction"] = value' in source
    assert "return self" in source


def test_emit_stub_method():
    """emit_stub produces a .pyi signature with ellipsis body."""
    m = MethodNode(
        name="instruct",
        params=[Param("self"), Param("value", type="str")],
        returns="Self",
    )
    stub = emit_stub(m)
    assert "def instruct(self, value: str) -> Self: ..." in stub


def test_module_node_collects_imports():
    """ModuleNode deduplicates and sorts imports from all classes."""
    mod = ModuleNode(
        doc="Auto-generated.",
        imports=["from typing import Self", "from typing import Any", "from typing import Self"],
        classes=[],
    )
    assert len(set(mod.imports)) <= len(mod.imports)  # allow dupes in input
    # emit_python should deduplicate
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_code_ir.py -v`
Expected: FAIL — module does not exist

**Step 3: Implement the Code IR**

```python
# scripts/code_ir.py
"""Code IR — structured representation of generated Python code.

Instead of building source strings directly, generator.py builds IR nodes.
IR nodes can be validated, transformed, and emitted to multiple targets
(.py, .pyi, tests, docs).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# --- Statement nodes ---

@dataclass(frozen=True)
class ReturnStmt:
    """return <expr>"""
    expr: str


@dataclass(frozen=True)
class AssignStmt:
    """<target> = <value>"""
    target: str
    value: str


@dataclass(frozen=True)
class SubscriptAssign:
    """<target>[<key>] = <value>"""
    target: str
    key: str
    value: str


@dataclass(frozen=True)
class AppendStmt:
    """<target>[<key>].append(<value>)"""
    target: str
    key: str
    value: str


@dataclass(frozen=True)
class ForAppendStmt:
    """for <var> in <iterable>: <target>[<key>].append(<var>)"""
    var: str
    iterable: str
    target: str
    key: str


@dataclass(frozen=True)
class IfStmt:
    """if <condition>: <body>"""
    condition: str
    body: list  # list of statement nodes


@dataclass(frozen=True)
class ImportStmt:
    """from <module> import <name>; return <expr>"""
    module: str
    name: str
    call: str  # e.g., "return helper(self, arg)"


@dataclass(frozen=True)
class RawStmt:
    """Escape hatch for complex statements that don't fit the IR."""
    code: str


Stmt = ReturnStmt | AssignStmt | SubscriptAssign | AppendStmt | ForAppendStmt | IfStmt | ImportStmt | RawStmt


# --- Param / Method / Class / Module ---

@dataclass(frozen=True)
class Param:
    """A method parameter."""
    name: str
    type: str | None = None
    default: str | None = None
    keyword_only: bool = False


@dataclass
class MethodNode:
    """A method in a class."""
    name: str
    params: list[Param] = field(default_factory=list)
    returns: str | None = None
    doc: str = ""
    body: list[Stmt] = field(default_factory=list)
    is_async: bool = False
    is_generator: bool = False  # async generator


@dataclass
class ClassAttr:
    """A class-level attribute (e.g., _ALIASES = {...})."""
    name: str
    type_hint: str
    value: str  # repr of the value


@dataclass
class ClassNode:
    """A builder class."""
    name: str
    bases: list[str] = field(default_factory=list)
    doc: str = ""
    attrs: list[ClassAttr] = field(default_factory=list)
    methods: list[MethodNode] = field(default_factory=list)


@dataclass
class ModuleNode:
    """A Python module containing imports and classes."""
    doc: str = ""
    imports: list[str] = field(default_factory=list)
    classes: list[ClassNode] = field(default_factory=list)


# --- Emitters ---

def _emit_param(p: Param) -> str:
    """Emit a single parameter."""
    parts = [p.name]
    if p.type:
        parts.append(f": {p.type}")
    if p.default:
        if p.type:
            parts.append(f" = {p.default}")
        else:
            parts.append(f"={p.default}")
    return "".join(parts)


def _emit_stmt(stmt: Stmt, indent: str = "        ") -> str:
    """Emit a statement as Python source."""
    if isinstance(stmt, ReturnStmt):
        return f"{indent}return {stmt.expr}"
    elif isinstance(stmt, AssignStmt):
        return f"{indent}{stmt.target} = {stmt.value}"
    elif isinstance(stmt, SubscriptAssign):
        return f'{indent}{stmt.target}["{stmt.key}"] = {stmt.value}'
    elif isinstance(stmt, AppendStmt):
        return f'{indent}{stmt.target}["{stmt.key}"].append({stmt.value})'
    elif isinstance(stmt, ForAppendStmt):
        lines = [
            f"{indent}for {stmt.var} in {stmt.iterable}:",
            f'{indent}    {stmt.target}["{stmt.key}"].append({stmt.var})',
        ]
        return "\n".join(lines)
    elif isinstance(stmt, IfStmt):
        lines = [f"{indent}if {stmt.condition}:"]
        for s in stmt.body:
            lines.append(_emit_stmt(s, indent + "    "))
        return "\n".join(lines)
    elif isinstance(stmt, ImportStmt):
        return f"{indent}from {stmt.module} import {stmt.name}\n{indent}{stmt.call}"
    elif isinstance(stmt, RawStmt):
        return "\n".join(f"{indent}{line}" for line in stmt.code.strip().split("\n"))
    else:
        raise TypeError(f"Unknown statement type: {type(stmt)}")


def emit_python(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit a node as Python source code."""
    if isinstance(node, MethodNode):
        return _emit_method_python(node)
    elif isinstance(node, ClassNode):
        return _emit_class_python(node)
    elif isinstance(node, ModuleNode):
        return _emit_module_python(node)
    raise TypeError(f"Cannot emit {type(node)}")


def _emit_method_python(m: MethodNode) -> str:
    """Emit a single method."""
    # Build parameter list
    parts = []
    saw_kw_only = False
    for p in m.params:
        if p.keyword_only and not saw_kw_only:
            parts.append("*")
            saw_kw_only = True
        parts.append(_emit_param(p))
    params_str = ", ".join(parts)

    ret = f" -> {m.returns}" if m.returns else ""
    prefix = "async " if m.is_async else ""

    lines = [f"    {prefix}def {m.name}({params_str}){ret}:"]

    if m.doc:
        lines.append(f'        """{m.doc}"""')

    if m.body:
        for stmt in m.body:
            lines.append(_emit_stmt(stmt))
    else:
        lines.append("        pass")

    return "\n".join(lines)


def _emit_class_python(c: ClassNode) -> str:
    """Emit a class."""
    bases = ", ".join(c.bases) if c.bases else ""
    header = f"class {c.name}({bases}):" if bases else f"class {c.name}:"
    lines = [header]

    if c.doc:
        lines.append(f'    """{c.doc}"""')
    lines.append("")

    for attr in c.attrs:
        lines.append(f"    {attr.name}: {attr.type_hint} = {attr.value}")
    if c.attrs:
        lines.append("")

    for method in c.methods:
        lines.append(_emit_method_python(method))
        lines.append("")

    return "\n".join(lines)


def _emit_module_python(mod: ModuleNode) -> str:
    """Emit a module."""
    lines = []
    if mod.doc:
        lines.append(f'"""{mod.doc}"""')
        lines.append("")

    # Deduplicate and sort imports
    unique_imports = sorted(set(mod.imports))
    lines.extend(unique_imports)
    lines.append("")

    for cls in mod.classes:
        lines.append(_emit_class_python(cls))
        lines.append("")

    return "\n".join(lines)


def emit_stub(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit a node as a .pyi type stub."""
    if isinstance(node, MethodNode):
        return _emit_method_stub(node)
    elif isinstance(node, ClassNode):
        return _emit_class_stub(node)
    elif isinstance(node, ModuleNode):
        return _emit_module_stub(node)
    raise TypeError(f"Cannot emit stub for {type(node)}")


def _emit_method_stub(m: MethodNode) -> str:
    parts = []
    saw_kw_only = False
    for p in m.params:
        if p.keyword_only and not saw_kw_only:
            parts.append("*")
            saw_kw_only = True
        parts.append(_emit_param(p))
    params_str = ", ".join(parts)
    ret = f" -> {m.returns}" if m.returns else ""
    prefix = "async " if m.is_async else ""
    return f"    {prefix}def {m.name}({params_str}){ret}: ..."


def _emit_class_stub(c: ClassNode) -> str:
    bases = ", ".join(c.bases) if c.bases else ""
    header = f"class {c.name}({bases}):" if bases else f"class {c.name}:"
    lines = [header]
    if c.doc:
        lines.append(f'    """{c.doc}"""')
    for method in c.methods:
        lines.append(_emit_method_stub(method))
    return "\n".join(lines)


def _emit_module_stub(mod: ModuleNode) -> str:
    lines = []
    if mod.doc:
        lines.append(f"# {mod.doc}")
    unique_imports = sorted(set(mod.imports))
    lines.extend(unique_imports)
    lines.append("")
    for cls in mod.classes:
        lines.append(_emit_class_stub(cls))
        lines.append("")
    return "\n".join(lines)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_code_ir.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add scripts/code_ir.py tests/test_code_ir.py
git commit -m "feat(codegen): add Code IR data model with Python and stub emitters"
```

---

### Task B2: Convert Generator to Produce IR Instead of Strings

**Files:**
- Modify: `scripts/generator.py` (replace gen_* functions with IR-producing equivalents)
- Modify: `tests/test_code_ir.py` (add round-trip tests)

**Step 1: Write failing round-trip test**

```python
# tests/test_code_ir.py — append

def test_roundtrip_builder_spec_to_ir_to_python():
    """BuilderSpec → IR → Python source should produce valid code."""
    from scripts.generator import spec_to_ir
    from scripts.code_ir import emit_python

    # Minimal BuilderSpec-like dict
    spec = _make_test_spec()
    ir_class = spec_to_ir(spec)
    source = emit_python(ir_class)

    assert "class TestBuilder(BuilderBase):" in source
    assert "def __init__(self, name: str)" in source
    assert "def instruct(self, value: str) -> Self:" in source
    assert "return self" in source


def _make_test_spec():
    """Helper to create a minimal BuilderSpec for testing."""
    from scripts.generator import BuilderSpec

    return BuilderSpec(
        name="TestBuilder",
        source_class="google.adk.test.TestClass",
        source_class_short="TestClass",
        output_module="test",
        doc="Test builder.",
        constructor_args=["name"],
        aliases={"instruct": "instruction"},
        reverse_aliases={"instruction": "instruct"},
        callback_aliases={},
        skip_fields={"name", "parent_agent"},
        additive_fields=set(),
        list_extend_fields=set(),
        fields=[
            {"name": "name", "type_str": "str", "required": True, "is_callback": False},
            {"name": "instruction", "type_str": "str | None", "required": False, "is_callback": False},
        ],
        terminals=[{"name": "build", "returns": "TestClass"}],
        extras=[],
        is_composite=False,
        is_standalone=False,
        field_docs={},
    )
```

**Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_code_ir.py::test_roundtrip_builder_spec_to_ir_to_python -v`
Expected: FAIL — `spec_to_ir` does not exist

**Step 3: Implement `spec_to_ir` in generator.py**

Add a new function that converts a `BuilderSpec` into a `ClassNode`:

```python
# scripts/generator.py — add new function

from scripts.code_ir import (
    ClassNode, ClassAttr, MethodNode, Param, ModuleNode,
    SubscriptAssign, ReturnStmt, ForAppendStmt, IfStmt, AppendStmt,
    ImportStmt, AssignStmt, RawStmt,
    emit_python, emit_stub,
)


def spec_to_ir(spec: BuilderSpec) -> ClassNode:
    """Convert a BuilderSpec into a ClassNode IR."""
    methods: list[MethodNode] = []

    # __init__
    methods.append(_ir_init_method(spec))

    # Alias methods
    for fluent_name, field_name in spec.aliases.items():
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        type_hint = field_info["type_str"] if field_info else "Any"
        doc = spec.field_docs.get(fluent_name, "") or spec.field_docs.get(field_name, "")
        if not doc and field_info:
            doc = field_info.get("description", "") or f"Set the `{field_name}` field."
        methods.append(MethodNode(
            name=fluent_name,
            params=[Param("self"), Param("value", type=type_hint)],
            returns="Self",
            doc=doc,
            body=[
                SubscriptAssign(target="self._config", key=field_name, value="value"),
                ReturnStmt("self"),
            ],
        ))

    # Callback methods
    for short_name, full_name in spec.callback_aliases.items():
        methods.append(MethodNode(
            name=short_name,
            params=[Param("self"), Param("*fns", type="Callable")],
            returns="Self",
            doc=f"Append callback(s) to `{full_name}`. Multiple calls accumulate.",
            body=[
                ForAppendStmt(var="fn", iterable="fns", target="self._callbacks", key=full_name),
                ReturnStmt("self"),
            ],
        ))
        methods.append(MethodNode(
            name=f"{short_name}_if",
            params=[Param("self"), Param("condition", type="bool"), Param("fn", type="Callable")],
            returns="Self",
            doc=f"Append callback to `{full_name}` only if condition is True.",
            body=[
                IfStmt(condition="condition", body=[
                    AppendStmt(target="self._callbacks", key=full_name, value="fn"),
                ]),
                ReturnStmt("self"),
            ],
        ))

    # Field methods (remaining)
    methods.extend(_ir_field_methods(spec))

    # Extra methods
    for extra in spec.extras:
        methods.append(_ir_extra_method(extra))

    # build() method
    if not spec.is_composite and not spec.is_standalone:
        import_name = _adk_import_name(spec)
        methods.append(MethodNode(
            name="build",
            params=[Param("self")],
            returns=import_name,
            doc=f"Resolve into a native ADK {import_name}.",
            body=[
                AssignStmt("config", "self._prepare_build_config()"),
                ReturnStmt(f"{import_name}(**config)"),
            ],
        ))

    # Class attributes
    attrs = [
        ClassAttr("_ALIASES", "dict[str, str]", repr(spec.aliases) if spec.aliases else "{}"),
        ClassAttr("_CALLBACK_ALIASES", "dict[str, str]",
                   repr(spec.callback_aliases) if spec.callback_aliases else "{}"),
    ]

    additive = spec.additive_fields & {f["name"] for f in spec.fields}
    attrs.append(ClassAttr("_ADDITIVE_FIELDS", "set[str]", repr(additive) if additive else "set()"))

    if not spec.is_composite and not spec.is_standalone and spec.inspection_mode != "init_signature":
        attrs.append(ClassAttr("_ADK_TARGET_CLASS", "", _adk_import_name(spec)))

    return ClassNode(
        name=spec.name,
        bases=["BuilderBase"],
        doc=spec.doc,
        attrs=attrs,
        methods=methods,
    )
```

The helper functions `_ir_init_method`, `_ir_field_methods`, `_ir_extra_method` follow the same pattern — converting the existing string-building logic into IR node construction. Each is straightforward: instead of `f"self._config[{field!r}] = value"`, you produce `SubscriptAssign(target="self._config", key=field, value="value")`.

**Step 4: Run tests**

Run: `uv run pytest tests/test_code_ir.py -v`
Expected: All PASS

**Step 5: Add parallel emission path**

Wire `spec_to_ir` + `emit_python` as an alternative to the existing `gen_runtime_class`. Add a `--use-ir` flag to generator.py CLI:

```python
# In generate_all(), add IR path:
if use_ir:
    for module_name, module_specs in by_module.items():
        ir_classes = [spec_to_ir(spec) for spec in module_specs]
        all_imports = []
        for spec in module_specs:
            all_imports.extend(gen_runtime_imports(spec))
        mod = ModuleNode(
            doc="Auto-generated by adk-fluent generator.",
            imports=all_imports,
            classes=ir_classes,
        )
        code = emit_python(mod)
        filepath = output_path / f"{module_name}.py"
        filepath.write_text(code)
```

**Step 6: Verify IR output matches string output**

Run: `uv run python scripts/generator.py seeds/seed.toml manifest.json --output-dir /tmp/ir_output --use-ir`
Run: `diff -r /tmp/ir_output src/adk_fluent/`
Expected: Output should be functionally equivalent (whitespace may differ).

**Step 7: Commit**

```bash
git add scripts/generator.py scripts/code_ir.py tests/test_code_ir.py
git commit -m "feat(codegen): add IR-based emission path parallel to string emission"
```

---

### Task B3: Migrate Stub and Test Generation to IR

**Files:**
- Modify: `scripts/generator.py` (stub and test gen via IR)
- Modify: `scripts/code_ir.py` (add test-specific nodes if needed)
- Modify: `tests/test_code_ir.py`

**Step 1: Write tests for stub emission from IR**

```python
def test_ir_stub_emission_matches_direct():
    """IR → emit_stub should produce equivalent output to gen_stub_class."""
    from scripts.generator import spec_to_ir, gen_stub_class, BuilderSpec
    from scripts.code_ir import emit_stub

    spec = _make_test_spec()
    ir = spec_to_ir(spec)
    stub_from_ir = emit_stub(ir)
    stub_direct = gen_stub_class(spec, "1.25.0")

    # Both should contain the same method signatures
    assert "def instruct(self, value: str" in stub_from_ir
    assert "def build(self)" in stub_from_ir
```

**Step 2: Implement, test, commit**

Follow same pattern as B2. The key insight is that `emit_stub(ClassNode)` already works — it just emits `...` bodies instead of full implementations. No new IR nodes needed for stubs.

For tests, add a `emit_test` function that generates pytest assertions from IR method signatures.

```bash
git commit -m "feat(codegen): emit stubs and test scaffolds from Code IR"
```

---

### Task B4: Remove Old String Emission, Make IR the Default

**Files:**
- Modify: `scripts/generator.py` (remove old gen_* string functions)
- Modify: `justfile` (remove --use-ir flag, IR is now default)

**Step 1: Remove old functions**

Delete `gen_alias_methods`, `gen_callback_methods`, `gen_extra_methods`, `gen_field_methods`, `gen_runtime_class`, `gen_runtime_module`, `gen_stub_class`, `gen_stub_module`, `gen_test_class`, `gen_test_module` — all replaced by IR path.

**Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 3: Run full pipeline**

Run: `just all && just test`
Expected: All pass, generated code identical to before.

**Step 4: Commit**

```bash
git add scripts/generator.py justfile
git commit -m "refactor(codegen): remove string emission, IR is now the only code generation path"
```

---

## Phase C: Reactive Pipeline

**Thesis:** Replace the sequential `just all` (scan → seed → generate → docs) with a dependency-tracked pipeline that uses content-addressed hashing to skip unchanged stages and only regenerate builders whose inputs actually changed.

### Task C1: Content-Addressed Hashing

**Files:**
- Create: `scripts/pipeline.py`
- Create: `tests/test_pipeline.py`

**Step 1: Write failing tests**

```python
# tests/test_pipeline.py
"""Tests for the reactive pipeline."""

import sys, os, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from scripts.pipeline import ContentHash, HashCache


def test_content_hash_file():
    """Hash a file by contents, not mtime."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"hello": "world"}')
        f.flush()
        h1 = ContentHash.of_file(f.name)
        h2 = ContentHash.of_file(f.name)
        assert h1 == h2
    os.unlink(f.name)


def test_content_hash_changes_with_content():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
        f.write("v1")
    h1 = ContentHash.of_file(path)

    with open(path, "w") as f:
        f.write("v2")
    h2 = ContentHash.of_file(path)

    assert h1 != h2
    os.unlink(path)


def test_hash_cache_stores_and_retrieves():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = HashCache(Path(tmpdir) / ".codegen_cache.json")
        cache.set("manifest.json", "abc123")
        assert cache.get("manifest.json") == "abc123"
        cache.save()

        # Reload
        cache2 = HashCache(Path(tmpdir) / ".codegen_cache.json")
        assert cache2.get("manifest.json") == "abc123"


def test_hash_cache_detects_changes():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = HashCache(Path(tmpdir) / ".codegen_cache.json")
        cache.set("manifest.json", "abc123")
        assert cache.changed("manifest.json", "abc123") is False
        assert cache.changed("manifest.json", "def456") is True
        assert cache.changed("new_file.json", "xyz") is True  # Not in cache
```

**Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL — module does not exist

**Step 3: Implement content hashing**

```python
# scripts/pipeline.py
"""Reactive pipeline with content-addressed caching.

Only rebuilds stages whose inputs actually changed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class ContentHash:
    """Content-addressed file hashing."""

    @staticmethod
    def of_file(path: str | Path) -> str:
        """SHA-256 hash of file contents."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def of_string(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()


class HashCache:
    """Persistent cache mapping file paths to content hashes."""

    def __init__(self, cache_path: Path):
        self._path = cache_path
        self._data: dict[str, str] = {}
        if cache_path.exists():
            self._data = json.loads(cache_path.read_text())

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, hash_val: str) -> None:
        self._data[key] = hash_val

    def changed(self, key: str, current_hash: str) -> bool:
        return self._data.get(key) != current_hash

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add scripts/pipeline.py tests/test_pipeline.py
git commit -m "feat(codegen): add content-addressed hashing for pipeline caching"
```

---

### Task C2: Dependency Graph and Incremental Rebuild

**Files:**
- Modify: `scripts/pipeline.py` (add PipelineRunner)
- Modify: `tests/test_pipeline.py`

**Step 1: Write failing tests**

```python
def test_pipeline_skips_unchanged_stage():
    """When input hash matches cache, stage is skipped."""
    from scripts.pipeline import PipelineRunner, Stage

    ran = []

    def stage_a(ctx):
        ran.append("a")
        return "result_a"

    with tempfile.TemporaryDirectory() as tmpdir:
        runner = PipelineRunner(cache_dir=Path(tmpdir))

        # First run — should execute
        runner.run_stage(Stage(
            name="scan",
            inputs=["manifest.json"],
            outputs=["seed.toml"],
            fn=stage_a,
        ), input_hashes={"manifest.json": "hash1"})
        assert "a" in ran

        ran.clear()

        # Second run with same hash — should skip
        runner.run_stage(Stage(
            name="scan",
            inputs=["manifest.json"],
            outputs=["seed.toml"],
            fn=stage_a,
        ), input_hashes={"manifest.json": "hash1"})
        assert "a" not in ran  # Skipped


def test_pipeline_reruns_on_changed_input():
    """When input hash changes, stage is re-executed."""
    from scripts.pipeline import PipelineRunner, Stage

    ran = []

    def stage_a(ctx):
        ran.append("a")

    with tempfile.TemporaryDirectory() as tmpdir:
        runner = PipelineRunner(cache_dir=Path(tmpdir))

        runner.run_stage(Stage(
            name="scan",
            inputs=["manifest.json"],
            outputs=["seed.toml"],
            fn=stage_a,
        ), input_hashes={"manifest.json": "hash1"})

        ran.clear()

        runner.run_stage(Stage(
            name="scan",
            inputs=["manifest.json"],
            outputs=["seed.toml"],
            fn=stage_a,
        ), input_hashes={"manifest.json": "hash2"})  # Changed!
        assert "a" in ran
```

**Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_pipeline.py::test_pipeline_skips_unchanged_stage -v`

**Step 3: Implement PipelineRunner**

```python
@dataclass
class Stage:
    """A pipeline stage with declared inputs and outputs."""
    name: str
    inputs: list[str]
    outputs: list[str]
    fn: callable


class PipelineRunner:
    """Runs pipeline stages, skipping those whose inputs haven't changed."""

    def __init__(self, cache_dir: Path):
        self._cache = HashCache(cache_dir / ".codegen_cache.json")

    def run_stage(self, stage: Stage, input_hashes: dict[str, str]) -> bool:
        """Run a stage if its inputs changed. Returns True if stage ran."""
        cache_key = f"stage:{stage.name}:inputs"
        combined = hashlib.sha256()
        for inp in sorted(stage.inputs):
            h = input_hashes.get(inp, "missing")
            combined.update(f"{inp}:{h}".encode())
        current_hash = combined.hexdigest()

        if not self._cache.changed(cache_key, current_hash):
            return False  # Skip — inputs unchanged

        stage.fn(None)
        self._cache.set(cache_key, current_hash)
        self._cache.save()
        return True
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add scripts/pipeline.py tests/test_pipeline.py
git commit -m "feat(codegen): add incremental pipeline runner with stage skipping"
```

---

### Task C3: Change Report Generation

**Files:**
- Modify: `scripts/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Step 1: Write failing test**

```python
def test_change_report_summarizes_diffs():
    """Pipeline produces a human-readable change report."""
    from scripts.pipeline import ChangeReport

    report = ChangeReport()
    report.add_auto("New field 'artifacts' on Agent → list_extend + singular .artifact() adder")
    report.add_auto("New field 'on_error_callback' on Agent → additive callback method")
    report.add_review("Override 'tool' on Agent may need signature update (new param added upstream)")
    report.add_unchanged("Pipeline builder — no changes")

    summary = report.summary()
    assert "2 auto-handled" in summary
    assert "1 needs review" in summary
    assert "1 unchanged" in summary
```

**Step 2: Implement**

```python
class ChangeReport:
    """Collects and summarizes changes from a pipeline run."""

    def __init__(self):
        self._auto: list[str] = []
        self._review: list[str] = []
        self._unchanged: list[str] = []

    def add_auto(self, msg: str): self._auto.append(msg)
    def add_review(self, msg: str): self._review.append(msg)
    def add_unchanged(self, msg: str): self._unchanged.append(msg)

    def summary(self) -> str:
        parts = [
            f"{len(self._auto)} auto-handled",
            f"{len(self._review)} needs review",
            f"{len(self._unchanged)} unchanged",
        ]
        lines = [", ".join(parts)]
        if self._auto:
            lines.append("\nAuto-handled:")
            lines.extend(f"  + {m}" for m in self._auto)
        if self._review:
            lines.append("\nNeeds review:")
            lines.extend(f"  ! {m}" for m in self._review)
        return "\n".join(lines)
```

**Step 3: Run tests, commit**

```bash
git add scripts/pipeline.py tests/test_pipeline.py
git commit -m "feat(codegen): add change report generation for pipeline runs"
```

---

### Task C4: Wire Pipeline into justfile

**Files:**
- Modify: `scripts/pipeline.py` (add CLI entry point)
- Modify: `justfile` (add `just pipeline` target)

**Step 1: Add CLI to pipeline.py**

```python
def main():
    """Run the full pipeline with incremental caching."""
    import argparse

    parser = argparse.ArgumentParser(description="Incremental codegen pipeline")
    parser.add_argument("--force", action="store_true", help="Force full rebuild")
    parser.add_argument("--report", action="store_true", help="Print change report")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    runner = PipelineRunner(cache_dir=project_root)

    # Hash inputs
    manifest_path = project_root / "manifest.json"
    manual_seed_path = project_root / "seeds" / "seed.manual.toml"

    if args.force:
        runner.force_all()

    if manifest_path.exists():
        manifest_hash = ContentHash.of_file(manifest_path)
    else:
        manifest_hash = "missing"

    manual_hash = ContentHash.of_file(manual_seed_path) if manual_seed_path.exists() else "none"

    # Stage 1: Scan (always runs if manifest missing)
    # Stage 2: Seed generation
    # Stage 3: Code generation
    # Stage 4: Documentation
    # ... wire each stage through runner.run_stage()

    if args.report:
        print(runner.report.summary())
```

**Step 2: Add justfile target**

```just
# --- Incremental pipeline ---
pipeline:
    @echo "Running incremental pipeline..."
    @uv run python scripts/pipeline.py --report
```

**Step 3: Run and verify**

Run: `just pipeline`
Expected: Pipeline runs, skips unchanged stages, prints report.

**Step 4: Commit**

```bash
git add scripts/pipeline.py justfile
git commit -m "feat(codegen): wire incremental pipeline into justfile"
```

---

## Summary

| Phase | Tasks | What Changes | Key Metric |
|-------|-------|-------------|------------|
| **A: Inference Engine** | A1-A6 | seed_generator.py derives behavior from types, not lookup tables | seed.manual.toml shrinks from 179 lines to ~40 |
| **B: AST-Based Emission** | B1-B4 | generator.py builds IR nodes, validates structure, emits from IR | generator.py complexity drops, output validated before write |
| **C: Reactive Pipeline** | C1-C4 | Content-addressed caching, incremental rebuilds, change reports | Full pipeline skips unchanged stages, produces audit trail |

Each phase is independently deployable. Phase A is the highest-leverage change. Phase B compounds with A. Phase C is infrastructure polish.
