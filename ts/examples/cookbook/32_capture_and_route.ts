/**
 * 32 — Capture & Route: IT helpdesk triage
 *
 * Mirrors `python/examples/cookbook/50_capture_and_route.py`.
 *
 * Pipeline topology:
 *   S.capture("ticket")
 *     >> triage [writes: priority]
 *     >> Route("priority")
 *         ├─ "p1" -> incident_commander
 *         ├─ "p2" -> senior_support
 *         └─ otherwise -> support_bot
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, Route, S } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const triage = new Agent("triage", MODEL)
  .instruct(
    "You are an IT helpdesk triage agent.\n" +
      "Read the ticket and classify it.\n" +
      "Ticket: {ticket}\n" +
      "Output the priority level: p1, p2, or p3.",
  )
  .writes("priority");

const router = new Route("priority")
  .eq(
    "p1",
    new Agent("incident_commander", MODEL).instruct(
      "CRITICAL INCIDENT.\nTicket: {ticket}\nPage on-call.",
    ),
  )
  .eq(
    "p2",
    new Agent("senior_support", MODEL).instruct(
      "Priority ticket.\nTicket: {ticket}\nResolve within 4 hours.",
    ),
  )
  .otherwise(
    new Agent("support_bot", MODEL).instruct(
      "Routine support.\nTicket: {ticket}\nProvide self-service guidance.",
    ),
  );

// S.capture creates a state-injection step that the runtime resolves
// into a CaptureAgent. The Pipeline.step() method accepts builders,
// transforms, or plain functions.
const capture = S.capture("ticket");

const helpdesk = new Pipeline("helpdesk_triage")
  .step({ name: "capture_ticket", _kind: "s_capture", _transform: capture })
  .step(triage)
  .step(router)
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

assert.equal(helpdesk._type, "SequentialAgent");
assert.equal(helpdesk.subAgents.length, 3);
assert.equal((helpdesk.subAgents[0] as Record<string, unknown>).name, "capture_ticket");
assert.equal((helpdesk.subAgents[1] as Record<string, unknown>).name, "triage");

// The Route is the last step and exposes its decision tree shape.
const built = router.build() as Record<string, unknown> & {
  branches: unknown[];
};
assert.equal(built._type, "Route");
assert.equal(built.key, "priority");
assert.equal(built.branches.length, 2);
assert.ok(built.default);

export { helpdesk };
