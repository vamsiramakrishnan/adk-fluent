/**
 * 66 — T module: fluent tool composition and wrappers
 *
 * Mirrors `python/examples/cookbook/66_t_module_tools.py`.
 *
 * `T.*` factories return `TComposite` instances. Compose with `.pipe()`.
 * Each composite can be passed wholesale to `agent.tools(...)`.
 *
 * Key concepts:
 *   - T.fn(): wrap callable as FunctionTool
 *   - T.agent(): wrap agent as AgentTool
 *   - T.googleSearch(): built-in Google Search
 *   - T.mock(): mock tool for testing
 *   - T.confirm(): human confirmation wrapper
 *   - T.timeout(): tool timeout wrapper
 *   - T.cache(): tool response caching
 *   - T.transform(): pre/post argument/result hooks
 *   - T.schema(): contract-checking schema
 *   - .pipe() composition for combining tools
 *   - Wrapper nesting (cache -> timeout -> tool)
 */
import assert from "node:assert/strict";
import { Agent, T, TComposite } from "../../src/index.js";

// ---------------------------------------------------------------------------
// 1. TComposite basics
// ---------------------------------------------------------------------------

const a = new TComposite([{ type: "raw", name: "tool_a" }]);
const b = new TComposite([{ type: "raw", name: "tool_b" }]);
const c = a.pipe(b);
assert.equal(c.items.length, 2);
assert.equal(c.items[0].name, "tool_a");
assert.equal(c.items[1].name, "tool_b");

// Three-way composition
const d = new TComposite([{ type: "raw", name: "tool_c" }]);
const three = a.pipe(b).pipe(d);
assert.equal(three.items.length, 3);

// ---------------------------------------------------------------------------
// 2. T.fn() wrapping
// ---------------------------------------------------------------------------

function searchWeb(query: string): unknown {
  return { results: [`Results for ${query}`] };
}

const fnTool = T.fn(searchWeb as never, { description: "Search the web" });
assert.ok(fnTool instanceof TComposite);
assert.equal(fnTool.items.length, 1);
assert.equal(fnTool.items[0].type, "function");

// ---------------------------------------------------------------------------
// 3. T.agent() wrapping
// ---------------------------------------------------------------------------

const helper = new Agent("helper", "gemini-2.5-flash").instruct("Help the user.");
const agentTool = T.agent(helper, { description: "Helper agent" });
assert.equal(agentTool.items.length, 1);
assert.equal(agentTool.items[0].type, "agent_tool");
assert.equal(agentTool.items[0].agent, helper);

// ---------------------------------------------------------------------------
// 4. T.googleSearch()
// ---------------------------------------------------------------------------

const gs = T.googleSearch();
assert.equal(gs.items.length, 1);
assert.equal(gs.items[0].type, "google_search");

// ---------------------------------------------------------------------------
// 5. Composition: T.fn() | T.googleSearch()
// ---------------------------------------------------------------------------

const composed = T.fn(searchWeb as never).pipe(T.googleSearch());
assert.equal(composed.items.length, 2);
assert.equal(composed.items[0].type, "function");
assert.equal(composed.items[1].type, "google_search");

// ---------------------------------------------------------------------------
// 6. T.schema()
// ---------------------------------------------------------------------------

class FakeToolSchema {}
const schemaTool = T.schema(FakeToolSchema);
assert.equal(schemaTool.items.length, 1);
assert.equal(schemaTool.items[0].type, "schema");
assert.equal(schemaTool.items[0].schema, FakeToolSchema);

// ---------------------------------------------------------------------------
// 7. T.mock() for testing
// ---------------------------------------------------------------------------

const mockTool = T.mock("search_api", { returns: "mock result" });
assert.equal(mockTool.items.length, 1);
assert.equal(mockTool.items[0].type, "mock");
assert.equal(mockTool.items[0].name, "search_api");
assert.equal(mockTool.items[0].returns, "mock result");

// Mock with side-effect callable
let callCount = 0;
function sideEffectFn(_query: string): string {
  callCount += 1;
  return `Called ${callCount} times`;
}

const mockWithSideEffect = T.mock("counter", { sideEffect: sideEffectFn as never });
assert.equal(mockWithSideEffect.items[0].type, "mock");
assert.equal(mockWithSideEffect.items[0].name, "counter");
assert.equal(typeof mockWithSideEffect.items[0].sideEffect, "function");

// ---------------------------------------------------------------------------
// 8. T.confirm() — human confirmation wrapper
// ---------------------------------------------------------------------------

function riskyOperation(target: string): string {
  return `Executed on ${target}`;
}

// Wrap single tool
const confirmSingle = T.confirm(T.fn(riskyOperation as never), "Are you sure?");
assert.equal(confirmSingle.items.length, 1);
assert.equal(confirmSingle.items[0].confirm, true);
assert.equal(confirmSingle.items[0].confirmMessage, "Are you sure?");

// Wrap a composite (wraps each item)
function sendEmail(to: string, body: string): unknown {
  return { ok: true, to, bytes: body.length };
}

const multi = T.fn(searchWeb as never).pipe(T.fn(sendEmail as never));
const confirmMulti = T.confirm(multi);
assert.equal(confirmMulti.items.length, 2);
assert.ok(confirmMulti.items.every((t) => t.confirm === true));

// ---------------------------------------------------------------------------
// 9. T.timeout() — tool execution timeout
// ---------------------------------------------------------------------------

function slowOperation(data: string): string {
  return `Processed ${data}`;
}

// Default 30s timeout
const timeoutDefault = T.timeout(T.fn(slowOperation as never));
assert.equal(timeoutDefault.items.length, 1);
assert.equal(timeoutDefault.items[0].timeout, 30);

// Custom timeout
const timeout5s = T.timeout(T.fn(slowOperation as never), 5);
assert.equal(timeout5s.items[0].timeout, 5);

// Timeout a composite
const timeoutMulti = T.timeout(
  T.fn(searchWeb as never).pipe(T.fn(sendEmail as never)),
  10,
);
assert.equal(timeoutMulti.items.length, 2);
assert.ok(timeoutMulti.items.every((t) => t.timeout === 10));

// ---------------------------------------------------------------------------
// 10. T.cache() — TTL-based result caching
// ---------------------------------------------------------------------------

function expensiveQuery(query: string): string {
  return `Result for ${query}`;
}

// Default 300s TTL
const cacheDefault = T.cache(T.fn(expensiveQuery as never));
assert.equal(cacheDefault.items.length, 1);
assert.equal(cacheDefault.items[0].cache, true);
assert.equal(cacheDefault.items[0].ttl, 300);

// Custom TTL
const cache60 = T.cache(T.fn(expensiveQuery as never), { ttl: 60 });
assert.equal(cache60.items[0].ttl, 60);

// Cache a composite
function translate(text: string, lang: string): string {
  return `Translated to ${lang}: ${text}`;
}

const cacheMulti = T.cache(
  T.fn(searchWeb as never).pipe(T.fn(translate as never)),
  { ttl: 180 },
);
assert.equal(cacheMulti.items.length, 2);
assert.ok(cacheMulti.items.every((t) => t.cache === true));
assert.ok(cacheMulti.items.every((t) => t.ttl === 180));

// ---------------------------------------------------------------------------
// 11. T.transform() — pre/post argument/result hooks
// ---------------------------------------------------------------------------

function processData(text: string): string {
  return `Processed: ${text}`;
}

// Pre-transform (modify arguments)
function preFn(args: { text: string }): { text: string } {
  return { text: args.text.toUpperCase() };
}

const transformPre = T.transform(T.fn(processData as never), { pre: preFn as never });
assert.equal(transformPre.items.length, 1);
assert.equal(typeof transformPre.items[0].preTransform, "function");
assert.equal(transformPre.items[0].postTransform, undefined);

// Post-transform (modify result)
function postFn(result: string): string {
  return result + " [verified]";
}

const transformPost = T.transform(T.fn(processData as never), { post: postFn as never });
assert.equal(typeof transformPost.items[0].postTransform, "function");

// Both pre and post
const transformBoth = T.transform(T.fn(processData as never), {
  pre: preFn as never,
  post: postFn as never,
});
assert.equal(typeof transformBoth.items[0].preTransform, "function");
assert.equal(typeof transformBoth.items[0].postTransform, "function");

// Transform a composite
const transformMulti = T.transform(
  T.fn(searchWeb as never).pipe(T.fn(translate as never)),
  { pre: preFn as never },
);
assert.equal(transformMulti.items.length, 2);
assert.ok(transformMulti.items.every((t) => typeof t.preTransform === "function"));

// ---------------------------------------------------------------------------
// 12. Wrapper composition (nesting via successive wrapping)
// ---------------------------------------------------------------------------

// Cache -> Timeout -> Tool
const nestedBase = T.fn(expensiveQuery as never);
const nestedTimeout = T.timeout(nestedBase, 5);
const nestedCached = T.cache(nestedTimeout, { ttl: 60 });

assert.equal(nestedCached.items.length, 1);
assert.equal(nestedCached.items[0].cache, true);
assert.equal(nestedCached.items[0].ttl, 60);
assert.equal(nestedCached.items[0].timeout, 5);

// ---------------------------------------------------------------------------
// 13. Protocol tools
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// 14. Skill toolset
// ---------------------------------------------------------------------------

const skill = T.skill("./skills/data-analysis");
assert.equal(skill.items[0].type, "skill_toolset");
assert.deepEqual(skill.items[0].paths, ["./skills/data-analysis"]);

const multiSkill = T.skill(["./skills/a", "./skills/b"]);
assert.deepEqual(multiSkill.items[0].paths, ["./skills/a", "./skills/b"]);

// ---------------------------------------------------------------------------
// 15. Builder integration
// ---------------------------------------------------------------------------

function toolA(x: string): string {
  return x;
}
function toolB(x: string): string {
  return x;
}

const agent = new Agent("composer", "gemini-2.5-flash")
  .instruct("Use the available tools.")
  .tools(T.fn(toolA as never).pipe(T.fn(toolB as never)))
  .build() as Record<string, unknown> & { tools: unknown[] };

assert.equal(agent._type, "LlmAgent");
assert.ok(Array.isArray(agent.tools));

// ---------------------------------------------------------------------------
// 16. Mixed composition: mock | real | wrapped
// ---------------------------------------------------------------------------

function fetchData(url: string): string {
  return `Data from ${url}`;
}

const fullStack = T.mock("db_query", { returns: "cached" })
  .pipe(T.cache(T.fn(fetchData as never), { ttl: 60 }))
  .pipe(T.timeout(T.fn(slowOperation as never), 15))
  .pipe(T.confirm(T.fn(riskyOperation as never), "Confirm risky action"));

assert.equal(fullStack.items.length, 4);

const fullAgent = new Agent("full_demo", "gemini-2.5-flash")
  .instruct("Handle requests using all available tools.")
  .tools(fullStack)
  .build() as Record<string, unknown> & { tools: unknown[] };

assert.equal(fullAgent._type, "LlmAgent");
assert.ok(Array.isArray(fullAgent.tools));

export { composed, fullStack };
