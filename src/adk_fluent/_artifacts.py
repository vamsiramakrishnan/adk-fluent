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

    @property
    def _artifact_op(self) -> str:
        """Signal for _fn_step() detection."""
        return self._op

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return self._name


class A:
    """Artifact operations — bridge between state and artifact service.

    Four verbs for four semantics:
    - publish: state -> artifact (bridge, copy out)
    - snapshot: artifact -> state (bridge, copy in)
    - save: content -> artifact (direct, no state bridge)
    - load: artifact -> pipeline (direct, no state bridge)
    """

    mime = _MimeConstants()

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
