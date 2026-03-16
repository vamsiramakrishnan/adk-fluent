# Plan: Visual Testing Infrastructure for Cookbooks (incl. A2UI)

## Audit Summary — What Exists Today

| Layer | Status | Details |
|---|---|---|
| **67 cookbook scripts** | Assertion-only | Verify builder state (e.g., `assert agent._config[...]`). No LLM calls, no visual output. |
| **70+ example folders** | `adk web`-ready | Generated via `cookbook_to_agents.py`. Each has `agent.py` with `root_agent`. Requires Vertex AI credentials. |
| **5 A2UI cookbooks** (70–74) | Assertion-only | Test `UIComponent` trees, `compile_surface()` JSON, namespace cross-wiring. Never render to a browser. |
| **A2UI compile pipeline** | Code-complete | `_ui.py` → `_ui_compile.py` builds valid A2UI JSON (createSurface, updateComponents, updateDataModel). |
| **A2UI client renderer** | **Missing** | No HTML/JS renderer in the repo. A2UI is protocol-based; the Flutter/React client is external. |
| **`a2ui-agent` package** | **Not published** | `SendA2uiToClientToolset` import fails; agents fall back to embedding JSON in responses. |
| **`.env.example`** | Vertex AI only | Requires `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI=TRUE`. |
| **`just agents`** | Works | Converts cookbooks → `adk web` folders. But `adk web` has no A2UI rendering. |
| **A2UI spec** | v0.10 complete | JSON schemas in `specification/v0_10/json/`. 18 components, 12 functions. |

### Core Gap

The cookbooks prove the *builder API* works. They don't prove the *agents* work end-to-end. There is no way to:
1. Run a cookbook agent against a real LLM and see output
2. Visually see what an A2UI surface looks like rendered in a browser
3. Go from `git clone` → running visual demo in < 5 minutes

---

## Plan

### Phase 1: A2UI Preview Renderer (static HTML)

**What**: A lightweight HTML+JS page that renders A2UI JSON into visual components — no server needed.

**Why**: The A2UI spec defines 18 components with clear JSON schemas. We can build a standalone renderer that takes compiled surface JSON and renders it using plain HTML/CSS. This gives instant visual feedback for any A2UI surface without needing the unpublished `a2ui-agent` package or a Flutter client.

**Files**:
- `visual/a2ui-renderer/index.html` — single-file app (HTML + inline JS + CSS)
- `visual/a2ui-renderer/render.js` — component-to-DOM mapping for all 18 A2UI component types
- `visual/a2ui-renderer/style.css` — Material Design-inspired styles matching A2UI spec

**Behavior**:
- Accepts A2UI JSON messages (paste or load from file)
- Renders `createSurface` → `updateComponents` → `updateDataModel` lifecycle
- Data binding works (text fields update data model, display fields react)
- Validation checks render inline errors
- Includes a gallery mode: loads all compiled A2UI surfaces from cookbooks 70–74

**Scope**: ~500 lines total. No build step, no npm. Opens with `open index.html`.

### Phase 2: Surface Snapshot Exporter

**What**: A Python script that compiles every A2UI cookbook's surfaces into JSON files the renderer can load.

**Files**:
- `scripts/export_a2ui_surfaces.py` — imports each A2UI cookbook, calls `compile_surface()`, writes JSON
- `visual/a2ui-renderer/surfaces/` — directory of exported JSON files (one per surface)

**Command**: `just a2ui-preview` — runs exporter + opens renderer in browser.

### Phase 3: Cookbook Visual Runner (FastAPI dev server)

**What**: A local dev server that lets you pick any cookbook agent, send it a prompt, and see the response — including streamed A2UI surfaces.

**Why**: `adk web` requires Vertex AI and the full ADK web client. A lightweight runner gives a faster, more focused experience specifically for adk-fluent cookbook demos.

**Files**:
- `visual/server.py` — FastAPI app (~200 lines)
  - `GET /` — serves the UI
  - `GET /api/cookbooks` — lists available cookbook agents
  - `POST /api/run` — runs an agent with a prompt, returns response + A2UI messages
  - `GET /api/stream/{cookbook}` — SSE stream for agent events
- `visual/templates/index.html` — single-page UI
  - Left sidebar: cookbook list grouped by category (crawl/walk/run + a2ui)
  - Center: chat interface for agent interaction
  - Right panel: A2UI surface renderer (reuses Phase 1 renderer)
  - Bottom: agent introspection panel (`.explain()` output, Mermaid diagram)

**Key design decisions**:
- Uses ADK's `InMemoryRunner` + `InMemorySessionService` (no external infra)
- Supports both Vertex AI and Gemini API key auth (auto-detects from env)
- A2UI surfaces intercepted from agent state (`_a2ui_surface_messages`) and rendered in real-time
- Each cookbook's `.explain()` / `.to_mermaid()` output shown alongside

### Phase 4: Config & One-Command Setup

**Files**:
- `visual/.env.example` — documented env template with both auth paths:
  ```
  # Option A: Gemini API key (simplest, no GCP needed)
  GOOGLE_API_KEY=your-gemini-api-key

  # Option B: Vertex AI (full GCP)
  GOOGLE_CLOUD_PROJECT=your-project
  GOOGLE_CLOUD_LOCATION=us-central1
  GOOGLE_GENAI_USE_VERTEXAI=TRUE
  ```
- `visual/README.md` — 3-step quickstart
- Justfile additions:
  - `just visual-setup` — install visual deps + copy `.env.example`
  - `just visual` — export surfaces + start dev server + open browser
  - `just a2ui-preview` — static A2UI preview only (no server, no LLM)

**pyproject.toml addition**:
```toml
visual = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "python-dotenv>=1.0",
]
```

### Phase 5: Cookbook Visual Test Suite (pytest-based)

**What**: Automated visual regression tests that run cookbooks against real LLMs and snapshot-test the A2UI output.

**Files**:
- `tests/visual/conftest.py` — fixtures for visual testing (runner, session, snapshot dir)
- `tests/visual/test_a2ui_render.py` — for each A2UI cookbook:
  1. Build the agent
  2. Send a test prompt
  3. Extract A2UI messages from state
  4. Validate against A2UI JSON schema
  5. Snapshot the component tree (golden file comparison)
- `tests/visual/golden/` — golden A2UI JSON snapshots

**Command**: `just test-visual` — runs visual test suite (requires API key).

**Marker**: `@pytest.mark.visual` — skipped by default in `just test`, opt-in via `just test-visual`.

---

## Implementation Order & Dependencies

```
Phase 1 (A2UI Renderer)     ← no dependencies, pure HTML/JS
    ↓
Phase 2 (Surface Exporter)  ← depends on Phase 1 for rendering target
    ↓
Phase 3 (Dev Server)        ← depends on Phase 1 renderer, Phase 2 surfaces
    ↓
Phase 4 (Config/Setup)      ← depends on Phase 3 for server startup
    ↓
Phase 5 (Visual Tests)      ← depends on Phase 3 runner, optional
```

Phases 1-2 deliver **static A2UI preview** (no LLM, no server, works offline).
Phases 3-4 deliver **full interactive runner** (requires API key).
Phase 5 adds **CI-grade visual regression** (requires API key).

---

## What This Does NOT Include

- **No Flutter/React client**: The renderer is a lightweight HTML preview, not a production A2UI client
- **No `a2ui-agent` package**: We work around the missing package by intercepting compiled surfaces
- **No deployment infra**: This is local dev/demo only
- **No video recording or screenshot diffing**: Visual tests compare JSON structure, not pixels

---

## Summary

| After Phase | User Experience |
|---|---|
| 1+2 | `just a2ui-preview` → browser opens, see all A2UI surfaces rendered visually |
| 3+4 | `just visual` → full dev server, pick any cookbook, chat with it, see A2UI live |
| 5 | `just test-visual` → automated regression tests validate A2UI output against golden files |
