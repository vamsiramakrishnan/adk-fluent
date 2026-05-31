/**
 * 12 — Guards (G namespace)
 *
 * Output validation as composable functions. Guards run as
 * before/after model callbacks; the `G` namespace ships ready-made guards
 * for length, JSON shape, PII, regex, budget, and more.
 */
import assert from "node:assert/strict";
import { Agent, G } from "../../src/index.js";

// Single guard via `G.length`.
const concise = new Agent("concise", "gemini-2.5-flash")
  .instruct("Answer in one sentence.")
  .guard(G.length({ max: 280 }))
  .build() as Record<string, unknown>;

// `.guard()` wires the composite into the after_model callback only (guards are
// single-phase: they validate/transform the response, so they run after the
// model — not double-registered into before_model).
assert.ok(concise.after_model_callback);
assert.ok(!concise.before_model_callback);

// Composed guards via `|` (TypeScript: `.pipe(...)` on the GComposite).
const safe = new Agent("safe", "gemini-2.5-flash")
  .instruct("Answer the user's question.")
  .guard(G.length({ max: 500 }).pipe(G.regex(/password|secret/i, { action: "redact" })))
  .build() as Record<string, unknown>;

assert.ok(safe.after_model_callback);
assert.ok(!safe.before_model_callback);

export { concise, safe };
