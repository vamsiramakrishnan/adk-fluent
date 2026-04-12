/**
 * 36 — `tap()`: pure observation primitive
 *
 * Mirrors `python/examples/cookbook/35_tap_observation.py`.
 *
 * `tap()` reads state and runs a side-effect (logging, metrics) without
 * mutating the state. Perfect for inserting observability between LLM
 * steps without spending tokens.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, tap } from "../../src/index.js";

// Anonymous lambda — name is auto-generated.
const anonTap = tap((s) => void s);
const anonBuilt = anonTap.build() as Record<string, unknown>;
assert.equal(anonBuilt._kind, "tap");
assert.match(String(anonBuilt.name), /^tap/);

// Named function keeps a meaningful name for traceability.
function logPredictionMetrics(state: Record<string, unknown>): void {
  void state;
}
const namedTap = tap(logPredictionMetrics, "logPredictionMetrics");
const namedBuilt = namedTap.build() as Record<string, unknown>;
assert.equal(namedBuilt.name, "logPredictionMetrics");

// `tap()` slots into a pipeline like any other step.
const pipeline = new Pipeline("ml_inference")
  .step(
    new Agent("feature_engineer", "gemini-2.5-flash").instruct(
      "Extract and normalize features from raw input.",
    ),
  )
  .step(tap((s) => void s, "log_features"))
  .step(
    new Agent("inference_engine", "gemini-2.5-flash").instruct(
      "Run inference on the prepared features and return predictions.",
    ),
  )
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

assert.equal(pipeline._type, "SequentialAgent");
assert.equal(pipeline.subAgents.length, 3);
assert.equal(pipeline.subAgents[1]._kind, "tap");
assert.equal(pipeline.subAgents[1].name, "log_features");

// Tap functions are stored on the primitive for the runtime to call.
assert.equal(typeof pipeline.subAgents[1]._fn, "function");

export { pipeline };
