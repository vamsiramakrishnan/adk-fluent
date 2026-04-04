# Skill-Powered Harness -- Building a CodAct Coding Agent

:::{tip} What you'll learn
How to combine the **Skills Path** and **Harness Path** -- loading domain expertise from SKILL.md files into autonomous agents with sandboxed workspace tools, permission policies, and context engineering. This recipe bridges two of adk-fluent's [three development pathways](../../user-guide/index.md#three-pathways).
:::

_Source: `78_harness_and_skills.py`_ · **Pathway: Skills + Harness**

## The Three Skill Layers

adk-fluent provides three levels of skill integration, each solving a different problem:

| Layer | Method | What it does | When to use |
|-------|--------|-------------|-------------|
| **L1** | `.use_skill("path/")` | Loads SKILL.md body into `static_instruction` (cached, not re-sent every turn) | Always -- domain expertise |
| **L2** | `T.skill("path/")` | Progressive disclosure via ADK `SkillToolset` (LLM loads on demand) | Many skills, LLM picks which |
| **L3** | `Skill("path/")` | Pre-composed agent graph from `agents:` block | Predetermined topology |

## Architecture

```
┌──────────────────────────────────────┐
│          Agent + Skills              │
│  .use_skill("code-review/")         │  ← L1: expertise (static, cached)
│  .use_skill("python-best-practices/")│
│  .instruct("Review the code.")       │  ← per-task instruction
│  .tools(H.workspace("/project"))     │  ← sandboxed tools
│  .harness(permissions=..., sandbox=.)│  ← permission + sandbox
└──────────────────────────────────────┘
```

## 8 Patterns

### Pattern 1: Minimal harness -- agent + workspace tools

The simplest harness: an agent with sandboxed file/shell tools.

```python
from adk_fluent import Agent, H

agent = (
    Agent("coder", "gemini-2.5-flash")
    .instruct("You are a coding assistant. Help the user with their project.")
    .tools(H.workspace("/path/to/project"))
)
built = agent.build()
# 7 tools: read_file, edit_file, write_file, glob_search, grep_search, bash, list_dir
assert len(built.tools) == 7
```

### Pattern 2: Skilled harness -- agent + expertise + workspace

Agent with domain expertise from SKILL.md files plus workspace tools:

```python
agent = (
    Agent("reviewer", "gemini-2.5-pro")
    .use_skill("examples/skills/code_reviewer/")
    .instruct("Review the code in this project. Focus on security.")
    .tools(H.workspace(project, read_only=True))
)
built = agent.build()
# Skills go to static_instruction (cached, not re-sent every turn)
assert "<skills>" in (built.static_instruction or "")
assert "code_reviewer" in (built.static_instruction or "")
# Instruction is separate (per-task)
assert "security" in (built.instruction or "")
```

### Pattern 3: Multi-skill agent -- stacked expertise

Stack multiple skills for compound expertise:

```python
agent = (
    Agent("analyst", "gemini-2.5-pro")
    .use_skill("examples/skills/research_pipeline/")
    .use_skill("examples/skills/code_reviewer/")
    .instruct("Analyze this codebase for quality and maintainability.")
)
built = agent.build()
static = built.static_instruction or ""
# Both skills present, order preserved
assert "research_pipeline" in static
assert "code_reviewer" in static
assert static.index("research_pipeline") < static.index("code_reviewer")
```

### Pattern 4: Permission-gated harness

Dangerous tools require approval:

```python
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
# Permission callback is registered as before_tool_callback
assert built.before_tool_callback is not None
```

### Pattern 5: Skilled agents in a pipeline

Each agent in a pipeline can have different expertise:

```python
from adk_fluent import Agent

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
# Each agent has its own skill
assert "research_pipeline" in (built.sub_agents[0].static_instruction or "")
assert "code_reviewer" in (built.sub_agents[1].static_instruction or "")
```

### Pattern 6: Mixing L1 and L3 skill layers

Combine `.use_skill()` (L1 expertise) with `Skill()` builder (L3 recipe):

```python
from adk_fluent import Skill

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
```

### Pattern 7: Workspace tool isolation

Workspace tools are sandboxed to the project directory:

```python
tools = H.workspace("/path/to/project")
read_fn = [t for t in tools if t.__name__ == "read_file"][0]

# Can read inside workspace
result = read_fn("test.txt")  # OK

# Cannot read outside workspace
result = read_fn("/etc/hostname")
assert "Error" in result or "outside" in result
```

### Pattern 8: Full harness -- the Claude-Code-like pattern

The complete pattern combining skills + workspace + permissions + context:

```python
from adk_fluent._context import C

harness_agent = (
    Agent("coder", "gemini-2.5-pro")
    # L1: Domain expertise
    .use_skill("examples/skills/code_reviewer/")
    .use_skill("examples/skills/research_pipeline/")
    # Per-task instruction
    .instruct("You are an expert coding assistant. Use your skills and tools.")
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

# Full setup verified
assert "<skills>" in (built.static_instruction or "")
assert len(built.tools) == 7
assert built.before_tool_callback is not None
```

## Key Insight: Skills + Harness Composition

Skills provide **what the agent knows** (domain expertise, cached as static instructions). The harness provides **what the agent can do** (tools, permissions, sandbox). Together they create an autonomous agent that is both expert and safe:

```
Skills  →  static_instruction  →  Cached expertise (never re-sent)
Harness →  tools + callbacks   →  Sandboxed capabilities
Prompt  →  instruction         →  Per-task directive (changes each turn)
```

:::{seealso}
- [Skills User Guide](../../user-guide/skills.md) -- declarative agent packages
- [Harness User Guide](../../user-guide/harness.md) -- autonomous runtime building
- [Recipe 77: Skill-Based Agents](77_skill_based_agents.md) -- pure Skills patterns
- [Recipe 79: Coding Agent Harness](79_coding_agent_harness.md) -- full 5-layer harness
:::
