/**
 * 67 — G module: declarative guard composition
 *
 * Mirrors `python/examples/cookbook/67_g_module_guards.py`.
 *
 * `G.*` factories return `GComposite` instances. Compose with `.pipe()`.
 * Guards run as after-model callbacks and either pass, transform the
 * response, or throw `GuardViolation`.
 *
 * Key concepts:
 *   - G.json(), G.length(), G.regex(): structural guards
 *   - G.output(), G.input(): schema validation guards
 *   - G.pii(), G.toxicity(), G.topic(): content safety guards
 *   - G.budget(), G.rateLimit(), G.maxTurns(): policy guards
 *   - G.grounded(), G.hallucination(): grounding guards
 *   - G.when(predicate, guard): conditional guards
 *   - G.guard(): custom guard function
 *   - .pipe() composition for stacking guards
 *   - Guard checks: GuardViolation on failure, transform on redact
 */
import assert from "node:assert/strict";
import { Agent, G, GComposite, GuardViolation } from "../../src/index.js";

// ---------------------------------------------------------------------------
// 1. GComposite composition with .pipe()
// ---------------------------------------------------------------------------

const jsonGuard = G.json();
assert.ok(jsonGuard instanceof GComposite);
assert.equal(jsonGuard.guards.length, 1);
assert.equal(jsonGuard.guards[0].name, "json");

const lengthGuard = G.length({ min: 10, max: 500 });
assert.ok(lengthGuard instanceof GComposite);

// Compose with pipe
const chain = G.json().pipe(G.length({ max: 500 }));
assert.ok(chain instanceof GComposite);
assert.equal(chain.guards.length, 2);

// Multiple guards chained
const multiChain = G.json()
  .pipe(G.length({ max: 500 }))
  .pipe(G.pii({ action: "redact" }));
assert.equal(multiChain.guards.length, 3);
assert.deepEqual(
  multiChain.guards.map((g) => g.name),
  ["json", "length", "pii"],
);

// ---------------------------------------------------------------------------
// 2. G.json() validates JSON output
// ---------------------------------------------------------------------------

// Valid JSON passes
G.json().guards[0].check('{"ok": true}');

// Invalid JSON throws GuardViolation
let jsonThrew = false;
try {
  G.json().guards[0].check("not json");
} catch (e) {
  jsonThrew = e instanceof GuardViolation;
}
assert.ok(jsonThrew, "json guard should throw GuardViolation on invalid JSON");

// ---------------------------------------------------------------------------
// 3. G.length() validates response length
// ---------------------------------------------------------------------------

// Within bounds passes
G.length({ min: 1, max: 100 }).guards[0].check("hello");

// Too long throws
let lengthThrew = false;
try {
  G.length({ max: 5 }).guards[0].check("this is way too long");
} catch (e) {
  lengthThrew = e instanceof GuardViolation;
}
assert.ok(lengthThrew, "length guard should throw GuardViolation when too long");

// Too short throws
let shortThrew = false;
try {
  G.length({ min: 100 }).guards[0].check("short");
} catch (e) {
  shortThrew = e instanceof GuardViolation;
}
assert.ok(shortThrew, "length guard should throw GuardViolation when too short");

// ---------------------------------------------------------------------------
// 4. G.regex() blocks or redacts pattern matches
// ---------------------------------------------------------------------------

// Redact mode: transforms output
const redacted = G.regex(/secret-\d+/, { action: "redact", replacement: "[REDACTED]" });
const result = redacted.guards[0].check("token: secret-12345 here") as unknown as string;
assert.equal(result, "token: [REDACTED] here");

// Block mode: throws GuardViolation
let blocked = false;
try {
  G.regex("forbidden", { action: "block" }).guards[0].check("contains forbidden word");
} catch (e) {
  blocked = e instanceof GuardViolation;
}
assert.ok(blocked, "regex(block) should throw on match");

// ---------------------------------------------------------------------------
// 5. G.output() and G.input() for schema validation
// ---------------------------------------------------------------------------

class ResponseSchema {
  answer!: string;
  confidence!: number;
}

class RequestSchema {
  query!: string;
  context!: string;
}

const outputGuard = G.output(ResponseSchema);
assert.equal(outputGuard.guards[0].name, "output");
assert.equal(outputGuard.guards[0].config?.schema, ResponseSchema);
assert.equal(outputGuard.guards[0].config?.phase, "post_model");

const inputGuard = G.input(RequestSchema);
assert.equal(inputGuard.guards[0].name, "input");
assert.equal(inputGuard.guards[0].config?.schema, RequestSchema);
assert.equal(inputGuard.guards[0].config?.phase, "pre_model");

// ---------------------------------------------------------------------------
// 6. G.pii() for PII detection
// ---------------------------------------------------------------------------

const pii = G.pii({ action: "redact" });
assert.equal(pii.guards[0].name, "pii");
assert.equal(pii.guards[0].config?.action, "redact");

const piiBlock = G.pii({ action: "block", threshold: 0.9 });
assert.equal(piiBlock.guards[0].config?.action, "block");
assert.equal(piiBlock.guards[0].config?.threshold, 0.9);

// Custom replacement
const piiCustom = G.pii({
  action: "redact",
  replacement: "[PATIENT-INFO]",
});
assert.equal(piiCustom.guards[0].config?.replacement, "[PATIENT-INFO]");

// ---------------------------------------------------------------------------
// 7. G.toxicity() for content safety
// ---------------------------------------------------------------------------

const toxicity = G.toxicity({ threshold: 0.8 });
assert.equal(toxicity.guards[0].name, "toxicity");
assert.equal(toxicity.guards[0].config?.threshold, 0.8);

// With custom judge
const customJudge = G.customJudge((text: string) => ({
  pass: !text.toLowerCase().includes("dangerous"),
  reason: "Contains dangerous content",
}));
const toxWithJudge = G.toxicity({ threshold: 0.7, judge: customJudge });
assert.equal(toxWithJudge.guards[0].config?.threshold, 0.7);
assert.ok(toxWithJudge.guards[0].config?.judge);

// ---------------------------------------------------------------------------
// 8. G.topic() for topic blocking
// ---------------------------------------------------------------------------

const deniedTopics = ["politics", "religion", "financial_advice"];
const topic = G.topic({ deny: deniedTopics });
assert.equal(topic.guards[0].name, "topic");
assert.deepEqual(topic.guards[0].config?.deny, deniedTopics);

// ---------------------------------------------------------------------------
// 9. G.budget(), G.rateLimit(), G.maxTurns() policy guards
// ---------------------------------------------------------------------------

const budget = G.budget({ maxTokens: 5000 });
assert.equal(budget.guards[0].name, "budget");
assert.equal(budget.guards[0].config?.maxTokens, 5000);

const rateLimit = G.rateLimit({ rpm: 60 });
assert.equal(rateLimit.guards[0].name, "rate_limit");
assert.equal(rateLimit.guards[0].config?.rpm, 60);

const maxTurns = G.maxTurns(10);
assert.equal(maxTurns.guards[0].name, "max_turns");
assert.equal(maxTurns.guards[0].config?.maxTurns, 10);

// ---------------------------------------------------------------------------
// 10. G.grounded() and G.hallucination() for grounding
// ---------------------------------------------------------------------------

const grounded = G.grounded({ sourcesKey: "documents" });
assert.equal(grounded.guards[0].name, "grounded");
assert.equal(grounded.guards[0].config?.sourcesKey, "documents");

const hallucination = G.hallucination({ threshold: 0.7, sourcesKey: "sources" });
assert.equal(hallucination.guards[0].name, "hallucination");
assert.equal(hallucination.guards[0].config?.threshold, 0.7);
assert.equal(hallucination.guards[0].config?.sourcesKey, "sources");

// ---------------------------------------------------------------------------
// 11. G.when() for conditional guards
// ---------------------------------------------------------------------------

function isProduction(state: Record<string, unknown>): boolean {
  return state.env === "production";
}

const conditionalPii = G.when(isProduction, G.pii({ action: "redact" }));
assert.equal(conditionalPii.guards.length, 1);
assert.ok(conditionalPii.guards[0].name.includes("when"));
assert.ok(conditionalPii.guards[0].config?.condition);

// Conditional with multiple guards
const conditionalMulti = G.when(
  (s) => s.strict_mode === true,
  G.json()
    .pipe(G.length({ max: 500 }))
    .pipe(G.pii({ action: "block" })),
);
assert.equal(conditionalMulti.guards.length, 3);
assert.ok(conditionalMulti.guards.every((g) => g.name.startsWith("when(")));

// ---------------------------------------------------------------------------
// 12. G.guard() for custom guards
// ---------------------------------------------------------------------------

let customCalls = 0;
const customGuard = G.guard(((response: string) => {
  customCalls++;
  if (response.includes("ERROR")) {
    throw new GuardViolation("custom", "post_model", "no errors allowed");
  }
}) as never);

customGuard.guards[0].check("ok response");
assert.equal(customCalls, 1);

let customThrew = false;
try {
  customGuard.guards[0].check("ERROR occurred");
} catch (e) {
  customThrew = e instanceof GuardViolation;
}
assert.ok(customThrew, "custom guard should throw on ERROR");
assert.equal(customCalls, 2);

// ---------------------------------------------------------------------------
// 13. Attach guard composite to an agent
// ---------------------------------------------------------------------------

const classifierAgent = new Agent("classifier", "gemini-2.5-flash")
  .instruct("Classify the email and return JSON.")
  .guard(G.json().pipe(G.length({ max: 200 })))
  .build() as Record<string, unknown>;

assert.equal(classifierAgent._type, "LlmAgent");

// ---------------------------------------------------------------------------
// 14. Full production example: medical agent with comprehensive guards
// ---------------------------------------------------------------------------

class MedicalResponseSchema {
  answer!: string;
  disclaimer!: string;
  sources!: string[];
}

const medicalAgent = new Agent("medical_advisor", "gemini-2.5-flash")
  .instruct(
    "You provide general health information only. " +
      "Always include disclaimers. Never diagnose or prescribe.",
  )
  .guard(
    // Structural validation
    G.output(MedicalResponseSchema)
      .pipe(G.length({ min: 50, max: 2000 }))
      // PII protection
      .pipe(G.pii({ action: "redact", replacement: "[PATIENT-INFO]" }))
      // Content safety
      .pipe(G.toxicity({ threshold: 0.7 }))
      .pipe(G.topic({ deny: ["specific_diagnosis", "prescription_dosage"] }))
      // Grounding
      .pipe(G.grounded({ sourcesKey: "medical_sources" }))
      .pipe(G.hallucination({ threshold: 0.6, sourcesKey: "medical_sources" }))
      // Policy limits
      .pipe(G.budget({ maxTokens: 8000 }))
      .pipe(G.maxTurns(5)),
  );

const medicalBuilt = medicalAgent.build() as Record<string, unknown>;
assert.equal(medicalBuilt._type, "LlmAgent");

// ---------------------------------------------------------------------------
// 15. Guard pipeline: individual agents with their own guards
// ---------------------------------------------------------------------------

const medWriter = new Agent("medical_writer", "gemini-2.5-flash")
  .instruct("Draft response.")
  .guard(G.pii({ action: "redact" }).pipe(G.length({ max: 1000 })));

const medReviewer = new Agent("medical_reviewer", "gemini-2.5-flash")
  .instruct("Review safety.")
  .guard(G.toxicity({ threshold: 0.8 }).pipe(G.budget({ maxTokens: 5000 })));

const medPipeline = medWriter.then(medReviewer).build() as {
  _type: string;
  subAgents: Record<string, unknown>[];
};

assert.equal(medPipeline._type, "SequentialAgent");
assert.equal(medPipeline.subAgents.length, 2);

// ---------------------------------------------------------------------------
// 16. Detector factories
// ---------------------------------------------------------------------------

// Regex-based PII detector
const regexDetector = G.regexDetector([
  /\b\d{3}-\d{2}-\d{4}\b/g,
  /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
]);
const findings = regexDetector.detect("SSN: 123-45-6789, email: test@example.com");
assert.ok(Array.isArray(findings));

// Multi-detector union
const multiDetector = G.multi(
  regexDetector,
  G.custom((text) => {
    const matches: string[] = [];
    if (text.includes("EMP-")) matches.push("EMP_ID");
    return matches;
  }),
);
assert.ok(typeof multiDetector.detect === "function");

// ---------------------------------------------------------------------------
// 17. toArray() flattens guard specs
// ---------------------------------------------------------------------------

const flatGuards = chain.toArray();
assert.equal(flatGuards.length, 2);
assert.equal(flatGuards[0].name, "json");
assert.equal(flatGuards[1].name, "length");

export { chain, multiChain };
