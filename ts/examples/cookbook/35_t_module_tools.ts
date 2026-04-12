/**
 * 35 — T module: tool composition
 *
 * Mirrors `python/examples/cookbook/66_t_module_tools.py`.
 *
 * `T.*` factories return `TComposite` instances. Compose with `.pipe()`.
 * Each composite can be passed wholesale to `agent.tools(...)`.
 */
import assert from "node:assert/strict";
import { Agent, T, TComposite } from "../../src/index.js";

// 1. Basic factories.
function searchWeb(query: string): unknown {
  return { results: [`hit for ${query}`] };
}
function sendEmail(to: string, body: string): unknown {
  return { ok: true, to, bytes: body.length };
}

const fnTool = T.fn(searchWeb as never, { description: "Search the web" });
assert.ok(fnTool instanceof TComposite);
assert.equal(fnTool.items.length, 1);
assert.equal(fnTool.items[0].type, "function");

// 2. Pipe composes tool collections.
const stack = T.fn(searchWeb as never).pipe(T.fn(sendEmail as never));
assert.equal(stack.items.length, 2);
assert.equal(stack.items[0].type, "function");
assert.equal(stack.items[1].type, "function");

// 3. Built-in tools.
const search = T.googleSearch();
assert.equal(search.items[0].type, "google_search");

// 4. Agent-as-tool: wrap a child agent for parent invocation.
const child = new Agent("calculator", "gemini-2.5-flash").instruct(
  "Calculate the requested expression and return the number.",
);
const childTool = T.agent(child, { description: "Run a math calculation" });
assert.equal(childTool.items[0].type, "agent_tool");
assert.equal(childTool.items[0].agent, child);

// 5. Wrappers: confirm, timeout, cache layer additional config onto a tool.
const confirmTool = T.confirm(searchWeb as never, "Run web search?");
assert.equal(confirmTool.items[0].confirm, true);
assert.equal(confirmTool.items[0].confirmMessage, "Run web search?");

const timeoutTool = T.timeout(T.fn(searchWeb as never), 5);
assert.equal(timeoutTool.items[0].timeout, 5);

const cacheTool = T.cache(T.fn(searchWeb as never), { ttl: 60 });
assert.equal(cacheTool.items[0].cache, true);
assert.equal(cacheTool.items[0].ttl, 60);

// 6. Transform wraps pre/post hooks onto a tool.
const transformed = T.transform(T.fn(searchWeb as never), {
  pre: ((args: { query: string }) => ({ query: args.query.trim() })) as never,
  post: ((res: unknown) => ({ wrapped: res })) as never,
});
assert.equal(typeof transformed.items[0].preTransform, "function");
assert.equal(typeof transformed.items[0].postTransform, "function");

// 7. Protocol tools: MCP, OpenAPI, A2A.
const mcp = T.mcp("https://example.com/mcp", { prefix: "ext_" });
assert.equal(mcp.items[0].type, "mcp");
assert.equal(mcp.items[0].prefix, "ext_");

const openapi = T.openapi("https://api.example.com/openapi.json");
assert.equal(openapi.items[0].type, "openapi");

const a2a = T.a2a("http://researcher:8001/.well-known/agent.json", {
  name: "researcher",
});
assert.equal(a2a.items[0].type, "a2a");
assert.equal(a2a.items[0].name, "researcher");

// 8. Skill toolset (progressive disclosure).
const skill = T.skill("./skills/data-analysis");
assert.equal(skill.items[0].type, "skill_toolset");
assert.deepEqual(skill.items[0].paths, ["./skills/data-analysis"]);

const multiSkill = T.skill(["./skills/a", "./skills/b"]);
assert.deepEqual(multiSkill.items[0].paths, ["./skills/a", "./skills/b"]);

// 9. Mock tool for testing.
const mock = T.mock("search", { returns: { results: [] } });
assert.equal(mock.items[0].type, "mock");
assert.equal(mock.items[0].name, "search");

// 10. End-to-end: attach a composite stack to an agent.
const agent = new Agent("researcher", "gemini-2.5-flash")
  .instruct("Use the available tools to answer the question.")
  .tools(stack)
  .build() as Record<string, unknown> & { tools: unknown[] };
assert.equal(agent._type, "LlmAgent");
assert.ok(Array.isArray(agent.tools));

const fullStack = stack.pipe(search).pipe(skill);

export { stack, fullStack };
