/**
 * 08 — Operator Composition (.then / .parallel / .times)
 *
 * Python uses operators (`>>`, `|`, `*`); TypeScript uses method chains
 * because JS has no operator overloading. The shapes that come out are
 * identical.
 *
 *   Python:      (a >> b) | c
 *   TypeScript:  a.then(b).parallel(c)
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

const a = new Agent("a", "gemini-2.5-flash").instruct("Step A.");
const b = new Agent("b", "gemini-2.5-flash").instruct("Step B.");
const c = new Agent("c", "gemini-2.5-flash").instruct("Step C.");

// a.then(b)  ─ Sequential
const seq = a.then(b).build() as Record<string, unknown>;
assert.equal(seq._type, "SequentialAgent");
assert.equal((seq.subAgents as unknown[]).length, 2);

// a.parallel(b)  ─ Parallel
const par = a.parallel(b).build() as Record<string, unknown>;
assert.equal(par._type, "ParallelAgent");
assert.equal((par.subAgents as unknown[]).length, 2);

// (a.then(b)).times(3)  ─ Loop wrapping a Pipeline body
const loop = a.then(b).times(3).build() as Record<string, unknown>;
assert.equal(loop._type, "LoopAgent");
assert.equal(loop.maxIterations, 3);
assert.equal((loop.subAgents as unknown[]).length, 2);

// (a.then(b)).parallel(c)  ─ FanOut wrapping a Pipeline + a single agent
const composed = a.then(b).parallel(c).build() as Record<string, unknown>;
assert.equal(composed._type, "ParallelAgent");
assert.equal((composed.subAgents as unknown[]).length, 2);

export { seq, par, loop, composed };
