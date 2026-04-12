/**
 * 43 — Code review agent
 *
 * Mirrors `python/examples/cookbook/57_code_review_agent.py`.
 *
 * Topology:
 *   diff_parser
 *     >> (style | security | logic)        (parallel review)
 *     >> tap(log)
 *     >> aggregator.outputAs(ReviewResult)
 *     >> comment_writer
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, FanOut, tap } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const ReviewResult = {
  type: "object",
  fields: ["approved", "findings_count", "critical_count", "summary"],
};

const diffParser = new Agent("diff_parser", MODEL)
  .instruct("Parse the git diff into reviewable chunks. Identify language and framework.")
  .writes("parsed_changes");

const styleReview = new Agent("style_checker", MODEL)
  .instruct("Review code style and conventions: naming, complexity, missing docs.")
  .writes("style_findings");

const securityReview = new Agent("security_scanner", MODEL)
  .instruct("Scan for security vulnerabilities: injection, secrets, validation.")
  .writes("security_findings");

const logicReview = new Agent("logic_reviewer", MODEL)
  .instruct("Review business logic correctness: edge cases, error handling.")
  .writes("logic_findings");

const fanout = new FanOut("parallel_review")
  .branch(styleReview)
  .branch(securityReview)
  .branch(logicReview);

const reviewLog: string[] = [];
const logTap = tap(() => reviewLog.push("reviews_complete"), "log_review_complete");

const aggregator = new Agent("finding_aggregator", MODEL)
  .instruct("Aggregate findings, count critical issues, decide approval.")
  .outputAs(ReviewResult);

const commentWriter = new Agent("comment_writer", MODEL).instruct(
  "Write a constructive code review comment grouped by file.",
);

const codeReview = new Pipeline("code_review")
  .step(diffParser)
  .step(fanout)
  .step(logTap)
  .step(aggregator)
  .step(commentWriter)
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

assert.equal(codeReview._type, "SequentialAgent");
assert.equal(codeReview.subAgents.length, 5);
assert.equal((codeReview.subAgents[0] as { name: string }).name, "diff_parser");

// Stage 2 fan-out has three parallel branches.
const fanoutBuilt = codeReview.subAgents[1] as { _type: string; subAgents: unknown[] };
assert.equal(fanoutBuilt._type, "ParallelAgent");
assert.equal(fanoutBuilt.subAgents.length, 3);

// Stage 3 is the tap primitive.
assert.equal(codeReview.subAgents[2]._kind, "tap");
assert.equal(codeReview.subAgents[2].name, "log_review_complete");

// Stage 4 carries the structured schema.
assert.equal(aggregator.inspect()._output_schema, ReviewResult);

export { codeReview };
