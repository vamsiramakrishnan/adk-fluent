/**
 * 40 — `mapOver()`: batch process list items
 *
 * Mirrors `python/examples/cookbook/39_map_over.py`.
 *
 * `mapOver(key, agent)` runs `agent` once per item in `state[key]`,
 * collecting per-item results. The Python equivalent is `map_over()`.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, mapOver } from "../../src/index.js";

const sentimentAnalyzer = new Agent("sentiment_analyzer", "gemini-2.5-flash").instruct(
  "Analyze the sentiment of the customer feedback in _item.",
);

// mapOver() returns a Primitive that the runtime walker iterates.
const mapper = mapOver("feedback_entries", sentimentAnalyzer);
const built = mapper.build() as Record<string, unknown>;
assert.equal(built._kind, "map_over");
assert.equal(built.name, "map_over_feedback_entries");
assert.equal(built._key, "feedback_entries");

// The wrapped agent is preserved.
const agents = built._agents as Record<string, unknown>[];
assert.equal(agents.length, 1);
assert.equal(agents[0].name, "sentiment_analyzer");

// Custom name for clarity in dashboards.
const ticketMapper = mapOver(
  "support_tickets",
  new Agent("priority_classifier", "gemini-2.5-flash").instruct(
    "Classify the urgency of the support ticket in _item.",
  ),
  "ticket_priorities",
);
const ticketBuilt = ticketMapper.build() as Record<string, unknown>;
assert.equal(ticketBuilt.name, "ticket_priorities");
assert.equal(ticketBuilt._key, "support_tickets");

// End-to-end pipeline: collect → map → summarize.
const pipeline = new Pipeline("feedback_processing")
  .step(
    new Agent("feedback_collector", "gemini-2.5-flash")
      .instruct("Collect customer feedback from all channels.")
      .writes("feedback_entries"),
  )
  .step(mapper)
  .step(
    new Agent("summary_writer", "gemini-2.5-flash").instruct(
      "Write an executive summary of the per-feedback sentiment results.",
    ),
  )
  .build() as { subAgents: Record<string, unknown>[] };

assert.equal(pipeline.subAgents.length, 3);
assert.equal(pipeline.subAgents[1]._kind, "map_over");

export { pipeline };
