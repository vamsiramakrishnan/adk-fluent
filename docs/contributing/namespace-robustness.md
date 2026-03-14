# Namespace Robustness: Uniformization & Partial Generation

This document analyzes the six namespace modules (S, C, P, A, M, T),
diagnoses their inconsistencies, proposes a uniform protocol, evaluates
which parts could be partially generated, and defines the test strategy.

---

## Current State: The Six Namespaces Side-by-Side

### Structural Comparison

```
Module     Lines  Base Type          Immutability      Compose Ops   Terminal         Async?
─────────  ─────  ─────────────────  ────────────────  ────────────  ───────────────  ──────
S (state)    596  Plain class        Constructor       >> +          __call__()       No
C (context) 2435  Frozen dataclass   @dataclass + hack + |           _compile_*()     Yes
P (prompt)  1094  Frozen dataclass   @dataclass(pure)  + |           build() / _compile  Both
A (artifact) 772  Frozen dataclass   @dataclass+slots  >>            __call__ (stub)  Yes
M (middle)   219  Plain class        Mutable list      |             to_stack()       N/A
T (tools)    155  Plain class        Mutable list      |             to_tools()       N/A
```

### Architectural Inconsistencies

**1. Three different base patterns**

| Pattern | Used By | How It Works |
|---------|---------|-------------|
| Frozen dataclass tree | C, P, A | Descriptors compose into AST, compiled at build-time |
| Callable wrapper | S | Wraps a closure, called directly at runtime |
| Mutable list accumulator | M, T | Appends items to a list, flattened at build-time |

**2. Composition operator meanings diverge**

| Operator | S | C | P | A | M | T |
|----------|---|---|---|---|---|---|
| `>>` | Chain (sequential) | — | — | Chain | — | — |
| `+` | Combine (parallel merge) | Union | Union | — | — | — |
| `\|` | — | Pipe | Pipe | — | Chain | Chain |

Users must remember: `>>` chains S transforms but `|` chains M middleware.
`+` merges S transforms in parallel but unions C/P blocks.

**3. Terminal protocol fragmented**

- `S`: No terminal — callable protocol, executed as `FnAgent` directly
- `C`: External function `_compile_context_spec()` called from `_base.py`
- `P`: Both `build()` instance method AND `_compile_prompt_spec()` function
- `A`: `__call__` is a no-op stub; real work in `ArtifactAgent` at runtime
- `M`: `to_stack()` returns list of middleware instances
- `T`: `to_tools()` returns list of tool/toolset objects

**4. `__post_init__` mutation in C breaks frozen invariant**

C's `CComposite`, `CPipe`, `CWhen`, and most leaf types use
`object.__setattr__()` inside `__post_init__` to eagerly create
`instruction_provider` closures. This is technically valid Python
but semantically breaks the frozen dataclass contract — the object
is mutated during construction.

P avoids this by deferring provider creation to compile-time.

**5. Metadata and contract tracing**

- S carries `_reads_keys` / `_writes_keys` (frozenset) for contract checking
- C carries `include_contents` / `instruction_provider` (runtime config, not metadata)
- P carries `_kind` discriminator only
- A carries `_produces_state` / `_consumes_state` / `_produces_artifact` / `_consumes_artifact`
- M, T carry nothing — opaque to contract checker

**6. Test coverage is uneven**

| Namespace | Test Files | Coverage Focus | Missing |
|-----------|-----------|----------------|---------|
| S | 4 files | Composition, tracing, basic ops | Error paths, edge cases for branch/when |
| C | 6+ files | Phases B/C/D, when, spec compilation | Composition property tests, error paths |
| P | 2 files | Schema, prompt structure | Composition, fingerprinting, LLM transforms |
| A | 1 file | MIME constants, basic ops | Pipeline integration, state bridging |
| M | 2 files | Basic wiring, schema | Scope, when, hook composition |
| T | 1 file | Basic wrapping | Composition, search, schema markers |

---

## Proposed Uniform Protocol

### Core Idea: `NamespaceSpec` Protocol

Every namespace module follows the same shape. Formalize it:

```python
# src/adk_fluent/_namespace_protocol.py

from __future__ import annotations
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class NamespaceSpec(Protocol):
    """Protocol that all namespace spec types (STransform, CTransform,
    PTransform, ATransform, MComposite, TComposite) should satisfy."""

    @property
    def _kind(self) -> str:
        """Discriminator tag for IR serialization."""
        ...

    def _as_list(self) -> tuple[Any, ...]:
        """Flatten for composite building."""
        ...

    def __repr__(self) -> str: ...
```

This protocol doesn't force structural changes — it documents
the contract that all six namespaces already *nearly* satisfy.

### Uniformization Matrix

Concrete changes to align the six modules:

| Change | S | C | P | A | M | T | Effort |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|--------|
| Add `_kind` discriminator | Add | Has | Has | Has | Add | Add | Low |
| Add `_as_list()` flattening | Add | Has | Has | Has | Add | Add | Low |
| Standardize compose operators | Keep `>>` `+` | Keep `+` `\|` | Keep `+` `\|` | Keep `>>` | Keep `\|` | Keep `\|` | None |
| Add `_reads_keys`/`_writes_keys` | Has | Add | Add | Has | Add | Add | Medium |
| Add fingerprinting | Add | Add | Has | Add | — | — | Medium |
| Uniform error handling | Add | Audit | Audit | Add | Add | Add | Medium |

**Rationale for keeping operator divergence**: S and A operate on
*sequential data flow* (state transforms chain left-to-right), so `>>`
is correct. C, P operate on *declarative composition* (sections union),
so `+` is correct. M, T are *flat collections* with no ordering
semantics, so `|` is correct. The operators are semantically accurate;
forcing uniformity would harm readability.

### What Should Change

**1. Add `_kind` and `_as_list()` to S, M, T**

S already has `__name__` but not `_kind`. Adding a `_kind` property
and `_as_list()` enables uniform IR conversion and introspection:

```python
# On STransform
@property
def _kind(self) -> str:
    return self.__name__  # "pick_a_b", "rename_x_y", etc.

def _as_list(self) -> tuple[STransform, ...]:
    return (self,)
```

```python
# On MComposite
@property
def _kind(self) -> str:
    return "middleware_chain"

def _as_list(self) -> tuple[Any, ...]:
    return tuple(self._stack)
```

**2. Add `_reads_keys`/`_writes_keys` to C and P**

C and P currently lack contract metadata. When the contract
checker runs, it can trace S and A data flow but C and P are
opaque. Adding key metadata enables:

```python
# C.from_state("query", "topic")
CFromState(keys=("query", "topic"))
# → _reads_keys = frozenset({"query", "topic"})
# → _writes_keys = frozenset()  (context doesn't write state)
```

```python
# P.from_state("topic")
PFromState(keys=("topic",))
# → _reads_keys = frozenset({"topic"})
# → _writes_keys = frozenset()
```

**3. Fix C's `__post_init__` mutation**

Replace eager provider creation with lazy compilation matching P's pattern:

```python
# Before (C — breaks frozen invariant):
@dataclass(frozen=True)
class CWindow(CTransform):
    n: int = 5
    def __post_init__(self):
        object.__setattr__(self, "instruction_provider",
                           _make_window_provider(self.n))

# After (deferred to compile time):
@dataclass(frozen=True)
class CWindow(CTransform):
    n: int = 5
    _kind: str = "window"
    # No __post_init__ — provider created in _compile_context_spec()
```

This is the single highest-value structural change. It:
- Makes C truly frozen (hashable, cacheable, serializable)
- Enables fingerprinting (providers are closures → unhashable)
- Aligns with P's already-working pattern
- Enables IR serialization of context specs

**4. Add fingerprinting to S, C, A**

P's `_fingerprint()` enables caching and versioning. Extending it:

```python
# Shared fingerprint utility
def fingerprint_spec(spec: NamespaceSpec) -> str:
    """SHA-256 of spec's _kind + structural content."""
    import hashlib
    h = hashlib.sha256()
    h.update(spec._kind.encode())
    for child in spec._as_list():
        h.update(fingerprint_spec(child).encode())
    return h.hexdigest()[:16]
```

---

## What Can Be Partially Generated?

### The Opportunity

Each namespace has three layers:

```
┌─────────────────────────────────────────────┐
│ Layer 3: SEMANTICS (fully handcoded)        │
│   How pick/window/role/retry actually work  │
│   Provider factories, compilation logic     │
│   Integration with ADK runtime              │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│ Layer 2: STRUCTURE (partially generatable)  │
│   Frozen dataclass definitions              │
│   Factory methods on namespace class        │
│   Composition operators                     │
│   _kind discriminators                      │
│   _reads_keys / _writes_keys metadata       │
│   _as_list() flattening                     │
│   __repr__()                                │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│ Layer 1: PROTOCOL (fully generatable)       │
│   NamespaceSpec protocol conformance        │
│   Type stubs (.pyi)                         │
│   Test scaffolds (composition, repr, etc.)  │
│   IR node definitions                       │
│   Documentation (factory method reference)  │
└─────────────────────────────────────────────┘
```

**Layer 3** is irreducibly handcoded — it's where the domain logic lives.
You can't generate what `S.pick()` does because it's a design decision.

**Layer 2** has significant boilerplate that follows patterns. Each
factory method on a namespace class:
1. Creates a frozen dataclass instance
2. Sets `_kind` discriminator
3. Computes `_reads_keys` / `_writes_keys`
4. Gives the instance a `__name__`

This is the same structure repeated 50+ times across the six modules.

**Layer 1** is pure boilerplate that can be fully generated from
a namespace manifest.

### Namespace Manifest: The Missing Seed File

Create a `seeds/namespace.toml` that declares the *structure* of
each namespace operation, while the *implementation* stays handcoded:

```toml
[meta]
version = "1.0"
description = "Namespace operation declarations for S, C, P, A, M, T"

# ─── S NAMESPACE ─── #

[[operations]]
namespace = "S"
name = "pick"
kind = "pick"
params = [
    { name = "keys", type = "*str", variadic = true },
]
returns = "STransform"
result_type = "StateReplacement"
reads = "opaque"          # None — reads full state
writes = "from_params"    # frozenset(keys)
doc = "Keep only the specified session-scoped keys."

[[operations]]
namespace = "S"
name = "drop"
kind = "drop"
params = [
    { name = "keys", type = "*str", variadic = true },
]
returns = "STransform"
result_type = "StateReplacement"
reads = "opaque"
writes = "opaque"
doc = "Remove the specified keys from state."

[[operations]]
namespace = "S"
name = "rename"
kind = "rename"
params = [
    { name = "mapping", type = "**str", variadic = true },
]
returns = "STransform"
result_type = "StateReplacement"
reads = "from_params_keys"     # frozenset(mapping.keys())
writes = "from_params_values"  # frozenset(mapping.values())
doc = "Rename state keys."

[[operations]]
namespace = "S"
name = "default"
kind = "default"
params = [
    { name = "defaults", type = "**Any", variadic = true },
]
returns = "STransform"
result_type = "StateDelta"
reads = "from_params_keys"
writes = "from_params_keys"
doc = "Fill missing keys with default values."

# ... similar entries for all 14 S operations ...

# ─── C NAMESPACE ─── #

[[operations]]
namespace = "C"
name = "window"
kind = "window"
params = [
    { name = "n", type = "int", default = 5 },
]
returns = "CTransform"
dataclass_name = "CWindow"
reads = []
writes = []
doc = "Last N turn-pairs."

[[operations]]
namespace = "C"
name = "from_state"
kind = "from_state"
params = [
    { name = "keys", type = "*str", variadic = true },
]
returns = "CTransform"
dataclass_name = "CFromState"
reads = "from_params"
writes = []
doc = "Inject state keys as context."

# ... 30+ C operations across phases A-D ...

# ─── P NAMESPACE ─── #

[[operations]]
namespace = "P"
name = "role"
kind = "role"
params = [
    { name = "text", type = "str" },
]
returns = "PTransform"
dataclass_name = "PRole"
section_order = 100
reads = []
writes = []
doc = "Agent persona."

# ... 18 P operations ...

# ─── M NAMESPACE ─── #

[[operations]]
namespace = "M"
name = "retry"
kind = "retry"
params = [
    { name = "max_attempts", type = "int", default = 3 },
    { name = "backoff", type = "float", default = 1.0 },
]
returns = "MComposite"
impl_class = "RetryMiddleware"
impl_module = "adk_fluent.middleware"
doc = "Retry with exponential backoff."

# ... 12 M operations ...

# ─── T NAMESPACE ─── #

[[operations]]
namespace = "T"
name = "fn"
kind = "fn"
params = [
    { name = "func_or_tool", type = "Any" },
    { name = "confirm", type = "bool", default = false, keyword_only = true },
]
returns = "TComposite"
doc = "Wrap callable as tool."

# ... 5 T operations ...

# ─── A NAMESPACE ─── #

[[operations]]
namespace = "A"
name = "publish"
kind = "publish"
params = [
    { name = "filename", type = "str" },
    { name = "from_key", type = "str", keyword_only = true },
]
returns = "ATransform"
reads = "from_param:from_key"
writes = []
produces_artifact = "from_param:filename"
doc = "State → artifact."

# ... 10 A operations ...
```

### What the Namespace Generator Emits

From `namespace.toml`, a new `scripts/namespace_generator.py` produces:

**1. Type stubs (`.pyi`)**

```python
# src/adk_fluent/_transforms.pyi  (generated)
class S:
    @staticmethod
    def pick(*keys: str) -> STransform:
        """Keep only the specified session-scoped keys.""" ...
    @staticmethod
    def drop(*keys: str) -> STransform:
        """Remove the specified keys from state.""" ...
    # ... all 14 operations with full signatures
```

Currently these stubs don't exist for namespace modules — IDE
autocomplete relies on reading the source. Generated stubs would
give users perfect autocomplete without reading 2400 lines of
`_context.py`.

**2. IR node definitions**

```python
# src/adk_fluent/_ir_namespaces.py  (generated)
@dataclass(frozen=True)
class SPickNode:
    _kind: str = "s.pick"
    keys: tuple[str, ...]
    reads_keys: frozenset[str] | None = None
    writes_keys: frozenset[str] = frozenset()

@dataclass(frozen=True)
class CWindowNode:
    _kind: str = "c.window"
    n: int = 5
    reads_keys: frozenset[str] = frozenset()
    writes_keys: frozenset[str] = frozenset()
```

**3. Test scaffolds**

```python
# tests/generated/test_namespace_protocol.py  (generated)

class TestSPickProtocol:
    def test_returns_stransform(self):
        result = S.pick("a", "b")
        assert isinstance(result, STransform)

    def test_kind(self):
        result = S.pick("a")
        assert "pick" in result._kind

    def test_writes_keys(self):
        result = S.pick("a", "b")
        assert result._writes_keys == frozenset({"a", "b"})

    def test_repr_not_empty(self):
        assert repr(S.pick("a"))

    def test_composition_rshift(self):
        composed = S.pick("a") >> S.rename(a="b")
        assert isinstance(composed, STransform)

    def test_composition_add(self):
        composed = S.pick("a") + S.set(b=1)
        assert isinstance(composed, STransform)


class TestCWindowProtocol:
    def test_returns_ctransform(self):
        result = C.window(n=3)
        assert isinstance(result, CTransform)

    def test_frozen(self):
        result = C.window(n=3)
        with pytest.raises(FrozenInstanceError):
            result.n = 5

    # ... similar for all operations
```

**4. API reference docs**

```markdown
<!-- docs/generated/api/s-namespace.md  (generated) -->
## S — State Transforms

| Method | Returns | Reads | Writes | Description |
|--------|---------|-------|--------|-------------|
| `S.pick(*keys)` | `STransform` | full state | `{keys}` | Keep only named keys |
| `S.drop(*keys)` | `STransform` | full state | full state | Remove named keys |
```

### What CANNOT Be Generated

The handcoded implementations — the actual closures inside each factory:

```python
# This stays handcoded — it IS the domain logic
@staticmethod
def pick(*keys: str) -> STransform:
    def _pick(state: dict) -> StateReplacement:
        return StateReplacement({k: state[k] for k in keys if k in state})
    return STransform(_pick, reads=None, writes=frozenset(keys), name=...)
```

The generator only produces the *envelope* (stubs, IR, tests, docs).
The *body* of each factory method is irreducibly creative code.

### Does It Add Value?

**Yes, for three reasons:**

**1. Consistency enforcement** — The generator validates that every
operation has `_kind`, `_reads_keys`, `_writes_keys`, proper `__repr__`,
and composition operators. Today, adding a new C operation means
manually adding a frozen dataclass, a factory method, an `__all__` export,
test coverage, and documentation. Miss any step and it's an inconsistency
that silently persists. The generator makes omissions impossible.

**2. Contract checker completeness** — The contract checker can only trace
data flow through operations that declare `_reads_keys`/`_writes_keys`.
Today it covers S and A but is blind to C and P. Generating metadata
from the manifest makes all six namespaces traceable.

**3. Test coverage amplification** — Today the six namespaces have
wildly uneven test coverage (S: 4 files, T: 1 file). Generated
protocol conformance tests guarantee a baseline: every operation is
instantiable, composable, repr-able, and has correct key metadata.
Property-based tests (via Hypothesis) can be generated too.

**The cost is low** — the namespace.toml manifest is ~200 lines for
all 70+ operations. The generator is ~300 lines. The generated output
replaces manual work that's already error-prone.

---

## Test Strategy

### Tier 1: Protocol Conformance (Generated)

Every operation gets these auto-generated tests:

```
test_returns_correct_type     — S.pick() → STransform
test_kind_set                 — result._kind contains operation name
test_reads_keys_type          — frozenset | None
test_writes_keys_type         — frozenset | None
test_repr_nonempty            — repr(result) is non-empty string
test_as_list_returns_tuple    — result._as_list() → tuple
test_composition_primary_op   — >> or + or | doesn't raise
test_frozen_if_dataclass      — mutation raises FrozenInstanceError
```

**Count**: ~8 tests × 70 operations = **~560 tests**, all generated.

### Tier 2: Semantic Correctness (Handcoded, Targeted)

Each operation's *behavior* needs handcoded tests:

```python
# S.pick — verify it keeps only named keys
def test_pick_keeps_named():
    t = S.pick("a", "b")
    result = t({"a": 1, "b": 2, "c": 3})
    assert result == StateReplacement({"a": 1, "b": 2})

def test_pick_preserves_scoped():
    t = S.pick("a")
    result = t({"a": 1, "app:x": 2, "user:y": 3})
    # scoped keys not in replacement — handled by FnAgent
    assert result == StateReplacement({"a": 1})

# C.window — verify compilation output
def test_window_compile():
    spec = C.window(n=3)
    compiled = _compile_context_spec("Do X.", spec)
    assert compiled["include_contents"] == "none"
    assert compiled["instruction"] is not None  # provider function
```

**Count**: ~3-5 tests per operation = **~250 handcoded tests**.

### Tier 3: Composition Properties (Generated via Hypothesis)

Property-based tests for algebraic laws:

```python
from hypothesis import given, strategies as st

# Identity law: S.identity() >> t == t
@given(keys=st.lists(st.text(min_size=1), min_size=1))
def test_identity_left(keys):
    t = S.pick(*keys)
    composed = S.identity() >> t
    state = {k: i for i, k in enumerate(keys)}
    assert composed(state) == t(state)

# Associativity: (a >> b) >> c == a >> (b >> c)
@given(keys=st.lists(st.text(min_size=1, max_size=5), min_size=3, max_size=3))
def test_chain_associativity(keys):
    a, b, c = S.set(**{keys[0]: 1}), S.set(**{keys[1]: 2}), S.set(**{keys[2]: 3})
    left = (a >> b) >> c
    right = a >> (b >> c)
    state = {}
    assert left(state) == right(state)

# + commutativity for StateDelta (when no key conflicts)
@given(
    k1=st.text(min_size=1, max_size=5),
    k2=st.text(min_size=1, max_size=5).filter(lambda x: x != k1),
)
def test_combine_commutative_no_conflict(k1, k2):
    a = S.set(**{k1: 1})
    b = S.set(**{k2: 2})
    state = {}
    assert (a + b)(state) == (b + a)(state)

# C union is commutative for non-conflicting blocks
def test_c_union_commutative():
    a = C.from_state("x")
    b = C.from_state("y")
    # Both orderings should produce equivalent compiled output
    assert type(a + b) == type(b + a) == CComposite
```

**Count**: ~20 property tests covering algebraic laws.

### Tier 4: Integration (Handcoded, End-to-End)

Verify that namespace specs survive the full build pipeline:

```python
def test_context_spec_survives_build():
    agent = (
        Agent("test", "gemini-2.5-flash")
        .instruct("Do things.")
        .context(C.window(n=3) + C.from_state("topic"))
        .build()
    )
    assert agent.include_contents == "none"
    assert callable(agent.instruction)

def test_prompt_spec_survives_build():
    agent = (
        Agent("test", "gemini-2.5-flash")
        .instruct(P.role("Expert.") + P.task("Analyze."))
        .build()
    )
    assert "Expert" in agent.instruction
    assert "Analyze" in agent.instruction

def test_stransform_in_pipeline():
    pipeline = (
        Agent("a", "gemini-2.5-flash").writes("result")
        >> S.pick("result")
        >> Agent("b", "gemini-2.5-flash")
    ).build()
    assert len(pipeline.sub_agents) >= 2
```

**Count**: ~30 integration tests.

### Total Test Budget

| Tier | Generated? | Count | Purpose |
|------|:---:|------:|---------|
| Protocol conformance | Yes | ~560 | Every op has _kind, keys, repr, compose |
| Semantic correctness | No | ~250 | Each op does what it claims |
| Composition properties | Partial | ~20 | Algebraic laws (identity, assoc, commute) |
| Integration | No | ~30 | Specs survive build pipeline |
| **Total** | | **~860** | |

---

## Generator Integration: Where It Fits

### New Files in `scripts/`

```
scripts/
  namespace_generator/
    __init__.py
    __main__.py         # Entry point: python -m scripts.namespace_generator
    manifest.py         # Parse namespace.toml
    stub_emitter.py     # Emit .pyi stubs for namespace classes
    ir_emitter.py       # Emit _ir_namespaces.py
    test_emitter.py     # Emit Tier 1 protocol tests
    doc_emitter.py      # Emit API reference tables
```

### New Justfile Commands

```text
# Generate namespace stubs, IR, tests, docs
namespace-gen:
    python -m scripts.namespace_generator seeds/namespace.toml

# Full pipeline now includes namespace generation
all: scan seed generate namespace-gen docs
```

### Integration with Existing Pipeline

```
scanner.py → manifest.json → seed_generator → seed.toml → generator → builders
                                                    ↓
                                          namespace.toml (new, hand-maintained)
                                                    ↓
                                        namespace_generator (new)
                                                    ↓
                              ┌──────────────┬───────────────┬──────────────┐
                              ▼              ▼               ▼              ▼
                        _*.pyi stubs   _ir_namespaces.py   tests/gen/   docs/gen/
```

The namespace manifest is **not** auto-generated from ADK — it's
hand-maintained because namespace operations are design decisions,
not reflections of upstream classes. But it feeds into the same
generator infrastructure pattern.

---

## Implementation Phases

### Phase 1: Protocol Alignment (No Generator Yet)

Handcoded changes to make all six namespaces structurally uniform:

1. Add `_kind` property to `STransform`, `MComposite`, `TComposite`
2. Add `_as_list()` to `STransform`, `MComposite`, `TComposite`
3. Add `_reads_keys`/`_writes_keys` to C and P leaf types
4. Refactor C `__post_init__` → deferred compilation
5. Add `__repr__` to any types missing it

Estimated: ~200 lines of changes across 4 files.

### Phase 2: Namespace Manifest

Write `seeds/namespace.toml` declaring all 70+ operations.
This is documentation-as-code — forces you to enumerate every
operation and its metadata.

Estimated: ~400 lines of TOML.

### Phase 3: Generator & Tests

Build `scripts/namespace_generator/` and generate:
- `.pyi` stubs
- Protocol conformance tests
- IR node definitions

Estimated: ~500 lines of generator code, ~560 generated test lines.

### Phase 4: CI Gate

Add `just check-namespace` to CI:
1. Regenerate from `namespace.toml`
2. Diff against committed files
3. Fail if stale (same pattern as `just check-gen`)

---

## Summary: Value Proposition

| Without Uniformization | With Uniformization |
|----------------------|-------------------|
| 6 namespace modules with 3 different patterns | 6 modules conforming to 1 protocol |
| Contract checker blind to C, P | Full data-flow tracing across all 6 |
| ~50 manual tests, uneven coverage | ~860 tests, systematic coverage |
| New operations require 5 manual steps | New operations: add to TOML, write body, done |
| IDE autocomplete: read 5K lines of source | IDE autocomplete: generated .pyi stubs |
| No fingerprinting for S, C, A | Uniform fingerprinting for caching/versioning |
| Documentation manually maintained | API reference tables auto-generated |

The meta-engineering pattern that works for builders (scanner → seed →
generator) extends naturally to namespaces. The key difference: builder
generation is fully automatic (upstream ADK drives it), while namespace
generation is *partially* automatic (human manifest drives structure,
handcoded bodies drive semantics). Both reduce maintenance burden and
enforce consistency through generation.
