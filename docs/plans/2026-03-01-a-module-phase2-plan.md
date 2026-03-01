# A Module Phase 2+3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add content transforms, LLM-aware loading, tool factories, multi-artifact ops, ArtifactSchema, contract Pass 16, and visualization integration to the A module.

**Architecture:** Phase 2 adds ergonomic helpers (content transforms as STransform factories, LLM-aware context injection via CTransform, ADK FunctionTool generation, batch ops) on top of Phase 1's ATransform/ArtifactNode/ArtifactAgent foundation. Phase 3 adds declarative `ArtifactSchema` with `Produces`/`Consumes` annotations, builds Pass 16 contract checking on the existing `_schema_base.py` metaclass infrastructure, and wires artifact edges into `viz.py`'s Mermaid output.

**Tech Stack:** Python stdlib (`json`, `csv`, `io`), existing `STransform` from `_transforms.py`, `CTransform` from `_context.py`, `DeclarativeMetaclass` from `_schema_base.py`, ADK's `FunctionTool`

______________________________________________________________________

## Context for Implementers

### Key files (all paths relative to repo root)

| File                                    | Role                                                           |
| --------------------------------------- | -------------------------------------------------------------- |
| `src/adk_fluent/_artifacts.py`          | A class, ATransform, \_MimeConstants — **main file to modify** |
| `src/adk_fluent/_transforms.py`         | STransform class — content transforms return these             |
| `src/adk_fluent/_context.py`            | CTransform class — A.for_llm() returns one of these            |
| `src/adk_fluent/_primitives.py`         | ArtifactAgent runtime — may need new ops                       |
| `src/adk_fluent/_primitive_builders.py` | \_ArtifactBuilder — may need batch support                     |
| `src/adk_fluent/_ir.py`                 | ArtifactNode — already in Node union                           |
| `src/adk_fluent/_schema_base.py`        | DeclarativeMetaclass — base for ArtifactSchema                 |
| `src/adk_fluent/testing/contracts.py`   | Pass 15 exists — add Pass 16                                   |
| `src/adk_fluent/viz.py`                 | ir_to_mermaid() — add ArtifactNode rendering                   |
| `src/adk_fluent/prelude.py`             | Public exports                                                 |
| `seeds/seed.manual.toml`                | Builder method definitions                                     |
| `tests/manual/test_artifacts.py`        | All artifact tests (currently 41 tests)                        |

### STransform constructor

```python
STransform(
    fn,                           # Callable[[dict], StateDelta | dict | None]
    *,
    reads: frozenset[str] | None = None,
    writes: frozenset[str] | None = None,
    name: str = "transform",
    capture_key: str | None = None,
)
```

### CTransform pattern

A frozen dataclass with `include_contents` and `instruction_provider` (async Callable). Factory methods return subclass instances. See existing `CFromState`, `CTemplate` in `_context.py` for patterns.

### Pre-commit checklist (run before every commit)

```bash
ruff check --fix . && ruff format .
just typecheck-core
just preflight
uv run pytest tests/ -x --tb=short -q
```

______________________________________________________________________

## Phase 2: Transform Helpers + LLM-Aware Loading + Tool Factories

### Task 1: Content Transforms — Post-Snapshot (A.as_json, A.as_csv, A.as_text)

These are STransform factories on the `A` class. Each takes a state key name and returns an `STransform` that parses the string value at that key into a structured value.

**Files:**

- Modify: `src/adk_fluent/_artifacts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

Add to `tests/manual/test_artifacts.py`:

```python
class TestContentTransformsPost:
    """A.as_json, A.as_csv, A.as_text — post-snapshot transforms."""

    def test_as_json_parses_string(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        t = A.as_json("data")
        assert isinstance(t, STransform)
        result = t({"data": '{"x": 1}'})
        assert result == {"data": {"x": 1}}

    def test_as_json_reads_writes_keys(self):
        from adk_fluent import A

        t = A.as_json("data")
        assert t._reads_keys == frozenset({"data"})
        assert t._writes_keys == frozenset({"data"})

    def test_as_csv_parses_string(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        csv_text = "name,score\nAlice,90\nBob,85"
        t = A.as_csv("rows")
        assert isinstance(t, STransform)
        result = t({"rows": csv_text})
        rows = result["rows"]
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["score"] == "90"

    def test_as_csv_with_columns(self):
        from adk_fluent import A

        csv_text = "name,score,grade\nAlice,90,A\nBob,85,B"
        t = A.as_csv("rows", columns=["name", "score"])
        result = t({"rows": csv_text})
        rows = result["rows"]
        assert set(rows[0].keys()) == {"name", "score"}

    def test_as_text_identity(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        t = A.as_text("content")
        assert isinstance(t, STransform)
        result = t({"content": "hello world"})
        assert result == {"content": "hello world"}

    def test_as_text_decode_bytes(self):
        from adk_fluent import A

        t = A.as_text("content")
        result = t({"content": b"hello bytes"})
        assert result == {"content": "hello bytes"}

    def test_as_text_custom_encoding(self):
        from adk_fluent import A

        t = A.as_text("content", encoding="latin-1")
        result = t({"content": "café".encode("latin-1")})
        assert result["content"] == "café"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestContentTransformsPost -v`
Expected: FAIL — `A` has no `as_json`, `as_csv`, `as_text` methods.

**Step 3: Implement the content transforms**

Add to the `A` class in `src/adk_fluent/_artifacts.py`:

```python
@staticmethod
def as_json(key: str) -> STransform:
    """Parse JSON string in state[key] to dict/list.

    Usage: A.snapshot("data.json", into_key="data") >> A.as_json("data")
    """
    import json as _json

    return STransform(
        lambda state: {key: _json.loads(state[key])},
        reads=frozenset({key}),
        writes=frozenset({key}),
        name=f"as_json_{key}",
    )

@staticmethod
def as_csv(key: str, *, columns: list[str] | None = None) -> STransform:
    """Parse CSV string in state[key] to list[dict].

    Usage: A.snapshot("data.csv", into_key="rows") >> A.as_csv("rows")
    """
    import csv as _csv
    import io as _io

    def _parse_csv(state: dict) -> dict:
        reader = _csv.DictReader(_io.StringIO(state[key]))
        if columns:
            return {key: [{c: row[c] for c in columns} for row in reader]}
        return {key: list(reader)}

    return STransform(
        _parse_csv,
        reads=frozenset({key}),
        writes=frozenset({key}),
        name=f"as_csv_{key}",
    )

@staticmethod
def as_text(key: str, *, encoding: str = "utf-8") -> STransform:
    """Ensure state[key] is a decoded string. Decodes bytes if needed.

    Usage: A.snapshot("raw.bin", into_key="text") >> A.as_text("text")
    """

    def _to_text(state: dict) -> dict:
        val = state[key]
        if isinstance(val, bytes):
            return {key: val.decode(encoding, errors="replace")}
        return {key: str(val)}

    return STransform(
        _to_text,
        reads=frozenset({key}),
        writes=frozenset({key}),
        name=f"as_text_{key}",
    )
```

You also need to add `STransform` import at the top of `_artifacts.py`:

```python
from adk_fluent._transforms import STransform
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestContentTransformsPost -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
git add src/adk_fluent/_artifacts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add post-snapshot content transforms as_json, as_csv, as_text"
```

______________________________________________________________________

### Task 2: Content Transforms — Pre-Publish (A.from_json, A.from_csv, A.from_markdown)

STransform factories that serialize structured state values into strings suitable for publishing to artifacts.

**Files:**

- Modify: `src/adk_fluent/_artifacts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
class TestContentTransformsPre:
    """A.from_json, A.from_csv, A.from_markdown — pre-publish transforms."""

    def test_from_json_serializes(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        t = A.from_json("config")
        assert isinstance(t, STransform)
        result = t({"config": {"x": 1, "y": [2, 3]}})
        import json

        assert json.loads(result["config"]) == {"x": 1, "y": [2, 3]}

    def test_from_json_indent(self):
        from adk_fluent import A

        t = A.from_json("config", indent=2)
        result = t({"config": {"x": 1}})
        assert "\n" in result["config"]  # indented output has newlines

    def test_from_csv_serializes(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        rows = [{"name": "Alice", "score": "90"}, {"name": "Bob", "score": "85"}]
        t = A.from_csv("rows")
        assert isinstance(t, STransform)
        result = t({"rows": rows})
        assert "Alice" in result["rows"]
        assert "Bob" in result["rows"]
        assert "name,score" in result["rows"] or "score,name" in result["rows"]

    def test_from_markdown_converts_to_html(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        t = A.from_markdown("report")
        assert isinstance(t, STransform)
        result = t({"report": "# Hello\n\nWorld"})
        assert "<h1>" in result["report"] or "<h1" in result["report"]
        assert "World" in result["report"]

    def test_from_json_reads_writes_keys(self):
        from adk_fluent import A

        t = A.from_json("data")
        assert t._reads_keys == frozenset({"data"})
        assert t._writes_keys == frozenset({"data"})
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestContentTransformsPre -v`
Expected: FAIL

**Step 3: Implement**

Add to the `A` class in `src/adk_fluent/_artifacts.py`:

```python
@staticmethod
def from_json(key: str, *, indent: int | None = None) -> STransform:
    """Serialize state[key] dict/list to JSON string.

    Usage: A.from_json("config") >> A.publish("config.json", from_key="config")
    """
    import json as _json

    return STransform(
        lambda state: {key: _json.dumps(state[key], indent=indent, default=str)},
        reads=frozenset({key}),
        writes=frozenset({key}),
        name=f"from_json_{key}",
    )

@staticmethod
def from_csv(key: str) -> STransform:
    """Serialize state[key] list[dict] to CSV string.

    Usage: A.from_csv("rows") >> A.publish("results.csv", from_key="rows")
    """
    import csv as _csv
    import io as _io

    def _to_csv(state: dict) -> dict:
        rows = state[key]
        if not rows:
            return {key: ""}
        buf = _io.StringIO()
        fieldnames = list(rows[0].keys())
        writer = _csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return {key: buf.getvalue()}

    return STransform(
        _to_csv,
        reads=frozenset({key}),
        writes=frozenset({key}),
        name=f"from_csv_{key}",
    )

@staticmethod
def from_markdown(key: str) -> STransform:
    """Convert Markdown state[key] to HTML string.

    Uses Python's built-in markdown if available, falls back to minimal conversion.
    Usage: A.from_markdown("report") >> A.publish("report.html", from_key="report")
    """

    def _md_to_html(state: dict) -> dict:
        text = state[key]
        try:
            import markdown

            return {key: markdown.markdown(text)}
        except ImportError:
            # Minimal fallback: wrap in <pre> if markdown not installed
            import html

            return {key: f"<pre>{html.escape(text)}</pre>"}

    return STransform(
        _md_to_html,
        reads=frozenset({key}),
        writes=frozenset({key}),
        name=f"from_markdown_{key}",
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestContentTransformsPre -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
git add src/adk_fluent/_artifacts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add pre-publish content transforms from_json, from_csv, from_markdown"
```

______________________________________________________________________

### Task 3: LLM-Aware Loading (A.for_llm)

Returns a CTransform descriptor that loads artifact content into LLM context at runtime. Text artifacts become instruction text; multimodal artifacts (image/audio/video/pdf) get a placeholder description (full multimodal injection requires ADK-level changes beyond our scope).

**Files:**

- Modify: `src/adk_fluent/_artifacts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
class TestForLlm:
    """A.for_llm — CTransform-compatible artifact context injection."""

    def test_for_llm_returns_ctransform(self):
        from adk_fluent import A
        from adk_fluent._context import CTransform

        result = A.for_llm("report.md")
        assert isinstance(result, CTransform)

    def test_for_llm_include_contents_none(self):
        from adk_fluent import A

        result = A.for_llm("report.md")
        assert result.include_contents == "none"

    def test_for_llm_has_instruction_provider(self):
        from adk_fluent import A

        result = A.for_llm("report.md")
        assert result.instruction_provider is not None
        assert callable(result.instruction_provider)

    def test_for_llm_filename_stored(self):
        from adk_fluent import A

        result = A.for_llm("report.md")
        assert result._filename == "report.md"

    def test_for_llm_scope_default(self):
        from adk_fluent import A

        result = A.for_llm("report.md")
        assert result._scope == "session"

    def test_for_llm_scope_user(self):
        from adk_fluent import A

        result = A.for_llm("report.md", scope="user")
        assert result._scope == "user"

    def test_for_llm_composes_with_c_plus(self):
        """A.for_llm() can be combined with C blocks via +."""
        from adk_fluent import A, C
        from adk_fluent._context import CTransform

        combined = C.from_state("topic") + A.for_llm("report.md")
        assert isinstance(combined, CTransform)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestForLlm -v`
Expected: FAIL

**Step 3: Implement**

Add a CTransform subclass and factory method. In `src/adk_fluent/_artifacts.py`:

```python
from adk_fluent._context import CTransform

@dataclass(frozen=True)
class _ArtifactContextBlock(CTransform):
    """CTransform that loads artifact content for LLM context injection.

    Text/text-like artifacts: decoded text injected as instruction context.
    Binary artifacts: placeholder description with filename, MIME, and type.
    """

    _filename: str = ""
    _scope: Literal["session", "user"] = "session"
    _version: int | None = None

    def __post_init__(self) -> None:
        provider = _make_artifact_context_provider(
            self._filename, self._scope, self._version
        )
        object.__setattr__(self, "instruction_provider", provider)
        object.__setattr__(self, "include_contents", "none")


def _make_artifact_context_provider(
    filename: str,
    scope: str,
    version: int | None,
) -> Callable:
    """Create an async instruction_provider that loads artifact content."""

    async def _provider(ctx: Any) -> str:
        svc = ctx._invocation_context.artifact_service
        if svc is None:
            return f"[Artifact '{filename}' unavailable: no artifact service configured]"

        app_name = ctx._invocation_context.app_name
        user_id = ctx._invocation_context.user_id
        session_id = ctx.session.id
        is_user = scope == "user"
        svc_session_id = None if is_user else session_id

        try:
            part = await svc.load_artifact(
                app_name=app_name,
                user_id=user_id,
                session_id=svc_session_id,
                filename=filename,
                version=version,
            )
        except Exception:
            return f"[Artifact '{filename}' could not be loaded]"

        if part is None:
            return f"[Artifact '{filename}' not found]"

        # Text content → inject directly
        if part.text is not None:
            return part.text

        # Binary content → detect MIME and provide description
        if part.inline_data:
            mime = part.inline_data.mime_type or _MimeConstants.detect(filename)
            if _MimeConstants.is_text_like(mime):
                return part.inline_data.data.decode("utf-8", errors="replace")
            # Non-text binary: placeholder
            size_kb = len(part.inline_data.data) / 1024
            return f"[Binary artifact: {filename}, type: {mime}, size: {size_kb:.1f}KB]"

        return f"[Artifact '{filename}': unrecognized format]"

    return _provider
```

Then add the `for_llm` static method to the `A` class:

```python
@staticmethod
def for_llm(
    filename: str,
    *,
    version: int | None = None,
    scope: Literal["session", "user"] = "session",
) -> CTransform:
    """Load artifact directly into LLM context. No state bridge.

    Text artifacts → decoded text injected as instruction context.
    Binary artifacts → placeholder description.
    Composes with C module: Agent("x").context(C.from_state("topic") + A.for_llm("report.md"))
    """
    return _ArtifactContextBlock(
        _filename=filename,
        _scope=scope,
        _version=version,
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestForLlm -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
git add src/adk_fluent/_artifacts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add A.for_llm() CTransform for LLM-aware artifact loading"
```

______________________________________________________________________

### Task 4: Tool Factories (A.tool namespace)

A nested class `_ToolFactory` exposed as `A.tool` that generates ADK `FunctionTool` instances for LLM agents to interact with artifacts at runtime.

**Files:**

- Modify: `src/adk_fluent/_artifacts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
class TestToolFactories:
    """A.tool.save, A.tool.load, A.tool.list, A.tool.version — FunctionTool generation."""

    def test_tool_save_creates_function_tool(self):
        from google.adk.tools import FunctionTool

        from adk_fluent import A

        tool = A.tool.save("save_report", mime=A.mime.markdown)
        assert isinstance(tool, FunctionTool)

    def test_tool_save_name(self):
        from adk_fluent import A

        tool = A.tool.save("save_report")
        assert tool.name == "save_report"

    def test_tool_save_with_allowed(self):
        from adk_fluent import A

        tool = A.tool.save("save_file", allowed=["report.md", "summary.txt"])
        assert tool.name == "save_file"

    def test_tool_load_creates_function_tool(self):
        from google.adk.tools import FunctionTool

        from adk_fluent import A

        tool = A.tool.load("read_file")
        assert isinstance(tool, FunctionTool)

    def test_tool_list_creates_function_tool(self):
        from google.adk.tools import FunctionTool

        from adk_fluent import A

        tool = A.tool.list("list_files")
        assert isinstance(tool, FunctionTool)

    def test_tool_version_creates_function_tool(self):
        from google.adk.tools import FunctionTool

        from adk_fluent import A

        tool = A.tool.version("check_version")
        assert isinstance(tool, FunctionTool)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestToolFactories -v`
Expected: FAIL

**Step 3: Implement**

Add to `src/adk_fluent/_artifacts.py`:

```python
class _ToolFactory:
    """Generates ADK FunctionTools for LLM artifact interaction.

    Usage:
        Agent("worker").tools(
            A.tool.load("read_data"),
            A.tool.save("save_result", allowed=["result.json"]),
        )
    """

    @staticmethod
    def save(
        name: str,
        *,
        mime: str | None = None,
        allowed: list[str] | None = None,
        scope: Literal["session", "user"] = "session",
    ) -> Any:
        """Create a FunctionTool that lets the LLM save artifact content.

        Args:
            name: Tool name (visible to LLM).
            mime: Default MIME type. Auto-detected from filename if not given.
            allowed: Whitelist of allowed filenames. None = any filename.
            scope: Artifact scope (session or user).
        """
        from google.adk.tools import FunctionTool

        allowed_set = frozenset(allowed) if allowed else None

        async def _save_fn(filename: str, content: str, tool_context: Any) -> dict:
            """Save content as a versioned artifact."""
            if allowed_set and filename not in allowed_set:
                return {"error": f"Filename '{filename}' not in allowed list: {sorted(allowed_set)}"}

            from google.genai import types as genai_types

            ctx = tool_context
            svc = ctx._invocation_context.artifact_service
            if svc is None:
                return {"error": "No artifact service configured"}

            resolved_mime = mime or _MimeConstants.detect(filename)
            part = genai_types.Part.from_text(text=content)
            is_user = scope == "user"
            svc_session_id = None if is_user else ctx.session.id

            version = await svc.save_artifact(
                app_name=ctx._invocation_context.app_name,
                user_id=ctx._invocation_context.user_id,
                session_id=svc_session_id,
                filename=filename,
                artifact=part,
            )
            delta_filename = f"user:{filename}" if is_user else filename
            ctx._event_actions.artifact_delta[delta_filename] = version
            return {"saved": filename, "version": version, "mime_type": resolved_mime}

        return FunctionTool(func=_save_fn, name=name)

    @staticmethod
    def load(
        name: str,
        *,
        scope: Literal["session", "user"] = "session",
    ) -> Any:
        """Create a FunctionTool that lets the LLM load artifact content."""
        from google.adk.tools import FunctionTool

        async def _load_fn(filename: str, tool_context: Any) -> dict:
            """Load artifact content."""
            ctx = tool_context
            svc = ctx._invocation_context.artifact_service
            if svc is None:
                return {"error": "No artifact service configured"}

            is_user = scope == "user"
            svc_session_id = None if is_user else ctx.session.id

            part = await svc.load_artifact(
                app_name=ctx._invocation_context.app_name,
                user_id=ctx._invocation_context.user_id,
                session_id=svc_session_id,
                filename=filename,
            )
            if part is None:
                return {"error": f"Artifact '{filename}' not found"}

            if part.text is not None:
                return {"filename": filename, "content": part.text}
            if part.inline_data:
                mime_type = part.inline_data.mime_type or _MimeConstants.detect(filename)
                if _MimeConstants.is_text_like(mime_type):
                    return {
                        "filename": filename,
                        "content": part.inline_data.data.decode("utf-8", errors="replace"),
                    }
                size_kb = len(part.inline_data.data) / 1024
                return {
                    "filename": filename,
                    "type": mime_type,
                    "size_kb": round(size_kb, 1),
                    "note": "Binary content — cannot display as text",
                }
            return {"filename": filename, "content": str(part)}

        return FunctionTool(func=_load_fn, name=name)

    @staticmethod
    def list(
        name: str,
        *,
        scope: Literal["session", "user"] = "session",
    ) -> Any:
        """Create a FunctionTool that lets the LLM list available artifacts."""
        from google.adk.tools import FunctionTool

        async def _list_fn(tool_context: Any) -> dict:
            """List available artifact filenames."""
            ctx = tool_context
            svc = ctx._invocation_context.artifact_service
            if svc is None:
                return {"error": "No artifact service configured"}

            is_user = scope == "user"
            svc_session_id = None if is_user else ctx.session.id

            keys = await svc.list_artifact_keys(
                app_name=ctx._invocation_context.app_name,
                user_id=ctx._invocation_context.user_id,
                session_id=svc_session_id,
            )
            return {"artifacts": keys}

        return FunctionTool(func=_list_fn, name=name)

    @staticmethod
    def version(
        name: str,
        *,
        scope: Literal["session", "user"] = "session",
    ) -> Any:
        """Create a FunctionTool that lets the LLM check artifact version metadata."""
        from google.adk.tools import FunctionTool

        async def _version_fn(filename: str, tool_context: Any) -> dict:
            """Get artifact version metadata."""
            ctx = tool_context
            svc = ctx._invocation_context.artifact_service
            if svc is None:
                return {"error": "No artifact service configured"}

            is_user = scope == "user"
            svc_session_id = None if is_user else ctx.session.id

            ver = await svc.get_artifact_version(
                app_name=ctx._invocation_context.app_name,
                user_id=ctx._invocation_context.user_id,
                session_id=svc_session_id,
                filename=filename,
            )
            if ver is None:
                return {"error": f"Artifact '{filename}' not found"}

            return {
                "filename": filename,
                "version": ver.version,
                "mime_type": ver.mime_type,
                "create_time": ver.create_time,
                "canonical_uri": ver.canonical_uri,
            }

        return FunctionTool(func=_version_fn, name=name)
```

Then add `tool` as a class attribute on `A`:

```python
class A:
    mime = _MimeConstants()
    tool = _ToolFactory()
    # ... rest of A class
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestToolFactories -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
git add src/adk_fluent/_artifacts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add A.tool factories for LLM artifact interaction"
```

______________________________________________________________________

### Task 5: Multi-Artifact Operations (A.publish_many, A.snapshot_many)

Batch factories that create multiple ATransform instances. These return a tuple of ATransforms suitable for `.artifacts(...)`.

**Files:**

- Modify: `src/adk_fluent/_artifacts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
class TestMultiArtifactOps:
    """A.publish_many, A.snapshot_many — batch operations."""

    def test_publish_many_returns_tuple(self):
        from adk_fluent import A

        result = A.publish_many(
            ("report.md", "report"),
            ("data.json", "raw_data"),
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_publish_many_each_is_atransform(self):
        from adk_fluent import A
        from adk_fluent._artifacts import ATransform

        result = A.publish_many(
            ("report.md", "report"),
            ("data.json", "raw_data"),
        )
        for t in result:
            assert isinstance(t, ATransform)
            assert t._op == "publish"

    def test_publish_many_correct_keys(self):
        from adk_fluent import A

        r, d = A.publish_many(
            ("report.md", "report"),
            ("data.json", "raw_data"),
        )
        assert r._filename == "report.md"
        assert r._from_key == "report"
        assert d._filename == "data.json"
        assert d._from_key == "raw_data"

    def test_snapshot_many_returns_tuple(self):
        from adk_fluent import A

        result = A.snapshot_many(
            ("report.md", "report_text"),
            ("data.json", "raw_data"),
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_snapshot_many_each_is_atransform(self):
        from adk_fluent import A
        from adk_fluent._artifacts import ATransform

        result = A.snapshot_many(
            ("report.md", "report_text"),
            ("data.json", "raw_data"),
        )
        for t in result:
            assert isinstance(t, ATransform)
            assert t._op == "snapshot"

    def test_snapshot_many_correct_keys(self):
        from adk_fluent import A

        r, d = A.snapshot_many(
            ("report.md", "report_text"),
            ("data.json", "raw_data"),
        )
        assert r._filename == "report.md"
        assert r._into_key == "report_text"
        assert d._filename == "data.json"
        assert d._into_key == "raw_data"

    def test_publish_many_with_artifacts_builder(self):
        """publish_many result works with .artifacts() via unpacking."""
        from adk_fluent import A, Agent

        transforms = A.publish_many(
            ("report.md", "report"),
            ("data.json", "raw_data"),
        )
        agent = Agent("writer").artifacts(*transforms)
        assert len(agent._lists.get("_artifact_transforms", [])) == 2
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestMultiArtifactOps -v`
Expected: FAIL

**Step 3: Implement**

Add to the `A` class:

```python
@staticmethod
def publish_many(
    *pairs: tuple[str, str],
    mime: str | None = None,
    scope: Literal["session", "user"] = "session",
) -> tuple[ATransform, ...]:
    """Batch publish: multiple (filename, from_key) pairs.

    Usage: Agent("w").artifacts(*A.publish_many(("r.md", "report"), ("d.json", "data")))
    """
    return tuple(
        A.publish(filename, from_key=key, mime=mime, scope=scope)
        for filename, key in pairs
    )

@staticmethod
def snapshot_many(
    *pairs: tuple[str, str],
    scope: Literal["session", "user"] = "session",
) -> tuple[ATransform, ...]:
    """Batch snapshot: multiple (filename, into_key) pairs.

    Usage: Agent("r").artifacts(*A.snapshot_many(("r.md", "text"), ("d.json", "data")))
    """
    return tuple(
        A.snapshot(filename, into_key=key, scope=scope)
        for filename, key in pairs
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestMultiArtifactOps -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
git add src/adk_fluent/_artifacts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add A.publish_many, A.snapshot_many batch operations"
```

______________________________________________________________________

## Phase 3: ArtifactSchema + Contract Integration + Visualization

### Task 6: ArtifactSchema — Produces/Consumes Annotations

Declarative schema using the existing `DeclarativeMetaclass` infrastructure. Two new annotation types: `Produces` (agent creates this artifact) and `Consumes` (agent requires this artifact).

**Files:**

- Create: `src/adk_fluent/_artifact_schema.py`
- Modify: `src/adk_fluent/_schema_base.py` (add new annotations)
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
class TestArtifactSchema:
    """ArtifactSchema with Produces/Consumes annotations."""

    def test_produces_annotation(self):
        from adk_fluent._artifact_schema import Produces

        p = Produces("report.md", mime="text/markdown")
        assert p.filename == "report.md"
        assert p.mime == "text/markdown"
        assert p.scope == "session"

    def test_consumes_annotation(self):
        from adk_fluent._artifact_schema import Consumes

        c = Consumes("data.csv", mime="text/csv")
        assert c.filename == "data.csv"
        assert c.mime == "text/csv"

    def test_schema_definition(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces

        class ResearchArtifacts(ArtifactSchema):
            findings: str = Produces("findings.json", mime="application/json")
            report: str = Produces("report.md", mime="text/markdown")
            source: str = Consumes("raw_data.csv", mime="text/csv")

        assert len(ResearchArtifacts._field_list) == 3

    def test_schema_produces_fields(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces

        class Artifacts(ArtifactSchema):
            report: str = Produces("report.md")
            source: str = Consumes("data.csv")

        produces = Artifacts.produces_fields()
        assert len(produces) == 1
        assert produces[0].filename == "report.md"

    def test_schema_consumes_fields(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces

        class Artifacts(ArtifactSchema):
            report: str = Produces("report.md")
            source: str = Consumes("data.csv")

        consumes = Artifacts.consumes_fields()
        assert len(consumes) == 1
        assert consumes[0].filename == "data.csv"

    def test_schema_produced_filenames(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Produces

        class Artifacts(ArtifactSchema):
            report: str = Produces("report.md")
            config: str = Produces("config.json")

        assert Artifacts.produced_filenames() == frozenset({"report.md", "config.json"})

    def test_schema_consumed_filenames(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes

        class Artifacts(ArtifactSchema):
            source: str = Consumes("data.csv")

        assert Artifacts.consumed_filenames() == frozenset({"data.csv"})
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestArtifactSchema -v`
Expected: FAIL

**Step 3: Implement**

Create `src/adk_fluent/_artifact_schema.py`:

```python
"""ArtifactSchema — declarative artifact contracts.

Defines which artifacts an agent produces and consumes,
enabling build-time contract validation (Pass 16).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adk_fluent._schema_base import DeclarativeField, DeclarativeMetaclass

__all__ = ["ArtifactSchema", "Consumes", "Produces"]


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


class _ArtifactSchemaMeta(DeclarativeMetaclass):
    """Metaclass for ArtifactSchema.

    Extracts Produces/Consumes from class-level annotations and defaults.
    Unlike other schemas that use Annotated[type, Annotation], ArtifactSchema
    uses default values (Produces/Consumes instances) as the annotation source.
    """

    _schema_base_name = "ArtifactSchema"

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        cls = type.__new__(mcs, name, bases, namespace)

        if name == "ArtifactSchema":
            cls._fields = {}
            cls._field_list = ()
            cls._produces = ()
            cls._consumes = ()
            return cls

        # Collect fields from class attributes that are Produces/Consumes
        fields: dict[str, DeclarativeField] = {}
        produces_list: list[Produces] = []
        consumes_list: list[Consumes] = []

        hints = getattr(cls, "__annotations__", {})
        for field_name, hint in hints.items():
            if field_name.startswith("_"):
                continue
            default = namespace.get(field_name)
            annotations: dict[type, Any] = {}
            if isinstance(default, Produces):
                annotations[Produces] = default
                produces_list.append(default)
            elif isinstance(default, Consumes):
                annotations[Consumes] = default
                consumes_list.append(default)

            if annotations:
                fields[field_name] = DeclarativeField(
                    name=field_name,
                    type_=hint if isinstance(hint, type) else str,
                    default=default,
                    annotations=annotations,
                )

        cls._fields = fields
        cls._field_list = tuple(fields.values())
        cls._produces = tuple(produces_list)
        cls._consumes = tuple(consumes_list)
        return cls


class ArtifactSchema(metaclass=_ArtifactSchemaMeta):
    """Declarative artifact contract.

    Usage::

        class ResearchArtifacts(ArtifactSchema):
            findings: str = Produces("findings.json", mime=A.mime.json)
            report: str = Produces("report.md", mime=A.mime.markdown)
            source: str = Consumes("raw_data.csv", mime=A.mime.csv)

        Agent("researcher").artifact_schema(ResearchArtifacts)
    """

    _produces: tuple[Produces, ...]
    _consumes: tuple[Consumes, ...]

    @classmethod
    def produces_fields(cls) -> tuple[Produces, ...]:
        """Return all Produces annotations."""
        return cls._produces

    @classmethod
    def consumes_fields(cls) -> tuple[Consumes, ...]:
        """Return all Consumes annotations."""
        return cls._consumes

    @classmethod
    def produced_filenames(cls) -> frozenset[str]:
        """Return set of artifact filenames this schema produces."""
        return frozenset(p.filename for p in cls._produces)

    @classmethod
    def consumed_filenames(cls) -> frozenset[str]:
        """Return set of artifact filenames this schema consumes."""
        return frozenset(c.filename for c in cls._consumes)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestArtifactSchema -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
git add src/adk_fluent/_artifact_schema.py tests/manual/test_artifacts.py
git commit -m "feat(A): add ArtifactSchema with Produces/Consumes annotations"
```

______________________________________________________________________

### Task 7: Pass 16 — ArtifactSchema Contract Validation

Add a new contract checking pass that validates ArtifactSchema dependencies in sequences: consumed artifacts must have upstream producers, and MIME types must be compatible.

**Files:**

- Modify: `src/adk_fluent/testing/contracts.py`
- Modify: `src/adk_fluent/_ir.py` (add `artifact_schema` field to AgentNode via `scripts/ir_generator.py`)
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
class TestPass16:
    """Pass 16: ArtifactSchema contract validation."""

    def test_schema_consumes_without_producer_is_error(self):
        from adk_fluent import Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes
        from adk_fluent.testing.contracts import check_contracts

        class NeedsData(ArtifactSchema):
            source: str = Consumes("data.csv")

        # Agent consumes data.csv but nothing produces it
        pipeline = Agent("reader").artifact_schema(NeedsData) >> Agent("writer")
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        errors = [i for i in issues if i["level"] == "error" and "data.csv" in i["message"]]
        assert len(errors) >= 1

    def test_schema_consumes_with_producer_is_clean(self):
        from adk_fluent import A, Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes
        from adk_fluent.testing.contracts import check_contracts

        class NeedsData(ArtifactSchema):
            source: str = Consumes("data.csv")

        pipeline = (
            Agent("writer").artifacts(A.save("data.csv", content="a,b"))
            >> Agent("reader").artifact_schema(NeedsData)
        )
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        schema_errors = [i for i in issues if i["level"] == "error" and "data.csv" in i["message"]]
        assert len(schema_errors) == 0

    def test_schema_produces_promotes_artifacts(self):
        from adk_fluent import Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces
        from adk_fluent.testing.contracts import check_contracts

        class ProducerSchema(ArtifactSchema):
            report: str = Produces("report.md")

        class ConsumerSchema(ArtifactSchema):
            source: str = Consumes("report.md")

        pipeline = (
            Agent("writer").artifact_schema(ProducerSchema)
            >> Agent("reader").artifact_schema(ConsumerSchema)
        )
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        schema_errors = [i for i in issues if i["level"] == "error" and "report.md" in i["message"]]
        assert len(schema_errors) == 0

    def test_schema_mime_mismatch_is_warning(self):
        from adk_fluent import Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces
        from adk_fluent.testing.contracts import check_contracts

        class ProducerSchema(ArtifactSchema):
            report: str = Produces("report.md", mime="text/markdown")

        class ConsumerSchema(ArtifactSchema):
            source: str = Consumes("report.md", mime="application/json")

        pipeline = (
            Agent("writer").artifact_schema(ProducerSchema)
            >> Agent("reader").artifact_schema(ConsumerSchema)
        )
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        warnings = [i for i in issues if i["level"] == "warning" and "MIME" in i["message"]]
        assert len(warnings) >= 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestPass16 -v`
Expected: FAIL

**Step 3: Implement**

First, add `artifact_schema` field to AgentNode. Open `scripts/ir_generator.py` and add to the AgentNode extension block (the `if ir_name == "AgentNode":` section):

```python
"artifact_schema": "type | None",
```

Then regenerate: `just generate`

Next, add the `.artifact_schema()` builder method to `seeds/seed.manual.toml`:

```toml
[[builders.Agent.extras]]
name = "artifact_schema"
signature = "(self, schema: type) -> Self"
doc = "Attach an ArtifactSchema declaring artifact dependencies."
behavior = "field_set"
target_field = "_artifact_schema"
example = '''Agent("researcher").artifact_schema(ResearchArtifacts)'''
see_also = ["ArtifactSchema", "Produces", "Consumes"]
```

Then regenerate again: `just seed && just generate`

Now add Pass 16 to `src/adk_fluent/testing/contracts.py`, after Pass 15:

```python
    # =================================================================
    # Pass 16: ArtifactSchema dependency validation
    # =================================================================

    artifact_mime_map: dict[str, str | None] = {}  # filename → mime

    for idx, child in enumerate(children):
        child_name = getattr(child, "name", "?")

        # Track MIME from ArtifactNode produces
        if isinstance(child, ArtifactNode):
            for artifact_name in child.produces_artifact:
                artifact_mime_map[artifact_name] = child.mime

        # Check ArtifactSchema on AgentNodes
        schema = getattr(child, "artifact_schema", None)
        if schema is None:
            continue

        # Check consumed artifacts are available
        for consumed in schema.consumes_fields():
            if consumed.filename not in artifacts_available:
                issues.append(
                    {
                        "level": "error",
                        "agent": _scoped(child_name),
                        "message": (
                            f"ArtifactSchema consumes '{consumed.filename}' "
                            f"but not produced upstream"
                        ),
                    }
                )

            # MIME compatibility check
            producer_mime = artifact_mime_map.get(consumed.filename)
            if producer_mime and consumed.mime and producer_mime != consumed.mime:
                issues.append(
                    {
                        "level": "warning",
                        "agent": _scoped(child_name),
                        "message": (
                            f"MIME mismatch: '{consumed.filename}' produced as "
                            f"{producer_mime}, consumed as {consumed.mime}"
                        ),
                    }
                )

        # Promote produced artifacts from schema
        for produced in schema.produces_fields():
            artifacts_available.add(produced.filename)
            artifact_mime_map[produced.filename] = produced.mime
```

Update the pass count in the docstring from "15 total" to "16 total".

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestPass16 -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
just generate
git add src/adk_fluent/testing/contracts.py src/adk_fluent/_ir_generated.py \
    seeds/seed.manual.toml src/adk_fluent/agent.py src/adk_fluent/agent.pyi \
    scripts/ir_generator.py tests/manual/test_artifacts.py
git commit -m "feat(A): add Pass 16 ArtifactSchema contract validation"
```

______________________________________________________________________

### Task 8: Visualization Integration — Artifact Edges

Add ArtifactNode rendering and artifact flow edges to `viz.py`. Artifact nodes get a distinctive shape; artifact flow uses dashed edges with `artifact:` prefix labels.

**Files:**

- Modify: `src/adk_fluent/viz.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
class TestVisualization:
    """Artifact edges in Mermaid visualization."""

    def test_artifact_node_rendered(self):
        from adk_fluent import A, Agent
        from adk_fluent.viz import ir_to_mermaid

        pipeline = Agent("writer") >> A.publish("report.md", from_key="output") >> Agent("reader")
        ir = pipeline.to_ir()
        mermaid = ir_to_mermaid(ir)
        assert "publish_report_md" in mermaid or "report" in mermaid.lower()

    def test_artifact_node_shape(self):
        """ArtifactNode should have a distinct shape (hexagon or stadium)."""
        from adk_fluent import A, Agent
        from adk_fluent.viz import ir_to_mermaid

        pipeline = Agent("writer") >> A.publish("report.md", from_key="output")
        ir = pipeline.to_ir()
        mermaid = ir_to_mermaid(ir)
        # Should use a distinctive shape, like hexagon {{...}} or stadium ([...])
        assert "artifact" in mermaid.lower() or "publish" in mermaid.lower()

    def test_artifact_data_flow_edges(self):
        """Artifact produces/consumes should generate data flow edges."""
        from adk_fluent import A, Agent
        from adk_fluent.viz import ir_to_mermaid

        pipeline = (
            Agent("writer").writes("output")
            >> A.publish("report.md", from_key="output")
            >> A.snapshot("report.md", into_key="text")
            >> Agent("reader")
        )
        ir = pipeline.to_ir()
        mermaid = ir_to_mermaid(ir, show_data_flow=True)
        # Should show artifact flow edges
        assert "report.md" in mermaid
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestVisualization -v`
Expected: FAIL (ArtifactNode not handled in viz.py, falls through to default)

**Step 3: Implement**

In `src/adk_fluent/viz.py`, add ArtifactNode import and handling.

After the `from adk_fluent._ir import (` block (line 53), add:

```python
from adk_fluent._ir import ArtifactNode
```

(Or add `ArtifactNode` to the existing import list.)

In the `_walk` function, add an `elif` for ArtifactNode before the `else` fallback (before line 114):

```python
        elif isinstance(n, ArtifactNode):
            op = getattr(n, "op", "?")
            fname = getattr(n, "filename", "?")
            label = f"{op} ({fname})" if fname else op
            # Hexagon shape for artifact nodes
            lines.append(f'    {nid}{{{{"{_sanitize(label)} artifact"}}}}')
```

In the data flow tracking section (after line 159, the reads_keys tracking), add artifact flow tracking:

```python
            # Artifact flow tracking
            if isinstance(n, ArtifactNode):
                for afn in getattr(n, "produces_artifact", frozenset()):
                    _producers.setdefault(f"artifact:{afn}", []).append(nid)
                for afn in getattr(n, "consumes_artifact", frozenset()):
                    _consumers.setdefault(f"artifact:{afn}", []).append(nid)
                # State keys produced/consumed by artifact ops
                for sk in getattr(n, "produces_state", frozenset()):
                    _producers.setdefault(sk, []).append(nid)
                for sk in getattr(n, "consumes_state", frozenset()):
                    _consumers.setdefault(sk, []).append(nid)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestVisualization -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
git add src/adk_fluent/viz.py tests/manual/test_artifacts.py
git commit -m "feat(A): add artifact node rendering and flow edges to visualization"
```

______________________________________________________________________

### Task 9: Exports + Prelude + Prelude Test Update

Add `ArtifactSchema`, `Produces`, `Consumes` to prelude. Update the prelude test.

**Files:**

- Modify: `src/adk_fluent/prelude.py`
- Modify: `tests/manual/test_api_surface_v2.py`
- Regenerate: `src/adk_fluent/__init__.py` (via `just generate`)
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
class TestPhase2Exports:
    """Phase 2+3 exports are importable."""

    def test_artifact_schema_importable(self):
        from adk_fluent.prelude import ArtifactSchema

        assert ArtifactSchema is not None

    def test_produces_importable(self):
        from adk_fluent.prelude import Produces

        assert Produces is not None

    def test_consumes_importable(self):
        from adk_fluent.prelude import Consumes

        assert Consumes is not None

    def test_for_llm_on_a(self):
        from adk_fluent import A

        assert hasattr(A, "for_llm")

    def test_tool_on_a(self):
        from adk_fluent import A

        assert hasattr(A, "tool")

    def test_content_transforms_on_a(self):
        from adk_fluent import A

        assert hasattr(A, "as_json")
        assert hasattr(A, "as_csv")
        assert hasattr(A, "as_text")
        assert hasattr(A, "from_json")
        assert hasattr(A, "from_csv")
        assert hasattr(A, "from_markdown")

    def test_batch_ops_on_a(self):
        from adk_fluent import A

        assert hasattr(A, "publish_many")
        assert hasattr(A, "snapshot_many")
```

**Step 2: Update prelude.py**

Add to `src/adk_fluent/prelude.py`:

```python
from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces
```

Add to `__all__`:

```python
    # Tier 8: Schemas
    "MiddlewareSchema",
    "ArtifactSchema",
    "Produces",
    "Consumes",
```

**Step 3: Update prelude test in `tests/manual/test_api_surface_v2.py`**

In `TestPrelude.test_prelude_all_contents`, add to the `expected` set:

```python
"ArtifactSchema",
"Produces",
"Consumes",
```

Update `test_prelude_all_count` from `41` to `44`.

**Step 4: Regenerate and run tests**

```bash
just generate
uv run pytest tests/manual/test_artifacts.py::TestPhase2Exports tests/manual/test_api_surface_v2.py::TestPrelude -v
```

Expected: PASS

**Step 5: Commit**

```bash
ruff check --fix . && ruff format .
just check-gen
git add src/adk_fluent/prelude.py src/adk_fluent/__init__.py \
    tests/manual/test_artifacts.py tests/manual/test_api_surface_v2.py
git commit -m "feat(A): export ArtifactSchema, Produces, Consumes in prelude"
```

______________________________________________________________________

### Task 10: End-to-End Integration Tests

Comprehensive integration tests covering Phase 2+3 features working together.

**Files:**

- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the tests**

```python
class TestPhase2E2E:
    """End-to-end integration tests for Phase 2+3."""

    def test_snapshot_then_as_json_pipeline(self):
        """A.snapshot >> A.as_json composes in a pipeline."""
        from adk_fluent import A, Agent

        pipeline = (
            Agent("writer")
            >> A.snapshot("data.json", into_key="data")
            >> A.as_json("data")
            >> Agent("processor")
        )
        ir = pipeline.to_ir()
        from adk_fluent._ir_generated import SequenceNode

        assert isinstance(ir, SequenceNode)

    def test_from_json_then_publish_pipeline(self):
        """A.from_json >> A.publish composes in a pipeline."""
        from adk_fluent import A, Agent

        pipeline = (
            Agent("processor")
            >> A.from_json("config")
            >> A.publish("config.json", from_key="config")
        )
        ir = pipeline.to_ir()
        from adk_fluent._ir_generated import SequenceNode

        assert isinstance(ir, SequenceNode)

    def test_full_roundtrip_pipeline(self):
        """Full pipeline: agent >> snapshot >> transform >> agent >> serialize >> publish."""
        from adk_fluent import A, Agent

        pipeline = (
            Agent("loader")
            >> A.snapshot("data.csv", into_key="rows")
            >> A.as_csv("rows")
            >> Agent("processor")
            >> A.from_json("result")
            >> A.publish("result.json", from_key="result")
        )
        ir = pipeline.to_ir()
        assert ir is not None

    def test_schema_with_tools_and_transforms(self):
        """Agent with artifact_schema, tools, and pipeline transforms all compose."""
        from adk_fluent import A, Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces

        class WorkerArtifacts(ArtifactSchema):
            result: str = Produces("result.json", mime="application/json")
            source: str = Consumes("input.csv", mime="text/csv")

        pipeline = (
            Agent("loader").artifacts(A.save("input.csv", content="a,b\n1,2"))
            >> Agent("worker")
            .artifact_schema(WorkerArtifacts)
            .tools(A.tool.load("read_input"), A.tool.save("save_result", allowed=["result.json"]))
        )
        built = pipeline.build()
        assert built is not None

    def test_contract_checking_full_pipeline(self):
        """Contract checker validates both Pass 15 and Pass 16 in same pipeline."""
        from adk_fluent import A, Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces
        from adk_fluent.testing.contracts import check_contracts

        class ProducerSchema(ArtifactSchema):
            report: str = Produces("report.md")

        class ConsumerSchema(ArtifactSchema):
            source: str = Consumes("report.md")

        pipeline = (
            Agent("writer").artifact_schema(ProducerSchema)
            >> A.publish("report.md", from_key="output")
            >> Agent("reader").artifact_schema(ConsumerSchema)
            >> A.snapshot("report.md", into_key="text")
            >> Agent("final")
        )
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        # No artifact-related errors (Pass 15 handles A.publish/snapshot, Pass 16 handles schemas)
        artifact_errors = [i for i in issues if i["level"] == "error" and "artifact" in i["message"].lower()]
        assert len(artifact_errors) == 0
```

**Step 2: Run tests**

Run: `uv run pytest tests/manual/test_artifacts.py::TestPhase2E2E -v`
Expected: PASS (5 tests)

**Step 3: Full CI verification**

```bash
ruff check --fix . && ruff format .
just typecheck-core
just preflight
just check-gen
uv run pytest tests/ -x --tb=short -q
```

**Step 4: Commit**

```bash
git add tests/manual/test_artifacts.py
git commit -m "test(A): add Phase 2+3 end-to-end integration tests"
```

______________________________________________________________________

## Summary

| Task      | Phase | What it adds                             | New tests         |
| --------- | ----- | ---------------------------------------- | ----------------- |
| 1         | 2     | A.as_json, A.as_csv, A.as_text           | 7                 |
| 2         | 2     | A.from_json, A.from_csv, A.from_markdown | 5                 |
| 3         | 2     | A.for_llm (CTransform)                   | 7                 |
| 4         | 2     | A.tool.save/load/list/version            | 6                 |
| 5         | 2     | A.publish_many, A.snapshot_many          | 7                 |
| 6         | 3     | ArtifactSchema, Produces, Consumes       | 7                 |
| 7         | 3     | Pass 16 contract validation              | 4                 |
| 8         | 3     | Artifact edges in viz.py                 | 3                 |
| 9         | 3     | Prelude exports                          | 7                 |
| 10        | 3     | End-to-end integration                   | 5                 |
| **Total** |       |                                          | **~58 new tests** |
