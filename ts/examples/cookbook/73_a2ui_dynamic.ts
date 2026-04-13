/**
 * 73 — A2UI Dynamic: LLM-Driven UI Generation
 *
 * Demonstrates the core A2UI value proposition: the LLM itself designs
 * interactive UI surfaces based on user intent. `.ui(UI.auto())` handles
 * everything -- it marks the agent for LLM-guided mode where the A2UI
 * toolset injects the full schema and gives the LLM a tool to send
 * UI components to the client.
 *
 * Cookbook covers:
 *   - UI.auto() as the one-line LLM-guided mode marker
 *   - Agent with domain tools + UI.auto()
 *   - Declarative mode for static surfaces
 *   - P.uiSchema() for lightweight component docs in prompt
 */
import assert from "node:assert/strict";
import { Agent, UI, UISurface, P } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// --- 1. UI.auto() is the LLM-guided mode marker ---
const auto = UI.auto();
assert.equal((auto as { type: string }).type, "a2ui_auto");
assert.equal((auto as { catalog: string }).catalog, "basic");

// --- 2. Agent with .ui(UI.auto()) + domain tools ---
function getData(query: string): string {
  return `Results for: ${query}`;
}

const agent = new Agent("dynamic_ui", MODEL)
  .instruct("Create interactive UIs based on user requests.")
  .tool(getData)
  .ui(UI.auto());

const built = agent.build() as Record<string, unknown>;
assert.equal(built.name, "dynamic_ui");
// Has at least the domain tool
assert.ok((built.tools as unknown[]).length >= 1);

// --- 3. Declarative mode still works for static surfaces ---
const form = UI.form("Bug Report", {
  fields: [{ label: "Title", required: true }, { label: "Severity" }],
  submit: "Submit Bug",
});
assert.ok(form instanceof UISurface);

const formAgent = new Agent("form_ui", MODEL).instruct("Collect bug reports.").ui(form);

const formBuilt = formAgent.build() as Record<string, unknown>;
assert.equal(formBuilt.name, "form_ui");

// --- 4. P.uiSchema() gives lightweight component docs ---
const schemaSection = P.uiSchema();
const rendered = schemaSection.render();
// The section renders non-empty content with catalog metadata
assert.ok(schemaSection.meta.uiSchema === true);
assert.ok(schemaSection.meta.catalog === "basic");

// --- 5. UI.auto() with custom catalog ---
const extendedAuto = UI.auto({ catalog: "extended" });
assert.equal((extendedAuto as { catalog: string }).catalog, "extended");

// Build strips _ui_spec from the ADK object
assert.equal((built as Record<string, unknown>)._ui_spec, undefined);

export { agent, formAgent };
