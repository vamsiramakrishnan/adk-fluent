# A Module (Phase 1) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the A (Artifacts) module Phase 1 — core factories, MIME safety, ATransform, ArtifactAgent, ArtifactNode, pipeline integration, builder method, and contract checking Pass 15.

**Architecture:** A is a hand-written module (`_artifacts.py`) following the same pattern as S (`_transforms.py`). Factories return `ATransform` descriptors that carry `_artifact_op` attributes. `_fn_step()` detects this and creates `_ArtifactBuilder`, which builds to `ArtifactAgent` at runtime and `ArtifactNode` in IR. Pass 15 validates artifact availability.

**Tech Stack:** Python 3.11+, dataclasses, google-adk artifact service API (`BaseArtifactService`, `types.Part`), existing adk-fluent IR/contract infrastructure.

**Design doc:** `docs/plans/2026-03-01-a-module-design.md`

---

### Task 1: A.mime — MIME Type Constants and Classifiers

**Files:**
- Create: `src/adk_fluent/_artifacts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
# tests/manual/test_artifacts.py
"""Tests for A module — artifact composition."""

from __future__ import annotations


class TestMimeConstants:
    def test_text_constants(self):
        from adk_fluent._artifacts import A

        assert A.mime.text == "text/plain"
        assert A.mime.markdown == "text/markdown"
        assert A.mime.html == "text/html"
        assert A.mime.csv == "text/csv"
        assert A.mime.json == "application/json"
        assert A.mime.xml == "application/xml"
        assert A.mime.yaml == "application/yaml"

    def test_media_constants(self):
        from adk_fluent._artifacts import A

        assert A.mime.pdf == "application/pdf"
        assert A.mime.png == "image/png"
        assert A.mime.jpeg == "image/jpeg"
        assert A.mime.gif == "image/gif"
        assert A.mime.webp == "image/webp"
        assert A.mime.svg == "image/svg+xml"
        assert A.mime.mp3 == "audio/mpeg"
        assert A.mime.wav == "audio/wav"
        assert A.mime.mp4 == "video/mp4"
        assert A.mime.binary == "application/octet-stream"

    def test_detect_from_filename(self):
        from adk_fluent._artifacts import A

        assert A.mime.detect("report.md") == "text/markdown"
        assert A.mime.detect("data.json") == "application/json"
        assert A.mime.detect("chart.png") == "image/png"
        assert A.mime.detect("unknown.xyz") == "application/octet-stream"
        assert A.mime.detect("report.pdf") == "application/pdf"

    def test_is_llm_inline(self):
        from adk_fluent._artifacts import A

        assert A.mime.is_llm_inline("image/png") is True
        assert A.mime.is_llm_inline("audio/wav") is True
        assert A.mime.is_llm_inline("video/mp4") is True
        assert A.mime.is_llm_inline("application/pdf") is True
        assert A.mime.is_llm_inline("text/plain") is False
        assert A.mime.is_llm_inline("application/json") is False

    def test_is_text_like(self):
        from adk_fluent._artifacts import A

        assert A.mime.is_text_like("text/plain") is True
        assert A.mime.is_text_like("text/markdown") is True
        assert A.mime.is_text_like("application/json") is True
        assert A.mime.is_text_like("application/csv") is True
        assert A.mime.is_text_like("application/xml") is True
        assert A.mime.is_text_like("image/png") is False
        assert A.mime.is_text_like("application/octet-stream") is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py -x --tb=short -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'adk_fluent._artifacts'`

**Step 3: Implement A.mime**

```python
# src/adk_fluent/_artifacts.py
"""A module — fluent artifact composition.

Bridges the state and artifact planes with explicit, honest semantics.
See docs/plans/2026-03-01-a-module-design.md for architectural rationale.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

__all__ = ["A", "ATransform"]

# Gemini-supported inline MIME prefixes (from LoadArtifactsTool)
_LLM_INLINE_PREFIXES = ("image/", "audio/", "video/")
_LLM_INLINE_TYPES = frozenset({"application/pdf"})
_TEXT_LIKE_TYPES = frozenset({
    "application/csv",
    "application/json",
    "application/xml",
    "application/yaml",
})


class _MimeConstants:
    """MIME type constants. Prevents typos that cause permanent misclassification."""

    # Text family
    text = "text/plain"
    markdown = "text/markdown"
    html = "text/html"
    csv = "text/csv"
    json = "application/json"
    xml = "application/xml"
    yaml = "application/yaml"

    # Document
    pdf = "application/pdf"

    # Image
    png = "image/png"
    jpeg = "image/jpeg"
    gif = "image/gif"
    webp = "image/webp"
    svg = "image/svg+xml"

    # Audio
    mp3 = "audio/mpeg"
    wav = "audio/wav"
    ogg = "audio/ogg"

    # Video
    mp4 = "video/mp4"
    webm = "video/webm"

    # Fallback
    binary = "application/octet-stream"

    @staticmethod
    def detect(filename: str) -> str:
        """Auto-detect MIME type from filename extension."""
        guessed, _ = mimetypes.guess_type(filename)
        return guessed or "application/octet-stream"

    @staticmethod
    def is_llm_inline(mime: str) -> bool:
        """Can Gemini consume this MIME type directly as inline content?"""
        normalized = mime.split(";", 1)[0].strip()
        return normalized.startswith(_LLM_INLINE_PREFIXES) or normalized in _LLM_INLINE_TYPES

    @staticmethod
    def is_text_like(mime: str) -> bool:
        """Can this be safely decoded as UTF-8 text?"""
        normalized = mime.split(";", 1)[0].strip()
        return normalized.startswith("text/") or normalized in _TEXT_LIKE_TYPES


class A:
    """Artifact operations — bridge between state and artifact service.

    Four verbs for four semantics:
    - publish: state → artifact (bridge, copy out)
    - snapshot: artifact → state (bridge, copy in)
    - save: content → artifact (direct, no state bridge)
    - load: artifact → pipeline (direct, no state bridge)
    """

    mime = _MimeConstants()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py -x --tb=short -q`
Expected: PASS (all 5 tests)

**Step 5: Lint**

Run: `ruff check --fix src/adk_fluent/_artifacts.py && ruff format src/adk_fluent/_artifacts.py`

**Step 6: Commit**

```bash
git add src/adk_fluent/_artifacts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add A.mime constants and classifiers"
```

---

### Task 2: ATransform Descriptor

**Files:**
- Modify: `src/adk_fluent/_artifacts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
# Append to tests/manual/test_artifacts.py

class TestATransform:
    def test_atransform_is_callable(self):
        from adk_fluent._artifacts import ATransform

        at = ATransform(
            _fn=lambda state: None,
            _op="publish",
            _bridges_state=True,
            _filename="report.md",
            _from_key="report",
            _into_key=None,
            _mime="text/markdown",
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset({"report.md"}),
            _consumes_artifact=frozenset(),
            _produces_state=frozenset(),
            _consumes_state=frozenset({"report"}),
            _name="publish_report",
        )
        assert callable(at)
        # Calling it returns None (no-op marker)
        assert at({"report": "text"}) is None

    def test_atransform_has_artifact_op_attr(self):
        from adk_fluent._artifacts import ATransform

        at = ATransform(
            _fn=lambda state: None,
            _op="snapshot",
            _bridges_state=True,
            _filename="report.md",
            _from_key=None,
            _into_key="text",
            _mime=None,
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset(),
            _consumes_artifact=frozenset({"report.md"}),
            _produces_state=frozenset({"text"}),
            _consumes_state=frozenset(),
            _name="snapshot_report",
        )
        # _fn_step() will look for this attribute
        assert at._artifact_op == "snapshot"

    def test_atransform_bridges_state_flag(self):
        from adk_fluent._artifacts import ATransform

        bridge = ATransform(
            _fn=lambda s: None, _op="publish", _bridges_state=True,
            _filename="f", _from_key="k", _into_key=None, _mime=None,
            _scope="session", _version=None, _metadata=None, _content=None,
            _decode=False, _produces_artifact=frozenset({"f"}),
            _consumes_artifact=frozenset(), _produces_state=frozenset(),
            _consumes_state=frozenset({"k"}), _name="t",
        )
        direct = ATransform(
            _fn=lambda s: None, _op="save", _bridges_state=False,
            _filename="f", _from_key=None, _into_key=None, _mime=None,
            _scope="session", _version=None, _metadata=None, _content="hi",
            _decode=False, _produces_artifact=frozenset({"f"}),
            _consumes_artifact=frozenset(), _produces_state=frozenset(),
            _consumes_state=frozenset(), _name="t",
        )
        assert bridge._bridges_state is True
        assert direct._bridges_state is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestATransform -x --tb=short -q`
Expected: FAIL — `ImportError: cannot import name 'ATransform'`

**Step 3: Implement ATransform**

Add to `src/adk_fluent/_artifacts.py` after the `_MimeConstants` class:

```python
@dataclass(frozen=True, slots=True)
class ATransform:
    """Composable artifact operation descriptor.

    Carries metadata for both artifact flow and state flow.
    _bridges_state is True only for publish/snapshot — operations that
    cross the state/artifact boundary.
    """

    _fn: Callable
    _op: Literal["publish", "snapshot", "save", "load", "list", "version", "delete"]
    _bridges_state: bool
    _filename: str | None
    _from_key: str | None
    _into_key: str | None
    _mime: str | None
    _scope: Literal["session", "user"]
    _version: int | None
    _metadata: dict[str, Any] | None
    _content: str | bytes | None
    _decode: bool
    _produces_artifact: frozenset[str]
    _consumes_artifact: frozenset[str]
    _produces_state: frozenset[str]
    _consumes_state: frozenset[str]
    _name: str

    def __call__(self, state: dict) -> None:
        """No-op marker. Real work happens in ArtifactAgent at runtime."""
        return None

    @property
    def _artifact_op(self) -> str:
        """Signal for _fn_step() detection."""
        return self._op

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return self._name
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestATransform -x --tb=short -q`
Expected: PASS (all 3 tests)

**Step 5: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_artifacts.py && ruff format src/adk_fluent/_artifacts.py
git add src/adk_fluent/_artifacts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add ATransform descriptor dataclass"
```

---

### Task 3: Core Factory Methods (publish, snapshot, save, load, list, version, delete, when)

**Files:**
- Modify: `src/adk_fluent/_artifacts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
# Append to tests/manual/test_artifacts.py

class TestPublish:
    def test_publish_from_state_key(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.publish("report.md", from_key="report")
        assert isinstance(at, ATransform)
        assert at._op == "publish"
        assert at._bridges_state is True
        assert at._filename == "report.md"
        assert at._from_key == "report"
        assert at._consumes_state == frozenset({"report"})
        assert at._produces_artifact == frozenset({"report.md"})

    def test_publish_auto_detects_mime(self):
        from adk_fluent._artifacts import A

        at = A.publish("report.md", from_key="report")
        assert at._mime == "text/markdown"

    def test_publish_explicit_mime(self):
        from adk_fluent._artifacts import A

        at = A.publish("chart.png", from_key="data", mime=A.mime.png)
        assert at._mime == "image/png"

    def test_publish_with_metadata(self):
        from adk_fluent._artifacts import A

        at = A.publish("report.md", from_key="report", metadata={"author": "bot"})
        assert at._metadata == {"author": "bot"}

    def test_publish_user_scope(self):
        from adk_fluent._artifacts import A

        at = A.publish("shared.md", from_key="report", scope="user")
        assert at._scope == "user"


class TestSnapshot:
    def test_snapshot_into_state_key(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.snapshot("report.md", into_key="text")
        assert isinstance(at, ATransform)
        assert at._op == "snapshot"
        assert at._bridges_state is True
        assert at._filename == "report.md"
        assert at._into_key == "text"
        assert at._consumes_artifact == frozenset({"report.md"})
        assert at._produces_state == frozenset({"text"})

    def test_snapshot_specific_version(self):
        from adk_fluent._artifacts import A

        at = A.snapshot("report.md", into_key="text", version=2)
        assert at._version == 2

    def test_snapshot_decode_flag(self):
        from adk_fluent._artifacts import A

        at = A.snapshot("data.csv", into_key="rows", decode=True)
        assert at._decode is True


class TestSave:
    def test_save_literal_content(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.save("report.md", content="# Hello")
        assert isinstance(at, ATransform)
        assert at._op == "save"
        assert at._bridges_state is False
        assert at._content == "# Hello"
        assert at._consumes_state == frozenset()
        assert at._produces_artifact == frozenset({"report.md"})

    def test_save_no_from_key(self):
        from adk_fluent._artifacts import A

        at = A.save("report.md", content="text")
        assert at._from_key is None


class TestLoad:
    def test_load_returns_atransform(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.load("report.md")
        assert isinstance(at, ATransform)
        assert at._op == "load"
        assert at._bridges_state is False
        assert at._into_key is None
        assert at._produces_state == frozenset()


class TestListVersionDelete:
    def test_list_into_key(self):
        from adk_fluent._artifacts import A

        at = A.list(into_key="artifacts")
        assert at._op == "list"
        assert at._into_key == "artifacts"
        assert at._produces_state == frozenset({"artifacts"})

    def test_version_into_key(self):
        from adk_fluent._artifacts import A

        at = A.version("report.md", into_key="meta")
        assert at._op == "version"
        assert at._filename == "report.md"
        assert at._into_key == "meta"

    def test_delete(self):
        from adk_fluent._artifacts import A

        at = A.delete("report.md")
        assert at._op == "delete"
        assert at._filename == "report.md"
        assert at._produces_state == frozenset()
        assert at._consumes_state == frozenset()


class TestWhen:
    def test_when_wraps_atransform(self):
        from adk_fluent._artifacts import A, ATransform

        inner = A.publish("report.md", from_key="report")
        at = A.when("has_report", inner)
        assert isinstance(at, ATransform)
        assert at._op == "publish"
        # when() should preserve inner's metadata
        assert at._filename == "report.md"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py -k "TestPublish or TestSnapshot or TestSave or TestLoad or TestListVersionDelete or TestWhen" -x --tb=short -q`
Expected: FAIL — `AttributeError: type object 'A' has no attribute 'publish'`

**Step 3: Implement factory methods on class A**

Add static methods to the `A` class in `src/adk_fluent/_artifacts.py`:

```python
    # Add these as static methods inside class A:

    @staticmethod
    def publish(
        filename: str,
        *,
        from_key: str,
        mime: str | None = None,
        metadata: dict[str, Any] | None = None,
        scope: Literal["session", "user"] = "session",
    ) -> ATransform:
        """Publish state content to artifact service.

        STATE BRIDGE: reads state[from_key], copies to versioned artifact.
        """
        resolved_mime = mime or _MimeConstants.detect(filename)
        return ATransform(
            _fn=lambda state: None,
            _op="publish",
            _bridges_state=True,
            _filename=filename,
            _from_key=from_key,
            _into_key=None,
            _mime=resolved_mime,
            _scope=scope,
            _version=None,
            _metadata=metadata,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset({filename}),
            _consumes_artifact=frozenset(),
            _produces_state=frozenset(),
            _consumes_state=frozenset({from_key}),
            _name=f"publish_{filename.replace('.', '_')}",
        )

    @staticmethod
    def snapshot(
        filename: str,
        *,
        into_key: str,
        version: int | None = None,
        decode: bool = False,
        scope: Literal["session", "user"] = "session",
    ) -> ATransform:
        """Snapshot artifact content into state.

        STATE BRIDGE: loads artifact, copies point-in-time content into state[into_key].
        """
        return ATransform(
            _fn=lambda state: None,
            _op="snapshot",
            _bridges_state=True,
            _filename=filename,
            _from_key=None,
            _into_key=into_key,
            _mime=None,
            _scope=scope,
            _version=version,
            _metadata=None,
            _content=None,
            _decode=decode,
            _produces_artifact=frozenset(),
            _consumes_artifact=frozenset({filename}),
            _produces_state=frozenset({into_key}),
            _consumes_state=frozenset(),
            _name=f"snapshot_{filename.replace('.', '_')}",
        )

    @staticmethod
    def save(
        filename: str,
        *,
        content: str | bytes,
        mime: str | None = None,
        metadata: dict[str, Any] | None = None,
        scope: Literal["session", "user"] = "session",
    ) -> ATransform:
        """Save literal content to artifact service. No state bridge."""
        resolved_mime = mime or _MimeConstants.detect(filename)
        return ATransform(
            _fn=lambda state: None,
            _op="save",
            _bridges_state=False,
            _filename=filename,
            _from_key=None,
            _into_key=None,
            _mime=resolved_mime,
            _scope=scope,
            _version=None,
            _metadata=metadata,
            _content=content,
            _decode=False,
            _produces_artifact=frozenset({filename}),
            _consumes_artifact=frozenset(),
            _produces_state=frozenset(),
            _consumes_state=frozenset(),
            _name=f"save_{filename.replace('.', '_')}",
        )

    @staticmethod
    def load(
        filename: str,
        *,
        scope: Literal["session", "user"] = "session",
    ) -> ATransform:
        """Load artifact for pipeline composition. No state bridge."""
        return ATransform(
            _fn=lambda state: None,
            _op="load",
            _bridges_state=False,
            _filename=filename,
            _from_key=None,
            _into_key=None,
            _mime=None,
            _scope=scope,
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset(),
            _consumes_artifact=frozenset({filename}),
            _produces_state=frozenset(),
            _consumes_state=frozenset(),
            _name=f"load_{filename.replace('.', '_')}",
        )

    @staticmethod
    def list(*, into_key: str) -> ATransform:
        """List artifact filenames into state. Lightweight metadata only."""
        return ATransform(
            _fn=lambda state: None,
            _op="list",
            _bridges_state=False,
            _filename=None,
            _from_key=None,
            _into_key=into_key,
            _mime=None,
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset(),
            _consumes_artifact=frozenset(),
            _produces_state=frozenset({into_key}),
            _consumes_state=frozenset(),
            _name="list_artifacts",
        )

    @staticmethod
    def version(
        filename: str,
        *,
        into_key: str,
    ) -> ATransform:
        """Get artifact version metadata into state. Lightweight metadata only."""
        return ATransform(
            _fn=lambda state: None,
            _op="version",
            _bridges_state=False,
            _filename=filename,
            _from_key=None,
            _into_key=into_key,
            _mime=None,
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset(),
            _consumes_artifact=frozenset({filename}),
            _produces_state=frozenset({into_key}),
            _consumes_state=frozenset(),
            _name=f"version_{filename.replace('.', '_')}",
        )

    @staticmethod
    def delete(filename: str) -> ATransform:
        """Delete all versions of an artifact. No state involvement."""
        return ATransform(
            _fn=lambda state: None,
            _op="delete",
            _bridges_state=False,
            _filename=filename,
            _from_key=None,
            _into_key=None,
            _mime=None,
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset(),
            _consumes_artifact=frozenset(),
            _produces_state=frozenset(),
            _consumes_state=frozenset(),
            _name=f"delete_{filename.replace('.', '_')}",
        )

    @staticmethod
    def when(predicate: str | Callable, transform: ATransform) -> ATransform:
        """Conditional artifact operation. Uniform with S.when(), C.when(), etc."""
        if isinstance(predicate, str):
            key = predicate
            pred_fn = lambda state: bool(state.get(key))  # noqa: E731
        else:
            pred_fn = predicate

        def _conditional(state: dict) -> None:
            if pred_fn(state):
                return transform._fn(state)
            return None

        return ATransform(
            _fn=_conditional,
            _op=transform._op,
            _bridges_state=transform._bridges_state,
            _filename=transform._filename,
            _from_key=transform._from_key,
            _into_key=transform._into_key,
            _mime=transform._mime,
            _scope=transform._scope,
            _version=transform._version,
            _metadata=transform._metadata,
            _content=transform._content,
            _decode=transform._decode,
            _produces_artifact=transform._produces_artifact,
            _consumes_artifact=transform._consumes_artifact,
            _produces_state=transform._produces_state,
            _consumes_state=transform._consumes_state,
            _name=f"when_{transform._name}",
        )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py -x --tb=short -q`
Expected: PASS (all tests)

**Step 5: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_artifacts.py && ruff format src/adk_fluent/_artifacts.py
git add src/adk_fluent/_artifacts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add core factories — publish, snapshot, save, load, list, version, delete, when"
```

---

### Task 4: ArtifactNode IR + _ArtifactBuilder + _fn_step Detection

**Files:**
- Modify: `src/adk_fluent/_ir.py` (add ArtifactNode)
- Modify: `src/adk_fluent/_primitive_builders.py` (add _ArtifactBuilder, extend _fn_step)
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
# Append to tests/manual/test_artifacts.py

class TestArtifactNode:
    def test_artifact_node_creation(self):
        from adk_fluent._ir import ArtifactNode

        node = ArtifactNode(
            name="publish_report",
            op="publish",
            bridges_state=True,
            filename="report.md",
            from_key="report",
            into_key=None,
            mime="text/markdown",
            scope="session",
            version=None,
            produces_artifact=frozenset({"report.md"}),
            consumes_artifact=frozenset(),
            produces_state=frozenset(),
            consumes_state=frozenset({"report"}),
        )
        assert node.name == "publish_report"
        assert node.bridges_state is True


class TestFnStepDetection:
    def test_fn_step_detects_artifact_op(self):
        from adk_fluent._artifacts import A
        from adk_fluent._primitive_builders import _fn_step, _ArtifactBuilder

        at = A.publish("report.md", from_key="report")
        builder = _fn_step(at)
        assert isinstance(builder, _ArtifactBuilder)

    def test_fn_step_artifact_builder_to_ir(self):
        from adk_fluent._artifacts import A
        from adk_fluent._ir import ArtifactNode
        from adk_fluent._primitive_builders import _fn_step

        at = A.publish("report.md", from_key="report")
        builder = _fn_step(at)
        ir_node = builder.to_ir()
        assert isinstance(ir_node, ArtifactNode)
        assert ir_node.op == "publish"
        assert ir_node.filename == "report.md"
        assert ir_node.produces_artifact == frozenset({"report.md"})
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestArtifactNode -x --tb=short -q`
Expected: FAIL — `ImportError: cannot import name 'ArtifactNode'`

**Step 3: Add ArtifactNode to _ir.py**

Add after `CaptureNode` in `src/adk_fluent/_ir.py`:

```python
@dataclass(frozen=True)
class ArtifactNode:
    """Artifact operation in the IR."""

    name: str
    op: Literal["publish", "snapshot", "save", "load", "list", "version", "delete"]
    bridges_state: bool
    filename: str | None
    from_key: str | None
    into_key: str | None
    mime: str | None
    scope: Literal["session", "user"]
    version: int | None
    produces_artifact: frozenset[str]
    consumes_artifact: frozenset[str]
    produces_state: frozenset[str]
    consumes_state: frozenset[str]
```

Add `Literal` to the imports if not already present.

**Step 4: Add _ArtifactBuilder and extend _fn_step in _primitive_builders.py**

Add `_ArtifactBuilder` class after `_CaptureBuilder`:

```python
class _ArtifactBuilder(PrimitiveBuilderBase):
    """Builder for artifact operations. Created by _fn_step() when it detects _artifact_op."""

    _CUSTOM_ATTRS = ("_atransform",)

    def build(self):
        from adk_fluent._primitives import ArtifactAgent

        return ArtifactAgent(name=self._config["name"], atransform=self._atransform)

    def to_ir(self):
        from adk_fluent._ir import ArtifactNode

        at = self._atransform
        return ArtifactNode(
            name=self._config.get("name", at._name),
            op=at._op,
            bridges_state=at._bridges_state,
            filename=at._filename,
            from_key=at._from_key,
            into_key=at._into_key,
            mime=at._mime,
            scope=at._scope,
            version=at._version,
            produces_artifact=at._produces_artifact,
            consumes_artifact=at._consumes_artifact,
            produces_state=at._produces_state,
            consumes_state=at._consumes_state,
        )
```

Extend `_fn_step()` to detect `_artifact_op` — add before the `_capture_key` check:

```python
def _fn_step(fn: Callable) -> BuilderBase:
    # Check for artifact operation (A module)
    artifact_op = getattr(fn, "_artifact_op", None)
    if artifact_op is not None:
        name = getattr(fn, "__name__", f"artifact_{artifact_op}")
        if not name.isidentifier():
            name = f"artifact_{artifact_op}"
        return _ArtifactBuilder(name, _atransform=fn)

    # Check for capture_key (S.capture())
    capture_key = getattr(fn, "_capture_key", None)
    # ... existing code ...
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py -x --tb=short -q`
Expected: PASS (all tests)

**Step 6: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_ir.py src/adk_fluent/_primitive_builders.py && ruff format src/adk_fluent/_ir.py src/adk_fluent/_primitive_builders.py
git add src/adk_fluent/_ir.py src/adk_fluent/_primitive_builders.py tests/manual/test_artifacts.py
git commit -m "feat(A): add ArtifactNode IR, _ArtifactBuilder, and _fn_step detection"
```

---

### Task 5: ArtifactAgent Runtime

**Files:**
- Modify: `src/adk_fluent/_primitives.py` (add ArtifactAgent)
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing test**

```python
# Append to tests/manual/test_artifacts.py
import pytest


class TestArtifactAgent:
    def test_agent_creation(self):
        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.publish("report.md", from_key="report")
        agent = ArtifactAgent(name="publish_report", atransform=at)
        assert agent.name == "publish_report"

    @pytest.mark.asyncio
    async def test_publish_saves_to_artifact_service(self):
        """Integration test: publish reads state, saves artifact."""
        from unittest.mock import AsyncMock, MagicMock

        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.publish("report.md", from_key="report")
        agent = ArtifactAgent(name="test", atransform=at)

        # Mock context
        ctx = MagicMock()
        ctx.session.state = {"report": "# My Report"}
        ctx.session.id = "sess-1"
        mock_svc = AsyncMock()
        mock_svc.save_artifact = AsyncMock(return_value=0)
        ctx._invocation_context.artifact_service = mock_svc
        ctx._invocation_context.app_name = "test_app"
        ctx._invocation_context.user_id = "user-1"
        ctx._event_actions.artifact_delta = {}

        async for _ in agent._run_async_impl(ctx):
            pass

        mock_svc.save_artifact.assert_called_once()
        call_kwargs = mock_svc.save_artifact.call_args[1]
        assert call_kwargs["filename"] == "report.md"
        assert ctx._event_actions.artifact_delta["report.md"] == 0

    @pytest.mark.asyncio
    async def test_snapshot_loads_text_into_state(self):
        """Integration test: snapshot loads artifact, writes to state."""
        from unittest.mock import AsyncMock, MagicMock

        import google.genai.types as types

        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.snapshot("report.md", into_key="text")
        agent = ArtifactAgent(name="test", atransform=at)

        ctx = MagicMock()
        ctx.session.state = {}
        ctx.session.id = "sess-1"
        mock_svc = AsyncMock()
        mock_svc.load_artifact = AsyncMock(
            return_value=types.Part.from_text(text="# Report Content")
        )
        ctx._invocation_context.artifact_service = mock_svc
        ctx._invocation_context.app_name = "test_app"
        ctx._invocation_context.user_id = "user-1"

        async for _ in agent._run_async_impl(ctx):
            pass

        assert ctx.session.state["text"] == "# Report Content"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestArtifactAgent -x --tb=short -q`
Expected: FAIL — `ImportError: cannot import name 'ArtifactAgent'`

**Step 3: Implement ArtifactAgent**

Add to `src/adk_fluent/_primitives.py` after `CaptureAgent`:

```python
class ArtifactAgent(BaseAgent):
    """Zero-cost artifact bridge/direct agent. No LLM call.

    Handles both bridge ops (publish/snapshot) and direct ops
    (save/load/list/version/delete).
    """

    _atransform: Any

    def __init__(self, *, atransform: Any, **kwargs: Any):
        super().__init__(**kwargs)
        object.__setattr__(self, "_atransform", atransform)

    async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Event, None]:
        from google.genai import types

        at = self._atransform
        svc = ctx._invocation_context.artifact_service
        if svc is None:
            raise ValueError("No artifact_service configured on Runner")

        app_name = ctx._invocation_context.app_name
        user_id = ctx._invocation_context.user_id
        session_id = ctx.session.id
        scope_filename = f"user:{at._filename}" if at._scope == "user" else at._filename

        if at._op == "publish":
            content = ctx.session.state.get(at._from_key, "")
            if isinstance(content, bytes):
                part = types.Part.from_bytes(data=content, mime_type=at._mime or "application/octet-stream")
            else:
                part = types.Part.from_text(text=str(content))
            version = await svc.save_artifact(
                app_name=app_name, user_id=user_id, session_id=session_id,
                filename=scope_filename, artifact=part,
                custom_metadata=at._metadata,
            )
            ctx._event_actions.artifact_delta[scope_filename] = version

        elif at._op == "save":
            if isinstance(at._content, bytes):
                part = types.Part.from_bytes(data=at._content, mime_type=at._mime or "application/octet-stream")
            else:
                part = types.Part.from_text(text=str(at._content))
            version = await svc.save_artifact(
                app_name=app_name, user_id=user_id, session_id=session_id,
                filename=scope_filename, artifact=part,
                custom_metadata=at._metadata,
            )
            ctx._event_actions.artifact_delta[scope_filename] = version

        elif at._op == "snapshot":
            part = await svc.load_artifact(
                app_name=app_name, user_id=user_id, session_id=session_id,
                filename=scope_filename, version=at._version,
            )
            if part is not None:
                if part.text is not None:
                    ctx.session.state[at._into_key] = part.text
                elif at._decode and part.inline_data:
                    ctx.session.state[at._into_key] = part.inline_data.data.decode("utf-8", errors="replace")
                elif part.inline_data:
                    # Binary: store URI reference
                    ctx.session.state[at._into_key] = (
                        f"artifact://apps/{app_name}/users/{user_id}"
                        f"/sessions/{session_id}/artifacts/{scope_filename}"
                    )
                else:
                    ctx.session.state[at._into_key] = str(part)

        elif at._op == "load":
            pass  # Direct pipeline load — no state bridge

        elif at._op == "list":
            keys = await svc.list_artifact_keys(
                app_name=app_name, user_id=user_id, session_id=session_id,
            )
            ctx.session.state[at._into_key] = keys

        elif at._op == "version":
            ver = await svc.get_artifact_version(
                app_name=app_name, user_id=user_id, session_id=session_id,
                filename=scope_filename,
            )
            if ver is not None:
                ctx.session.state[at._into_key] = {
                    "version": ver.version,
                    "mime_type": ver.mime_type,
                    "create_time": ver.create_time,
                    "canonical_uri": ver.canonical_uri,
                }

        elif at._op == "delete":
            await svc.delete_artifact(
                app_name=app_name, user_id=user_id, session_id=session_id,
                filename=scope_filename,
            )

        return
        yield  # noqa: RET504 — async generator protocol
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestArtifactAgent -x --tb=short -q`
Expected: PASS (all 3 tests)

**Step 5: Lint and commit**

```bash
ruff check --fix src/adk_fluent/_primitives.py && ruff format src/adk_fluent/_primitives.py
git add src/adk_fluent/_primitives.py tests/manual/test_artifacts.py
git commit -m "feat(A): add ArtifactAgent runtime for publish/snapshot/save/load/list/version/delete"
```

---

### Task 6: Pipeline Integration (>> operator)

**Files:**
- Test: `tests/manual/test_artifacts.py`

No code changes needed — `_fn_step()` already detects `_artifact_op` (Task 4), and `__rshift__` in `_base.py` already calls `_fn_step()` for callables. This task validates the integration end-to-end.

**Step 1: Write the integration test**

```python
# Append to tests/manual/test_artifacts.py

class TestPipelineIntegration:
    def test_agent_rshift_atransform(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.workflow import Pipeline

        pipeline = Agent("writer").instruct("Write.") >> A.publish("report.md", from_key="output")
        assert isinstance(pipeline, Pipeline)

    def test_atransform_in_multi_step_pipeline(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.workflow import Pipeline

        pipeline = (
            Agent("researcher").instruct("Research.")
            >> A.publish("findings.md", from_key="findings")
            >> A.snapshot("findings.md", into_key="source")
            >> Agent("writer").instruct("Write from {source}.")
        )
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_to_ir_includes_artifact_nodes(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent._ir import ArtifactNode

        pipeline = (
            Agent("writer").instruct("Write.")
            >> A.publish("report.md", from_key="output")
        )
        ir = pipeline.to_ir()
        # IR should contain an ArtifactNode
        children = ir.children if hasattr(ir, "children") else []
        artifact_nodes = [c for c in children if isinstance(c, ArtifactNode)]
        assert len(artifact_nodes) == 1
        assert artifact_nodes[0].op == "publish"
```

**Step 2: Run tests**

Run: `uv run pytest tests/manual/test_artifacts.py::TestPipelineIntegration -x --tb=short -q`
Expected: PASS (all 3 tests — if they fail, debug the `_fn_step` → `_ArtifactBuilder` wiring)

**Step 3: Commit**

```bash
git add tests/manual/test_artifacts.py
git commit -m "test(A): add pipeline integration tests for >> operator"
```

---

### Task 7: Module Export (prelude + __init__)

**Files:**
- Modify: `src/adk_fluent/prelude.py`
- Run: `just generate` (regenerates `__init__.py` from `__all__` exports)

**Step 1: Write test**

```python
# Append to tests/manual/test_artifacts.py

class TestExports:
    def test_import_from_adk_fluent(self):
        from adk_fluent import A, ATransform

        assert hasattr(A, "publish")
        assert hasattr(A, "mime")
        assert ATransform is not None

    def test_import_from_prelude(self):
        from adk_fluent.prelude import A

        assert hasattr(A, "publish")
```

**Step 2: Run to verify it fails**

Run: `uv run pytest tests/manual/test_artifacts.py::TestExports -x --tb=short -q`
Expected: FAIL — `ImportError: cannot import name 'A' from 'adk_fluent'`

**Step 3: Add to prelude.py**

Add import and `__all__` entry:

```python
from adk_fluent._artifacts import A
```

And add `"A"` to the Tier 2 section of `__all__`.

**Step 4: Regenerate __init__.py**

Run: `just generate`

This auto-discovers `__all__` from `_artifacts.py` and adds `A` and `ATransform` to `__init__.py`.

**Step 5: Run to verify**

Run: `uv run pytest tests/manual/test_artifacts.py::TestExports -x --tb=short -q`
Expected: PASS

**Step 6: Lint and commit**

```bash
ruff check --fix . && ruff format .
just check-gen
git add src/adk_fluent/prelude.py src/adk_fluent/__init__.py tests/manual/test_artifacts.py
git commit -m "feat(A): export A and ATransform from prelude and __init__"
```

---

### Task 8: Contract Checking Pass 15 (Artifact Availability)

**Files:**
- Modify: `src/adk_fluent/testing/contracts.py`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing tests**

```python
# Append to tests/manual/test_artifacts.py

class TestContractChecking:
    def test_snapshot_without_upstream_publish_is_error(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        pipeline = (
            Agent("writer").instruct("Write.")
            >> A.snapshot("report.md", into_key="text")  # no upstream publish!
        )
        ir = pipeline.to_ir()
        from adk_fluent.testing.contracts import check_contracts

        issues = check_contracts(ir)
        artifact_issues = [i for i in issues if "artifact" in i.get("message", "").lower()]
        assert any(i["level"] == "error" for i in artifact_issues)

    def test_snapshot_with_upstream_publish_is_clean(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        pipeline = (
            Agent("writer").instruct("Write.").save_as("report")
            >> A.publish("report.md", from_key="report")
            >> A.snapshot("report.md", into_key="text")
        )
        ir = pipeline.to_ir()
        from adk_fluent.testing.contracts import check_contracts

        issues = check_contracts(ir)
        artifact_errors = [
            i for i in issues
            if "artifact" in i.get("message", "").lower() and i["level"] == "error"
        ]
        assert len(artifact_errors) == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/manual/test_artifacts.py::TestContractChecking -x --tb=short -q`
Expected: FAIL — no artifact-related issues found (Pass 15 doesn't exist yet)

**Step 3: Implement Pass 15**

Add to `src/adk_fluent/testing/contracts.py` after Pass 14, inside the sequence validation loop. Follow the existing pass pattern:

```python
# ── Pass 15: Artifact availability ─────────────────────────
artifacts_available: set[str] = set()

for idx, child in enumerate(children):
    child_name = getattr(child, "name", "?")

    if not hasattr(child, "consumes_artifact"):
        continue

    # Check consumed artifacts are available upstream
    for artifact_name in getattr(child, "consumes_artifact", frozenset()):
        if artifact_name not in artifacts_available:
            issues.append({
                "level": "error",
                "agent": _scoped(child_name),
                "message": (
                    f"Consumes artifact '{artifact_name}' but no upstream "
                    f"A.publish() or A.save() produces it"
                ),
            })

    # Check consumed state keys (bridge ops)
    if getattr(child, "bridges_state", False):
        for key in getattr(child, "consumes_state", frozenset()):
            if key not in produced_keys:
                issues.append({
                    "level": "error",
                    "agent": _scoped(child_name),
                    "message": (
                        f"A.publish() reads state key '{key}' but no upstream "
                        f"agent produces it"
                    ),
                })

    # Promote produced artifacts
    for artifact_name in getattr(child, "produces_artifact", frozenset()):
        artifacts_available.add(artifact_name)

    # Promote produced state keys (so downstream state checks see them)
    for key in getattr(child, "produces_state", frozenset()):
        produced_keys.add(key)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/manual/test_artifacts.py::TestContractChecking -x --tb=short -q`
Expected: PASS (both tests)

**Step 5: Run full test suite to check for regressions**

Run: `uv run pytest tests/ -x --tb=short -q`
Expected: All existing tests still pass

**Step 6: Lint and commit**

```bash
ruff check --fix src/adk_fluent/testing/contracts.py && ruff format src/adk_fluent/testing/contracts.py
git add src/adk_fluent/testing/contracts.py tests/manual/test_artifacts.py
git commit -m "feat(A): add contract checking Pass 15 — artifact availability validation"
```

---

### Task 9: Builder Method (.artifacts())

**Files:**
- Modify: `seeds/seed.manual.toml`
- Run: `just seed && just generate`
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write the failing test**

```python
# Append to tests/manual/test_artifacts.py

class TestBuilderMethod:
    def test_artifacts_builder_method(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        agent = (
            Agent("writer")
            .instruct("Write.")
            .save_as("report")
            .artifacts(
                A.publish("report.md", from_key="report"),
            )
        )
        # Should not raise
        assert agent is not None
```

**Step 2: Run to verify it fails**

Run: `uv run pytest tests/manual/test_artifacts.py::TestBuilderMethod -x --tb=short -q`
Expected: FAIL — `AttributeError: 'Agent' has no attribute 'artifacts'`

**Step 3: Add to seed.manual.toml**

```toml
[[builders.Agent.extras]]
name = "artifacts"
signature = "(self, *transforms: Any) -> Self"
doc = "Attach artifact operations (A.publish, A.snapshot, etc.) that fire after this agent."
behavior = "runtime_helper"
helper_func = "_add_artifacts"
example = '''Agent("writer").artifacts(A.publish("report.md", from_key="output"))'''
see_also = ["A", "ATransform"]
```

**Step 4: Add the helper function**

Add `_add_artifacts` to `src/adk_fluent/_helpers.py`:

```python
def _add_artifacts(builder: Any, *transforms: Any) -> Any:
    """Attach artifact transforms as after-agent hooks."""
    if not hasattr(builder, "_artifact_transforms"):
        builder._artifact_transforms = []
    builder._artifact_transforms.extend(transforms)
    return builder
```

**Step 5: Regenerate**

Run: `just seed && just generate`

**Step 6: Run tests**

Run: `uv run pytest tests/manual/test_artifacts.py::TestBuilderMethod -x --tb=short -q`
Expected: PASS

**Step 7: Lint and commit**

```bash
ruff check --fix . && ruff format .
just check-gen
git add seeds/seed.manual.toml src/adk_fluent/_helpers.py
git add src/adk_fluent/agent.py src/adk_fluent/agent.pyi  # regenerated
git commit -m "feat(A): add .artifacts() builder method via seed"
```

---

### Task 10: Full Integration Test + Preflight

**Files:**
- Test: `tests/manual/test_artifacts.py`

**Step 1: Write end-to-end integration test**

```python
# Append to tests/manual/test_artifacts.py

class TestEndToEnd:
    def test_full_pipeline_builds(self):
        """End-to-end: pipeline with A operations builds without error."""
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        pipeline = (
            Agent("researcher")
            .model("gemini-2.5-flash")
            .instruct("Research the topic.")
            .save_as("findings")
            >> A.publish("findings.md", from_key="findings")
            >> A.snapshot("findings.md", into_key="source")
            >> Agent("writer")
            .model("gemini-2.5-flash")
            .instruct("Write report from {source}.")
            .save_as("report")
            >> A.publish("report.md", from_key="report")
        )
        # Should build without error
        app = pipeline.build()
        assert app is not None

    def test_full_pipeline_contract_check(self):
        """Contract checker validates artifact flow correctly."""
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.testing.contracts import check_contracts

        pipeline = (
            Agent("researcher")
            .instruct("Research.")
            .save_as("findings")
            >> A.publish("findings.md", from_key="findings")
            >> A.snapshot("findings.md", into_key="source")
            >> Agent("writer")
            .instruct("Write.")
        )
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        artifact_errors = [
            i for i in issues
            if "artifact" in i.get("message", "").lower() and i["level"] == "error"
        ]
        assert len(artifact_errors) == 0
```

**Step 2: Run full test suite**

Run: `uv run pytest tests/ -x --tb=short -q`
Expected: ALL PASS

**Step 3: Run preflight**

Run: `just preflight`
Expected: PASS

**Step 4: Run check-gen**

Run: `just check-gen`
Expected: PASS (generated files are up-to-date)

**Step 5: Run typecheck**

Run: `just typecheck-core`
Expected: 0 errors

**Step 6: Final commit**

```bash
git add tests/manual/test_artifacts.py
git commit -m "test(A): add end-to-end integration tests for Phase 1"
```

---

## Summary

| Task | What | Key Files |
|------|------|-----------|
| 1 | A.mime constants + classifiers | `_artifacts.py`, `test_artifacts.py` |
| 2 | ATransform descriptor dataclass | `_artifacts.py` |
| 3 | Core factories (publish/snapshot/save/load/list/version/delete/when) | `_artifacts.py` |
| 4 | ArtifactNode IR + _ArtifactBuilder + _fn_step detection | `_ir.py`, `_primitive_builders.py` |
| 5 | ArtifactAgent runtime | `_primitives.py` |
| 6 | Pipeline integration tests (>> operator) | `test_artifacts.py` |
| 7 | Module export (prelude + __init__) | `prelude.py`, `__init__.py` |
| 8 | Contract checking Pass 15 | `contracts.py` |
| 9 | Builder method (.artifacts()) | `seed.manual.toml`, `_helpers.py` |
| 10 | Full integration test + preflight | `test_artifacts.py` |

Phase 2 and Phase 3 plans will be written after Phase 1 ships and patterns stabilize.
