/**
 * 09 — Route Branching
 *
 * Deterministic state-based routing. Use `Route` when the next step is
 * decided by a rule (a state field) rather than by the LLM. Faster, cheaper,
 * and easier to test than LLM-based delegation.
 */
import assert from "node:assert/strict";
import { Agent, Route } from "../../src/index.js";

const vip = new Agent("vip_handler", "gemini-2.5-flash").instruct("White-glove treatment.");
const trial = new Agent("trial_handler", "gemini-2.5-flash").instruct("Encourage upgrade.");
const standard = new Agent("standard_handler", "gemini-2.5-flash").instruct("Standard reply.");

const router = new Route("tier")
  .eq("VIP", vip)
  .contains("trial", trial)
  .otherwise(standard)
  .build() as Record<string, unknown>;

assert.equal(router._type, "Route");
assert.equal(router.key, "tier");
const branches = router.branches as {
  label: string;
  predicate: (s: Record<string, unknown>) => boolean;
}[];
assert.equal(branches.length, 2);
assert.equal(branches[0].label, "eq:VIP");
assert.equal(branches[1].label, "contains:trial");

// Predicates work directly on a state object — no LLM call needed.
assert.equal(branches[0].predicate({ tier: "VIP" }), true);
assert.equal(branches[0].predicate({ tier: "free" }), false);
assert.equal(branches[1].predicate({ tier: "trial-30d" }), true);

export { router };
