# Skills -- Composable Agent Packages

**Skills** turn YAML + Markdown into executable agent graphs. Instead of writing Python code for every agent topology, you declare agents and their wiring in a `SKILL.md` file and load it with `Skill("path/")`. The same file that documents your agent system for humans and coding agents also runs as a live adk-fluent pipeline.

## Why Skills?

| Without Skills | With Skills |
|---------------|-------------|
| Write Python for each agent topology | Declare topology in YAML, load with one line |
| Agent logic locked in code | Portable across frameworks (agentskills.io) |
| Non-developers can't author agents | Anyone who writes YAML can author a skill |
| Documentation separate from implementation | The skill file IS the documentation |
| Share via PyPI packages | Share via `npx skills add` or Git |
| Discover by reading source code | `SkillRegistry.find(tags=["research"])` |

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
    .tools(T.skill("skills/"))
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

# Print configuration summary
skill.explain()
# Skill: research_pipeline
#   Description: Multi-step research with fact-checking and synthesis.
#   Version: 1.0.0
#   Tags: research, synthesis, citations
#   Agents: researcher, fact_checker, synthesizer
#   Topology: researcher >> fact_checker >> synthesizer
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

See [Example 77 -- Skill-Based Agents](../../examples/cookbook/77_skill_based_agents.py) for 12 runnable patterns covering all the concepts above.

Example skill files:
- [`examples/skills/research_pipeline/SKILL.md`](../../examples/skills/research_pipeline/SKILL.md) -- Sequential pipeline
- [`examples/skills/code_reviewer/SKILL.md`](../../examples/skills/code_reviewer/SKILL.md) -- Parallel fan-out with merge
