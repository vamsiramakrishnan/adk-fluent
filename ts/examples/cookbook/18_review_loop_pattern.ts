/**
 * 18 — Review Loop Pattern
 *
 * Worker → reviewer, looping until the reviewer signals quality is high
 * enough or `maxRounds` is hit. The `reviewLoop` higher-order constructor
 * wires this up in one call.
 */
import assert from "node:assert/strict";
import { Agent, reviewLoop } from "../../src/index.js";

const writer = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write a 3-paragraph essay about {topic}.")
  .writes("draft");

const reviewer = new Agent("reviewer", "gemini-2.5-flash")
  .instruct("Score the draft 0-100 and write `quality: <score>` in your reply.")
  .writes("review");

const loop = reviewLoop(writer, reviewer, {
  qualityKey: "quality",
  target: 85,
  maxRounds: 3,
}).build() as Record<string, unknown>;

assert.equal(loop._type, "LoopAgent");
assert.equal(loop.maxIterations, 3);
assert.equal((loop.subAgents as unknown[]).length, 2);

export { loop };
