/**
 * 64 — MiddlewareSchema: typed middleware state declarations
 *
 * Mirrors `python/examples/cookbook/64_middleware_schema.py`.
 *
 * Demonstrates MiddlewareSchema for declaring middleware state
 * dependencies. In TypeScript, schemas are plain objects/classes with
 * typed field annotations rather than Python metaclass-driven types.
 *
 * Key concepts:
 *   - MiddlewareSchema: declarative reads/writes annotations
 *   - readsKeys() / writesKeys(): introspect dependencies
 *   - schema + agents attributes on middleware classes
 *   - M.scope() and M.when() preserve schema references
 *   - Composition with M.pipe()
 */
import assert from "node:assert/strict";
import { M, MComposite } from "../../src/index.js";

// ---------------------------------------------------------------------------
// MiddlewareSchema — lightweight TypeScript equivalent
// ---------------------------------------------------------------------------

/** Annotation marking a field as a state read dependency. */
interface Reads {
  kind: "reads";
  scope?: string;
}

/** Annotation marking a field as a state write dependency. */
interface Writes {
  kind: "writes";
  scope?: string;
}

/** Field descriptor for a middleware schema. */
interface SchemaField {
  name: string;
  annotation: Reads | Writes;
}

/**
 * Base for typed middleware schemas. Provides readsKeys/writesKeys
 * introspection from declared fields.
 */
class MiddlewareSchema {
  readonly fields: SchemaField[];

  constructor(fields: SchemaField[]) {
    this.fields = fields;
  }

  /** Return the set of scoped read keys (e.g., "app:token_budget"). */
  readsKeys(): Set<string> {
    const keys = new Set<string>();
    for (const f of this.fields) {
      if (f.annotation.kind === "reads") {
        const scope = f.annotation.scope;
        keys.add(scope ? `${scope}:${f.name}` : f.name);
      }
    }
    return keys;
  }

  /** Return the set of scoped write keys (e.g., "temp:tokens_used"). */
  writesKeys(): Set<string> {
    const keys = new Set<string>();
    for (const f of this.fields) {
      if (f.annotation.kind === "writes") {
        const scope = f.annotation.scope;
        keys.add(scope ? `${scope}:${f.name}` : f.name);
      }
    }
    return keys;
  }

  toString(): string {
    const fieldNames = this.fields.map((f) => f.name).join(", ");
    return `${this.constructor.name}(${fieldNames})`;
  }
}

// ---------------------------------------------------------------------------
// 1. Declaring a MiddlewareSchema
// ---------------------------------------------------------------------------

class BudgetState extends MiddlewareSchema {
  constructor() {
    super([
      { name: "token_budget", annotation: { kind: "reads", scope: "app" } },
      { name: "tokens_used", annotation: { kind: "writes", scope: "temp" } },
    ]);
  }
}

const budgetState = new BudgetState();
assert.deepEqual(budgetState.readsKeys(), new Set(["app:token_budget"]));
assert.deepEqual(budgetState.writesKeys(), new Set(["temp:tokens_used"]));

// ---------------------------------------------------------------------------
// 2. Mixed reads and writes
// ---------------------------------------------------------------------------

class EnrichmentState extends MiddlewareSchema {
  constructor() {
    super([
      { name: "api_key", annotation: { kind: "reads", scope: "app" } },
      { name: "enriched_data", annotation: { kind: "writes" } }, // default scope
    ]);
  }
}

const enrichment = new EnrichmentState();
assert.deepEqual(enrichment.readsKeys(), new Set(["app:api_key"]));
assert.deepEqual(enrichment.writesKeys(), new Set(["enriched_data"]));

// ---------------------------------------------------------------------------
// 3. Session-scoped reads (default scope)
// ---------------------------------------------------------------------------

class AuditState extends MiddlewareSchema {
  constructor() {
    super([
      { name: "user_id", annotation: { kind: "reads" } },
      { name: "request_context", annotation: { kind: "reads" } },
    ]);
  }
}

const audit = new AuditState();
assert.deepEqual(audit.readsKeys(), new Set(["user_id", "request_context"]));
assert.deepEqual(audit.writesKeys(), new Set());

// ---------------------------------------------------------------------------
// 4. Empty schema
// ---------------------------------------------------------------------------

class NoOpState extends MiddlewareSchema {
  constructor() {
    super([]);
  }
}

const noop = new NoOpState();
assert.deepEqual(noop.readsKeys(), new Set());
assert.deepEqual(noop.writesKeys(), new Set());

// ---------------------------------------------------------------------------
// 5. Binding schema to middleware class
// ---------------------------------------------------------------------------

class BudgetEnforcer {
  readonly agents = "writer";
  readonly schema = new BudgetState();

  async beforeAgent(_ctx: unknown, _agentName: string): Promise<void> {
    // In production: read token_budget from state, check remaining
  }

  async afterModel(_ctx: unknown, _response: unknown): Promise<void> {
    // In production: update tokens_used in state
  }
}

const enforcer = new BudgetEnforcer();
assert.ok(enforcer.schema instanceof BudgetState);
assert.equal(enforcer.agents, "writer");
assert.deepEqual(enforcer.schema.readsKeys(), new Set(["app:token_budget"]));

// ---------------------------------------------------------------------------
// 6. Schema preserved through M.scope() and M.when()
// ---------------------------------------------------------------------------

const scopedMw = M.scope(["writer"], M.cost());
assert.equal(scopedMw.middlewares.length, 1);
assert.equal(scopedMw.middlewares[0].name, "scope");
assert.deepEqual(scopedMw.middlewares[0].config.agents, ["writer"]);

const conditionalMw = M.when(() => true, M.cost());
assert.equal(conditionalMw.middlewares.length, 1);
assert.equal(conditionalMw.middlewares[0].name, "when");

// ---------------------------------------------------------------------------
// 7. Composing middleware with schemas
// ---------------------------------------------------------------------------

const observabilityStack = M.retry({ maxAttempts: 3 })
  .pipe(M.log())
  .pipe(M.cost())
  .pipe(M.latency());

assert.equal(observabilityStack.middlewares.length, 4);
assert.deepEqual(
  observabilityStack.middlewares.map((m) => m.name),
  ["retry", "log", "cost", "latency"],
);

// Scoped cost tracking: only track for the expensive agent
const scopedCost = M.scope(["writer"], M.cost());
const conditionalLatency = M.when(() => false, M.latency());

// Both produce single-element composites
assert.equal(scopedCost.middlewares.length, 1);
assert.equal(conditionalLatency.middlewares.length, 1);

// ---------------------------------------------------------------------------
// 8. Full production pipeline with schema-aware middleware
// ---------------------------------------------------------------------------

class ComplianceState extends MiddlewareSchema {
  constructor() {
    super([
      { name: "patient_id", annotation: { kind: "reads" } },
      { name: "audit_log", annotation: { kind: "writes", scope: "temp" } },
    ]);
  }
}

class ComplianceMiddleware {
  readonly agents = "patient_lookup";
  readonly schema = new ComplianceState();

  async beforeAgent(_ctx: unknown, _agentName: string): Promise<void> {
    // In production: verify patient consent
  }

  async afterAgent(_ctx: unknown, _agentName: string): Promise<void> {
    // In production: write audit entry
  }
}

const compliance = new ComplianceMiddleware();
assert.deepEqual(compliance.schema.readsKeys(), new Set(["patient_id"]));
assert.deepEqual(compliance.schema.writesKeys(), new Set(["temp:audit_log"]));
assert.equal(compliance.agents, "patient_lookup");

// ---------------------------------------------------------------------------
// 9. Repr
// ---------------------------------------------------------------------------

const repr = budgetState.toString();
assert.ok(repr.includes("BudgetState"));
assert.ok(repr.includes("token_budget"));
assert.ok(repr.includes("tokens_used"));

// ---------------------------------------------------------------------------
// 10. Middleware composition works independently of agents
// ---------------------------------------------------------------------------

const fullStack = M.retry({ maxAttempts: 3 })
  .pipe(M.log())
  .pipe(M.cost());

assert.equal(fullStack.middlewares.length, 3);
assert.deepEqual(
  fullStack.middlewares.map((m) => m.name),
  ["retry", "log", "cost"],
);

// Flat array round-trip
const flat = fullStack.toArray();
assert.equal(flat.length, 3);
assert.equal(flat[0].name, "retry");

export { MiddlewareSchema, BudgetState, EnrichmentState, AuditState };
