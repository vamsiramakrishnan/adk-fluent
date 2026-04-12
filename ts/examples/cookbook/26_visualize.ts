/**
 * 26 — Visualize topologies
 *
 * Every builder has a `.visualize()` method that renders its topology
 * to one of four formats:
 *
 *   - "ascii"    — `tree`-style listing for terminals and `.explain()`
 *   - "mermaid"  — `flowchart TD` source for markdown / GitHub PRs
 *   - "markdown" — full anatomy report (mermaid + facts + instructions)
 *   - "json"     — the underlying VizNode IR for custom renderers
 *
 * The same renderer also works on already-built tagged-config trees via
 * the top-level `visualize()` function — useful for hand-rolled configs,
 * deserialised state from another process, or output from the
 * Python-to-TypeScript transpiler.
 */
import assert from "node:assert/strict";
import { Agent, FanOut, Loop, Pipeline, Route, visualize } from "../../src/index.js";

const writer = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write a draft about {topic}.")
  .writes("draft");

const critic = new Agent("critic", "gemini-2.5-flash")
  .instruct("Score the {draft} 0-100. Reply `quality: <score>`.")
  .writes("quality");

const research = new FanOut("research")
  .branch(new Agent("web", "gemini-2.5-flash").instruct("Search the web for {topic}."))
  .branch(new Agent("papers", "gemini-2.5-flash").instruct("Search arXiv for {topic}."));

const refine = new Loop("refine").step(writer).step(critic).maxIterations(3);

const router = new Route("deliverable")
  .eq("memo", new Agent("memo", "gemini-2.5-flash").instruct("Format as a memo."))
  .otherwise(new Agent("brief", "gemini-2.5-flash").instruct("Format as a brief."));

const pipeline = new Pipeline("flow").step(research).step(refine).step(router);

// ── 1. ASCII tree (default) ──────────────────────────────────────────────────
const ascii = pipeline.visualize();
assert.ok(ascii.includes("flow"));
assert.ok(ascii.includes("[seq]"));
assert.ok(ascii.includes("[par]"));
assert.ok(ascii.includes("[loop]"));
assert.ok(ascii.includes("[route]"));

// ── 2. Mermaid flowchart ─────────────────────────────────────────────────────
const mermaid = pipeline.visualize({ format: "mermaid" });
assert.ok(mermaid.startsWith("flowchart TD"));
assert.ok(mermaid.includes("research"));
assert.ok(mermaid.includes("-->"));

// ── 3. Markdown anatomy report ───────────────────────────────────────────────
const md = pipeline.visualize({ format: "markdown" });
assert.ok(md.includes("```mermaid"));
assert.ok(md.includes("## flow"));
assert.ok(md.includes("| field | value |"));

// ── 4. JSON IR (custom renderers) ────────────────────────────────────────────
const ir = JSON.parse(pipeline.visualize({ format: "json" })) as { kind: string };
assert.equal(ir.kind, "sequence");

// ── 5. visualize() works on already-built tagged configs ─────────────────────
const built = pipeline.build();
const standalone = visualize(built, { format: "ascii" });
assert.equal(standalone, ascii);

export { pipeline, ascii, mermaid, md };
