/**
 * 61 — `fanOutMerge` higher-order pattern
 *
 * `fanOutMerge` builds a `FanOut` of N parallel branches and stamps a
 * `_merge_key` annotation on the result via `.native()`. The runtime
 * layer uses that key to combine branch outputs into a single state slot.
 */
import assert from "node:assert/strict";
import { Agent, FanOut, fanOutMerge } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const webSearch = new Agent("web_search", MODEL)
  .instruct("Search the open web for {topic}.")
  .writes("web_results");

const newsSearch = new Agent("news_search", MODEL)
  .instruct("Search news outlets for {topic}.")
  .writes("news_results");

const academicSearch = new Agent("academic_search", MODEL)
  .instruct("Search academic papers for {topic}.")
  .writes("academic_results");

const research = fanOutMerge([webSearch, newsSearch, academicSearch], {
  mergeKey: "all_results",
  name: "research_fan_out",
});

assert.ok(research instanceof FanOut);

const built = research.build() as {
  _type: string;
  name: string;
  subAgents: Array<{ name: string }>;
  _merge_key: string;
};

assert.equal(built._type, "ParallelAgent");
assert.equal(built.name, "research_fan_out");
assert.equal(built.subAgents.length, 3);
assert.equal(built.subAgents[0].name, "web_search");
assert.equal(built.subAgents[1].name, "news_search");
assert.equal(built.subAgents[2].name, "academic_search");

// `.native()` injected the merge key annotation.
assert.equal(built._merge_key, "all_results");

// Defaults: omit options to use "merged" / "fan_out_merge".
const defaulted = fanOutMerge([webSearch, newsSearch]);
const defaultedBuilt = defaulted.build() as {
  name: string;
  _merge_key: string;
  subAgents: unknown[];
};
assert.equal(defaultedBuilt.name, "fan_out_merge");
assert.equal(defaultedBuilt._merge_key, "merged");
assert.equal(defaultedBuilt.subAgents.length, 2);

export { research };
