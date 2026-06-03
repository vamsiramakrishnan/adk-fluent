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
import { visualize as visualizeRender } from "../visualize/index.js";
import type { VisualizeOptions } from "../visualize/index.js";
import { CTransform } from "../namespaces/context.js";
import { STransform } from "../namespaces/state.js";
import { AComposite } from "../namespaces/artifacts.js";
import { getWorkflow } from "./builder-internals.js";
import {
  fromDict as _fromDict,
  fromNative as _fromNative,
  fromYaml as _fromYaml,
  toDict as _toDict,
  toYaml as _toYaml,
} from "./builder-serialization.js";
import {
  Signal,
  SignalPredicate,
  makeRuleSpec,
  type ReactorHandler,
  type RuleSpec,
  type RuleSpecOptions,
} from "../namespaces/reactor.js";

// Re-exported for importers that wire the registries (index.ts,
// builders/workflow.ts) at module load. Implementations live in
// builder-internals.ts; serialization lives in builder-serialization.ts.
export { registerBuilderClass, registerWorkflow } from "./builder-internals.js";
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

  /**
   * Append to a callback list, returning a new builder.
   *
   * Accepts ``unknown`` so that generated builders can pass through values
   * whose type the emitter could not narrow. The cast is safe at runtime
   * because the value is only invoked when ``.build()`` is called.
   */
  protected _addCallback(key: string, fn: CallbackFn | unknown): this {
    const next = this._clone();
    let bucket = next._callbacks.get(key);
    if (!bucket) {
      bucket = [];
      next._callbacks.set(key, bucket);
    }
    bucket.push(fn as CallbackFn);
    return next;
  }

  /** Append to a list field, returning a new builder. */
  protected _addToList(key: string, item: unknown): this {
    const next = this._clone();
    let bucket = next._lists.get(key);
    if (!bucket) {
      bucket = [];
      next._lists.set(key, bucket);
    }
    bucket.push(item);
    return next;
  }

  /** Replace a list field entirely, returning a new builder. */
  protected _setList(key: string, items: unknown[]): this {
    const next = this._clone();
    next._lists.set(key, [...items]);
    return next;
  }

  /**
   * Build a plain config object from this builder's state.
   *
   * Used by generated builders that don't have a corresponding
   * `@google/adk` class to construct directly. Returns a tagged
   * config object: ``{ _type: typeName, ...config, ...lists, ...callbacks }``.
   *
   * Sub-builders inside list fields are recursively built.
   */
  protected _buildConfig(typeName: string): Record<string, unknown> {
    const result: Record<string, unknown> = { _type: typeName };

    // Plain config (skip private keys starting with _)
    for (const [k, v] of this._config) {
      if (k.startsWith("_")) continue;
      result[k] = v;
    }

    // Lists — auto-build sub-builders
    for (const [k, v] of this._lists) {
      if (v.length === 0) continue;
      result[k] = v.map((item) => (item instanceof BuilderBase ? item.build() : item));
    }

    // Callbacks
    for (const [k, v] of this._callbacks) {
      if (k.startsWith("_") || v.length === 0) continue;
      if (v.length === 1) {
        result[k] = v[0];
      } else {
        // Compose multiple callbacks into a single async-fold
        const fns = [...v];
        result[k] = async (...args: unknown[]) => {
          for (const fn of fns) {
            await fn(...args);
          }
        };
      }
    }

    return this._applyNativeHooks(result);
  }

  /** Apply any registered ``.native()`` post-build hooks. */
  protected _applyNativeHooks<T>(result: T): T {
    const hooks = this._callbacks.get("_native_hooks");
    if (hooks) {
      for (const hook of hooks) {
        (hook as (obj: T) => void)(result);
      }
    }
    return result;
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
  then(
    other: BuilderBase | ((...args: unknown[]) => unknown) | CTransform | STransform | AComposite,
  ): BuilderBase {
    const Pipeline = getWorkflow("Pipeline");

    // Cross-namespace: a C (context) transform binds to an adjacent Agent's
    // ``.context()`` rather than becoming a state step. ``Agent.then(C)``
    // configures that agent; ``Pipeline.then(C)`` reconfigures the
    // pipeline's last Agent step. Mirrors Python ``Agent >> C``.
    // (S and A transforms fall through and are wrapped as a pipeline step,
    //  exactly like a plain function / fn-step is wrapped today.)
    if (other instanceof CTransform) {
      return this._applyContextTransform(other);
    }

    const myName = (this._config.get("name") as string) ?? "";
    const otherName =
      other instanceof BuilderBase
        ? ((other._config.get("name") as string) ?? "")
        : other instanceof STransform || other instanceof AComposite
          ? ((other as { name?: string }).name ?? "step")
          : ((other as { name?: string }).name ?? "fn");

    if (this instanceof Pipeline) {
      const clone = this._clone();
      const existing = (clone._lists.get("sub_agents") ?? []) as unknown[];
      clone._lists.set("sub_agents", [...existing, other]);
      clone._config.set("name", `${myName}_then_${otherName}`);
      return clone;
    }

    const name = `${myName}_then_${otherName}`;
    const p = new Pipeline(name);
    p._lists.set("sub_agents", [this, other]);
    return p;
  }

  /**
   * Bind a C (context) transform to an Agent in a ``.then()`` chain.
   *
   * A context transform has no standalone state effect; it shapes what an
   * agent sees. In a mixed pipeline it therefore attaches to an adjacent
   * Agent's ``.context()`` instead of becoming a pipeline step:
   *
   * - ``Agent.then(C)``    → that agent, configured with the context.
   * - ``Pipeline.then(C)`` → the pipeline with its **last Agent step**
   *                          reconfigured. Non-Agent trailing steps
   *                          (S/A/fn) are skipped to find the agent the
   *                          context applies to.
   *
   * Throws when no Agent is available to receive the context (e.g.
   * ``FanOut.then(C)`` or a pipeline ending in only S/A steps), pointing
   * the user at the explicit ``.context()`` form. Mirrors Python
   * ``_base.py::_apply_context_transform``.
   */
  protected _applyContextTransform(ctransform: CTransform): BuilderBase {
    const Pipeline = getWorkflow("Pipeline");

    // Direct case: self exposes ``.context()`` (an Agent).
    const maybeCtx = this as unknown as {
      context?: (spec: unknown) => BuilderBase;
    };
    if (typeof maybeCtx.context === "function") {
      return maybeCtx.context(ctransform);
    }

    // Pipeline case: rebind the last Agent step's context.
    if (this instanceof Pipeline) {
      const clone = this._clone();
      const steps = (clone._lists.get("sub_agents") ?? []) as unknown[];
      for (let i = steps.length - 1; i >= 0; i--) {
        const step = steps[i] as { context?: (spec: unknown) => BuilderBase };
        if (step && typeof step.context === "function") {
          steps[i] = step.context(ctransform);
          clone._lists.set("sub_agents", steps);
          return clone;
        }
      }
    }

    throw new Error(
      `Cannot bind a context transform via .then() here: the left operand ` +
        `(${this.constructor.name}) has no Agent to receive it. A C transform ` +
        `configures an agent's context — place it adjacent to an Agent ` +
        `(e.g. agent.then(C.window(5))), or use agent.context(C...).`,
    );
  }

  /**
   * Parallel composition: `a.parallel(b)` — equivalent to Python's `a | b`.
   *
   * Returns a FanOut that runs this and `other` concurrently.
   * If `this` is already a FanOut, appends `other` as a new branch.
   */
  parallel(other: BuilderBase): BuilderBase {
    const FanOut = getWorkflow("FanOut");

    const myName = (this._config.get("name") as string) ?? "";
    const otherName = (other._config.get("name") as string) ?? "";

    if (this instanceof FanOut) {
      const clone = this._clone();
      const existing = (clone._lists.get("sub_agents") ?? []) as unknown[];
      clone._lists.set("sub_agents", [...existing, other]);
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

    const Loop = getWorkflow("Loop");
    const Pipeline = getWorkflow("Pipeline");

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
  timesUntil(predicate: StatePredicate | UntilSpec, opts?: { max?: number }): BuilderBase {
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
    const Fallback = getWorkflow("Fallback");
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

  /**
   * Render this builder's topology as a string.
   *
   * Builds the agent and dispatches to the requested format. The
   * default `"ascii"` format produces a `tree`-style listing suitable
   * for terminal output and `.explain()`-style introspection.
   *
   *   console.log(pipeline.visualize());                       // ascii
   *   console.log(pipeline.visualize({ format: "mermaid" }));  // mermaid
   *   console.log(pipeline.visualize({ format: "markdown" })); // anatomy
   */
  visualize(opts: VisualizeOptions = {}): string {
    return visualizeRender(this.build(), opts);
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
  // Reactive rules (.on)
  // ------------------------------------------------------------------

  /**
   * Attach a declarative reactor rule to this builder.
   *
   * When ``R.compile()`` walks this tree it turns every attached
   * ``RuleSpec`` into a live ``ReactorRule``. If ``handler`` is omitted
   * the default coerces the builder itself (``.askAsync()``) into a
   * handler so the rule re-invokes the agent with a short description
   * of the triggering signal change.
   *
   * ``predicate`` accepts either a bare ``Signal`` (promoted to
   * ``signal.changed``) or a ``SignalPredicate``.
   */
  on(
    predicate: SignalPredicate<unknown> | Signal<unknown>,
    handler?: ReactorHandler,
    opts: RuleSpecOptions = {},
  ): this {
    let pred: SignalPredicate<unknown>;
    if (predicate instanceof SignalPredicate) {
      pred = predicate;
    } else if (predicate instanceof Signal) {
      pred = (predicate as Signal<unknown>).changed;
    } else {
      throw new TypeError(
        ".on(predicate, ...) requires a SignalPredicate or Signal. " + `Got ${typeof predicate}.`,
      );
    }

    const name = opts.name ?? this.name;
    const resolved: ReactorHandler = handler ?? this._defaultReactorHandler();
    const spec = makeRuleSpec(pred, resolved, { ...opts, name });

    const next = this._clone();
    const existing = (next._lists.get("_reactor_rules") ?? []) as RuleSpec[];
    next._lists.set("_reactor_rules", [...existing, spec]);
    return next;
  }

  /**
   * Default reactor handler: fire-and-forget run of this builder.
   * Subclasses that know how to invoke themselves (e.g. Agent) override.
   */
  protected _defaultReactorHandler(): ReactorHandler {
    return async () => {
      // base no-op; Agent overrides with an .askAsync() call.
    };
  }

  /**
   * Read-only view of reactor rules attached via ``.on()``. Useful for
   * tests and introspection.
   */
  get _reactor_rules(): readonly RuleSpec[] {
    return (this._lists.get("_reactor_rules") ?? []) as RuleSpec[];
  }

  // ------------------------------------------------------------------
  // Contracts: consumes / produces / enforceContracts (annotation + runtime)
  // ------------------------------------------------------------------

  /**
   * Annotate what state keys this agent reads. Contract-only by default —
   * NO runtime effect unless promoted via {@link enforceContracts}.
   *
   * ``schema`` may be any object whose field names can be recovered:
   * a Zod object (``.shape`` / ``.keyof()``), an explicit
   * ``{ fields: string[] }`` descriptor, an array of key strings, or a
   * plain object (its own keys). Mirrors Python ``_base.py::consumes``.
   */
  consumes(schema: unknown): this {
    let next = this._setConfig("_consumes", schema);
    // If enforcement is already enabled, (re)install the gate over THIS clone's
    // schema so calling .consumes() after .enforceContracts() still enforces.
    if (next._config.get("_enforceConsumes")) {
      next = next._installContractGate(
        "before_agent_callback",
        "consumes",
        next._makeConsumesGate(schema),
      );
    }
    return next;
  }

  /**
   * Annotate what state keys this agent writes. Contract-only by default —
   * NO runtime effect unless promoted via {@link enforceContracts}.
   * Mirrors Python ``_base.py::produces``.
   */
  produces(schema: unknown): this {
    let next = this._setConfig("_produces", schema);
    if (next._config.get("_enforceProduces")) {
      next = next._installContractGate(
        "after_agent_callback",
        "produces",
        next._makeProducesGate(schema),
      );
    }
    return next;
  }

  /**
   * Promote {@link consumes} / {@link produces} annotations to RUNTIME checks.
   *
   * * **consumes** — installs a ``before_agent_callback`` asserting every
   *   state key named by the consumes schema is present before execution.
   * * **produces** — installs an ``after_agent_callback`` asserting every
   *   state key named by the produces schema was actually written.
   *
   * Violations throw an ``Error``. The schema is read live at execution
   * time, so call order relative to ``.consumes()`` / ``.produces()`` does
   * not matter. Mirrors Python ``_base.py::enforce_contracts``.
   */
  enforceContracts(opts: { consumes?: boolean; produces?: boolean } = {}): this {
    const checkConsumes = opts.consumes ?? true;
    const checkProduces = opts.produces ?? true;

    let next: this = this._setConfig("_enforceConsumes", checkConsumes)._setConfig(
      "_enforceProduces",
      checkProduces,
    );

    // Install gates now for any schema already declared. .consumes() /
    // .produces() called LATER re-install over their own clone (so call order
    // does not matter), and the marker keeps exactly one gate per kind. Each
    // gate closes over the schema VALUE — not a builder clone — so it stays
    // correct across immutable clones without sharing mutable state, keeping
    // sub-expression reuse safe.
    const consumesSchema = next._config.get("_consumes");
    if (checkConsumes && consumesSchema != null) {
      next = next._installContractGate(
        "before_agent_callback",
        "consumes",
        next._makeConsumesGate(consumesSchema),
      );
    }
    const producesSchema = next._config.get("_produces");
    if (checkProduces && producesSchema != null) {
      next = next._installContractGate(
        "after_agent_callback",
        "produces",
        next._makeProducesGate(producesSchema),
      );
    }
    return next;
  }

  /** Build the before-agent gate enforcing a consumes schema (value-captured). */
  private _makeConsumesGate(schema: unknown): CallbackFn {
    const name = (this._config.get("name") as string) ?? "?";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (callbackContext: any) => {
      const state = (callbackContext?.state ?? {}) as State;
      const missing = BuilderBase._schemaFieldNames(schema).filter((k) => !(k in state));
      if (missing.length > 0) {
        throw new Error(
          `contract violation: agent '${name}' .consumes() requires state ` +
            `key(s) [${missing.join(", ")}], which are absent before execution.`,
        );
      }
      return undefined;
    };
  }

  /** Build the after-agent gate enforcing a produces schema (value-captured). */
  private _makeProducesGate(schema: unknown): CallbackFn {
    const name = (this._config.get("name") as string) ?? "?";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (callbackContext: any) => {
      const state = (callbackContext?.state ?? {}) as State;
      const missing = BuilderBase._schemaFieldNames(schema).filter((k) => !(k in state));
      if (missing.length > 0) {
        throw new Error(
          `contract violation: agent '${name}' .produces() promised state ` +
            `key(s) [${missing.join(", ")}], which were not written.`,
        );
      }
      return undefined;
    };
  }

  /**
   * Install a contract gate on a callback list, replacing any prior gate with
   * the same marker so re-running .consumes() / .produces() never duplicates it.
   */
  private _installContractGate(callbackKey: string, marker: string, gate: CallbackFn): this {
    const clone = this._clone();
    const existing = clone._callbacks.get(callbackKey) ?? [];
    const tagged = gate as CallbackFn & { __contractGate?: string };
    tagged.__contractGate = marker;
    const filtered = existing.filter(
      (fn) => (fn as CallbackFn & { __contractGate?: string }).__contractGate !== marker,
    );
    filtered.push(tagged);
    clone._callbacks.set(callbackKey, filtered);
    return clone;
  }

  /**
   * Recover the field names declared by a contract schema.
   *
   * Supports several shapes so the contract layer is not coupled to a
   * single schema library:
   * - ``{ fields: string[] }`` — explicit descriptor
   * - ``string[]`` — bare key list
   * - Zod object — ``.shape`` keys (or ``.keyof().options``)
   * - plain object — its own enumerable keys
   */
  protected static _schemaFieldNames(schema: unknown): string[] {
    if (schema == null) return [];
    if (Array.isArray(schema)) {
      return schema.filter((x): x is string => typeof x === "string");
    }
    const obj = schema as Record<string, unknown>;
    // Explicit descriptor: { fields: [...] }
    if (Array.isArray(obj.fields)) {
      return (obj.fields as unknown[]).filter((x): x is string => typeof x === "string");
    }
    // Zod object: prefer .shape (plain object of field → validator)
    const shape = (obj as { shape?: unknown }).shape;
    if (shape && typeof shape === "object") {
      return Object.keys(shape as Record<string, unknown>);
    }
    // Zod object via internal _def.shape() accessor
    const def = (obj as { _def?: { shape?: unknown } })._def;
    if (def && typeof def.shape === "function") {
      try {
        const s = (def.shape as () => Record<string, unknown>)();
        if (s && typeof s === "object") return Object.keys(s);
      } catch {
        /* fall through */
      }
    }
    // Zod keyof().options
    const keyofFn = (obj as { keyof?: () => { options?: unknown } }).keyof;
    if (typeof keyofFn === "function") {
      try {
        const options = keyofFn.call(obj).options;
        if (Array.isArray(options)) {
          return options.filter((x): x is string => typeof x === "string");
        }
      } catch {
        /* fall through */
      }
    }
    // Plain object: use own enumerable keys.
    return Object.keys(obj);
  }

  // ------------------------------------------------------------------
  // Flow control: proceedIf
  // ------------------------------------------------------------------

  /**
   * Only run this agent if ``predicate(state)`` is truthy. Installs a
   * ``before_agent_callback`` gate. When the predicate returns a falsy
   * value the agent is skipped (the gate returns an empty ``model`` content
   * marker so the pipeline continues to the next step).
   *
   * Errors thrown *inside* the predicate PROPAGATE — they are NOT silently
   * treated as "skip". A thrown error (e.g. a typo'd state key) is a bug,
   * not a skip signal. Guard against missing keys explicitly
   * (e.g. ``(s) => s.valid === "yes"``). Mirrors Python ``_base.py::proceed_if``.
   */
  proceedIf(predicate: StatePredicate): this {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const gate: CallbackFn = (callbackContext: any) => {
      const state = (callbackContext?.state ?? {}) as State;
      // Predicate errors intentionally propagate (no try/catch).
      if (!predicate(state)) {
        // Skip marker: an empty model-role content, mirroring the Python
        // ``types.Content(role="model", parts=[])`` sentinel.
        return { role: "model", parts: [] };
      }
      return undefined;
    };
    return this._addCallback("before_agent_callback", gate);
  }

  // ------------------------------------------------------------------
  // Serialization: toDict / fromDict / toYaml / fromYaml / fromNative
  //
  // Implementations live in builder-serialization.ts (the TS counterpart of
  // Python's _base_serialization.py). These methods are thin delegations so
  // the public API stays on the builder class.
  // ------------------------------------------------------------------

  /** Serialize builder state to a plain dict. See builder-serialization. */
  toDict(): Record<string, unknown> {
    return _toDict(this);
  }

  /** Reconstruct a builder from a {@link toDict} payload. */
  static fromDict(data: Record<string, unknown>): BuilderBase {
    return _fromDict(data);
  }

  /** Serialize builder state to a YAML string (requires the optional `yaml` package). */
  toYaml(): string {
    return _toYaml(this);
  }

  /** Reconstruct a builder from YAML produced by {@link toYaml}. */
  static fromYaml(source: string): BuilderBase {
    return _fromYaml(source);
  }

  /** Adopt a native ADK agent object as a fluent builder — the inverse of `build()`. */
  static fromNative(native: unknown): BuilderBase {
    return _fromNative(native);
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

// Agent / BaseAgent registration for fromDict / fromNative reconstruction is
// performed by the package barrel (index.ts), which imports those classes and
// calls registerBuilderClass(...) synchronously. A top-level await here would
// deadlock the barrel's circular module graph (index → builder-base → agent →
// builder-base). Workflow builders self-register via the _workflowRegistry
// when builders/workflow.js loads. Callers importing builder-base in isolation
// (without the barrel or an explicit registerBuilderClass) get the clear
// "not registered" error from resolveBuilderClass.
