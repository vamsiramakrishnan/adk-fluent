/**
 * Cookbook smoke test.
 *
 * Each cookbook file under `examples/cookbook/` is a self-contained
 * script with top-level `assert` calls. Importing the module executes
 * those assertions, so this test acts as both a runner and a
 * regression suite.
 */
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { describe, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const cookbookDir = resolve(here, "../../examples/cookbook");

const files = readdirSync(cookbookDir)
  .filter((name) => /^\d+_.*\.ts$/.test(name))
  .sort();

describe("cookbook examples", () => {
  for (const file of files) {
    it(file, async () => {
      // Dynamic import — top-level asserts run on first import.
      await import(resolve(cookbookDir, file));
    });
  }
});
