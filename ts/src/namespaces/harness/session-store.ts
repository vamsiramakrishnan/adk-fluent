/**
 * Session store — unified persistence layer that composes `SessionTape`
 * (event replay) and a per-store branch registry (Python parity). Mirrors
 * `python/src/adk_fluent/_session/`.
 *
 * `SessionSnapshot` is the frozen on-disk format; `SessionStore` is the
 * mutable runtime object. A store can be serialized to a snapshot,
 * persisted, and hydrated back into a fresh store without losing branch
 * metadata (parent lineage, messages history, timestamps, arbitrary
 * metadata bag).
 *
 * Why not delegate everything to `ForkManager`? The minimal TS
 * `ForkManager` in `lifecycle.ts` predates the Python parity push and
 * only tracks `{name, state, createdAt}`. The Python `Branch` is richer
 * (messages, parent, metadata, active-branch pointer) and the snapshot
 * format preserves all of it. This module keeps its own branch registry
 * keyed by name so snapshots round-trip losslessly; the older
 * `ForkManager` remains wired in for back-compat wherever it is still
 * used.
 */

import { writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { dirname } from "node:path";
import { SessionTape, type HarnessEvent } from "./events.js";
import { ForkManager, type ForkBranch } from "./lifecycle.js";

// ─── Branch ────────────────────────────────────────────────────────────────

export interface BranchOptions {
  name: string;
  state: Record<string, unknown>;
  messages?: ReadonlyArray<Record<string, unknown>>;
  parent?: string | null;
  createdAt?: number;
  metadata?: Record<string, unknown>;
}

/**
 * Immutable record of a named state snapshot. Mirrors Python
 * `_session._fork.Branch`.
 *
 * Branches are constructed via `ForkRegistry.fork()` — instances are
 * deeply cloned so the owner of the manager cannot mutate the recorded
 * state after the fact. Fields are public `readonly` so callers can
 * inspect them without invoking getters.
 */
export class Branch {
  readonly name: string;
  readonly state: Readonly<Record<string, unknown>>;
  readonly messages: ReadonlyArray<Record<string, unknown>>;
  readonly parent: string | null;
  readonly createdAt: number;
  readonly metadata: Readonly<Record<string, unknown>>;

  constructor(options: BranchOptions) {
    if (!options.name) {
      throw new Error("Branch.name must be a non-empty string");
    }
    this.name = options.name;
    this.state = Object.freeze(deepClone(options.state ?? {}));
    this.messages = Object.freeze((options.messages ?? []).map((m) => deepClone(m)));
    this.parent = options.parent ?? null;
    this.createdAt = options.createdAt ?? Date.now() / 1000;
    this.metadata = Object.freeze({ ...(options.metadata ?? {}) });
    Object.freeze(this);
  }

  /** Plain-dict representation suitable for `SessionSnapshot` payloads. */
  toDict(): Record<string, unknown> {
    return {
      name: this.name,
      state: deepClone(this.state),
      messages: this.messages.map((m) => deepClone(m)),
      parent: this.parent,
      created_at: this.createdAt,
      metadata: { ...this.metadata },
    };
  }

  static fromDict(data: Record<string, unknown>): Branch {
    return new Branch({
      name: String(data.name ?? "unnamed"),
      state: (data.state as Record<string, unknown>) ?? {},
      messages: (data.messages as ReadonlyArray<Record<string, unknown>>) ?? [],
      parent: (data.parent as string | null) ?? null,
      createdAt:
        typeof data.created_at === "number" ? (data.created_at as number) : Date.now() / 1000,
      metadata: (data.metadata as Record<string, unknown>) ?? {},
    });
  }
}

// ─── ForkRegistry — Python-parity internal branch manager ─────────────────

export type MergeStrategy = "union" | "intersection" | "prefer";

export interface ForkOptions {
  messages?: ReadonlyArray<Record<string, unknown>>;
  parent?: string | null;
  metadata?: Record<string, unknown>;
}

export interface MergeOptions {
  strategy?: MergeStrategy;
  prefer?: string;
}

export interface ForkDiff {
  onlyA: Record<string, unknown>;
  onlyB: Record<string, unknown>;
  different: Record<string, { a: unknown; b: unknown }>;
  same: string[];
}

/**
 * Internal branch manager used by `SessionStore`. Mirrors Python
 * `_session._fork.ForkManager` feature-for-feature: branch lineage,
 * merge strategies, diff, delete, active-pointer, and callback
 * factories.
 *
 * Kept local to this module to avoid breaking the pre-parity
 * `ForkManager` exported from `lifecycle.ts` — callers that want the
 * rich API go through `SessionStore`.
 */
export class ForkRegistry {
  readonly maxBranches: number;
  private readonly branches = new Map<string, Branch>();
  private activeName: string | null = null;

  constructor(opts: { maxBranches?: number } = {}) {
    this.maxBranches = opts.maxBranches ?? 20;
  }

  /** Create a named branch from `state`. */
  fork(name: string, state: Record<string, unknown>, opts: ForkOptions = {}): Branch {
    if (this.maxBranches > 0 && this.branches.size >= this.maxBranches) {
      // Evict the oldest branch (by createdAt) before inserting.
      let oldest: Branch | undefined;
      for (const b of this.branches.values()) {
        if (!oldest || b.createdAt < oldest.createdAt) oldest = b;
      }
      if (oldest && oldest.name !== name) this.branches.delete(oldest.name);
    }
    const branch = new Branch({
      name,
      state,
      messages: opts.messages,
      parent: opts.parent ?? this.activeName,
      metadata: opts.metadata,
    });
    this.branches.set(name, branch);
    this.activeName = name;
    return branch;
  }

  /** Return a deep clone of `name`'s state and mark it active. */
  switch(name: string): Record<string, unknown> {
    const branch = this.branches.get(name);
    if (!branch) {
      const available = [...this.branches.keys()].sort().join(", ");
      throw new Error(`Branch '${name}' not found. Available: ${available}`);
    }
    this.activeName = name;
    return deepClone(branch.state);
  }

  get(name: string): Branch {
    const branch = this.branches.get(name);
    if (!branch) throw new Error(`Branch '${name}' not found`);
    return branch;
  }

  has(name: string): boolean {
    return this.branches.has(name);
  }

  delete(name: string): void {
    this.branches.delete(name);
    if (this.activeName === name) this.activeName = null;
  }

  /**
   * Merge state from multiple branches.
   *
   * - `union` (default): combine all keys; last branch wins on conflict.
   * - `intersection`: keep only keys present in every branch; use last
   *    branch's values.
   * - `prefer`: start with union, then overlay `prefer` branch's values.
   */
  merge(branchNames: string[] = [], opts: MergeOptions = {}): Record<string, unknown> {
    const names = branchNames.length > 0 ? branchNames : [...this.branches.keys()];
    const states: Record<string, unknown>[] = [];
    for (const name of names) {
      const branch = this.branches.get(name);
      if (!branch) throw new Error(`Branch '${name}' not found.`);
      states.push(branch.state as Record<string, unknown>);
    }
    if (states.length === 0) return {};

    const strategy = opts.strategy ?? "union";

    if (strategy === "intersection") {
      let common = new Set(Object.keys(states[0]));
      for (let i = 1; i < states.length; i++) {
        const next = new Set(Object.keys(states[i]));
        common = new Set([...common].filter((k) => next.has(k)));
      }
      const result: Record<string, unknown> = {};
      const last = states[states.length - 1];
      for (const k of common) result[k] = deepClone(last[k]);
      return result;
    }

    if (strategy === "prefer" && opts.prefer) {
      const result: Record<string, unknown> = {};
      let preferredState: Record<string, unknown> | undefined;
      for (let i = 0; i < names.length; i++) {
        Object.assign(result, deepClone(states[i]));
        if (names[i] === opts.prefer) preferredState = states[i];
      }
      if (preferredState) Object.assign(result, deepClone(preferredState));
      return result;
    }

    // union (default) — last wins.
    const result: Record<string, unknown> = {};
    for (const state of states) Object.assign(result, deepClone(state));
    return result;
  }

  diff(branchA: string, branchB: string): ForkDiff {
    const a = this.get(branchA).state as Record<string, unknown>;
    const b = this.get(branchB).state as Record<string, unknown>;
    const keysA = new Set(Object.keys(a));
    const keysB = new Set(Object.keys(b));

    const onlyA: Record<string, unknown> = {};
    for (const k of keysA) if (!keysB.has(k)) onlyA[k] = deepClone(a[k]);
    const onlyB: Record<string, unknown> = {};
    for (const k of keysB) if (!keysA.has(k)) onlyB[k] = deepClone(b[k]);

    const different: Record<string, { a: unknown; b: unknown }> = {};
    const same: string[] = [];
    for (const k of keysA) {
      if (!keysB.has(k)) continue;
      if (JSON.stringify(a[k]) === JSON.stringify(b[k])) {
        same.push(k);
      } else {
        different[k] = { a: deepClone(a[k]), b: deepClone(b[k]) };
      }
    }

    return { onlyA, onlyB, different, same };
  }

  /** Return an array of `{name, parent, keys, messages, active, ...metadata}`. */
  listBranches(): Array<Record<string, unknown>> {
    return [...this.branches.values()].map((b) => ({
      name: b.name,
      parent: b.parent,
      keys: Object.keys(b.state).length,
      messages: b.messages.length,
      active: b.name === this.activeName,
      ...b.metadata,
    }));
  }

  /** Raw insertion-ordered branch list for snapshot serialisation. */
  all(): Branch[] {
    return [...this.branches.values()];
  }

  get active(): string | null {
    return this.activeName;
  }

  set active(name: string | null) {
    if (name !== null && !this.branches.has(name)) {
      throw new Error(`Cannot set active to unknown branch '${name}'`);
    }
    this.activeName = name;
  }

  get size(): number {
    return this.branches.size;
  }

  clear(): void {
    this.branches.clear();
    this.activeName = null;
  }

  // ------------------------------------------------------------- callbacks

  /**
   * Build an `afterAgent`-style callback that auto-forks the active
   * state into `branchName` after every agent run.
   */
  saveCallback(branchName: string): (ctx: unknown) => void {
    return (ctx: unknown) => {
      const state = (ctx as { state?: Record<string, unknown> })?.state;
      if (state) this.fork(branchName, state);
    };
  }

  /**
   * Build a `beforeAgent`-style callback that restores state from
   * `branchName` into the active context.
   */
  restoreCallback(branchName: string): (ctx: unknown) => void {
    return (ctx: unknown) => {
      if (!this.branches.has(branchName)) return;
      const restored = this.switch(branchName);
      const state = (ctx as { state?: Record<string, unknown> })?.state;
      if (state) Object.assign(state, restored);
    };
  }
}

// ─── SessionSnapshot (frozen) ──────────────────────────────────────────────

export interface SessionSnapshotData {
  version: number;
  activeBranch: string | null;
  events: ReadonlyArray<Record<string, unknown>>;
  branches: Readonly<Record<string, Record<string, unknown>>>;
}

/**
 * Frozen, serialisable bundle of tape events + branches. Round-trips
 * losslessly through `toDict()` / `fromDict()` and `save()` / `load()`.
 *
 * The dict format is deliberately snake-case (`active_branch`,
 * `created_at`) so snapshots are portable across the Python and TS
 * runtimes.
 */
export class SessionSnapshot {
  readonly version: number;
  readonly activeBranch: string | null;
  readonly events: ReadonlyArray<Record<string, unknown>>;
  readonly branches: Readonly<Record<string, Record<string, unknown>>>;

  constructor(data: Partial<SessionSnapshotData> = {}) {
    this.version = data.version ?? 1;
    this.activeBranch = data.activeBranch ?? null;
    this.events = Object.freeze([...(data.events ?? [])].map((e) => ({ ...e })));
    const branches: Record<string, Record<string, unknown>> = {};
    for (const [name, branch] of Object.entries(data.branches ?? {})) {
      branches[name] = deepClone(branch) as Record<string, unknown>;
    }
    this.branches = Object.freeze(branches);
    Object.freeze(this);
  }

  /** Snake-cased dict payload mirroring the Python shape. */
  toDict(): Record<string, unknown> {
    return {
      version: this.version,
      active_branch: this.activeBranch,
      events: this.events.map((e) => ({ ...e })),
      branches: deepClone(this.branches),
    };
  }

  static fromDict(data: Record<string, unknown>): SessionSnapshot {
    return new SessionSnapshot({
      version: typeof data.version === "number" ? data.version : 1,
      activeBranch: (data.active_branch as string | null) ?? null,
      events: (data.events as ReadonlyArray<Record<string, unknown>>) ?? [],
      branches: (data.branches as Record<string, Record<string, unknown>>) ?? {},
    });
  }

  /** Persist the snapshot to a JSON file. */
  save(path: string): void {
    const dir = dirname(path);
    if (dir && dir !== "." && !existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    writeFileSync(path, JSON.stringify(this.toDict(), null, 2), "utf8");
  }

  /** Load a snapshot previously written by `save()`. */
  static load(path: string): SessionSnapshot {
    const text = readFileSync(path, "utf8");
    return SessionSnapshot.fromDict(JSON.parse(text));
  }

  get eventCount(): number {
    return this.events.length;
  }

  get branchCount(): number {
    return Object.keys(this.branches).length;
  }
}

// ─── SessionStore (mutable runtime) ────────────────────────────────────────

export interface SessionStoreOptions {
  tape?: SessionTape;
  forks?: ForkRegistry;
  /** Optional legacy `ForkManager` from `lifecycle.ts`. Unused by new code. */
  legacyForks?: ForkManager;
  activeBranch?: string | null;
  maxBranches?: number;
}

/**
 * Session-scoped container for tape + fork registry. One object, one
 * lifetime, one snapshot artifact. Matches Python
 * `_session._store.SessionStore` feature for feature.
 */
export class SessionStore {
  readonly tape: SessionTape;
  readonly forks: ForkRegistry;
  /** Back-compat legacy manager, exposed for callers that still use it. */
  readonly legacyForks: ForkManager;

  constructor(opts: SessionStoreOptions = {}) {
    this.tape = opts.tape ?? new SessionTape();
    this.forks = opts.forks ?? new ForkRegistry({ maxBranches: opts.maxBranches });
    this.legacyForks = opts.legacyForks ?? new ForkManager();
    if (opts.activeBranch !== undefined && opts.activeBranch !== null) {
      if (this.forks.has(opts.activeBranch)) {
        this.forks.active = opts.activeBranch;
      }
    }
  }

  // ---------------------------------------------------- passthroughs

  /** Record a harness event into the tape. */
  recordEvent(event: HarnessEvent): void {
    this.tape.record(event);
  }

  /** Create a named branch. */
  fork(name: string, state: Record<string, unknown>, opts: ForkOptions = {}): Branch {
    return this.forks.fork(name, state, opts);
  }

  /** Switch to a named branch. */
  switch(name: string): Record<string, unknown> {
    return this.forks.switch(name);
  }

  get activeBranch(): string | null {
    return this.forks.active;
  }

  // ---------------------------------------------------- snapshot / restore

  /** Produce a frozen snapshot of the whole store. */
  snapshot(): SessionSnapshot {
    const branches: Record<string, Record<string, unknown>> = {};
    for (const branch of this.forks.all()) {
      branches[branch.name] = branch.toDict();
    }
    return new SessionSnapshot({
      version: 1,
      activeBranch: this.forks.active,
      events: this.tape.events as unknown as ReadonlyArray<Record<string, unknown>>,
      branches,
    });
  }

  /** Rehydrate a store from a snapshot, preserving branch metadata. */
  static fromSnapshot(snapshot: SessionSnapshot): SessionStore {
    const tape = new SessionTape();
    for (const event of snapshot.events) {
      // SessionTape.record expects a HarnessEvent shape; forward the raw
      // entry as an unknown-typed event. The tape's internal list accepts
      // anything with a `kind`, which the snapshot entry already has.
      tape.record(event as unknown as HarnessEvent);
    }
    const forks = new ForkRegistry();
    for (const [name, data] of Object.entries(snapshot.branches)) {
      const branch = Branch.fromDict({ ...data, name });
      // Inline-insert preserving the original createdAt / metadata.
      (forks as unknown as { branches: Map<string, Branch> }).branches.set(name, branch);
    }
    if (
      snapshot.activeBranch &&
      (forks as unknown as { branches: Map<string, Branch> }).branches.has(snapshot.activeBranch)
    ) {
      forks.active = snapshot.activeBranch;
    }
    return new SessionStore({ tape, forks });
  }

  // ---------------------------------------------------- callback factories

  /** `afterAgent` callback that snapshots state to `branchName`. */
  autoFork(branchName: string): (ctx: unknown) => void {
    return this.forks.saveCallback(branchName);
  }

  /** `beforeAgent` callback that restores state from `branchName`. */
  autoRestore(branchName: string): (ctx: unknown) => void {
    return this.forks.restoreCallback(branchName);
  }

  // ---------------------------------------------------- reporting

  /** Quick-glance summary of tape + fork state. */
  summary(): {
    eventCount: number;
    branchCount: number;
    activeBranch: string | null;
    tape: { size: number };
  } {
    return {
      eventCount: this.tape.events.length,
      branchCount: this.forks.size,
      activeBranch: this.forks.active,
      tape: { size: this.tape.events.length },
    };
  }

  /** Drop everything. Tape events and branches are both wiped. */
  clear(): void {
    this.tape.clear();
    this.forks.clear();
    this.legacyForks.clear();
  }
}

// ─── SessionPlugin ─────────────────────────────────────────────────────────

export interface SessionPluginOptions {
  /** Branch name format. Defaults to `auto:<agent>`. */
  branchNamer?: (agentName: string) => string;
}

/**
 * Session-scoped plugin that auto-forks after every agent run. Use as a
 * thin wrapper around a `SessionStore` — the plugin exposes
 * `afterAgent(ctx, agentName)` to be wired into the agent lifecycle.
 *
 * We do not subclass ADK's `BasePlugin` here because the TS ADK runtime
 * surface differs from Python. The plugin is intentionally a plain
 * object so it can be adapted to whichever plugin layer the caller is
 * running against.
 */
export class SessionPlugin {
  readonly store: SessionStore;
  private readonly branchNamer: (agentName: string) => string;

  constructor(store: SessionStore, options: SessionPluginOptions = {}) {
    this.store = store;
    this.branchNamer = options.branchNamer ?? ((name) => `auto:${name}`);
  }

  /** Invoke after every agent run to capture its state into a branch. */
  afterAgent(ctx: unknown, agentName: string): void {
    const state = (ctx as { state?: Record<string, unknown> })?.state;
    if (!state) return;
    this.store.fork(this.branchNamer(agentName), state);
  }

  /** Invoke before every agent run to restore a previously captured branch. */
  beforeAgent(ctx: unknown, agentName: string): void {
    const branchName = this.branchNamer(agentName);
    if (!this.store.forks.has(branchName)) return;
    const restored = this.store.switch(branchName);
    const state = (ctx as { state?: Record<string, unknown> })?.state;
    if (state) Object.assign(state, restored);
  }
}

// ─── helpers ───────────────────────────────────────────────────────────────

function deepClone<T>(value: T): T {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

// Suppress the "unused import" warning for ForkBranch — it is re-exported
// below so callers can keep consuming the legacy shape.
export type { ForkBranch };
