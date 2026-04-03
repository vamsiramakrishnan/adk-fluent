"""Skill-Powered Harness — Building a CodAct Coding Agent

Demonstrates how to build a Claude-Code-like coding agent harness using
adk-fluent's three-layer skill architecture:

  L1: .use_skill()  — expertise loading (SKILL.md body → static_instruction)
  L2: T.skill()     — progressive disclosure (SkillToolset, LLM loads on demand)
  L3: Skill()       — recipe (pre-composed agent workflow from SKILL.md)

Plus the H namespace for harness runtime primitives:

  H.workspace()     — sandboxed file/shell tools (read, edit, write, glob, grep, bash)
  H.ask_before()    — permission policies (which tools need approval)
  H.auto_allow()    — auto-approved tools
  H.workspace_only()— sandbox policies (restrict fs to workspace)

Architecture:
    ┌──────────────────────────────────────┐
    │          Agent + Skills              │
    │  .use_skill("code-review/")         │  ← L1: expertise (static, cached)
    │  .use_skill("python-best-practices/")│
    │  .instruct("Review the code.")       │  ← per-task instruction
    │  .tools(H.workspace("/project"))     │  ← sandboxed tools
    │  .harness(permissions=..., sandbox=.)│  ← permission + sandbox
    └──────────────────────────────────────┘
"""

import os
import tempfile

import pytest

from adk_fluent import Agent, H, Pipeline, Skill
from adk_fluent._harness import PermissionPolicy, SandboxPolicy, SkillSpec


# ======================================================================
# Pattern 1: Minimal harness — agent + workspace tools
# ======================================================================


def test_minimal_harness():
    """The simplest harness: an agent with workspace tools."""
    with tempfile.TemporaryDirectory() as project:
        # Create a sample file
        with open(os.path.join(project, "main.py"), "w") as f:
            f.write("def hello():\n    print('hello world')\n")

        agent = (
            Agent("coder", "gemini-2.5-flash")
            .instruct("You are a coding assistant. Help the user with their project.")
            .tools(H.workspace(project))
        )
        built = agent.build()
        # 7 tools: read, edit, write, glob, grep, bash, ls
        assert len(built.tools) == 7


# ======================================================================
# Pattern 2: Skilled harness — agent + expertise + workspace
# ======================================================================


def test_skilled_harness():
    """Agent with expertise from SKILL.md files + workspace tools."""
    with tempfile.TemporaryDirectory() as project:
        agent = (
            Agent("reviewer", "gemini-2.5-pro")
            .use_skill("examples/skills/code_reviewer/")
            .instruct("Review the code in this project. Focus on security.")
            .tools(H.workspace(project, read_only=True))
        )
        built = agent.build()
        # Skills go to static_instruction (cached)
        assert "<skills>" in (built.static_instruction or "")
        assert "code_reviewer" in (built.static_instruction or "")
        # Instruction is separate (per-task)
        assert "security" in (built.instruction or "")
        # Read-only tools: read, glob, grep, ls, bash = 5
        # (read_only disables edit/write but bash is still available)
        assert len(built.tools) == 5


# ======================================================================
# Pattern 3: Multi-skill agent — stacked expertise
# ======================================================================


def test_multi_skill_agent():
    """Agent with multiple skills = compound expertise."""
    agent = (
        Agent("analyst", "gemini-2.5-pro")
        .use_skill("examples/skills/research_pipeline/")
        .use_skill("examples/skills/code_reviewer/")
        .instruct("Analyze this codebase for quality and maintainability.")
    )
    built = agent.build()
    static = built.static_instruction or ""
    # Both skills present in static instruction
    assert "research_pipeline" in static
    assert "code_reviewer" in static
    # Order preserved
    assert static.index("research_pipeline") < static.index("code_reviewer")


# ======================================================================
# Pattern 4: Permission-gated harness
# ======================================================================


def test_permission_gated_harness():
    """Harness with permission policies on dangerous tools."""
    with tempfile.TemporaryDirectory() as project:
        agent = (
            Agent("coder", "gemini-2.5-flash")
            .instruct("Help with the project.")
            .tools(H.workspace(project))
            .harness(
                permissions=(
                    H.auto_allow("read_file", "glob_search", "grep_search", "list_dir")
                    .merge(H.ask_before("edit_file", "write_file", "bash"))
                ),
                sandbox=H.workspace_only(project),
            )
        )
        built = agent.build()
        # Permission callback is registered
        assert built.before_tool_callback is not None


# ======================================================================
# Pattern 5: Skilled agents in a pipeline
# ======================================================================


def test_skilled_pipeline():
    """Pipeline where each agent has different expertise."""
    researcher = (
        Agent("researcher", "gemini-2.5-flash")
        .use_skill("examples/skills/research_pipeline/")
        .instruct("Research the topic: {topic}")
        .writes("findings")
    )
    reviewer = (
        Agent("reviewer", "gemini-2.5-flash")
        .use_skill("examples/skills/code_reviewer/")
        .instruct("Review the findings for accuracy.")
        .reads("findings")
        .writes("review")
    )
    pipeline = researcher >> reviewer
    built = pipeline.build()
    assert len(built.sub_agents) == 2
    # Each agent has its own skill
    assert "research_pipeline" in (built.sub_agents[0].static_instruction or "")
    assert "code_reviewer" in (built.sub_agents[1].static_instruction or "")


# ======================================================================
# Pattern 6: Mixing L1 (.use_skill) with L3 (Skill builder)
# ======================================================================


def test_skill_layer_mixing():
    """Mix .use_skill() (L1 expertise) with Skill() builder (L3 recipe)."""
    # L3: Skill builder creates a pre-composed agent graph
    research_pipeline = Skill("examples/skills/research_pipeline/")

    # L1: Agent with expertise from a different skill
    editor = (
        Agent("editor", "gemini-2.5-pro")
        .use_skill("examples/skills/code_reviewer/")
        .instruct("Polish the research report.")
        .reads("report")
    )

    # Compose them: recipe >> skilled agent
    pipeline = research_pipeline >> editor
    built = pipeline.build()
    assert len(built.sub_agents) == 2


# ======================================================================
# Pattern 7: Workspace tool isolation
# ======================================================================


def test_workspace_isolation():
    """Workspace tools are sandboxed to the project directory."""
    with tempfile.TemporaryDirectory() as project:
        tools = H.workspace(project)
        read_fn = [t for t in tools if t.__name__ == "read_file"][0]

        # Can read inside workspace
        test_file = os.path.join(project, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello\n")
        result = read_fn("test.txt")
        assert "hello" in result

        # Cannot read outside workspace
        result = read_fn("/etc/hostname")
        assert "Error" in result or "outside" in result


# ======================================================================
# Pattern 8: Full harness — the Claude-Code-like pattern
# ======================================================================


def test_full_harness_pattern():
    """The complete pattern: skills + workspace + permissions + context."""
    from adk_fluent._context import C

    with tempfile.TemporaryDirectory() as project:
        harness_agent = (
            Agent("coder", "gemini-2.5-pro")
            # L1: Domain expertise
            .use_skill("examples/skills/code_reviewer/")
            .use_skill("examples/skills/research_pipeline/")
            # Per-task instruction
            .instruct(
                "You are an expert coding assistant. "
                "Use your skills and tools to help the user."
            )
            # Sandboxed workspace tools
            .tools(H.workspace(project))
            # Context engineering
            .context(C.rolling(n=20))
            # Harness configuration
            .harness(
                permissions=(
                    H.auto_allow("read_file", "glob_search", "grep_search", "list_dir")
                    .merge(H.ask_before("edit_file", "write_file", "bash"))
                ),
                sandbox=H.workspace_only(project),
                auto_compress=100_000,
            )
        )
        built = harness_agent.build()

        # Verify the full setup
        assert "<skills>" in (built.static_instruction or "")
        assert "code_reviewer" in (built.static_instruction or "")
        assert "research_pipeline" in (built.static_instruction or "")
        assert len(built.tools) == 7
        assert built.before_tool_callback is not None
        # Instruction may be compiled to a function by context spec
        instr = built.instruction
        if callable(instr):
            # C.rolling() compiles instruction into an InstructionProvider
            assert instr is not None
        else:
            assert "expert coding assistant" in (instr or "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
