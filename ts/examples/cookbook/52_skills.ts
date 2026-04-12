/**
 * 52 — `.skill()` metadata for A2A AgentCards
 *
 * Skills are declarative metadata about what an agent can do. They are
 * consumed by `A2AServer` when it generates the agent's AgentCard for
 * remote discovery. Calling `.skill()` repeatedly accumulates entries
 * in the agent's skill list.
 *
 * Skills do NOT affect local execution — they are pure metadata.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

const research = new Agent("research_agent", "gemini-2.5-pro")
  .describe("Multi-source research with citations.")
  .instruct("Conduct deep research and cite all sources.")
  .skill("deep_research", "Deep Research", "Multi-source research with academic citations.", [
    "research",
    "citations",
    "academic",
  ])
  .skill("fact_check", "Fact Check", "Verify claims against authoritative sources.", [
    "verification",
    "fact-checking",
  ])
  .skill("summarize", "Summarize Sources", "Produce a TL;DR digest of multiple sources.", [
    "summarization",
  ]);

const built = research.build() as Record<string, unknown> & {
  skills: string[];
};

assert.equal(built.name, "research_agent");
// Skills are appended in order — the underlying list stores skill_id strings.
assert.deepEqual(built.skills, ["deep_research", "fact_check", "summarize"]);

// An agent with no skills declared simply omits the field.
const plain = new Agent("plain", "gemini-2.5-flash").instruct("Hi.").build() as Record<
  string,
  unknown
>;
assert.equal(plain.skills, undefined);

export { research, built };
