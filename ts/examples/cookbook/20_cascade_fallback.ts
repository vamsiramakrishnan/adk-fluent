/**
 * 20 — Cascade Fallback Pattern
 *
 * Try the cheapest model first, fall back to mid-tier, then to the most
 * capable. Saves cost on the easy queries while preserving correctness on
 * the hard ones.
 */
import assert from "node:assert/strict";
import { Agent, cascade } from "../../src/index.js";

const tier1 = new Agent("tier1", "gemini-2.5-flash-lite").instruct("Answer concisely.");
const tier2 = new Agent("tier2", "gemini-2.5-flash").instruct("Answer carefully.");
const tier3 = new Agent("tier3", "gemini-2.5-pro").instruct("Reason step by step.");

const resilient = cascade(tier1, tier2, tier3).build() as Record<string, unknown>;

assert.equal(resilient._type, "Fallback");
assert.equal((resilient.children as unknown[]).length, 3);

export { resilient };
