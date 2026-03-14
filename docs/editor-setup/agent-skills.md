# Agent Skills

adk-fluent ships **8 agent skills** that follow the open [Agent Skills](https://agentskills.io) standard. These skills teach AI coding agents how to develop, test, debug, and maintain adk-fluent projects — going beyond rules files by providing step-by-step procedures, runnable helper scripts, and auto-generated reference data.

## What are Agent Skills?

Agent Skills are portable knowledge packages for AI coding agents. Each skill is a directory containing a `SKILL.md` file (YAML frontmatter + Markdown instructions) plus optional `references/` and `scripts/` directories. They are supported by 30+ agent platforms including Claude Code, Gemini CLI, Cursor, GitHub Copilot, and OpenAI Codex.

Skills use **progressive disclosure**:

1. **Metadata** (~100 tokens) — loaded at startup for all skills
2. **Instructions** (<5000 tokens) — loaded when the skill activates
3. **References & scripts** — loaded on demand during execution

## Available Skills

### Development workflow

| Skill | Description | When it activates |
|-------|-------------|-------------------|
| `develop-feature` | Implement new builder methods, namespace functions, patterns, or operators | Adding new capabilities to the library |
| `write-tests` | Write tests using `.mock()`, contract checking, and namespace patterns | Adding test coverage for new or existing features |
| `add-cookbook` | Create runnable cookbook examples (pytest files with `.mock()`) | Adding new examples or tutorials |
| `debug-builder` | Debug builder issues — build failures, contracts, state flow | A builder isn't working as expected |

### Code quality

| Skill | Description | When it activates |
|-------|-------------|-------------------|
| `review-pr` | PR review with adk-fluent-specific checks (deprecated methods, import hygiene, generated file protection) | Reviewing pull requests |
| `architect-agents` | Design multi-agent systems — topology selection, data flow, context engineering | Planning agent workflows |

### Infrastructure

| Skill | Description | When it activates |
|-------|-------------|-------------------|
| `codegen-pipeline` | Run the code generation pipeline (scan → seed → generate) | Regenerating builders from ADK |
| `upgrade-adk` | Upgrade to a new ADK version with impact analysis | New ADK version released |

### Shared resources

All skills share auto-generated reference files and helper scripts in `_shared/`:

| Resource | Contents |
|----------|----------|
| `references/api-surface.md` | Complete builder method inventory organized by concern |
| `references/deprecated-methods.md` | Deprecated method mappings extracted from seed.manual.toml |
| `references/builder-inventory.md` | 132 builders across 9 modules |
| `references/patterns-and-primitives.md` | Pattern function signatures |
| `references/namespace-methods.md` | All S, C, P, A, M, T, E, G methods |
| `references/generated-files.md` | Generated vs hand-written file classification |
| `references/development-commands.md` | All justfile commands |
| `scripts/check-deprecated.py` | Scan code for deprecated method usage |
| `scripts/validate-imports.py` | Check for internal module imports |
| `scripts/list-builders.py` | Print builder inventory from manifest |
| `scripts/list-generated-files.py` | Classify generated vs hand-written files |

These references are regenerated from `manifest.json` and `seed.toml` by `scripts/skill_generator.py`, so they never go stale.

## Installing Skills

### If you cloned the repo

Skills are already in place. Claude Code reads from `.claude/skills/`, Gemini CLI reads from `.gemini/skills/`. Nothing to do.

### If you installed via pip

Skills are not included in the pip package. Copy them from the repository:

::::{tab-set}
:::{tab-item} Claude Code
```bash
# Clone skills into your project
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/vamsiramakrishnan/adk-fluent.git /tmp/adk-fluent-skills
cd /tmp/adk-fluent-skills && git sparse-checkout set .claude/skills

# Copy to your project
cp -r /tmp/adk-fluent-skills/.claude/skills/ .claude/skills/
rm -rf /tmp/adk-fluent-skills
```
:::
:::{tab-item} Gemini CLI
```bash
# Clone skills into your project
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/vamsiramakrishnan/adk-fluent.git /tmp/adk-fluent-skills
cd /tmp/adk-fluent-skills && git sparse-checkout set .gemini/skills

# Copy to your project
cp -r /tmp/adk-fluent-skills/.gemini/skills/ .gemini/skills/
rm -rf /tmp/adk-fluent-skills
```
:::
:::{tab-item} One-liner (Claude Code)
```bash
curl -sL https://github.com/vamsiramakrishnan/adk-fluent/archive/refs/heads/master.tar.gz \
  | tar xz --strip-components=1 "adk-fluent-master/.claude/skills"
```
:::
::::

### Via skillpm (npm-based package manager)

[skillpm](https://www.npmjs.com/package/skillpm) is a package manager built on npm for distributing Agent Skills across platforms.

```bash
npx skillpm install adk-fluent-skills
```

:::{note}
The `adk-fluent-skills` npm package is not yet published. See [Publishing Skills](#publishing-skills) below for how to set this up.
:::

## Using Skills

Once installed, skills activate automatically based on context. For example:

- Ask Claude Code to "add a new builder method for retry logic" → `develop-feature` skill activates
- Ask "review this PR" → `review-pr` skill activates with automated checks
- Ask "design a customer support triage system" → `architect-agents` skill activates

Skills provide the agent with:

- **Step-by-step procedures** — not just what to do, but the exact sequence
- **Helper scripts** — runnable checks the agent can execute (e.g., scan for deprecated methods)
- **Reference data** — auto-generated from the same sources as the codebase, always current

### Example: PR review with automated checks

When the `review-pr` skill activates, the agent automatically runs:

```bash
# Scan for deprecated method usage
uv run .claude/skills/_shared/scripts/check-deprecated.py src/ tests/ examples/

# Check for internal module imports
uv run .claude/skills/_shared/scripts/validate-imports.py src/ tests/ examples/

# Verify no generated files were hand-edited
just check-gen
```

Then applies the 12-point review checklist covering generated file protection, import hygiene, test coverage, backward compatibility, type safety, and security.

## Keeping Skills Updated

Skills reference data is auto-generated by `scripts/skill_generator.py` from the same `manifest.json` and `seed.toml` that power the rest of the codegen pipeline.

```bash
# Regenerate skill references
just skills

# Or as part of the full pipeline
just all    # scan → seed → generate → docs → skills → docs-build
```

The generated references update automatically when:
- A new ADK version changes the builder inventory
- Deprecated methods are added or removed in `seed.manual.toml`
- New patterns or namespace methods are added to the source code
- The justfile targets change

## Publishing Skills

To publish adk-fluent skills for installation via `skillpm` or other registries:

### 1. Add a `package.json`

```json
{
  "name": "adk-fluent-skills",
  "version": "1.0.0",
  "description": "Agent skills for developing with adk-fluent",
  "keywords": ["agent-skill"],
  "license": "MIT",
  "repository": "vamsiramakrishnan/adk-fluent"
}
```

### 2. Create a canonical `skills/` directory

Structure the skills following the Agent Skills spec:

```
skills/
├── develop-feature/
│   └── SKILL.md
├── write-tests/
│   └── SKILL.md
├── architect-agents/
│   └── SKILL.md
├── review-pr/
│   └── SKILL.md
├── debug-builder/
│   └── SKILL.md
├── add-cookbook/
│   └── SKILL.md
└── _shared/
    ├── references/
    └── scripts/
```

### 3. Publish to npm

```bash
npm publish
```

Users then install with:

```bash
npx skillpm install adk-fluent-skills
```

skillpm auto-detects the user's installed agents (Claude Code, Cursor, Gemini CLI, etc.) and copies skills to the correct directories.

### 4. Add frontmatter metadata for registries

Each SKILL.md should include publishing metadata:

```yaml
---
name: architect-agents
description: Design multi-agent systems with adk-fluent.
license: MIT
compatibility: Requires Python 3.11+ and adk-fluent installed
metadata:
  author: adk-fluent-contributors
  version: "1.0"
---
```

## Skill architecture

```{mermaid}
graph TD
    M[manifest.json] --> SG[skill_generator.py]
    S[seed.toml] --> SG
    SC[Source code] --> SG
    GA[.gitattributes] --> SG
    JF[justfile] --> SG

    SG --> CR[".claude/skills/_shared/references/"]
    SG --> CS[".claude/skills/_shared/scripts/"]
    SG --> GR[".gemini/skills/_shared/references/"]
    SG --> GS[".gemini/skills/_shared/scripts/"]

    SK1["SKILL.md (hand-written)"] --> |procedures| Agent
    CR --> |on-demand references| Agent
    CS --> |runnable checks| Agent

    style SG fill:#4f46e5,color:#fff
    style SK1 fill:#7c3aed,color:#fff
    style Agent fill:#059669,color:#fff
```

The generator reads the same data sources as `llms_generator.py` and follows the same parse → resolve → emit pattern. SKILL.md files stay hand-written (procedures and judgment), while reference data is always auto-generated.
