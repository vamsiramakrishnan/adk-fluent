/**
 * 17 — Primitives (tap, expect, gate, race, mapOver)
 *
 * Function-level building blocks that interleave with agents inside a
 * pipeline. They're zero-cost (no LLM calls) and excellent for inline
 * observation, assertion, and control flow.
 */
import assert from "node:assert/strict";
import { Agent, tap, expect as expectStep, gate, race, mapOver } from "../../src/index.js";

const writer = new Agent("writer", "gemini-2.5-flash").instruct("Write a draft.").writes("draft");
const reviewer = new Agent("reviewer", "gemini-2.5-flash").instruct("Review {draft}.");

// tap — observe state without mutating it
const observed = tap((s) => {
  // Log/record/metric — anything that doesn't change state.
  void s;
});

// expect — contract assertion (raises if pred is false)
const requireDraft = expectStep((s) => "draft" in s, "draft must be set before review");

// gate — conditional execution
const onlyIfReady = gate((s) => Boolean(s.ready), reviewer);

// race — first-to-finish wins
const fastest = race(
  new Agent("source_a", "gemini-2.5-flash"),
  new Agent("source_b", "gemini-2.5-flash"),
);

// mapOver — apply an agent across a list in state
const perItem = mapOver("items", new Agent("classify", "gemini-2.5-flash"));

// Compose them into a single pipeline
const pipeline = writer.then(observed).then(requireDraft).then(onlyIfReady);
const built = pipeline.build() as Record<string, unknown>;
assert.equal(built._type, "SequentialAgent");
assert.equal((built.subAgents as unknown[]).length, 4);

assert.equal((fastest.build() as Record<string, unknown>)._type, "Primitive");
assert.equal((perItem.build() as Record<string, unknown>)._type, "Primitive");

export { pipeline, fastest, perItem };
