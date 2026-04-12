/**
 * 45 — Customer support triage
 *
 * Mirrors `python/examples/cookbook/56_customer_support_triage.py`.
 *
 * Topology:
 *   capture(customer_message)
 *     >> classifier [C.none, writes: intent]
 *     >> Route("intent")
 *         ├─ "billing"   -> billing_handler
 *         ├─ "technical" -> tech_handler
 *         ├─ "account"   -> account_handler
 *         └─ otherwise   -> general_handler
 *     >> satisfaction_monitor [writes: resolved]
 *     >> gate(resolved == "no") -> escalation
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, Route, C, S, gate } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

const classifier = new Agent("intent_classifier", MODEL)
  .instruct(
    "Classify the customer message as 'billing', 'technical', 'account', " +
      "or 'general'. Customer said: {customer_message}",
  )
  .context(C.none())
  .writes("intent");

const billingHandler = new Agent("billing_specialist", MODEL)
  .instruct("You are a billing specialist. Help with: {customer_message}")
  .context(C.none().add(C.fromState("customer_message")))
  .writes("agent_response");

const techHandler = new Agent("tech_support", MODEL)
  .instruct("You are a tech support engineer. Issue: {customer_message}")
  .context(C.none().add(C.fromState("customer_message")))
  .writes("agent_response");

const accountHandler = new Agent("account_manager", MODEL)
  .instruct("You are an account manager. Request: {customer_message}")
  .context(C.none().add(C.fromState("customer_message")))
  .writes("agent_response");

const generalHandler = new Agent("general_support", MODEL)
  .instruct("Help with general inquiries.")
  .context(C.userOnly())
  .writes("agent_response");

const router = new Route("intent")
  .eq("billing", billingHandler)
  .eq("technical", techHandler)
  .eq("account", accountHandler)
  .otherwise(generalHandler);

const satisfaction = new Agent("satisfaction_monitor", MODEL)
  .instruct("Evaluate if the customer's issue was resolved. Set resolved to 'yes' or 'no'.")
  .writes("resolved");

const escalation = new Agent("escalation_handler", MODEL).instruct(
  "Customer issue unresolved. Escalate to a human supervisor with full context.",
);
const escalationGate = gate((s) => s.resolved === "no", escalation, "escalation_gate");

const captureMessage = S.capture("customer_message");

const supportSystem = new Pipeline("support_triage")
  .step({ name: "capture_customer_message", _kind: "s_capture", _transform: captureMessage })
  .step(classifier)
  .step(router)
  .step(satisfaction)
  .step(escalationGate)
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

assert.equal(supportSystem._type, "SequentialAgent");
assert.equal(supportSystem.subAgents.length, 5);
assert.equal((supportSystem.subAgents[1] as { name: string }).name, "intent_classifier");

// Route shape — built when traversed.
const routerBuilt = router.build() as Record<string, unknown> & { branches: unknown[] };
assert.equal(routerBuilt._type, "Route");
assert.equal(routerBuilt.key, "intent");
assert.equal(routerBuilt.branches.length, 3);
assert.ok(routerBuilt.default);

// Escalation gate primitive.
assert.equal(supportSystem.subAgents[4]._kind, "gate");

export { supportSystem };
