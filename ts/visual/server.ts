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
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve, basename } from "node:path";
import { pathToFileURL } from "node:url";

// ── Path setup ────────────────────────────────────────────────
const TS_DIR = resolve(import.meta.dirname, "..");
const ROOT = resolve(TS_DIR, "..");
const COOKBOOK_DIR = join(TS_DIR, "examples", "cookbook");
const SHARED_VISUAL = join(ROOT, "shared", "visual");

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
      has_agent: true,
      folder: null,
      has_surface: group === "a2ui",
    });
  }

  _cookbooks = entries;
  return entries;
}

// ── Agent loading ─────────────────────────────────────────────
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

// ── API routes ────────────────────────────────────────────────
app.get("/api/health", (c) => {
  const cookbooks = discoverCookbooks();
  return c.json({
    status: "ok",
    cookbooks: cookbooks.length,
    language: "TypeScript",
  });
});

app.get("/api/cookbooks", (c) => {
  return c.json(discoverCookbooks());
});

app.get("/api/inspect/:cookbookId", (c) => {
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
    let InMemoryRunner;
    try {
      const runners = await import("@google/adk/runners");
      InMemoryRunner = runners.InMemoryRunner;
    } catch {
      return c.json({
        error:
          "ADK runner not available. Install @google/adk to enable agent execution.",
        response: null,
        surface_messages: null,
      });
    }

    const runner = new InMemoryRunner({ agent, appName: "visual_runner" });

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
      const content = (event as Record<string, unknown>).content as
        | { parts?: Array<{ text?: string }> }
        | undefined;
      if (content?.parts) {
        for (const part of content.parts) {
          if (part.text) responseText += part.text;
        }
      }
    }

    const finalSession = await runner.sessionService.getSession({
      appName: "visual_runner",
      userId: "visual_user",
      sessionId: session.id,
    });
    const state = (finalSession as Record<string, unknown>)?.state as
      | Record<string, unknown>
      | undefined;
    const surfaceMessages = state?.["_a2ui_surface_messages"] ?? null;

    return c.json({
      response: responseText,
      surface_messages: surfaceMessages,
    });
  } catch (err) {
    return c.json(
      { error: err instanceof Error ? err.message : String(err) },
      500,
    );
  }
});

// ── Start ─────────────────────────────────────────────────────
const PORT = parseInt(process.env.PORT ?? "8099", 10);
console.log(
  `adk-fluent-ts visual runner starting on http://localhost:${PORT}`,
);
serve({ fetch: app.fetch, port: PORT });
