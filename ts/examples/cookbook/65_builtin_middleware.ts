/**
 * 65 — Built-in middleware: observability, resilience, and error handling
 *
 * Mirrors `python/examples/cookbook/65_builtin_middleware.py`.
 *
 * Demonstrates built-in middleware factories for production pipelines:
 * retry, logging, cost tracking, latency, circuit breaker, timeout,
 * cache, fallback model, dedup, trace, and metrics.
 *
 * Key concepts:
 *   - M.retry() / M.log() / M.cost() / M.latency(): observability
 *   - M.circuitBreaker() / M.timeout(): resilience
 *   - M.cache() / M.fallbackModel() / M.dedup(): efficiency
 *   - M.trace() / M.metrics(): distributed observability
 *   - .pipe() composition for stacking middleware
 *   - M.scope() for agent-targeted middleware
 *   - M.when() for conditional middleware
 */
import assert from "node:assert/strict";
import { Agent, M, MComposite } from "../../src/index.js";

// ---------------------------------------------------------------------------
// 1. Core observability middleware
// ---------------------------------------------------------------------------

const retry = M.retry({ maxAttempts: 3 });
assert.ok(retry instanceof MComposite);
assert.equal(retry.middlewares.length, 1);
assert.equal(retry.middlewares[0].name, "retry");
assert.equal(retry.middlewares[0].config.maxAttempts, 3);

const log = M.log();
assert.equal(log.middlewares[0].name, "log");

const cost = M.cost();
assert.equal(cost.middlewares[0].name, "cost");

const latency = M.latency();
assert.equal(latency.middlewares[0].name, "latency");

// ---------------------------------------------------------------------------
// 2. Topology logging
// ---------------------------------------------------------------------------

const topoLog = M.topologyLog();
assert.equal(topoLog.middlewares[0].name, "topology_log");

// ---------------------------------------------------------------------------
// 3. Resilience middleware
// ---------------------------------------------------------------------------

// Circuit breaker
const cb = M.circuitBreaker({ threshold: 5, resetAfter: 60 });
assert.equal(cb.middlewares[0].name, "circuit_breaker");
assert.equal(cb.middlewares[0].config.threshold, 5);
assert.equal(cb.middlewares[0].config.resetAfter, 60);

// Timeout
const timeout = M.timeout(30);
assert.equal(timeout.middlewares[0].name, "timeout");
assert.equal(timeout.middlewares[0].config.seconds, 30);

// Cache
const cache = M.cache({ ttl: 60 });
assert.equal(cache.middlewares[0].name, "cache");
assert.equal(cache.middlewares[0].config.ttl, 60);

// Fallback model
const fallback = M.fallbackModel("gemini-2.0-flash");
assert.equal(fallback.middlewares[0].name, "fallback_model");
assert.equal(fallback.middlewares[0].config.model, "gemini-2.0-flash");

// Dedup
const dedup = M.dedup({ window: 10 });
assert.equal(dedup.middlewares[0].name, "dedup");
assert.equal(dedup.middlewares[0].config.window, 10);

// ---------------------------------------------------------------------------
// 4. Distributed observability
// ---------------------------------------------------------------------------

const trace = M.trace();
assert.equal(trace.middlewares[0].name, "trace");

const metrics = M.metrics();
assert.equal(metrics.middlewares[0].name, "metrics");

// ---------------------------------------------------------------------------
// 5. Production observability stack (pipe composition)
// ---------------------------------------------------------------------------

const productionStack = M.retry({ maxAttempts: 3 })
  .pipe(M.log())
  .pipe(M.cost())
  .pipe(M.latency())
  .pipe(M.topologyLog());

assert.equal(productionStack.middlewares.length, 5);
assert.deepEqual(
  productionStack.middlewares.map((m) => m.name),
  ["retry", "log", "cost", "latency", "topology_log"],
);

// ---------------------------------------------------------------------------
// 6. Scoped middleware: target specific agents
// ---------------------------------------------------------------------------

const scopedCost = M.scope(["writer"], M.cost());
assert.equal(scopedCost.middlewares[0].name, "scope");
assert.deepEqual(scopedCost.middlewares[0].config.agents, ["writer"]);

const multiScoped = M.scope(["writer", "reviewer"], M.log());
assert.deepEqual(multiScoped.middlewares[0].config.agents, ["writer", "reviewer"]);

// ---------------------------------------------------------------------------
// 7. Conditional middleware
// ---------------------------------------------------------------------------

let debugMode = false;
const debugLog = M.when(() => debugMode, M.log());
assert.equal(debugLog.middlewares[0].name, "when");

const streamLatency = M.when(() => true, M.latency());
assert.equal(streamLatency.middlewares[0].name, "when");

// ---------------------------------------------------------------------------
// 8. Composing scoped + conditional middleware for pipelines
// ---------------------------------------------------------------------------

// Build the middleware stack that would be attached to a pipeline:
// global retry + logging, scoped cost for one agent, conditional latency.
const pipelineMw = M.retry({ maxAttempts: 3 })
  .pipe(M.log())
  .pipe(M.scope(["writer"], M.cost()))
  .pipe(M.when(() => debugMode, M.latency()));

assert.equal(pipelineMw.middlewares.length, 4);
assert.deepEqual(
  pipelineMw.middlewares.map((m) => m.name),
  ["retry", "log", "scope", "when"],
);

// Pipeline still builds without middleware wiring.
const writer = new Agent("writer", "gemini-2.5-flash").instruct("Write content.");
const reviewer = new Agent("reviewer", "gemini-2.5-flash").instruct("Review content.");
const pipeline = writer.then(reviewer).build() as { _type: string; subAgents: unknown[] };
assert.equal(pipeline._type, "SequentialAgent");
assert.equal(pipeline.subAgents.length, 2);

// ---------------------------------------------------------------------------
// 9. Full resilience stack
// ---------------------------------------------------------------------------

const resilienceStack = M.retry({ maxAttempts: 3 })
  .pipe(M.circuitBreaker({ threshold: 5, resetAfter: 60 }))
  .pipe(M.timeout(30))
  .pipe(M.cache({ ttl: 60 }))
  .pipe(M.fallbackModel("gemini-2.0-flash"))
  .pipe(M.dedup({ window: 10 }))
  .pipe(M.log())
  .pipe(M.cost())
  .pipe(M.latency());

assert.equal(resilienceStack.middlewares.length, 9);

// Verify order is preserved
assert.deepEqual(
  resilienceStack.middlewares.map((m) => m.name),
  [
    "retry",
    "circuit_breaker",
    "timeout",
    "cache",
    "fallback_model",
    "dedup",
    "log",
    "cost",
    "latency",
  ],
);

// ---------------------------------------------------------------------------
// 10. toArray() flattens back into spec list
// ---------------------------------------------------------------------------

const flat = productionStack.toArray();
assert.equal(flat.length, 5);
assert.equal(flat[0].name, "retry");
assert.equal(flat[4].name, "topology_log");

// ---------------------------------------------------------------------------
// 11. Single-hook shortcuts
// ---------------------------------------------------------------------------

const seen: string[] = [];
const beforeHook = M.beforeAgent(((_ctx: unknown, name: unknown) =>
  seen.push(String(name))) as never);
assert.equal(beforeHook.middlewares[0].name, "before_agent");

assert.equal(M.afterAgent((() => {}) as never).middlewares[0].name, "after_agent");
assert.equal(M.beforeModel((() => {}) as never).middlewares[0].name, "before_model");
assert.equal(M.afterModel((() => {}) as never).middlewares[0].name, "after_model");
assert.equal(M.onLoop((() => {}) as never).middlewares[0].name, "on_loop");
assert.equal(M.onTimeout((() => {}) as never).middlewares[0].name, "on_timeout");
assert.equal(M.onRoute((() => {}) as never).middlewares[0].name, "on_route");
assert.equal(M.onFallback((() => {}) as never).middlewares[0].name, "on_fallback");

// ---------------------------------------------------------------------------
// 12. Full resilience + observability stack composition
// ---------------------------------------------------------------------------

// API gateway stack: resilience + fallback + observability
const apiGatewayStack = resilienceStack;
assert.equal(apiGatewayStack.middlewares.length, 9);

// E-commerce stack: scoped cost tracking for expensive agent
const ecommerceStack = M.retry({ maxAttempts: 3 })
  .pipe(M.log())
  .pipe(M.topologyLog())
  .pipe(M.scope(["fraud_detector"], M.cost()));

assert.equal(ecommerceStack.middlewares.length, 4);

// Agent still builds independently.
const apiAgent = new Agent("api_gateway", "gemini-2.5-flash")
  .instruct("Route API requests.")
  .build() as Record<string, unknown>;
assert.equal(apiAgent._type, "LlmAgent");

// ---------------------------------------------------------------------------
// 13. Sampling middleware
// ---------------------------------------------------------------------------

const sampled = M.sample(0.1, M.log());
assert.equal(sampled.middlewares[0].name, "sample");
assert.equal(sampled.middlewares[0].config.rate, 0.1);

export { productionStack, resilienceStack };
