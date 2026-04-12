/**
 * 55 — Nested pipelines (Pipeline of Pipelines)
 *
 * Workflow builders are themselves builders, so they can be nested
 * inside other workflow builders. A common pattern: an outer Pipeline
 * whose middle stage is a FanOut, where one branch is itself another
 * Pipeline. The auto-build machinery walks the tree top-down.
 *
 * Topology built here:
 *
 *   outer (Pipeline)
 *     ├── intake          (Agent)
 *     ├── fanout (FanOut)
 *     │     ├── web_branch (Pipeline)
 *     │     │     ├── web_search (Agent)
 *     │     │     └── web_summarize (Agent)
 *     │     └── docs_branch (Pipeline)
 *     │           ├── docs_search (Agent)
 *     │           └── docs_summarize (Agent)
 *     └── final_writeup    (Agent)
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, FanOut } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const intake = new Agent("intake", MODEL)
  .instruct("Capture the user's research question into structured form.")
  .writes("question");

const webSearch = new Agent("web_search", MODEL)
  .instruct("Search the web for: {question}")
  .writes("web_results");
const webSummarize = new Agent("web_summarize", MODEL)
  .instruct("Summarise these web results: {web_results}")
  .writes("web_summary");

const docsSearch = new Agent("docs_search", MODEL)
  .instruct("Search internal docs for: {question}")
  .writes("docs_results");
const docsSummarize = new Agent("docs_summarize", MODEL)
  .instruct("Summarise these doc hits: {docs_results}")
  .writes("docs_summary");

const webBranch = new Pipeline("web_branch").step(webSearch).step(webSummarize);
const docsBranch = new Pipeline("docs_branch").step(docsSearch).step(docsSummarize);

const fanout = new FanOut("research_fanout").branch(webBranch).branch(docsBranch);

const finalWriteup = new Agent("final_writeup", MODEL)
  .instruct("Combine {web_summary} and {docs_summary} into a final report.")
  .writes("report");

const outer = new Pipeline("research_outer")
  .step(intake)
  .step(fanout)
  .step(finalWriteup)
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

// Outer is a SequentialAgent of 3 stages.
assert.equal(outer._type, "SequentialAgent");
assert.equal(outer.subAgents.length, 3);
assert.equal((outer.subAgents[0] as { name: string }).name, "intake");

// Middle stage is a ParallelAgent with two pipeline branches.
const fanoutBuilt = outer.subAgents[1] as {
  _type: string;
  subAgents: Record<string, unknown>[];
};
assert.equal(fanoutBuilt._type, "ParallelAgent");
assert.equal(fanoutBuilt.subAgents.length, 2);

// Each branch is itself a SequentialAgent with 2 sub-agents.
const webBuilt = fanoutBuilt.subAgents[0] as {
  _type: string;
  name: string;
  subAgents: Record<string, unknown>[];
};
assert.equal(webBuilt._type, "SequentialAgent");
assert.equal(webBuilt.name, "web_branch");
assert.equal(webBuilt.subAgents.length, 2);
assert.equal((webBuilt.subAgents[0] as { name: string }).name, "web_search");

const docsBuilt = fanoutBuilt.subAgents[1] as {
  _type: string;
  name: string;
  subAgents: Record<string, unknown>[];
};
assert.equal(docsBuilt._type, "SequentialAgent");
assert.equal(docsBuilt.name, "docs_branch");
assert.equal(docsBuilt.subAgents.length, 2);

// Final stage round-trips its output_key.
const finalBuilt = outer.subAgents[2] as { name: string; output_key: string };
assert.equal(finalBuilt.name, "final_writeup");
assert.equal(finalBuilt.output_key, "report");

export { outer };
