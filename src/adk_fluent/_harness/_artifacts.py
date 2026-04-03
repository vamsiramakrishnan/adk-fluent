"""Artifact and blob handling — managing large outputs and binary data.

Coding harnesses need to handle outputs that don't fit in context:
screenshots, large test outputs, generated images, CSV exports.

The ArtifactStore provides a simple filesystem-backed store with
metadata tracking::

    store = ArtifactStore("/project/.harness/artifacts")
    ref = store.save("test-output.txt", large_output)
    ref = store.save_binary("screenshot.png", png_bytes)

    # Retrieve
    content = store.load("test-output.txt")

    # Reference in LLM context (short summary instead of full content)
    summary = store.summarize("test-output.txt")
    # → "Artifact: test-output.txt (45.2 KB, text/plain)"
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = ["ArtifactStore", "ArtifactRef"]


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A reference to a stored artifact."""

    name: str
    path: str
    size_bytes: int
    mime_type: str
    sha256: str
    created_at: float


class ArtifactStore:
    """Filesystem-backed artifact store for large outputs and blobs.

    Artifacts are stored in a dedicated directory with metadata tracking.
    Each artifact gets a content-addressable hash for deduplication.

    Args:
        root: Directory to store artifacts in.
        max_inline_bytes: Maximum size for inline content in LLM context.
    """

    def __init__(self, root: str | Path, *, max_inline_bytes: int = 10_000) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_inline_bytes = max_inline_bytes
        self._manifest: dict[str, ArtifactRef] = {}
        self._load_manifest()

    def save(self, name: str, content: str, *, mime_type: str = "text/plain") -> ArtifactRef:
        """Save a text artifact.

        Args:
            name: Artifact name (e.g., "test-output.txt").
            content: Text content.
            mime_type: MIME type.

        Returns:
            Reference to the saved artifact.
        """
        data = content.encode("utf-8")
        return self._save_bytes(name, data, mime_type)

    def save_binary(self, name: str, data: bytes, *, mime_type: str = "application/octet-stream") -> ArtifactRef:
        """Save a binary artifact (image, PDF, etc.).

        Args:
            name: Artifact name (e.g., "screenshot.png").
            data: Binary content.
            mime_type: MIME type.

        Returns:
            Reference to the saved artifact.
        """
        return self._save_bytes(name, data, mime_type)

    def load(self, name: str) -> str | None:
        """Load a text artifact by name.

        Returns:
            Text content, or None if not found.
        """
        ref = self._manifest.get(name)
        if ref is None:
            return None
        try:
            return Path(ref.path).read_text(encoding="utf-8")
        except Exception:
            return None

    def load_binary(self, name: str) -> bytes | None:
        """Load a binary artifact by name."""
        ref = self._manifest.get(name)
        if ref is None:
            return None
        try:
            return Path(ref.path).read_bytes()
        except Exception:
            return None

    def summarize(self, name: str) -> str:
        """Get a short summary of an artifact for LLM context.

        Instead of including full content, this returns a compact
        reference suitable for injection into prompts.
        """
        ref = self._manifest.get(name)
        if ref is None:
            return f"Artifact not found: {name}"

        size_str = _human_size(ref.size_bytes)
        summary = f"[Artifact: {ref.name} ({size_str}, {ref.mime_type})]"

        # If small enough, include content inline
        if ref.size_bytes <= self.max_inline_bytes and ref.mime_type.startswith("text/"):
            content = self.load(name)
            if content:
                summary += f"\n{content}"
        return summary

    def list_artifacts(self) -> list[ArtifactRef]:
        """List all stored artifacts."""
        return list(self._manifest.values())

    def delete(self, name: str) -> bool:
        """Delete an artifact."""
        ref = self._manifest.pop(name, None)
        if ref is None:
            return False
        try:
            Path(ref.path).unlink(missing_ok=True)
            self._save_manifest()
            return True
        except Exception:
            return False

    def _save_bytes(self, name: str, data: bytes, mime_type: str) -> ArtifactRef:
        sha = hashlib.sha256(data).hexdigest()
        # Use content-addressable filename for dedup
        storage_name = f"{sha[:16]}_{name}"
        storage_path = self.root / storage_name

        storage_path.write_bytes(data)

        ref = ArtifactRef(
            name=name,
            path=str(storage_path),
            size_bytes=len(data),
            mime_type=mime_type,
            sha256=sha,
            created_at=time.time(),
        )
        self._manifest[name] = ref
        self._save_manifest()
        return ref

    def _save_manifest(self) -> None:
        """Persist the manifest to disk."""
        manifest_path = self.root / "_manifest.json"
        data = {}
        for name, ref in self._manifest.items():
            data[name] = {
                "name": ref.name,
                "path": ref.path,
                "size_bytes": ref.size_bytes,
                "mime_type": ref.mime_type,
                "sha256": ref.sha256,
                "created_at": ref.created_at,
            }
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_manifest(self) -> None:
        """Load manifest from disk if it exists."""
        manifest_path = self.root / "_manifest.json"
        if not manifest_path.exists():
            return
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            for name, info in data.items():
                self._manifest[name] = ArtifactRef(**info)
        except Exception:
            pass


def _human_size(size: int) -> str:
    """Convert bytes to human-readable size."""
    fsize = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if fsize < 1024:
            return f"{fsize:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        fsize /= 1024
    return f"{fsize:.1f} TB"
