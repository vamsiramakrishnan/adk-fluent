# AI Coding Agent & Editor Setup

How to configure AI coding agents and code editors to generate accurate **adk-fluent** and Google ADK code.

AI coding agents work best when they have access to up-to-date API documentation and project conventions.
The pages below show you how to wire that context into your tool of choice — using rules files, MCP servers, or both.

## Pick your tool

````{grid} 1 2 2 3
---
gutter: 3
---
```{grid-item-card} Claude Code
:link: claude-code
:link-type: doc
CLI-based AI coding agent from Anthropic. Uses `CLAUDE.md` for project rules and supports MCP servers.
```

```{grid-item-card} Cursor
:link: cursor
:link-type: doc
AI-first code editor. Uses `.cursor/rules/` for project context and supports MCP servers.
```

```{grid-item-card} VS Code (Copilot)
:link: vscode
:link-type: doc
GitHub Copilot in VS Code. Uses `.github/instructions/` for project context and supports MCP via `.vscode/mcp.json`.
```

```{grid-item-card} Windsurf
:link: windsurf
:link-type: doc
AI code editor by Codeium. Uses `.windsurfrules` for project context and supports MCP servers.
```

```{grid-item-card} Cline
:link: cline
:link-type: doc
VS Code extension. Uses `.clinerules/` for project context and supports MCP servers.
```

```{grid-item-card} Zed
:link: zed
:link-type: doc
High-performance editor. Uses `llms.txt` via `#fetch` and supports MCP context servers.
```

```{grid-item-card} Agent Skills
:link: agent-skills
:link-type: doc
14 portable skills for developing, testing, debugging, deploying, evaluating, and reviewing adk-fluent projects. Works with any Agent Skills-compatible platform.
```
````

## How it works

Each setup page covers two complementary approaches:

Rules files
: A project-level file (e.g. `CLAUDE.md`, `.cursorrules`) that tells the AI agent about adk-fluent's API patterns, conventions, and best practices. This is the **most impactful** step — it teaches the agent *how* to write idiomatic adk-fluent code.

MCP servers
: A [Model Context Protocol](https://modelcontextprotocol.io/) server that gives the AI agent live access to adk-fluent's full documentation. This lets the agent look up exact method signatures, builder options, and cookbook recipes on demand.

Both approaches can be used independently, but combining them gives the best results.

:::\{tip}
All rules files (`CLAUDE.md`, `.cursor/rules/adk-fluent.mdc`, `.windsurfrules`, etc.) are **auto-generated** from the same source of truth by `scripts/llms_generator.py`. They update automatically when the API changes, so they never go stale. Run `just llms` to regenerate them locally, or let CI handle it.
:::

```{toctree}
---
hidden: true
---
claude-code
cursor
vscode
windsurf
cline
zed
agent-skills
```
