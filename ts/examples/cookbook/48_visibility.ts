/**
 * 48 — Visibility (show / hide)
 *
 * Mirrors `python/examples/cookbook/51_visibility_policies.py`.
 *
 * The TS API exposes per-agent visibility overrides via `.show()` and
 * `.hide()`. They set the private `_visibility` config key which is
 * stripped from `.build()` output but visible via `.inspect()`.
 *
 * Scenario: a 4-stage content pipeline (drafter → fact_checker →
 * compliance → publisher) where only the publisher's output should
 * reach the user. Intermediate agents are marked `hide()`, and a
 * single override (`compliance`) is force-shown for debugging.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const drafter = new Agent("drafter", MODEL)
  .instruct("Write a first draft of the article.")
  .writes("draft")
  .hide();

const factChecker = new Agent("fact_checker", MODEL)
  .instruct("Review the draft for factual accuracy: {draft}")
  .writes("checked_draft")
  .hide();

const compliance = new Agent("compliance", MODEL)
  .instruct("Review for brand guidelines and tone: {checked_draft}")
  .writes("compliance_report")
  .show(); // force-visible for debugging

const publisher = new Agent("publisher", MODEL)
  .instruct("Produce the final published version.")
  .writes("published");

const contentPipeline = new Pipeline("content_review")
  .step(drafter)
  .step(factChecker)
  .step(compliance)
  .step(publisher)
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

assert.equal(contentPipeline._type, "SequentialAgent");
assert.equal(contentPipeline.subAgents.length, 4);

// Visibility flag lives at the builder level (private) so the .build()
// dict does not carry it. Inspect each builder directly.
assert.equal(drafter.inspect()._visibility, "hide");
assert.equal(factChecker.inspect()._visibility, "hide");
assert.equal(compliance.inspect()._visibility, "show");

// Publisher does not set visibility — default is undefined (terminal
// agents are user-facing under the topology inference rules).
assert.equal(publisher.inspect()._visibility, undefined);

export { contentPipeline };
