"""Skill registry — directory scanner for skill discovery.

Scans a directory tree for ``SKILL.md`` files, indexes their metadata,
and provides discovery APIs.

Usage::

    from adk_fluent import SkillRegistry

    registry = SkillRegistry("skills/")
    registry.list()                          # all skill metadata
    registry.find(tags=["research"])          # filter by tags
    registry.get("deep-research")            # get Skill builder by name
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = ["SkillRegistry"]


class SkillRegistry:
    """Directory scanner for skill discovery.

    Scans a directory tree for ``SKILL.md`` files, parses their frontmatter,
    and provides discovery by name, tags, or description.
    """

    def __init__(self, path: str | Path) -> None:
        """Scan *path* for ``SKILL.md`` files and index their metadata.

        Parameters
        ----------
        path:
            Root directory to scan (recursively).
        """
        from adk_fluent._skill_parser import parse_skill_file

        self._root = Path(path)
        self._skills: dict[str, Any] = {}  # name -> SkillDefinition

        if not self._root.is_dir():
            raise NotADirectoryError(f"Skill registry path is not a directory: {self._root}")

        for skill_md in sorted(self._root.rglob("SKILL.md")):
            try:
                skill_def = parse_skill_file(skill_md)
                self._skills[skill_def.name] = skill_def
            except Exception:
                # Skip unparseable skill files silently
                continue

    def find(
        self,
        *,
        tags: list[str] | None = None,
        name: str | None = None,
    ) -> list[Any]:
        """Find skills matching criteria.

        Parameters
        ----------
        tags:
            Match skills that have ALL specified tags.
        name:
            Match skills whose name contains this substring.

        Returns
        -------
        List of :class:`~adk_fluent.skill.Skill` builders (lazy — not built).
        """
        from adk_fluent.skill import Skill

        results = []
        for skill_def in self._skills.values():
            if tags and not all(t in skill_def.tags for t in tags):
                continue
            if name and name not in skill_def.name:
                continue
            if skill_def.path:
                results.append(Skill(skill_def.path))
        return results

    def list(self) -> list[dict[str, Any]]:
        """List all discovered skills with their metadata.

        Returns
        -------
        List of dicts with keys: ``name``, ``description``, ``tags``,
        ``path``, ``has_agents``, ``version``.
        """
        return [
            {
                "name": sd.name,
                "description": sd.description,
                "tags": sd.tags,
                "path": str(sd.path) if sd.path else None,
                "has_agents": len(sd.agents) > 0,
                "version": sd.version,
            }
            for sd in self._skills.values()
        ]

    def get(self, name: str) -> Any:
        """Get a :class:`~adk_fluent.skill.Skill` builder by exact name.

        Raises :class:`KeyError` if *name* is not found.
        """
        from adk_fluent.skill import Skill

        if name not in self._skills:
            available = ", ".join(sorted(self._skills.keys()))
            raise KeyError(f"Skill '{name}' not found. Available: {available}")
        sd = self._skills[name]
        if sd.path is None:
            raise ValueError(f"Skill '{name}' has no file path")
        return Skill(sd.path)

    def names(self) -> list[str]:
        """Return sorted list of all skill names."""
        return sorted(self._skills.keys())

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __repr__(self) -> str:
        return f"SkillRegistry({self._root!s}, skills={len(self._skills)})"
