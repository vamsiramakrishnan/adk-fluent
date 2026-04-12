/**
 * 06 — Loop Agent
 *
 * Iterative draft refinement: writer → critic, repeated up to 3 times.
 *
 * Demonstrates the `Loop` builder which wraps `LoopAgent`. The body runs
 * in sequence; the loop terminates when `maxIterations` is hit or the
 * optional `until()` predicate becomes true.
 */
import assert from "node:assert/strict";
import { Agent, Loop } from "../../src/index.js";

const refiner = new Loop("refine")
  .step(
    new Agent("writer", "gemini-2.5-flash")
      .instruct("Write a 3-paragraph draft about {topic}.")
      .writes("draft"),
  )
  .step(
    new Agent("critic", "gemini-2.5-flash")
      .instruct("Critique the draft. Set state.done=true if it's ready.")
      .writes("feedback"),
  )
  .maxIterations(3)
  .until((s) => Boolean(s.done))
  .build() as Record<string, unknown>;

assert.equal(refiner._type, "LoopAgent");
assert.equal(refiner.maxIterations, 3);
assert.equal((refiner.subAgents as unknown[]).length, 2);

export { refiner };
