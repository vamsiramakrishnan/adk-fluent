"""Multimodal file reading — images, PDFs, and binary files.

Claude Code can read screenshots, images, and PDFs. This module extends
the standard ``read_file`` tool to detect binary file types and return
them as base64-encoded content suitable for multimodal LLM input::

    tools = H.workspace("/project", multimodal=True)
    # read_file now handles .png, .jpg, .pdf, etc.

The LLM's vision capability handles the rest — we just pass the bytes.
"""

from __future__ import annotations

import base64
import mimetypes
from collections.abc import Callable
from pathlib import Path

from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["make_multimodal_read_file"]

# File extensions we handle as multimodal content
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"})
_PDF_EXTENSIONS = frozenset({".pdf"})
_BINARY_EXTENSIONS = _IMAGE_EXTENSIONS | _PDF_EXTENSIONS


def _is_multimodal_file(path: str) -> bool:
    """Check if a file should be handled as multimodal content."""
    return Path(path).suffix.lower() in _BINARY_EXTENSIONS


def _get_mime_type(path: str) -> str:
    """Get MIME type for a file."""
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def make_multimodal_read_file(
    sandbox: SandboxPolicy,
    *,
    max_image_bytes: int = 5_000_000,  # 5 MB
) -> Callable:
    """Create a multimodal file-read tool.

    For text files, behaves identically to the standard ``read_file``.
    For images and PDFs, returns a structured dict with base64 content
    that ADK can pass to the LLM as multimodal input.

    Args:
        sandbox: Sandbox policy for path validation.
        max_image_bytes: Maximum size for binary files.
    """

    def read_file(path: str, offset: int = 0, limit: int = 2000) -> str | dict:
        """Read a file with line numbers. Handles images and PDFs as multimodal content.

        For text files: returns numbered lines with offset/limit support.
        For images/PDFs: returns base64-encoded content for LLM vision.

        Args:
            path: Absolute or workspace-relative file path.
            offset: Line number to start from (0-based, text files only).
            limit: Maximum number of lines to return (text files only).
        """
        resolved = sandbox.resolve_path(path)
        if not sandbox.validate_path(resolved, write=False):
            return f"Error: path '{path}' is outside the allowed workspace."

        if _is_multimodal_file(resolved):
            return _read_binary(resolved, path, max_image_bytes)

        # Standard text file reading
        try:
            with open(resolved, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            selected = lines[offset : offset + limit]
            numbered = [f"{offset + i + 1}\t{line}" for i, line in enumerate(selected)]
            return "".join(numbered)
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:
            return f"Error reading file: {e}"

    return read_file


def _read_binary(resolved: str, display_path: str, max_bytes: int) -> str:
    """Read a binary file and return base64-encoded content."""
    try:
        data = Path(resolved).read_bytes()
        if len(data) > max_bytes:
            return f"Error: file is too large ({len(data)} bytes, max {max_bytes})."
        mime = _get_mime_type(resolved)
        b64 = base64.b64encode(data).decode("ascii")
        return f"[Binary file: {display_path} ({len(data)} bytes, {mime})]\ndata:{mime};base64,{b64}"
    except FileNotFoundError:
        return f"Error: file not found: {display_path}"
    except Exception as e:
        return f"Error reading binary file: {e}"
