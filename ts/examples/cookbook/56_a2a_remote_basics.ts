/**
 * 56 — A2A RemoteAgent basics
 *
 * `RemoteAgent` consumes a remote A2A (Agent-to-Agent) endpoint as if it
 * were any other builder. It supports `.describe()`, `.timeout()`,
 * `.sends()` / `.receives()` for state ↔ message marshalling, and
 * `.persistentContext()` for keeping a `contextId` across calls.
 *
 * Because RemoteAgent extends BuilderBase, every operator works:
 *   .then() / .parallel() / .fallback() / .times()
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, Fallback, RemoteAgent } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// Construct a remote agent from an explicit agent-card URL.
const researcher = new RemoteAgent("researcher", {
  agentCard: "http://researcher.svc.local:8001/.well-known/agent.json",
})
  .describe("Remote research specialist with citation tools")
  .timeout(30)
  .sends("query")
  .receives("findings", "citations")
  .persistentContext();

const built = researcher.build() as Record<string, unknown>;
assert.equal(built._type, "RemoteAgent");
assert.equal(built.name, "researcher");
assert.equal(built.agent_card, "http://researcher.svc.local:8001/.well-known/agent.json");
assert.equal(built.description, "Remote research specialist with citation tools");
assert.equal(built.timeout, 30);

// `_sends`, `_receives`, `_persistent_context` are private config keys —
// stripped from `.build()` but visible via `.inspect()`.
const snap = researcher.inspect();
assert.deepEqual(snap._sends, ["query"]);
assert.deepEqual(snap._receives, ["findings", "citations"]);
assert.equal(snap._persistent_context, true);

// `.discover()` is a static helper for DNS `.well-known` lookup.
const discovered = RemoteAgent.discover("research-agent.acme.com", "researcher");
const discoveredBuilt = discovered.build() as Record<string, unknown>;
assert.equal(
  discoveredBuilt.agent_card,
  "https://research-agent.acme.com/.well-known/agent.json",
);

// Env-var configured remote — no agent_card baked in, runtime resolves it.
const envRemote = new RemoteAgent("code", { env: "CODE_AGENT_URL" });
const envBuilt = envRemote.build() as Record<string, unknown>;
assert.equal(envBuilt.env, "CODE_AGENT_URL");
assert.equal(envBuilt.agent_card, undefined);

// Operators compose with local agents — pipeline mixes local + remote steps.
const writer = new Agent("writer", MODEL).instruct("Draft a brief.").writes("draft");
const summariser = new Agent("summariser", MODEL).instruct("Summarise findings.");

const mixed = writer.then(researcher).then(summariser);
assert.ok(mixed instanceof Pipeline);
const mixedBuilt = mixed.build() as { subAgents: Record<string, unknown>[] };
assert.equal(mixedBuilt.subAgents.length, 3);
assert.equal((mixedBuilt.subAgents[1] as { _type: string })._type, "RemoteAgent");

// Fallback chain: try remote first, fall back to local agent on failure.
const localFallback = new Agent("local_fallback", MODEL).instruct("Fallback brief.");
const fb = researcher.fallback(localFallback);
assert.ok(fb instanceof Fallback);
const fbBuilt = fb.build() as { children: unknown[] };
assert.equal(fbBuilt.children.length, 2);

export { researcher, mixed };
