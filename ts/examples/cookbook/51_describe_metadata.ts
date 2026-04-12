/**
 * 51 — `.describe()` metadata for transfer routing
 *
 * The `description` field is metadata — it is NOT part of the LLM
 * instruction. Coordinator LLMs use it during transfer routing to
 * decide which sub-agent to hand off to. Always set `.describe()` on
 * sub-agents in a multi-agent system.
 *
 * This cookbook builds a research coordinator with three specialists,
 * each with a clear description. The built object preserves the
 * descriptions on every sub-agent so the runtime transfer tool sees
 * them.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const webSearcher = new Agent("web_searcher", MODEL)
  .describe("Searches the public web for recent news, blogs, and forum posts.")
  .instruct("Search the web for: {query}")
  .isolate();

const academicSearcher = new Agent("academic_searcher", MODEL)
  .describe("Searches arXiv, Google Scholar, and PubMed for peer-reviewed research.")
  .instruct("Find academic papers on: {query}")
  .isolate();

const internalSearcher = new Agent("internal_searcher", MODEL)
  .describe("Searches the company's internal Confluence and Notion workspaces.")
  .instruct("Search internal docs for: {query}")
  .isolate();

const coordinator = new Agent("research_coordinator", "gemini-2.5-pro")
  .describe("Routes research questions to the appropriate specialist.")
  .instruct(
    "You coordinate research. Pick the best specialist based on the question. " +
      "Web for current events, academic for science, internal for company-specific.",
  )
  .subAgent(webSearcher)
  .subAgent(academicSearcher)
  .subAgent(internalSearcher)
  .build() as Record<string, unknown> & {
  description: string;
  sub_agents: Record<string, unknown>[];
};

assert.equal(coordinator.name, "research_coordinator");
assert.equal(coordinator.description, "Routes research questions to the appropriate specialist.");
assert.equal(coordinator.sub_agents.length, 3);

// Each specialist's description survives the build.
const [web, academic, internal] = coordinator.sub_agents;
assert.equal(web.name, "web_searcher");
assert.ok((web.description as string).includes("public web"));

assert.equal(academic.name, "academic_searcher");
assert.ok((academic.description as string).includes("arXiv"));

assert.equal(internal.name, "internal_searcher");
assert.ok((internal.description as string).includes("Confluence"));

// `.isolate()` prevents specialists from transferring back to the
// coordinator or to each other. The built object carries both flags.
assert.equal(web.disallow_transfer_to_parent, true);
assert.equal(web.disallow_transfer_to_peers, true);

// And critically: `description` is NOT the same as `instruction`.
assert.notEqual(coordinator.description, coordinator.instruction);

export { coordinator };
