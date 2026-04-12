/**
 * 39 — `race()`: first-to-complete wins
 *
 * Mirrors `python/examples/cookbook/42_race.py`.
 *
 * `race(...agents)` runs all agents concurrently and returns the result
 * of the first one to finish. The other branches are cancelled.
 *
 * Real-world use case: search across multiple providers (Westlaw, Lexis,
 * Google Scholar) and return whichever responds first.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, race } from "../../src/index.js";

const westlaw = new Agent("westlaw_search", "gemini-2.5-flash").instruct(
  "Search Westlaw for the requested case law.",
);
const lexis = new Agent("lexis_search", "gemini-2.5-flash").instruct(
  "Search LexisNexis for the requested case law.",
);
const scholar = new Agent("scholar_search", "gemini-2.5-flash").instruct(
  "Search Google Scholar for the requested case law.",
);

const fastest = race(westlaw, lexis, scholar);
const built = fastest.build() as Record<string, unknown>;
assert.equal(built._kind, "race");
assert.equal(built.name, "race");

// All branches are stored on the primitive for the runtime to launch.
const branches = built._agents as Record<string, unknown>[];
assert.equal(branches.length, 3);
assert.equal(branches[0].name, "westlaw_search");
assert.equal(branches[1].name, "lexis_search");
assert.equal(branches[2].name, "scholar_search");

// Slot into a research pipeline.
const research = new Pipeline("legal_research")
  .step(
    new Agent("query_classifier", "gemini-2.5-flash")
      .instruct("Classify the legal query into federal vs. state vs. international.")
      .writes("query_type"),
  )
  .step(fastest)
  .step(
    new Agent("citation_formatter", "gemini-2.5-flash").instruct(
      "Format the winning search result into a Bluebook citation.",
    ),
  )
  .build() as { subAgents: Record<string, unknown>[] };

assert.equal(research.subAgents.length, 3);
assert.equal(research.subAgents[1]._kind, "race");

export { fastest, research };
