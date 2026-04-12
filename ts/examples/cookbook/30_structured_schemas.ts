/**
 * 30 — Structured output schemas with `.outputAs()`
 *
 * Mirrors `python/examples/cookbook/53_structured_schemas.py`.
 *
 * In Python, `.returns(Schema)` (or the `agent @ Schema` operator)
 * forces an LLM to emit JSON matching a Pydantic model. In TypeScript
 * we use the equivalent `.outputAs(schema)` method, with Zod as the
 * idiomatic schema library (any object works at the builder level —
 * the schema flows straight through to ADK).
 */
import assert from "node:assert/strict";
import { Agent, Pipeline } from "../../src/index.js";

// Schema objects can be plain markers in the builder layer; the runtime
// will pass them through to ADK as-is.
const ClaimIntake = {
  type: "object",
  fields: ["claimant_name", "policy_number", "incident_date", "description"],
};

const RiskAssessment = {
  type: "object",
  fields: ["risk_level", "flags", "recommended_action"],
};

const intake = new Agent("intake_agent", "gemini-2.5-flash")
  .instruct("Extract claim details from the raw submission. Return JSON only.")
  .outputAs(ClaimIntake)
  .writes("intake_data");

const risk = new Agent("risk_agent", "gemini-2.5-flash")
  .instruct("Analyze the claim intake data and determine the risk level.")
  .outputAs(RiskAssessment)
  .writes("risk_report");

const summary = new Agent("summary_agent", "gemini-2.5-flash").instruct(
  "Produce a plain-language summary for the claims adjuster.",
);

// _output_schema is a private config key kept on the builder for the
// @google/adk runtime adapter to read. Inspect verifies it's attached.
assert.equal(intake.inspect()._output_schema, ClaimIntake);
assert.equal((intake.build() as Record<string, unknown>).output_key, "intake_data");
assert.equal(risk.inspect()._output_schema, RiskAssessment);

// .outputAs() is immutable: a new builder is returned and the original
// stays schema-free.
const baseAgent = new Agent("intake_agent", "gemini-2.5-flash").instruct(
  "Extract claim details and return structured JSON.",
);
const typedAgent = baseAgent.outputAs(ClaimIntake);
assert.equal(baseAgent.inspect()._output_schema, undefined);
assert.equal(typedAgent.inspect()._output_schema, ClaimIntake);

// Wire it all into a pipeline.
const pipeline = new Pipeline("claim_flow").step(intake).step(risk).step(summary).build() as {
  _type: string;
  subAgents: Record<string, unknown>[];
};
assert.equal(pipeline._type, "SequentialAgent");
assert.equal(pipeline.subAgents.length, 3);
assert.equal(pipeline.subAgents[0].name, "intake_agent");
assert.equal(pipeline.subAgents[2].name, "summary_agent");

export { pipeline };
