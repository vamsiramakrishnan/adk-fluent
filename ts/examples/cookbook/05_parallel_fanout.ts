/**
 * 05 — Parallel FanOut
 *
 * Multi-source research: web, papers, and news searched in parallel.
 *
 * Demonstrates the `FanOut` builder which wraps `ParallelAgent`. Each branch
 * runs concurrently. The same workflow can also be expressed via the
 * `.parallel()` method on any agent (Python's `|` operator equivalent).
 */
import assert from "node:assert/strict";
import { Agent, FanOut } from "../../src/index.js";

const research = new FanOut("research")
  .branch(new Agent("web", "gemini-2.5-flash").instruct("Search the web.").writes("web_results"))
  .branch(new Agent("papers", "gemini-2.5-flash").instruct("Search arXiv.").writes("paper_results"))
  .branch(new Agent("news", "gemini-2.5-flash").instruct("Search news.").writes("news_results"))
  .build() as Record<string, unknown>;

assert.equal(research._type, "ParallelAgent");
assert.equal((research.subAgents as unknown[]).length, 3);

// Equivalent expression using `.parallel()` (the TS analog of Python's `|`).
const research2 = new Agent("web", "gemini-2.5-flash")
  .instruct("Search the web.")
  .parallel(new Agent("papers", "gemini-2.5-flash").instruct("Search arXiv."))
  .parallel(new Agent("news", "gemini-2.5-flash").instruct("Search news."))
  .build() as Record<string, unknown>;

assert.equal(research2._type, "ParallelAgent");
assert.equal((research2.subAgents as unknown[]).length, 3);

export { research, research2 };
