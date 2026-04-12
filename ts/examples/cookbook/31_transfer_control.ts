/**
 * 31 — Transfer control: `.isolate()`, `.stay()`, `.noPeers()`
 *
 * Mirrors `python/examples/cookbook/54_transfer_control.py`.
 *
 * A customer-service hub: a coordinator routes to specialist sub-agents
 * that must complete their task before returning. `.isolate()` is the
 * shorthand for "no transfer to parent or peers" — the most common
 * pattern for specialists.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

// Specialist agents — fully isolated, must finish before returning.
const billing = new Agent("billing_specialist", "gemini-2.5-flash")
  .instruct("You handle billing inquiries: refunds, disputes, subscriptions.")
  .describe("Handles billing, payment, and subscription issues")
  .isolate();

const technical = new Agent("technical_specialist", "gemini-2.5-flash")
  .instruct("You handle technical support: bugs, integrations, configs.")
  .describe("Handles technical support and troubleshooting")
  .isolate();

// General support keeps defaults — may transfer back to coordinator.
const general = new Agent("general_support", "gemini-2.5-flash")
  .instruct("You handle account questions and general inquiries.")
  .describe("Handles general inquiries and account questions");

const coordinator = new Agent("service_coordinator", "gemini-2.5-flash")
  .instruct(
    "You are the front-line coordinator. Route customers to billing, " +
      "technical, or general support.",
  )
  .subAgent(billing)
  .subAgent(technical)
  .subAgent(general)
  .build() as Record<string, unknown> & { sub_agents: Record<string, unknown>[] };

// Coordinator can transfer freely (default → flag absent).
assert.equal(coordinator.disallow_transfer_to_parent, undefined);
assert.equal(coordinator.disallow_transfer_to_peers, undefined);

// Specialists are fully isolated.
const builtBilling = billing.build() as Record<string, unknown>;
assert.equal(builtBilling.disallow_transfer_to_parent, true);
assert.equal(builtBilling.disallow_transfer_to_peers, true);

const builtTechnical = technical.build() as Record<string, unknown>;
assert.equal(builtTechnical.disallow_transfer_to_parent, true);
assert.equal(builtTechnical.disallow_transfer_to_peers, true);

// General support keeps defaults.
const builtGeneral = general.build() as Record<string, unknown>;
assert.equal(builtGeneral.disallow_transfer_to_parent, undefined);
assert.equal(builtGeneral.disallow_transfer_to_peers, undefined);

// Coordinator wires the three specialists.
assert.equal(coordinator.sub_agents.length, 3);
assert.equal(coordinator.sub_agents[0].name, "billing_specialist");
assert.equal(coordinator.sub_agents[1].name, "technical_specialist");
assert.equal(coordinator.sub_agents[2].name, "general_support");

// `.stay()` blocks parent transfers only; `.noPeers()` blocks peers only.
const stayOnly = new Agent("stay_only", "gemini-2.5-flash").instruct("...").stay();
const noPeersOnly = new Agent("no_peers_only", "gemini-2.5-flash").instruct("...").noPeers();
const stayBuilt = stayOnly.build() as Record<string, unknown>;
const peersBuilt = noPeersOnly.build() as Record<string, unknown>;
assert.equal(stayBuilt.disallow_transfer_to_parent, true);
assert.equal(stayBuilt.disallow_transfer_to_peers, undefined);
assert.equal(peersBuilt.disallow_transfer_to_parent, undefined);
assert.equal(peersBuilt.disallow_transfer_to_peers, true);

export { coordinator };
