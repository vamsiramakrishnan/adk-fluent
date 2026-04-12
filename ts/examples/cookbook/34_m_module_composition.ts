/**
 * 34 — M module: fluent middleware composition
 *
 * Mirrors `python/examples/cookbook/62_m_module_composition.py`.
 *
 * `M.*` factories return `MComposite` instances. The Python API uses the
 * `|` operator to stack middleware; in TypeScript we use `.pipe()`.
 */
import assert from "node:assert/strict";
import { M, MComposite } from "../../src/index.js";

// 1. Built-in factories produce MComposite instances.
const retry = M.retry({ maxAttempts: 3 });
assert.ok(retry instanceof MComposite);
assert.equal(retry.middlewares.length, 1);
assert.equal(retry.middlewares[0].name, "retry");
assert.equal(retry.middlewares[0].config.maxAttempts, 3);

// 2. Pipe composes middleware chains (Python's `|`).
const stack = M.retry({ maxAttempts: 3 }).pipe(M.log()).pipe(M.cost());
assert.ok(stack instanceof MComposite);
assert.equal(stack.middlewares.length, 3);
assert.deepEqual(
  stack.middlewares.map((m) => m.name),
  ["retry", "log", "cost"],
);

// 3. Scoped middleware restricts to specific agents.
const scoped = M.scope(["writer"], M.cost());
assert.equal(scoped.middlewares.length, 1);
assert.equal(scoped.middlewares[0].name, "scope");
assert.deepEqual(scoped.middlewares[0].config.agents, ["writer"]);

const multiScoped = M.scope(["writer", "reviewer"], M.log());
assert.deepEqual(multiScoped.middlewares[0].config.agents, ["writer", "reviewer"]);

// 4. M.when() applies middleware conditionally.
let debug = false;
const debugLog = M.when(() => debug, M.log());
assert.equal(debugLog.middlewares.length, 1);
assert.equal(debugLog.middlewares[0].name, "when");

// 5. Single-hook shortcuts produce one-element composites.
const seen: string[] = [];
const beforeHook = M.beforeAgent(((_ctx: unknown, name: unknown) => seen.push(String(name))) as never);
assert.equal(beforeHook.middlewares.length, 1);
assert.equal(beforeHook.middlewares[0].name, "before_agent");

assert.equal(M.afterAgent((() => {}) as never).middlewares[0].name, "after_agent");
assert.equal(M.beforeModel((() => {}) as never).middlewares[0].name, "before_model");
assert.equal(M.afterModel((() => {}) as never).middlewares[0].name, "after_model");
assert.equal(M.onLoop((() => {}) as never).middlewares[0].name, "on_loop");
assert.equal(M.onTimeout((() => {}) as never).middlewares[0].name, "on_timeout");
assert.equal(M.onRoute((() => {}) as never).middlewares[0].name, "on_route");
assert.equal(M.onFallback((() => {}) as never).middlewares[0].name, "on_fallback");

// 6. Reliability factories: circuit breaker, timeout, cache, dedup, fallback.
assert.equal(M.circuitBreaker({ threshold: 5 }).middlewares[0].name, "circuit_breaker");
assert.equal(M.timeout(30).middlewares[0].name, "timeout");
assert.equal(M.cache({ ttl: 60 }).middlewares[0].name, "cache");
assert.equal(M.fallbackModel("gemini-2.0-flash").middlewares[0].name, "fallback_model");
assert.equal(M.dedup({ window: 10 }).middlewares[0].name, "dedup");
assert.equal(M.sample(0.1, M.log()).middlewares[0].name, "sample");
assert.equal(M.trace().middlewares[0].name, "trace");
assert.equal(M.metrics().middlewares[0].name, "metrics");

// 7. Production resilience stack.
const resilience = M.retry({ maxAttempts: 3 })
  .pipe(M.circuitBreaker({ threshold: 5 }))
  .pipe(M.timeout(30))
  .pipe(M.cache({ ttl: 60 }));
assert.equal(resilience.middlewares.length, 4);

// 8. Full observability + resilience stack.
const fullStack = M.retry({ maxAttempts: 3 })
  .pipe(M.circuitBreaker({ threshold: 5 }))
  .pipe(M.timeout(30))
  .pipe(M.cache({ ttl: 60 }))
  .pipe(M.fallbackModel("gemini-2.0-flash"))
  .pipe(M.dedup({ window: 10 }))
  .pipe(M.log())
  .pipe(M.cost());
assert.equal(fullStack.middlewares.length, 8);

// 9. toArray() flattens the chain back into a plain spec list.
const flat = stack.toArray();
assert.equal(flat.length, 3);
assert.equal(flat[0].name, "retry");

export { resilience, fullStack };
