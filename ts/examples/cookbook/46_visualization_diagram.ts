/**
 * 46 — Architecture diagrams from live code
 *
 * Mirrors `python/examples/cookbook/48_visualization.py`.
 *
 * Cookbook 26 showed `agent.visualize()` for ASCII output. This cookbook
 * focuses on mermaid + markdown rendering for documentation pipelines:
 * the diagram lives next to the code and never goes stale.
 */
import assert from "node:assert/strict";
import { Agent, FanOut, Pipeline, visualize } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// Stage 1 — alert triage
const triage = new Agent("alert_ingestor", MODEL)
  .instruct("Ingest alert from PagerDuty/OpsGenie and extract severity, service, description.")
  .writes("alert_data");

// Stage 2 — parallel diagnosis
const diagnosis = new FanOut("diagnosis")
  .branch(
    new Agent("log_analyzer", MODEL).instruct(
      "Search application logs for errors correlated with the alert timeframe.",
    ),
  )
  .branch(
    new Agent("metrics_checker", MODEL).instruct(
      "Check Prometheus/Grafana metrics for anomalies in the affected service.",
    ),
  )
  .branch(
    new Agent("trace_analyzer", MODEL).instruct(
      "Analyze distributed traces to identify the failing component.",
    ),
  );

// Stage 3 — resolution
const resolution = new Agent("incident_responder", MODEL).instruct(
  "Synthesize findings and recommend remediation. Draft incident report.",
);

const incidentPipeline = new Pipeline("incident_response")
  .step(triage)
  .step(diagnosis)
  .step(resolution);

// 1. ASCII format — terminal-friendly tree.
const ascii = incidentPipeline.visualize({ format: "ascii" });
assert.match(ascii, /alert_ingestor/);
assert.match(ascii, /log_analyzer/);
assert.match(ascii, /incident_responder/);

// 2. Mermaid — drop into a Markdown doc and GitHub renders it natively.
const mermaid = incidentPipeline.visualize({ format: "mermaid" });
assert.match(mermaid, /flowchart|graph/);
for (const name of [
  "alert_ingestor",
  "log_analyzer",
  "metrics_checker",
  "trace_analyzer",
  "incident_responder",
]) {
  assert.ok(mermaid.includes(name), `mermaid output missing ${name}`);
}
assert.match(mermaid, /-->/);

// 3. Markdown — full anatomy view.
const md = incidentPipeline.visualize({ format: "markdown" });
assert.match(md, /alert_ingestor/);

// 4. The free-function `visualize()` accepts a built config too.
const built = incidentPipeline.build();
const ascii2 = visualize(built, { format: "ascii" });
assert.equal(ascii2, ascii);

// Built shape has the expected three top-level stages.
const builtShape = built as { subAgents: Record<string, unknown>[] };
assert.equal(builtShape.subAgents.length, 3);
assert.equal((builtShape.subAgents[1] as { _type: string })._type, "ParallelAgent");

export { incidentPipeline };
