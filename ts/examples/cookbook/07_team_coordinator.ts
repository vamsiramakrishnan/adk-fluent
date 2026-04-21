/**
 * 07 — Team Coordinator
 *
 * A coordinator with three specialist sub-agents. The LLM picks which
 * specialist to transfer to via ADK's transfer_to_agent tool.
 *
 * `.transferTo()` registers each specialist; `.isolate()` prevents the
 * specialist from re-transferring (the most predictable default).
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

const billing = new Agent("billing", "gemini-2.5-flash")
  .describe("Handles invoices, refunds, and payment disputes.")
  .instruct("You handle billing questions only.")
  .isolate();

const technical = new Agent("technical", "gemini-2.5-flash")
  .describe("Handles bugs, integrations, and API errors.")
  .instruct("You handle technical issues only.")
  .isolate();

const general = new Agent("general", "gemini-2.5-flash")
  .describe("Handles everything else.")
  .instruct("You handle general inquiries only.")
  .isolate();

const coordinator = new Agent("triage", "gemini-2.5-flash")
  .instruct("Read the incoming message and transfer to the right specialist.")
  .transferTo(billing)
  .transferTo(technical)
  .transferTo(general)
  .build() as Record<string, unknown>;

assert.equal(coordinator._type, "LlmAgent");
const subs = coordinator.sub_agents as Record<string, unknown>[];
assert.equal(subs.length, 3);
assert.deepEqual(
  subs.map((s) => s.name),
  ["billing", "technical", "general"],
);
// Specialists are isolated → cannot transfer back to parent or to peers.
for (const sub of subs) {
  assert.equal(sub.disallow_transfer_to_parent, true);
  assert.equal(sub.disallow_transfer_to_peers, true);
}

export { coordinator };
