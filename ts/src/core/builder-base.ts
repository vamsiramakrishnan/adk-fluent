/**
 * BuilderBase — immutable fluent builder foundation for adk-fluent-ts.
 *
 * Every builder method returns a new instance (immutable clone pattern).
 * Call `.build()` to produce a native @google/adk object.
 *
 * This is the TypeScript equivalent of Python's `BuilderBase` in `_base.py`.
 * Key differences from the Python version:
 * - Immutable: every setter clones instead of copy-on-write with freeze/fork
 * - Explicit methods: no Proxy or __getattr__ — all setters are generated or hand-written
 * - Method-based operators: .then(), .parallel(), .times() instead of >>, |, *
 */

import type { CallbackFn, State, StatePredicate, UntilSpec } from "./types.js";

/**
 * Abstract base class for all fluent builders.
 *
 * Subclasses must implement:
 * - `build()`: produce the native ADK object
 * - `_clone()`: produce a shallow copy of this builder
 */
export abstract class BuilderBase<TBuild = unknown> {
  /** Key-value configuration (name, model, instruction, etc.) */
  protected _config: Map<string, unknown>;

  /** Callback lists (before_agent, after_model, etc.) */
  protected _callbacks: Map<string, CallbackFn[]>;

  /** List-typed fields (sub_agents, tools, etc.) */
  protected _lists: Map<string, unknown[]>;

  constructor(name: string, extras?: Record<string, unknown>) {
    this._config = new Map<string, unknown>([["name", name]]);
    this._callbacks = new Map<string, CallbackFn[]>();
    this._lists = new Map<string, unknown[]>();
    if (extras) {
      for (const [k, v] of Object.entries(extras)) {
        this._config.set(k, v);
      }
    }
  }

  /** Produce the native @google/adk object. */
  abstract build(): TBuild;

  /**
   * Create a shallow clone of this builder with independent config/callback/list maps.
   * Subclasses should override to copy any additional instance state.
   */
  protected _clone(): this {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ctor = this.constructor as new (...args: any[]) => this;
    const clone = Object.create(Ctor.prototype) as this;
    clone._config = new Map(this._config);
    clone._callbacks = new Map<string, CallbackFn[]>();
    for (const [k, v] of this._callbacks) {
      clone._callbacks.set(k, [...v]);
    }
    clone._lists = new Map<string, unknown[]>();
    for (const [k, v] of this._lists) {
      clone._lists.set(k, [...v]);
    }
    return clone;
  }

  // ------------------------------------------------------------------
  // Protected helpers for subclass setters
  // ------------------------------------------------------------------

  /** Set a config key, returning a new builder. */
  protected _setConfig(key: string, value: unknown): this {
    const next = this._clone();
    next._config.set(key, value);
    return next;
  }

  /** Append to a callback list, returning a new builder. */
  protected _addCallback(key: string, fn: CallbackFn): this {
    const next = this._clone();
    if (!next._callbacks.has(key)) {
      next._callbacks.set(key, []);
    }
    next._callbacks.get(key)!.push(fn);
    return next;
  }

  /** Append to a list field, returning a new builder. */
  protected _addToList(key: string, item: unknown): this {
    const next = this._clone();
    if (!next._lists.has(key)) {
      next._lists.set(key, []);
    }
    next._lists.get(key)!.push(item);
    return next;
  }

  /** Replace a list field entirely, returning a new builder. */
  protected _setList(key: string, items: unknown[]): this {
    const next = this._clone();
    next._lists.set(key, [...items]);
    return next;
  }

  // ------------------------------------------------------------------
  // Composition methods (replacing Python operators)
  // ------------------------------------------------------------------

  /**
   * Sequential composition: `a.then(b)` — equivalent to Python's `a >> b`.
   *
   * Returns a Pipeline that runs this builder first, then `other`.
   * If `this` is already a Pipeline, appends `other` as a new step.
   */
  then(other: BuilderBase | ((...args: unknown[]) => unknown)): BuilderBase {
    // Lazy import to avoid circular deps — resolved at call time
    const { Pipeline } = require("../builders/workflow.js");

    const myName = (this._config.get("name") as string) ?? "";
    const otherName =
      other instanceof BuilderBase
        ? ((other._config.get("name") as string) ?? "")
        : (other as Function).name ?? "fn";

    if (this instanceof Pipeline) {
      const clone = this._clone();
      clone._addToList("sub_agents", other);
      clone._config.set("name", `${myName}_then_${otherName}`);
      return clone;
    }

    const name = `${myName}_then_${otherName}`;
    const p = new Pipeline(name);
    p._lists.set("sub_agents", [this, other]);
    return p;
  }

  /**
   * Parallel composition: `a.parallel(b)` — equivalent to Python's `a | b`.
   *
   * Returns a FanOut that runs this and `other` concurrently.
   * If `this` is already a FanOut, appends `other` as a new branch.
   */
  parallel(other: BuilderBase): BuilderBase {
    const { FanOut } = require("../builders/workflow.js");

    const myName = (this._config.get("name") as string) ?? "";
    const otherName = (other._config.get("name") as string) ?? "";

    if (this instanceof FanOut) {
      const clone = this._clone();
      clone._addToList("sub_agents", other);
      clone._config.set("name", `${myName}_and_${otherName}`);
      return clone;
    }

    const name = `${myName}_and_${otherName}`;
    const f = new FanOut(name);
    f._lists.set("sub_agents", [this, other]);
    return f;
  }

  /**
   * Loop composition: `a.times(3)` — equivalent to Python's `a * 3`.
   *
   * Repeats this builder's workflow N times.
   */
  times(iterations: number): BuilderBase {
    if (iterations < 1) {
      throw new Error(`Loop iterations must be >= 1, got ${iterations}`);
    }

    const { Loop, Pipeline } = require("../builders/workflow.js");

    const myName = (this._config.get("name") as string) ?? "";
    const name = `${myName}_x${iterations}`;
    const loop = new Loop(name);
    loop._config.set("max_iterations", iterations);

    if (this instanceof Pipeline) {
      const subAgents = this._lists.get("sub_agents") ?? [];
      loop._lists.set("sub_agents", [...subAgents]);
    } else {
      loop._lists.set("sub_agents", [this]);
    }
    return loop;
  }

  /**
   * Conditional loop: `a.timesUntil(pred, { max: 5 })`.
   * Equivalent to Python's `a * until(pred, max=5)`.
   */
  timesUntil(
    predicate: StatePredicate | UntilSpec,
    opts?: { max?: number },
  ): BuilderBase {
    let pred: StatePredicate;
    let max: number;
    if (typeof predicate === "function") {
      pred = predicate;
      max = opts?.max ?? 10;
    } else {
      // UntilSpec object
      pred = predicate.predicate;
      max = predicate.max;
    }

    const loop = this.times(max);
    loop._config.set("_until_predicate", pred);
    return loop;
  }

  /**
   * Fallback chain: `a.fallback(b)` — equivalent to Python's `a // b`.
   *
   * Tries this builder first. If it fails, falls back to `other`.
   */
  fallback(other: BuilderBase): BuilderBase {
    const { Fallback } = require("../builders/workflow.js");
    return new Fallback(`${this._config.get("name")}_or_${other._config.get("name")}`, [
      this,
      other,
    ]);
  }

  /**
   * Structured output: `agent.outputAs(schema)` — equivalent to Python's `agent @ Schema`.
   *
   * Forces the LLM to respond with structured output matching the schema.
   */
  outputAs(schema: unknown): this {
    return this._setConfig("_output_schema", schema);
  }

  // ------------------------------------------------------------------
  // Introspection
  // ------------------------------------------------------------------

  /** Return the builder's configured name. */
  get name(): string {
    return (this._config.get("name") as string) ?? "";
  }

  /** Return a snapshot of the current config for debugging. */
  inspect(): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    for (const [k, v] of this._config) {
      result[k] = v;
    }
    for (const [k, v] of this._callbacks) {
      if (v.length > 0) result[`callbacks.${k}`] = v.length;
    }
    for (const [k, v] of this._lists) {
      if (v.length > 0) result[`lists.${k}`] = v.length;
    }
    return result;
  }

  /**
   * Escape hatch: modify the native ADK object after build().
   * `fn` receives the raw object for direct manipulation.
   */
  native(fn: (obj: TBuild) => void): this {
    return this._addCallback("_native_hooks", fn as CallbackFn);
  }

  /** Debug mode: log builder operations to stderr. */
  debug(enabled = true): this {
    return this._setConfig("_debug", enabled);
  }

  // ------------------------------------------------------------------
  // Data flow convenience methods
  // ------------------------------------------------------------------

  /** Store the agent's text response in state[key] after execution. */
  writes(key: string): this {
    return this._setConfig("output_key", key);
  }

  /** Inject state[key] values into this agent's prompt. */
  reads(...keys: string[]): this {
    return this._setConfig("_reads_keys", keys);
  }

  // ------------------------------------------------------------------
  // toString / Symbol.toStringTag
  // ------------------------------------------------------------------

  toString(): string {
    const name = this._config.get("name") ?? "unnamed";
    return `${this.constructor.name}("${name}")`;
  }

  get [Symbol.toStringTag](): string {
    return this.constructor.name;
  }
}

/**
 * Helper to resolve a builder-or-built value.
 * If the item is a BuilderBase, calls .build(). Otherwise returns as-is.
 */
export function autoBuild<T>(item: BuilderBase<T> | T): T {
  if (item instanceof BuilderBase) {
    return item.build();
  }
  return item;
}
