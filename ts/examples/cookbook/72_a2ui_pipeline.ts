/**
 * 72 — A2UI Pipeline: UI in Multi-Agent Pipelines
 *
 * Demonstrates using S.toUi() and S.fromUi() to bridge state data
 * between agents and A2UI surfaces in pipeline workflows.
 *
 * Cookbook covers:
 *   - S.toUi() bridge agent state to A2UI data model
 *   - S.fromUi() bridge A2UI data model back to agent state
 *   - M.a2uiLog() log A2UI surface operations
 *   - C.withUi() include UI surface state in context
 *   - Pipeline pattern with UI-attached agents
 */
import assert from "node:assert/strict";
import { Agent, UI, S, C, M, STransform, MComposite, CTransform } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// --- 1. S.toUi() creates a state transform ---
const toUi = S.toUi("total", "count");
assert.ok(toUi instanceof STransform);
assert.match(toUi.name, /toUi/);
assert.match(toUi.name, /total/);
assert.match(toUi.name, /count/);

// --- 2. S.fromUi() creates a state transform ---
const fromUi = S.fromUi("name", "email");
assert.ok(fromUi instanceof STransform);
assert.match(fromUi.name, /fromUi/);
assert.match(fromUi.name, /name/);
assert.match(fromUi.name, /email/);

// --- 3. S.toUi() applies as a transform ---
const state = { total: 42, count: 10, other: "ignored" };
const bridged = toUi.apply(state);
assert.ok(bridged != null);

// --- 4. S.fromUi() applies as a transform ---
const uiState = { _a2ui_data_form: { name: "Alice", email: "alice@example.com" } };
const extracted = fromUi.apply(uiState);
assert.ok(extracted != null);

// --- 5. M.a2uiLog() middleware ---
const logMw = M.a2uiLog();
assert.ok(logMw instanceof MComposite);

const debugLog = M.a2uiLog({ level: "debug" });
assert.ok(debugLog instanceof MComposite);

// --- 6. C.withUi() context ---
const uiCtx = C.withUi("dashboard");
assert.ok(uiCtx instanceof CTransform);

// --- 7. Pipeline pattern with UI ---
const calcAgent = new Agent("calc", MODEL).instruct("Calculate totals.").writes("total");

const renderer = new Agent("renderer", MODEL)
  .instruct("Display results.")
  .ui(
    UI.dashboard("Metrics", {
      cards: [
        { label: "Total", value: "0" },
        { label: "Count", value: "0" },
      ],
    }),
  );

// Both agents build correctly
const calcBuilt = calcAgent.build() as Record<string, unknown>;
assert.equal(calcBuilt.name, "calc");

const rendererBuilt = renderer.build() as Record<string, unknown>;
assert.equal(rendererBuilt.name, "renderer");

export { toUi, fromUi, calcAgent, renderer };
