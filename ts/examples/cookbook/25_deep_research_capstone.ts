/**
 * 25 — Deep Research (capstone)
 *
 * Pulls multiple cookbook patterns into one realistic pipeline:
 *
 *   1. Parallel fan-out: query web, papers, and news in parallel.
 *   2. Sequential merge: synthesize findings into a draft.
 *   3. Review loop: critic re-runs the writer until quality is high.
 *   4. Route: pick the final formatter based on requested deliverable.
 *   5. Guards: enforce length + redact secrets on the final output.
 *
 * The shape mirrors how you'd build a "deep research" agent in Python
 * adk-fluent — but expressed in TypeScript with method-chained operators.
 */
import assert from "node:assert/strict";
import { Agent, FanOut, G, Route, reviewLoop } from "../../src/index.js";

// ── 1. Parallel research fan-out ─────────────────────────────────────────────
const webSearch = new Agent("web", "gemini-2.5-flash")
  .describe("Searches the open web for recent coverage.")
  .instruct("Search the web for recent coverage of {topic}. Return 5 key findings.")
  .writes("web_findings");

const paperSearch = new Agent("papers", "gemini-2.5-flash")
  .describe("Searches academic literature.")
  .instruct("Search arXiv / Semantic Scholar for {topic}. Return 5 citations.")
  .writes("paper_findings");

const newsSearch = new Agent("news", "gemini-2.5-flash")
  .describe("Searches news outlets.")
  .instruct("Search news for {topic} in the last 30 days. Return 5 headlines.")
  .writes("news_findings");

const research = new FanOut("research").branch(webSearch).branch(paperSearch).branch(newsSearch);

// ── 2. Synthesis + 3. review loop ────────────────────────────────────────────
const writer = new Agent("writer", "gemini-2.5-pro")
  .instruct("Synthesise {web_findings}, {paper_findings}, {news_findings} into a 1-page brief.")
  .writes("draft");

const critic = new Agent("critic", "gemini-2.5-flash")
  .instruct(
    "Score the draft 0-100 on clarity, completeness, and citation quality. Reply `quality: <score>`.",
  )
  .writes("quality");

const refined = reviewLoop(writer, critic, {
  qualityKey: "quality",
  target: 85,
  maxRounds: 3,
});

// ── 4. Routing on requested deliverable ──────────────────────────────────────
const exec = new Agent("exec_summary", "gemini-2.5-flash")
  .instruct("Compress {draft} into a 5-bullet executive summary.")
  .writes("final");

const slides = new Agent("slides_outline", "gemini-2.5-flash")
  .instruct("Convert {draft} into a 10-slide deck outline.")
  .writes("final");

const memo = new Agent("memo", "gemini-2.5-flash")
  .instruct("Format {draft} as a 1-page internal memo.")
  .writes("final");

const formatter = new Route("deliverable")
  .eq("exec_summary", exec)
  .eq("slides", slides)
  .otherwise(memo);

// ── 5. Final guard: length cap + redact secrets ──────────────────────────────
const safetyGuards = G.length({ max: 4000 }).pipe(
  G.regex(/(api[_-]?key|password|secret)/i, { action: "redact", replacement: "[REDACTED]" }),
);

const guarded = new Agent("publisher", "gemini-2.5-flash")
  .instruct("Return the final deliverable from {final} verbatim.")
  .guard(safetyGuards);

// ── Compose the whole pipeline ───────────────────────────────────────────────
const pipeline = research.then(refined).then(formatter).then(guarded).build() as Record<
  string,
  unknown
>;

assert.equal(pipeline._type, "SequentialAgent");
const stages = pipeline.subAgents as Record<string, unknown>[];
assert.equal(stages.length, 4);
assert.equal(stages[0]._type, "ParallelAgent");
assert.equal(stages[1]._type, "LoopAgent");
assert.equal(stages[2]._type, "Route");
assert.equal(stages[3]._type, "LlmAgent");

export { pipeline };
