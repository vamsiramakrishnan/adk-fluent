# adk-fluent-ts Visual Cookbook Runner

TypeScript equivalent of the Python visual runner. Same shared SPA frontend,
native Hono backend for executing TypeScript cookbook agents.

## Quick Start

```bash
# 1. Configure credentials (pick one)
cp ts/visual/.env.example ts/visual/.env
# Edit with your Gemini API key or Vertex AI project

# 2. Launch
just visual-ts
# or with a custom port:
just visual-ts 3000
```

Opens at `http://localhost:8099` (or your chosen port):
- **Left sidebar**: all 75 TS cookbooks, grouped by difficulty
- **Center**: chat with any agent
- **Right panel**: live A2UI surface rendering + JSON inspector

The frontend shows a **TypeScript** badge to distinguish from the Python runner.

## Architecture

```
shared/visual/
└── index.html          # Shared SPA (HTML + CSS + JS, no build step)

ts/visual/
├── server.ts           # Hono dev server (auto-discovers TS cookbooks)
├── tsconfig.json       # TypeScript config for the server
├── .env.example        # Credentials template
└── README.md           # This file

ts/examples/cookbook/
└── *.ts                # 75 runnable cookbook examples
```

## API Contract

Both Python and TypeScript visual servers implement the same 4 endpoints:

| Endpoint | Method | Response |
|----------|--------|----------|
| `/api/health` | GET | `{status, cookbooks, language}` |
| `/api/cookbooks` | GET | `[{id, name, group, badge, ...}]` |
| `/api/inspect/:id` | GET | `{cookbook_id, explain, mermaid, surface_messages}` |
| `/api/run` | POST | `{response, surface_messages}` |

## How It Works

1. **Cookbook Discovery**: scans `ts/examples/cookbook/[0-9][0-9]_*.ts`,
   extracts titles from JSDoc headers, classifies by group (crawl/walk/run/a2ui).

2. **Agent Loading**: dynamic `import()` of cookbook files, looks for exports
   named `rootAgent`, `agent`, `pipeline`, or `default`.

3. **Execution**: runs agents via `@google/adk` `InMemoryRunner`, streams
   response text, extracts A2UI surface messages from session state.

## Running Both Servers

```bash
# Python on 8098, TypeScript on 8099 — run side by side
just visual-py &
just visual-ts &
```
