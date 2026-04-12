/**
 * 47 — Full operator algebra in one expression
 *
 * Mirrors `python/examples/cookbook/34_full_algebra.py`.
 *
 * Code review pipeline using every composition operator the TS API
 * exposes (Python's `>> | * // @` translated to method chains):
 *
 *   diff_parser
 *     .then(style.parallel(security).parallel(logic))   // >> + |
 *     .then(aggregator.outputAs(ReviewVerdict)           // >> + @
 *           .fallback(backup.outputAs(ReviewVerdict)))   // //
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, FanOut, Fallback } from "../../src/index.js";

const FAST = "gemini-2.5-flash";
const STRONG = "gemini-2.5-pro";

const ReviewVerdict = {
  type: "object",
  fields: ["has_issues", "critical_count", "summary"],
};

const diffParser = new Agent("diff_parser", FAST)
  .instruct("Parse the git diff into individual file changes with context.")
  .writes("parsed_diff");

const styleChecker = new Agent("style_checker", FAST).instruct(
  "Check code style: naming conventions, formatting, docstrings.",
);
const securityScanner = new Agent("security_scanner", FAST).instruct(
  "Scan for security issues: injection, auth bypass, secrets in code.",
);
const logicReviewer = new Agent("logic_reviewer", FAST).instruct(
  "Review business logic: edge cases, error handling, race conditions.",
);

// `.parallel()` chains: a | b | c -> a.parallel(b).parallel(c)
const reviewers = styleChecker.parallel(securityScanner).parallel(logicReviewer);
assert.ok(reviewers instanceof FanOut);

const aggregator = new Agent("finding_aggregator", FAST)
  .instruct("Aggregate all review findings into a final verdict.")
  .outputAs(ReviewVerdict);

const backup = new Agent("backup_aggregator", STRONG)
  .instruct("Aggregate all review findings into a final verdict.")
  .outputAs(ReviewVerdict);

const aggregatorWithFallback = aggregator.fallback(backup);
assert.ok(aggregatorWithFallback instanceof Fallback);

// Compose with `.then()` — single expression mirrors Python `>>` chain.
const reviewPipeline = diffParser.then(reviewers).then(aggregatorWithFallback);
assert.ok(reviewPipeline instanceof Pipeline);

const built = reviewPipeline.build() as {
  _type: string;
  subAgents: Record<string, unknown>[];
};
assert.equal(built._type, "SequentialAgent");
assert.equal(built.subAgents.length, 3);

// Step 1 — diff parser with output_key.
const step1 = built.subAgents[0] as { name: string; output_key: string };
assert.equal(step1.name, "diff_parser");
assert.equal(step1.output_key, "parsed_diff");

// Step 2 — fan-out of three reviewers.
const fanout = built.subAgents[1] as { _type: string; subAgents: unknown[] };
assert.equal(fanout._type, "ParallelAgent");
assert.equal(fanout.subAgents.length, 3);

// Step 3 — fallback chain (primary + backup).
const fallback = built.subAgents[2] as { _type: string; children: unknown[] };
assert.equal(fallback._type, "Fallback");
assert.equal(fallback.children.length, 2);

// Both aggregator builders carry the structured schema.
assert.equal(aggregator.inspect()._output_schema, ReviewVerdict);
assert.equal(backup.inspect()._output_schema, ReviewVerdict);

export { reviewPipeline };
