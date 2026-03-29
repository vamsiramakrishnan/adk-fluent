"""Skill-Based Agents -- Composable Skills from SKILL.md Files

Skills are the 100x multiplier for agent development. Instead of writing
Python agent code, you declare agent topologies in YAML inside SKILL.md
files and compose them with the same operators you already know.

A single SKILL.md file serves four purposes:
  1. Documentation for coding agents (Claude Code, Gemini CLI)
  2. Progressive disclosure for ADK SkillToolset (L1/L2/L3)
  3. Executable agent graph for adk-fluent runtime
  4. Publishable artifact via npx skills

Skill topology (research_pipeline):
    researcher >> fact_checker >> synthesizer

Skill topology (code_reviewer):
    (analyzer | style_checker | security_auditor) >> summarizer
"""

import pytest

from adk_fluent import Agent, Skill, SkillRegistry


# ======================================================================
# Pattern 1: Load and run a skill
# ======================================================================


def test_skill_load_and_build():
    """Load a skill from a SKILL.md file and build it into ADK agents."""
    skill = Skill("examples/skills/research_pipeline/")
    built = skill.build()

    # It's a real ADK SequentialAgent with 3 sub-agents
    assert len(built.sub_agents) == 3
    assert built.sub_agents[0].name == "researcher"
    assert built.sub_agents[1].name == "fact_checker"
    assert built.sub_agents[2].name == "synthesizer"


# ======================================================================
# Pattern 2: Override model for all agents in a skill
# ======================================================================


def test_skill_model_override():
    """Override the model for every agent in the skill."""
    skill = Skill("examples/skills/research_pipeline/").model("gemini-2.5-pro")
    built = skill.build()
    # All agents now use the overridden model
    for agent in built.sub_agents:
        assert agent.model == "gemini-2.5-pro"


# ======================================================================
# Pattern 3: Inject tool implementations
# ======================================================================


def test_skill_inject_tools():
    """Inject custom tool implementations by name."""

    def my_search(query: str) -> str:
        """Custom web search implementation."""
        return f"Results for: {query}"

    skill = Skill("examples/skills/research_pipeline/").inject(web_search=my_search)
    built = skill.build()

    # The researcher agent should have the injected tool
    researcher = built.sub_agents[0]
    assert any("my_search" in str(t) or hasattr(t, "func") for t in researcher.tools)


# ======================================================================
# Pattern 4: Skill composition with >> (pipeline)
# ======================================================================


def test_skill_chaining():
    """Chain skills together with >> just like agents."""
    research = Skill("examples/skills/research_pipeline/")
    review = Skill("examples/skills/code_reviewer/")

    # Skill >> Skill creates a Pipeline of skills
    pipeline = research >> review
    built = pipeline.build()
    assert len(built.sub_agents) == 2


# ======================================================================
# Pattern 5: Skill + Agent mixing
# ======================================================================


def test_skill_agent_mixing():
    """Mix skills and agents in the same pipeline."""
    research = Skill("examples/skills/research_pipeline/")
    editor = Agent("editor", "gemini-2.5-flash").instruct("Polish the report.")

    pipeline = research >> editor
    built = pipeline.build()
    assert len(built.sub_agents) == 2


# ======================================================================
# Pattern 6: Skill as AgentTool (coordinator pattern)
# ======================================================================


def test_skill_as_agent_tool():
    """Use a skill as a tool the coordinator LLM can invoke."""
    research = Skill("examples/skills/research_pipeline/")

    coordinator = (
        Agent("coordinator", "gemini-2.5-pro")
        .instruct("You have access to a research skill. Use it when needed.")
        .agent_tool(research.describe("Deep multi-source research with citations"))
    )
    built = coordinator.build()
    # The coordinator has the research skill as a callable tool
    assert len(built.tools) > 0


# ======================================================================
# Pattern 7: Fan-out parallel skills
# ======================================================================


def test_skill_parallel():
    """Run skills in parallel with | operator."""
    research = Skill("examples/skills/research_pipeline/")
    review = Skill("examples/skills/code_reviewer/")

    parallel = research | review
    built = parallel.build()
    assert len(built.sub_agents) == 2


# ======================================================================
# Pattern 8: Skill registry and discovery
# ======================================================================


def test_skill_registry():
    """Discover skills from a directory."""
    registry = SkillRegistry("examples/skills/")

    # List all skills
    all_skills = registry.list()
    assert len(all_skills) >= 2

    # Find by tags
    research_skills = registry.find(tags=["research"])
    assert len(research_skills) >= 1

    # Get by name
    skill = registry.get("research_pipeline")
    assert skill._config["name"] == "research_pipeline"


# ======================================================================
# Pattern 9: Introspection
# ======================================================================


def test_skill_introspection():
    """Inspect skill configuration and contracts."""
    skill = Skill("examples/skills/research_pipeline/")

    # Topology expression
    assert skill.topology_expr() == "researcher >> fact_checker >> synthesizer"

    # Input/output contract
    contract = skill.contract()
    assert contract["input"] == {"topic": "str"}
    assert contract["output"] == {"report": "str"}


# ======================================================================
# Pattern 10: Configure specific agent within skill
# ======================================================================


def test_skill_configure_agent():
    """Override settings for a specific agent in the skill."""
    skill = Skill("examples/skills/research_pipeline/").configure("synthesizer", model="gemini-2.5-pro")
    built = skill.build()
    assert built.sub_agents[2].model == "gemini-2.5-pro"


# ======================================================================
# Pattern 11: FanOut topology from SKILL.md
# ======================================================================


def test_skill_fanout_topology():
    """Skills can declare parallel topology in YAML."""
    skill = Skill("examples/skills/code_reviewer/")
    built = skill.build()

    # (analyzer | style_checker | security_auditor) >> summarizer
    # = Pipeline with 2 sub_agents: FanOut and summarizer
    assert len(built.sub_agents) == 2
    # First sub_agent should be a FanOut (ParallelAgent)
    fanout = built.sub_agents[0]
    assert len(fanout.sub_agents) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
