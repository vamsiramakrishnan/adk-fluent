/**
 * 04 — Sequential Pipeline
 *
 * Contract review system: extractor → risk_analyst → summarizer.
 *
 * Demonstrates the `Pipeline` builder, which wraps `SequentialAgent`. Each
 * `.step()` accepts a sub-builder and is auto-built at `.build()` time.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline } from "../../src/index.js";

const pipeline = new Pipeline("contract_review")
  .step(
    new Agent("extractor", "gemini-2.5-flash").instruct(
      "Extract key terms from the contract: parties involved, " +
        "effective dates, payment terms, and termination clauses.",
    ),
  )
  .step(
    new Agent("risk_analyst", "gemini-2.5-flash").instruct(
      "Analyze the extracted terms for legal risks. Flag unusual clauses.",
    ),
  )
  .step(
    new Agent("summarizer", "gemini-2.5-flash").instruct(
      "Produce a one-page executive summary in clear, non-legal language.",
    ),
  )
  .build() as Record<string, unknown>;

assert.equal(pipeline._type, "SequentialAgent");
const subs = pipeline.subAgents as Record<string, unknown>[];
assert.equal(subs.length, 3);
assert.equal(subs[0].name, "extractor");
assert.equal(subs[1].name, "risk_analyst");
assert.equal(subs[2].name, "summarizer");

export { pipeline };
