/**
 * 16 — Middleware-style callbacks
 *
 * Cross-cutting concerns (logging, latency tracking, retries) attached as
 * before/after callbacks. The `M` namespace exposes ready-made factories,
 * but the same effect can be achieved by writing the callback inline.
 *
 * Note: a first-class `.middleware()` shortcut on `Agent` is on the roadmap.
 * Today you compose middleware-style hooks via `.beforeModel()` /
 * `.afterModel()` directly.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

interface Stats {
  calls: number;
  totalMs: number;
}
const stats: Stats = { calls: 0, totalMs: 0 };

const startTimer = (): void => {
  stats.calls += 1;
  (globalThis as { __startedAt?: number }).__startedAt = Date.now();
};

const endTimer = (): void => {
  const started = (globalThis as { __startedAt?: number }).__startedAt;
  if (started !== undefined) {
    stats.totalMs += Date.now() - started;
  }
};

const agent = new Agent("observed", "gemini-2.5-flash")
  .instruct("Do some work.")
  .beforeModel(startTimer)
  .afterModel(endTimer)
  .build() as Record<string, unknown>;

assert.equal(typeof agent.before_model_callback, "function");
assert.equal(typeof agent.after_model_callback, "function");

// Run the callbacks once to verify the timer wiring works end-to-end.
await (agent.before_model_callback as () => Promise<void> | void)();
await (agent.after_model_callback as () => Promise<void> | void)();
assert.equal(stats.calls, 1);
assert.ok(stats.totalMs >= 0);

export { agent, stats };
