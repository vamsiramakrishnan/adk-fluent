/**
 * 53 — Planner and code executor wiring
 *
 * Two slots on every Agent for advanced reasoning workflows:
 *   - `.planner(p)`       — attach a planner (e.g. BuiltInPlanner, PlanReActPlanner)
 *   - `.codeExecutor(ce)` — attach a code executor (e.g. UnsafeLocalCodeExecutor)
 *
 * The fluent setters accept either a builder instance (auto-built) or
 * a raw object. The built agent receives the resolved native value.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

// Use raw config objects to keep this cookbook free of any optional
// runtime deps (the planner/executor builder shapes are auto-generated
// and may need extra constructor args we don't want to model here).
const thinkingPlanner = { _type: "BuiltInPlanner", thinking_config: { mode: "deep" } };
const sandboxExecutor = { _type: "UnsafeLocalCodeExecutor", error_retry_attempts: 2 };

const dataAgent = new Agent("data_analyst", "gemini-2.5-pro")
  .instruct(
    "Analyse the user's CSV. Plan your steps before running code, " +
      "then execute Python in the sandbox.",
  )
  .planner(thinkingPlanner)
  .codeExecutor(sandboxExecutor)
  .build() as Record<string, unknown>;

assert.equal(dataAgent.name, "data_analyst");
assert.equal(dataAgent.model, "gemini-2.5-pro");

// Both slots round-trip into the built object under their snake_case names.
assert.deepEqual(dataAgent.planner, thinkingPlanner);
assert.deepEqual(dataAgent.code_executor, sandboxExecutor);

// Agents that omit either slot don't emit the key (defaults are undefined).
const plain = new Agent("plain", "gemini-2.5-flash").instruct("hi").build() as Record<
  string,
  unknown
>;
assert.equal(plain.planner, undefined);
assert.equal(plain.code_executor, undefined);

export { dataAgent };
