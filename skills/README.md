Development skills for building agents with adk-fluent. Install into any coding agent via `npx skills`.

## Install

```bash
npx skills add vamsiramakrishnan/adk-fluent -y -g
```

**Expected output:**
```
✓ Detected agents: claude-code, gemini-cli
✓ Installed 6 skills from vamsiramakrishnan/adk-fluent
```

## Update

```bash
npx skills check -g
npx skills update -g
```

## Skills

| Skill | Why it exists | When it activates |
|-------|---------------|-------------------|
| `adk-fluent-cheatsheet` | Eliminates API lookup friction — instant access to every builder method, operator, and namespace function | Before writing or modifying any adk-fluent agent code |
| `adk-fluent-deploy-guide` | Eliminates deployment confusion — maps the path from `adk web` to production | Deploying an agent to any target environment |
| `adk-fluent-dev-guide` | Eliminates "where do I start?" paralysis — complete development lifecycle | **Always active** at the start of every agent development session |
| `adk-fluent-eval-guide` | Eliminates "is my agent good enough?" uncertainty — evaluation methodology with E namespace | Running agent evaluations or writing eval suites |
| `adk-fluent-observe-guide` | Eliminates blind spots — layers introspection, logging, tracing, and metrics | Setting up observability for development or production |
| `adk-fluent-scaffold` | Eliminates boilerplate — generates complete project with agent, tools, tests, and eval cases | Creating a new adk-fluent project from scratch |

## Additional internal skills (clone the repo)

The repository contains 8 additional skills for library contributors that are not published separately:

| Skill | Purpose |
|-------|---------|
| `develop-feature` | Implement new builder methods, namespace functions, patterns |
| `write-tests` | Write tests with `.mock()`, contract checking, namespace patterns |
| `add-cookbook` | Create runnable cookbook examples |
| `debug-builder` | Debug builder issues — build failures, contracts, state flow |
| `review-pr` | PR review with 12-point automated checklist |
| `architect-agents` | Design multi-agent topologies and data flow |
| `codegen-pipeline` | Run the code generation pipeline (scan → seed → generate) |
| `upgrade-adk` | Upgrade to a new ADK version with impact analysis |

These are available in `.claude/skills/` and `.gemini/skills/` when you clone the repository.

## Compatibility

These skills work with any [Agent Skills](https://agentskills.io)-compatible tool:
Gemini CLI, Claude Code, Cursor, GitHub Copilot, Amp, and more.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `npx skills` not found | Install Node.js 18+ from [nodejs.org](https://nodejs.org) |
| Skills not activating | Verify your agent reads from the correct directory (`.claude/skills/` for Claude Code) |
| Stale references | Run `just skills` to regenerate from latest manifest |
| Missing `manifest.json` | Run `just scan` first |
