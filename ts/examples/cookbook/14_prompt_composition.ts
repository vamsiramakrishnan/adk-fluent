/**
 * 14 — Prompt Composition (P namespace)
 *
 * Build instructions from named sections instead of one giant string.
 * Sections always render in canonical order (role → context → task →
 * constraint → format → example) regardless of how they were added.
 */
import assert from "node:assert/strict";
import { Agent, P } from "../../src/index.js";

const prompt = P.role("You are a senior data analyst.")
  .add(P.task("Analyze the {topic} dataset and report key trends."))
  .add(P.constraint("Use bullet points.", "Limit to 5 findings.", "Cite the data."))
  .add(P.format("Markdown with H2 headings."));

const agent = new Agent("analyst", "gemini-2.5-flash").instruct(prompt).build() as Record<
  string,
  unknown
>;

assert.equal(agent._type, "LlmAgent");
const rendered = String((agent.instruction as { render: (s?: object) => string }).render({}));
assert.match(rendered, /senior data analyst/);
assert.match(rendered, /Analyze the/);
assert.match(rendered, /bullet points/);
assert.match(rendered, /Markdown/);

// Templates carry `{key}` placeholders that the runtime adapter substitutes
// from agent state. The cookbook only checks the literal template survives
// the round-trip — actual substitution happens inside `@google/adk`.
const templated = P.template("Hello {user}, today is {day}.");
assert.match(templated.render(), /\{user\}/);

export { agent, templated };
