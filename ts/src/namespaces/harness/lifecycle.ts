/**
 * Lifecycle utilities — context compression, budget monitoring, cancellation,
 * and conversation forks. Mirrors several files under `_harness/`.
 */

// ─── ContextCompressor ─────────────────────────────────────────────────────

export type CompressionStrategy = (messages: unknown[]) => unknown[];

export interface ContextCompressorOptions {
  threshold?: number;
  strategy?: CompressionStrategy;
  onCompress?: (newSize: number) => void;
}

export class ContextCompressor {
  readonly threshold: number;
  readonly strategy: CompressionStrategy;
  readonly onCompress?: (newSize: number) => void;

  constructor(opts: ContextCompressorOptions = {}) {
    this.threshold = opts.threshold ?? 100_000;
    this.strategy =
      opts.strategy ??
      ((msgs) => {
        // Default strategy: drop the oldest 30% of messages.
        const cut = Math.floor(msgs.length * 0.3);
        return msgs.slice(cut);
      });
    this.onCompress = opts.onCompress;
  }

  shouldCompress(currentTokens: number): boolean {
    return currentTokens >= this.threshold;
  }

  compressMessages(messages: unknown[]): unknown[] {
    const compressed = this.strategy(messages);
    this.onCompress?.(compressed.length);
    return compressed;
  }
}

// ─── BudgetMonitor ─────────────────────────────────────────────────────────

export type BudgetThresholdHandler = (monitor: BudgetMonitor) => void;

/**
 * Tracks cumulative token usage and fires callbacks when configurable
 * thresholds are crossed. Does NOT compress — delegates to handlers.
 */
export class BudgetMonitor {
  readonly maxTokens: number;
  private _used = 0;
  private readonly thresholds: Array<{
    ratio: number;
    handler: BudgetThresholdHandler;
    fired: boolean;
  }> = [];

  constructor(maxTokens = 200_000) {
    this.maxTokens = maxTokens;
  }

  get used(): number {
    return this._used;
  }

  get utilization(): number {
    return this._used / this.maxTokens;
  }

  /** Register a callback that fires once when `ratio` of the budget is used. */
  onThreshold(ratio: number, handler: BudgetThresholdHandler): this {
    this.thresholds.push({ ratio, handler, fired: false });
    return this;
  }

  /** Update used token count. Fires any newly-crossed thresholds. */
  update(used: number): void {
    this._used = used;
    const u = this.utilization;
    for (const t of this.thresholds) {
      if (!t.fired && u >= t.ratio) {
        t.fired = true;
        t.handler(this);
      }
    }
  }

  /** Add to used token count instead of replacing. */
  add(deltaTokens: number): void {
    this.update(this._used + deltaTokens);
  }

  reset(): void {
    this._used = 0;
    for (const t of this.thresholds) t.fired = false;
  }

  /** Build an after-model callback that auto-tracks token usage. */
  afterModelHook(): (event: { inputTokens?: number; outputTokens?: number }) => void {
    return (event) => {
      this.add((event.inputTokens ?? 0) + (event.outputTokens ?? 0));
    };
  }
}

// ─── CancellationToken ─────────────────────────────────────────────────────

/**
 * Cooperative cancellation token. Checked before each tool call.
 * On cancel, the agent is told to stop gracefully.
 */
export class CancellationToken {
  private _cancelled = false;
  snapshot: unknown = null;

  get cancelled(): boolean {
    return this._cancelled;
  }

  cancel(snapshot?: unknown): void {
    this._cancelled = true;
    if (snapshot !== undefined) this.snapshot = snapshot;
  }

  reset(): void {
    this._cancelled = false;
    this.snapshot = null;
  }

  throwIfCancelled(): void {
    if (this._cancelled) throw new Error("Cancelled");
  }
}

// ─── ForkManager ───────────────────────────────────────────────────────────

export interface ForkManagerOptions {
  maxBranches?: number;
}

export interface ForkBranch {
  name: string;
  state: Record<string, unknown>;
  createdAt: number;
}

/**
 * Manages named branches of session state for parallel exploration.
 * Forks let an agent try multiple approaches and pick the best one.
 */
export class ForkManager {
  readonly maxBranches: number;
  private readonly branches = new Map<string, ForkBranch>();

  constructor(opts: ForkManagerOptions = {}) {
    this.maxBranches = opts.maxBranches ?? 20;
  }

  /** Save a snapshot of `state` under `name`. */
  fork(name: string, state: Record<string, unknown>): ForkBranch {
    const branch: ForkBranch = {
      name,
      state: structuredClone(state),
      createdAt: Date.now(),
    };
    this.branches.set(name, branch);
    if (this.branches.size > this.maxBranches) {
      // evict oldest
      const oldest = [...this.branches.entries()].sort(
        (a, b) => a[1].createdAt - b[1].createdAt,
      )[0];
      if (oldest) this.branches.delete(oldest[0]);
    }
    return branch;
  }

  switch(name: string): Record<string, unknown> {
    const b = this.branches.get(name);
    if (!b) throw new Error(`No fork '${name}'`);
    return structuredClone(b.state);
  }

  /** Diff two branches by key. */
  diff(a: string, b: string): Record<string, { from?: unknown; to?: unknown }> {
    const sa = this.branches.get(a)?.state ?? {};
    const sb = this.branches.get(b)?.state ?? {};
    const out: Record<string, { from?: unknown; to?: unknown }> = {};
    const keys = new Set([...Object.keys(sa), ...Object.keys(sb)]);
    for (const k of keys) {
      if (JSON.stringify(sa[k]) !== JSON.stringify(sb[k])) {
        out[k] = { from: sa[k], to: sb[k] };
      }
    }
    return out;
  }

  /** Shallow merge of two branches (b wins on conflict). */
  merge(a: string, b: string): Record<string, unknown> {
    const sa = this.branches.get(a)?.state ?? {};
    const sb = this.branches.get(b)?.state ?? {};
    return { ...sa, ...sb };
  }

  list(): string[] {
    return [...this.branches.keys()];
  }

  clear(): void {
    this.branches.clear();
  }
}
