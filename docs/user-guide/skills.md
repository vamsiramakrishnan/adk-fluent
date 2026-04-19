# Skills -- Composable Agent Packages

**Skills** turn YAML + Markdown into executable agent graphs. Instead of writing Python code for every agent topology, you declare agents and their wiring in a `SKILL.md` file and load it with `Skill("path/")`. The same file that documents your agent system for humans and coding agents also runs as a live adk-fluent pipeline.

## When Skills Make Life Easy

Skills aren't always the right tool. Here are the five scenarios where they provide a step change — and the anti-patterns where you should stick with Python.

### 1. Your team has domain experts who aren't Python developers

A product manager, researcher, or domain specialist can author this:

```yaml
agents:
  classifier:
    instruct: |
      Classify the customer issue into: billing, technical, account.
      Be precise — routing depends on your classification.
    writes: category
  billing_handler:
    instruct: Handle billing issues with empathy. Offer refund if appropriate.
  technical_handler:
    instruct: Diagnose the technical problem step by step.
topology: classifier >> (billing_handler | technical_handler)
```

They don't need to know what `BuilderBase` is, what `.reads()` vs `.writes()` means in Python, or how `SequentialAgent` wiring works. They write instructions and topology in a format they already understand from config files. An engineer reviews the YAML and deploys it.

**Without skills**, the domain expert writes a requirements doc, an engineer translates it to Python, the domain expert reviews the Python they can't fully read, and every prompt tweak requires an engineer round-trip.

### 2. You're building a library of reusable capabilities

You have 15 agent topologies across your organization. Without skills:

```python
# team_a/agents/research.py — 45 lines
# team_b/agents/research.py — 52 lines (slightly different copy)
# team_c/research_utils.py  — 38 lines (yet another copy)
```

With skills:

```python
# One shared skill file, three consumers
research = Skill("shared_skills/research_pipeline/")

# Team A: use as-is
team_a = research.ask("Research quantum computing")

# Team B: stronger model
team_b = research.model("gemini-2.5-pro").ask("Research quantum computing")

# Team C: custom search tool
team_c = research.inject(web_search=internal_search).ask("Research quantum computing")
```

The skill is the **single source of truth**. Teams customize at load time with `.model()`, `.inject()`, `.configure()` — without forking the code.

### 3. You're composing agent systems from existing pieces

This is where the multiplier is largest. You have working skills and want to assemble them into larger systems:

```python
# Without skills: 80+ lines of Python wiring
researcher = Agent("researcher", "gemini-2.5-flash").instruct("...").writes("findings")
fact_checker = Agent("fact_checker", "gemini-2.5-flash").instruct("...").reads("findings").writes("verified")
writer = Agent("writer", "gemini-2.5-pro").instruct("...").reads("verified").writes("draft")
critic = Agent("critic", "gemini-2.5-flash").instruct("...").reads("draft").writes("quality")
editor = Agent("editor", "gemini-2.5-pro").instruct("...").reads("draft")

pipeline = researcher >> fact_checker >> writer >> (writer >> critic) * 3 >> editor
```

```python
# With skills: 3 lines
pipeline = (
    Skill("skills/research_pipeline/")
    >> (Skill("skills/writing/") >> Skill("skills/critique/")) * 3
    >> Skill("skills/editing/")
)
```

Each skill is a tested, documented black box. You compose at the skill level — not the agent level.

### 4. You want the same file to be docs AND runtime

A `SKILL.md` file is simultaneously consumed by:

| Consumer | What happens |
|----------|-------------|
| **Claude Code / Gemini CLI** | Coding agent reads the prose and learns how to use the skill |
| **ADK SkillToolset** | Progressive disclosure — LLM loads instructions on demand |
| **adk-fluent `Skill()`** | Parses `agents:` block into executable agent graph |
| **Humans reading GitHub** | Markdown renders as documentation |

Without skills, you maintain two artifacts: a Python file and a separate README explaining it. They drift apart. With skills, there is one file and it cannot drift from itself.

### 5. You need rapid prototyping with instant feedback

When you're iterating on prompt design, skills let you edit YAML and re-run without touching Python:

```bash
# Edit the YAML
vim skills/research_pipeline/SKILL.md

# Re-run immediately — no code changes
python -c "from adk_fluent import Skill; print(Skill('skills/research_pipeline/').ask('test'))"
```

Compare this to editing Python files, re-importing modules, dealing with class definitions — skills collapse the edit-run loop.

### When NOT to use skills

Skills are the wrong choice when:

| Scenario | Use instead |
|----------|-------------|
| **Complex conditional logic** in agent wiring (if/else, dynamic routing beyond `Route`) | Python with `conditional()`, `gate()`, custom predicates |
| **Dynamic tool registration** that changes per request | Python with runtime `.tool()` calls |
| **Agents that need deep callback customization** (custom `before_model`, `after_tool` with complex state) | Python with explicit callback functions |
| **Single-use, one-off agents** that won't be reused | Inline `Agent()` builder — no file needed |
| **Performance-critical inner loops** where parsing YAML adds overhead | Pre-built Python agents |

**Rule of thumb**: If the topology is stable and the main variation is in prompts, models, and tools — use a skill. If the topology itself changes dynamically — use Python.

## Architecture

```
                SKILL.md File
        ┌──────────────────────────┐
        │ ---                      │
        │ name: research_pipeline  │    parse_skill_file()
        │ agents:                  │ ────────────────────────►  SkillDefinition
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

**Three components:**

| Component | Role | Description |
|-----------|------|-------------|
| `Skill` | Builder | Load, configure, and compose a skill from a SKILL.md file |
| `SkillRegistry` | Discovery | Scan directories for skills, find by name/tags |
| `T.skill()` | Tool wrapper | Wrap ADK's native `SkillToolset` for progressive disclosure |

## Writing a Skill File

A skill file is standard [agentskills.io](https://agentskills.io) format extended with an `agents:` block:

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

### Skill File Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Skill identifier (lowercase, underscores OK) |
| `description` | Yes | What the skill does and when to use it |
| `version` | No | Semantic version |
| `tags` | No | Discovery tags (`[research, web]`) |
| `agents` | No | Agent topology declaration (adk-fluent extension) |
| `topology` | No | Expression wiring agents (`a >> b`, `a \| b`, `a * 3`) |
| `input` | No | Input contract (key: type pairs) |
| `output` | No | Output contract (key: type pairs) |
| `eval` | No | Inline evaluation cases |
| `metadata` | No | Arbitrary key-value pairs |
| Markdown body | No | Documentation for humans and coding agents |

### Agent Definition Fields

Each agent in the `agents:` block supports:

| Field | Description | Example |
|-------|-------------|---------|
| `model` | LLM model (default: `gemini-2.5-flash`) | `gemini-2.5-pro` |
| `instruct` | System prompt with `{key}` template variables | `Research {topic}.` |
| `tools` | Tool names (resolved via `.inject()` or built-ins) | `[web_search]` |
| `reads` | State keys to inject as context | `[findings]` |
| `writes` | State key to store the agent's output | `report` |
| `describe` | Description for transfer routing | `Research specialist` |

### Topology Expressions

The `topology:` field uses the same operators as Python expressions:

| Expression | Meaning | ADK Result |
|-----------|---------|------------|
| `a >> b >> c` | Sequential pipeline | `SequentialAgent` |
| `a \| b \| c` | Parallel fan-out | `ParallelAgent` |
| `a * 3` | Loop 3 iterations | `LoopAgent` |
| `(a \| b) >> c` | Fan-out then merge | Pipeline with nested FanOut |
| `(a >> b) * 3` | Loop a pipeline | Loop with nested Pipeline |

If no `topology:` is specified, agents run in **definition order** as a pipeline.

### Backward Compatibility

Skills without an `agents:` block work everywhere as pure documentation -- Claude Code, Gemini CLI, Cursor, and 30+ other tools. The `agents:` block is an opt-in extension. A skill file can be **both** documentation and an executable agent graph.

## Loading and Running Skills

### Basic Usage

```python
from adk_fluent import Skill

# Load from directory (looks for SKILL.md inside)
skill = Skill("skills/research_pipeline/")

# Load from file path directly
skill = Skill("skills/research_pipeline/SKILL.md")

# Build into native ADK agent
agent = skill.build()

# One-shot execution
result = skill.ask("Research quantum computing advances")

# Async execution
result = await skill.ask_async("Research quantum computing")
```

### Model Override

Override the model for **all** agents in the skill:

```python
# Use a stronger model for the entire skill
fast = Skill("skills/research_pipeline/").model("gemini-2.5-flash")
pro  = Skill("skills/research_pipeline/").model("gemini-2.5-pro")
```

### Per-Agent Configuration

Override settings for a **specific** agent:

```python
skill = (
    Skill("skills/research_pipeline/")
    .configure("synthesizer", model="gemini-2.5-pro")
    .configure("researcher", model="gemini-2.5-flash")
)
```

### Tool Injection

Tools referenced by name in `agents.tools` are resolved via `.inject()`:

```python
def my_search(query: str) -> str:
    """Custom web search implementation."""
    return requests.get(f"https://api.search.com/?q={query}").text

skill = Skill("skills/research_pipeline/").inject(web_search=my_search)
```

Resolution order:
1. `.inject()` resources (explicit)
2. Built-in ADK tools (`google_search`)
3. Skipped (fails at runtime if the agent needs it)

## Composing Skills

Skills extend `BuilderBase` -- **all operators work** exactly like agents:

### Pipeline (`>>`)

```python
research = Skill("skills/research_pipeline/")
writing  = Skill("skills/technical_writing/")
review   = Skill("skills/code_review/")

pipeline = research >> writing >> review
result = pipeline.ask("Write a blog about RAG architectures")
```

### Parallel (`|`)

```python
web = Skill("skills/web_research/")
papers = Skill("skills/paper_research/")

parallel = web | papers
# Both run concurrently, results merged into state
```

### Loop (`*`)

```python
writer = Skill("skills/writing/")
critic = Skill("skills/critique/")

from adk_fluent import until
refined = (writer >> critic) * until(lambda s: s.get("quality") == "APPROVED", max=3)
```

### Fallback (`//`)

```python
fast = Skill("skills/quick_research/")
deep = Skill("skills/deep_research/")

research = fast // deep  # Try fast first, fall back to deep
```

### Skill + Agent Mixing

```python
from adk_fluent import Agent, Route

research = Skill("skills/research_pipeline/")

pipeline = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the query into: research, coding, general.")
    .writes("category")
    >> Route("category")
        .eq("research", research)
        .eq("coding", Skill("skills/code_gen/"))
        .otherwise(Agent("general", "gemini-2.5-flash").instruct("Help the user."))
)
```

### Skill as AgentTool

The coordinator LLM decides **when** to invoke each skill:

```python
coordinator = (
    Agent("coordinator", "gemini-2.5-pro")
    .instruct("You have specialized skills. Use them as needed.")
    .agent_tool(Skill("skills/research_pipeline/").describe("Deep research"))
    .agent_tool(Skill("skills/code_review/").describe("Code review"))
    .agent_tool(Skill("skills/data_analysis/").describe("Data analysis"))
)
```

## Skill Discovery

### SkillRegistry

Scan a directory tree for skills and discover them by name or tags:

```python
from adk_fluent import SkillRegistry

registry = SkillRegistry("skills/")

# List all skills
for info in registry.list():
    print(f"{info['name']}: {info['description']} (tags: {info['tags']})")

# Find by tags
research_skills = registry.find(tags=["research"])

# Find by name substring
code_skills = registry.find(name="code")

# Get a specific skill by exact name
skill = registry.get("research_pipeline")

# Check if a skill exists
if "research_pipeline" in registry:
    print("Found it!")
```

### Registry API

| Method | Description |
|--------|-------------|
| `SkillRegistry(path)` | Scan directory recursively for SKILL.md files |
| `.list()` | All skills with metadata (name, description, tags, path) |
| `.find(tags=, name=)` | Filter by tags (all must match) or name substring |
| `.get(name)` | Get Skill builder by exact name (raises `KeyError`) |
| `.names()` | Sorted list of all skill names |
| `len(registry)` | Number of discovered skills |
| `name in registry` | Check if a skill exists |

## ADK Native SkillToolset (`T.skill()`)

For ADK's native progressive disclosure pattern (L1/L2/L3), use `T.skill()`:

```python
from adk_fluent import Agent, T

agent = (
    Agent("assistant", "gemini-2.5-pro")
    .instruct("Help the user. Load skills as needed.")
    .tools(T.skill("skills/research_pipeline/"))
)
```

This wraps ADK's `SkillToolset` which provides:
- **L1 -- Metadata** (~100 tokens): Always in system prompt as XML index
- **L2 -- Instructions**: Loaded on demand via `load_skill()` tool call
- **L3 -- Resources**: Loaded via `load_skill_resource()` on demand

The LLM decides when to activate a skill -- its tools become visible only while the skill is active.

### T.skill() vs Skill()

| | `T.skill()` | `Skill()` |
|---|---|---|
| **Purpose** | Native ADK progressive disclosure | Fluent builder for agent graphs |
| **Mechanism** | LLM loads skill instructions on demand | Parses `agents:` block into Pipeline/FanOut/Loop |
| **Requires** | ADK `SkillToolset` (google-adk) | Only adk-fluent |
| **Best for** | Many skills, LLM picks which to use | Predetermined topology, compose with operators |

## Introspection

```python
skill = Skill("skills/research_pipeline/")

# View the topology expression
skill.topology_expr()
# → "researcher >> fact_checker >> synthesizer"

# View the input/output contract
skill.contract()
# → {"input": {"topic": "str"}, "output": {"report": "str"}}

# Print configuration summary (inherited from BuilderBase)
skill.explain()
# Returns a multi-line summary of builder state
```

## Skill Builder API Reference

| Method | Description |
|--------|-------------|
| `Skill(path)` | Load and parse a SKILL.md file |
| `.model(str)` | Override model for ALL agents in the skill |
| `.inject(**tools)` | Inject tool implementations by name |
| `.configure(name, **kw)` | Override settings for a specific agent |
| `.describe(str)` | Set/override skill description |
| `.build()` | Produce native ADK agent graph |
| `.ask(prompt)` | One-shot sync execution |
| `.ask_async(prompt)` | One-shot async execution |
| `.stream(prompt)` | Async streaming |
| `.session()` | Multi-turn chat |
| `.topology_expr()` | Return the topology expression string |
| `.contract()` | Return input/output schema |
| `.explain()` | Print configuration summary |
| `.mock(responses)` | Replace LLM with canned responses |
| `.test(prompt, contains=)` | Inline smoke test |

All operators: `>>` (pipeline), `|` (parallel), `*` (loop), `//` (fallback), `@` (schema)

## Best Practices

1. **Use valid Python identifiers for skill names** -- ADK requires agent names without hyphens. Use underscores: `research_pipeline`, not `research-pipeline`.

2. **Declare `topology:` explicitly** -- don't rely on definition order. Explicit wiring is clearer and supports fan-out/loop patterns.

3. **Use `.inject()` for external tools** -- keep skills self-contained. Tool implementations are injected at load time, not baked into the YAML.

4. **Use `.configure()` sparingly** -- if you're overriding every agent, you're fighting the skill. Write a new one instead.

5. **Keep skills focused** -- one skill = one capability. Compose multiple skills with `>>` and `|` rather than making one giant skill.

6. **Write the markdown body** -- the prose below `---` serves as documentation for coding agents and humans. A skill without documentation is just configuration.

7. **Add `eval:` cases** -- inline evaluation cases document expected behavior and can be used with `E.suite()` for automated testing.

8. **Use `tags:` for discovery** -- `SkillRegistry.find(tags=["research"])` only works if skills are tagged consistently.

## Cookbook Examples

See [Example 77 -- Skill-Based Agents](../../python/examples/cookbook/77_skill_based_agents.py) for 12 runnable patterns covering all the concepts above.

Example skill files:
- [`python/examples/skills/research_pipeline/SKILL.md`](../../python/examples/skills/research_pipeline/SKILL.md) -- Sequential pipeline
- [`python/examples/skills/code_reviewer/SKILL.md`](../../python/examples/skills/code_reviewer/SKILL.md) -- Parallel fan-out with merge
