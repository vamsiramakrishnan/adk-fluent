/**
 * 63 — A2A discovery: `AgentRegistry` and `RemoteAgent.discover`
 *
 * Two patterns for locating remote agents at build time:
 *
 *   1. `AgentRegistry(url).find({ name })`     — registry-backed lookup
 *   2. `RemoteAgent.discover("host.example")`  — DNS `.well-known` lookup
 *
 * Both produce a stub `RemoteAgent` pre-configured with the resolved
 * agent-card URL. The runtime layer is responsible for actually fetching
 * the card; the fluent surface just records the lookup metadata.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, AgentRegistry, RemoteAgent } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// 1. Registry-based lookup.
const registry = new AgentRegistry("http://registry.acme.local:9000");
assert.equal(registry.url, "http://registry.acme.local:9000");

const researcher = registry
  .find({ name: "researcher" })
  .describe("Registry-discovered research agent")
  .timeout(20)
  .sends("query")
  .receives("findings");

const researcherBuilt = researcher.build() as Record<string, unknown>;
assert.equal(researcherBuilt._type, "RemoteAgent");
assert.equal(researcherBuilt.name, "researcher");
assert.equal(researcherBuilt.agent_card, "http://registry.acme.local:9000/agents/researcher");
assert.equal(researcherBuilt.timeout, 20);
// Private send/receive config visible via inspect (stripped from build).
const researcherSnap = researcher.inspect();
assert.deepEqual(researcherSnap._sends, ["query"]);
assert.deepEqual(researcherSnap._receives, ["findings"]);

// 2. DNS .well-known discovery.
const summariser = RemoteAgent.discover("summariser.agents.acme.com")
  .describe("DNS-discovered summariser")
  .persistentContext();
const summariserBuilt = summariser.build() as Record<string, unknown>;
assert.equal(
  summariserBuilt.agent_card,
  "https://summariser.agents.acme.com/.well-known/agent.json",
);
// `discover()` defaults the agent name to the host string.
assert.equal(summariserBuilt.name, "summariser.agents.acme.com");
assert.equal(summariser.inspect()._persistent_context, true);

// `discover()` accepts an explicit short name as the second arg.
const named = RemoteAgent.discover("summariser.agents.acme.com", "summariser");
assert.equal((named.build() as { name: string }).name, "summariser");

// Discovered agents drop into pipelines like any other builder.
const local = new Agent("router", MODEL).instruct("Coordinate.");
const pipeline = local.then(researcher).then(summariser);
assert.ok(pipeline instanceof Pipeline);
const pipelineBuilt = pipeline.build() as { subAgents: Array<{ _type?: string; name: string }> };
assert.equal(pipelineBuilt.subAgents.length, 3);
assert.equal(pipelineBuilt.subAgents[1]._type, "RemoteAgent");
assert.equal(pipelineBuilt.subAgents[2]._type, "RemoteAgent");

export { researcher, summariser, pipeline };
