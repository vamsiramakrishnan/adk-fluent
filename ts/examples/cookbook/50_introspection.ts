/**
 * 50 — Introspection: inspect / visualize / toString
 *
 * The TS API exposes three lightweight introspection helpers:
 *   - `.inspect()`    — snapshot of the builder config (incl. private keys)
 *   - `.visualize()`  — render topology as ascii / mermaid / markdown
 *   - `.toString()`   — single-line debug label
 *
 * These work on agents AND workflow builders.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, FanOut } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const researcher = new Agent("researcher", MODEL)
  .instruct("Research the topic: {topic}")
  .writes("findings");

const writer = new Agent("writer", MODEL)
  .instruct("Write an article from {findings}")
  .writes("draft");

const reviewer = new Agent("reviewer", MODEL)
  .instruct("Review the draft: {draft}")
  .writes("review");

// 1. inspect() — surfaces every config key the builder has set.
const snapshot = researcher.inspect();
assert.equal(snapshot.name, "researcher");
assert.equal(snapshot.model, MODEL);
assert.equal(snapshot.instruction, "Research the topic: {topic}");
assert.equal(snapshot.output_key, "findings");

// 2. toString() — single-line label using the constructor + name.
assert.equal(researcher.toString(), 'Agent("researcher")');

const pipeline = new Pipeline("research_flow").step(researcher).step(writer).step(reviewer);
assert.equal(pipeline.toString(), 'Pipeline("research_flow")');

// 3. visualize() — default ascii rendering.
const ascii = pipeline.visualize();
assert.equal(typeof ascii, "string");
assert.ok(ascii.length > 0);
assert.ok(ascii.includes("research_flow"));

// 4. visualize({ format: "mermaid" }) — for docs/runbooks.
const mermaid = pipeline.visualize({ format: "mermaid" });
assert.equal(typeof mermaid, "string");
for (const name of ["researcher", "writer", "reviewer"]) {
  assert.ok(mermaid.includes(name), `mermaid missing ${name}`);
}

// 5. Works on FanOut topologies too.
const fanout = new FanOut("parallel_research")
  .branch(new Agent("web", MODEL).instruct("Search web."))
  .branch(new Agent("papers", MODEL).instruct("Search papers."));
const fanoutMermaid = fanout.visualize({ format: "mermaid" });
assert.ok(fanoutMermaid.includes("web"));
assert.ok(fanoutMermaid.includes("papers"));

// 6. inspect() also surfaces callback counts.
const monitored = new Agent("monitored", MODEL)
  .instruct("Watched agent.")
  .beforeModel(() => undefined)
  .afterModel(() => undefined)
  .afterModel(() => undefined);
const monitoredSnap = monitored.inspect();
assert.equal(monitoredSnap["callbacks.before_model_callback"], 1);
assert.equal(monitoredSnap["callbacks.after_model_callback"], 2);

export { pipeline, fanout, monitored };
