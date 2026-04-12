/**
 * 37 — `expect()`: state contract assertions
 *
 * Mirrors `python/examples/cookbook/36_expect_assertions.py`.
 *
 * `expect()` is a zero-LLM contract check that throws when its predicate
 * returns false. Used as a quality gate between pipeline stages.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, expect } from "../../src/index.js";

// `expect()` returns a Primitive with a stored predicate + message.
const e = expect((s) => "metrics" in s, "Metrics must be computed");
const built = e.build() as Record<string, unknown>;
assert.equal(built._kind, "expect");
assert.equal(built._msg, "Metrics must be computed");
assert.equal(typeof built._pred, "function");

// Default message when none specified.
const eDefault = expect((s) => Boolean(s));
const defaultBuilt = eDefault.build() as Record<string, unknown>;
assert.equal(defaultBuilt._msg, "Assertion failed");

// Smoke-test the predicate.
const passed = (built._pred as (s: Record<string, unknown>) => boolean)({ metrics: 42 });
assert.equal(passed, true);
const failed = (built._pred as (s: Record<string, unknown>) => boolean)({});
assert.equal(failed, false);

// Slot multiple expects between agents to gate each pipeline stage.
const validatedPipeline = new Pipeline("data_quality_pipeline")
  .step(
    new Agent("data_ingester", "gemini-2.5-flash")
      .instruct("Ingest raw event data and emit a list of events.")
      .writes("events"),
  )
  .step(expect((s) => "events" in s, "Ingestion must produce events data"))
  .step(
    new Agent("aggregator", "gemini-2.5-flash").instruct(
      "Aggregate events into daily/weekly/monthly cohort metrics.",
    ),
  )
  .step(
    expect(
      (s) => Array.isArray(s.events) && (s.events as unknown[]).length > 0,
      "Events array must not be empty after aggregation",
    ),
  )
  .step(
    new Agent("report_builder", "gemini-2.5-flash").instruct(
      "Build the final analytics report with trend analysis.",
    ),
  )
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

assert.equal(validatedPipeline._type, "SequentialAgent");
assert.equal(validatedPipeline.subAgents.length, 5);
assert.equal(validatedPipeline.subAgents[1]._kind, "expect");
assert.equal(validatedPipeline.subAgents[3]._kind, "expect");

export { validatedPipeline };
