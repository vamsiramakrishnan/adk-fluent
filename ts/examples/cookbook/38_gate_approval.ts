/**
 * 38 — `gate()`: conditional execution / human approval
 *
 * Mirrors `python/examples/cookbook/41_gate_approval.py`.
 *
 * `gate(pred, agent)` runs the wrapped agent only when `pred(state)` is
 * true. In the Python cookbook this is used to pause for human approval
 * on high-risk legal documents; in TypeScript the same primitive wraps a
 * downstream agent so it only fires when the gate condition holds.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, gate } from "../../src/index.js";

// gate() wraps a downstream agent with a predicate.
const finalizer = new Agent("contract_finalizer", "gemini-2.5-flash").instruct(
  "Finalize the contract with the approved terms.",
);
const gated = gate((s) => s.liability_risk === "high", finalizer, "high_risk_gate");

const built = gated.build() as Record<string, unknown>;
assert.equal(built._kind, "gate");
assert.equal(built.name, "high_risk_gate");
assert.equal(typeof built._pred, "function");

// The predicate fires correctly.
const pred = built._pred as (s: Record<string, unknown>) => boolean;
assert.equal(pred({ liability_risk: "high" }), true);
assert.equal(pred({ liability_risk: "low" }), false);

// The wrapped agent is preserved on the primitive's `_agents` list.
const agents = built._agents as Record<string, unknown>[];
assert.equal(agents.length, 1);
assert.equal(agents[0].name, "contract_finalizer");

// Compose into a multi-stage legal review pipeline. The drafter always
// runs; the finalizer only fires when the contract is high-risk.
const contractPipeline = new Pipeline("contract_review")
  .step(
    new Agent("clause_analyzer", "gemini-2.5-flash")
      .instruct("Analyze the contract clauses and assess liability risk.")
      .writes("liability_risk"),
  )
  .step(gated)
  .build() as { subAgents: Record<string, unknown>[] };

assert.equal(contractPipeline.subAgents.length, 2);
assert.equal(contractPipeline.subAgents[1]._kind, "gate");

export { contractPipeline };
