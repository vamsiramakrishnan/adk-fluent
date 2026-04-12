/**
 * 10 — Fallback Operator (.fallback)
 *
 * Try a fast/cheap model first; on failure, fall back to a strong model.
 * Mirrors Python's `fast // strong` operator.
 */
import assert from "node:assert/strict";
import { Agent, Fallback } from "../../src/index.js";

const fast = new Agent("fast", "gemini-2.5-flash").instruct("Answer concisely.");
const strong = new Agent("strong", "gemini-2.5-pro").instruct("Answer carefully.");

// Method-chained form: a.fallback(b)
const chained = fast.fallback(strong).build() as Record<string, unknown>;
assert.equal(chained._type, "Fallback");
assert.equal((chained.children as unknown[]).length, 2);

// Builder form for explicit chains.
const explicit = new Fallback("resilient").attempt(fast).attempt(strong).build() as Record<
  string,
  unknown
>;
assert.equal(explicit._type, "Fallback");
assert.equal((explicit.children as unknown[]).length, 2);

export { chained, explicit };
