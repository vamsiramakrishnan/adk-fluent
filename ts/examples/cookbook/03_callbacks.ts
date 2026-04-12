/**
 * 03 — Callbacks
 *
 * before_model / after_model callbacks. The fluent builder appends them to
 * the underlying ADK callback lists; calling the builder twice composes the
 * callbacks into a single async-fold that runs both in order.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

const fired: string[] = [];

const beforeModel = (): void => {
  fired.push("before");
};
const afterModel = (): void => {
  fired.push("after");
};

const agent = new Agent("logger", "gemini-2.5-flash")
  .instruct("Log everything.")
  .beforeModel(beforeModel)
  .afterModel(afterModel)
  .build() as Record<string, unknown>;

assert.equal(typeof agent.before_model_callback, "function");
assert.equal(typeof agent.after_model_callback, "function");

// Composing two callbacks of the same kind folds them into one wrapper.
const agent2 = new Agent("multi", "gemini-2.5-flash")
  .instruct("Run two before-model hooks.")
  .beforeModel(() => fired.push("a"))
  .beforeModel(() => fired.push("b"))
  .build() as Record<string, unknown>;

const folded = agent2.before_model_callback as (...args: unknown[]) => Promise<void>;
await folded();
assert.deepEqual(fired.slice(-2), ["a", "b"]);

export { agent, agent2 };
