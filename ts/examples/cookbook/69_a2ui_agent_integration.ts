/**
 * 69 — A2UI Agent Integration: Wiring UI to Agents
 *
 * Demonstrates attaching UI surfaces to agents and cross-namespace integration.
 *
 * Cookbook covers:
 *   - Agent.ui() with declarative surface
 *   - Agent.ui() with LLM-guided mode (UI.auto)
 *   - T.a2ui() toolset for LLM-controlled UI
 *   - G.a2ui() guard for LLM-generated UI validation
 *   - P.uiSchema() inject catalog schema into prompt
 *   - S.toUi() / S.fromUi() state bridging
 */
import assert from "node:assert/strict";
import {
  Agent,
  UI,
  UISurface,
  T,
  G,
  P,
  S,
  TComposite,
  GComposite,
  STransform,
} from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// --- 1. Agent.ui() with declarative surface ---
const formSurface = UI.form("ticket", {
  fields: [{ label: "Issue", type: "longText" }, { label: "Priority" }],
});
const agent = new Agent("support", MODEL).instruct("Help users.").ui(formSurface);
assert.equal(agent.inspect()._ui_spec, formSurface);

// --- 2. Agent.ui() with LLM-guided mode ---
const auto = UI.auto();
const creative = new Agent("creative", MODEL).instruct("Build UIs.").ui(auto);
assert.equal(creative.inspect()._ui_spec, auto);
assert.equal((auto as { type: string }).type, "a2ui_auto");

// --- 3. Agent.ui() with component tree ---
const formAgent = new Agent("form", MODEL).ui(
  UI.surface(
    "signup",
    UI.column([
      UI.text("Sign Up"),
      UI.row([UI.textField("Email"), UI.textField("Password")]),
      UI.button("Submit"),
    ]),
  ),
);
assert.ok(formAgent.inspect()._ui_spec != null);

// --- 4. T.a2ui() tool composition ---
const tc = T.a2ui();
assert.ok(tc instanceof TComposite);
assert.equal(tc.items[0].type, "a2ui");

// Compose with other tools
const composed = T.googleSearch().pipe(T.a2ui());
assert.ok(composed instanceof TComposite);
assert.ok(composed.items.length >= 2);

// --- 5. G.a2ui() guard ---
const gc = G.a2ui({ maxComponents: 30 });
assert.ok(gc instanceof GComposite);

// Compose with other guards
const composedGuard = G.pii().pipe(G.a2ui());
assert.ok(composedGuard instanceof GComposite);

// --- 6. P.uiSchema() prompt injection ---
const ps = P.uiSchema();
assert.equal(ps.section, "UI Schema");
assert.equal(ps.meta.uiSchema, true);

// Compose with other prompt sections
const fullPrompt = P.role("UI designer").add(P.uiSchema()).add(P.task("Build a dashboard"));
assert.ok(fullPrompt instanceof Object);

// --- 7. S.toUi() / S.fromUi() state bridging ---
const toUi = S.toUi("total", "count");
assert.ok(toUi instanceof STransform);
assert.match(toUi.name, /toUi/);

const fromUi = S.fromUi("name", "email");
assert.ok(fromUi instanceof STransform);
assert.match(fromUi.name, /fromUi/);

// --- 8. Build strips _ui_spec from the ADK object ---
const built = agent.build() as Record<string, unknown>;
assert.equal(built._ui_spec, undefined);
assert.equal(built.name, "support");

export { agent, creative, formAgent, toUi, fromUi };
