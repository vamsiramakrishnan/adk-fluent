/**
 * 19 — Map-Reduce Pattern
 *
 * Apply `mapper` to every item in `state.items`, then aggregate with
 * `reducer`. Common shape for "summarize 50 documents", "score 1k records",
 * etc.
 */
import assert from "node:assert/strict";
import { Agent, mapReduce } from "../../src/index.js";

const summarizeOne = new Agent("summarize", "gemini-2.5-flash")
  .instruct("Summarize the document in 1 sentence.")
  .writes("summary");

const aggregate = new Agent("aggregate", "gemini-2.5-flash")
  .instruct("Combine all summaries into a single executive overview.")
  .writes("report");

const pipeline = mapReduce(summarizeOne, aggregate, {
  itemsKey: "documents",
  resultKey: "report",
}).build() as Record<string, unknown>;

assert.equal(pipeline._type, "SequentialAgent");
assert.equal((pipeline.subAgents as unknown[]).length, 2);

export { pipeline };
