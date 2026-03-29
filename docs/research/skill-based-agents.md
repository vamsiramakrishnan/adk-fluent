# Skill-Based Agents in adk-fluent: Research & 100x Vision

> **Status**: Research / RFC
> **Date**: 2026-03-29
> **Branch**: `claude/skill-based-agents-research-NSzDc`

---

## 0. Industry Landscape: Skills Across Frameworks

### Skills vs Tools — The Critical Distinction

| Aspect | Tools | Skills |
|--------|-------|--------|
| **Nature** | Atomic functions (API calls) | Knowledge + workflow packages |
| **Mechanism** | Function calling (JSON-RPC) | Prompt/context injection |
| **Loading** | Always registered | On-demand (progressive disclosure) |
| **Token cost** | Schema always in context | Metadata only (~100 tokens); body on demand |
| **Reusability** | Per-framework | Cross-platform (agentskills.io standard) |
| **Composition** | Chain/parallel via orchestrator | Patterns compose patterns |
| **Analogy** | "What the agent **can do**" | "What the agent **knows how to do**" |

> "MCP gives your agent access to external tools and data. Skills teach your agent what to do with those tools and data."

### How Other Frameworks Handle Skills

| Framework | Unit Name | Key Pattern | Composition Model |
|-----------|-----------|-------------|-------------------|
| **Google ADK** | `SkillToolset` | Progressive disclosure (L1→L2→L3) | Dynamic tool gating via `adk_additional_tools` |
| **Semantic Kernel** | Plugins | `@kernel_function` on class methods | Planner auto-decomposes into multi-plugin plans |
| **LangChain** | Skills (agentskills.io) | MD files + subagent isolation | `create_deep_agent(skills=[...])` |
| **CrewAI** | Roles (agents) | Role-based metaphor with delegation | `Process.hierarchical` with manager agent |
| **AutoGen → MS Agent Framework** | `@ai_function` | Actor model, agent-as-tool | Graph-based workflows + MCP/A2A native |
| **A2A Protocol** | `AgentSkill` in AgentCard | JSON metadata for discovery | Per-skill auth, input/output modes |

### Google ADK SkillToolset — The Native Pattern

ADK's `SkillToolset` implements three-level progressive disclosure:

```
L1 — Metadata (~100 tokens)     Always in system prompt as XML index
L2 — Instructions (<5K tokens)  Loaded via load_skill(name) tool call
L3 — Resources (on demand)      Loaded via load_skill_resource(name, path)
```

The critical innovation: **skill-gated tool access**. Skills declare needed tools:
```yaml
metadata:
  adk_additional_tools: ["google_search", "code_interpreter"]
```
When a skill is activated, its tools become visible to the LLM. Deactivated → tools disappear. This means **skills control their own tool surface area**.

### Five Skill Design Patterns (ADK Community)

| # | Pattern | Description | Example |
|---|---------|-------------|---------|
| 1 | **Tool Wrapper** | Package library conventions as on-demand expertise | "How to use BigQuery best practices" |
| 2 | **Generator** | Produce structured output using reusable templates | "Generate Terraform config from spec" |
| 3 | **Reviewer** | Evaluate artifacts against a checklist with severity ratings | "Review PR against 12-point checklist" |
| 4 | **Inversion** | Agent interviews user through structured phases before acting | "Gather requirements → then design" |
| 5 | **Pipeline** | Sequential multi-step workflow with validation gates | "Research → Write → Review → Publish" |

Production systems typically combine 2-3 patterns.

### The agentskills.io Standard

Open standard (released Dec 2025), adopted by 30+ tools including Claude Code, Gemini CLI, GitHub Copilot, Cursor, OpenAI Codex, Windsurf, and more. Key fields:

| Field | Required | Constraints |
|-------|----------|-------------|
| `name` | Yes | Max 64 chars, lowercase + hyphens |
| `description` | Yes | Max 1024 chars |
| `allowed-tools` | No | Space-delimited pre-approved tools |
| `metadata` | No | Arbitrary key-value (including `adk_additional_tools`) |

**Cross-platform guarantee**: A skill authored for Claude Code works in ADK via `load_skill_from_dir()`, works in Gemini CLI, works in Cursor — same file, zero changes.

---

## 1. What Are Agent Skills Today?

Agent Skills (per [agentskills.io](https://agentskills.io)) are **portable knowledge packages** — Markdown files with YAML frontmatter that teach AI coding agents *how* to do things. They are consumed by tools like Claude Code, Gemini CLI, Cursor, Copilot, and Amp.

### Current Anatomy of a Skill File

```yaml
---
name: architect-agents
description: Design multi-agent systems with adk-fluent.
allowed-tools: Bash, Read, Glob, Grep
metadata:
  license: Apache-2.0
  author: vamsiramakrishnan
  version: "0.12.1"
---

# Architect Multi-Agent Systems with adk-fluent

## Step 1: Choose the right topology
...procedural knowledge...

## Step 2: Design the data flow
...code examples, decision tables...
```

### What adk-fluent Already Has

| Layer | What Exists | Where |
|-------|------------|-------|
| **Internal skills** | 14 skills for library development | `.claude/skills/`, `.gemini/skills/` |
| **Published skills** | 6 skills for agent developers | `skills/` (installable via `npx skills`) |
| **Shared references** | Auto-generated API surface, patterns, namespaces | `.claude/skills/_shared/references/` |
| **Helper scripts** | Validation, listing, deprecation checking | `.claude/skills/_shared/scripts/` |
| **Skill generator** | Reads `manifest.json` + `seed.toml` → generates references | `scripts/skill_generator.py` |

### Key Insight: Two Separate Worlds

Today, **skills live outside the runtime**. They're documentation that coding agents read. Meanwhile, **adk-fluent agents live inside the runtime** — they're Python objects with tools, state, and LLM calls. These two worlds don't talk to each other.

---

## 2. The 100x Vision: Skills as First-Class Runtime Constructs

What if a Skill wasn't just an MD file a coding agent reads, but a **composable runtime unit** that adk-fluent agents can discover, load, configure, and execute?

### The Conceptual Bridge

```
TODAY:
  MD Skill File → Coding Agent reads it → Coding Agent writes code → Code runs agents

100x FUTURE:
  MD Skill File → Skill() builder parses it → Produces configured agent graph → Runs directly
```

### The Three Layers

| Layer | Name | What It Does |
|-------|------|-------------|
| **L1** | Skill Authoring | Write skills as MD + YAML that declare agent topologies, not just prose |
| **L2** | Skill Runtime | `Skill()` builder that parses skill files into live adk-fluent agent graphs |
| **L3** | Skill Composition | Meta-patterns that wire multiple skills into orchestrated workflows |

---

## 3. Layer 1: Skill Authoring — The Extended Skill Format

Extend the agentskills.io format with an `agents` block that declares the topology:

```yaml
---
name: deep-research
description: Multi-source research with synthesis and citation
version: "1.0.0"
tags: [research, synthesis, citations]

# Standard agentskills.io fields
allowed-tools: Bash, Read, WebSearch, WebFetch

# NEW: Agent topology declaration
agents:
  researcher:
    model: gemini-2.5-flash
    instruct: |
      Research {topic} using available tools.
      Find primary sources and extract key findings.
    tools: [web_search, web_fetch]
    writes: findings

  fact_checker:
    model: gemini-2.5-flash
    instruct: |
      Verify the claims in {findings}.
      Flag any unsupported assertions.
    reads: [findings]
    writes: verified_findings

  synthesizer:
    model: gemini-2.5-pro
    instruct: |
      Synthesize {verified_findings} into a coherent report.
      Include citations for all claims.
    reads: [verified_findings]
    writes: report

topology: researcher >> fact_checker >> synthesizer

# Input/output contract
input:
  topic: str
output:
  report: str

# Evaluation criteria
eval:
  - prompt: "Research quantum computing advances in 2025"
    expect: "contains citations"
  - prompt: "Research climate policy in the EU"
    rubrics: ["Factual", "Cited", "Balanced"]
---

# Deep Research Skill

This skill performs multi-source research with fact-checking and synthesis.

## When to use
- User needs comprehensive research on a topic
- Citations and fact-checking are important
- Multiple perspectives are needed
```

### What's New vs Standard agentskills.io

| Field | Standard | Extended |
|-------|----------|----------|
| `name`, `description`, `tags` | Yes | Yes |
| `allowed-tools` | Yes | Yes |
| `agents:` block | No | **NEW** — declares agent topology |
| `topology:` | No | **NEW** — expression syntax for wiring |
| `input:` / `output:` | No | **NEW** — typed contract |
| `eval:` | No | **NEW** — inline evaluation cases |
| Markdown body | Prose for coding agents | Prose + documentation for humans |

### Backward Compatibility

Skills without `agents:` remain pure documentation — coding agents read them as before. The `agents:` block is opt-in. A skill can be BOTH documentation (for coding agents) AND executable (for adk-fluent runtime).

---

## 4. Layer 2: Skill Runtime — The `Skill()` Builder

### API Design

```python
from adk_fluent import Skill

# Load from file
research = Skill("skills/deep-research/SKILL.md")

# One-shot execution
result = research.ask("Research quantum computing advances in 2025")

# Compose with other builders
pipeline = research >> Agent("editor").instruct("Polish {report}.")

# Override at load time
research_fast = Skill("skills/deep-research/SKILL.md").model("gemini-2.5-flash")

# Inject dependencies
research_custom = (
    Skill("skills/deep-research/SKILL.md")
    .inject(web_search=my_search_fn, web_fetch=my_fetch_fn)
)
```

### Builder Methods

```python
class Skill(BuilderBase):
    """Load and configure a skill from an MD file."""

    def __init__(self, path: str | Path):
        """Parse YAML frontmatter + agents block."""

    # Overrides (applied to all agents in the skill)
    def model(self, model: str) -> Self: ...
    def inject(self, **resources) -> Self: ...
    def middleware(self, mw) -> Self: ...
    def guard(self, g) -> Self: ...
    def context(self, ctx) -> Self: ...

    # Override a specific agent within the skill
    def configure(self, agent_name: str, **overrides) -> Self: ...

    # Contract
    def input(self, **schema) -> Self: ...    # Override input contract
    def output(self, **schema) -> Self: ...   # Override output contract

    # Execution (inherited from BuilderBase)
    def build(self) -> ADKBaseAgent: ...
    def ask(self, prompt: str) -> str: ...
    def ask_async(self, prompt: str) -> str: ...

    # Introspection
    def explain(self) -> None: ...
    def topology(self) -> str: ...            # Mermaid diagram of internal agents
    def contract(self) -> dict: ...           # Input/output schema

    # Composition (all operators work)
    # >> | * // @
```

### How `build()` Works

```
SKILL.md
  → parse YAML frontmatter
  → extract agents: block
  → for each agent: create Agent() builder with instruct/model/tools/reads/writes
  → parse topology: expression (>> | * // @)
  → wire agents into Pipeline/FanOut/Loop
  → apply skill-level overrides (model, middleware, guards)
  → resolve tool references against inject() resources
  → return native ADK agent (SequentialAgent/ParallelAgent/LlmAgent)
```

---

## 5. Layer 3: Skill Composition — The Meta-Pattern

This is where the 100x multiplier lives. Skills compose with ALL existing adk-fluent operators:

### Pattern 1: Skill Chaining (`>>`)

```python
research = Skill("skills/deep-research/SKILL.md")
writing  = Skill("skills/technical-writing/SKILL.md")
review   = Skill("skills/code-review/SKILL.md")

pipeline = research >> writing >> review
result = pipeline.ask("Write a technical blog about RAG architectures")
```

Each skill is a black box with a contract (input/output). The `>>` operator wires `output` of one to `input` of the next via state keys.

### Pattern 2: Skill Fan-Out (`|`)

```python
web_research    = Skill("skills/web-research/SKILL.md")
paper_research  = Skill("skills/paper-research/SKILL.md")
patent_research = Skill("skills/patent-research/SKILL.md")

parallel = web_research | paper_research | patent_research
# All three run concurrently, results merged into state
```

### Pattern 3: Skill Loops (`*`)

```python
writer = Skill("skills/writing/SKILL.md")
critic = Skill("skills/critique/SKILL.md")

refined = (writer >> critic) * until(lambda s: s.get("quality") == "APPROVED", max=3)
```

### Pattern 4: Skill Fallback (`//`)

```python
fast_research = Skill("skills/quick-research/SKILL.md")
deep_research = Skill("skills/deep-research/SKILL.md")

research = fast_research // deep_research  # Try fast first, fall back to deep
```

### Pattern 5: Skill + Agent Mixing

```python
research = Skill("skills/deep-research/SKILL.md")

# Skill as a step in a larger agent pipeline
pipeline = (
    Agent("classifier").instruct("Classify the query.").writes("category")
    >> Route("category")
        .eq("research", research)
        .eq("coding", Skill("skills/code-gen/SKILL.md"))
        .otherwise(Agent("general").instruct("Handle general queries."))
)
```

### Pattern 6: Skill as AgentTool

```python
coordinator = (
    Agent("coordinator", "gemini-2.5-pro")
    .instruct("You have access to specialized skills. Use them as needed.")
    .agent_tool(Skill("skills/deep-research/SKILL.md"))
    .agent_tool(Skill("skills/code-review/SKILL.md"))
    .agent_tool(Skill("skills/data-analysis/SKILL.md"))
)
```

The coordinator LLM decides WHEN to invoke each skill, just like any other tool.

### Pattern 7: Skill Registry & Discovery

```python
from adk_fluent import SkillRegistry

# Load all skills from a directory
registry = SkillRegistry("skills/")

# Discovery
research_skills = registry.find(tags=["research"])
all_skills = registry.list()

# Dynamic tool loading (BM25-indexed)
agent = (
    Agent("assistant", "gemini-2.5-pro")
    .instruct("Help the user with any task.")
    .tools(T.search(registry))  # LLM discovers and loads skills on demand
)
```

### Pattern 8: Remote Skills (A2A Bridge)

```python
# A skill published as an A2A server
from adk_fluent import A2AServer, Skill

server = (
    A2AServer(Skill("skills/deep-research/SKILL.md"))
    .port(8001)
    .skill("research", "Deep Research", tags=["research"])
)

# Consumed remotely
remote_research = RemoteAgent("research", agent_card="http://research:8001/.well-known/agent.json")

# Or via Skill with remote source
remote = Skill("http://research:8001/.well-known/skill.md")  # Fetch & parse
```

### Pattern 9: Skill Presets

```python
from adk_fluent import Skill, Preset

# A skill that bundles configuration (not a full agent graph)
safety_preset = Skill("skills/safety-guardrails/SKILL.md").as_preset()

# Apply to any agent
agent = Agent("assistant").use(safety_preset)
# Equivalent to applying all the guards, middleware, and constraints declared in the skill
```

### Pattern 10: Meta-Skills (Skills that compose Skills)

```yaml
---
name: full-content-pipeline
description: End-to-end content creation pipeline

skills:
  research: deep-research          # Reference by name
  writing: technical-writing
  review: code-review
  publish: content-publishing

topology: research >> writing >> (review * until(approved)) >> publish

input:
  topic: str
  audience: str
output:
  published_url: str
---
```

A meta-skill references OTHER skills by name. The runtime resolves them from the registry.

---

## 6. Tabulated Comparison: Current vs Skill-Based

| Dimension | Today (Code-Only) | Skill-Based (100x) | Multiplier |
|-----------|-------------------|---------------------|------------|
| **Authoring** | Write Python code | Write YAML+MD (or Python) | 5x faster to author |
| **Reuse** | Copy-paste agent code | `Skill("path")` one-liner | 10x reuse |
| **Composition** | Manual wiring in Python | `>>`, `\|`, `*`, `//` on Skills | 3x fewer lines |
| **Discovery** | Read code / docs | `SkillRegistry.find(tags=)` | 10x discoverability |
| **Portability** | Python-only | MD files work in any agent framework | 5x portability |
| **Testing** | Write pytest manually | Inline `eval:` in skill file | 3x faster eval |
| **Sharing** | Publish PyPI package | `npx skills add` or URL | 10x distribution |
| **Documentation** | Separate from code | Skill IS the documentation | 2x maintainability |
| **Versioning** | Git + semver on package | Version in frontmatter + Git | 1.5x clarity |
| **Non-dev authoring** | Requires Python knowledge | YAML + natural language | 20x accessibility |

---

## 7. The Skill Lifecycle

```
                    ┌──────────────┐
                    │   AUTHOR     │
                    │  (YAML+MD)   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   PUBLISH    │
                    │ npx skills   │
                    │ Git / Registry│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼───────┐ ┌──▼──────────┐
       │  CODING     │ │ RUNTIME  │ │   A2A       │
       │  AGENT      │ │ Skill()  │ │ A2AServer() │
       │  reads MD   │ │ builder  │ │ publishes   │
       └─────────────┘ └────┬─────┘ └──────┬──────┘
                            │              │
                     ┌──────▼──────┐  ┌────▼──────┐
                     │  COMPOSE    │  │  REMOTE   │
                     │ >> | * //   │  │  CONSUME  │
                     └──────┬──────┘  └───────────┘
                            │
                     ┌──────▼──────┐
                     │  EXECUTE    │
                     │ .ask()      │
                     │ .stream()   │
                     │ adk web     │
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │  EVALUATE   │
                     │ inline eval │
                     │ E.suite()   │
                     └─────────────┘
```

---

## 8. Implementation Roadmap

### Phase 1: Skill Parser (Foundation)

| Task | Effort | Depends On |
|------|--------|------------|
| YAML frontmatter parser for `agents:` block | S | - |
| Topology expression parser (`>>`, `\|`, `*`) | M | Parser |
| `Skill.__init__(path)` — load and validate | S | Parser |
| `Skill.build()` — produce ADK agent graph | M | Parser, topology |
| `Skill.explain()` / `Skill.topology()` | S | Build |
| Contract validation (input/output schemas) | S | Parser |

### Phase 2: Composition (Core Value)

| Task | Effort | Depends On |
|------|--------|------------|
| Operator support (`>>`, `\|`, `*`, `//`, `@`) | S | Phase 1 |
| Skill + Agent mixing | S | Phase 1 |
| `.configure(agent_name, **overrides)` | M | Phase 1 |
| `.inject()` for tool resolution | M | Phase 1 |
| Skill as AgentTool (`.agent_tool(Skill(...))`) | S | Phase 1 |

### Phase 3: Registry & Discovery

| Task | Effort | Depends On |
|------|--------|------------|
| `SkillRegistry(path)` — directory scanner | M | Phase 1 |
| `registry.find(tags=, name=)` | S | Registry |
| `T.search(registry)` integration | M | Registry, T namespace |
| Remote skill loading (`Skill("http://...")`) | M | Phase 1 |

### Phase 4: Meta-Skills & Ecosystem

| Task | Effort | Depends On |
|------|--------|------------|
| `skills:` references in frontmatter (meta-skills) | M | Phase 3 |
| `Skill.as_preset()` | S | Phase 1 |
| `A2AServer(Skill(...))` bridge | S | Phase 1, A2A |
| Skill generator: emit `agents:` block from Python | L | All phases |
| `adk skill init` CLI scaffolding | M | Phase 1 |

**Effort key**: S = small (1-2 days), M = medium (3-5 days), L = large (1-2 weeks)

---

## 9. Design Decisions & Trade-offs

### Decision 1: YAML vs Python for topology

**Choice**: Support BOTH.

```yaml
# YAML (in SKILL.md)
topology: researcher >> fact_checker >> synthesizer
```

```python
# Python (programmatic)
Skill("research.md").topology(researcher >> fact_checker >> synthesizer)
```

YAML is more accessible; Python is more powerful. The YAML parser handles the common cases (`>>`, `|`, `* N`). Complex topologies (conditional routing, dynamic wiring) use Python.

### Decision 2: Tool resolution

Tools referenced in `agents.tools` are resolved in this order:
1. `.inject()` resources (explicit)
2. Built-in tools (`web_search` → `T.google_search()`)
3. Registry lookup (by name)
4. Fail with clear error

### Decision 3: Skill file location convention

```
skills/
  deep-research/
    SKILL.md           # The skill definition
    tools/             # Optional: custom tool implementations
      search.py
    tests/             # Optional: pytest-based tests
      test_skill.py
    fixtures/          # Optional: test fixtures
```

### Decision 4: Compatibility with agentskills.io

The `agents:` block is an adk-fluent extension. Standard agentskills.io consumers ignore unknown YAML keys. This means:
- A skill with `agents:` works in Claude Code (as documentation) AND in adk-fluent (as runtime)
- A skill WITHOUT `agents:` works everywhere (documentation only)
- No breaking changes to the standard

---

## 10. Example: Full Skill-Based Application

```python
from adk_fluent import Agent, Skill, SkillRegistry, Route

# Load skills
registry = SkillRegistry("skills/")

research   = Skill("skills/deep-research/SKILL.md")
coding     = Skill("skills/code-generation/SKILL.md")
analysis   = Skill("skills/data-analysis/SKILL.md")
writing    = Skill("skills/technical-writing/SKILL.md")

# Build the orchestrator
app = (
    Agent("orchestrator", "gemini-2.5-pro")
    .instruct("""
        You are a versatile assistant with specialized skills.
        Classify the user's request and delegate to the appropriate skill.
        For complex requests, chain multiple skills together.
    """)
    .agent_tool(research.describe("Deep multi-source research"))
    .agent_tool(coding.describe("Code generation and review"))
    .agent_tool(analysis.describe("Data analysis and visualization"))
    .agent_tool(writing.describe("Technical writing and editing"))
    .middleware(M.log() | M.cost() | M.retry(max_attempts=2))
    .guard(G.pii() | G.length(max=5000))
)

# Run
result = app.ask("Research the latest advances in quantum error correction and write a technical blog post")
```

**Lines of code**: ~20 (vs 200+ for equivalent hand-wired agent graph)

---

## 11. Why This Is 100x

| Without Skills | With Skills |
|---------------|-------------|
| Each team writes agents from scratch | Reuse community skills like npm packages |
| Agent topology locked in Python code | Topology declared in portable YAML |
| Non-developers can't author agents | Anyone who can write YAML can author a skill |
| Testing requires pytest setup | Inline eval cases in the skill file |
| Sharing requires PyPI packaging | `npx skills add author/skill` |
| Discovery requires reading source code | `SkillRegistry.find(tags=["research"])` |
| Composition requires understanding internals | `skill_a >> skill_b` just works |
| Documentation is separate from implementation | The skill file IS both |
| One agent framework, one ecosystem | Skills portable across frameworks |
| Local only | Skills → A2A servers with one line |

The compound effect: a **marketplace of composable agent skills** where the unit of sharing is not code, but capability. Each skill is simultaneously documentation (for humans and coding agents), a runtime construct (for adk-fluent), and a publishable artifact (for the ecosystem).

---

## 12. Bridging ADK SkillToolset — The Native Path

adk-fluent already has generated builders for `SkillToolset`, `LoadSkillTool`, and `LoadSkillResourceTool`. The fluent bridge makes these composable:

### T.skill() — Skill as Tool Composition

```python
from adk_fluent import Agent, T

# Load skills from directory (uses ADK's native SkillToolset)
agent = (
    Agent("assistant", "gemini-2.5-pro")
    .instruct("Help the user with any task. Load skills as needed.")
    .tools(T.skill("skills/"))                # All skills in directory
    .tools(T.skill("skills/deep-research/"))  # Single skill
)
```

`T.skill()` would wrap `SkillToolset` with fluent ergonomics:

```python
class T:
    @staticmethod
    def skill(
        path: str | Path | list[str],
        *,
        additional_tools: list | None = None,
        code_executor: Any | None = None,
    ) -> TComposite:
        """Wrap ADK SkillToolset as composable tool."""
        from google.adk.skills import load_skill_from_dir
        skills = [load_skill_from_dir(Path(p)) for p in _normalize(path)]
        toolset = SkillToolset(
            skills=skills,
            additional_tools=additional_tools or [],
            code_executor=code_executor,
        )
        return TComposite([toolset], kind="skill_toolset")
```

### Skill-Gated Tools in Fluent API

```python
# Skills that dynamically gate which tools are visible
research = Skill("skills/deep-research/SKILL.md")  # declares adk_additional_tools: [web_search]
coding = Skill("skills/code-gen/SKILL.md")          # declares adk_additional_tools: [code_interpreter]

agent = (
    Agent("assistant", "gemini-2.5-pro")
    .instruct("Use skills to help the user.")
    .tools(
        T.skill([research, coding],
                additional_tools=[web_search, code_interpreter])
    )
)
# web_search only visible when research skill is active
# code_interpreter only visible when coding skill is active
```

### Skill Presets from Native Skills

```python
# A skill file that only has configuration (no agents block)
# e.g., skills/safety-guardrails/SKILL.md with guards, middleware, constraints
safety = Skill("skills/safety-guardrails/SKILL.md").as_preset()

agent = Agent("assistant").use(safety)
# Applies: guards, middleware, constraints declared in the skill
```

---

## 13. Relationship Between Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SKILL ECOSYSTEM                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │  agentskills.io │   │  ADK SkillToolset│   │  adk-fluent      │  │
│  │  Standard       │   │  (Native)        │   │  Skill() Builder │  │
│  │                 │   │                  │   │                  │  │
│  │  MD + YAML      │──▶│  L1/L2/L3       │──▶│  Fluent API      │  │
│  │  Cross-platform │   │  Progressive    │   │  Composable      │  │
│  │  30+ tools      │   │  disclosure     │   │  >> | * // @     │  │
│  └────────┬────────┘   └────────┬────────┘   └────────┬─────────┘  │
│           │                     │                      │            │
│           ▼                     ▼                      ▼            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    SKILL FILE (SKILL.md)                     │    │
│  │                                                              │    │
│  │  Consumed by:                                                │    │
│  │  1. Coding agents (Claude Code, Gemini CLI) → as docs       │    │
│  │  2. ADK SkillToolset → as progressive disclosure tools      │    │
│  │  3. adk-fluent Skill() → as executable agent graph          │    │
│  │  4. A2AServer → as publishable remote capability            │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   COMPOSITION LAYER                           │   │
│  │                                                               │   │
│  │  Skill >> Skill          Pipeline of skills                   │   │
│  │  Skill | Skill           Parallel skills                      │   │
│  │  Skill * 3               Iterative skill                      │   │
│  │  Skill // Skill          Fallback skills                      │   │
│  │  Agent >> Skill >> Agent  Mixed pipelines                     │   │
│  │  .agent_tool(Skill)      Skill as tool                        │   │
│  │  SkillRegistry.find()    Discovery                            │   │
│  │  Meta-Skill(skills: {})  Skills that compose skills           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### The Same File, Four Consumers

A single `SKILL.md` file serves four purposes simultaneously:

| Consumer | What It Reads | What It Gets |
|----------|--------------|-------------|
| **Claude Code / Gemini CLI** | Frontmatter + markdown body | Documentation for coding agent |
| **ADK SkillToolset** | Frontmatter + body + resources | Progressive disclosure tools |
| **adk-fluent `Skill()`** | Frontmatter + `agents:` block + topology | Executable agent graph |
| **`A2AServer(Skill())`** | Everything above + network config | Remote-callable service |

The `agents:` block is the only extension. Without it, the file degrades gracefully to its other three roles.

---

## 14. Open Questions

1. **Schema inference**: Can we auto-infer input/output contracts from `reads`/`writes` in the agents block?
2. **Tool sandboxing**: Should skills run tools in a sandbox by default?
3. **Versioning**: How do we handle breaking changes in skill contracts?
4. **Caching**: Should parsed skills be cached (like compiled templates)?
5. **Hot reload**: Can skills be reloaded without restarting the runtime?
6. **Access control**: Should skills declare required permissions?
7. **Telemetry**: Should skills auto-instrument with `M.trace()`?
8. **Marketplace**: What does a skill marketplace look like beyond `npx skills`?
