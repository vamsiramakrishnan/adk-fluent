"""A module — fluent artifact composition.

Bridges the state and artifact planes with explicit, honest semantics.
See docs/plans/2026-03-01-a-module-design.md for architectural rationale.
"""

from __future__ import annotations

import mimetypes

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


class A:
    """Artifact operations — bridge between state and artifact service.

    Four verbs for four semantics:
    - publish: state -> artifact (bridge, copy out)
    - snapshot: artifact -> state (bridge, copy in)
    - save: content -> artifact (direct, no state bridge)
    - load: artifact -> pipeline (direct, no state bridge)
    """

    mime = _MimeConstants()


# Placeholder for future ATransform class
ATransform = None
