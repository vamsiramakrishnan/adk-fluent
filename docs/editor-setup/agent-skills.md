# Agent Skills

adk-fluent ships **14 agent skills** that follow the open [Agent Skills](https://agentskills.io) standard. These skills teach AI coding agents how to develop, test, debug, deploy, evaluate, and maintain adk-fluent projects — going beyond rules files by providing step-by-step procedures, runnable helper scripts, and auto-generated reference data.

## What are Agent Skills?

Agent Skills are portable knowledge packages for AI coding agents. Each skill is a directory containing a `SKILL.md` file (YAML frontmatter + Markdown instructions) plus optional `references/` and `scripts/` directories. They are supported by 30+ agent platforms including Claude Code, Gemini CLI, Cursor, GitHub Copilot, and OpenAI Codex.

Skills use **progressive disclosure**:

1. **Metadata** (~100 tokens) — loaded at startup for all skills
2. **Instructions** (<5000 tokens) — loaded when the skill activates
3. **References & scripts** — loaded on demand during execution

## Available Skills

### Agent development lifecycle

These skills cover the full journey from design to production.

| Skill | Why it exists | When it activates |
|-------|---------------|-------------------|
| `/dev-guide` | Eliminates the "where do I start?" paralysis. Provides the complete development lifecycle from spec to deploy. | **Always active** — loaded at the start of every agent development session |
| `/cheatsheet` | Eliminates API lookup friction. Gives instant access to every builder method, operator, and namespace function. | Before writing or modifying any adk-fluent agent code |
| `/scaffold-project` | Eliminates boilerplate. Generates a complete project with `agent.py`, `tools.py`, tests, and eval cases. | Creating a new adk-fluent project from scratch |
| `/architect-agents` | Eliminates topology guesswork. Helps choose between Pipeline, FanOut, Loop, Route, Race, and 10+ other patterns. | Designing multi-agent systems or planning data flow |
| `/deploy-agent` | Eliminates deployment confusion. Maps the path from `adk web` to Agent Engine or Cloud Run production. | Deploying an agent to any target environment |
| `/eval-agent` | Eliminates "is my agent good enough?" uncertainty. Provides evaluation methodology with the E namespace. | Running agent evaluations, writing eval suites, debugging eval results |
| `/observe-agent` | Eliminates blind spots. Layers introspection, logging, tracing, and metrics via the M namespace. | Setting up observability for development or production |

### Library development

These skills are for contributors working on the adk-fluent library itself.

| Skill | Why it exists | When it activates |
|-------|---------------|-------------------|
| `/develop-feature` | Eliminates "how do I add this?" confusion. Classifies the change type and provides the exact implementation path. | Adding new builder methods, namespace functions, patterns, or operators |
| `/write-tests` | Eliminates test guesswork. Provides patterns for mock-based testing, contract checking, and namespace verification. | Adding test coverage for new or existing features |
| `/add-cookbook` | Eliminates example boilerplate. Scaffolds runnable cookbook examples that serve as both documentation and test. | Adding new examples or tutorials |
| `/debug-builder` | Eliminates "why doesn't this work?" frustration. Provides a systematic inspect → diagnose → fix workflow. | A builder isn't working as expected or a build fails |

### Code quality & maintenance

| Skill | Why it exists | When it activates |
|-------|---------------|-------------------|
| `/review-pr` | Eliminates review inconsistency. Runs 12 automated checks specific to adk-fluent (deprecated methods, import hygiene, generated file protection). | Reviewing pull requests |
| `/codegen-pipeline` | Eliminates pipeline confusion. Documents the scan → seed → generate pipeline and how to run it. | Regenerating builders from ADK or syncing with a new version |
| `/upgrade-adk` | Eliminates upgrade anxiety. Provides step-by-step impact analysis, regeneration, and rollback procedures. | New `google-adk` version released |

## Quick reference: skill invocation

Every skill is invoked with a `/` prefix in Claude Code, Gemini CLI, or any compatible agent:

```
/cheatsheet          — "How do I use .reads() with .writes()?"
/scaffold-project    — "Create a new customer support agent"
/architect-agents    — "Design a research pipeline with fallback models"
/deploy-agent        — "Deploy my agent to Cloud Run"
/eval-agent          — "Write an eval suite for my summarizer"
/observe-agent       — "Add logging and cost tracking"
/dev-guide           — "Walk me through building this agent"
/develop-feature     — "Add a .retry() method to the agent builder"
/write-tests         — "Write tests for the new cascade pattern"
/add-cookbook         — "Create an example for conditional gating"
/debug-builder       — "My pipeline build is failing"
/review-pr           — "Review PR #42"
/codegen-pipeline    — "Regenerate after ADK update"
/upgrade-adk         — "Upgrade to google-adk 1.25.0"
```

## Shared resources

All skills share auto-generated reference files and helper scripts in `_shared/`:

### Reference files

| Resource | Contents | Updated by |
|----------|----------|------------|
| `references/api-surface.md` | Complete builder method inventory organized by concern | `just skills` |
| `references/namespace-methods.md` | All S, C, P, A, M, T, E, G methods with signatures | `just skills` |
| `references/patterns-and-primitives.md` | Pattern function signatures and expression operators | `just skills` |
| `references/builder-inventory.md` | 135 builders across 9 modules | `just skills` |
| `references/deprecated-methods.md` | Deprecated method → replacement mapping | `just skills` |
| `references/generated-files.md` | Generated vs hand-written file classification | `just skills` |
| `references/development-commands.md` | All justfile commands and dev workflow | `just skills` |

### Helper scripts

These scripts are designed to be run by both humans and AI agents:

| Script | What it does | How to run | Expected output |
|--------|-------------|------------|-----------------|
| `check-deprecated.py` | Scans source files for deprecated method usage | `uv run .claude/skills/_shared/scripts/check-deprecated.py src/ tests/ examples/` | List of deprecated calls with file:line and suggested replacements, or "No deprecated methods found" |
| `validate-imports.py` | Checks for imports from internal modules (e.g., `adk_fluent._base`) | `uv run .claude/skills/_shared/scripts/validate-imports.py src/ tests/ examples/` | List of violations with file:line, or "All imports are valid" |
| `list-builders.py` | Prints the complete builder inventory from `manifest.json` | `uv run .claude/skills/_shared/scripts/list-builders.py` | Table of 135 builders grouped by module |
| `list-generated-files.py` | Classifies every file as generated or hand-written | `uv run .claude/skills/_shared/scripts/list-generated-files.py` | Two-column table: file path and classification |

:::{tip}
If a helper script fails with `ModuleNotFoundError`, ensure you're running from the repository root and have installed dependencies with `uv sync --all-extras`.
:::

## Installing Skills

### If you cloned the repo

Skills are already in place. Claude Code reads from `.claude/skills/`, Gemini CLI reads from `.gemini/skills/`. Nothing to do.

### If you installed via pip

Skills are not included in the pip package. Install them with one command:

::::{tab-set}
:::{tab-item} npx skills (Recommended)
```bash
# Installs 6 published skills to all detected agents
npx skills add vamsiramakrishnan/adk-fluent -y -g
```

**Expected output:**
```
✓ Detected agents: claude-code, gemini-cli
✓ Installed 6 skills from vamsiramakrishnan/adk-fluent
  adk-fluent-cheatsheet
  adk-fluent-deploy-guide
  adk-fluent-dev-guide
  adk-fluent-eval-guide
  adk-fluent-observe-guide
  adk-fluent-scaffold
```

**Escape hatch:** If `npx skills` is not available, use the manual methods below.
:::
:::{tab-item} Claude Code (manual)
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
:::{tab-item} Gemini CLI (manual)
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

### Published vs internal skills

| Distribution | Skills included | Install method |
|-------------|----------------|----------------|
| **Published** (6 skills) | cheatsheet, deploy-guide, dev-guide, eval-guide, observe-guide, scaffold | `npx skills add` |
| **Internal** (14 skills) | All 6 published + develop-feature, write-tests, add-cookbook, debug-builder, review-pr, architect-agents, codegen-pipeline, upgrade-adk | Clone the repo |

The 8 internal-only skills are designed for library contributors and are not published separately. They are automatically available when you clone the repository.

## Using Skills

Once installed, skills activate automatically based on context. For example:

- Ask "design a customer support triage system" → `/architect-agents` activates
- Ask "add a new builder method for retry logic" → `/develop-feature` activates
- Ask "review this PR" → `/review-pr` activates with automated checks
- Ask "deploy my agent to Cloud Run" → `/deploy-agent` activates
- Ask "write an eval suite for my agent" → `/eval-agent` activates

Skills provide the agent with:

- **Step-by-step procedures** — not just what to do, but the exact sequence
- **Helper scripts** — runnable checks the agent can execute (e.g., scan for deprecated methods)
- **Reference data** — auto-generated from the same sources as the codebase, always current

### Example: PR review with automated checks

When the `/review-pr` skill activates, the agent automatically runs:

```bash
# Scan for deprecated method usage
uv run .claude/skills/_shared/scripts/check-deprecated.py src/ tests/ examples/

# Check for internal module imports
uv run .claude/skills/_shared/scripts/validate-imports.py src/ tests/ examples/

# Verify no generated files were hand-edited
just check-gen
```

Then applies the 12-point review checklist covering generated file protection, import hygiene, test coverage, backward compatibility, type safety, and security.

**Expected output** (clean PR):
```
No deprecated methods found.
All imports are valid.
Generated files are up-to-date.
```

### Example: scaffolding a new project

When the `/scaffold-project` skill activates, the agent:

1. Asks clarifying questions (problem domain, tools needed, deployment target)
2. Creates the project structure (`agent.py`, `tools.py`, `__init__.py`)
3. Writes mock-based tests
4. Creates eval cases (`evalset.json`, `eval_config.json`)
5. Verifies with `uv run pytest` and `adk web`

## Keeping Skills Updated

Skills reference data is auto-generated by `scripts/skill_generator.py` from the same `manifest.json` and `seed.toml` that power the rest of the codegen pipeline.

```bash
# Regenerate skill references only
just skills

# Or as part of the full pipeline
just all    # scan → seed → generate → docs → skills → docs-build
```

**Expected output:**
```
Generating agent skill references...
  Written .claude/skills/_shared/references/api-surface.md
  Written .claude/skills/_shared/references/namespace-methods.md
  Written .claude/skills/_shared/references/patterns-and-primitives.md
  Written .claude/skills/_shared/references/builder-inventory.md
  Written .claude/skills/_shared/references/deprecated-methods.md
  Written .claude/skills/_shared/references/generated-files.md
  Written .claude/skills/_shared/references/development-commands.md
  Written .gemini/skills/_shared/references/...
  Written skills/adk-fluent-cheatsheet/SKILL.md
  ...
```

The generated references update automatically when:
- A new ADK version changes the builder inventory
- Deprecated methods are added or removed in `seed.manual.toml`
- New patterns or namespace methods are added to the source code
- The justfile targets change

## Troubleshooting

### Skill not activating

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent doesn't use skill knowledge | Skills directory not in expected location | Verify `.claude/skills/` (Claude Code) or `.gemini/skills/` (Gemini CLI) exists in your project root |
| Skill activates but references are stale | References weren't regenerated after ADK update | Run `just skills` to regenerate |
| "command not found: just" | `just` task runner not installed | Install with `cargo install just` or `brew install just` |
| Script fails with `ModuleNotFoundError` | Dependencies not installed | Run `uv sync --all-extras` from the repo root |
| Script fails with `FileNotFoundError: manifest.json` | Manifest not generated | Run `just scan` first |
| `npx skills` fails | Node.js/npm not installed or outdated | Install Node.js 18+ from [nodejs.org](https://nodejs.org) |

### Verifying skill installation

```bash
# Claude Code — list installed skills
ls .claude/skills/

# Expected: 14 directories + _shared/
# add-cookbook  architect-agents  cheatsheet  codegen-pipeline  debug-builder
# deploy-agent  dev-guide  develop-feature  eval-agent  observe-agent
# review-pr  scaffold-project  upgrade-adk  write-tests  _shared

# Gemini CLI — list installed skills
ls .gemini/skills/

# Published skills — list installed
ls skills/

# Expected: 6 directories
# adk-fluent-cheatsheet  adk-fluent-deploy-guide  adk-fluent-dev-guide
# adk-fluent-eval-guide  adk-fluent-observe-guide  adk-fluent-scaffold
```

## Publishing Skills

### Via npx skills (Recommended)

The 6 published skills in `skills/` are distributed via the [Agent Skills](https://agentskills.io) registry:

```bash
# Users install with:
npx skills add vamsiramakrishnan/adk-fluent -y -g

# Update to latest:
npx skills check -g
npx skills update -g
```

### Custom npm package

To publish as a standalone npm package:

#### 1. Add a `package.json`

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

#### 2. Publish to npm

```bash
npm publish
```

#### 3. Users install with:

```bash
npx skillpm install adk-fluent-skills
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
    SG --> PUB["skills/ (published)"]

    SK1["SKILL.md (hand-written)"] --> |procedures| Agent
    CR --> |on-demand references| Agent
    CS --> |runnable checks| Agent

    style SG fill:#E65100,color:#fff
    style SK1 fill:#F57C00,color:#fff
    style Agent fill:#059669,color:#fff
    style PUB fill:#d97706,color:#fff
```

The generator reads the same data sources as `llms_generator.py` and follows the same parse → resolve → emit pattern. SKILL.md files stay hand-written (procedures and judgment), while reference data is always auto-generated.

## Relationship to rules files

Skills and rules files serve different purposes:

| Feature | Rules files (`CLAUDE.md`, `.cursorrules`) | Agent Skills (`SKILL.md`) |
|---------|-------------------------------------------|---------------------------|
| **Loaded** | Always, at session start | On-demand, when context matches |
| **Size** | Full API reference (~30KB) | Focused procedure (<5KB each) |
| **Purpose** | "Here's the API" — reference knowledge | "Here's how to do X" — procedural knowledge |
| **Includes** | Builder methods, namespaces, patterns | Step-by-step workflows, scripts, checklists |
| **Generated by** | `scripts/llms_generator.py` | `scripts/skill_generator.py` (references only) |

Both are auto-generated from the same source of truth (`manifest.json` + `seed.toml`), so they never contradict each other.
