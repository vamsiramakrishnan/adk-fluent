/**
 * 71 — A2UI LLM-Guided Mode: let the LLM design the UI.
 *
 * The new ergonomic shape: pass `llmGuided: true` and the agent self-wires
 * the prompt schema. (The `T.a2ui()` toolset throws A2UINotInstalled
 * because the `a2ui-agent` JS package is not yet published — auto-tooling
 * is a no-op at build time once the package ships.)
 */
import assert from "node:assert/strict";
import { Agent, P, UI, UIAutoSpec } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// --- 1. Shortest path: omit spec, set the flag ---
const auto = new Agent("creative", MODEL)
  .instruct("Build beautiful UIs.")
  .ui(undefined, { llmGuided: true });
const autoSpec = auto.inspect()._ui_spec as UIAutoSpec;
assert.ok(autoSpec instanceof UIAutoSpec);
assert.equal(autoSpec.catalog, "basic");
assert.equal(autoSpec.fromFlag, true);

// --- 2. Equivalent: pass UI.auto() explicitly + flag (auto-wires tools) ---
const explicit = new Agent("designer", MODEL)
  .instruct(P.role("UI designer").union(P.uiSchema()).union(P.task("Build a dashboard")))
  .ui(UI.auto({ catalog: "extended" }), { llmGuided: true });
const explicitSpec = explicit.inspect()._ui_spec as UIAutoSpec;
assert.equal(explicitSpec.catalog, "extended");
assert.equal(explicit.inspect()._a2uiAutoGuard, true);

// --- 3. Prompt-only: UI.auto() without llmGuided does NOT auto-wire tools ---
const promptOnly = new Agent("noisy", MODEL)
  .instruct("Mention available components only.")
  .ui(UI.auto());
assert.equal(promptOnly.inspect()._a2uiAutoTool, false);

export { auto, explicit, promptOnly };
