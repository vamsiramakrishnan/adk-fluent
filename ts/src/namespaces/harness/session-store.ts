/**
 * Session store — unified persistence layer that composes `SessionTape`
 * (event replay) and `ForkManager` (branch state). Mirrors
 * `python/src/adk_fluent/_session/`.
 *
 * `SessionSnapshot` is the frozen on-disk format; `SessionStore` is the
 * mutable runtime object. A store can be serialized to a snapshot,
 * persisted, and hydrated back into a fresh store.
 */

import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import { SessionTape, type HarnessEvent } from "./events.js";
import { ForkManager, type ForkBranch } from "./lifecycle.js";

// ─── SessionSnapshot (frozen) ──────────────────────────────────────────────

export interface SessionSnapshotData {
  events: readonly HarnessEvent[];
  branches: Readonly<Record<string, { state: Record<string, unknown>; createdAt: number }>>;
  activeBranch: string | null;
  version: number;
}

/**
 * Frozen, serializable snapshot of a session. Combines the tape events
 * with the fork branches into one atomic unit so `save()` writes exactly
 * one file.
 */
export class SessionSnapshot implements SessionSnapshotData {
  readonly events: readonly HarnessEvent[];
  readonly branches: Readonly<
    Record<string, { state: Record<string, unknown>; createdAt: number }>
  >;
  readonly activeBranch: string | null;
  readonly version: number;

  constructor(data: Partial<SessionSnapshotData> = {}) {
    this.events = Object.freeze([...(data.events ?? [])]);
    this.branches = Object.freeze({ ...(data.branches ?? {}) });
    this.activeBranch = data.activeBranch ?? null;
    this.version = data.version ?? 1;
    Object.freeze(this);
  }

  toJSON(): SessionSnapshotData {
    return {
      events: this.events,
      branches: this.branches,
      activeBranch: this.activeBranch,
      version: this.version,
    };
  }

  static fromJSON(data: SessionSnapshotData): SessionSnapshot {
    return new SessionSnapshot(data);
  }

  /** Persist the snapshot to a JSON file. */
  save(path: string): void {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(this.toJSON(), null, 2), "utf8");
  }

  /** Load a snapshot from a JSON file. */
  static load(path: string): SessionSnapshot {
    const text = readFileSync(path, "utf8");
    return SessionSnapshot.fromJSON(JSON.parse(text));
  }
}

// ─── SessionStore (mutable runtime) ────────────────────────────────────────

export interface SessionStoreOptions {
  tape?: SessionTape;
  forks?: ForkManager;
  activeBranch?: string | null;
}

/**
 * Single source of truth for session state. Records events into a
 * `SessionTape` and manages branches through a `ForkManager`. Use
 * `snapshot()` / `fromSnapshot()` for atomic persistence.
 */
export class SessionStore {
  readonly tape: SessionTape;
  readonly forks: ForkManager;
  private activeBranchName: string | null;

  constructor(opts: SessionStoreOptions = {}) {
    this.tape = opts.tape ?? new SessionTape();
    this.forks = opts.forks ?? new ForkManager();
    this.activeBranchName = opts.activeBranch ?? null;
  }

  get activeBranch(): string | null {
    return this.activeBranchName;
  }

  /** Record a harness event into the tape. */
  recordEvent(event: HarnessEvent): void {
    this.tape.record(event);
  }

  /** Fork the current state into a named branch. */
  fork(name: string, state: Record<string, unknown>): ForkBranch {
    return this.forks.fork(name, state);
  }

  /** Switch to a named branch, returning its captured state. */
  switch(name: string): Record<string, unknown> {
    const state = this.forks.switch(name);
    this.activeBranchName = name;
    return state;
  }

  /** Produce a frozen snapshot of the entire store. */
  snapshot(): SessionSnapshot {
    const branches: Record<string, { state: Record<string, unknown>; createdAt: number }> = {};
    for (const name of this.forks.list()) {
      // ForkManager doesn't expose internal branches, but switch() returns
      // a clone. Use it to capture each branch.
      branches[name] = {
        state: this.forks.switch(name),
        createdAt: Date.now(),
      };
    }
    // Restore active branch context after iterating.
    if (this.activeBranchName && branches[this.activeBranchName]) {
      // no-op: switch() doesn't mutate manager state, just clones
    }
    return new SessionSnapshot({
      events: [...this.tape.events],
      branches,
      activeBranch: this.activeBranchName,
      version: 1,
    });
  }

  /** Rehydrate a store from a snapshot. */
  static fromSnapshot(snapshot: SessionSnapshot): SessionStore {
    const tape = new SessionTape();
    for (const e of snapshot.events) tape.record(e);
    const forks = new ForkManager();
    for (const [name, { state }] of Object.entries(snapshot.branches)) {
      forks.fork(name, state);
    }
    return new SessionStore({
      tape,
      forks,
      activeBranch: snapshot.activeBranch,
    });
  }

  /** Auto-fork: save the current state into a branch named `auto:<agent>`. */
  autoFork(branchName: string, state: Record<string, unknown>): ForkBranch {
    return this.fork(branchName, state);
  }

  /** Restore a previously auto-forked branch. */
  autoRestore(branchName: string): Record<string, unknown> {
    return this.switch(branchName);
  }

  /** Human-readable summary for debugging. */
  summary(): { eventCount: number; branchCount: number; activeBranch: string | null } {
    return {
      eventCount: this.tape.events.length,
      branchCount: this.forks.list().length,
      activeBranch: this.activeBranchName,
    };
  }

  clear(): void {
    this.tape.clear();
    this.forks.clear();
    this.activeBranchName = null;
  }
}
