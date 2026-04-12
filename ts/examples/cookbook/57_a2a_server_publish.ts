/**
 * 57 — A2A: publish a local agent via `A2AServer`
 *
 * `A2AServer` wraps a local builder and produces a tagged config that
 * describes the HTTP listener, advertised metadata, and skill catalog
 * exposed to remote callers.
 *
 * Methods exercised:
 *   .port()             — listener port
 *   .version()          — semver string
 *   .provider(name,url) — provider metadata block
 *   .skill(id, title)   — append to advertised skill catalog
 *   .healthCheck()      — enable /healthz endpoint
 *   .gracefulShutdown() — drain timeout in seconds
 */
import assert from "node:assert/strict";
import { Agent, A2AServer } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// The local agent we want to publish.
const researcher = new Agent("researcher", MODEL)
  .instruct("Conduct deep research with citations.")
  .describe("Academic research assistant");

const server = new A2AServer(researcher)
  .port(8001)
  .version("1.2.0")
  .provider("Acme Corp", "https://acme.com")
  .skill("research", "Academic Research", {
    description: "Deep research with citations",
    tags: ["research", "citations"],
  })
  .skill("summarise", "Document Summarisation", {
    description: "Distill long documents into key points",
    tags: ["summarisation"],
  })
  .healthCheck()
  .gracefulShutdown(45);

const built = server.build() as Record<string, unknown> & {
  agent: Record<string, unknown>;
  provider: { name: string; url?: string };
  skills: Array<Record<string, unknown>>;
};

assert.equal(built._type, "A2AServer");
assert.equal(built.port, 8001);
assert.equal(built.version, "1.2.0");
assert.equal(built.healthCheck, true);
assert.equal(built.gracefulShutdownTimeout, 45);

// Provider metadata block.
assert.deepEqual(built.provider, { name: "Acme Corp", url: "https://acme.com" });

// Two skills advertised.
assert.equal(built.skills.length, 2);
assert.equal(built.skills[0].id, "research");
assert.equal(built.skills[0].title, "Academic Research");
assert.deepEqual(built.skills[0].tags, ["research", "citations"]);
assert.equal(built.skills[1].id, "summarise");

// The wrapped agent is auto-built into a real ADK config.
assert.equal(built.agent.name, "researcher");
assert.equal(built.agent.description, "Academic research assistant");

// Server metadata is immutable: chaining a new skill clones rather than mutating.
const extended = server.skill("translate", "Translate", { tags: ["i18n"] });
const extendedBuilt = extended.build() as { skills: unknown[] };
assert.equal(extendedBuilt.skills.length, 3);
// Original is unchanged.
assert.equal((server.build() as { skills: unknown[] }).skills.length, 2);

export { server };
