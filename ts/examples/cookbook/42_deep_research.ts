/**
 * 42 — Deep Research: end-to-end research pipeline
 *
 * Mirrors `python/examples/cookbook/55_deep_research.py`.
 *
 * Pipeline topology:
 *   query_analyzer
 *     >> ( web | academic | news )         (parallel search)
 *     >> synthesizer
 *     >> ( reviewer >> revisor ).timesUntil(score >= 0.85, max=3)
 *     >> report_writer.outputAs(ResearchReport)
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, FanOut, Loop, C } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// Plain schema marker — the runtime adapter forwards it to ADK.
const ResearchReport = {
  type: "object",
  fields: ["title", "executive_summary", "key_findings", "confidence_score"],
};

// Stage 1: Decompose the query.
const queryAnalyzer = new Agent("query_analyzer", MODEL)
  .instruct(
    "Analyze the research query. Decompose it into 3-5 sub-questions and " +
      "identify which sources are most relevant.",
  )
  .writes("research_plan");

// Stage 2: Parallel search across three sources.
const parallelSearch = new FanOut("parallel_search")
  .branch(
    new Agent("web_searcher", MODEL)
      .instruct("Search the web. Summarize key findings.")
      .context(C.none().add(C.fromState("research_plan")))
      .writes("web_results"),
  )
  .branch(
    new Agent("academic_searcher", MODEL)
      .instruct("Search academic databases. Extract methodology and conclusions.")
      .context(C.none().add(C.fromState("research_plan")))
      .writes("academic_results"),
  )
  .branch(
    new Agent("news_searcher", MODEL)
      .instruct("Search recent news for current developments.")
      .context(C.none().add(C.fromState("research_plan")))
      .writes("news_results"),
  );

// Stage 3: Synthesize across sources.
const synthesizer = new Agent("synthesizer", MODEL)
  .instruct("Synthesize findings. Identify consensus, contradictions, gaps.")
  .context(C.none().add(C.fromState("web_results", "academic_results", "news_results")))
  .writes("synthesis");

// Stage 4: Quality review loop. Run reviewer + revisor up to 3 times,
// stopping early when the quality score is high enough.
const qualityLoop = new Agent("quality_reviewer", MODEL)
  .instruct(
    "Review the synthesis for accuracy, completeness, and bias. " +
      "Score quality from 0 to 1. If below 0.85, request improvements.",
  )
  .context(C.none().add(C.fromState("synthesis")))
  .writes("quality_score")
  .then(
    new Agent("revision_agent", MODEL)
      .instruct("Revise the synthesis based on reviewer feedback.")
      .context(C.none().add(C.fromState("synthesis", "quality_score")))
      .writes("synthesis"),
  )
  .timesUntil((s) => Number(s.quality_score ?? 0) >= 0.85, { max: 3 });

// Stage 5: Final structured report.
const reportWriter = new Agent("report_writer", MODEL)
  .instruct("Write the final research report with summary, findings, and confidence.")
  .context(C.none().add(C.fromState("synthesis")))
  .outputAs(ResearchReport);

// Compose into the full pipeline.
const deepResearch = new Pipeline("deep_research")
  .step(queryAnalyzer)
  .step(parallelSearch)
  .step(synthesizer)
  .step(qualityLoop)
  .step(reportWriter)
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

assert.equal(deepResearch._type, "SequentialAgent");
assert.equal(deepResearch.subAgents.length, 5);
assert.equal((deepResearch.subAgents[0] as { name: string }).name, "query_analyzer");

// Stage 2 is a fan-out with three branches.
const fanout = deepResearch.subAgents[1] as { _type: string; subAgents: unknown[] };
assert.equal(fanout._type, "ParallelAgent");
assert.equal(fanout.subAgents.length, 3);

// Stage 4 is the quality loop (Loop).
const loop = deepResearch.subAgents[3] as { _type: string };
assert.equal(loop._type, "LoopAgent");
assert.ok(qualityLoop instanceof Loop);

// Stage 5 carries the schema (private key — verify on the builder).
assert.equal(reportWriter.inspect()._output_schema, ResearchReport);

export { deepResearch };
