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

  debounce(ms: number): this {
    this._debounceMs = ms;
    return this;
  }

  throttle(ms: number): this {
    this._throttleMs = ms;
    return this;
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
}
