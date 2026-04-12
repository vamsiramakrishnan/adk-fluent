/**
 * 01 — Simple Agent
 *
 * Email Classifier — minimal LLM agent.
 *
 * Mirrors python/examples/cookbook/01_simple_agent.py: a single agent with
 * name, model, instruction, and description. Demonstrates that the fluent
 * builder produces the same shape an `@google/adk` `LlmAgent` constructor
 * would (we assert against the tagged config object that `.build()` emits).
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

const agent = new Agent("email_classifier", "gemini-2.5-flash")
  .instruct(
    "You are an email classifier for a SaaS company. " +
      "Read the incoming email and classify it as one of: " +
      "billing, technical, or general.",
  )
  .describe("Classifies customer emails by intent")
  .build() as Record<string, unknown>;

assert.equal(agent._type, "LlmAgent");
assert.equal(agent.name, "email_classifier");
assert.equal(agent.model, "gemini-2.5-flash");
assert.equal(agent.description, "Classifies customer emails by intent");
assert.match(String(agent.instruction), /classify/);

export { agent };
