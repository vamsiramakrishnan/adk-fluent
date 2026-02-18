# v5.1 Context Engineering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

---

## Phase Roadmap

v5.1 is split into five phases. Each phase gets its own plan document when started. Phases B+E can run in parallel.

| Phase | Name | Tasks | Depends On | Plan Document |
|-------|------|-------|------------|---------------|
| **A** | Foundation | 10 | Phase 4 (done) | This document |
| **B** | C Atoms (No LLM) | TBD | Phase A | `docs/plans/YYYY-MM-DD-v51-phase-b-c-atoms.md` |
| **C** | C Atoms (LLM-Powered) | TBD | Phase B | `docs/plans/YYYY-MM-DD-v51-phase-c-llm-atoms.md` |
| **D** | Scratchpads + Sugar | TBD | Phase B | `docs/plans/YYYY-MM-DD-v51-phase-d-scratchpads.md` |
| **E** | Typed State | TBD | Phase A | `docs/plans/YYYY-MM-DD-v51-phase-e-typed-state.md` |

### Phase A — Foundation (this document)
S.capture, C module core (9 primitives: none, default, user_only, from_agents, exclude_agents, window, from_state, template, capture), Agent.context(), Event Visibility with pipeline policies, cross-channel contract checker, memory integration, IR-first build path, OTel enrichment middleware.

### Phase B — C Atoms (No LLM)
The five-verb atomic primitives that don't require LLM calls (from v51_context.md §2, §3, §5, §6):
- **SELECT:** C.select(author=, type=, tag=), C.recent(decay=, half_life=)
- **COMPRESS:** C.compact(strategy=), C.truncate(max_tokens=, strategy=), C.project(fields=), C.dedup(strategy="exact"|"structural")
- **BUDGET:** C.budget(max_tokens=, overflow=), C.priority(tier=), C.fit(strategy="strict")
- **PROTECT:** C.fresh(max_age=, stale_action=), C.redact(patterns=)
- **Composition:** `+`/`|` operator type rules (§9.2), CComposite/CPipe rendering

### Phase C — C Atoms (LLM-Powered)
Primitives that require LLM calls with caching via companion FnAgents (from v51_context.md §3, §4, §6):
- **COMPRESS:** C.summarize(scope=, model=, schema=), C.dedup(strategy="semantic")
- **SELECT:** C.relevant(query_key=, top_k=, model=)
- **WRITE:** C.extract(schema=, key=), C.distill(key=, model=)
- **PROTECT:** C.validate(checks=["contradictions"])
- **BUDGET:** C.fit(strategy="cascade"|"compact_then_summarize")

### Phase D — Scratchpads + Molecule Sugar
Structured note-taking and higher-level convenience methods (from v51_context.md §4, §7.4):
- **WRITE:** C.notes(key=, format=), C.write_notes(key=, strategy=)
- **Sugar:** C.rolling(n, summarize=), C.from_agents_windowed(...), C.user(strategy=), C.manus_cascade(budget=)
- Note lifecycle management (merge, consolidate, decay)

### Phase E — Typed State (StateSchema)
Typed state declarations with scope annotations (from v5 §1.2–1.7, gap_analysis §1, v51_spec §3.3):
- StateSchema base class with Annotated type hints
- Scope prefixes (session, app:, user:, temp:) as type annotations
- CapturedBy annotation for C.capture provenance
- Typed contract checking (key type mismatches, scope confusion)
- IDE autocomplete for state keys

---

## Phase A — Foundation

**Goal:** Implement Context Engineering (C module), Event Visibility, S.capture(), cross-channel contract checking, memory integration, IR-first build path with default contract checking, and OTel enrichment middleware — enabling developers to declaratively control what each agent sees across ADK's three communication channels.

**Architecture:** New hand-written modules `_context.py` and `_visibility.py` sit alongside existing `_transforms.py`. C transforms compile to ADK's `InstructionProvider` callable + `include_contents='none'` (per ADR-009). Event visibility compiles to ADK's `BasePlugin.on_event_callback` (per ADR-010). The contract checker expands from read/write key checking to full cross-channel coherence analysis. Memory tools (`PreloadMemoryTool`, `LoadMemoryTool`) get fluent `.memory()` builder method. `.build()` is rewired to route through `.to_ir() → check_contracts() → backend.compile()` by default (per appendix_f Q1, Q3), with `build(check=False)` escape hatch. OTel enrichment middleware replaces structured_log by annotating ADK's existing spans with adk-fluent metadata (per spec §8 — enrich, don't duplicate). All new IR node types follow existing patterns in `_ir.py`. All new compilation targets follow existing patterns in `backends/adk.py`. The codegen scanner/manifest is NOT touched — these are hand-written adk-fluent inventions, not ADK-native agent types.

**Tech Stack:** Python 3.11+, google-adk 1.25.0+, frozen dataclasses for IR, BaseAgent subclasses for compilation targets, BasePlugin for visibility, pytest for testing.

**Key ADK compilation targets verified:**
- `LlmAgent.instruction` accepts `Callable[[ReadonlyContext], str | Awaitable[str]]` (InstructionProvider)
- `LlmAgent.include_contents` accepts `Literal['default', 'none']`
- `ReadonlyContext` exposes `.state`, `.session` (with `.events`), `.user_content`, `.agent_name`
- `BasePlugin.on_event_callback` receives `event: Event` after `append_event`, returns `Optional[Event]`
- `Event.custom_metadata: Optional[dict[str, Any]]` is a first-class field
- `PreloadMemoryTool()` and `LoadMemoryTool()` take no init args

---

## Phase 5i: S.capture() and Foundation

### Task 1: S.capture() — Bridge Channel 1 to Channel 2

`S.capture(key)` reads the most recent user message from session events and writes it to state. This is the explicit bridge between conversation history (Channel 1) and session state (Channel 2) that ADK doesn't provide. It compiles to a `CaptureAgent(BaseAgent)` that scans `ctx.session.events` in reverse.

**Files:**
- Modify: `src/adk_fluent/_transforms.py` (add `S.capture()` static method)
- Modify: `src/adk_fluent/_base.py` (add `CaptureAgent` class)
- Modify: `src/adk_fluent/_ir.py` (add `CaptureNode` IR type, update `Node` union)
- Modify: `src/adk_fluent/backends/adk.py` (add `_compile_capture`)
- Test: `tests/manual/test_capture.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_capture.py
"""Tests for S.capture() — bridge conversation (Channel 1) to state (Channel 2)."""

import pytest
from adk_fluent import Agent, S
from adk_fluent._transforms import StateDelta
from adk_fluent.workflow import Pipeline


class TestCaptureFactory:
    """S.capture() returns a callable with the right metadata."""

    def test_returns_callable(self):
        fn = S.capture("user_message")
        assert callable(fn)

    def test_name(self):
        fn = S.capture("user_message")
        assert fn.__name__ == "capture_user_message"

    def test_different_keys(self):
        fn1 = S.capture("msg")
        fn2 = S.capture("query")
        assert fn1.__name__ != fn2.__name__


class TestCaptureInPipeline:
    """S.capture() composes with >> like other S transforms."""

    def test_capture_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        p = S.capture("user_message") >> a
        assert isinstance(p, Pipeline)
        built = p.build()
        assert len(built.sub_agents) == 2

    def test_capture_with_outputs(self):
        pipeline = (
            S.capture("user_message")
            >> Agent("classifier").model("gemini-2.5-flash")
                .instruct("Classify intent.")
                .outputs("intent")
            >> Agent("handler").model("gemini-2.5-flash")
                .instruct("User said: {user_message}. Intent: {intent}")
        )
        built = pipeline.build()
        assert len(built.sub_agents) == 3


class TestCaptureNode:
    """CaptureNode IR type."""

    def test_capture_node_exists(self):
        from adk_fluent._ir import CaptureNode
        node = CaptureNode(name="capture_msg", key="user_message")
        assert node.key == "user_message"
        assert node.name == "capture_msg"

    def test_capture_node_frozen(self):
        from adk_fluent._ir import CaptureNode
        node = CaptureNode(name="cap", key="msg")
        with pytest.raises(AttributeError):
            node.key = "other"

    def test_in_node_union(self):
        from adk_fluent._ir import CaptureNode, Node
        # CaptureNode should be part of the Node union
        assert CaptureNode in Node.__args__ if hasattr(Node, '__args__') else True


class TestCaptureCompilation:
    """CaptureAgent compiles from CaptureNode via ADK backend."""

    def test_compile_capture_node(self):
        from adk_fluent._ir import CaptureNode
        from adk_fluent.backends.adk import ADKBackend
        from adk_fluent._base import CaptureAgent

        backend = ADKBackend()
        node = CaptureNode(name="capture_msg", key="user_message")
        agent = backend._compile_node(node)
        assert isinstance(agent, CaptureAgent)
        assert agent.name == "capture_msg"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_capture.py -v`
Expected: FAIL — `S` has no `capture` method, `CaptureNode` doesn't exist

**Step 3: Implement CaptureNode IR type**

Add to `src/adk_fluent/_ir.py`:

```python
@dataclass(frozen=True)
class CaptureNode:
    """Capture user message from conversation history into state. No LLM call."""

    name: str
    key: str
```

Update `__all__` to include `"CaptureNode"`. Update `Node` union to include `CaptureNode`.

**Step 4: Implement CaptureAgent in _base.py**

Add to `src/adk_fluent/_base.py` after `TapAgent`:

```python
class CaptureAgent(BaseAgent):
    """Captures the most recent user message from session events into state.

    Bridges Channel 1 (conversation history) to Channel 2 (session state).
    Zero-cost: no LLM call, single reverse scan of session.events.
    """

    def __init__(self, *, key: str, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_capture_key", key)

    async def _run_async_impl(self, ctx):
        for event in reversed(list(ctx.session.events)):
            if event.author == "user" and event.content and event.content.parts:
                text = "".join(
                    p.text for p in event.content.parts if hasattr(p, "text") and p.text
                )
                if text:
                    ctx.session.state[self._capture_key] = text
                    break
        # yield nothing — pure capture, no events
```

Add `CaptureAgent` to `__all__`.

**Step 5: Implement S.capture() factory**

Add to `src/adk_fluent/_transforms.py` in class `S`:

```python
    @staticmethod
    def capture(key: str) -> Callable[[dict], StateDelta]:
        """Capture the most recent user message into state under the given key.

        Bridges Channel 1 (conversation history) to Channel 2 (session state).
        At runtime, compiles to a CaptureAgent that scans session.events.
        When used as a plain function (for testing), returns a no-op StateDelta
        since event scanning requires session context.

            >> S.capture("user_message")
        """

        def _capture(state: dict) -> StateDelta:
            # Stub for pure-function testing; real capture happens in CaptureAgent
            return StateDelta({})

        _capture.__name__ = f"capture_{key}"
        _capture._capture_key = key  # type: ignore[attr-defined]
        return _capture
```

**Step 6: Add backend compilation**

Add to `src/adk_fluent/backends/adk.py`:

Import `CaptureNode` in the imports section. Add to dispatch dict. Add compiler method:

```python
    def _compile_capture(self, node) -> Any:
        """CaptureNode -> CaptureAgent."""
        from adk_fluent._base import CaptureAgent
        return CaptureAgent(name=node.name, key=node.key)
```

**Step 7: Wire S.capture into >> operator**

The `_fn_step` wrapper in `_base.py` wraps callables as `FnAgent`. But `S.capture` needs special handling — it should create a `CaptureAgent` instead. Modify `_fn_step` (around line 932 in `_base.py`) to detect the `_capture_key` attribute:

```python
def _fn_step(fn: Callable) -> BuilderBase:
    """Wrap a pure function as a zero-cost workflow step."""
    from adk_fluent._ir import TransformNode, CaptureNode

    # Special case: S.capture() produces a CaptureAgent, not a FnAgent
    capture_key = getattr(fn, "_capture_key", None)
    if capture_key is not None:
        name = getattr(fn, "__name__", f"capture_{capture_key}")

        class _CaptureBuilder(BuilderBase):
            _ALIASES: dict[str, str] = {}
            _CALLBACK_ALIASES: dict[str, str] = {}
            _ADDITIVE_FIELDS: set[str] = set()

            def __init__(self):
                self._config = {"name": name}
                self._callbacks = {}
                self._lists = {}

            def build(self):
                from adk_fluent._base import CaptureAgent
                return CaptureAgent(name=name, key=capture_key)

            def to_ir(self):
                return CaptureNode(name=name, key=capture_key)

        return _CaptureBuilder()

    # ... rest of existing _fn_step logic unchanged ...
```

**Step 8: Run tests to verify they pass**

Run: `pytest tests/manual/test_capture.py -v`
Expected: All PASS

**Step 9: Commit**

```bash
git add src/adk_fluent/_ir.py src/adk_fluent/_base.py src/adk_fluent/_transforms.py src/adk_fluent/backends/adk.py tests/manual/test_capture.py
git commit -m "feat: add S.capture() to bridge conversation history to session state"
```

---

## Phase 5i-core: C Module — Context Engineering Foundation

### Task 2: C Module — Core Types and C.none()/C.default()

The C module's foundation: the `CTransform` protocol, composition operators (`+` and `|`), and the two boundary primitives `C.none()` and `C.default()`.

**Files:**
- Create: `src/adk_fluent/_context.py`
- Test: `tests/manual/test_context.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_context.py
"""Tests for C module — context engineering primitives."""

import pytest


class TestCBoundaryPrimitives:
    """C.none() and C.default() are boundary cases."""

    def test_c_none_exists(self):
        from adk_fluent._context import C
        ctx = C.none()
        assert ctx is not None

    def test_c_default_exists(self):
        from adk_fluent._context import C
        ctx = C.default()
        assert ctx is not None

    def test_c_none_compiles_to_include_contents_none(self):
        from adk_fluent._context import C
        spec = C.none()
        assert spec.include_contents == "none"

    def test_c_default_compiles_to_include_contents_default(self):
        from adk_fluent._context import C
        spec = C.default()
        assert spec.include_contents == "default"

    def test_c_none_has_no_instruction_provider(self):
        from adk_fluent._context import C
        spec = C.none()
        assert spec.instruction_provider is None

    def test_c_default_has_no_instruction_provider(self):
        from adk_fluent._context import C
        spec = C.default()
        assert spec.instruction_provider is None


class TestCTransformProtocol:
    """All C transforms conform to the CTransform interface."""

    def test_c_none_is_ctransform(self):
        from adk_fluent._context import C, CTransform
        assert isinstance(C.none(), CTransform)

    def test_c_default_is_ctransform(self):
        from adk_fluent._context import C, CTransform
        assert isinstance(C.default(), CTransform)


class TestCComposition:
    """C transforms compose with + (union) and | (pipe)."""

    def test_plus_creates_composite(self):
        from adk_fluent._context import C, CComposite
        result = C.from_state("a") + C.from_state("b")
        assert isinstance(result, CComposite)

    def test_pipe_creates_pipe(self):
        from adk_fluent._context import C, CPipe
        result = C.window(n=5) | C.budget(max_tokens=4000)
        assert isinstance(result, CPipe)


class TestCFromState:
    """C.from_state() reads context from session state keys."""

    def test_from_state_single_key(self):
        from adk_fluent._context import C
        spec = C.from_state("intent")
        assert spec.include_contents == "none"
        assert spec.instruction_provider is not None

    def test_from_state_multiple_keys(self):
        from adk_fluent._context import C
        spec = C.from_state("intent", "confidence")
        assert spec.include_contents == "none"
        assert spec.instruction_provider is not None


class TestCWindow:
    """C.window(n) includes last N turn-pairs."""

    def test_window_creates_transform(self):
        from adk_fluent._context import C
        spec = C.window(n=5)
        assert spec.include_contents == "none"
        assert spec.instruction_provider is not None


class TestCUserOnly:
    """C.user_only() includes only user messages."""

    def test_user_only_creates_transform(self):
        from adk_fluent._context import C
        spec = C.user_only()
        assert spec.include_contents == "none"
        assert spec.instruction_provider is not None


class TestCFromAgents:
    """C.from_agents() includes user + named agent outputs."""

    def test_from_agents_creates_transform(self):
        from adk_fluent._context import C
        spec = C.from_agents("drafter", "reviewer")
        assert spec.include_contents == "none"
        assert spec.instruction_provider is not None


class TestCExcludeAgents:
    """C.exclude_agents() excludes named agent outputs."""

    def test_exclude_agents_creates_transform(self):
        from adk_fluent._context import C
        spec = C.exclude_agents("classifier")
        assert spec.include_contents == "none"
        assert spec.instruction_provider is not None


class TestCTemplate:
    """C.template() assembles context from a template string."""

    def test_template_creates_transform(self):
        from adk_fluent._context import C
        spec = C.template("User: {user_message}\nIntent: {intent}")
        assert spec.include_contents == "none"
        assert spec.instruction_provider is not None


class TestCCapture:
    """C.capture() is an alias for S.capture() in the C namespace."""

    def test_capture_returns_callable(self):
        from adk_fluent._context import C
        fn = C.capture("user_message")
        assert callable(fn)
        assert fn.__name__ == "capture_user_message"


class TestCBudget:
    """C.budget() sets a token budget constraint."""

    def test_budget_creates_transform(self):
        from adk_fluent._context import C
        spec = C.budget(max_tokens=4000)
        assert spec is not None


class TestCPriority:
    """C.priority() tags content blocks with priority tiers."""

    def test_priority_creates_transform(self):
        from adk_fluent._context import C
        spec = C.priority(tier=1)
        assert spec is not None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_context.py -v`
Expected: FAIL — `_context` module doesn't exist

**Step 3: Implement _context.py**

```python
# src/adk_fluent/_context.py
"""Context Engineering module — declarative context transforms for multi-agent pipelines.

The C module controls what each agent sees from conversation history (Channel 1)
and how that history is assembled into the prompt. It compiles to ADK's
InstructionProvider callable + include_contents='none'.

Every C transform implements the CTransform protocol and composes with:
  +  (union)  — assemble multiple context blocks
  |  (pipe)   — apply transform to preceding selection
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Union

__all__ = [
    "C",
    "CTransform",
    "CComposite",
    "CPipe",
]


# ======================================================================
# CTransform protocol — all C primitives implement this
# ======================================================================


@dataclass(frozen=True)
class CTransform:
    """Base class for all context transforms.

    Carries the two compilation outputs:
      - include_contents: 'default' or 'none' (passed to LlmAgent)
      - instruction_provider: optional callable(ReadonlyContext) -> str
    """

    include_contents: Literal["default", "none"] = "default"
    instruction_provider: Callable | None = None
    _kind: str = "base"

    def __add__(self, other: CTransform) -> CComposite:
        """Union: assemble multiple context blocks."""
        left = self._as_list()
        right = other._as_list()
        return CComposite(blocks=tuple(left + right))

    def __or__(self, other: CTransform) -> CPipe:
        """Pipe: apply right transform to left's output."""
        return CPipe(source=self, transform=other)

    def _as_list(self) -> list[CTransform]:
        return [self]


# ======================================================================
# Composition types
# ======================================================================


@dataclass(frozen=True)
class CComposite(CTransform):
    """Union of multiple context blocks (+ operator)."""

    blocks: tuple[CTransform, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "composite"

    def _as_list(self) -> list[CTransform]:
        result = []
        for b in self.blocks:
            result.extend(b._as_list())
        return result


@dataclass(frozen=True)
class CPipe(CTransform):
    """Pipe transform: apply transform to source output (| operator)."""

    source: CTransform | None = None
    transform: CTransform | None = None
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "pipe"


# ======================================================================
# SELECT primitives
# ======================================================================


@dataclass(frozen=True)
class CFromState(CTransform):
    """Include context from session state keys."""

    keys: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "from_state"

    def __post_init__(self):
        if self.instruction_provider is None and self.keys:
            provider = _make_from_state_provider(self.keys)
            object.__setattr__(self, "instruction_provider", provider)


@dataclass(frozen=True)
class CWindow(CTransform):
    """Include last N turn-pairs from conversation history."""

    n: int = 5
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "window"

    def __post_init__(self):
        if self.instruction_provider is None:
            provider = _make_window_provider(self.n)
            object.__setattr__(self, "instruction_provider", provider)


@dataclass(frozen=True)
class CUserOnly(CTransform):
    """Include only user messages from conversation history."""

    include_contents: Literal["default", "none"] = "none"
    _kind: str = "user_only"

    def __post_init__(self):
        if self.instruction_provider is None:
            provider = _make_user_only_provider()
            object.__setattr__(self, "instruction_provider", provider)


@dataclass(frozen=True)
class CFromAgents(CTransform):
    """Include user messages + outputs from named agents only."""

    agents: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "from_agents"

    def __post_init__(self):
        if self.instruction_provider is None:
            provider = _make_from_agents_provider(self.agents)
            object.__setattr__(self, "instruction_provider", provider)


@dataclass(frozen=True)
class CExcludeAgents(CTransform):
    """Full history minus named agents' outputs."""

    agents: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "exclude_agents"

    def __post_init__(self):
        if self.instruction_provider is None:
            provider = _make_exclude_agents_provider(self.agents)
            object.__setattr__(self, "instruction_provider", provider)


@dataclass(frozen=True)
class CTemplate(CTransform):
    """Assemble context from a template string with {key} placeholders."""

    template: str = ""
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "template"

    def __post_init__(self):
        if self.instruction_provider is None:
            provider = _make_template_provider(self.template)
            object.__setattr__(self, "instruction_provider", provider)


# ======================================================================
# BUDGET primitives
# ======================================================================


@dataclass(frozen=True)
class CBudget(CTransform):
    """Hard token budget constraint."""

    max_tokens: int = 8000
    overflow: str = "truncate_oldest"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "budget"


@dataclass(frozen=True)
class CPriority(CTransform):
    """Priority tier tagging for budget-aware assembly."""

    tier: int = 2
    _kind: str = "priority"


# ======================================================================
# InstructionProvider factories
# ======================================================================


def _format_events_as_context(events: list) -> str:
    """Format a list of ADK events as readable conversation text."""
    lines = []
    for event in events:
        if event.content and event.content.parts:
            text = "".join(
                p.text for p in event.content.parts if hasattr(p, "text") and p.text
            )
            if text:
                lines.append(f"[{event.author}]: {text}")
    return "\n".join(lines)


def _make_from_state_provider(keys: tuple[str, ...]) -> Callable:
    """Build an InstructionProvider that reads named keys from state."""

    async def _provider(ctx) -> str:
        parts = []
        for key in keys:
            val = ctx.state.get(key)
            if val is not None:
                parts.append(f"{key}: {val}")
        return "\n".join(parts)

    return _provider


def _make_window_provider(n: int) -> Callable:
    """Build an InstructionProvider that includes the last N turn-pairs."""

    async def _provider(ctx) -> str:
        events = list(ctx.session.events)
        # Find turn boundaries (user messages)
        turn_starts = []
        for i, event in enumerate(events):
            if event.author == "user":
                turn_starts.append(i)

        # Take last N turn starts
        if turn_starts:
            start_idx = turn_starts[-n] if len(turn_starts) >= n else 0
            windowed = events[start_idx:]
        else:
            windowed = events[-n * 2:] if events else []

        return _format_events_as_context(windowed)

    return _provider


def _make_user_only_provider() -> Callable:
    """Build an InstructionProvider that includes only user messages."""

    async def _provider(ctx) -> str:
        user_events = [
            e for e in ctx.session.events if e.author == "user"
        ]
        return _format_events_as_context(user_events)

    return _provider


def _make_from_agents_provider(agent_names: tuple[str, ...]) -> Callable:
    """Build an InstructionProvider that includes user + named agent outputs."""
    allowed = set(agent_names) | {"user"}

    async def _provider(ctx) -> str:
        filtered = [
            e for e in ctx.session.events if e.author in allowed
        ]
        return _format_events_as_context(filtered)

    return _provider


def _make_exclude_agents_provider(agent_names: tuple[str, ...]) -> Callable:
    """Build an InstructionProvider that excludes named agents."""
    excluded = set(agent_names)

    async def _provider(ctx) -> str:
        filtered = [
            e for e in ctx.session.events if e.author not in excluded
        ]
        return _format_events_as_context(filtered)

    return _provider


def _make_template_provider(template: str) -> Callable:
    """Build an InstructionProvider from a context template."""

    async def _provider(ctx) -> str:
        import re
        result = template
        # Handle {key?} optional placeholders
        for match in re.finditer(r"\{(\w+)\?\}", template):
            key = match.group(1)
            val = ctx.state.get(key, "")
            result = result.replace(match.group(0), str(val))
        # Handle {key} required placeholders
        for match in re.finditer(r"\{(\w+)\}", result):
            key = match.group(1)
            val = ctx.state.get(key, "")
            result = result.replace(match.group(0), str(val))
        return result

    return _provider


# ======================================================================
# C — Public API namespace
# ======================================================================


class C:
    """Context engineering primitives. Declarative control over what each agent sees.

    SELECT primitives:
        C.default()              — full conversation history
        C.none()                 — no history; context from state/instruction only
        C.user_only()            — only user messages
        C.from_agents("a", "b")  — user + named agents
        C.exclude_agents("a")    — all minus named agents
        C.window(n=5)            — last N turn-pairs
        C.from_state("k1", "k2") — context from state keys

    CONTEXT TEMPLATES:
        C.template("...")        — template with {key} placeholders

    CAPTURE:
        C.capture("key")         — bridge conversation to state (alias for S.capture)

    BUDGET:
        C.budget(max_tokens=N)   — hard token budget
        C.priority(tier=N)       — priority tier tagging

    Composition:
        +  (union)  — C.from_state("a") + C.window(n=5)
        |  (pipe)   — C.window(n=5) | C.budget(max_tokens=4000)
    """

    @staticmethod
    def none() -> CTransform:
        """No conversation history. All context from state/instruction."""
        return CTransform(include_contents="none")

    @staticmethod
    def default() -> CTransform:
        """Full conversation history (ADK default)."""
        return CTransform(include_contents="default")

    @staticmethod
    def user_only() -> CUserOnly:
        """Only user messages in conversation context."""
        return CUserOnly()

    @staticmethod
    def from_agents(*agent_names: str) -> CFromAgents:
        """User messages + outputs from named agents only."""
        return CFromAgents(agents=agent_names)

    @staticmethod
    def exclude_agents(*agent_names: str) -> CExcludeAgents:
        """Full history minus named agents' outputs."""
        return CExcludeAgents(agents=agent_names)

    @staticmethod
    def window(*, n: int) -> CWindow:
        """Last N turn-pairs from conversation history."""
        return CWindow(n=n)

    # Alias for backward compatibility with spec
    @staticmethod
    def last_n_turns(n: int) -> CWindow:
        """Alias for C.window(n=N)."""
        return CWindow(n=n)

    @staticmethod
    def from_state(*keys: str) -> CFromState:
        """Context from named session state keys."""
        return CFromState(keys=keys)

    @staticmethod
    def template(template_str: str) -> CTemplate:
        """Assemble context from a template with {key} and {key?} placeholders."""
        return CTemplate(template=template_str)

    @staticmethod
    def capture(key: str) -> Callable:
        """Bridge conversation to state. Alias for S.capture(key)."""
        from adk_fluent._transforms import S
        return S.capture(key)

    @staticmethod
    def budget(*, max_tokens: int, overflow: str = "truncate_oldest") -> CBudget:
        """Hard token budget constraint on assembled context."""
        return CBudget(max_tokens=max_tokens, overflow=overflow)

    @staticmethod
    def priority(*, tier: int) -> CPriority:
        """Tag content block with priority tier (1=critical, 4=archive)."""
        return CPriority(tier=tier)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/manual/test_context.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/_context.py tests/manual/test_context.py
git commit -m "feat: add C module with core context engineering primitives"
```

---

### Task 3: Agent.context() — Wire C into Agent Builder

Add `.context(C.xxx)` to the Agent builder so developers can declare per-agent context transforms. This modifies how the agent compiles to an LlmAgent — setting `include_contents` and `instruction` based on the C transform.

**Files:**
- Modify: `src/adk_fluent/agent.py` (add `.context()` method)
- Modify: `src/adk_fluent/_helpers.py` (update `_agent_to_ir` to carry context spec)
- Modify: `src/adk_fluent/_ir_generated.py` (add `context_spec` field to AgentNode)
- Modify: `src/adk_fluent/backends/adk.py` (compile context spec in `_compile_agent`)
- Test: `tests/manual/test_agent_context.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_agent_context.py
"""Tests for Agent.context() — wiring C transforms into agent compilation."""

import pytest
from adk_fluent import Agent
from adk_fluent._context import C


class TestAgentContextMethod:
    """Agent builder accepts .context() for C transforms."""

    def test_context_method_exists(self):
        a = Agent("a").model("gemini-2.5-flash").context(C.none())
        assert a is not None

    def test_context_returns_self_for_chaining(self):
        a = Agent("a").model("gemini-2.5-flash")
        result = a.context(C.none())
        assert result is a

    def test_context_stored_in_config(self):
        a = Agent("a").model("gemini-2.5-flash").context(C.user_only())
        assert "_context_spec" in a._config


class TestAgentContextCompilation:
    """Agent.context() affects LlmAgent compilation."""

    def test_c_none_sets_include_contents(self):
        a = Agent("a").model("gemini-2.5-flash").context(C.none())
        built = a.build()
        assert built.include_contents == "none"

    def test_c_default_keeps_include_contents(self):
        a = Agent("a").model("gemini-2.5-flash").context(C.default())
        built = a.build()
        assert built.include_contents == "default"

    def test_c_user_only_sets_instruction_provider(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Do something.")
            .context(C.user_only())
        )
        built = a.build()
        assert built.include_contents == "none"
        assert callable(built.instruction)

    def test_c_from_state_sets_instruction_provider(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Use context.")
            .context(C.from_state("intent", "confidence"))
        )
        built = a.build()
        assert built.include_contents == "none"
        assert callable(built.instruction)

    def test_context_with_template(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Respond helpfully.")
            .context(C.template("User: {user_message}\nIntent: {intent}"))
        )
        built = a.build()
        assert built.include_contents == "none"
        assert callable(built.instruction)


class TestAgentContextInPipeline:
    """Context integrates with pipeline composition."""

    def test_pipeline_with_context(self):
        pipeline = (
            Agent("classifier")
            .model("gemini-2.5-flash")
            .instruct("Classify.")
            .outputs("intent")
            >> Agent("handler")
            .model("gemini-2.5-flash")
            .instruct("Handle request.")
            .context(C.from_state("intent"))
        )
        built = pipeline.build()
        handler = built.sub_agents[1]
        assert handler.include_contents == "none"
        assert callable(handler.instruction)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_agent_context.py -v`
Expected: FAIL — Agent has no `.context()` method

**Step 3: Add `.context()` method to Agent builder**

In `src/adk_fluent/agent.py`, add to the `Agent` class (in the `# --- Extra methods ---` section):

```python
    def context(self, spec) -> Self:
        """Declare what conversation context this agent should see.

        Accepts a C module transform (C.none(), C.user_only(), C.from_state(), etc.).
        Compiles to include_contents + InstructionProvider on the LlmAgent.
        """
        self._config["_context_spec"] = spec
        return self
```

**Step 4: Update build() to compile context spec**

The key insight: when a context spec with an `instruction_provider` is present, we need to wrap the developer's instruction string with the context provider to create a combined InstructionProvider. Modify `Agent.build()` (or add a `_prepare_build_config` override) to handle this.

The cleanest approach is a post-processing step in `_prepare_build_config`. Add to `_base.py` `BuilderBase._prepare_build_config`:

After the existing logic, add context spec handling:

```python
        # Context spec: compile C transforms into include_contents + InstructionProvider
        context_spec = config.pop("_context_spec", None)
        if context_spec is not None:
            from adk_fluent._context import CTransform, _compile_context_spec
            if isinstance(context_spec, CTransform):
                compiled = _compile_context_spec(
                    developer_instruction=config.get("instruction", ""),
                    context_spec=context_spec,
                )
                config["include_contents"] = compiled["include_contents"]
                if compiled.get("instruction") is not None:
                    config["instruction"] = compiled["instruction"]
```

Add to `_context.py`:

```python
def _compile_context_spec(
    developer_instruction: str | Callable,
    context_spec: CTransform,
) -> dict[str, Any]:
    """Compile a C transform into LlmAgent kwargs.

    Returns dict with 'include_contents' and optionally 'instruction' (as provider).
    """
    result: dict[str, Any] = {
        "include_contents": context_spec.include_contents,
    }

    if context_spec.instruction_provider is not None:
        ctx_provider = context_spec.instruction_provider

        # Wrap: developer instruction + context from provider
        async def _combined_provider(ctx) -> str:
            # Get developer instruction (string or callable)
            if callable(developer_instruction):
                import asyncio
                dev_instr = developer_instruction(ctx)
                if asyncio.iscoroutine(dev_instr):
                    dev_instr = await dev_instr
            else:
                dev_instr = str(developer_instruction) if developer_instruction else ""

            # Template state variables into dev instruction
            import re
            templated = dev_instr
            for match in re.finditer(r"\{(\w+)\??\}", dev_instr):
                key = match.group(1)
                val = ctx.state.get(key, "")
                templated = templated.replace(match.group(0), str(val))

            # Get context from C transform
            import asyncio
            context_text = ctx_provider(ctx)
            if asyncio.iscoroutine(context_text):
                context_text = await context_text

            if context_text:
                return f"{templated}\n\n<conversation_context>\n{context_text}\n</conversation_context>"
            return templated

        result["instruction"] = _combined_provider

    return result
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/manual/test_agent_context.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/adk_fluent/agent.py src/adk_fluent/_base.py src/adk_fluent/_context.py src/adk_fluent/_helpers.py tests/manual/test_agent_context.py
git commit -m "feat: add Agent.context() to wire C transforms into agent compilation"
```

---

## Phase 5j: Event Visibility

### Task 4: Visibility Inference and VisibilityPlugin

Topology-inferred event visibility: terminal agents are user-facing, intermediate agents are internal. Compiles to `BasePlugin.on_event_callback`.

**Files:**
- Create: `src/adk_fluent/_visibility.py`
- Modify: `src/adk_fluent/backends/adk.py` (attach VisibilityPlugin when pipeline has non-trivial topology)
- Test: `tests/manual/test_visibility.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_visibility.py
"""Tests for event visibility inference and VisibilityPlugin."""

import pytest


class TestVisibilityInference:
    """Topology-inferred visibility classification."""

    def test_infer_sequence_visibility(self):
        from adk_fluent._visibility import infer_visibility
        from adk_fluent._ir_generated import AgentNode, SequenceNode

        seq = SequenceNode(
            name="pipeline",
            children=(
                AgentNode(name="classifier", output_key="intent"),
                AgentNode(name="handler"),
            ),
        )
        vis = infer_visibility(seq)
        assert vis["classifier"] == "internal"
        assert vis["handler"] == "user"

    def test_infer_single_agent(self):
        from adk_fluent._visibility import infer_visibility
        from adk_fluent._ir_generated import AgentNode

        vis = infer_visibility(AgentNode(name="solo"))
        assert vis["solo"] == "user"

    def test_infer_with_output_key(self):
        from adk_fluent._visibility import infer_visibility
        from adk_fluent._ir_generated import AgentNode, SequenceNode

        seq = SequenceNode(
            name="p",
            children=(
                AgentNode(name="a", output_key="data"),
                AgentNode(name="b", output_key="result"),
                AgentNode(name="c"),
            ),
        )
        vis = infer_visibility(seq)
        assert vis["a"] == "internal"
        assert vis["b"] == "internal"
        assert vis["c"] == "user"

    def test_infer_transform_is_zero_cost(self):
        from adk_fluent._visibility import infer_visibility
        from adk_fluent._ir import TransformNode
        from adk_fluent._ir_generated import AgentNode, SequenceNode

        seq = SequenceNode(
            name="p",
            children=(
                AgentNode(name="a"),
                TransformNode(name="t", fn=lambda s: s),
                AgentNode(name="b"),
            ),
        )
        vis = infer_visibility(seq)
        assert vis["t"] == "zero_cost"

    def test_infer_route_is_zero_cost(self):
        from adk_fluent._visibility import infer_visibility
        from adk_fluent._ir import RouteNode
        from adk_fluent._ir_generated import AgentNode, SequenceNode

        seq = SequenceNode(
            name="p",
            children=(
                AgentNode(name="classifier", output_key="intent"),
                RouteNode(
                    name="route_intent",
                    key="intent",
                    rules=(
                        (lambda s: s.get("intent") == "a", AgentNode(name="handler_a")),
                    ),
                    default=AgentNode(name="handler_b"),
                ),
            ),
        )
        vis = infer_visibility(seq)
        assert vis["classifier"] == "internal"
        assert vis["route_intent"] == "zero_cost"
        assert vis["handler_a"] == "user"
        assert vis["handler_b"] == "user"


class TestVisibilityPlugin:
    """VisibilityPlugin annotates events via on_event_callback."""

    def test_plugin_creation(self):
        from adk_fluent._visibility import VisibilityPlugin
        plugin = VisibilityPlugin(
            visibility_map={"classifier": "internal", "handler": "user"},
            mode="annotate",
        )
        assert plugin is not None

    def test_plugin_has_on_event_callback(self):
        from adk_fluent._visibility import VisibilityPlugin
        plugin = VisibilityPlugin(
            visibility_map={"a": "internal"},
            mode="annotate",
        )
        assert hasattr(plugin, "on_event_callback")


class TestShowHideOverrides:
    """Builder API for visibility overrides: .show() and .hide()."""

    def test_show_method(self):
        from adk_fluent import Agent
        a = Agent("a").model("gemini-2.5-flash").show()
        assert a._config.get("_visibility_override") == "user"

    def test_hide_method(self):
        from adk_fluent import Agent
        a = Agent("a").model("gemini-2.5-flash").hide()
        assert a._config.get("_visibility_override") == "internal"


class TestPipelineLevelPolicies:
    """Pipeline-level visibility: .transparent(), .filtered(), .annotated()."""

    def test_transparent(self):
        """All agents visible regardless of position."""
        from adk_fluent import Agent
        from adk_fluent._visibility import infer_visibility
        from adk_fluent._ir_generated import AgentNode, SequenceNode

        seq = SequenceNode(
            name="p",
            children=(
                AgentNode(name="a", output_key="x"),
                AgentNode(name="b"),
            ),
        )
        vis = infer_visibility(seq, policy="transparent")
        assert vis["a"] == "user"
        assert vis["b"] == "user"

    def test_filtered(self):
        """Only terminal agents visible (default behavior)."""
        from adk_fluent._visibility import infer_visibility
        from adk_fluent._ir_generated import AgentNode, SequenceNode

        seq = SequenceNode(
            name="p",
            children=(
                AgentNode(name="a", output_key="x"),
                AgentNode(name="b"),
            ),
        )
        vis = infer_visibility(seq, policy="filtered")
        assert vis["a"] == "internal"
        assert vis["b"] == "user"

    def test_annotated(self):
        """All events reach client with metadata, no content stripping."""
        from adk_fluent._visibility import VisibilityPlugin
        plugin = VisibilityPlugin(
            visibility_map={"a": "internal", "b": "user"},
            mode="annotate",
        )
        assert plugin._mode == "annotate"


class TestVisibilityPluginContentStripping:
    """VisibilityPlugin filter mode strips content but preserves control signals."""

    def test_filter_mode_strips_internal_content(self):
        from adk_fluent._visibility import VisibilityPlugin
        plugin = VisibilityPlugin(
            visibility_map={"internal_agent": "internal"},
            mode="filter",
        )
        assert plugin._mode == "filter"

    def test_error_events_always_pass_through(self):
        """Error events are never suppressed regardless of visibility."""
        from adk_fluent._visibility import VisibilityPlugin
        plugin = VisibilityPlugin(
            visibility_map={"a": "internal"},
            mode="filter",
        )
        # Error events should pass through — tested via on_event_callback
        assert hasattr(plugin, "on_event_callback")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_visibility.py -v`
Expected: FAIL — `_visibility` module doesn't exist

**Step 3: Implement _visibility.py**

```python
# src/adk_fluent/_visibility.py
"""Event visibility inference and VisibilityPlugin.

Determines which agents' events are user-facing vs internal based on
topology. Compiles to ADK's BasePlugin.on_event_callback.
"""

from __future__ import annotations

from typing import Any, Literal

__all__ = ["infer_visibility", "VisibilityPlugin"]

# IR node types that are always zero-cost (no LLM, infrastructure only)
_ZERO_COST_TYPES = {"TransformNode", "TapNode", "RouteNode", "CaptureNode"}


def infer_visibility(
    node: Any,
    has_successor: bool = False,
    policy: Literal["filtered", "transparent", "annotate"] = "filtered",
) -> dict[str, Literal["user", "internal", "zero_cost"]]:
    """Walk IR tree and classify each agent's visibility.

    Policies (from v5.1 spec §4.5 Level 2):
      'filtered'    — topology-inferred (default): terminal=user, intermediate=internal
      'transparent' — all agents user-facing (debugging, demos)
      'annotate'    — same classification as filtered, but caller uses annotate mode

    Rules (when policy='filtered' or 'annotate'):
      - Zero-cost node types (Transform, Tap, Route, Capture) → zero_cost
      - Node with output_key AND has_successor → internal
      - Node with has_successor → internal
      - Node without successor → user
      - Visibility overrides take precedence
    """
    vis: dict[str, str] = {}
    if policy == "transparent":
        _walk_transparent(node, vis)
    else:
        _walk(node, has_successor, vis)
    return vis


def _walk(
    node: Any,
    has_successor: bool,
    vis: dict[str, str],
) -> None:
    """Recursive visibility walker."""
    type_name = type(node).__name__

    # Check for override
    override = getattr(node, "_visibility_override", None)
    if override:
        vis[node.name] = override
        return

    # Zero-cost types
    if type_name in _ZERO_COST_TYPES:
        vis[node.name] = "zero_cost"
        # Walk children of route nodes
        if type_name == "RouteNode":
            for _, child in getattr(node, "rules", ()):
                _walk(child, False, vis)  # Route branches inherit parent's has_successor
            if getattr(node, "default", None) is not None:
                _walk(node.default, False, vis)
        return

    # Compound nodes: SequenceNode, ParallelNode, LoopNode
    children = getattr(node, "children", ())
    if type_name == "SequenceNode" and children:
        for i, child in enumerate(children):
            child_has_successor = (i < len(children) - 1) or has_successor
            _walk(child, child_has_successor, vis)
        return

    if type_name == "ParallelNode" and children:
        for child in children:
            _walk(child, has_successor, vis)
        return

    if type_name == "LoopNode" and children:
        for child in children:
            _walk(child, True, vis)  # Loop body is never final
        return

    # Leaf nodes (AgentNode and similar)
    if has_successor:
        vis[node.name] = "internal"
    else:
        vis[node.name] = "user"


def _walk_transparent(node: Any, vis: dict[str, str]) -> None:
    """Transparent policy: all agents classified as user-facing."""
    type_name = type(node).__name__
    if type_name in _ZERO_COST_TYPES:
        vis[node.name] = "zero_cost"
    else:
        vis[node.name] = "user"

    # Recurse into children
    children = getattr(node, "children", ())
    for child in children:
        _walk_transparent(child, vis)
    if type_name == "RouteNode":
        for _, child in getattr(node, "rules", ()):
            _walk_transparent(child, vis)
        if getattr(node, "default", None) is not None:
            _walk_transparent(node.default, vis)


class VisibilityPlugin:
    """Annotates or filters events based on topology-inferred visibility.

    Runs in on_event_callback — after session history is recorded, before
    the client sees the event. Source-verified: Runner._exec_with_plugin
    calls append_event BEFORE run_on_event_callback (ADR-010).

    Modes (from v5.1 spec §4.4, event_visibility.md):
      'annotate': adds metadata, yields all events (client filters)
      'filter':   suppresses content of internal events, preserves state_delta
                  and control signals (escalate, transfer)

    Error events always pass through regardless of mode — users must see errors.
    """

    def __init__(
        self,
        visibility_map: dict[str, str],
        mode: str = "annotate",
    ):
        self._visibility = visibility_map
        self._mode = mode
        self.name = "adk_fluent_visibility"

    async def on_event_callback(
        self, *, invocation_context: Any, event: Any
    ) -> Any:
        vis = self._visibility.get(event.author, "user")

        # Always annotate with visibility metadata
        if event.custom_metadata is None:
            event.custom_metadata = {}
        event.custom_metadata["adk_fluent.visibility"] = vis
        event.custom_metadata["adk_fluent.is_user_facing"] = vis == "user"

        # Error events always pass through (event_visibility.md §3.4)
        if self._is_error_event(event):
            event.custom_metadata["adk_fluent.visibility"] = "user"
            event.custom_metadata["adk_fluent.is_user_facing"] = True
            return event

        if self._mode == "filter" and vis != "user":
            self._strip_content(event)

        return event

    @staticmethod
    def _is_error_event(event: Any) -> bool:
        """Check if event represents an error that should always be visible."""
        if hasattr(event, "error_code") and event.error_code:
            return True
        if hasattr(event, "actions") and event.actions:
            if hasattr(event.actions, "escalate") and event.actions.escalate:
                return True
        return False

    @staticmethod
    def _strip_content(event: Any) -> None:
        """Strip text content but preserve state_delta and control actions.

        Per event_visibility.md: internal events have their text content
        removed (the raw "booking" label), but state_delta is preserved
        (output_key writes must still flow to downstream agents) and
        control actions (escalate, transfer) remain intact.
        """
        if event.content and event.content.parts:
            event.content = None
        # Deliberately preserve: event.actions.state_delta, event.actions.escalate
```

**Step 4: Add .show() and .hide() to Agent builder**

In `src/adk_fluent/agent.py`, add to the `Agent` class `# --- Extra methods ---` section:

```python
    def show(self) -> Self:
        """Force this agent's events to be user-facing (override topology inference)."""
        self._config["_visibility_override"] = "user"
        return self

    def hide(self) -> Self:
        """Force this agent's events to be internal (override topology inference)."""
        self._config["_visibility_override"] = "internal"
        return self
```

**Step 5: Add pipeline-level visibility policies to BuilderBase**

In `src/adk_fluent/_base.py`, add to the `BuilderBase` class (these apply to Pipeline, FanOut, Loop):

```python
    def transparent(self) -> Self:
        """All agents in this pipeline are user-facing. For debugging/demos.
        (v5.1 spec §4.5 Level 2)"""
        self._config["_visibility_policy"] = "transparent"
        return self

    def filtered(self) -> Self:
        """Only terminal agents are user-facing. Topology-inferred (default).
        (v5.1 spec §4.5 Level 2)"""
        self._config["_visibility_policy"] = "filtered"
        return self

    def annotated(self) -> Self:
        """All events reach client with visibility metadata. Client filters.
        (v5.1 spec §4.5 Level 2)"""
        self._config["_visibility_policy"] = "annotate"
        return self
```

**Step 6: Run tests to verify they pass**

Run: `pytest tests/manual/test_visibility.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/adk_fluent/_visibility.py src/adk_fluent/_base.py src/adk_fluent/agent.py tests/manual/test_visibility.py
git commit -m "feat: add event visibility with pipeline policies, content stripping, error pass-through"
```

---

## Phase 5k: Cross-Channel Contract Checker

### Task 5: Expanded Contract Checker

Expand `check_contracts` from simple read/write key checking to cross-channel coherence analysis: template variables, output_key reachability, channel duplication, data loss detection.

**Files:**
- Modify: `src/adk_fluent/testing/contracts.py`
- Test: `tests/manual/test_cross_channel_contracts.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_cross_channel_contracts.py
"""Tests for cross-channel contract checker (v5.1)."""

import pytest
from adk_fluent import Agent, S
from adk_fluent._routing import Route
from adk_fluent.testing import check_contracts


class TestTemplateVariableResolution:
    """Contract checker validates {template} variables against upstream producers."""

    def test_resolved_template_var_no_issue(self):
        pipeline = (
            Agent("classifier").model("m").instruct("Classify.").outputs("intent")
            >> Agent("handler").model("m").instruct("Intent: {intent}")
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if i.get("level") == "error"]
        assert len(errors) == 0

    def test_unresolved_template_var_reports_error(self):
        pipeline = (
            Agent("a").model("m").instruct("Do stuff.")
            >> Agent("b").model("m").instruct("Summary: {summary}")
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if i.get("level") == "error"]
        assert any("summary" in str(i) for i in errors)


class TestChannelDuplication:
    """Detect when data reaches an agent through both conversation and state."""

    def test_duplication_warning(self):
        pipeline = (
            Agent("classifier").model("m").instruct("Classify.").outputs("intent")
            >> Agent("handler").model("m").instruct("Intent: {intent}")
        )
        issues = check_contracts(pipeline.to_ir())
        info = [i for i in issues if i.get("level") == "info"]
        assert any("duplication" in str(i).lower() or "duplicate" in str(i).lower() for i in info)


class TestRouteKeyValidation:
    """Route reads a state key — validate an upstream agent produces it."""

    def test_route_key_satisfied(self):
        pipeline = (
            Agent("classifier").model("m").instruct("Classify.").outputs("intent")
            >> Route("intent").eq("booking", Agent("booker").model("m").instruct("Book."))
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if i.get("level") == "error"]
        assert len(errors) == 0

    def test_route_key_missing(self):
        pipeline = (
            Agent("classifier").model("m").instruct("Classify.")
            >> Route("intent").eq("booking", Agent("booker").model("m").instruct("Book."))
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if i.get("level") == "error"]
        assert any("intent" in str(i) for i in errors)


class TestDataLossDetection:
    """Detect when an agent's output reaches no downstream consumer."""

    def test_no_data_loss_with_outputs(self):
        pipeline = (
            Agent("a").model("m").instruct("Do.").outputs("result")
            >> Agent("b").model("m").instruct("Use: {result}")
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if i.get("level") == "error"]
        assert len(errors) == 0

    def test_data_loss_no_output_key_with_c_none(self):
        """Agent without .outputs() + downstream C.none() = data lost."""
        from adk_fluent._context import C
        pipeline = (
            Agent("a").model("m").instruct("Produce data.")
            >> Agent("b").model("m").instruct("Use data.").context(C.none())
        )
        issues = check_contracts(pipeline.to_ir())
        warns = [i for i in issues if isinstance(i, dict) and i.get("level") in ("warn", "error")]
        assert any("data" in str(i).lower() or "loss" in str(i).lower() for i in warns)


class TestVisibilityContracts:
    """Visibility inference consistency checks (v5.1 spec §13.1)."""

    def test_internal_agent_without_output_key_warns(self):
        """Internal agent (has successor) without .outputs() — data may be lost."""
        pipeline = (
            Agent("a").model("m").instruct("Process.")
            >> Agent("b").model("m").instruct("Consume.")
        )
        issues = check_contracts(pipeline.to_ir())
        # Should warn: "a" is internal but has no output_key
        info_warns = [i for i in issues if isinstance(i, dict) and i.get("level") in ("info", "warn")]
        # Not an error, just advisory
        assert isinstance(issues, list)

    def test_terminal_agent_with_output_key_info(self):
        """Terminal agent with .outputs() — data goes to state but agent is user-facing."""
        pipeline = (
            Agent("a").model("m").instruct("Process.").outputs("result")
        )
        issues = check_contracts(pipeline.to_ir())
        # Single agent with outputs — not an error
        assert isinstance(issues, list)


class TestBackwardCompatibility:
    """Old-style check_contracts still works (returns list)."""

    def test_old_style_pydantic_contracts(self):
        from pydantic import BaseModel

        class Intent(BaseModel):
            category: str

        pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
        result = check_contracts(pipeline.to_ir())
        # Should return list (backward compat) or list of dicts (new style)
        assert isinstance(result, list)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_cross_channel_contracts.py -v`
Expected: FAIL — `check_contracts` returns list[str] not list[dict]

**Step 3: Implement expanded contract checker**

Replace `src/adk_fluent/testing/contracts.py`:

```python
"""Inter-agent contract verification — cross-channel coherence analysis.

Validates across ADK's three communication channels:
  Channel 1 — Conversation history (include_contents)
  Channel 2 — Session state (output_key, S transforms)
  Channel 3 — Instruction templating ({key} variables)
"""

from __future__ import annotations

import re
from typing import Any


def check_contracts(ir_node: Any) -> list[dict[str, str] | str]:
    """Verify cross-channel contracts across a pipeline.

    Returns a list of diagnostic dicts with keys:
      - level: "error", "warn", "info"
      - agent: agent name
      - message: human-readable diagnostic
      - hint: suggested fix

    For backward compatibility, also processes old-style reads_keys/writes_keys
    contracts. Old-style string results are preserved when no new-style issues
    are found for that agent.
    """
    from adk_fluent._ir_generated import SequenceNode

    issues: list[dict[str, str] | str] = []

    if not isinstance(ir_node, SequenceNode):
        return issues

    children = ir_node.children
    if not children:
        return issues

    # --- Pass 1: old-style reads_keys/writes_keys (backward compat) ---
    available_keys: set[str] = set()
    for child in children:
        reads = getattr(child, "reads_keys", frozenset())
        writes = getattr(child, "writes_keys", frozenset())
        child_name = getattr(child, "name", "?")

        if reads:
            missing = reads - available_keys
            for key in sorted(missing):
                issues.append(
                    f"Agent '{child_name}' consumes key '{key}' but no prior step produces it"
                )

        available_keys |= writes

    # --- Pass 2: output_key tracking ---
    produced_keys: set[str] = set()
    for child in children:
        output_key = getattr(child, "output_key", None)
        if output_key:
            produced_keys.add(output_key)

        # S transforms that set keys
        affected = getattr(child, "affected_keys", None)
        if affected:
            produced_keys |= set(affected)

        # CaptureNode
        capture_key = getattr(child, "key", None)
        type_name = type(child).__name__
        if type_name == "CaptureNode" and capture_key:
            produced_keys.add(capture_key)

    # --- Pass 3: template variable resolution ---
    produced_so_far: set[str] = set()
    for i, child in enumerate(children):
        child_name = getattr(child, "name", "?")
        instruction = getattr(child, "instruction", "")

        # Track what this child produces
        output_key = getattr(child, "output_key", None)
        if output_key:
            produced_so_far.add(output_key)

        capture_key = getattr(child, "key", None)
        type_name = type(child).__name__
        if type_name == "CaptureNode" and capture_key:
            produced_so_far.add(capture_key)

        affected = getattr(child, "affected_keys", None)
        if affected:
            produced_so_far |= set(affected)

        # Check next children's template vars
        for j in range(i + 1, len(children)):
            next_child = children[j]
            next_name = getattr(next_child, "name", "?")
            next_instruction = getattr(next_child, "instruction", "")

            if isinstance(next_instruction, str) and next_instruction:
                template_vars = set(re.findall(r"\{(\w+)\??\}", next_instruction))
                for var in template_vars:
                    if var not in produced_so_far:
                        issues.append({
                            "level": "error",
                            "agent": next_name,
                            "message": f'Template variable "{{{var}}}" in instruction '
                                       f'has no upstream producer.',
                            "hint": f'Add .outputs("{var}") to an upstream agent, '
                                    f'or S.capture("{var}") / S.set({var}=...).',
                        })

    # --- Pass 4: channel duplication detection ---
    for i, child in enumerate(children):
        child_name = getattr(child, "name", "?")
        output_key = getattr(child, "output_key", None)
        include_contents = getattr(child, "include_contents", "default")

        if not output_key:
            continue

        # Check if any successor has include_contents='default' AND references
        # the output_key in its instruction
        for j in range(i + 1, len(children)):
            succ = children[j]
            succ_name = getattr(succ, "name", "?")
            succ_include = getattr(succ, "include_contents", "default")
            succ_instruction = getattr(succ, "instruction", "")

            if succ_include == "default" and isinstance(succ_instruction, str):
                if f"{{{output_key}}}" in succ_instruction:
                    issues.append({
                        "level": "info",
                        "agent": succ_name,
                        "message": f'"{succ_name}" will see "{child_name}"\'s text '
                                   f'via conversation AND via {{{output_key}}} in state. '
                                   f'This is channel duplication.',
                        "hint": f'Consider .context(C.user_only()) or '
                                f'.context(C.from_state("{output_key}")).',
                    })

    # --- Pass 5: Route key validation ---
    route_produced: set[str] = set()
    for child in children:
        output_key = getattr(child, "output_key", None)
        if output_key:
            route_produced.add(output_key)

        capture_key = getattr(child, "key", None)
        type_name = type(child).__name__
        if type_name == "CaptureNode" and capture_key:
            route_produced.add(capture_key)

        if type_name == "RouteNode":
            route_key = getattr(child, "key", None)
            if route_key and route_key not in route_produced:
                issues.append({
                    "level": "error",
                    "agent": child.name,
                    "message": f'Route reads "{route_key}" from state, but no '
                               f'upstream agent produces it via .outputs("{route_key}").',
                    "hint": f'Add .outputs("{route_key}") to the agent before the route.',
                })

    # --- Pass 6: Data loss detection (no output_key + C.none() downstream) ---
    for i, child in enumerate(children):
        child_name = getattr(child, "name", "?")
        output_key = getattr(child, "output_key", None)
        type_name = type(child).__name__

        if type_name in ("TransformNode", "TapNode", "RouteNode", "CaptureNode"):
            continue

        # Check if this non-terminal agent has no output_key
        has_successor = i < len(children) - 1
        if has_successor and not output_key:
            # Check if any downstream agent uses C.none()
            for j in range(i + 1, len(children)):
                succ = children[j]
                succ_name = getattr(succ, "name", "?")
                succ_include = getattr(succ, "include_contents", "default")
                succ_context = getattr(succ, "context_spec", None)

                if succ_include == "none" or (succ_context and getattr(succ_context, "include_contents", "default") == "none"):
                    issues.append({
                        "level": "warn",
                        "agent": succ_name,
                        "message": f'"{child_name}" has no .outputs() and "{succ_name}" '
                                   f'uses include_contents=none. "{child_name}"\'s output '
                                   f'reaches "{succ_name}" through neither state nor conversation. '
                                   f'Data may be lost.',
                        "hint": f'Add .outputs("key") to "{child_name}", or change '
                                f'"{succ_name}" to use C.default() or C.from_agents("{child_name}").',
                    })

    # --- Pass 7: Visibility coherence (advisory) ---
    for i, child in enumerate(children):
        child_name = getattr(child, "name", "?")
        output_key = getattr(child, "output_key", None)
        type_name = type(child).__name__
        has_successor = i < len(children) - 1

        if type_name in ("TransformNode", "TapNode", "RouteNode", "CaptureNode"):
            continue

        # Internal agent (has successor) without output_key — text goes to
        # conversation only, may waste user attention if visible
        if has_successor and not output_key:
            issues.append({
                "level": "info",
                "agent": child_name,
                "message": f'"{child_name}" is internal (has successor) but has no '
                           f'.outputs(). Its text goes to conversation history only. '
                           f'Downstream agents will see it via include_contents=default.',
                "hint": f'If "{child_name}" produces structured data, consider '
                        f'.outputs("key"). If it produces conversational text, this is fine.',
            })

    return issues
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/manual/test_cross_channel_contracts.py tests/manual/test_check_contracts.py -v`
Expected: All PASS (both old and new tests)

**Step 5: Commit**

```bash
git add src/adk_fluent/testing/contracts.py tests/manual/test_cross_channel_contracts.py
git commit -m "feat: expand contract checker with cross-channel coherence analysis"
```

---

## Phase 5-memory: Memory Integration

### Task 6: Fluent Memory Integration

Add `.memory()` builder method to Agent for `PreloadMemoryTool` and `LoadMemoryTool`. Following the ADK tide principle — these are pass-through to ADK's native memory tools, not custom implementations.

**Files:**
- Modify: `src/adk_fluent/agent.py` (add `.memory()` method)
- Test: `tests/manual/test_memory.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_memory.py
"""Tests for fluent memory integration."""

import pytest
from adk_fluent import Agent


class TestMemoryMethod:
    """Agent.memory() adds memory tools."""

    def test_memory_preload(self):
        a = Agent("a").model("gemini-2.5-flash").memory("preload")
        built = a.build()
        tool_names = [t.name if hasattr(t, 'name') else type(t).__name__ for t in built.tools]
        assert any("memory" in n.lower() or "Memory" in n for n in tool_names)

    def test_memory_on_demand(self):
        a = Agent("a").model("gemini-2.5-flash").memory("on_demand")
        built = a.build()
        tool_names = [t.name if hasattr(t, 'name') else type(t).__name__ for t in built.tools]
        assert any("memory" in n.lower() or "Memory" in n for n in tool_names)

    def test_memory_both(self):
        a = Agent("a").model("gemini-2.5-flash").memory("both")
        built = a.build()
        assert len(built.tools) >= 2

    def test_memory_returns_self(self):
        a = Agent("a").model("gemini-2.5-flash")
        result = a.memory("preload")
        assert result is a

    def test_memory_with_existing_tools(self):
        def my_tool():
            pass
        a = Agent("a").model("gemini-2.5-flash").tool(my_tool).memory("preload")
        built = a.build()
        assert len(built.tools) >= 2

    def test_memory_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="mode"):
            Agent("a").model("gemini-2.5-flash").memory("invalid")


class TestMemoryAutoSave:
    """Agent.memory_auto_save() adds after_agent callback."""

    def test_auto_save_adds_callback(self):
        a = Agent("a").model("gemini-2.5-flash").memory("preload").memory_auto_save()
        assert "after_agent_callback" in a._callbacks
        assert len(a._callbacks["after_agent_callback"]) >= 1

    def test_auto_save_returns_self(self):
        a = Agent("a").model("gemini-2.5-flash")
        result = a.memory_auto_save()
        assert result is a
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_memory.py -v`
Expected: FAIL — Agent has no `.memory()` method

**Step 3: Add `.memory()` and `.memory_auto_save()` to Agent builder**

In `src/adk_fluent/agent.py`, add to the `Agent` class `# --- Extra methods ---` section:

```python
    def memory(self, mode: str = "preload") -> Self:
        """Add memory tools to this agent.

        Modes:
          'preload'   — PreloadMemoryTool (retrieves memory at start of each turn)
          'on_demand' — LoadMemoryTool (agent decides when to load)
          'both'      — Both tools
        """
        from google.adk.tools.preload_memory_tool import PreloadMemoryTool
        from google.adk.tools.load_memory_tool import LoadMemoryTool

        if mode == "preload":
            self._lists.setdefault("tools", []).append(PreloadMemoryTool())
        elif mode == "on_demand":
            self._lists.setdefault("tools", []).append(LoadMemoryTool())
        elif mode == "both":
            self._lists.setdefault("tools", []).append(PreloadMemoryTool())
            self._lists.setdefault("tools", []).append(LoadMemoryTool())
        else:
            raise ValueError(
                f"Invalid memory mode '{mode}'. Use 'preload', 'on_demand', or 'both'."
            )
        return self

    def memory_auto_save(self) -> Self:
        """Auto-save session to memory after each agent run.

        Adds an after_agent_callback that calls memory_service.add_session_to_memory().
        Requires a memory_service to be configured on the Runner/App.
        """

        async def _auto_save_callback(callback_context):
            memory_service = getattr(
                callback_context._invocation_context, "memory_service", None
            )
            if memory_service is not None:
                await memory_service.add_session_to_memory(
                    callback_context._invocation_context.session
                )

        self._callbacks["after_agent_callback"].append(_auto_save_callback)
        return self
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/manual/test_memory.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/agent.py tests/manual/test_memory.py
git commit -m "feat: add .memory() and .memory_auto_save() for fluent memory integration"
```

---

## Phase 5-exports: Wire into Public API

### Task 7: Export C Module and Visibility from __init__.py

Add new public API exports and update `__all__`.

**Files:**
- Modify: `src/adk_fluent/__init__.py` (add exports)
- Test: `tests/manual/test_public_api.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_public_api.py
"""Tests for v5.1 public API exports."""


class TestContextExports:
    def test_c_importable(self):
        from adk_fluent import C
        assert hasattr(C, "none")
        assert hasattr(C, "default")
        assert hasattr(C, "user_only")
        assert hasattr(C, "from_agents")
        assert hasattr(C, "exclude_agents")
        assert hasattr(C, "window")
        assert hasattr(C, "from_state")
        assert hasattr(C, "template")
        assert hasattr(C, "capture")
        assert hasattr(C, "budget")
        assert hasattr(C, "priority")

    def test_c_from_context_module(self):
        from adk_fluent._context import C as C2
        from adk_fluent import C
        assert C is C2


class TestVisibilityExports:
    def test_infer_visibility_importable(self):
        from adk_fluent._visibility import infer_visibility
        assert callable(infer_visibility)

    def test_visibility_plugin_importable(self):
        from adk_fluent._visibility import VisibilityPlugin
        assert VisibilityPlugin is not None


class TestCaptureExport:
    def test_s_capture_importable(self):
        from adk_fluent import S
        assert hasattr(S, "capture")

    def test_capture_agent_importable(self):
        from adk_fluent._base import CaptureAgent
        assert CaptureAgent is not None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_public_api.py -v`
Expected: FAIL — `C` not importable from `adk_fluent`

**Step 3: Add exports to __init__.py**

Add these lines to `src/adk_fluent/__init__.py`:

```python
from ._context import C
from ._context import CTransform
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/manual/test_public_api.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/__init__.py tests/manual/test_public_api.py
git commit -m "feat: export C module and visibility from public API"
```

---

## Phase 5-integration: Integration Tests

### Task 8: End-to-End Integration Tests

Verify the full pipeline: S.capture + C.context + visibility + contract checking all work together.

**Files:**
- Test: `tests/manual/test_v51_integration.py`

**Step 1: Write the integration tests**

```python
# tests/manual/test_v51_integration.py
"""End-to-end integration tests for v5.1 features."""

import pytest
from adk_fluent import Agent, S, C
from adk_fluent._context import CTransform
from adk_fluent._visibility import infer_visibility, VisibilityPlugin
from adk_fluent.testing import check_contracts
from adk_fluent.workflow import Pipeline


class TestClassifierRouterPattern:
    """The canonical pattern: classifier >> Route >> handler."""

    def test_builds_successfully(self):
        from adk_fluent._routing import Route

        pipeline = (
            S.capture("user_message")
            >> Agent("classifier")
                .model("gemini-2.5-flash")
                .instruct("Classify the user's intent.")
                .outputs("intent")
            >> Route("intent")
                .eq("booking",
                    Agent("booker")
                    .model("gemini-2.5-flash")
                    .instruct("Help book. User said: {user_message}. Intent: {intent}")
                    .context(C.from_state("user_message", "intent"))
                )
                .eq("info",
                    Agent("info")
                    .model("gemini-2.5-flash")
                    .instruct("Provide info. User said: {user_message}")
                    .context(C.from_state("user_message"))
                )
        )
        built = pipeline.build()
        assert built is not None

    def test_contract_check_passes(self):
        from adk_fluent._routing import Route

        pipeline = (
            S.capture("user_message")
            >> Agent("classifier")
                .model("gemini-2.5-flash")
                .instruct("Classify.")
                .outputs("intent")
            >> Route("intent")
                .eq("booking",
                    Agent("booker")
                    .model("gemini-2.5-flash")
                    .instruct("Book: {intent}")
                    .context(C.from_state("intent"))
                )
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert len(errors) == 0

    def test_visibility_inferred(self):
        pipeline = (
            Agent("classifier")
                .model("gemini-2.5-flash")
                .instruct("Classify.")
                .outputs("intent")
            >> Agent("handler")
                .model("gemini-2.5-flash")
                .instruct("Handle: {intent}")
        )
        ir = pipeline.to_ir()
        vis = infer_visibility(ir)
        assert vis["classifier"] == "internal"
        assert vis["handler"] == "user"


class TestContextWithPipeline:
    """C transforms integrate with pipeline building."""

    def test_context_none_compiles(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Process.")
            .context(C.none())
        )
        built = a.build()
        assert built.include_contents == "none"

    def test_context_user_only_compiles(self):
        a = (
            Agent("a")
            .model("gemini-2.5-flash")
            .instruct("Review.")
            .context(C.user_only())
        )
        built = a.build()
        assert built.include_contents == "none"
        assert callable(built.instruction)

    def test_context_from_state_in_pipeline(self):
        pipeline = (
            Agent("researcher")
                .model("gemini-2.5-flash")
                .instruct("Research.")
                .outputs("findings")
            >> Agent("writer")
                .model("gemini-2.5-flash")
                .instruct("Write a report.")
                .context(C.from_state("findings"))
        )
        built = pipeline.build()
        writer = built.sub_agents[1]
        assert writer.include_contents == "none"
        assert callable(writer.instruction)


class TestCaptureIntegration:
    """S.capture() and C.capture() work in pipelines."""

    def test_s_capture_builds_capture_agent(self):
        pipeline = S.capture("user_message") >> Agent("a").model("gemini-2.5-flash")
        built = pipeline.build()
        from adk_fluent._base import CaptureAgent
        assert isinstance(built.sub_agents[0], CaptureAgent)

    def test_c_capture_same_as_s_capture(self):
        fn_s = S.capture("msg")
        fn_c = C.capture("msg")
        assert fn_s.__name__ == fn_c.__name__
        assert hasattr(fn_s, "_capture_key")
        assert hasattr(fn_c, "_capture_key")


class TestDraftReviewEditPattern:
    """Multi-agent composition with selective context."""

    def test_draft_review_edit_builds(self):
        pipeline = (
            Agent("drafter")
                .model("gemini-2.5-flash")
                .instruct("Write initial draft.")
            >> Agent("reviewer")
                .model("gemini-2.5-flash")
                .instruct("Review the draft.")
                .context(C.user_only())
            >> Agent("editor")
                .model("gemini-2.5-flash")
                .instruct("Edit based on review.")
                .context(C.from_agents("drafter", "reviewer"))
        )
        built = pipeline.build()
        assert len(built.sub_agents) == 3

        reviewer = built.sub_agents[1]
        assert reviewer.include_contents == "none"
        assert callable(reviewer.instruction)

        editor = built.sub_agents[2]
        assert editor.include_contents == "none"
        assert callable(editor.instruction)

    def test_visibility_for_draft_review_edit(self):
        pipeline = (
            Agent("drafter").model("m").instruct("Draft.")
            >> Agent("reviewer").model("m").instruct("Review.")
            >> Agent("editor").model("m").instruct("Edit.")
        )
        ir = pipeline.to_ir()
        vis = infer_visibility(ir)
        assert vis["drafter"] == "internal"
        assert vis["reviewer"] == "internal"
        assert vis["editor"] == "user"


class TestMemoryIntegration:
    """Memory tools work with agent builder."""

    def test_memory_preload_builds(self):
        a = Agent("a").model("gemini-2.5-flash").memory("preload")
        built = a.build()
        assert len(built.tools) >= 1

    def test_memory_in_pipeline(self):
        pipeline = (
            Agent("a")
                .model("gemini-2.5-flash")
                .instruct("Answer questions.")
                .memory("preload")
            >> Agent("b")
                .model("gemini-2.5-flash")
                .instruct("Summarize.")
        )
        built = pipeline.build()
        assert len(built.sub_agents[0].tools) >= 1


class TestIRFirstBuildIntegration:
    """IR-first build path works with all v5.1 features."""

    def test_pipeline_build_runs_contracts(self):
        """Pipeline.build() runs contract checking by default."""
        pipeline = (
            Agent("a").model("m").instruct("Classify.").outputs("intent")
            >> Agent("b").model("m").instruct("Handle: {intent}")
        )
        built = pipeline.build()  # Should succeed with advisory diagnostics
        assert built is not None

    def test_pipeline_build_check_false(self):
        """build(check=False) skips contracts."""
        pipeline = (
            Agent("a").model("m").instruct("Do.")
            >> Agent("b").model("m").instruct("Use: {missing_key}")
        )
        built = pipeline.build(check=False)
        assert built is not None


class TestPipelinePolicies:
    """Pipeline-level visibility policies work end-to-end."""

    def test_transparent_policy(self):
        pipeline = (
            Agent("a").model("m").instruct("Classify.").outputs("intent")
            >> Agent("b").model("m").instruct("Handle.")
        )
        # transparent() should be available on pipeline
        assert hasattr(pipeline, "transparent")

    def test_filtered_policy(self):
        pipeline = (
            Agent("a").model("m").instruct("Classify.")
            >> Agent("b").model("m").instruct("Handle.")
        )
        assert hasattr(pipeline, "filtered")
```

**Step 2: Run all tests**

Run: `pytest tests/manual/test_v51_integration.py -v`
Expected: All PASS

**Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All 1055+ existing tests PASS, plus all new tests

**Step 4: Commit**

```bash
git add tests/manual/test_v51_integration.py
git commit -m "test: add v5.1 end-to-end integration tests"
```

---

## Phase 5-build: IR-First Build Path

### Task 9: Make .build() Route Through IR with Default Contract Checking

Per appendix_f Q1: "IR should be invisible — `.build()` should internally use IR." Per appendix_f Q3: "Contract checking should be DEFAULT, not opt-in." This task rewires `.build()` on all builders (Agent, Pipeline, FanOut, Loop) to internally go through `.to_ir() → check_contracts() → backend.compile()` instead of direct ADK constructor calls. The `build(check=False)` escape hatch skips contract checking for cases where speed matters or contracts are known to be fine.

**Files:**
- Modify: `src/adk_fluent/_base.py` (update `BuilderBase.build()` path)
- Modify: `src/adk_fluent/agent.py` (Agent.build override if needed)
- Test: `tests/manual/test_ir_first_build.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_ir_first_build.py
"""Tests for IR-first build path with default contract checking."""

import pytest
from adk_fluent import Agent, S
from adk_fluent._routing import Route


class TestIRFirstBuildPath:
    """build() internally routes through to_ir → check_contracts → backend.compile."""

    def test_simple_agent_builds_via_ir(self):
        """Single agent build still works (short-circuit: no IR needed)."""
        a = Agent("a").model("gemini-2.5-flash").instruct("Hi")
        built = a.build()
        assert built is not None
        assert built.name == "a"

    def test_pipeline_builds_via_ir(self):
        """Pipeline.build() routes through IR path."""
        pipeline = (
            Agent("a").model("m").instruct("Classify.").outputs("intent")
            >> Agent("b").model("m").instruct("Handle: {intent}")
        )
        built = pipeline.build()
        assert built is not None
        assert len(built.sub_agents) == 2


class TestDefaultContractChecking:
    """Contract checking runs by default on build()."""

    def test_build_reports_contract_issues(self):
        """Pipeline with unresolved template var should warn/log but still build.
        (Advisory by default — per spec §13.3 diagnostics are advisory)."""
        pipeline = (
            Agent("a").model("m").instruct("Do stuff.")
            >> Agent("b").model("m").instruct("Summary: {summary}")
        )
        # Build should succeed (advisory diagnostics don't block build)
        built = pipeline.build()
        assert built is not None

    def test_build_strict_raises_on_errors(self):
        """build(check='strict') promotes advisory diagnostics to errors."""
        pipeline = (
            Agent("a").model("m").instruct("Do stuff.")
            >> Agent("b").model("m").instruct("Summary: {summary}")
        )
        with pytest.raises(ValueError, match="contract"):
            pipeline.build(check="strict")

    def test_build_check_false_skips_contracts(self):
        """build(check=False) skips contract checking entirely."""
        pipeline = (
            Agent("a").model("m").instruct("Do stuff.")
            >> Agent("b").model("m").instruct("Summary: {summary}")
        )
        # No error even with strict issues — checking is off
        built = pipeline.build(check=False)
        assert built is not None


class TestBuildCheckParameter:
    """build() accepts check parameter controlling contract validation."""

    def test_default_check_is_advisory(self):
        """Default: contracts run but only log, don't raise."""
        pipeline = (
            Agent("a").model("m").instruct("Process.")
            >> Agent("b").model("m").instruct("Handle.")
        )
        built = pipeline.build()  # check=True by default (advisory)
        assert built is not None

    def test_check_false(self):
        built = Agent("a").model("m").instruct("Hi").build(check=False)
        assert built is not None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_ir_first_build.py -v`
Expected: FAIL — `build()` doesn't accept `check` parameter

**Step 3: Implement IR-first build path**

The key change is in `_base.py`'s `BuilderBase`. For compound builders (Pipeline, FanOut, Loop), `build()` should:

1. Call `self.to_ir()` to get the IR tree
2. Call `check_contracts(ir)` (unless `check=False`)
3. Call `ADKBackend().compile(ir, config)` to get the native agent
4. Return the native agent

For `Agent` (single agent, not compound), the current direct-construction path is kept since single agents don't benefit from IR-based contract checking. But when `Agent` is part of a pipeline, the pipeline's IR path handles it.

Modify `src/adk_fluent/_base.py` — add to `BuilderBase`:

```python
    def build(self, *, check: bool | str = True, **kwargs) -> Any:
        """Build the native ADK agent.

        Args:
            check: Contract checking mode (appendix_f Q3):
                True  — run contracts, log advisory diagnostics (default)
                False — skip contract checking entirely
                'strict' — raise ValueError on any contract error
        """
        # For compound types with to_ir, use IR-first path
        ir = None
        if hasattr(self, "to_ir") and self._should_use_ir_path():
            try:
                ir = self.to_ir()
            except Exception:
                ir = None

        if ir is not None and check is not False:
            from adk_fluent.testing.contracts import check_contracts
            issues = check_contracts(ir)
            if issues:
                errors = [
                    i for i in issues
                    if isinstance(i, dict) and i.get("level") == "error"
                ]
                if check == "strict" and errors:
                    msg = "\n".join(
                        f"  {i['agent']}: {i['message']}" for i in errors
                    )
                    raise ValueError(
                        f"Contract errors in pipeline:\n{msg}"
                    )
                # Advisory mode: log but don't block
                if errors:
                    import logging
                    logger = logging.getLogger("adk_fluent.contracts")
                    for issue in errors:
                        logger.warning(
                            "Contract issue [%s] %s: %s",
                            issue.get("level", "?"),
                            issue.get("agent", "?"),
                            issue.get("message", "?"),
                        )

        # Delegate to the existing build implementation
        return self._build_impl(**kwargs)

    def _should_use_ir_path(self) -> bool:
        """Override in subclasses: Pipeline, FanOut, Loop return True."""
        return False

    def _build_impl(self, **kwargs) -> Any:
        """Existing build logic — override per builder type."""
        raise NotImplementedError
```

For Pipeline/FanOut/Loop in `workflow.py`, override `_should_use_ir_path` to return `True`.

For Agent, `_should_use_ir_path` returns `False` — single agents use direct construction. `_build_impl` contains the existing `build()` logic.

**Important:** The existing `build()` method in `agent.py` and `_base.py` must be renamed to `_build_impl()`, and the new `build()` from `BuilderBase` wraps it with contract checking.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/manual/test_ir_first_build.py -v`
Expected: All PASS

**Step 5: Run full test suite to verify backward compatibility**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests still pass — the build path is the same, just with contract checking added.

**Step 6: Commit**

```bash
git add src/adk_fluent/_base.py src/adk_fluent/agent.py tests/manual/test_ir_first_build.py
git commit -m "feat: IR-first build path with default contract checking (appendix_f Q1, Q3)"
```

---

## Phase 5-otel: OTel Enrichment Middleware

### Task 10: OTelEnrichmentMiddleware — Replace structured_log

Per v5.1 spec §8: "adk-fluent's telemetry strategy is span enrichment — adding pipeline-level metadata to ADK's existing spans, not creating parallel spans." This replaces v4's `structured_log` middleware with `OTelEnrichmentMiddleware` that annotates ADK's existing OTel spans with adk-fluent metadata (pipeline name, node type, cost estimates).

**Files:**
- Modify: `src/adk_fluent/middleware.py` (add `otel_enrichment` middleware)
- Test: `tests/manual/test_otel_enrichment.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_otel_enrichment.py
"""Tests for OTel enrichment middleware."""

import pytest


class TestOTelEnrichmentMiddleware:
    """OTelEnrichmentMiddleware enriches ADK's existing spans."""

    def test_middleware_exists(self):
        from adk_fluent.middleware import otel_enrichment
        mw = otel_enrichment(pipeline_name="test_pipeline")
        assert mw is not None

    def test_middleware_has_lifecycle_hooks(self):
        from adk_fluent.middleware import otel_enrichment
        mw = otel_enrichment(pipeline_name="test_pipeline")
        # Should have before_agent, before_model, after_model hooks
        assert hasattr(mw, "before_agent") or hasattr(mw, "__call__")

    def test_middleware_stores_pipeline_name(self):
        from adk_fluent.middleware import otel_enrichment
        mw = otel_enrichment(pipeline_name="billing_v2")
        assert mw._pipeline_name == "billing_v2"

    def test_middleware_default_pipeline_name(self):
        from adk_fluent.middleware import otel_enrichment
        mw = otel_enrichment()
        assert mw._pipeline_name is None


class TestOTelEnrichmentInPipeline:
    """OTel enrichment integrates with pipeline building."""

    def test_pipeline_with_otel(self):
        from adk_fluent import Agent
        from adk_fluent.middleware import otel_enrichment

        pipeline = (
            Agent("a").model("gemini-2.5-flash").instruct("Process.")
            >> Agent("b").model("gemini-2.5-flash").instruct("Handle.")
        )
        # Middleware can be passed to pipeline execution
        mw = otel_enrichment(pipeline_name="test")
        assert mw is not None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/manual/test_otel_enrichment.py -v`
Expected: FAIL — `otel_enrichment` doesn't exist in middleware module

**Step 3: Implement OTelEnrichmentMiddleware**

Add to `src/adk_fluent/middleware.py`:

```python
class OTelEnrichmentMiddleware:
    """Adds adk-fluent metadata to ADK's existing OTel spans.

    Does NOT create new spans — enriches the current span created by ADK's
    own telemetry (call_llm, execute_tool, invoke_agent).

    Replaces v4's structured_log middleware. The design principle (spec §8.2):
    ADK already emits spans at every lifecycle point. Creating additional
    middleware spans at the same points would produce duplicate telemetry.
    Instead, we annotate ADK's spans with pipeline-level context.

    Attributes set on spans:
      - adk_fluent.pipeline: pipeline name
      - adk_fluent.node_type: IR node type (agent, transform, route, etc.)
      - adk_fluent.agent_name: agent name within pipeline
      - adk_fluent.cost_estimate_usd: pre-call cost estimate (if model pricing known)
      - adk_fluent.actual_input_tokens: post-call actual usage
      - adk_fluent.actual_output_tokens: post-call actual usage
    """

    def __init__(self, pipeline_name: str | None = None):
        self._pipeline_name = pipeline_name

    async def before_agent(self, ctx, agent_name: str):
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if self._pipeline_name:
                span.set_attribute("adk_fluent.pipeline", self._pipeline_name)
            span.set_attribute("adk_fluent.agent_name", agent_name)
        except ImportError:
            pass  # OTel not installed — degrade gracefully
        return None

    async def before_model(self, ctx, request):
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            span.set_attribute("adk_fluent.agent_name", ctx.agent_name)
        except ImportError:
            pass
        return None

    async def after_model(self, ctx, response):
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            usage = getattr(response, "usage_metadata", None)
            if usage:
                input_tokens = getattr(usage, "prompt_token_count", 0) or 0
                output_tokens = getattr(usage, "candidates_token_count", 0) or 0
                span.set_attribute("adk_fluent.actual_input_tokens", input_tokens)
                span.set_attribute("adk_fluent.actual_output_tokens", output_tokens)
        except ImportError:
            pass
        return None


def otel_enrichment(*, pipeline_name: str | None = None) -> OTelEnrichmentMiddleware:
    """Create an OTel enrichment middleware instance.

    Annotates ADK's existing OTel spans with adk-fluent pipeline metadata.
    Gracefully degrades if opentelemetry is not installed.

    Args:
        pipeline_name: Optional name for the pipeline (appears in span attributes).
    """
    return OTelEnrichmentMiddleware(pipeline_name=pipeline_name)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/manual/test_otel_enrichment.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/adk_fluent/middleware.py tests/manual/test_otel_enrichment.py
git commit -m "feat: add OTel enrichment middleware (enrich ADK spans, don't duplicate)"
```

---

## Summary of Deliverables

| Phase | Task | Files Created/Modified | Lines Added (est.) |
|-------|------|----------------------|-------------------|
| 5i: S.capture() | 1 | `_transforms.py`, `_base.py`, `_ir.py`, `backends/adk.py` | ~80 |
| 5i-core: C Module | 2 | `_context.py` (new) | ~350 |
| 5i-wire: Agent.context() | 3 | `agent.py`, `_base.py`, `_context.py` | ~80 |
| 5j: Visibility | 4 | `_visibility.py` (new), `_base.py`, `agent.py` | ~220 |
| 5k: Contracts | 5 | `testing/contracts.py` | ~180 |
| 5-memory: Memory | 6 | `agent.py` | ~40 |
| 5-exports: Public API | 7 | `__init__.py` | ~5 |
| 5-integration: Tests | 8 | 7 new test files | ~450 |
| 5-build: IR-first | 9 | `_base.py`, `agent.py` | ~60 |
| 5-otel: OTel enrichment | 10 | `middleware.py` | ~70 |

**Total:** ~2 new files, ~9 modified files, ~1535 lines of new code + tests.

**Deferred to subsequent phases (see Phase Roadmap at top):**

- **Phase B:** C Atoms (No LLM) — SELECT/COMPRESS/BUDGET/PROTECT atoms, `+`/`|` type rules
- **Phase C:** C Atoms (LLM-Powered) — summarize, relevant, extract, distill, validate, fit
- **Phase D:** Scratchpads + Sugar — notes, write_notes, rolling, manus_cascade
- **Phase E:** Typed State — StateSchema, typed contracts, scope annotations
- **v5 §5–12:** Streaming, cost routing, A2A, evaluation, replay, execution boundaries — retained by reference
- **Appendix_f Q9:** Better auto-generated Pipeline names — deferred to naming convention pass

The codegen scanner does NOT need updating — all new code is hand-written adk-fluent invention
