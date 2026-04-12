/**
 * 29 — Conditional loops with `.timesUntil()`
 *
 * Mirrors `python/examples/cookbook/30_until_operator.py`.
 *
 * In Python: `(a >> b) * until(pred, max=5)`. In TypeScript we use the
 * method-chained form: `a.then(b).timesUntil(pred, { max: 5 })`. The
 * loop runs the body until the predicate returns true, capped by `max`.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, Loop } from "../../src/index.js";

const documentChecker = new Agent("document_checker", "gemini-2.5-flash")
  .instruct("Review the uploaded identity documents for completeness.")
  .writes("identity_status");

const verifier = new Agent("verification_agent", "gemini-2.5-flash").instruct(
  "Cross-reference document data against external databases.",
);

// `(doc >> verifier) * until(pred, max=5)`
const onboardingLoop = documentChecker
  .then(verifier)
  .timesUntil((s) => s.identity_status === "verified", { max: 5 });

assert.ok(onboardingLoop instanceof Loop);

// Default max for timesUntil is 10 when omitted.
const complianceCheck = new Agent("kyc_screener", "gemini-2.5-flash")
  .instruct("Screen customer against KYC/AML watchlists.")
  .then(
    new Agent("risk_assessor", "gemini-2.5-flash").instruct(
      "Assess customer risk based on screening results.",
    ),
  )
  .timesUntil((s) => Boolean(s.kyc_clear));

assert.ok(complianceCheck instanceof Loop);

// Embedded inside a larger pipeline.
const fullOnboarding = new Agent("intake_agent", "gemini-2.5-flash")
  .instruct("Collect customer information and upload instructions.")
  .then(
    new Agent("document_validator", "gemini-2.5-flash")
      .instruct("Validate documents meet format requirements.")
      .then(
        new Agent("identity_verifier", "gemini-2.5-flash").instruct(
          "Verify identity using biometric and document matching.",
        ),
      )
      .timesUntil((s) => Boolean(s.verification_passed), { max: 3 }),
  )
  .then(
    new Agent("welcome_agent", "gemini-2.5-flash").instruct(
      "Send welcome package and account activation details.",
    ),
  );

assert.ok(fullOnboarding instanceof Pipeline);
const builtFull = fullOnboarding.build() as { subAgents: unknown[] };
assert.equal(builtFull.subAgents.length, 3);

// Fixed-count repetition with .times() — equivalent to Python's `agent * 3`.
const docRetry = new Agent("doc_requester", "gemini-2.5-flash")
  .instruct("Request missing documents.")
  .times(3);
assert.ok(docRetry instanceof Loop);

export { onboardingLoop, fullOnboarding, docRetry };
