/**
 * Reactor — typed reactive signals + priority-scheduled rule dispatch.
 *
 * Mirrors `python/src/adk_fluent/_reactor/`. A `Signal` holds a single
 * value with a monotonic version; mutations fan out to synchronous
 * subscribers, an optional `EventBus`, and (via `SignalPredicate`) to
 * declarative `.when(...)` handlers scheduled by a `Reactor`.
 *
 * Design decisions
 * ----------------
 * - **Equality guard by default.** `signal.set(v)` is a no-op when
 *   `v === current` (strict equality, plus `NaN`-safe handling via
 *   `Object.is`). Pass `{ force: true }` to emit anyway.
 * - **Version is monotonic.** Even when equality-guarded emissions are
 *   skipped, the version never rewinds. Consumers can memoize on it.
 * - **Observer isolation.** A failing subscriber never blocks other
 *   subscribers or the mutation itself.
 * - **Predicate composition.** `&`, `|`, `~` operators aren't available
 *   in TS, so we expose `.and()`, `.or()`, `.not()` methods.
 * - **Priority preemption.** Lower numeric priority wins. When a rule
 *   fires while one is running, the running task is cancelled and the
 *   new one takes over; the current rule's token gets `resume_cursor`
 *   set to the tape's head.
 */

import type { EventBus, SignalChangedEvent } from "./harness/events.js";
import { AgentToken, TokenRegistry } from "./harness/lifecycle.js";

// ─── Signal ────────────────────────────────────────────────────────────────

export type SignalSubscriber<T = unknown> = (value: T, previous: T) => void;

export interface SignalOptions {
  bus?: EventBus;
}

/**
 * Typed reactive state cell.
 */
export class Signal<T = unknown> {
  readonly name: string;
  private _value: T;
  private _version = 0;
  private _bus?: EventBus;
  private readonly _subs: Array<SignalSubscriber<T>> = [];

  constructor(name: string, initial: T, opts: SignalOptions = {}) {
    this.name = name;
    this._value = initial;
    this._bus = opts.bus;
  }

  /** Monotonic mutation counter. Survives equality-guarded no-ops. */
  get version(): number {
    return this._version;
  }

  get value(): T {
    return this._value;
  }

  get(): T {
    if (_activeTracker !== null) _activeTracker.add(this as Signal<unknown>);
    return this._value;
  }

  /**
   * Set the signal's value. Emits `SignalChangedEvent` unless unchanged.
   * Returns true if an emission happened, false if skipped.
   */
  set(value: T, opts: { force?: boolean } = {}): boolean {
    const prev = this._value;
    if (!opts.force && Object.is(prev, value)) return false;
    this._value = value;
    this._version += 1;
    for (const sub of [...this._subs]) {
      try {
        sub(value, prev);
      } catch {
        // observer isolation — one failing subscriber never blocks another
      }
    }
    if (this._bus) {
      const event: SignalChangedEvent = {
        kind: "signal_changed",
        name: this.name,
        version: this._version,
        value: safeValue(value),
        previous: safeValue(prev),
        timestamp: Date.now(),
      };
      this._bus.emit(event);
    }
    return true;
  }

  /** Apply `fn(current) -> new` atomically. Returns whether emission occurred. */
  update(fn: (current: T) => T): boolean {
    return this.set(fn(this._value));
  }

  /** Register a sync observer. Returns an unsubscribe callable. */
  subscribe(fn: SignalSubscriber<T>): () => void {
    this._subs.push(fn);
    return () => {
      const idx = this._subs.indexOf(fn);
      if (idx >= 0) this._subs.splice(idx, 1);
    };
  }

  /** Wire this signal to a bus. Returns self for chaining. */
  attach(bus: EventBus): this {
    this._bus = bus;
    return this;
  }

  // ── predicate helpers ────────────────────────────────────────────────────

  /** Predicate that fires on every change. */
  get changed(): SignalPredicate<T> {
    return SignalPredicate.onChanged(this);
  }

  /** Predicate that fires when value rises (new > prev). */
  get rising(): SignalPredicate<T> {
    return SignalPredicate.onRising(this);
  }

  /** Predicate that fires when value falls (new < prev). */
  get falling(): SignalPredicate<T> {
    return SignalPredicate.onFalling(this);
  }

  /** Predicate that fires when value equals `expected` after a change. */
  is(expected: T): SignalPredicate<T> {
    return SignalPredicate.onEquals(this, expected);
  }

  toString(): string {
    return `Signal(name=${this.name}, value=${String(this._value)}, v=${this._version})`;
  }
}

function safeValue(value: unknown): unknown {
  if (
    value === null ||
    value === undefined ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return String(value);
  }
}

// ─── SignalPredicate ───────────────────────────────────────────────────────

export type PredicateFn = (current: unknown, previous: unknown) => boolean;

/**
 * Declarative predicate over one or more signals. Use `.and()` / `.or()`
 * / `.not()` to compose, `.where(fn)` to add an extra guard, and
 * `.debounce(ms)` / `.throttle(ms)` for rate control.
 */
export class SignalPredicate<T = unknown> {
  readonly deps: ReadonlyArray<Signal<unknown>>;
  private readonly check: PredicateFn;
  private _debounceMs = 0;
  private _throttleMs = 0;
  private _lastFired = 0;
  private _debounceTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(deps: ReadonlyArray<Signal<unknown>>, check: PredicateFn) {
    this.deps = deps;
    this.check = check;
  }

  static onChanged<U>(signal: Signal<U>): SignalPredicate<U> {
    return new SignalPredicate([signal as Signal<unknown>], () => true);
  }

  static onRising<U>(signal: Signal<U>): SignalPredicate<U> {
    return new SignalPredicate([signal as Signal<unknown>], (curr, prev) => {
      return typeof curr === "number" && typeof prev === "number" && curr > prev;
    });
  }

  static onFalling<U>(signal: Signal<U>): SignalPredicate<U> {
    return new SignalPredicate([signal as Signal<unknown>], (curr, prev) => {
      return typeof curr === "number" && typeof prev === "number" && curr < prev;
    });
  }

  static onEquals<U>(signal: Signal<U>, expected: U): SignalPredicate<U> {
    return new SignalPredicate([signal as Signal<unknown>], (curr) => Object.is(curr, expected));
  }

  and(other: SignalPredicate<unknown>): SignalPredicate<T> {
    const merged = dedupe([...this.deps, ...other.deps]);
    return new SignalPredicate<T>(merged, (c, p) => this.check(c, p) && other.check(c, p));
  }

  or(other: SignalPredicate<unknown>): SignalPredicate<T> {
    const merged = dedupe([...this.deps, ...other.deps]);
    return new SignalPredicate<T>(merged, (c, p) => this.check(c, p) || other.check(c, p));
  }

  not(): SignalPredicate<T> {
    return new SignalPredicate<T>(this.deps, (c, p) => !this.check(c, p));
  }

  where(fn: PredicateFn): SignalPredicate<T> {
    return new SignalPredicate<T>(this.deps, (c, p) => this.check(c, p) && fn(c, p));
  }

  /**
   * Return a fresh predicate with the given debounce window.
   *
   * Immutable: the base predicate is unchanged and can be reused.
   * Preserves any throttle window already attached.
   */
  debounce(ms: number): SignalPredicate<T> {
    const next = new SignalPredicate<T>(this.deps, this.check);
    next._debounceMs = ms;
    next._throttleMs = this._throttleMs;
    return next;
  }

  /**
   * Return a fresh predicate with the given throttle window.
   *
   * Immutable: the base predicate is unchanged and can be reused.
   * Preserves any debounce window already attached.
   */
  throttle(ms: number): SignalPredicate<T> {
    const next = new SignalPredicate<T>(this.deps, this.check);
    next._debounceMs = this._debounceMs;
    next._throttleMs = ms;
    return next;
  }

  /** @internal — used by the R namespace to inspect wiring. */
  get _debounceMsValue(): number {
    return this._debounceMs;
  }

  /** @internal — used by the R namespace to inspect wiring. */
  get _throttleMsValue(): number {
    return this._throttleMs;
  }

  /**
   * Evaluate the predicate for a (current, previous) pair. Returns:
   * - false / "throttled": don't fire
   * - true: fire immediately
   * - "debounce": fire after `debounceMs` elapses without another hit
   *
   * When the predicate returns "debounce", the caller passes a `fire`
   * callback invoked once after the debounce window lapses.
   */
  evaluate(current: unknown, previous: unknown, fire: () => void): "fired" | "skipped" {
    if (!this.check(current, previous)) return "skipped";
    const now = Date.now();
    if (this._throttleMs > 0 && now - this._lastFired < this._throttleMs) {
      return "skipped";
    }
    if (this._debounceMs > 0) {
      if (this._debounceTimer !== null) clearTimeout(this._debounceTimer);
      this._debounceTimer = setTimeout(() => {
        this._debounceTimer = null;
        this._lastFired = Date.now();
        fire();
      }, this._debounceMs);
      return "skipped"; // caller should not fire now
    }
    this._lastFired = now;
    fire();
    return "fired";
  }
}

function isThenable(v: unknown): boolean {
  return (
    !!v &&
    (typeof v === "object" || typeof v === "function") &&
    typeof (v as { then?: unknown }).then === "function"
  );
}

function dedupe(signals: Array<Signal<unknown>>): Signal<unknown>[] {
  const seen = new Set<Signal<unknown>>();
  const out: Signal<unknown>[] = [];
  for (const s of signals) {
    if (!seen.has(s)) {
      seen.add(s);
      out.push(s);
    }
  }
  return out;
}

// ─── Reactor ───────────────────────────────────────────────────────────────

export type ReactorHandler = (ctx: ReactorContext) => Promise<void> | void;

export interface ReactorContext {
  /** Name of the agent this rule is bound to, if any. */
  agentName: string | null;
  /** Per-agent token if the reactor is registry-aware. */
  token: AgentToken | null;
  /** Previous value that triggered the rule. */
  previous: unknown;
  /** Current value that triggered the rule. */
  current: unknown;
  /** Tape head cursor at the moment the rule fired. */
  cursor: number;
}

export interface ReactorRuleOptions {
  /** Stable agent name for targeted preemption via `TokenRegistry`. */
  agentName?: string;
  /** Lower number = higher priority. Default 100. */
  priority?: number;
  /** If true, interrupt any currently-running rule when this one fires. */
  preemptive?: boolean;
}

export interface ReactorRule {
  readonly predicate: SignalPredicate<unknown>;
  readonly handler: ReactorHandler;
  readonly agentName: string | null;
  readonly priority: number;
  readonly preemptive: boolean;
}

export interface ReactorOptions {
  registry?: TokenRegistry;
  /** Called with cursor head when a rule preempts another. Used for
   * emitting an `interrupt` event on a tape or bus. */
  onPreempt?: (victim: ReactorRule, cursor: number) => void;
  /** Optional hook that returns the current tape head cursor, used to
   * stamp `ReactorContext.cursor` and feed preemption resume. */
  cursor?: () => number;
}

/**
 * Declarative priority-scheduled dispatcher over reactive signals.
 *
 * Register rules with `.when(predicate, handler, opts)`, then call
 * `.start()` to subscribe to the underlying signals. Rules are ordered
 * by numeric priority (lower = more important). A `preemptive` rule
 * that fires while another is running cancels the running rule's
 * `AgentToken` with the current cursor so resumption is possible.
 */
interface QueueEntry {
  rule: ReactorRule;
  current: unknown;
  previous: unknown;
}

export class Reactor {
  private readonly rules: ReactorRule[] = [];
  private readonly unsubs: Array<() => void> = [];
  private _current: { rule: ReactorRule; token: AgentToken | null } | null = null;
  private readonly queue: QueueEntry[] = [];
  private readonly registry: TokenRegistry;
  private readonly onPreempt?: (victim: ReactorRule, cursor: number) => void;
  private readonly cursor: () => number;
  private _started = false;

  constructor(opts: ReactorOptions = {}) {
    this.registry = opts.registry ?? new TokenRegistry();
    this.onPreempt = opts.onPreempt;
    this.cursor = opts.cursor ?? (() => 0);
  }

  /** Register a rule. */
  when(
    predicate: SignalPredicate<unknown>,
    handler: ReactorHandler,
    opts: ReactorRuleOptions = {},
  ): this {
    const rule: ReactorRule = {
      predicate,
      handler,
      agentName: opts.agentName ?? null,
      priority: opts.priority ?? 100,
      preemptive: opts.preemptive ?? false,
    };
    this.rules.push(rule);
    return this;
  }

  /** Subscribe to every signal referenced by the registered rules. */
  start(): void {
    if (this._started) return;
    this._started = true;
    const seenSignals = new Set<Signal<unknown>>();
    for (const rule of this.rules) {
      for (const sig of rule.predicate.deps) {
        if (seenSignals.has(sig)) continue;
        seenSignals.add(sig);
        const off = sig.subscribe((curr, prev) => this._onChange(sig, curr, prev));
        this.unsubs.push(off);
      }
    }
  }

  /** Tear down subscriptions. Does not cancel in-flight tasks. */
  stop(): void {
    while (this.unsubs.length) {
      const off = this.unsubs.pop();
      if (off) off();
    }
    this._started = false;
  }

  private _onChange(_sig: Signal<unknown>, current: unknown, previous: unknown): void {
    // Check every rule for this signal; dispatch in priority order.
    const candidates = this.rules
      .filter((r) => r.predicate.deps.includes(_sig))
      .slice()
      .sort((a, b) => a.priority - b.priority);

    for (const rule of candidates) {
      const evaluated = rule.predicate.evaluate(current, previous, () => {
        this._dispatch(rule, current, previous);
      });
      if (evaluated === "fired") {
        // already dispatched synchronously via `fire`
      }
    }
  }

  private _dispatch(rule: ReactorRule, current: unknown, previous: unknown): void {
    const cursor = this.cursor();

    if (this._current && rule.preemptive) {
      // Preempt the running rule.
      const victim = this._current.rule;
      const victimToken = this._current.token;
      if (victimToken) victimToken.cancelWithCursor(cursor);
      this.onPreempt?.(victim, cursor);
      this._current = null;
    } else if (this._current) {
      // Lower-priority rule (or equal-priority reentry): queue it with
      // its own trigger values so the eventual run reflects the right
      // signal state.
      this.queue.push({ rule, current, previous });
      return;
    }

    // Swap in a fresh token for this run. Any in-flight handler holds a
    // reference to the previous token via `ctx.token`, so preemption of
    // the old run is still observable; the new run gets a clean slate.
    let token: AgentToken | null = null;
    if (rule.agentName) {
      token = new AgentToken(rule.agentName);
      this.registry.install(token);
    }
    this._current = { rule, token };

    const ctx: ReactorContext = {
      agentName: rule.agentName,
      token,
      previous,
      current,
      cursor,
    };

    let result: unknown;
    try {
      result = rule.handler(ctx);
    } catch {
      // Rule failures are isolated from the reactor loop.
      this._finish();
      return;
    }

    if (isThenable(result)) {
      (result as Promise<void>).then(
        () => this._finish(),
        () => this._finish(),
      );
    } else {
      this._finish();
    }
  }

  private _finish(): void {
    this._current = null;
    const next = this.queue.shift();
    if (next) this._dispatch(next.rule, next.current, next.previous);
  }

  /** Expose the token registry so callers can cancel specific agents. */
  tokens(): TokenRegistry {
    return this.registry;
  }

  /** The rules registered against this reactor (read-only copy). */
  getRules(): readonly ReactorRule[] {
    return [...this.rules];
  }
}

// ─── Read-tracking for computed signals ────────────────────────────────────

let _activeTracker: Set<Signal<unknown>> | null = null;

/** @internal used by Signal.get() to record reads during tracking. */
export function _recordRead(sig: Signal<unknown>): void {
  if (_activeTracker !== null) _activeTracker.add(sig);
}

function trackReads<R>(fn: () => R): { value: R; deps: Set<Signal<unknown>> } {
  const prev = _activeTracker;
  const deps = new Set<Signal<unknown>>();
  _activeTracker = deps;
  try {
    const value = fn();
    return { value, deps };
  } finally {
    _activeTracker = prev;
  }
}

/**
 * Create a derived signal that re-runs `fn` whenever a dependency changes.
 *
 * Dependencies are auto-tracked: every ``Signal.get()`` called during
 * ``fn`` is subscribed. The first invocation seeds the value; later
 * changes to any tracked dep trigger a recompute and emission.
 */
export function computed<T>(name: string, fn: () => T, opts: SignalOptions = {}): Signal<T> {
  const { value: initial, deps } = trackReads(fn);
  const out = new Signal<T>(name, initial, opts);
  const recompute = (): void => {
    const { value } = trackReads(fn);
    out.set(value);
  };
  for (const dep of deps) {
    dep.subscribe(() => recompute());
  }
  return out;
}

// ─── RuleSpec ──────────────────────────────────────────────────────────────

/**
 * A declarative reactor rule attached to a builder via ``.on()``.
 *
 * Immutable. Stored on builders in the ``_reactor_rules`` list and
 * materialized into a ``ReactorRule`` by ``R.compile()``.
 */
export interface RuleSpec {
  readonly predicate: SignalPredicate<unknown>;
  readonly handler: ReactorHandler | null;
  readonly name: string;
  readonly priority: number;
  readonly preemptive: boolean;
}

export interface RuleSpecOptions {
  name?: string;
  priority?: number;
  preemptive?: boolean;
}

export function makeRuleSpec(
  predicate: SignalPredicate<unknown>,
  handler: ReactorHandler | null,
  opts: RuleSpecOptions = {},
): RuleSpec {
  return Object.freeze({
    predicate,
    handler,
    name: opts.name ?? "",
    priority: opts.priority ?? 0,
    preemptive: opts.preemptive ?? false,
  });
}

// ─── SignalRegistry ────────────────────────────────────────────────────────

/**
 * Thread-safe-style (single-threaded in Node) name→signal registry
 * backing the ``R`` facade.
 *
 * One registry per logical session. The module-level ``defaultRegistry``
 * is the default scope used by ``R.*``; tests and isolated workflows can
 * create a dedicated instance and use it directly.
 *
 * Every signal created through the registry shares the registry's bus,
 * so mutations flow through a single event stream the reactor observes.
 */
export class SignalRegistry {
  private _signals = new Map<string, Signal<unknown>>();
  private _rules: RuleSpec[] = [];
  private _bus?: EventBus;

  constructor(opts: { bus?: EventBus } = {}) {
    this._bus = opts.bus;
  }

  get bus(): EventBus | undefined {
    return this._bus;
  }

  /** Attach a bus. Existing signals are re-wired to it. */
  attach(bus: EventBus): this {
    this._bus = bus;
    for (const sig of this._signals.values()) {
      sig.attach(bus);
    }
    return this;
  }

  /**
   * Get-or-create the named signal. Re-calling with the same name
   * returns the same instance. ``initial`` is only used on first
   * creation.
   */
  signal<T = unknown>(name: string, initial?: T): Signal<T> {
    const existing = this._signals.get(name) as Signal<T> | undefined;
    if (existing) return existing;
    const sig = new Signal<T>(name, initial as T, { bus: this._bus });
    this._signals.set(name, sig as Signal<unknown>);
    return sig;
  }

  /** Return an existing signal or throw. */
  get<T = unknown>(name: string): Signal<T> {
    const sig = this._signals.get(name);
    if (!sig) {
      throw new Error(
        `Signal '${name}' is not registered. Create it with R.signal('${name}', ...) first.`,
      );
    }
    return sig as Signal<T>;
  }

  has(name: string): boolean {
    return this._signals.has(name);
  }

  names(): string[] {
    return [...this._signals.keys()];
  }

  /** Drop every signal and standalone rule. Primarily for tests. */
  clear(): void {
    this._signals.clear();
    this._rules = [];
  }

  /** Register a standalone rule (not tied to a specific builder). */
  rule(
    predicate: SignalPredicate<unknown>,
    handler: ReactorHandler,
    opts: RuleSpecOptions = {},
  ): RuleSpec {
    const spec = makeRuleSpec(predicate, handler, opts);
    this._rules.push(spec);
    return spec;
  }

  rules(): readonly RuleSpec[] {
    return [...this._rules];
  }

  /** @internal */
  _internalRegister(name: string, sig: Signal<unknown>): void {
    if (!this._signals.has(name)) this._signals.set(name, sig);
  }
}

/** Module-level default registry backing the ``R`` facade. */
export let defaultRegistry = new SignalRegistry();

// ─── R — the namespace facade ──────────────────────────────────────────────

/**
 * Walk a builder tree collecting every ``RuleSpec`` attached via ``.on()``.
 *
 * Inspects ``_reactor_rules`` on the builder itself and recurses into
 * ``_lists["sub_agents" | "steps" | "branches" | "agents" | "children"]``.
 */
function walkRules(nodes: readonly unknown[], registry: SignalRegistry): RuleSpec[] {
  const seen = new Set<unknown>();
  const out: RuleSpec[] = [];

  const visit = (node: unknown): void => {
    if (node === null || node === undefined || seen.has(node)) return;
    seen.add(node);

    const rules = (node as { _reactor_rules?: RuleSpec[] })._reactor_rules;
    if (rules && rules.length) out.push(...rules);

    const lists = (node as { _lists?: Map<string, unknown[]> })._lists;
    if (lists instanceof Map) {
      for (const key of ["sub_agents", "steps", "branches", "agents", "children"]) {
        const children = lists.get(key);
        if (children) for (const child of children) visit(child);
      }
    }

    for (const attr of ["_children", "_agents", "_steps", "_branches"] as const) {
      const seq = (node as Record<string, unknown>)[attr];
      if (Array.isArray(seq)) for (const child of seq) visit(child);
    }
  };

  for (const node of nodes) visit(node);
  out.push(...registry.rules());
  return out;
}

function autoName(spec: RuleSpec): string {
  const deps = [...spec.predicate.deps].map((s) => s.name).sort();
  return deps.length ? `on_${deps.join("+")}` : "on_rule";
}

function coerceHandler(handler: ReactorHandler): ReactorHandler {
  return (ctx) => {
    try {
      return handler(ctx);
    } catch (err) {
      throw err;
    }
  };
}

/**
 * Options for ``R.compile()``.
 */
export interface RCompileOptions {
  /** Optional bus to attach to the registry and reactor. */
  bus?: EventBus;
  /** Override the registry used for rule discovery. */
  registry?: SignalRegistry;
  /** Passed through to the constructed ``Reactor``. */
  cursor?: () => number;
  /** Passed through to the constructed ``Reactor``. */
  onPreempt?: (victim: ReactorRule, cursor: number) => void;
  /** Passed through to the constructed ``Reactor``. */
  tokenRegistry?: TokenRegistry;
}

/**
 * The reactive namespace — first-class signals, predicates, and rules.
 *
 * Mirrors the ergonomics of ``S`` (state), ``C`` (context), ``M``
 * (middleware): name-addressed factories instead of manual object
 * construction. Every call delegates to ``defaultRegistry`` unless a
 * dedicated registry is supplied via ``R.scope()``.
 *
 * Example::
 *
 *     import { Agent, R } from "adk-fluent-ts";
 *
 *     const temp = R.signal("temp", 72);
 *     const cooler = new Agent("cooler", "gemini-2.5-flash")
 *       .instruct("Plan a cool-down.")
 *       .on(R.rising("temp").where((v) => (v as number) > 90));
 *
 *     const reactor = R.compile([cooler]);
 *     reactor.start();
 *     temp.set(92);
 */
export const R = {
  // --- Registry access ---------------------------------------------------

  /** The active default registry. */
  registry(): SignalRegistry {
    return defaultRegistry;
  },

  /** Swap the module-level default registry. Primarily for tests. */
  setRegistry(reg: SignalRegistry): void {
    defaultRegistry = reg;
  },

  /** Return a fresh, isolated registry. */
  scope(opts: { bus?: EventBus } = {}): SignalRegistry {
    return new SignalRegistry(opts);
  },

  /** Drop every signal and standalone rule from the default registry. */
  clear(): void {
    defaultRegistry.clear();
  },

  /** Attach a bus to the default registry. Returns it for chaining. */
  attach(bus: EventBus): SignalRegistry {
    return defaultRegistry.attach(bus);
  },

  // --- Signals -----------------------------------------------------------

  /** Get-or-create a named signal in the default registry. */
  signal<T = unknown>(name: string, initial?: T): Signal<T> {
    return defaultRegistry.signal<T>(name, initial);
  },

  /** Return an existing signal by name, or throw. */
  get<T = unknown>(name: string): Signal<T> {
    return defaultRegistry.get<T>(name);
  },

  /** Names of registered signals (insertion order). */
  names(): string[] {
    return defaultRegistry.names();
  },

  // --- Predicate factories (name-addressed) ------------------------------

  /** Predicate that fires on every change of the named signal. */
  changed(name: string): SignalPredicate<unknown> {
    return SignalPredicate.onChanged(defaultRegistry.signal(name));
  },

  /** Predicate that fires when the named signal rises (new > prev). */
  rising(name: string): SignalPredicate<unknown> {
    return SignalPredicate.onRising(defaultRegistry.signal(name));
  },

  /** Predicate that fires when the named signal falls (new < prev). */
  falling(name: string): SignalPredicate<unknown> {
    return SignalPredicate.onFalling(defaultRegistry.signal(name));
  },

  /** Predicate that fires when the named signal equals `expected`. */
  is<T = unknown>(name: string, expected: T): SignalPredicate<unknown> {
    return SignalPredicate.onEquals(defaultRegistry.signal<T>(name), expected);
  },

  // --- Composition -------------------------------------------------------

  /** Fire when any of the passed predicates match. */
  any(...preds: SignalPredicate<unknown>[]): SignalPredicate<unknown> {
    if (preds.length === 0) throw new Error("R.any() requires at least one predicate");
    let combined = preds[0] as SignalPredicate<unknown>;
    for (let i = 1; i < preds.length; i += 1) {
      combined = combined.or(preds[i] as SignalPredicate<unknown>);
    }
    return combined;
  },

  /** Fire only when all of the passed predicates match. */
  all(...preds: SignalPredicate<unknown>[]): SignalPredicate<unknown> {
    if (preds.length === 0) throw new Error("R.all() requires at least one predicate");
    let combined = preds[0] as SignalPredicate<unknown>;
    for (let i = 1; i < preds.length; i += 1) {
      combined = combined.and(preds[i] as SignalPredicate<unknown>);
    }
    return combined;
  },

  // --- Derived signals ---------------------------------------------------

  /**
   * Create a derived signal driven by `fn`. Dependencies are auto-tracked
   * via `Signal.get()`. Registered on the default registry so it can be
   * referenced by name via `R.get(name)` / `R.changed(name)`.
   */
  computed<T>(name: string, fn: () => T): Signal<T> {
    const sig = computed<T>(name, fn, { bus: defaultRegistry.bus });
    defaultRegistry._internalRegister(name, sig as Signal<unknown>);
    return sig;
  },

  // --- Rule helpers ------------------------------------------------------

  /** Register a standalone rule against the default registry. */
  rule(
    predicate: SignalPredicate<unknown>,
    handler: ReactorHandler,
    opts: RuleSpecOptions = {},
  ): RuleSpec {
    return defaultRegistry.rule(predicate, handler, opts);
  },

  // --- Compilation -------------------------------------------------------

  /**
   * Build a `Reactor` with every rule discovered on the given builders
   * plus any standalone rules on the registry.
   *
   * Walks each builder's ``_reactor_rules`` (attached via ``.on()``) and
   * recurses into nested Pipelines / FanOuts / Loops. The bus attached
   * to the registry is reused unless one is supplied explicitly.
   */
  compile(builders: readonly unknown[] = [], opts: RCompileOptions = {}): Reactor {
    const reg = opts.registry ?? defaultRegistry;
    if (opts.bus) reg.attach(opts.bus);
    const reactor = new Reactor({
      registry: opts.tokenRegistry,
      onPreempt: opts.onPreempt,
      cursor: opts.cursor,
    });
    for (const spec of walkRules(builders, reg)) {
      if (spec.handler === null) {
        throw new Error(
          `Rule '${spec.name || "<anonymous>"}' has no handler. ` +
            `Pass one via .on(predicate, handler) or R.rule(pred, fn).`,
        );
      }
      reactor.when(spec.predicate, coerceHandler(spec.handler), {
        agentName: spec.name || autoName(spec),
        priority: spec.priority,
        preemptive: spec.preemptive,
      });
    }
    return reactor;
  },
};

// ─── ReactorPlugin ─────────────────────────────────────────────────────────

/**
 * Lifecycle plugin that starts/stops a ``Reactor`` from session callbacks.
 *
 * Mirrors ``python/src/adk_fluent/_reactor/_plugin.py``. Duck-typed
 * against the ADK plugin protocol — exposes ``onSessionStart`` and
 * ``onSessionEnd`` hooks that the runtime invokes around each session.
 */
export class ReactorPlugin {
  readonly name = "reactor";
  private readonly reactor: Reactor;

  constructor(reactor: Reactor) {
    this.reactor = reactor;
  }

  /** Start the reactor. */
  start(): void {
    this.reactor.start();
  }

  /** Stop the reactor. */
  stop(): void {
    this.reactor.stop();
  }

  async onSessionStart(): Promise<void> {
    this.reactor.start();
  }

  async onSessionEnd(): Promise<void> {
    this.reactor.stop();
  }
}
