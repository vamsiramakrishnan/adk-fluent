"""Skill loading — L1 expertise layer.

Skills are SKILL.md files containing domain expertise (methodology,
best practices, judgment criteria). They map to ``static_instruction``
on the agent — cached, stable context that persists across turns.

The separation is meaningful:
    - Skills → ``static_instruction`` (cached expertise, stable)
    - ``.instruct()`` → ``instruction`` (per-task, dynamic)

Usage::

    spec = SkillSpec.from_path("skills/code-review/")
    compiled = compile_skills_to_static([spec])
    # → '<skills><skill name="code-review">...</skill></skills>'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["SkillSpec", "compile_skills_to_static"]


@dataclass(frozen=True, slots=True)
class SkillSpec:
    """Parsed skill specification for attachment to an agent.

    This is the L1 (expertise) layer: knowledge loaded from a SKILL.md
    file and injected into the agent's instruction context.
    """

    name: str
    description: str
    body: str
    allowed_tools: list[str]
    path: Path | None = None

    @staticmethod
    def from_path(path: str | Path) -> SkillSpec:
        """Parse a SKILL.md file into a SkillSpec."""
        from adk_fluent._skill_parser import parse_skill_file

        sd = parse_skill_file(path)
        return SkillSpec(
            name=sd.name,
            description=sd.description,
            body=sd.body,
            allowed_tools=sd.allowed_tools,
            path=sd.path,
        )


def compile_skills_to_static(skills: list[SkillSpec]) -> str:
    """Compile a list of SkillSpecs into a single static instruction block.

    Skills map to ``static_instruction`` (cacheable, stable content).
    The agent's ``.instruct()`` remains the per-task instruction.

    Structure::

        <skills>
        <skill name="research-methodology">
        [skill body content]
        </skill>
        <skill name="citation-standards">
        [skill body content]
        </skill>
        </skills>
    """
    if not skills:
        return ""
    parts = ["<skills>"]
    for skill in skills:
        parts.append(f'<skill name="{skill.name}">')
        parts.append(skill.body.strip())
        parts.append("</skill>")
    parts.append("</skills>")
    return "\n".join(parts)
