/**
 * 28 — Plain functions as pipeline steps
 *
 * Mirrors `python/examples/cookbook/29_function_steps.py`.
 *
 * Not every step in a workflow needs an LLM. `Pipeline.step(fn)` accepts
 * a plain function — perfect for ETL, parsing, validation, or any
 * deterministic transform that would otherwise waste tokens.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline } from "../../src/index.js";

function normalizeQuery(state: Record<string, unknown>): Record<string, unknown> {
  const q = String(state.query ?? "")
    .trim()
    .toLowerCase();
  return { ...state, query: q };
}

function tagPriority(state: Record<string, unknown>): Record<string, unknown> {
  const q = String(state.query ?? "");
  const priority = q.includes("urgent") ? "high" : "normal";
  return { ...state, priority };
}

const responder = new Agent("responder", "gemini-2.5-flash")
  .instruct("Respond to {query} with priority={priority}.")
  .writes("response");

const pipelineBuilt = new Pipeline("etl_then_llm")
  .step(normalizeQuery)
  .step(tagPriority)
  .step(responder)
  .build() as { _type: string; subAgents: unknown[] };

assert.equal(pipelineBuilt._type, "SequentialAgent");
assert.equal(pipelineBuilt.subAgents.length, 3);

// The plain function steps pass through unchanged; only the LlmAgent
// gets a .name property.
const llm = pipelineBuilt.subAgents[2] as { name?: string };
assert.equal(llm.name, "responder");

// And the function steps are still callable functions, ready to be
// wrapped at runtime by an executor.
assert.equal(typeof pipelineBuilt.subAgents[0], "function");
assert.equal(typeof pipelineBuilt.subAgents[1], "function");

export { pipelineBuilt as pipeline };
