# Skill-Based Agents -- Composable Skills from SKILL.md Files

:::{tip} What you'll learn
How to declare agent topologies in YAML, load them as `Skill()` builders, compose them with operators, inject tools, and discover skills via `SkillRegistry`. This is the **Skills Path** -- one of adk-fluent's [three development pathways](../../user-guide/index.md#three-pathways).
:::

_Source: `77_skill_based_agents.py`_ · **Pathway: Skills**

## Why Skills?

A single SKILL.md file serves **four purposes simultaneously**:

| Consumer | What happens |
|----------|-------------|
| **Claude Code / Gemini CLI** | Coding agent reads the prose and learns how to use the skill |
| **ADK SkillToolset** | Progressive disclosure -- LLM loads instructions on demand |
| **adk-fluent `Skill()`** | Parses `agents:` block into executable agent graph |
| **Humans reading GitHub** | Markdown renders as documentation |

Without skills, you maintain two artifacts (Python + README) that drift apart. With skills, one file cannot drift from itself.

## Architecture

```
              SKILL.md File
      ┌──────────────────────────┐
      │ ---                      │
      │ name: research_pipeline  │    parse_skill_file()
      │ agents:                  │ ──────────────────────►  SkillDefinition
      │   researcher: ...        │                               │
      │   writer: ...            │                               │
      │ topology: a >> b         │                               │
      │ ---                      │                               ▼
      │ # Documentation          │                         Skill("path/")
      │ Use when user needs...   │                               │
      └──────────────────────────┘                               │ .build()
                                                                 ▼
                                                        Native ADK Agent
                                                   (SequentialAgent, etc.)
```

## 11 Patterns

### Pattern 1: Load and run a skill

```python
from adk_fluent import Skill

skill = Skill("examples/skills/research_pipeline/")
built = skill.build()

# It's a real ADK SequentialAgent with 3 sub-agents
assert len(built.sub_agents) == 3
assert built.sub_agents[0].name == "researcher"
assert built.sub_agents[1].name == "fact_checker"
assert built.sub_agents[2].name == "synthesizer"
```

### Pattern 2: Override model for all agents

```python
skill = Skill("examples/skills/research_pipeline/").model("gemini-2.5-pro")
built = skill.build()
# All agents now use the overridden model
for agent in built.sub_agents:
    assert agent.model == "gemini-2.5-pro"
```

### Pattern 3: Inject tool implementations

Tools referenced by name in the YAML are resolved via `.inject()`:

```python
def my_search(query: str) -> str:
    """Custom web search implementation."""
    return f"Results for: {query}"

skill = Skill("examples/skills/research_pipeline/").inject(web_search=my_search)
built = skill.build()
# The researcher agent has the injected tool
```

### Pattern 4: Skill composition with `>>` (pipeline)

```python
research = Skill("examples/skills/research_pipeline/")
review = Skill("examples/skills/code_reviewer/")

# Skill >> Skill creates a Pipeline of skills
pipeline = research >> review
built = pipeline.build()
assert len(built.sub_agents) == 2
```

### Pattern 5: Skill + Agent mixing

```python
from adk_fluent import Agent

research = Skill("examples/skills/research_pipeline/")
editor = Agent("editor", "gemini-2.5-flash").instruct("Polish the report.")

pipeline = research >> editor
built = pipeline.build()
assert len(built.sub_agents) == 2
```

### Pattern 6: Skill as AgentTool (coordinator pattern)

The coordinator LLM decides **when** to invoke each skill:

```python
from adk_fluent import Agent

research = Skill("examples/skills/research_pipeline/")

coordinator = (
    Agent("coordinator", "gemini-2.5-pro")
    .instruct("You have access to a research skill. Use it when needed.")
    .agent_tool(research.describe("Deep multi-source research with citations"))
)
built = coordinator.build()
assert len(built.tools) > 0
```

### Pattern 7: Fan-out parallel skills

```python
research = Skill("examples/skills/research_pipeline/")
review = Skill("examples/skills/code_reviewer/")

parallel = research | review
built = parallel.build()
assert len(built.sub_agents) == 2
```

### Pattern 8: Skill registry and discovery

```python
from adk_fluent import SkillRegistry

registry = SkillRegistry("examples/skills/")

# List all skills
all_skills = registry.list()
assert len(all_skills) >= 2

# Find by tags
research_skills = registry.find(tags=["research"])
assert len(research_skills) >= 1

# Get by name
skill = registry.get("research_pipeline")
```

### Pattern 9: Introspection

```python
skill = Skill("examples/skills/research_pipeline/")

# Topology expression
assert skill.topology_expr() == "researcher >> fact_checker >> synthesizer"

# Input/output contract
contract = skill.contract()
assert contract["input"] == {"topic": "str"}
assert contract["output"] == {"report": "str"}
```

### Pattern 10: Configure specific agent within skill

```python
skill = Skill("examples/skills/research_pipeline/").configure(
    "synthesizer", model="gemini-2.5-pro"
)
built = skill.build()
assert built.sub_agents[2].model == "gemini-2.5-pro"
```

### Pattern 11: FanOut topology from SKILL.md

Skills can declare parallel topology in their YAML `topology:` field:

```python
skill = Skill("examples/skills/code_reviewer/")
built = skill.build()

# (analyzer | style_checker | security_auditor) >> summarizer
# = Pipeline with 2 sub_agents: FanOut and summarizer
assert len(built.sub_agents) == 2
fanout = built.sub_agents[0]
assert len(fanout.sub_agents) == 3
```

## SKILL.md File Format

```yaml
---
name: research_pipeline
description: Multi-step research with fact-checking and synthesis.
version: "1.0.0"
tags: [research, synthesis, citations]

agents:
  researcher:
    model: gemini-2.5-flash
    instruct: |
      Research {topic} thoroughly.
      Find primary sources and extract key findings.
    tools: [web_search]
    writes: findings

  fact_checker:
    model: gemini-2.5-flash
    instruct: |
      Verify the claims in {findings}.
      Flag unsupported assertions.
    reads: [findings]
    writes: verified_findings

  synthesizer:
    model: gemini-2.5-pro
    instruct: |
      Synthesize {verified_findings} into a coherent report
      with citations.
    reads: [verified_findings]
    writes: report

topology: researcher >> fact_checker >> synthesizer

input:
  topic: str
output:
  report: str
---

# Research Pipeline

Use when the user needs comprehensive research with citations.
```

## When to Use Skills vs Pipeline Python

| Scenario | Use Skills | Use Pipeline Python |
|----------|-----------|-------------------|
| Topology is stable, variation is in prompts/models | Yes | Overkill |
| Domain experts (non-Python) own the agent logic | Yes | No |
| Sharing capabilities across teams | Yes | Harder |
| Complex conditional routing, dynamic tool registration | No | Yes |
| Deep callback customization | No | Yes |
| One-off agents that won't be reused | No | Yes |

:::{seealso}
- [Skills User Guide](../../user-guide/skills.md) -- full reference
- [Example SKILL.md files](../../../examples/skills/) -- research_pipeline, code_reviewer
- [Three Pathways](../../user-guide/index.md#three-pathways) -- how Skills fits into the bigger picture
:::
