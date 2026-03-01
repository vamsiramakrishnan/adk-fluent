# A Module: Fluent Artifact Composition

**Date**: 2026-03-01
**Status**: Draft
**Approach**: Phased (B → C)

## Context

adk-fluent has five composition namespaces: `P` (prompts), `C` (context),
`S` (state transforms), `M` (middleware), `T` (tools). Each owns a mechanism.
Artifacts currently have no composition surface — developers must write raw
async callbacks to `ctx.save_artifact()` / `ctx.load_artifact()` with manual
MIME type handling, no pipeline integration, no contract checking, and no
visibility in `.explain()` or `visualize`.

Google ADK's artifact system is capable — versioned storage, session/user
scoping, multiple backends (InMemory, File, GCS) — but the raw API requires
~15 lines of boilerplate per artifact operation and provides no build-time
validation. MIME type errors at save time are permanent and silent (there is no
auto-detection on load), making correctness a developer responsibility with no
safety net.

`A` earns its place alongside `P`/`C`/`S`/`M`/`T` because it manages the
**state ↔ artifact boundary** — a bridge between the two parallel data planes
that ADK keeps strictly separate.

## Problem

### The Two Data Planes

ADK agents have two parallel data systems with fundamentally different
characteristics:

| Aspect         | State (S)                                      | Artifacts (A)                                    |
| -------------- | ---------------------------------------------- | ------------------------------------------------ |
| What it holds  | Key-value pairs (strings, numbers, small JSON) | Files and blobs (PDFs, images, CSVs, large text) |
| Size           | Small — fits in session JSON                   | Large — stored in a service backend              |
| Lifetime       | Session-scoped, serialized with session        | Versioned, survives session, can be user-scoped  |
| Access pattern | Synchronous dict reads                         | Async service calls                              |
| Primary use    | Control flow, agent coordination, metadata     | Data payloads, generated outputs, uploads        |
| ADK mechanism  | `session.state["key"]`                         | `ctx.save_artifact()` / `ctx.load_artifact()`    |
| Versioning     | None (last-write-wins)                         | Built-in (version 0, 1, 2...)                    |
| Scope          | Session only                                   | Session OR user-scoped (cross-session)           |
| Deletion       | `state[key] = None`                            | `delete_artifact()`                              |
| Tracking       | `event.actions.state_delta`                    | `event.actions.artifact_delta`                   |
| Backend        | In-memory dict in session                      | InMemory, File, GCS services                     |

### What Raw ADK Artifact Code Looks Like

Before discussing why A earns its own module, here's what artifact handling
looks like today in raw ADK — this is the baseline A replaces:

```python
import google.genai.types as types
from google.adk.agents.callback_context import CallbackContext

async def process_latest_report(context: CallbackContext):
    """Loads the latest report artifact and processes its data."""
    filename = "generated_report.pdf"
    try:
        report_artifact = await context.load_artifact(filename=filename)

        if report_artifact and report_artifact.inline_data:
            print(f"Successfully loaded '{filename}'.")
            print(f"MIME Type: {report_artifact.inline_data.mime_type}")
            pdf_bytes = report_artifact.inline_data.data
            print(f"Report size: {len(pdf_bytes)} bytes.")
            # ... further processing ...
        else:
            print(f"Artifact '{filename}' not found.")

    except ValueError as e:
        print(f"Error: {e}. Is ArtifactService configured?")
    except Exception as e:
        print(f"Unexpected error during artifact load: {e}")
```

This is ~20 lines for a single load — with manual error handling, MIME type
inspection, binary/text branching, and no pipeline integration. Saving is
equally verbose (construct Part, choose `Part.from_text()` vs
`Part.from_bytes()`, pass MIME type, handle errors). Every artifact operation
in a multi-agent pipeline means another callback like this.

**With A module (Phase 1)**:

```python
# The same operation:
A.snapshot("generated_report.pdf", into_key="report_ref")

# Or for LLM consumption (Phase 2, no state bridge):
A.for_llm("generated_report.pdf")
```

### Why Not S (State Transforms)?

S transforms operate on `state → state` using **synchronous dict access**.
Artifacts require **async service calls** through `ctx.artifact_service` which
S transforms fundamentally have no access to.

The STransform callable protocol is `fn(state: dict) -> StateDelta | StateReplacement`.
It receives a plain dict, returns a plain dict. There is no `ctx`, no async, no
service access. This is by design — S transforms are pure functions on state,
which makes them composable, testable, and zero-cost (no LLM call, no I/O).

Artifacts violate every one of these properties:

| Property           | S (State)                    | Artifacts                                          |
| ------------------ | ---------------------------- | -------------------------------------------------- |
| **I/O**            | None — pure dict transform   | Async service calls (GCS, filesystem)              |
| **Context access** | None — receives plain `dict` | Requires `CallbackContext` or `InvocationContext`  |
| **Data type**      | JSON-serializable values     | Binary blobs (images, PDFs, audio) with MIME types |
| **Versioning**     | Last-write-wins              | Version 0, 1, 2... with metadata per version       |
| **Scope**          | Session-scoped dict          | Session OR user-scoped (cross-session persistence) |
| **Error modes**    | Dict key missing             | Service unavailable, auth failure, quota exceeded  |

S can _reference_ artifacts by storing filenames/URIs in state keys, but it
cannot _manage_ them — it has no access to the artifact service.

### Why Not C (Context Engineering)?

C manages what the **LLM sees in its conversation context** — history windowing,
message filtering, summarization, deduplication. It operates on the context
plane: `events/messages → instruction provider`.

Artifacts are data objects, not context. The distinction:

| Aspect              | C (Context)                                     | Artifacts                                          |
| ------------------- | ----------------------------------------------- | -------------------------------------------------- |
| **What it manages** | LLM conversation history, message selection     | Versioned files and blobs                          |
| **Output**          | Instruction string or `include_contents` config | `types.Part` (text or binary blob)                 |
| **Scope**           | Current invocation's LLM request                | Persistent across invocations/sessions             |
| **Composition**     | `+` (union of context strategies)               | `>>` (pipeline steps between agents)               |
| **Side effects**    | None — read-only transformation of history      | Writes to artifact service, mutates artifact_delta |

C _could_ inject artifact content into LLM context (and `A.for_llm()` in Phase
2 does exactly this by returning a C-compatible descriptor). But C cannot
**save** artifacts, **version** them, **delete** them, or manage their MIME
types. These are lifecycle operations that belong to a dedicated module.

The relationship: `A.for_llm()` is the **bridge from A to C** — it takes an
artifact and produces a C-compatible context injection. A manages the artifact
lifecycle; C manages what the LLM sees. They collaborate, but each owns a
distinct concern.

### Why A Earns Its Own Module

A manages the **artifact lifecycle** — a concern that doesn't fit in any
existing module:

- **Not S** — requires async I/O, binary data, versioning, MIME types
- **Not C** — artifacts are persistent data objects, not conversation context
- **Not M** — middleware is per-invocation hooks, not data management
- **Not T** — tools are LLM-callable functions, not pipeline data flow
- **Not P** — prompts are instruction text, not file storage

A sits at the intersection of state and artifact service, managing the boundary
between ADK's two data planes. That boundary management is a distinct concern
with its own vocabulary (publish, snapshot, MIME, version, scope), its own
contract checking needs (artifact availability, MIME compatibility), and its own
composition semantics (`>>` pipeline steps).

### Where State and Artifacts Connect

The bridge between state and artifacts is **keys**:

1. **State references artifacts by name** — `state["report_artifact"] = "report.md"`
   stores the filename so downstream agents know what to load
1. **Artifacts extract into state** — loading an artifact's text content into
   `state["report_text"]` for an LLM to consume
1. **State metadata about artifacts** — `state["report_version"] = 3`,
   `state["report_mime"] = "text/markdown"`

This is exactly what A formalizes. Its factories make these bridges explicit,
traceable, and honestly named:

```python
# publish: state → artifact (the bridge out — explicitly named)
A.publish("report.md", from_key="report")

# snapshot: artifact → state (the bridge in — explicitly named)
A.snapshot("report.md", into_key="report_text")
```

### Current Pain Points

1. **Boilerplate**: 15 lines per artifact operation (define async fn, construct
   Part, handle MIME, call service, return)
1. **MIME fragility**: `Part.from_bytes()` requires explicit MIME — typo
   `"text/markdwn"` causes permanent misclassification, silent at save, broken
   at load
1. **Invisible flow**: artifact dependencies between agents are hidden inside
   callback bodies — IR/contract checker/explain/visualize can't see them
1. **No LLM awareness**: developers must know which MIME types Gemini can consume
   inline (image/\*, audio/\*, video/\*, application/pdf) vs. which need text
   conversion
1. **No composition**: can't chain artifact operations in `>>` pipelines like
   S transforms

## Architectural Honesty: The State–Artifact Bridge

> **ADK deliberately keeps state and artifacts separate. We are choosing to
> bridge them. This section explains why ADK separates them, why we bridge them
> anyway, and exactly what tradeoffs that creates.**

### Why ADK Keeps Them Separate

Google's ADK engineers made a deliberate architectural choice: `state_delta` and
`artifact_delta` are independent streams. When `ctx.save_artifact()` is called,
the version is recorded in `event.actions.artifact_delta` — **state is never
touched**. When `ctx.load_artifact()` is called, the content goes to the caller
— **state is never touched**. There is no "state holds a pointer to an artifact"
convention anywhere in ADK core. Zero.

This separation exists for good reasons:

1. **Size isolation** — State serializes with the session as JSON. If artifact
   content (potentially MBs of images, PDFs, long reports) leaked into state,
   session serialization and snapshot/restore would bloat. Artifacts live in
   their own backend (GCS, filesystem) precisely to avoid this.

1. **Lifecycle independence** — State dies with the session (except `app:` /
   `user:` scoped keys). Artifacts have their own versioned lifecycle, can
   persist across sessions, and can be deleted independently. Coupling them
   would create lifecycle entanglement.

1. **Access pattern separation** — State is synchronous dict access. Artifacts
   require async service calls. ADK's State class has no async methods. Mixing
   the two would force async into every state operation.

1. **Delta tracking independence** — `state_delta` updates the session object
   directly via `_update_session_state()`. `artifact_delta` is bookkeeping in
   event history — it never mutates session state. Coupling them would create
   cross-delta dependencies in the persistence layer.

1. **Backend flexibility** — State lives in session storage. Artifacts live in
   their own backend. Coupling them would create cross-backend transactional
   requirements that neither system is designed for.

### What We Are Doing

The A module creates a **bridge layer** that treats state as a staging area for
artifact content:

- `A.publish("report.md", from_key="report")` reads `state["report"]`, copies
  the content to the artifact service
- `A.snapshot("report.md", into_key="text")` reads from the artifact service,
  copies a point-in-time snapshot into `state["text"]`

**This is an adk-fluent abstraction, not native ADK behavior.** ADK has no
equivalent. We are deliberately creating a coupling that ADK deliberately avoids.

### Why We Bridge Anyway

The separation is architecturally clean but creates real developer friction:

1. **LLMs read from state, not from artifact service** — The instruction template
   `{report}` reads from `session.state["report"]`. If artifact content isn't in
   state, the LLM can't see it through the normal instruction/context mechanism.
   The only alternative is `LoadArtifactsTool` (a runtime tool call), which costs
   an extra LLM round-trip and is non-deterministic (the LLM must decide to call
   it).

1. **Pipeline data flow goes through state** — In `Agent >> S.transform >> Agent`
   pipelines, data flows through state. If artifacts can't enter and exit state,
   they're second-class citizens in the `>>` composition that makes adk-fluent
   valuable. Users would have to drop out of the fluent API to handle artifacts.

1. **ADK itself bridges at the tool/plugin level** — `LoadArtifactsTool` loads
   artifacts into LLM context (bridging artifact → model).
   `SaveFilesAsArtifactsPlugin` intercepts user uploads and saves them as
   artifacts (bridging content → artifact). The bridge pattern already exists in
   ADK — it's just implicit and scattered across tools and plugins rather than
   explicit and composable.

1. **The alternative is worse** — Without A, users write raw async callbacks that
   do exactly the same bridging, but with no type safety, no contract checking,
   no pipeline integration, and no visibility. The bridge happens regardless; the
   question is whether it's explicit or hidden.

### The Tradeoffs We Accept

By bridging state and artifacts, we accept these consequences:

| Tradeoff                             | Risk                                                                                                                                                                                                                       | Mitigation                                                                                                                                                                                                                                         |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **State bloat**                      | `A.snapshot()` puts artifact text content into `session.state`, which serializes with the session. A 100KB report is now 100KB of session JSON.                                                                            | Contract checker emits a **warning** when `A.snapshot()` is used without a corresponding `S.drop()` downstream. Docs recommend `temp:` prefix for ephemeral snapshots (ADK auto-strips `temp:` keys before persistence).                           |
| **Staleness**                        | Once loaded into state, the value is a point-in-time copy. The artifact can be updated by another agent, but the state key holds the old value.                                                                            | The name `snapshot` makes this explicit. Not `sync`, not `bind`, not `mirror` — a snapshot. Docs note this is a copy, not a live reference.                                                                                                        |
| **Binary impossibility**             | Images, PDFs, audio literally cannot live in state (not JSON-serializable). `A.snapshot("chart.png")` can only store a URI reference, never the actual bytes. This creates an asymmetry between text and binary artifacts. | For binary artifacts, `A.snapshot()` stores an artifact URI string. The naming `as_ref=True` makes this explicit. `A.for_llm()` (Phase 2) provides the proper channel for binary content — direct LLM context injection, bypassing state entirely. |
| **Conceptual confusion**             | Users might think `state["text"]` IS the artifact. It's not — it's a copy. Modifying `state["text"]` doesn't update the artifact.                                                                                          | Naming: `publish` (not `save`) and `snapshot` (not `load`). These words carry the right semantics — you publish content to a versioned store, you take a snapshot for local use.                                                                   |
| **Violation of ADK's design intent** | We're coupling what ADK deliberately decouples. Future ADK changes to artifact internals could break assumptions.                                                                                                          | A operates through the public `BaseArtifactService` interface only. It never accesses internal artifact storage. The bridge is at the API boundary, not the implementation boundary.                                                               |

### Naming: Making the Bridge Transparent

The original design used `A.save()` and `A.load()`, which hide the bridging
semantics. These names suggest you're saving/loading artifacts directly, when
you're actually copying between state and the artifact service.

Revised naming that makes the bridge explicit:

| Operation                        | Name                                 | Why this name                                                                                                                               |
| -------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| State → artifact service         | `A.publish(filename, from_key=...)`  | "Publish" implies taking content from one place and putting it in a versioned store. It's clearly a copy-out operation, not a direct write. |
| Artifact service → state         | `A.snapshot(filename, into_key=...)` | "Snapshot" implies a point-in-time copy. The artifact continues to live and version independently.                                          |
| Direct artifact write (no state) | `A.save(filename, content=...)`      | When content is literal (not from state), "save" is accurate — you're directly saving to the artifact service.                              |
| Direct artifact read (no state)  | `A.load(filename)`                   | When there's no `into_key`, this returns the artifact for use in `A.for_llm()` or pipeline transforms. No state bridge.                     |
| List artifacts                   | `A.list(into_key=...)`               | Listing is metadata, not content. Putting a list of filenames in state is lightweight and safe.                                             |
| Artifact metadata                | `A.version(filename, into_key=...)`  | Metadata is small. Safe to put in state.                                                                                                    |
| Delete artifact                  | `A.delete(filename)`                 | Direct operation, no state involved.                                                                                                        |

This gives us **four verbs for four semantics**:

```python
# publish: state → artifact (copy out, versioned)
A.publish("report.md", from_key="report")

# snapshot: artifact → state (copy in, point-in-time)
A.snapshot("report.md", into_key="report_text")

# save: content → artifact (direct, no state bridge)
A.save("report.md", content="# My Report")

# load: artifact → pipeline (direct, no state bridge)
A.load("report.md")  # returns ATransform for >> composition
```

The user reads `publish` and understands: "I'm publishing state content to the
artifact store." The user reads `snapshot` and understands: "I'm taking a
snapshot of the artifact into state." Neither name hides what's happening.

**When there's no state bridge, use the simple verbs** — `A.save(content=...)`
directly writes content to the artifact service, `A.load()` directly reads for
pipeline composition. No bridge, no naming gymnastics.

### Alternative Designs Considered

**Alternative 1: No state bridge at all.** A only manages artifacts directly.
No `from_key`/`into_key`. Pipeline integration via a separate artifact context
mechanism.

_Rejected because_: Loses the entire pipeline composition story. Users would
need to drop out of `>>` chains to handle artifacts, defeating the purpose of a
fluent API.

**Alternative 2: URI references only.** `A.snapshot()` only puts artifact URI
strings in state, never content. Content access happens exclusively via
`A.for_llm()` or `A.tool.load()`.

_Rejected because_: LLMs consume text through instruction templates (`{key}`),
which read from state. If state only has URIs, the LLM sees
`artifact://apps/myapp/.../report.md/versions/3` instead of the report content.
This is useless for the most common use case (feed artifact text to next agent).

**Alternative 3: The bridge with explicit semantics (chosen).**
`A.publish()` / `A.snapshot()` with clear copy semantics. Contract checker warns
about size risks. Documentation and naming make the bridge transparent.

_Chosen because_: Maximizes ergonomic value while being honest about what's
happening. The user knows they're bridging two systems. The naming tells them
the semantics. The contract checker catches the risks.

## Goals

1. **Zero-ceremony artifact wiring** — `A.publish()` / `A.snapshot()` /
   `A.save()` / `A.load()` in pipelines, same ergonomics as `S.pick()` /
   `S.drop()`
1. **MIME safety** — constants prevent typos, auto-detection from filenames,
   LLM compatibility checks at build time
1. **Contract checking** — build-time validation that artifacts are produced
   before consumed, with cross-validation against state flow
1. **Pipeline integration** — `>>` operator, `.artifacts()` builder method,
   composable transforms
1. **LLM-aware loading** — automatic format conversion based on MIME type and
   target channel (inline context vs. state vs. tool response)
1. **Tool generation** — one-line creation of artifact tools for LLM agents

## Design

### Phase 1: Core Factories + MIME Safety + Pipeline Integration

The foundation. Everything else builds on this.

#### 1.1 MIME Constants (`A.mime`)

MIME type errors are permanent and silent. A provides a safe vocabulary:

```python
class A:
    class mime:
        """MIME type constants. Prevents typos that cause permanent misclassification."""

        # Text family (LLM can read directly after decode)
        text     = "text/plain"
        markdown = "text/markdown"
        html     = "text/html"
        csv      = "text/csv"
        json     = "application/json"
        xml      = "application/xml"
        yaml     = "application/yaml"

        # Document (LLM can read PDF inline)
        pdf      = "application/pdf"

        # Image (LLM can see inline)
        png      = "image/png"
        jpeg     = "image/jpeg"
        gif      = "image/gif"
        webp     = "image/webp"
        svg      = "image/svg+xml"

        # Audio (LLM can hear inline)
        mp3      = "audio/mpeg"
        wav      = "audio/wav"
        ogg      = "audio/ogg"

        # Video (LLM can watch inline)
        mp4      = "video/mp4"
        webm     = "video/webm"

        # Binary fallback
        binary   = "application/octet-stream"

        @staticmethod
        def detect(filename: str) -> str:
            """Auto-detect MIME type from filename extension.
            Falls back to 'application/octet-stream'.
            Uses Python's mimetypes.guess_type() (same as Part.from_uri).
            """

        @staticmethod
        def is_llm_inline(mime: str) -> bool:
            """Can Gemini consume this MIME type directly as inline content?
            True for: image/*, audio/*, video/*, application/pdf.
            """

        @staticmethod
        def is_text_like(mime: str) -> bool:
            """Can this be safely decoded as UTF-8 text?
            True for: text/*, application/json, application/csv,
            application/xml, application/yaml.
            """
```

**Design rationale**: Every factory in A accepts `mime=A.mime.markdown` instead
of hand-typing `"text/markdown"`. The constant is pyright-checkable at edit time.
`A.mime.detect("report.pdf")` provides safe auto-detection. The classifier
methods (`is_llm_inline`, `is_text_like`) encode ADK's actual MIME support
matrix from `LoadArtifactsTool._as_safe_part_for_llm`.

#### 1.2 Core Factories

The four verbs reflect four distinct semantics:

**`A.publish` — state → artifact service (the bridge, copy out)**

```python
A.publish("report.md", from_key="report")
# ⚠ STATE BRIDGE: reads state["report"] (str), copies to artifact "report.md".
# MIME auto-detected from extension: text/markdown.
# Metadata: consumes_state={"report"}, produces_artifact={"report.md"}

A.publish("chart.png", from_key="chart_data", mime=A.mime.png)
# ⚠ STATE BRIDGE: reads state["chart_data"] (base64 str or bytes).
# Explicit MIME required for binary — no guessing.
# Metadata: consumes_state={"chart_data"}, produces_artifact={"chart.png"}

A.publish("report.md", from_key="report", metadata={"author": "researcher"})
# Custom metadata attached to ArtifactVersion.
```

**`A.snapshot` — artifact service → state (the bridge, copy in)**

```python
A.snapshot("report.md", into_key="report_text")
# ⚠ STATE BRIDGE: loads latest version, copies text into state["report_text"].
# This is a point-in-time copy. The artifact versions independently.
# Metadata: consumes_artifact={"report.md"}, produces_state={"report_text"}

A.snapshot("report.md", into_key="report_text", version=1)
# Snapshot a specific version.

A.snapshot("chart.png", into_key="chart_ref")
# Binary artifact: puts artifact URI string into state (not the bytes).
# Binary content cannot live in state (JSON serialization constraint).
# URI: artifact://apps/{app}/users/{u}/sessions/{s}/artifacts/chart.png/versions/{v}

A.snapshot("data.csv", into_key="data", decode=True)
# Force text decode of any artifact (even if stored with binary MIME type).
# Useful for text-like MIME types: csv, json, xml.
```

**`A.save` — content → artifact service (direct, no state bridge)**

```python
A.save("report.md", content="# My Report\n\nFindings here.")
# Direct write. Content is literal, not read from state.
# No state bridge — no coupling between the two planes.
# Metadata: consumes_state=set(), produces_artifact={"report.md"}

A.save("config.json", content=json.dumps(config), mime=A.mime.json)
# Direct write with explicit MIME type.
```

**`A.load` — artifact → pipeline (direct, no state bridge)**

```python
A.load("report.md")
# Direct read. Returns ATransform for >> composition or A.for_llm().
# Does NOT write to state. Content stays in the artifact pipeline.
# Use with >> transforms (Phase 2) or A.for_llm().
```

**Metadata and lifecycle (no state bridge)**

```python
A.list(into_key="artifacts")
# Metadata only (list of filenames). Small, safe to put in state.
# state["artifacts"] = ["report.md", "chart.png"]

A.version("report.md", into_key="report_meta")
# Metadata only. state["report_meta"] = {version: 3, mime_type: ..., ...}

A.delete("report.md")
# Direct operation. No state involved.
```

**Scope**

```python
A.publish("shared.md", from_key="report", scope="user")
# User-scoped artifact (persists across sessions).
# Internally prepends "user:" to filename per ADK convention.

A.snapshot("shared.md", into_key="report_text", scope="user")
# Snapshot from user-scoped artifact.
```

**Conditional**

```python
A.when("has_report", A.publish("report.md", from_key="report"))
# Only publish if state["has_report"] is truthy.
# Uniform with S.when(), C.when(), M.when(), P.when().
```

#### 1.3 ATransform Return Type

All factories return `ATransform`:

```python
@dataclass(frozen=True, slots=True)
class ATransform:
    """Composable artifact operation descriptor."""
    _fn: Callable                              # Marker function (real work at runtime)
    _op: Literal["publish", "snapshot", "save", "load",
                  "list", "version", "delete"]
    _bridges_state: bool                       # True for publish/snapshot, False for save/load
    _filename: str | None
    _from_key: str | None                      # State key to read (publish)
    _into_key: str | None                      # State key to write (snapshot/list/version)
    _mime: str | None                          # Explicit MIME override
    _scope: Literal["session", "user"]
    _version: int | None                       # Specific version (snapshot)
    _metadata: dict[str, Any] | None           # Custom metadata (publish/save)
    _content: str | bytes | None               # Literal content (save)
    _decode: bool                              # Force text decode (snapshot)
    _produces_artifact: frozenset[str]          # Artifact filenames produced
    _consumes_artifact: frozenset[str]          # Artifact filenames consumed
    _produces_state: frozenset[str]             # State keys written (only for bridge ops)
    _consumes_state: frozenset[str]             # State keys read (only for bridge ops)
    _name: str
```

**Two separate key sets** — one for artifact flow (`_produces_artifact` /
`_consumes_artifact`) and one for state flow (`_produces_state` /
`_consumes_state`). The `_bridges_state` flag is `True` only for `publish` and
`snapshot` — the operations that cross the boundary. For `save` (direct content)
and `load` (pipeline-only), state key sets are empty. The contract checker
validates each plane independently and can warn specifically about bridge
operations.

#### 1.4 Pipeline Integration (`>>`)

ATransform participates in pipelines via the same `_fn_step()` detection pattern
used by `S.capture()`:

```python
pipeline = (
    Agent("researcher").instruct("Research the topic.").save_as("findings")
    >> A.publish("findings.md", from_key="findings")     # state → artifact
    >> A.snapshot("findings.md", into_key="source")       # artifact → state
    >> Agent("writer").instruct("Write report from {source}.").save_as("report")
    >> A.publish("report.md", from_key="report")          # state → artifact
)
```

Build-time wiring:

1. `ATransform` is callable (but a no-op marker, like `S.capture()`)
1. `_fn_step()` detects `_artifact_op` attribute on the callable
1. Creates `_ArtifactBuilder` (analogous to `_CaptureBuilder`)
1. At `.build()`, creates `ArtifactAgent` (new runtime agent, accesses
   `ctx.artifact_service` and `ctx.session.state`)
1. At `.to_ir()`, emits `ArtifactNode`

#### 1.5 Builder Method

```python
Agent("writer") \
    .instruct("Write the report.") \
    .save_as("report") \
    .artifacts(
        A.publish("report.md", from_key="report"),
        A.publish("summary.txt", from_key="report", mime=A.mime.text),
    )
```

`.artifacts()` attaches `ATransform` instances that fire as after-agent hooks.
Added to `seed.manual.toml` as a new extras entry.

#### 1.6 Runtime: `ArtifactAgent`

New class in `_primitives.py`, following the `CaptureAgent` pattern:

```python
class ArtifactAgent(BaseAgent):
    """Zero-cost artifact agent. No LLM call.
    Handles both bridge ops (publish/snapshot) and direct ops (save/load).
    """

    async def _run_async_impl(self, ctx):
        svc = ctx._invocation_context.artifact_service
        if svc is None:
            raise ValueError("No artifact_service configured on Runner")

        if self._op == "publish":  # STATE BRIDGE: state → artifact
            content = self._read_from_state(ctx)  # reads state[from_key]
            part = self._to_part(content)      # str→Part.from_text, bytes→Part.from_bytes
            version = await svc.save_artifact(
                app_name=..., user_id=..., session_id=...,
                filename=self._filename,
                artifact=part,
                custom_metadata=self._metadata,
            )
            ctx._event_actions.artifact_delta[self._filename] = version

        elif self._op == "save":  # DIRECT: content → artifact (no state)
            part = self._to_part(self._content)
            version = await svc.save_artifact(
                app_name=..., user_id=..., session_id=...,
                filename=self._filename,
                artifact=part,
                custom_metadata=self._metadata,
            )
            ctx._event_actions.artifact_delta[self._filename] = version

        elif self._op == "snapshot":  # STATE BRIDGE: artifact → state
            part = await svc.load_artifact(
                app_name=..., user_id=..., session_id=...,
                filename=self._filename,
                version=self._version,
            )
            if part is not None:
                if A.mime.is_text_like(self._mime) or self._decode:
                    ctx.session.state[self._into_key] = self._extract_text(part)
                else:
                    # Binary: store URI reference, not bytes
                    ctx.session.state[self._into_key] = self._build_uri(...)

        elif self._op == "load":  # DIRECT: artifact → pipeline (no state)
            # Content stays in pipeline context, not written to state.
            # Used with >> transforms or A.for_llm().
            pass

        elif self._op == "list":
            keys = await svc.list_artifact_keys(...)
            ctx.session.state[self._into_key] = keys

        elif self._op == "version":
            ver = await svc.get_artifact_version(...)
            ctx.session.state[self._into_key] = self._version_to_dict(ver)

        elif self._op == "delete":
            await svc.delete_artifact(...)
```

#### 1.7 IR Node

```python
@dataclass(frozen=True)
class ArtifactNode:
    """Artifact operation in the IR."""
    name: str
    op: Literal["publish", "snapshot", "save", "load",
                "list", "version", "delete"]
    bridges_state: bool                     # True for publish/snapshot
    filename: str | None
    from_key: str | None                    # State key read (publish only)
    into_key: str | None                    # State key written (snapshot/list/version)
    mime: str | None
    scope: Literal["session", "user"]
    version: int | None
    produces_artifact: frozenset[str]
    consumes_artifact: frozenset[str]
    produces_state: frozenset[str]          # Non-empty only when bridges_state=True
    consumes_state: frozenset[str]          # Non-empty only when bridges_state=True
```

#### 1.8 Contract Checking (Pass 15: Artifact Availability)

New pass walks the sequence tracking `artifacts_available: set[str]`:

```python
# Pass 15: Artifact availability + bridge validation
artifacts_available: set[str] = set()

for child in children:
    if not isinstance(child, ArtifactNode):
        continue

    # ── Artifact plane validation ──────────────────────────
    for artifact_name in child.consumes_artifact:
        if artifact_name not in artifacts_available:
            issues.append(error(
                f"Consumes artifact '{artifact_name}' but no upstream "
                f"A.publish() or A.save() produces it"
            ))

    # ── State plane validation (bridge ops only) ──────────
    if child.bridges_state:
        for key in child.consumes_state:
            if key not in state_available:
                issues.append(error(
                    f"A.publish() reads state key '{key}' but no "
                    f"upstream agent produces it"
                ))

    # ── Bridge-specific warnings ──────────────────────────
    if child.op == "snapshot" and child.into_key:
        # Warn if snapshot content isn't cleaned up downstream
        # (risk: large text bloating session serialization)
        if not _has_downstream_drop(children, child.into_key):
            issues.append(info(
                f"A.snapshot() writes '{child.into_key}' to state. "
                f"Consider using temp:{child.into_key} or adding "
                f"S.drop('{child.into_key}') downstream to avoid "
                f"session bloat."
            ))

    # ── Promote produces ──────────────────────────────────
    artifacts_available |= child.produces_artifact
    state_available |= child.produces_state
```

**Cross-validation**: Pass 15 checks artifact availability AND feeds
`produces_state` / `consumes_state` back into the running state availability
set. The two planes reinforce each other — an `A.snapshot()` that writes to
state is visible to downstream state checks in Pass 10.

**Bridge warnings**: The contract checker specifically warns about `A.snapshot()`
operations that write to state without a downstream `S.drop()` or `temp:` prefix.
This is the primary mitigation for state bloat — the checker nudges users toward
safe patterns.

**MIME validation**: If an `A.publish()` specifies `mime=A.mime.png` but
`from_key` reads a state key produced by a text-outputting agent, the contract
checker warns about likely MIME mismatch.

### Phase 2: Transform Helpers + LLM-Aware Loading + Tool Factories

Builds on Phase 1 to make artifacts truly useful in multi-agent workflows.

#### 2.1 Content Transforms (`A.as_*` and `A.from_*`)

Composable transforms that convert artifact content. Compose with
`A.snapshot()` (post-load) or `A.publish()` (pre-save) via `>>` / `<<`:

**Post-snapshot (artifact → structured state)**

```python
A.snapshot("data.json", into_key="data") >> A.as_json()
# Snapshots artifact text, json.loads() it, puts dict in state["data"]

A.snapshot("results.csv", into_key="rows") >> A.as_csv()
# Snapshots artifact text, csv.DictReader, puts list[dict] in state["rows"]

A.snapshot("results.csv", into_key="rows") >> A.as_csv(columns=["name", "score"])
# Selective column extraction

A.snapshot("raw.bin", into_key="text") >> A.as_text(encoding="utf-8")
# Force UTF-8 decode of binary artifact snapshot
```

**Pre-publish (structured state → artifact)**

```python
A.publish("config.json", from_key="config") << A.from_json(indent=2)
# json.dumps(state["config"]) → publishes as text artifact with json MIME

A.publish("results.csv", from_key="rows") << A.from_csv()
# csv.writer over state["rows"] (list[dict]) → csv text artifact

A.publish("report.html", from_key="report") << A.from_markdown()
# markdown.markdown(state["report"]) → html text artifact
```

**Design principle**: A ships lightweight transforms for JSON/CSV/text that are
pure Python stdlib (no heavy dependencies). Heavy transforms (PDF generation,
image processing) happen via code execution tools or custom functions. The
composition point (`>>` / `<<`) is the extensibility mechanism.

#### 2.2 LLM-Aware Loading (`A.for_llm`)

When an artifact needs to go to the LLM, `A.for_llm()` provides **direct
injection into LLM context without touching state** — no bridge, no snapshot:

```python
A.for_llm("report.md")
# DIRECT (no state bridge): artifact → LLM context
# Text/CSV/JSON → decoded text injected via instruction context
# Image/Audio/Video/PDF → inline Part added to LLM context
# Other binary → placeholder description with filename, MIME, size
# Uses same classification as LoadArtifactsTool._as_safe_part_for_llm

# Integration with C module
Agent("reviewer") \
    .instruct("Review this report.") \
    .context(C.from_state("topic") + A.for_llm("report.md"))
# A.for_llm() returns a CTransform-compatible descriptor that loads
# the artifact and injects it as context content.
# This is the PREFERRED path for binary artifacts — bypasses state entirely.

# Conditional
A.for_llm("chart.png").when("needs_visual_review")
```

**MIME-aware conversion matrix** (matches ADK's `LoadArtifactsTool`):

| Artifact MIME      | LLM receives        | Notes                                            |
| ------------------ | ------------------- | ------------------------------------------------ |
| `image/*`          | Inline image Part   | Gemini native multimodal                         |
| `audio/*`          | Inline audio Part   | Gemini native multimodal                         |
| `video/*`          | Inline video Part   | Gemini native multimodal                         |
| `application/pdf`  | Inline PDF Part     | Gemini native document understanding             |
| `text/*`           | Decoded text string | UTF-8 decode, charset stripped                   |
| `application/json` | Decoded text string | Treated as text-like                             |
| `application/csv`  | Decoded text string | Treated as text-like                             |
| `application/xml`  | Decoded text string | Treated as text-like                             |
| Other binary       | Placeholder text    | `[Binary artifact: name, type: mime, size: NKB]` |

#### 2.3 Tool Factories (`A.tool`)

LLMs need tools to interact with artifacts at runtime. Today this requires ~15
lines of boilerplate per tool. A generates them in one line:

```python
# Save tool — LLM decides when to call and what content to save
save_tool = A.tool.save("save_report", mime=A.mime.markdown)
# Creates FunctionTool: save_report(filename: str, content: str)
#   → {"saved": filename, "version": int}

# Scoped save — whitelist allowed filenames (prevents arbitrary writes)
save_tool = A.tool.save("save_report",
    allowed=["report.md", "summary.txt"],
    mime=A.mime.markdown,
)
# LLM can only save to whitelisted filenames

# Load tool — LLM can read artifact content
load_tool = A.tool.load("read_file")
# Creates FunctionTool: read_file(filename: str)
#   → text content (or description for binary)

# List tool — LLM can discover available artifacts
list_tool = A.tool.list("list_files")
# Creates FunctionTool: list_files()
#   → {"artifacts": ["file1.md", "file2.png"]}

# Version tool — LLM can check artifact metadata
version_tool = A.tool.version("check_version")
# Creates FunctionTool: check_version(filename: str)
#   → {"version": 3, "mime_type": "text/markdown", "created": "..."}

# Full toolbox on an agent
Agent("worker") \
    .instruct("Process the data and save results.") \
    .tools(
        A.tool.load("read_data"),
        A.tool.save("save_result", allowed=["result.json"]),
        A.tool.list("list_available"),
    )
```

**Design rationale**: The generated tools handle Part construction, MIME type
assignment, error handling, and response formatting. The `allowed` parameter on
save tools provides a security boundary — the LLM can only write to declared
filenames, preventing arbitrary file creation.

#### 2.4 Multi-Artifact Operations

```python
A.publish_many(
    ("report.md", "report"),
    ("data.json", "raw_data"),
    ("summary.txt", "summary"),
)
# ⚠ STATE BRIDGE (batch): reads multiple state keys, publishes to artifacts
# Equivalent to A.publish("report.md", from_key="report")
#            + A.publish("data.json", from_key="raw_data")
#            + A.publish("summary.txt", from_key="summary")
# Executes as single ArtifactAgent with multiple operations

A.snapshot_many(
    ("report.md", "report_text"),
    ("data.json", "raw_data"),
)
# ⚠ STATE BRIDGE (batch): snapshots multiple artifacts into state
```

### Phase 3: ArtifactSchema + Full Contract Integration + Visualization

#### 3.1 ArtifactSchema

New schema type using the existing `DeclarativeMetaclass` from `_schema_base.py`:

```python
from adk_fluent import ArtifactSchema

class ResearchArtifacts(ArtifactSchema):
    findings: str = Produces("findings.json", mime=A.mime.json)
    report:   str = Produces("report.md",     mime=A.mime.markdown)
    source:   str = Consumes("raw_data.csv",  mime=A.mime.csv)

Agent("researcher") \
    .instruct("Research and produce findings.") \
    .artifact_schema(ResearchArtifacts)
```

**New annotation types** (alongside existing `Reads`, `Writes`, `Param`,
`Confirms`, `Timeout`):

```python
@dataclass(frozen=True)
class Produces:
    """Declares that an agent produces this artifact."""
    filename: str
    mime: str | None = None
    scope: str = "session"

@dataclass(frozen=True)
class Consumes:
    """Declares that an agent requires this artifact from upstream."""
    filename: str
    mime: str | None = None
    scope: str = "session"
```

Schema enables:

- **Pyright checking** — `ResearchArtifacts.findings` is a typed descriptor
- **Contract checking (Pass 16)** — validates artifact schemas match pipeline
  flow and MIME types are compatible
- **Documentation** — `.explain()` lists artifact contracts per agent
- **MIME validation** — schema declares expected MIME, checker warns on mismatch
  between producer and consumer

#### 3.2 Contract Checking (Pass 16: ArtifactSchema Validation)

```python
# Pass 16: ArtifactSchema dependency validation
for child in children:
    schema = getattr(child, "artifact_schema", None)
    if schema is None:
        continue

    # Check consumed artifacts are available
    for field in schema.consumes_fields():
        if field.filename not in artifacts_available:
            issues.append(error(f"ArtifactSchema consumes '{field.filename}' "
                                f"but not produced upstream"))

        # MIME compatibility check
        producer_mime = artifact_mime_map.get(field.filename)
        if producer_mime and field.mime and producer_mime != field.mime:
            issues.append(warning(f"MIME mismatch: '{field.filename}' produced "
                                  f"as {producer_mime}, consumed as {field.mime}"))

    # Promote produced artifacts
    for field in schema.produces_fields():
        artifacts_available.add(field.filename)
        artifact_mime_map[field.filename] = field.mime
```

#### 3.3 Visualization Integration

`adk-fluent visualize` and `.explain()` gain artifact edges:

```
                   state:findings
researcher ─────────────────────▶ A.publish ─ ─ ─ artifact:findings.md ─ ─ ─▶
                                                                              │
◀─ ─ ─ ─ ─ ─ ─artifact:findings.md ─ ─ ─ ─  A.snapshot ◀─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
                                                  │
                                           state:source
                                           (point-in-time copy)
                                                  │
                                                  ▼
                                                writer
```

- Artifact edges rendered as **dashed lines** (distinct from solid state edges)
- MIME types shown as edge labels
- Scope (session/user) indicated by color or annotation

#### 3.4 Lineage Tracking

```python
A.save("report_v2.md", from_key="revised",
    lineage=A.derived_from("report.md"))
# Stores {"derived_from": "report.md", "source_version": N} in custom_metadata
# Visualization can show derivation DAG

A.lineage("report_v2.md", into_key="history")
# Traverses custom_metadata.derived_from chain
# state["history"] = [
#     {"filename": "report_v2.md", "version": 1, "derived_from": "report.md"},
#     {"filename": "report.md", "version": 3, "derived_from": None},
# ]
```

## Implementation Architecture

### File Layout

```
src/adk_fluent/
  _artifacts.py          # A class, ATransform, A.mime (hand-written)
  _primitives.py         # ArtifactAgent added alongside CaptureAgent
  _primitive_builders.py # _ArtifactBuilder added alongside _CaptureBuilder
  _ir.py                 # ArtifactNode added
  _schema_base.py        # Produces, Consumes annotations (Phase 3)
  testing/contracts.py   # Pass 15 (Phase 1), Pass 16 (Phase 3)
  prelude.py             # A re-exported as Tier 2 composition namespace
```

### Build Pipeline Integration

Same pattern as `S.capture()`:

```
A.publish("report.md", from_key="report")   # Returns ATransform (callable, bridges_state=True)
         │
         ▼
_fn_step(atransform)                        # Detects _artifact_op attribute
         │
         ▼
_ArtifactBuilder(name, op, ...)             # Stores operation params
         │
    ┌────┴────┐
    ▼         ▼
.build()   .to_ir()
    │         │
    ▼         ▼
ArtifactAgent  ArtifactNode(bridges_state=True)
(runtime)      (contract checking, visualization)
```

### Export

```python
# __init__.py
from ._artifacts import A, ATransform

# prelude.py — Tier 2: Composition namespaces
from adk_fluent import P, C, S, M, T, A
```

## Phase Summary

| Phase | Ships                                                                                                                                                                                                                          | Key Capability                                                                                      | Depends On |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- | ---------- |
| **1** | `A.publish/snapshot/save/load/list/version/delete`, `A.mime.*`, `A.when()`, `ATransform`, `ArtifactNode`, `ArtifactAgent`, `_ArtifactBuilder`, Pass 15 (with bridge warnings), `>>` integration, `.artifacts()` builder method | Zero-ceremony artifact wiring with MIME safety, contract checking, and transparent bridge semantics | Nothing    |
| **2** | `A.as_json/csv/text()`, `A.from_json/csv/markdown()`, `A.for_llm()`, `A.tool.save/load/list/version()`, `A.publish_many/snapshot_many()`                                                                                       | Transform composability, LLM-aware loading (no state bridge), tool generation                       | Phase 1    |
| **3** | `ArtifactSchema`, `Produces`/`Consumes` annotations, Pass 16, visualization artifact edges (dashed + annotated), `A.lineage()`, `.artifact_schema()` builder method                                                            | Full declarative contracts, visualization, lineage                                                  | Phase 1+2  |

Each phase is independently shippable and non-breaking.

## Verb Reference

Quick reference for which operations bridge state and which don't:

| Verb         | Direction              | Bridges State? | State Risk                   | Use When                                                    |
| ------------ | ---------------------- | -------------- | ---------------------------- | ----------------------------------------------------------- |
| `A.publish`  | state → artifact       | **Yes**        | Reads from state             | Agent output needs to persist as versioned artifact         |
| `A.snapshot` | artifact → state       | **Yes**        | Writes to state (bloat risk) | Next agent needs artifact content via `{key}` template      |
| `A.save`     | content → artifact     | No             | None                         | Direct content write, no state involvement                  |
| `A.load`     | artifact → pipeline    | No             | None                         | Pipeline composition with `>>` transforms                   |
| `A.for_llm`  | artifact → LLM context | No             | None                         | Binary/multimodal content for LLM (preferred over snapshot) |
| `A.list`     | metadata → state       | Lightweight    | Filenames only               | Agent needs to discover available artifacts                 |
| `A.version`  | metadata → state       | Lightweight    | Small dict only              | Agent needs artifact version/MIME info                      |
| `A.delete`   | artifact deletion      | No             | None                         | Cleanup                                                     |

**Rule of thumb**: If the verb is `publish` or `snapshot`, you're crossing the
state/artifact boundary. The contract checker will remind you.

## Non-Goals

- **Heavy format converters** — no PDF generation, image processing, or audio
  transcoding. Use code execution tools or external libraries.
- **Streaming artifacts** — large file streaming is out of scope; artifacts are
  loaded/saved atomically.
- **Artifact search** — semantic search over artifact content is out of scope;
  use RAG tools.
- **Artifact permissions** — access control is delegated to the underlying
  artifact service backend (GCS IAM, filesystem permissions).
- **Transparent state/artifact merging** — we do NOT silently mix the two planes.
  Bridge operations are explicitly named (`publish`/`snapshot`) and flagged by
  the contract checker. This is a design principle, not a limitation.
