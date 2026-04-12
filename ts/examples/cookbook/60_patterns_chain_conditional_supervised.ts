/**
 * 60 — Higher-order patterns: `chain`, `conditional`, `supervised`
 *
 * The `patterns` module ships short-hand constructors for common multi-
 * agent topologies. Each one takes builders and returns a builder.
 *
 *   chain(a, b, c)               — Pipeline of N agents
 *   conditional(pred, then, else?) — gated branch (then-only or if/else)
 *   supervised(worker, supervisor) — Loop until supervisor sets `approved`
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, Loop, chain, conditional, supervised } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// 1. chain — sequential pipeline shorthand.
const collect = new Agent("collect", MODEL).instruct("Collect requirements.").writes("reqs");
const design = new Agent("design", MODEL).instruct("Design from {reqs}.").writes("design");
const implement = new Agent("implement", MODEL).instruct("Implement {design}.");

const pipeline = chain(collect, design, implement);
assert.ok(pipeline instanceof Pipeline);
const pipelineBuilt = pipeline.build() as { _type: string; subAgents: unknown[] };
assert.equal(pipelineBuilt._type, "SequentialAgent");
assert.equal(pipelineBuilt.subAgents.length, 3);

// 2a. conditional — single-arm gate (no else).
const escalate = new Agent("escalate", MODEL).instruct("Escalate to a human.");
const onlyIfUrgent = conditional((s) => s.priority === "urgent", escalate);
// Single-arm conditional returns a `gate` primitive — build to inspect.
const onlyIfUrgentBuilt = onlyIfUrgent.build() as Record<string, unknown>;
assert.equal(onlyIfUrgentBuilt._kind, "gate");

// 2b. conditional — if/else, returns a Pipeline of two gates.
const refund = new Agent("refund", MODEL).instruct("Issue a refund.");
const declineRefund = new Agent("decline", MODEL).instruct("Decline politely.");
const ifElse = conditional(
  (s) => Number(s.amount ?? 0) < 100,
  refund,
  declineRefund,
);
assert.ok(ifElse instanceof Pipeline);
const ifElseBuilt = ifElse.build() as { subAgents: Array<{ _kind: string; name: string }> };
assert.equal(ifElseBuilt.subAgents.length, 2);
assert.equal(ifElseBuilt.subAgents[0]._kind, "gate");
assert.equal(ifElseBuilt.subAgents[1]._kind, "gate");
assert.equal(ifElseBuilt.subAgents[0].name, "if");
assert.equal(ifElseBuilt.subAgents[1].name, "else");

// 3. supervised — Loop until `approved` is truthy in state.
const writer = new Agent("writer", MODEL).instruct("Draft a contract clause.").writes("clause");
const lawyer = new Agent("lawyer", MODEL)
  .instruct("Review the clause. Set `approved` to true if it looks safe.")
  .writes("approved");

const sup = supervised(writer, lawyer, { approvedKey: "approved", maxRounds: 4 });
assert.ok(sup instanceof Loop);
const supBuilt = sup.build() as {
  _type: string;
  subAgents: unknown[];
  maxIterations: number;
};
assert.equal(supBuilt._type, "LoopAgent");
assert.equal(supBuilt.subAgents.length, 2);
assert.equal(supBuilt.maxIterations, 4);

// Custom name override.
const named = supervised(writer, lawyer, { name: "legal_review", maxRounds: 2 });
const namedBuilt = named.build() as { name: string };
assert.equal(namedBuilt.name, "legal_review");

export { pipeline, ifElse, sup };
