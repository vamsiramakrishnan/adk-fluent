/**
 * 49 — `.native()` post-build hook
 *
 * The `.native()` escape hatch lets you reach past the fluent API and
 * mutate the raw built object after `.build()` returns. Use it for ADK
 * features that the fluent surface does not yet expose.
 *
 * Hooks are stored as callbacks; multiple hooks compose in order.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

// Single hook: tag the built object with custom metadata
const tagged = new Agent("tagged", "gemini-2.5-flash")
  .instruct("Echo the prompt back.")
  .native((obj) => {
    (obj as Record<string, unknown>).custom_tag = "production";
    (obj as Record<string, unknown>).deployed_at = "2026-04-12";
  })
  .build() as Record<string, unknown>;

assert.equal(tagged.name, "tagged");
assert.equal(tagged.custom_tag, "production");
assert.equal(tagged.deployed_at, "2026-04-12");

// Multiple hooks compose in registration order.
const trail: string[] = [];
const layered = new Agent("layered", "gemini-2.5-flash")
  .instruct("Multi-hook agent.")
  .native(() => {
    trail.push("first");
  })
  .native(() => {
    trail.push("second");
  })
  .native((obj) => {
    (obj as Record<string, unknown>).hook_count = trail.length;
  })
  .build() as Record<string, unknown>;

assert.deepEqual(trail, ["first", "second"]);
assert.equal(layered.hook_count, 2);

// `.native()` is also useful for patching deprecated or undocumented
// fields without re-running the whole builder pipeline.
const patched = new Agent("patched", "gemini-2.5-flash")
  .instruct("Patched agent.")
  .native((obj) => {
    (obj as Record<string, unknown>).legacy_flag = true;
  })
  .build() as Record<string, unknown>;

assert.equal(patched.legacy_flag, true);

export { tagged, layered, patched };
