/**
 * 69 — A2UI Agent Integration: Wiring UI to Agents
 *
 * Demonstrates the new schema-driven UI surface (Zod) plus the
 * declarative-vs-LLM-guided behavior matrix on `Agent.ui()`.
 */
import assert from "node:assert/strict";
import { z } from "zod";
import {
  Agent,
  G,
  GComposite,
  P,
  S,
  STransform,
  UI,
  UIAutoSpec,
  UISurface,
} from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// --- 1. Schema-driven form: UI.form(z.object(...)) ---
const Ticket = z.object({
  title: z.string(),
  email: z.string().email(),
  priority: z.enum(["low", "medium", "high"]),
});
const ticketSurface = UI.form(Ticket, { title: "Ticket", submitAction: "submit_ticket" });
assert.ok(ticketSurface instanceof UISurface);

// --- 2. UI.paths(Schema) for reflective binding ---
const paths = UI.paths<{ title: { path: string }; email: { path: string } }>(Ticket);
assert.equal(paths.email.path, "/email");

// --- 3. Declarative .ui(surface) ---
const declarative = new Agent("support", MODEL).instruct("Help users.").ui(ticketSurface);
assert.equal(declarative.inspect()._ui_spec, ticketSurface);

// --- 4. LLM-guided via the flag (no spec needed) ---
const guided = new Agent("creative", MODEL)
  .instruct("Build UIs.")
  .ui(undefined, { llmGuided: true });
const guidedSpec = guided.inspect()._ui_spec;
assert.ok(guidedSpec instanceof UIAutoSpec);
assert.equal((guidedSpec as UIAutoSpec).fromFlag, true);
assert.equal(guided.inspect()._a2uiAutoTool, true);
assert.equal(guided.inspect()._a2uiAutoGuard, true);

// --- 5. Cross-namespace: G.a2ui still composes with other guards ---
const composedGuard = G.pii().pipe(G.a2ui());
assert.ok(composedGuard instanceof GComposite);

// --- 6. P.uiSchema() and S.toUi() bridges still work ---
const ps = P.uiSchema();
assert.equal(ps.section, "UI Schema");
const toUi = S.toUi("total");
assert.ok(toUi instanceof STransform);

export { ticketSurface, declarative, guided };
