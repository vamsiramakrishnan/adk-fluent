---
orphan: true
---

# Shared Visual Runner — Cross-Language Conformance Tool

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared visual runner that lets both Python and TypeScript adk-fluent agents run through the same SPA frontend, with native backends for each language, and align TS cookbooks to cover the 64-79 gap.

**Architecture:** The existing `index.html` SPA moves to `shared/visual/` as the single shared frontend. Python keeps its FastAPI server at `python/visual/server.py` (port 8098). A new Hono server at `ts/visual/server.ts` (port 8099) implements the same 4-endpoint API contract. The SPA adds a language badge from `/api/health`. The justfile gets `visual-py` and `visual-ts` commands. TS cookbooks 64-79 are ported to close the numbering gap.

**Tech Stack:** Hono (TS HTTP server — zero-dep, fast, same API as Express), tsx (runtime), existing FastAPI (Python). Vanilla JS SPA (no framework).

---

## File Structure

### Shared (move + enhance)

- `shared/visual/index.html` — moved from `python/visual/index.html`, add language badge
- `shared/visual/cookbook_meta.md` — merged Python + TS sample prompts

### TypeScript (new)

- `ts/visual/server.ts` — Hono server implementing the 4-endpoint API contract
- `ts/visual/tsconfig.json` — standalone TS config for the visual server

### TypeScript cookbooks (new — gap fill 64-79)

- `ts/examples/cookbook/64_middleware_schema.ts`
- `ts/examples/cookbook/65_builtin_middleware.ts`
- `ts/examples/cookbook/66_t_module_tools.ts`
- `ts/examples/cookbook/67_g_module_guards.ts`
- `ts/examples/cookbook/68_a2ui_basics.ts` (renumber: Python's 70)
- `ts/examples/cookbook/69_a2ui_agent_integration.ts` (renumber: Python's 71)
- `ts/examples/cookbook/70_a2ui_operators.ts` (renumber: Python's 72)
- `ts/examples/cookbook/71_a2ui_llm_guided.ts` (renumber: Python's 73)
- `ts/examples/cookbook/72_a2ui_pipeline.ts` (renumber: Python's 74)
- `ts/examples/cookbook/73_a2ui_dynamic.ts` (renumber: Python's 77)
- `ts/examples/cookbook/74_harness_and_skills.ts` (renumber: Python's 78)
- `ts/examples/cookbook/75_coding_agent_harness.ts` (renumber: Python's 79)

Note: Python cookbooks 68-69 (engine_selection, asyncio_backend), 70/71 (temporal_backend, compute_layer), 75-76 (prefect_backend, dbos_backend), and 77 (skill_based_agents) are Python-runtime-specific. TS equivalents are not applicable. The TS cookbooks will cover the feature-equivalent subset.

### Justfile (modify)

- Root `justfile` — update `visual` to `visual-py`, add `visual-ts`, update `a2ui-preview`

### Python (modify)

- `python/visual/server.py` — add `language` field to `/api/health`, change default port to 8098

---

## Task 1: Move index.html to shared/visual/ and add language badge

**Files:**
- Move: `python/visual/index.html` → `shared/visual/index.html`
- Modify: `shared/visual/index.html` (add language badge from `/api/health`)

- [ ] **Step 1: Move index.html**

```bash
mkdir -p shared/visual
git mv python/visual/index.html shared/visual/index.html
```

- [ ] **Step 2: Add language badge to the SPA**

In `shared/visual/index.html`, find the `checkServer()` function that calls `/api/health`. It currently reads `{status, cookbooks}`. Update it to also read `language` and display it in the header.

Find the header element (the `<header>` tag with the title) and add a badge span:

```html
<span id="lang-badge" style="
  display:none; font-size:0.7rem; padding:2px 8px;
  border-radius:4px; margin-left:8px;
  background:var(--accent); color:#fff; vertical-align:middle;
"></span>
```

In the `checkServer()` JS function, after the fetch succeeds, add:

```javascript
const langBadge = document.getElementById('lang-badge');
if (langBadge && data.language) {
  langBadge.textContent = data.language;
  langBadge.style.display = 'inline';
}
```

- [ ] **Step 3: Move cookbook_meta.md**

```bash
git mv python/visual/cookbook_meta.md shared/visual/cookbook_meta.md
```

- [ ] **Step 4: Commit**

```bash
git add shared/visual/ python/visual/
git commit -m "refactor: move visual SPA to shared/visual/ for cross-language use"
```

---

## Task 2: Update Python server (port 8098, language field, serve shared SPA)

**Files:**
- Modify: `python/visual/server.py`

- [ ] **Step 1: Add language field to /api/health**

In `python/visual/server.py`, find the `/api/health` route handler. Change the return from:
```python
return {"status": "ok", "cookbooks": len(cookbooks)}
```
to:
```python
return {"status": "ok", "cookbooks": len(cookbooks), "language": "Python"}
```

- [ ] **Step 2: Serve shared SPA instead of local index.html**

Find the route that serves `index.html` (the `@app.get("/")` handler). Change:
```python
return FileResponse(str(VISUAL_DIR / "index.html"))
```
to:
```python
SHARED_VISUAL = Path(__file__).parent.parent.parent / "shared" / "visual"
# ... (add near the top with other path constants)

return FileResponse(str(SHARED_VISUAL / "index.html"))
```

Add `SHARED_VISUAL` near the other path constants at the top of the file:
```python
SHARED_VISUAL = ROOT.parent / "shared" / "visual"
```

Where `ROOT` is already defined as `Path(__file__).parent.parent`.

- [ ] **Step 3: Verify the server starts**

```bash
cd python && uv run python -c "from visual.server import app; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add python/visual/server.py
git commit -m "feat(visual): serve shared SPA, add language field to health endpoint"
```

---

## Task 3: Create the TypeScript visual server

**Files:**
- Create: `ts/visual/server.ts`
- Create: `ts/visual/tsconfig.json`
- Modify: `ts/package.json` (add hono + tsx dev deps)

- [ ] **Step 1: Add dev dependencies**

```bash
cd ts && npm install --save-dev hono @hono/node-server tsx
```

- [ ] **Step 2: Create ts/visual/tsconfig.json**

```json
{
  "extends": "../tsconfig.json",
  "compilerOptions": {
    "outDir": "../dist/visual",
    "rootDir": "."
  },
  "include": ["*.ts"]
}
```

- [ ] **Step 3: Create ts/visual/server.ts**

```{code-block} typescript
:force:

/**
 * adk-fluent-ts Visual Cookbook Runner — Hono dev server.
 *
 * Auto-discovers TypeScript cookbook agents, serves the shared SPA,
 * runs agents against real LLMs, and returns A2UI surfaces.
 *
 * Usage:
 *   npx tsx ts/visual/server.ts
 *   # or via justfile:
 *   just visual-ts
 */
import { Hono } from "hono";
import { cors } from "hono/cors";
import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve, basename } from "node:path";
import { pathToFileURL } from "node:url";

// ── Path setup ────────────────────────────────────────────────
const TS_DIR = resolve(import.meta.dirname, "..");
const ROOT = resolve(TS_DIR, "..");
const COOKBOOK_DIR = join(TS_DIR, "examples", "cookbook");
const SHARED_VISUAL = join(ROOT, "shared", "visual");
const SURFACES_DIR = join(TS_DIR, "visual", "surfaces");

// ── Cookbook grouping (mirrors Python) ─────────────────────────
const CRAWL = new Set([1, 2, 3, 8, 10, 11, 21, 22, 23, 24, 26]);
const WALK = new Set([
  4, 5, 6, 7, 12, 13, 14, 16, 17, 18, 19, 20, 27, 29, 30, 31, 32, 33, 35,
  36, 37, 38, 39, 40, 41, 42, 56,
]);
const A2UI = new Set([58, 59, 68, 69, 70, 71, 72, 73]);

function getGroup(num: number): string {
  if (CRAWL.has(num)) return "crawl";
  if (WALK.has(num)) return "walk";
  if (A2UI.has(num)) return "a2ui";
  return "run";
}

// ── Title extraction ──────────────────────────────────────────
function parseTitle(filepath: string): string {
  try {
    const text = readFileSync(filepath, "utf-8");
    const match = text.match(/\/\*\*\s*\n\s*\*\s*\d+\s*[—–-]\s*(.+)/);
    if (match) return match[1].trim();
    const fallback = text.match(/\/\*\*\s*\n\s*\*\s*(.+)/);
    if (fallback) return fallback[1].trim();
  } catch {
    // ignore
  }
  return basename(filepath, ".ts").replace(/^\d+_/, "").replace(/_/g, " ");
}

// ── Cookbook discovery ─────────────────────────────────────────
interface CookbookEntry {
  id: string;
  name: string;
  group: string;
  badge: string;
  has_agent: boolean;
  folder: string | null;
  has_surface: boolean;
}

let _cookbooks: CookbookEntry[] | null = null;

function discoverCookbooks(): CookbookEntry[] {
  if (_cookbooks) return _cookbooks;
  const entries: CookbookEntry[] = [];

  if (!existsSync(COOKBOOK_DIR)) {
    _cookbooks = entries;
    return entries;
  }

  const files = readdirSync(COOKBOOK_DIR)
    .filter((f) => /^\d{2}_.*\.ts$/.test(f))
    .sort();

  for (const file of files) {
    const filepath = join(COOKBOOK_DIR, file);
    const id = basename(file, ".ts");
    const num = parseInt(id.substring(0, 2), 10);
    const group = getGroup(num);
    const title = parseTitle(filepath);

    entries.push({
      id,
      name: title,
      group,
      badge: group,
      has_agent: true, // TS cookbooks are self-contained
      folder: null,
      has_surface: group === "a2ui",
    });
  }

  _cookbooks = entries;
  return entries;
}

// ── Agent loading + execution ─────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _agentCache = new Map<string, any>();

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function loadAgent(cookbookId: string): Promise<any> {
  if (_agentCache.has(cookbookId)) return _agentCache.get(cookbookId);

  const cookbooks = discoverCookbooks();
  const cb = cookbooks.find((c) => c.id === cookbookId);
  if (!cb) throw new Error(`Unknown cookbook: ${cookbookId}`);

  const filepath = join(COOKBOOK_DIR, `${cookbookId}.ts`);
  if (!existsSync(filepath)) throw new Error(`File not found: ${filepath}`);

  const mod = await import(pathToFileURL(filepath).href);

  // Look for exported agent-like objects
  const agent =
    mod.root_agent ?? mod.rootAgent ?? mod.agent ?? mod.pipeline ?? mod.default;
  if (!agent) {
    throw new Error(
      `No agent export found in ${cookbookId}.ts (tried: root_agent, rootAgent, agent, pipeline, default)`,
    );
  }

  _agentCache.set(cookbookId, agent);
  return agent;
}

// ── App ───────────────────────────────────────────────────────
const app = new Hono();
app.use("/*", cors());

// Serve shared SPA
app.get("/", (c) => {
  const html = readFileSync(join(SHARED_VISUAL, "index.html"), "utf-8");
  return c.html(html);
});

// Serve static surfaces if they exist
if (existsSync(SURFACES_DIR)) {
  app.use("/surfaces/*", serveStatic({ root: join(TS_DIR, "visual") }));
}

// ── API routes ────────────────────────────────────────────────
app.get("/api/health", (c) => {
  const cookbooks = discoverCookbooks();
  return c.json({ status: "ok", cookbooks: cookbooks.length, language: "TypeScript" });
});

app.get("/api/cookbooks", (c) => {
  return c.json(discoverCookbooks());
});

app.get("/api/inspect/:cookbookId", async (c) => {
  const cookbookId = c.req.param("cookbookId");
  try {
    const filepath = join(COOKBOOK_DIR, `${cookbookId}.ts`);
    const source = existsSync(filepath)
      ? readFileSync(filepath, "utf-8")
      : null;

    return c.json({
      cookbook_id: cookbookId,
      explain: source ? `TypeScript cookbook source:\n\n${source}` : null,
      mermaid: null,
      surface_messages: null,
    });
  } catch (err) {
    return c.json({ error: String(err) }, 500);
  }
});

app.post("/api/run", async (c) => {
  const body = await c.req.json<{ cookbook: string; prompt: string }>();
  const { cookbook, prompt } = body;

  if (!cookbook || !prompt) {
    return c.json({ error: "Missing cookbook or prompt" }, 400);
  }

  try {
    const agent = await loadAgent(cookbook);

    // Try to use InMemoryRunner from @google/adk
    const { InMemoryRunner } = await import("@google/adk/runners");
    const runner = new InMemoryRunner({
      agent,
      appName: "visual_runner",
    });

    const session = await runner.sessionService.createSession({
      appName: "visual_runner",
      userId: "visual_user",
    });

    let responseText = "";
    for await (const event of runner.runAsync({
      userId: "visual_user",
      sessionId: session.id,
      newMessage: { role: "user", parts: [{ text: prompt }] },
    })) {
      if (event.content?.parts) {
        for (const part of event.content.parts) {
          if ("text" in part && part.text) {
            responseText += part.text;
          }
        }
      }
    }

    // Extract A2UI surface messages from session state
    const finalSession = await runner.sessionService.getSession({
      appName: "visual_runner",
      userId: "visual_user",
      sessionId: session.id,
    });
    const surfaceMessages =
      finalSession?.state?.["_a2ui_surface_messages"] ?? null;

    return c.json({ response: responseText, surface_messages: surfaceMessages });
  } catch (err) {
    return c.json(
      { error: err instanceof Error ? err.message : String(err) },
      500,
    );
  }
});

// ── Start ─────────────────────────────────────────────────────
const PORT = parseInt(process.env.PORT ?? "8099", 10);
console.log(`adk-fluent-ts visual runner starting on http://localhost:${PORT}`);
serve({ fetch: app.fetch, port: PORT });
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd ts && npx tsx --no-warnings visual/server.ts &
sleep 2
curl -s http://localhost:8099/api/health | head -1
kill %1
```

Expected: `{"status":"ok","cookbooks":63,"language":"TypeScript"}`

- [ ] **Step 5: Commit**

```bash
git add ts/visual/ ts/package.json ts/package-lock.json
git commit -m "feat(visual): add TypeScript visual runner with Hono server"
```

---

## Task 4: Update justfile with visual-py, visual-ts commands

**Files:**
- Modify: `justfile`

- [ ] **Step 1: Replace visual commands in justfile**

Find the existing visual commands (lines ~351-371) and replace with:

```make
# --- Visual: A2UI preview (static, no LLM, no server) ---
a2ui-preview:
    @echo "Exporting A2UI surfaces from cookbooks..."
    @{{PY}} {{SHARED_DIR}}/scripts/export_a2ui_surfaces.py
    @echo "Opening A2UI gallery in browser..."
    @python3 -c "import webbrowser; webbrowser.open('shared/visual/index.html')" 2>/dev/null || echo "Open shared/visual/index.html in your browser"

# --- Visual: Python cookbook runner (requires API key) ---
visual-py: a2ui-preview
    @echo "Starting Python visual runner at http://localhost:8098..."
    @cd {{PYTHON_DIR}} && uv run uvicorn visual.server:app --host 0.0.0.0 --port 8098 --reload

# --- Visual: TypeScript cookbook runner (requires API key) ---
visual-ts:
    @echo "Starting TypeScript visual runner at http://localhost:8099..."
    @cd {{TS_DIR}} && npx tsx visual/server.ts

# --- Visual: export surfaces only ---
visual-export:
    @echo "Exporting A2UI surfaces..."
    @{{PY}} {{SHARED_DIR}}/scripts/export_a2ui_surfaces.py

# --- Visual test suite (requires API key) ---
test-visual:
    @echo "Running visual test suite..."
    @cd {{PYTHON_DIR}} && uv run pytest tests/visual/ -v --tb=short -m visual

# --- Visual: legacy alias ---
visual: visual-py
```

- [ ] **Step 2: Commit**

```bash
git add justfile
git commit -m "feat(justfile): add visual-py and visual-ts commands"
```

---

## Task 5: Port TS cookbooks 64-67 (middleware schema, builtin middleware, T module, G module)

**Files:**
- Create: `ts/examples/cookbook/64_middleware_schema.ts`
- Create: `ts/examples/cookbook/65_builtin_middleware.ts`
- Create: `ts/examples/cookbook/66_t_module_tools.ts`
- Create: `ts/examples/cookbook/67_g_module_guards.ts`

These are feature-equivalent ports, not line-by-line translations. Each should follow the established TS cookbook pattern: JSDoc header with `N — Title`, imports from `../../src/index.js`, `node:assert/strict` assertions, named exports.

- [ ] **Step 1: Read the Python source for each cookbook**

Read these files to understand what each demonstrates:
- `python/examples/cookbook/64_middleware_schema.py`
- `python/examples/cookbook/65_builtin_middleware.py`
- `python/examples/cookbook/66_t_module_tools.py`
- `python/examples/cookbook/67_g_module_guards.py`

- [ ] **Step 2: Write 64_middleware_schema.ts**

Port the Python cookbook to TypeScript. Use the TS namespace APIs:
- `M.*` methods use camelCase (e.g., `M.retry({maxAttempts: 3})`)
- `MiddlewareSchema` → TypeScript equivalent
- Use `assert` from `node:assert/strict`

- [ ] **Step 3: Write 65_builtin_middleware.ts**

Port builtin middleware demos: `M.retry()`, `M.log()`, `M.cost()`, `M.latency()`, `M.circuitBreaker()`, `M.timeout()`, `M.cache()`.

- [ ] **Step 4: Write 66_t_module_tools.ts**

Port T module composition: `T.fn()`, `T.agent()`, `T.googleSearch()`, `T.mock()`, `T.confirm()`, `T.timeout()`, `T.cache()`.

- [ ] **Step 5: Write 67_g_module_guards.ts**

Port G module guards: `G.guard()`, `G.pii()`, `G.toxicity()`, `G.length()`, `G.schema()`.

- [ ] **Step 6: Run all existing TS tests to verify no regressions**

```bash
cd ts && npm test
```

- [ ] **Step 7: Commit**

```bash
git add ts/examples/cookbook/64_middleware_schema.ts ts/examples/cookbook/65_builtin_middleware.ts ts/examples/cookbook/66_t_module_tools.ts ts/examples/cookbook/67_g_module_guards.ts
git commit -m "feat(ts/cookbook): port cookbooks 64-67 (middleware schema, builtin mw, T module, G module)"
```

---

## Task 6: Port TS cookbooks 68-73 (A2UI series + harness)

**Files:**
- Create: `ts/examples/cookbook/68_a2ui_basics.ts`
- Create: `ts/examples/cookbook/69_a2ui_agent_integration.ts`
- Create: `ts/examples/cookbook/70_a2ui_operators.ts`
- Create: `ts/examples/cookbook/71_a2ui_llm_guided.ts`
- Create: `ts/examples/cookbook/72_a2ui_pipeline.ts`
- Create: `ts/examples/cookbook/73_a2ui_dynamic.ts`

Note: TS already has `58_ui_basics.ts` and `59_ui_form_dashboard.ts` covering basic A2UI. These new cookbooks port the advanced Python A2UI series (70-74, 77) to the TS numbering (68-73).

- [ ] **Step 1: Read the Python A2UI cookbooks**

Read these files:
- `python/examples/cookbook/70_a2ui_basics.py`
- `python/examples/cookbook/71_a2ui_agent_integration.py`
- `python/examples/cookbook/72_a2ui_operators.py`
- `python/examples/cookbook/73_a2ui_llm_guided.py`
- `python/examples/cookbook/74_a2ui_pipeline.py`
- `python/examples/cookbook/77_a2ui_dynamic.py`

- [ ] **Step 2: Write 68_a2ui_basics.ts**

Port the full A2UI basics: all component factories, presets (form, dashboard, wizard, confirm, table), data binding, validation checks. Use `UI.*` namespace with TS syntax.

- [ ] **Step 3: Write 69_a2ui_agent_integration.ts**

Port agent integration: `Agent.ui(surface)`, `T.a2ui()`, `G.a2ui()`, `P.uiSchema()`, `S.toUi()`, `S.fromUi()`.

- [ ] **Step 4: Write 70_a2ui_operators.ts**

Port operator composition for A2UI layouts: row/column chaining, nested composition.

- [ ] **Step 5: Write 71_a2ui_llm_guided.ts**

Port LLM-guided mode: `UI.auto({catalog: "basic"})`, schema injection, guard validation.

- [ ] **Step 6: Write 72_a2ui_pipeline.ts**

Port A2UI in multi-step pipelines: surfaces attached to pipeline steps.

- [ ] **Step 7: Write 73_a2ui_dynamic.ts**

Port dynamic A2UI: `UI.auto()` with domain tools, LLM deciding the UI at runtime.

- [ ] **Step 8: Run tests**

```bash
cd ts && npm test
```

- [ ] **Step 9: Commit**

```bash
git add ts/examples/cookbook/68_a2ui_basics.ts ts/examples/cookbook/69_a2ui_agent_integration.ts ts/examples/cookbook/70_a2ui_operators.ts ts/examples/cookbook/71_a2ui_llm_guided.ts ts/examples/cookbook/72_a2ui_pipeline.ts ts/examples/cookbook/73_a2ui_dynamic.ts
git commit -m "feat(ts/cookbook): port A2UI cookbooks 68-73 (basics through dynamic)"
```

---

## Task 7: Port TS cookbooks 74-75 (harness + coding agent)

**Files:**
- Create: `ts/examples/cookbook/74_harness_and_skills.ts`
- Create: `ts/examples/cookbook/75_coding_agent_harness.ts`

- [ ] **Step 1: Read the Python harness cookbooks**

Read these files:
- `python/examples/cookbook/78_harness_and_skills.py`
- `python/examples/cookbook/79_coding_agent_harness.py`

- [ ] **Step 2: Write 74_harness_and_skills.ts**

Port harness+skills: `H.hooks()`, `H.permissions()`, `H.planMode()`, `H.sessionStore()`, `H.usage()`, skills integration. Use the TS H namespace (already ported — see `23_coding_harness.ts` for patterns).

- [ ] **Step 3: Write 75_coding_agent_harness.ts**

Port the full coding agent harness: `H.codingAgent(workspace)` bundle, workspace tools, sandbox, permissions, executor, todos, plan mode.

- [ ] **Step 4: Run tests**

```bash
cd ts && npm test
```

- [ ] **Step 5: Commit**

```bash
git add ts/examples/cookbook/74_harness_and_skills.ts ts/examples/cookbook/75_coding_agent_harness.ts
git commit -m "feat(ts/cookbook): port harness cookbooks 74-75 (skills + coding agent)"
```

---

## Task 8: Update TS cookbook INDEX.md and verify parity

**Files:**
- Modify: `ts/examples/cookbook/INDEX.md`

- [ ] **Step 1: Read current TS INDEX.md**

```bash
cat ts/examples/cookbook/INDEX.md
```

- [ ] **Step 2: Update INDEX.md with new cookbooks 64-75**

Add entries for all new cookbooks in the appropriate sections, following the existing format.

- [ ] **Step 3: Verify cookbook count**

```bash
ls ts/examples/cookbook/*.ts | wc -l
# Expected: 75 (63 existing + 12 new)
```

- [ ] **Step 4: Commit**

```bash
git add ts/examples/cookbook/INDEX.md
git commit -m "docs(ts/cookbook): update INDEX.md with cookbooks 64-75"
```

---

## Task 9: Smoke test the full system

- [ ] **Step 1: Verify Python visual server starts and serves shared SPA**

```bash
cd python && uv run python -c "
from visual.server import app, discover_cookbooks
cbs = discover_cookbooks()
print(f'Python: {len(cbs)} cookbooks discovered')
assert any(c['group'] == 'a2ui' for c in cbs), 'No A2UI cookbooks found'
print('OK')
"
```

- [ ] **Step 2: Verify TS visual server starts and discovers cookbooks**

```bash
cd ts && npx tsx -e "
import { readFileSync } from 'fs';
const server = readFileSync('visual/server.ts', 'utf-8');
console.log('TS server exists:', server.length, 'bytes');
" && echo "OK"
```

- [ ] **Step 3: Verify TS cookbooks all parse without errors**

```bash
cd ts && npx tsx --no-warnings -e "
import { readdirSync } from 'fs';
const cbs = readdirSync('examples/cookbook').filter(f => f.endsWith('.ts') && /^\d/.test(f));
console.log('TS cookbooks:', cbs.length);
console.log('Range:', cbs[0], '...', cbs[cbs.length-1]);
"
```

- [ ] **Step 4: Final commit with any fixups**

```bash
git status
# If clean, skip. Otherwise:
git add -A && git commit -m "chore: smoke test fixups for shared visual runner"
```
