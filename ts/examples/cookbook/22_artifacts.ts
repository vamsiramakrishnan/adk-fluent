/**
 * 22 — Artifacts (A namespace)
 *
 * Bridge state and the artifact store. `A.publish` writes a state field to
 * a named artifact; `A.snapshot` reads an artifact back into state. Useful
 * for handing large blobs (PDFs, datasets, generated images) between
 * pipeline stages without bloating the in-memory state.
 */
import assert from "node:assert/strict";
import { Agent, A } from "../../src/index.js";

const writer = new Agent("writer", "gemini-2.5-flash")
  .instruct("Generate a report.")
  .writes("report");

// After this agent, copy state.report → artifact "report.md".
const withArtifact = writer
  .artifacts(A.publish("report.md", { fromKey: "report" }))
  .build() as Record<string, unknown>;

assert.equal(withArtifact._type, "LlmAgent");
const arts = withArtifact.artifacts as unknown[];
assert.equal(arts.length, 1);

// Snapshot the other direction: read an existing artifact into state.
const reader = new Agent("reader", "gemini-2.5-flash")
  .instruct("Process the previously-saved report from state.")
  .artifacts(A.snapshot("report.md", { intoKey: "report" }))
  .build() as Record<string, unknown>;

assert.equal((reader.artifacts as unknown[]).length, 1);

export { withArtifact, reader };
