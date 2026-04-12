/**
 * 62 — Route: all matchers (`eq`, `ne`, `contains`, `gt`, `lt`, `gte`,
 * `lte`, `when`, `otherwise`)
 *
 * `Route(key)` is the deterministic state-based router. Each matcher
 * appends a branch — branches are evaluated in declaration order, with
 * `.otherwise()` providing the fallback. The built object is a tagged
 * `Route` config with `branches` and `default` slots.
 */
import assert from "node:assert/strict";
import { Agent, Route } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const vip = new Agent("vip_handler", MODEL).instruct("Premium white-glove support.");
const trial = new Agent("trial_handler", MODEL).instruct("Convert trial users.");
const free = new Agent("free_handler", MODEL).instruct("Standard support.");
const big = new Agent("big_account", MODEL).instruct("High value account.");
const small = new Agent("small_account", MODEL).instruct("Small ticket.");
const archived = new Agent("archived_handler", MODEL).instruct("Archived account.");
const fraudFlag = new Agent("fraud_handler", MODEL).instruct("Fraud review.");
const fallback = new Agent("default_handler", MODEL).instruct("Catch-all.");

// Stack matchers — evaluated top to bottom at runtime.
const router = new Route("tier")
  .eq("VIP", vip)
  .ne("archived", archived) // anything except archived
  .contains("trial", trial)
  .gt(10000, big)
  .lt(100, small)
  .gte(1000, vip)
  .lte(50, free)
  .when((s) => Boolean(s.fraud_score && Number(s.fraud_score) > 0.9), fraudFlag)
  .otherwise(fallback);

const built = router.build() as {
  _type: string;
  key: string;
  branches: Array<{ label: string; predicate: (s: Record<string, unknown>) => boolean }>;
  default: Record<string, unknown>;
};

assert.equal(built._type, "Route");
assert.equal(built.key, "tier");
assert.equal(built.branches.length, 8);
assert.ok(built.default);

// Branch labels record the matcher type and value.
const labels = built.branches.map((b) => b.label);
assert.deepEqual(labels, [
  "eq:VIP",
  "ne:archived",
  "contains:trial",
  "gt:10000",
  "lt:100",
  "gte:1000",
  "lte:50",
  "when",
]);

// Predicates are real functions — exercise each one.
const [eqB, neB, containsB, gtB, ltB, gteB, lteB, whenB] = built.branches;
assert.equal(eqB.predicate({ tier: "VIP" }), true);
assert.equal(eqB.predicate({ tier: "free" }), false);
assert.equal(neB.predicate({ tier: "active" }), true);
assert.equal(neB.predicate({ tier: "archived" }), false);
assert.equal(containsB.predicate({ tier: "trial-30d" }), true);
assert.equal(containsB.predicate({ tier: "VIP" }), false);
assert.equal(gtB.predicate({ tier: 25000 }), true);
assert.equal(gtB.predicate({ tier: 5000 }), false);
assert.equal(ltB.predicate({ tier: 50 }), true);
assert.equal(gteB.predicate({ tier: 1000 }), true);
assert.equal(gteB.predicate({ tier: 999 }), false);
assert.equal(lteB.predicate({ tier: 50 }), true);
assert.equal(lteB.predicate({ tier: 51 }), false);
assert.equal(whenB.predicate({ tier: 100, fraud_score: 0.95 }), true);
assert.equal(whenB.predicate({ tier: 100, fraud_score: 0.1 }), false);

// `default` is the otherwise() fallback, auto-built.
assert.equal((built.default as { name: string }).name, "default_handler");

export { router };
