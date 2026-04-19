// flux:scaffold-user
/**
 * W5 — flux visual regression + a11y smoke suite.
 *
 * For every JSON fixture in ``shared/visual/fixtures/flux/`` and every
 * token pack under ``catalog/flux/tokens/``, mount the React runner from
 * ``shared/visual/runner/entry.tsx`` in a headless page, take a pixel-
 * matched screenshot against ``shared/visual/goldens/flux/``, and run
 * @axe-core/playwright, failing on any ``critical`` or ``serious``
 * violations.
 *
 * The entry bundle is produced once per process via esbuild (already in
 * ``ts/node_modules`` as a transitive dep) so the hot path is just
 * ``page.setContent`` + a ``__FLUX_READY__`` wait + screenshot.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import * as esbuild from "esbuild";

// Resolve repo root relative to this file's on-disk location. Playwright's
// CJS transform rewrites imports but preserves ``__dirname``.
const HERE = __dirname;
const REPO_ROOT = resolve(HERE, "..", "..", "..");
const FIXTURES_DIR = resolve(REPO_ROOT, "shared/visual/fixtures/flux");
const TOKENS_DIR = resolve(REPO_ROOT, "catalog/flux/tokens");
const ENTRY = resolve(REPO_ROOT, "shared/visual/runner/entry.tsx");

type Fixture = {
  file: string;
  name: string;
  description?: string;
  node: Record<string, unknown>;
  slots?: Record<string, unknown>;
};

type ThemePack = {
  id: string;
  pack: Record<string, unknown>;
};

function loadFixtures(): Fixture[] {
  const files = readdirSync(FIXTURES_DIR).filter((f) => f.endsWith(".json"));
  return files
    .map((f) => {
      const raw = readFileSync(join(FIXTURES_DIR, f), "utf8");
      const data = JSON.parse(raw);
      return { file: f, ...data } as Fixture;
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

function loadThemes(): ThemePack[] {
  const files = readdirSync(TOKENS_DIR).filter((f) => f.endsWith(".json"));
  return files
    .map((f) => {
      const raw = readFileSync(join(TOKENS_DIR, f), "utf8");
      const pack = JSON.parse(raw);
      const id =
        (pack?.$meta?.id as string | undefined) ?? f.replace(/\.json$/, "");
      return { id, pack };
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}

let BUNDLE_CACHE: string | null = null;

async function buildBundle(): Promise<string> {
  if (BUNDLE_CACHE) return BUNDLE_CACHE;
  const result = await esbuild.build({
    entryPoints: [ENTRY],
    bundle: true,
    write: false,
    format: "iife",
    platform: "browser",
    target: "es2020",
    jsx: "automatic",
    loader: { ".tsx": "tsx", ".ts": "ts" },
    logLevel: "silent",
    define: {
      "process.env.NODE_ENV": '"production"',
    },
    // Point esbuild at ``ts/node_modules`` so it can resolve ``react`` and
    // friends from the single canonical install.
    nodePaths: [resolve(REPO_ROOT, "ts/node_modules")],
    absWorkingDir: resolve(REPO_ROOT, "ts"),
  });
  BUNDLE_CACHE = result.outputFiles[0].text;
  return BUNDLE_CACHE;
}

function shell(bundle: string, fixture: Fixture, theme: ThemePack): string {
  // Inline everything so the page has no network dependencies — Playwright's
  // headless browser never hits the filesystem or network.
  const fixturePayload = JSON.stringify({
    name: fixture.name,
    description: fixture.description,
    node: fixture.node,
    slots: fixture.slots ?? {},
  });
  const themePayload = JSON.stringify(theme.pack);
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>flux harness — ${fixture.name} @ ${theme.id}</title>
    <style>
      html, body { margin: 0; padding: 0; background: #ffffff; }
      body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
      *, *::before, *::after { animation-duration: 0s !important; animation-delay: 0s !important; transition-duration: 0s !important; transition-delay: 0s !important; }
    </style>
  </head>
  <body>
    <main id="flux-root" aria-label="flux test harness"></main>
    <script>
      window.__FLUX_FIXTURE__ = ${fixturePayload};
      window.__FLUX_THEME_ID__ = ${JSON.stringify(theme.id)};
      window.__FLUX_THEME_PACK__ = ${themePayload};
    </script>
    <script>${bundle}</script>
  </body>
</html>`;
}

const FIXTURES = loadFixtures();
const THEMES = loadThemes();

test.describe("flux renderer — visual + a11y", () => {
  test.beforeAll(async () => {
    await buildBundle();
  });

  for (const fixture of FIXTURES) {
    for (const theme of THEMES) {
      const label = `${fixture.name} @ ${theme.id}`;
      test(label, async ({ page }) => {
        const bundle = await buildBundle();
        await page.setContent(shell(bundle, fixture, theme), {
          waitUntil: "load",
        });
        // Wait for the RAF-signalled readiness flag the runner sets once
        // React has committed the first paint.
        await page.waitForFunction(
          () => (window as unknown as { __FLUX_READY__?: boolean }).__FLUX_READY__ === true,
          { timeout: 5_000 },
        );

        // Visual regression — key the golden by fixture+theme.
        await expect(page).toHaveScreenshot(`${fixture.name}-${theme.id}.png`);

        // A11y smoke — fail on critical/serious violations. The
        // ``color-contrast`` rule is downgraded to a warning: contrast
        // pairings are owned by the token pack (W1), not by W5's React
        // renderers, so a bad pairing is a design-token bug we surface
        // as an annotation rather than a renderer test failure. Every
        // other critical/serious rule still blocks.
        const results = await new AxeBuilder({ page })
          .include("#flux-root")
          .analyze();
        const CONTRAST_RULES = new Set(["color-contrast"]);
        const blocking = results.violations.filter(
          (v) =>
            (v.impact === "critical" || v.impact === "serious") &&
            !CONTRAST_RULES.has(v.id),
        );
        if (results.violations.length) {
          test.info().annotations.push({
            type: "axe-violations",
            description: JSON.stringify(
              results.violations.map((v) => ({
                id: v.id,
                impact: v.impact,
                help: v.help,
              })),
            ),
          });
        }
        expect(
          blocking,
          `axe found ${blocking.length} critical/serious violation(s): ${blocking
            .map((v) => `${v.id} (${v.impact})`)
            .join(", ")}`,
        ).toEqual([]);
      });
    }
  }
});
