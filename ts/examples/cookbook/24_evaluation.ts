/**
 * 24 — Evaluation (E namespace)
 *
 * Build evaluation suites for an agent. Compose criteria with `.pipe()`,
 * add cases via `E.case_`, and run a suite (or compare multiple agents
 * side-by-side) via `E.suite` / `E.compare`.
 *
 * Criteria are pluggable — they describe *what* to score; the runtime
 * resolves *how*.
 */
import assert from "node:assert/strict";
import { Agent, E } from "../../src/index.js";

const summarizer = new Agent("summarizer", "gemini-2.5-flash").instruct(
  "Summarize the input in 1-2 sentences.",
);

// Compose criteria: ROUGE-1 match + LLM-judge semantic match + safety.
const criteria = E.responseMatch({ threshold: 0.7 })
  .pipe(E.semanticMatch({ threshold: 0.8 }))
  .pipe(E.safety({ threshold: 1.0 }));
assert.equal(criteria.toArray().length, 3);

// Build a suite with three cases.
const suite = E.suite(summarizer)
  .add(
    E.case_("Summarize: 'The quick brown fox jumps over the lazy dog.'", {
      expect: "A fox jumps over a dog.",
    }),
  )
  .add(E.case_("Summarize: 'Roses are red, violets are blue.'", { expect: "A short rhyme." }))
  .withCriteria(criteria);

assert.equal(suite.cases.length, 2);
assert.equal(suite.criteria.length, 1);

// Side-by-side comparison: same eval set across two agents.
const fast = new Agent("fast", "gemini-2.5-flash-lite").instruct("Answer.");
const slow = new Agent("careful", "gemini-2.5-pro").instruct("Reason carefully then answer.");
const comparison = E.compare(fast, slow).add(E.case_("What is 17 * 23?", { expect: "391" }));
assert.equal(comparison.agents.length, 2);
assert.equal(comparison.cases.length, 1);

// Personas for user-simulation cases.
const expert = E.persona.expert();
assert.equal(expert.id, "expert");

export { suite, comparison };
