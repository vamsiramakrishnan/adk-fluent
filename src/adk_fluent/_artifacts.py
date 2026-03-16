"""A module — fluent artifact composition.

Bridges the state and artifact planes with explicit, honest semantics.
See docs/plans/2026-03-01-a-module-design.md for architectural rationale.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from adk_fluent._context import CTransform
from adk_fluent._transforms import STransform

__all__ = ["A", "ATransform"]

# Gemini-supported inline MIME prefixes (from LoadArtifactsTool)
_LLM_INLINE_PREFIXES = ("image/", "audio/", "video/")
_LLM_INLINE_TYPES = frozenset({"application/pdf"})
_TEXT_LIKE_TYPES = frozenset(
    {
        "application/csv",
        "application/json",
        "application/xml",
        "application/yaml",
    }
)


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

    # --- Composition operators ---

    def __rshift__(self, other: Any) -> Any:
        """Chain: ``a >> b``. Delegates to the pipeline operator when chaining with builders."""
        if isinstance(other, ATransform):
            # Both are artifact ops — chain via pipeline
            from adk_fluent._base import _fn_step

            return _fn_step(self) >> _fn_step(other)

        from adk_fluent._base import BuilderBase, _fn_step
        from adk_fluent._routing import Route

        if isinstance(other, BuilderBase | Route):
            return _fn_step(self) >> other
        if callable(other) and not isinstance(other, type):
            return _fn_step(self) >> other
        return NotImplemented

    # --- NamespaceSpec protocol conformance ---

    @property
    def _kind(self) -> str:
        """Discriminator tag for IR serialization (NamespaceSpec protocol)."""
        return self._op

    def _as_list(self) -> tuple[ATransform, ...]:
        """Flatten for composite building (NamespaceSpec protocol)."""
        return (self,)

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """State keys this artifact op reads (NamespaceSpec protocol)."""
        return self._consumes_state

    @property
    def _writes_keys(self) -> frozenset[str] | None:
        """State keys this artifact op writes (NamespaceSpec protocol)."""
        return self._produces_state

    # --- Legacy / internal accessors ---

    @property
    def _artifact_op(self) -> str:
        """Signal for _fn_step() detection."""
        return self._op

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return self._name


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

        # Text content -> inject directly
        if part.text is not None:
            return part.text

        # Binary content -> detect MIME and provide description
        if part.inline_data:
            mime = part.inline_data.mime_type or _MimeConstants.detect(filename)
            if _MimeConstants.is_text_like(mime):
                return part.inline_data.data.decode("utf-8", errors="replace")
            size_kb = len(part.inline_data.data) / 1024
            return f"[Binary artifact: {filename}, type: {mime}, size: {size_kb:.1f}KB]"

        return f"[Artifact '{filename}': unrecognized format]"

    return _provider


@dataclass(frozen=True)
class _ArtifactContextBlock(CTransform):
    """CTransform that loads artifact content for LLM context injection."""

    _filename: str = ""
    _scope: Literal["session", "user"] = "session"
    _version: int | None = None

    def __post_init__(self) -> None:
        provider = _make_artifact_context_provider(self._filename, self._scope, self._version)
        object.__setattr__(self, "instruction_provider", provider)
        object.__setattr__(self, "include_contents", "none")


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
        """Create a FunctionTool that lets the LLM save artifact content."""
        from google.adk.tools.function_tool import FunctionTool

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

        _save_fn.__name__ = name
        return FunctionTool(func=_save_fn)

    @staticmethod
    def load(
        name: str,
        *,
        scope: Literal["session", "user"] = "session",
    ) -> Any:
        """Create a FunctionTool that lets the LLM load artifact content."""
        from google.adk.tools.function_tool import FunctionTool

        async def _load_fn(filename: str, tool_context: Any) -> dict:
            """Load artifact content."""
            import warnings

            ctx = tool_context
            svc = ctx._invocation_context.artifact_service
            if svc is None:
                warnings.warn(
                    "No artifact service configured — load tool returning error dict "
                    "instead of raising. Configure an artifact service to use this tool.",
                    stacklevel=2,
                )
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
                warnings.warn(
                    f"Artifact '{filename}' not found — load tool returning error dict "
                    "instead of raising.",
                    stacklevel=2,
                )
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

        _load_fn.__name__ = name
        return FunctionTool(func=_load_fn)

    @staticmethod
    def list(
        name: str,
        *,
        scope: Literal["session", "user"] = "session",
    ) -> Any:
        """Create a FunctionTool that lets the LLM list available artifacts."""
        from google.adk.tools.function_tool import FunctionTool

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

        _list_fn.__name__ = name
        return FunctionTool(func=_list_fn)

    @staticmethod
    def version(
        name: str,
        *,
        scope: Literal["session", "user"] = "session",
    ) -> Any:
        """Create a FunctionTool that lets the LLM check artifact version metadata."""
        from google.adk.tools.function_tool import FunctionTool

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

        _version_fn.__name__ = name
        return FunctionTool(func=_version_fn)


class A:
    """Artifact operations — bridge between state and artifact service.

    Four verbs for four semantics:
    - publish: state -> artifact (bridge, copy out)
    - snapshot: artifact -> state (bridge, copy in)
    - save: content -> artifact (direct, no state bridge)
    - load: artifact -> pipeline (direct, no state bridge)
    """

    mime = _MimeConstants()
    tool = _ToolFactory()

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

    @staticmethod
    def for_llm(
        filename: str,
        *,
        version: int | None = None,
        scope: Literal["session", "user"] = "session",
    ) -> CTransform:
        """Load artifact directly into LLM context. No state bridge.

        Text artifacts are decoded and injected as instruction context.
        Binary artifacts get a placeholder description with MIME and size.
        Composes with C module: Agent("x").context(C.from_state("topic") + A.for_llm("report.md"))
        """
        return _ArtifactContextBlock(
            _filename=filename,
            _scope=scope,
            _version=version,
        )

    @staticmethod
    def publish_many(
        *pairs: tuple[str, str],
        mime: str | None = None,
        scope: Literal["session", "user"] = "session",
    ) -> tuple[ATransform, ...]:
        """Batch publish: multiple (filename, from_key) pairs.

        Usage: Agent("w").artifacts(*A.publish_many(("r.md", "report"), ("d.json", "data")))
        """
        return tuple(A.publish(filename, from_key=key, mime=mime, scope=scope) for filename, key in pairs)

    @staticmethod
    def snapshot_many(
        *pairs: tuple[str, str],
        scope: Literal["session", "user"] = "session",
    ) -> tuple[ATransform, ...]:
        """Batch snapshot: multiple (filename, into_key) pairs.

        Usage: Agent("r").artifacts(*A.snapshot_many(("r.md", "text"), ("d.json", "data")))
        """
        return tuple(A.snapshot(filename, into_key=key, scope=scope) for filename, key in pairs)
