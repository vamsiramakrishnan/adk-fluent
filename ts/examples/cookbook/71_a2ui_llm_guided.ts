/**
 * 71 — A2UI LLM-Guided Mode: Let the LLM Design the UI
 *
 * Demonstrates LLM-guided UI mode where the agent has full control
 * over the A2UI surface via toolset and catalog schema injection.
 *
 * Cookbook covers:
 *   - UI.auto() for LLM-guided mode
 *   - P.uiSchema() inject catalog schema into prompt
 *   - T.a2ui() toolset for LLM-controlled UI
 *   - G.a2ui() guard to validate LLM-generated UI output
 *   - Full namespace symphony combining all four
 */
import assert from "node:assert/strict";
import { Agent, UI, T, G, P, TComposite, GComposite } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// --- 1. Basic LLM-guided agent ---
const autoAgent = new Agent("creative", MODEL).instruct("Build beautiful UIs.").ui(UI.auto());
const autoSpec = autoAgent.inspect()._ui_spec as { type: string; catalog: string };
assert.equal(autoSpec.type, "a2ui_auto");
assert.equal(autoSpec.catalog, "basic");

// --- 2. LLM-guided with catalog schema in prompt ---
const guided = new Agent("designer", MODEL)
  .instruct(P.role("UI designer").add(P.uiSchema()).add(P.task("Build a dashboard")))
  .ui(UI.auto());
assert.ok(guided.inspect()._ui_spec != null);

// --- 3. Full namespace symphony ---
const fullAgent = new Agent("support", MODEL)
  .instruct(P.role("Support agent").add(P.uiSchema()).add(P.task("Help customers")))
  .tools(T.googleSearch().pipe(T.a2ui()))
  .guard(G.pii().pipe(G.a2ui({ maxComponents: 30 })))
  .ui(UI.auto());
assert.ok(fullAgent.inspect()._ui_spec != null);

// --- 4. UI.auto() with custom catalog ---
const custom = UI.auto({ catalog: "extended" });
assert.equal((custom as { catalog: string }).catalog, "extended");

// --- 5. P.uiSchema() produces schema metadata ---
const schemaSection = P.uiSchema();
assert.equal(schemaSection.section, "UI Schema");
assert.equal(schemaSection.meta.uiSchema, true);
assert.equal(schemaSection.meta.catalog, "basic");

// --- 6. P.uiSchema() with options ---
const customSchema = P.uiSchema({ catalog: "extended", examples: false });
assert.equal(customSchema.meta.catalog, "extended");
assert.equal(customSchema.meta.examples, false);

export { autoAgent, guided, fullAgent };
