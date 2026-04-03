"""Tests for .use_skill() on Agent — L1 expertise loading.

.use_skill() loads SKILL.md body into static_instruction (cached, stable context).
Multiple skills compose additively. Skills are orthogonal to .instruct().
"""

import pytest

from adk_fluent import Agent, Skill
from adk_fluent._harness import SkillSpec, _compile_skills_to_static


# ======================================================================
# SkillSpec parsing
# ======================================================================


class TestSkillSpec:
    def test_from_path(self):
        """Parse a SKILL.md file into a SkillSpec."""
        spec = SkillSpec.from_path("examples/skills/research_pipeline/")
        assert spec.name == "research_pipeline"
        assert "research" in spec.description.lower()
        assert len(spec.body) > 0  # Has markdown body

    def test_from_path_with_file(self):
        """Parse an explicit SKILL.md path."""
        spec = SkillSpec.from_path("examples/skills/research_pipeline/SKILL.md")
        assert spec.name == "research_pipeline"

    def test_body_is_markdown(self):
        """The body should be the markdown content, not YAML frontmatter."""
        spec = SkillSpec.from_path("examples/skills/research_pipeline/")
        assert "---" not in spec.body[:10]  # No YAML fence at start
        assert "Research Pipeline" in spec.body  # Has the heading


# ======================================================================
# Skill compilation to static instruction
# ======================================================================


class TestCompileSkills:
    def test_single_skill(self):
        """Single skill compiles to XML-wrapped content."""
        spec = SkillSpec(
            name="test-skill",
            description="A test skill",
            body="Do things well.\n\n## Steps\n1. First\n2. Second",
            allowed_tools=[],
        )
        result = _compile_skills_to_static([spec])
        assert '<skills>' in result
        assert '<skill name="test-skill">' in result
        assert "Do things well." in result
        assert '</skill>' in result
        assert '</skills>' in result

    def test_multiple_skills(self):
        """Multiple skills compile into ordered XML blocks."""
        specs = [
            SkillSpec(name="alpha", description="", body="Alpha content", allowed_tools=[]),
            SkillSpec(name="beta", description="", body="Beta content", allowed_tools=[]),
        ]
        result = _compile_skills_to_static(specs)
        assert '<skill name="alpha">' in result
        assert '<skill name="beta">' in result
        # Alpha comes before beta (order preserved)
        assert result.index("Alpha content") < result.index("Beta content")

    def test_empty_skills(self):
        """Empty skills list produces empty string."""
        assert _compile_skills_to_static([]) == ""


# ======================================================================
# .use_skill() on Agent
# ======================================================================


class TestSkillOnAgent:
    def test_single_skill_sets_static_instruction(self):
        """A single .use_skill() call populates static_instruction on build."""
        agent = (
            Agent("coder", "gemini-2.5-flash")
            .use_skill("examples/skills/research_pipeline/")
            .instruct("Research {topic}")
        )
        built = agent.build()
        # static_instruction should contain the skill content
        static = built.static_instruction
        assert static is not None
        assert "<skills>" in static
        assert "research_pipeline" in static
        # Regular instruction is preserved separately
        assert "Research {topic}" in (built.instruction or "")

    def test_multiple_skills_compose(self):
        """Multiple .use_skill() calls stack expertise."""
        agent = (
            Agent("reviewer", "gemini-2.5-flash")
            .use_skill("examples/skills/research_pipeline/")
            .use_skill("examples/skills/code_reviewer/")
            .instruct("Review the submission.")
        )
        built = agent.build()
        static = built.static_instruction
        assert "research_pipeline" in static
        assert "code_reviewer" in static

    def test_skill_preserves_instruct(self):
        """Skills go to static_instruction; .instruct() goes to instruction."""
        agent = (
            Agent("worker", "gemini-2.5-flash")
            .instruct("Do the task.")
            .use_skill("examples/skills/research_pipeline/")
        )
        built = agent.build()
        assert "Do the task." in (built.instruction or "")
        assert "<skills>" in (built.static_instruction or "")

    def test_skill_with_existing_static(self):
        """Skills append to existing static_instruction."""
        agent = (
            Agent("worker", "gemini-2.5-flash")
            .static("You are an expert assistant.")
            .use_skill("examples/skills/research_pipeline/")
            .instruct("Do the task.")
        )
        built = agent.build()
        static = built.static_instruction
        assert "expert assistant" in static
        assert "<skills>" in static

    def test_skill_without_instruct(self):
        """Skills work even without .instruct()."""
        agent = (
            Agent("helper", "gemini-2.5-flash")
            .use_skill("examples/skills/research_pipeline/")
        )
        built = agent.build()
        assert "<skills>" in (built.static_instruction or "")

    def test_skill_with_tools_and_context(self):
        """Skills compose with tools and context."""
        def my_search(query: str) -> str:
            return f"Results: {query}"

        agent = (
            Agent("researcher", "gemini-2.5-flash")
            .use_skill("examples/skills/research_pipeline/")
            .tool(my_search)
            .instruct("Research {topic}.")
            .writes("findings")
        )
        built = agent.build()
        assert "<skills>" in (built.static_instruction or "")
        assert len(built.tools) > 0
        assert built.output_key == "findings"

    def test_skill_immutability_after_freeze(self):
        """Skills respect copy-on-write after freeze (from operators)."""
        base = Agent("worker", "gemini-2.5-flash").instruct("Base.")
        # Freeze by using in an operator expression
        _ = base >> Agent("other", "gemini-2.5-flash").instruct("Other.")

        # Now base is frozen — use_skill should fork
        with_skill = base.use_skill("examples/skills/research_pipeline/")

        # base should not be modified (frozen copy preserved)
        base_built = base.build()
        assert base_built.static_instruction is None or "<skills>" not in (base_built.static_instruction or "")

        # with_skill should have the skill
        skilled_built = with_skill.build()
        assert "<skills>" in (skilled_built.static_instruction or "")

    def test_skill_in_pipeline(self):
        """Skilled agents work in pipelines."""
        from adk_fluent import Pipeline

        pipeline = (
            Pipeline("flow")
            .step(
                Agent("researcher", "gemini-2.5-flash")
                .use_skill("examples/skills/research_pipeline/")
                .instruct("Research {topic}.")
                .writes("findings")
            )
            .step(
                Agent("writer", "gemini-2.5-flash")
                .use_skill("examples/skills/code_reviewer/")
                .instruct("Review {findings}.")
                .reads("findings")
            )
        )
        built = pipeline.build()
        assert len(built.sub_agents) == 2

    def test_skill_with_operator(self):
        """Skilled agents work with >> operator."""
        researcher = (
            Agent("researcher", "gemini-2.5-flash")
            .use_skill("examples/skills/research_pipeline/")
            .instruct("Research.")
            .writes("findings")
        )
        writer = (
            Agent("writer", "gemini-2.5-flash")
            .instruct("Write based on {findings}.")
            .reads("findings")
        )
        pipeline = researcher >> writer
        built = pipeline.build()
        assert len(built.sub_agents) == 2


# ======================================================================
# .use_skill() + Skill() builder interop
# ======================================================================


class TestSkillInterop:
    def test_skill_builder_still_works(self):
        """The Skill() builder (recipe layer) still works unchanged."""
        skill = Skill("examples/skills/research_pipeline/")
        built = skill.build()
        assert len(built.sub_agents) == 3

    def test_skill_builder_chaining(self):
        """Skill >> Agent still works."""
        research = Skill("examples/skills/research_pipeline/")
        editor = Agent("editor", "gemini-2.5-flash").instruct("Edit.")
        pipeline = research >> editor
        built = pipeline.build()
        assert len(built.sub_agents) == 2

    def test_skilled_agent_as_agent_tool(self):
        """A skilled agent can be used as an agent_tool."""
        expert = (
            Agent("expert", "gemini-2.5-flash")
            .use_skill("examples/skills/research_pipeline/")
            .instruct("Research deeply.")
            .describe("Deep research expert")
        )
        coordinator = (
            Agent("coordinator", "gemini-2.5-pro")
            .instruct("Use the expert when needed.")
            .agent_tool(expert)
        )
        built = coordinator.build()
        assert len(built.tools) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
