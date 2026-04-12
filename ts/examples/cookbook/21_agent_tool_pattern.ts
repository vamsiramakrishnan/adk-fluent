/**
 * 21 — Agent-as-Tool
 *
 * Wrap an entire agent as a callable tool exposed to a parent LLM. The
 * parent stays in control and can decide when (and how often) to invoke
 * the specialist. Compare with `.subAgent()`, which fully transfers control.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

const translator = new Agent("translator", "gemini-2.5-flash")
  .describe("Translates English text to French.")
  .instruct("Translate the input to French. Reply with only the translation.");

const writer = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write a short bilingual greeting. Use the translator tool to produce the French line.")
  .agentTool(translator)
  .build() as Record<string, unknown>;

assert.equal(writer._type, "LlmAgent");
const tools = writer.tools as unknown[];
assert.equal(tools.length, 1);

export { writer };
