# Appendix E: Learning from adk-web — Pain Points and How We Build Better

> An honest analysis of adk-web's developer experience issues, what we can learn from them,
> and how `adk-fluent dev` avoids the same mistakes.

---

## 1. adk-web: What It Is

[adk-web](https://github.com/google/adk-web) is the built-in developer UI for Google's Agent Development Kit. It's an Angular 19 application that provides:

- Chat interface for agent interaction
- Event monitoring and distributed tracing
- Artifact management
- Evaluation tools
- Agent builder (visual)

It runs as a separate process from the Python backend and communicates via HTTP API.

---

## 2. The Pain Points (From GitHub Issues + User Reports)

### 2.1 Two-Process Architecture

**The problem:**
```bash
# Terminal 1: Start the Python backend
adk api_server --allow_origins=http://localhost:4200

# Terminal 2: Start the Angular frontend
cd adk-web && npm install && npm run serve
# Wait for Angular compilation...
# Opens at http://localhost:4200
```

Two terminals. Two processes. Two ports. CORS configuration. The Python backend at `:8000`, the Angular frontend at `:4200`. If either dies, the other is useless.

**Why this is painful:**
- Developers forget to start one of the processes
- Port conflicts when other tools use 4200 or 8000
- CORS misconfiguration is a common issue ([GitHub #267](https://github.com/google/adk-web/issues/267) — "Frontend not calling backend properly")
- No shared process lifecycle — Ctrl+C in one terminal doesn't stop the other

**Our approach with `adk-fluent dev`:** Single process. The Python process serves both the API and the embedded UI. One port. No CORS (same origin). Ctrl+C stops everything.

### 2.2 Heavy Frontend Stack

**The problem:** adk-web requires:
- Node.js (LTS)
- npm
- Angular CLI (`@angular/cli`)
- Full `npm install` (~300 MB node_modules)
- Angular compilation on every code change (3-10 seconds)

This is a full frontend development environment. Most agent developers are Python developers, not Angular developers. Requiring npm/Node.js for a dev tool is a high barrier.

**Why this is painful:**
- Python developers don't have Node.js installed and don't want to
- `npm install` in the adk-web repo downloads ~300 MB of node_modules
- Angular compilation adds seconds to every page refresh
- Updating adk-web requires tracking Angular version compatibility

**Our approach:** No Node.js. No npm. No compilation step. The embedded UI is a pre-built static HTML/CSS/JS bundle (~50 KB gzipped) served from the Python process. We ship it as package data inside `adk_fluent/static/`.

Technology choices for the embedded UI:
- **Preact** (3 KB) or **vanilla JS** — not React (40 KB), not Angular (200 KB)
- **Single HTML file** with inline CSS and JS for simplicity
- **WebSocket** connection to the Python backend for real-time events
- **Zero build step** — the HTML file is a static asset, not compiled

### 2.3 Agent Discovery Failures

**The problem:** Users report that `adk web` doesn't find their agents ([GitHub #1895](https://github.com/google/adk-python/issues/1895) — "Why is my agent not showing up?"):

- Agent module must follow specific directory conventions
- Must have a `root_agent` variable at module scope
- Module must be importable from the working directory
- `.env` files must be in the agent directory (problematic in monorepos — [GitHub #71](https://github.com/google/adk-web/issues/71))

**Why this is painful:**
- The "no agents found" error gives no guidance on what went wrong
- The directory convention isn't obvious to new users
- Monorepo users with many agents need `.env` files copied everywhere

**Our approach with `adk-fluent dev`:**

1. **Accept any Python expression**, not just module directories:
   ```bash
   adk-fluent dev agent.py              # File path
   adk-fluent dev mypackage.agents      # Module path
   adk-fluent dev agents/               # Directory (scans for builders)
   ```

2. **Auto-detect builders** by scanning for `BuilderBase` instances:
   ```python
   # If the user does: adk-fluent dev agent.py
   # We find all BuilderBase instances in the module
   # No need for a specific variable name like "root_agent"
   ```

3. **Clear error messages:**
   ```
   $ adk-fluent dev agent.py

   Error: No agent builders found in agent.py

   Looked for:
     - Variables that are Agent, Pipeline, FanOut, or Loop instances
     - A variable named 'root_agent' (ADK convention)
     - A variable named 'agent' or 'pipeline'

   Found these variables: [my_agent (Agent), helper (Agent)]
   Did you mean: adk-fluent dev agent.py --var my_agent
   ```

4. **Single `.env` file** at project root, inherited by all agents.

### 2.4 UI Crashes Under Load

**The problem:** [GitHub #377](https://github.com/google/adk-web/issues/377) — "DevUI freezes/crashes browser when inspecting tool logs." The Angular UI struggles with large volumes of events, particularly during tool execution with verbose logging.

**Why this happens:** Event tracing in the UI renders every event as a DOM node. For a multi-agent pipeline with many tool calls, this can mean hundreds or thousands of DOM elements, overwhelming the browser's rendering engine.

**Our approach:**
- **Terminal-first tracing** — primary event stream in the terminal, not the browser
- **Virtualized lists** — if we render events in the UI, use virtual scrolling (only render visible events)
- **Event filtering** — filter by agent, type, or severity before rendering
- **Pagination** — for tool logs, show last N events with a "load more" option
- **SSE for streaming** — events stream via Server-Sent Events, not polling. The client processes them incrementally.

### 2.5 No Stop Button

**The problem:** [GitHub #79](https://github.com/google/adk-web/issues/79) — There's no way to stop an in-progress agent execution from the UI. If an agent is stuck in a loop or making an expensive API call, the user must kill the entire `adk web` process and restart.

**Our approach:**
- **Server-side cancellation** via a `/v1/cancel` endpoint
- **WebSocket close** triggers cancellation — closing the browser tab stops the agent
- **Timeout enforcement** — `adk-fluent dev` respects `.timeout()` settings from the builder
- **Ctrl+C in terminal** cancels the current request (not the whole server)

### 2.6 State Tab Not Updating

**The problem:** [GitHub #312](https://github.com/google/adk-web/issues/312) — The state tab doesn't reflect changes to session state during execution. Users can't see how `.writes()` and state transforms are working.

**Our approach:**
- **Live state diff** — WebSocket pushes state changes as they happen
- **State timeline** — show state at each step of the pipeline, not just the final state
- **IR-aware state view** — because we have the IR, we know which agent writes which key. The UI can show expected vs. actual state.

### 2.7 Eval UI Issues

**The problem:** [GitHub #376](https://github.com/google/adk-web/issues/376) — Missing "Create Evaluation Set" option. [GitHub #289](https://github.com/google/adk-web/issues/289) — Evaluation UI doesn't render if there's more than one folder in the project.

**Our approach:**
- **Programmatic evals first** — `.eval()`, `.eval_suite()`, `adk-fluent test` are the primary eval path
- **UI eval display** is secondary — show eval results in the dev UI as a read-only report, not a full eval management system
- The dev UI shows: pass/fail count, per-case details, cost per eval run

---

## 3. What We'd Build: The `adk-fluent dev` UI

### 3.1 Design Principles

1. **Terminal-first, UI-second** — the terminal is the primary interface; the UI is supplementary
2. **Read-only UI** — the UI displays information; all actions happen via the terminal or API
3. **Zero build step** — no compilation, no bundling, no npm
4. **Instant load** — the UI is < 50 KB, loads in < 100ms
5. **Mobile-friendly** — responsive layout for testing from phones/tablets

### 3.2 UI Layout

```
┌─────────────────────────────────────────────────────┐
│ adk-fluent dev    research_pipeline    ⚡ connected  │
├────────────────────────┬────────────────────────────┤
│                        │                            │
│   Chat                 │   Inspector                │
│                        │                            │
│   [User]: Research     │   ┌─ Events ─────────────┐ │
│   AI in healthcare     │   │ researcher: started   │ │
│                        │   │ researcher: tool_call │ │
│   [Agent]: Here are    │   │   web_search("AI...")│ │
│   the findings...      │   │ researcher: completed │ │
│                        │   │ analyst: started      │ │
│                        │   │ ...                   │ │
│                        │   └─────────────────────┘ │
│                        │                            │
│                        │   ┌─ State ──────────────┐ │
│                        │   │ findings: "..."       │ │
│                        │   │ analysis: "..."       │ │
│                        │   └─────────────────────┘ │
│                        │                            │
│   ┌──────────────┐     │   ┌─ Pipeline ──────────┐ │
│   │ Type message  │     │   │ [researcher] → ✓    │ │
│   └──────────────┘     │   │ [analyst] → ▶       │ │
│                        │   │ [writer] → ○        │ │
│                        │   └─────────────────────┘ │
└────────────────────────┴────────────────────────────┘
```

### 3.3 Implementation: Vanilla JS + WebSocket

```html
<!-- The entire UI in one file: adk_fluent/static/dev-ui.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>adk-fluent dev</title>
  <style>
    /* ~200 lines of CSS — no framework, no Tailwind */
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, -apple-system, sans-serif; }
    /* ... */
  </style>
</head>
<body>
  <div id="app"><!-- Rendered by JS --></div>
  <script>
    // ~500 lines of vanilla JS
    // WebSocket connection to ws://localhost:8080/ws
    // Renders chat, events, state, pipeline status
    // No framework, no build step, no dependencies
  </script>
</body>
</html>
```

**Total size:** ~20 KB uncompressed, ~8 KB gzipped. Loads instantly.

**Why vanilla JS instead of Preact/React/Lit:**
- Zero build step
- Zero npm dependencies
- Loads in < 50ms (no framework bootstrap)
- The UI is simple enough that a framework adds complexity without benefit
- A single HTML file is trivially embeddable as package data

### 3.4 The Terminal UI

The terminal output during `adk-fluent dev` is equally important:

```
  adk-fluent dev v0.X.0

  Agent: research_pipeline (3 agents)
  Server: http://localhost:8080
  UI: http://localhost:8080/ui

  ─── Events ──────────────────────────────────────
  14:32:01 [REQ] POST /v1/ask "Research AI in healthcare"
  14:32:01 [researcher] started (gemini-2.5-flash)
  14:32:01 [researcher] tool_call: web_search("AI healthcare 2024")
  14:32:02 [researcher] tool_result: 3 results
  14:32:03 [researcher] completed (1.8s, 450→1200 tokens, $0.002)
  14:32:03 [researcher] state: findings="AI in healthcare..."
  14:32:03 [analyst] started (gemini-2.5-flash)
  14:32:04 [analyst] completed (1.2s, 1800→800 tokens, $0.002)
  14:32:04 [writer] started (gemini-2.5-flash)
  14:32:06 [writer] completed (2.1s, 2500→3000 tokens, $0.004)
  14:32:06 [RES] 200 OK (5.1s total, $0.008)
  ─────────────────────────────────────────────────
```

This gives the developer everything they need without opening a browser.

---

## 4. How `adk-fluent dev` Compares to `adk web`

| Aspect | adk web | adk-fluent dev |
|--------|---------|----------------|
| **Processes** | 2 (Python + Angular) | 1 (Python only) |
| **Ports** | 2 (8000 + 4200) | 1 (8080) |
| **CORS** | Required (cross-origin) | Not needed (same origin) |
| **Frontend deps** | Node.js, npm, Angular CLI | None |
| **UI size** | ~200 MB (node_modules) | ~20 KB (embedded HTML) |
| **Startup time** | 10-30s (Angular compile) | 1-3s (import + serve) |
| **Hot reload** | Angular HMR (frontend only) | watchfiles (agent Python code) |
| **Backend** | ADK only | Any backend (ADK, Temporal, Prefect, DBOS) |
| **Agent discovery** | Directory convention | Auto-detect BuilderBase instances |
| **State inspection** | Broken ([#312](https://github.com/google/adk-web/issues/312)) | Live WebSocket updates |
| **Stop execution** | Not possible ([#79](https://github.com/google/adk-web/issues/79)) | `/v1/cancel` endpoint |
| **Event tracing** | Crashes on large payloads ([#377](https://github.com/google/adk-web/issues/377)) | Terminal + virtualized UI |
| **Multi-agent** | Yes (directory scanning) | Yes (auto-detect builders) |
| **Eval integration** | Buggy ([#376](https://github.com/google/adk-web/issues/376), [#289](https://github.com/google/adk-web/issues/289)) | Read-only eval results display |
| **.env handling** | Per-agent directory ([#71](https://github.com/google/adk-web/issues/71)) | Project root, inherited |

---

## 5. What We Should NOT Build (Learned from adk-web)

### 5.1 Don't Build a Visual Agent Builder

adk-web includes an "Agent Builder" feature. This is a drag-and-drop UI for creating agents visually. It sounds cool but:

- **The fluent API IS the builder.** `Agent("x").instruct("...") >> Agent("y")` is already concise. A visual tool can't be more concise.
- **Visual builders generate code you can't easily modify.** The generated code is a black box.
- **Maintenance cost is enormous.** Every new builder method needs a corresponding UI element.

The fluent API is the interface. The dev UI is for inspection, not construction.

### 5.2 Don't Build a Full Event Replay System

adk-web attempts to show event traces with full replay capability. This leads to:
- Massive DOM trees that crash the browser
- Complex state management for timeline scrubbing
- Storage requirements for event persistence

Instead, build:
- **Terminal event log** (primary) — lightweight, always available
- **Current-request event display** (UI) — shows events for the active request only
- **"Download events as JSON"** button — for offline analysis

### 5.3 Don't Build Artifact Management UI

adk-web has artifact viewing/management. This is a file browser in the browser — not high value for a dev tool. Instead:
- Show artifact metadata in the event log
- Provide a `/artifacts` endpoint that returns JSON
- Let users open artifacts with their native OS tools

---

## 6. The Coexistence Strategy

### 6.1 `adk-fluent dev` Does Not Replace `adk web`

They serve different audiences:

- **`adk web`**: Full-featured development UI for teams building complex agents with native ADK. Rich tracing, artifact management, eval workflows. Requires Node.js.
- **`adk-fluent dev`**: Lightweight development server for fluent API users. Terminal-first, browser-optional. Zero Node.js dependency. Works with all backends.

### 6.2 Interoperability

Since `adk-fluent dev` exposes a REST API that's compatible with `adk api_server`:
```
POST /v1/ask         → compatible with adk web frontend
POST /v1/stream      → compatible with adk web SSE
/.well-known/agent.json → A2A compatible
```

A user could theoretically:
1. Run `adk-fluent dev agent.py` (our lightweight server)
2. Point `adk-web` at it (`--api-url http://localhost:8080`)
3. Get the full Angular UI with our multi-backend server

This is an advanced use case, but it's possible because we use standard HTTP APIs.

### 6.3 Migration Path

For teams currently using `adk web`:
1. Keep using `adk web` for its rich features
2. Use `adk-fluent dev` when they need:
   - Non-ADK backend development (Temporal, Prefect, DBOS)
   - Lighter-weight development on low-resource machines
   - CI/CD integration (no Node.js in Docker images)
   - Quick ad-hoc testing without the full Angular stack

---

## 7. Technical Implementation Notes

### 7.1 The dev-ui.html Must Work Offline

The embedded UI cannot depend on CDNs. No `<script src="https://cdn...">`. Everything must be inline or bundled in the HTML file. This means:
- No Google Fonts (use system-ui)
- No CDN-hosted CSS frameworks
- No external Mermaid.js (for pipeline visualization, use inline SVG generation from Python)

### 7.2 WebSocket Protocol

```typescript
// Client → Server
{ "type": "ask", "prompt": "Hello", "session_id": "optional" }
{ "type": "cancel" }

// Server → Client
{ "type": "text", "content": "Hello!", "agent": "helper" }
{ "type": "event", "agent": "helper", "kind": "tool_call", "data": {...} }
{ "type": "state", "key": "findings", "value": "...", "agent": "researcher" }
{ "type": "done", "metadata": { "tokens_in": 100, "tokens_out": 500, "cost": 0.002 } }
{ "type": "error", "message": "Model provider timeout" }
```

### 7.3 Hot Reload Implementation

```python
# Uses watchfiles (already in dev extras)
import watchfiles

async def watch_and_reload(module_path: str, on_change: Callable):
    async for changes in watchfiles.awatch(module_path):
        changed_files = [str(c[1]) for c in changes]
        if any(f.endswith('.py') for f in changed_files):
            # Reimport the module
            importlib.invalidate_caches()
            module = importlib.reload(sys.modules[module_path])
            builder = _find_builder(module)
            on_change(builder)
            print(f"  Reloaded: {', '.join(changed_files)}")
```

**Caveat:** Python module reloading is imperfect. If the agent module imports from other modules that also changed, those need reloading too. We should reload the entire module tree rooted at the agent file.

**Fallback:** If reload fails (syntax error, import error), keep the previous version running and print the error. Don't crash the server.
