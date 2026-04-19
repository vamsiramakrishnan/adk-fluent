// flux:scaffold-user
/**
 * Playwright config for the flux visual runner.
 *
 * Both config and specs live under ``shared/visual/specs/``. The directory
 * declares ``"type": "commonjs"`` in its own ``package.json`` and symlinks
 * ``node_modules`` to ``ts/node_modules`` so Playwright's TS-to-CJS
 * transform can resolve ``@playwright/test`` / ``@axe-core/playwright`` /
 * ``esbuild`` without any workspace glue.
 *
 * Goldens are written under ``../goldens/flux/`` keyed by
 * ``{fixture}-{theme}.png``. See ``flux.spec.ts`` for the assertion rules.
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: /.*\.spec\.ts$/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [["list"]],
  timeout: 30_000,
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.005,
      threshold: 0.2,
      animations: "disabled",
    },
  },
  // Resolve goldens to the shared tree so both Python and TS runners can
  // read them. ``{arg}`` is the filename passed to toHaveScreenshot.
  snapshotPathTemplate:
    "{testDir}/../goldens/flux/{arg}{ext}",
  use: {
    viewport: { width: 640, height: 400 },
    deviceScaleFactor: 1,
    colorScheme: "light",
    ...devices["Desktop Chrome"],
  },
  projects: [
    {
      name: "flux-chromium",
      use: { browserName: "chromium" },
    },
  ],
});
