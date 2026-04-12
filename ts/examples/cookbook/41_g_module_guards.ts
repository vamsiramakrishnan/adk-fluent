/**
 * 41 — G module: output validation guards
 *
 * Mirrors `python/examples/cookbook/67_g_module_guards.py`.
 *
 * `G.*` factories return `GComposite` instances. Compose with `.pipe()`.
 * Guards run as after-model callbacks and either pass, transform the
 * response, or throw `GuardViolation`.
 */
import assert from "node:assert/strict";
import { Agent, G, GComposite, GuardViolation } from "../../src/index.js";

// 1. Built-in guards.
const lengthGuard = G.length({ max: 500 });
assert.ok(lengthGuard instanceof GComposite);
assert.equal(lengthGuard.guards.length, 1);
assert.equal(lengthGuard.guards[0].name, "length");

const jsonGuard = G.json();
assert.equal(jsonGuard.guards[0].name, "json");

// 2. Pipe composes guards.
const stack = G.json().pipe(G.length({ max: 1000 }));
assert.equal(stack.guards.length, 2);
assert.deepEqual(
  stack.guards.map((g) => g.name),
  ["json", "length"],
);

// 3. Guards run their checks: GuardViolation thrown on failure.
let threw = false;
try {
  G.length({ max: 5 }).guards[0].check("this is way too long");
} catch (e) {
  threw = e instanceof GuardViolation;
}
assert.ok(threw, "length guard should throw GuardViolation when too long");

let jsonThrew = false;
try {
  G.json().guards[0].check("not json");
} catch (e) {
  jsonThrew = e instanceof GuardViolation;
}
assert.ok(jsonThrew, "json guard should throw GuardViolation on invalid JSON");

// Valid JSON passes.
G.json().guards[0].check('{"ok": true}');

// 4. Regex guard with redact action transforms output.
const redacted = G.regex(/secret-\d+/, { action: "redact", replacement: "[REDACTED]" });
const result = redacted.guards[0].check("token: secret-12345 here") as unknown as string;
assert.equal(result, "token: [REDACTED] here");

// Regex guard with block action throws.
let blocked = false;
try {
  G.regex("forbidden", { action: "block" }).guards[0].check("contains forbidden word");
} catch (e) {
  blocked = e instanceof GuardViolation;
}
assert.ok(blocked, "regex(block) should throw on match");

// 5. PII / toxicity / topic / grounded — runtime-resolved by ADK.
const pii = G.pii({ action: "redact" });
assert.equal(pii.guards[0].name, "pii");
assert.equal(pii.guards[0].config?.action, "redact");

const tox = G.toxicity({ threshold: 0.7 });
assert.equal(tox.guards[0].config?.threshold, 0.7);

const topic = G.topic({ deny: ["medical", "legal"] });
assert.deepEqual(topic.guards[0].config?.deny, ["medical", "legal"]);

const grounded = G.grounded({ sourcesKey: "docs" });
assert.equal(grounded.guards[0].config?.sourcesKey, "docs");

// 6. Resource guards.
assert.equal(G.budget({ maxTokens: 1024 }).guards[0].config?.maxTokens, 1024);
assert.equal(G.rateLimit({ rpm: 30 }).guards[0].config?.rpm, 30);
assert.equal(G.maxTurns(5).guards[0].config?.maxTurns, 5);

// 7. Custom guard via G.guard().
let calls = 0;
const customGuard = G.guard(((response: string) => {
  calls++;
  if (response.includes("ERROR")) throw new GuardViolation("custom", "post_model", "no errors");
}) as never);
customGuard.guards[0].check("ok response");
assert.equal(calls, 1);

// 8. Attach a guard composite to an agent.
const agent = new Agent("classifier", "gemini-2.5-flash")
  .instruct("Classify the email and return JSON.")
  .guard(G.json().pipe(G.length({ max: 200 })))
  .build() as Record<string, unknown>;
assert.equal(agent._type, "LlmAgent");

export { stack };
