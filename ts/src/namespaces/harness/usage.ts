/**
 * Token usage / cost tracker. Mirrors `_harness/_usage.py`.
 */

export interface UsageTrackerOptions {
  costPerMillionInput?: number;
  costPerMillionOutput?: number;
}

export interface UsageRecord {
  model: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  costUsd: number;
  timestamp: number;
}

export class UsageTracker {
  readonly costPerMillionInput: number;
  readonly costPerMillionOutput: number;
  readonly records: UsageRecord[] = [];

  constructor(opts: UsageTrackerOptions = {}) {
    this.costPerMillionInput = opts.costPerMillionInput ?? 0;
    this.costPerMillionOutput = opts.costPerMillionOutput ?? 0;
  }

  /** Record token usage for one model call. */
  record(model: string, inputTokens: number, outputTokens: number): UsageRecord {
    const totalTokens = inputTokens + outputTokens;
    const costUsd =
      (inputTokens / 1_000_000) * this.costPerMillionInput +
      (outputTokens / 1_000_000) * this.costPerMillionOutput;
    const rec: UsageRecord = {
      model,
      inputTokens,
      outputTokens,
      totalTokens,
      costUsd,
      timestamp: Date.now(),
    };
    this.records.push(rec);
    return rec;
  }

  get totalInputTokens(): number {
    return this.records.reduce((s, r) => s + r.inputTokens, 0);
  }

  get totalOutputTokens(): number {
    return this.records.reduce((s, r) => s + r.outputTokens, 0);
  }

  get totalTokens(): number {
    return this.totalInputTokens + this.totalOutputTokens;
  }

  get totalCostUsd(): number {
    return this.records.reduce((s, r) => s + r.costUsd, 0);
  }

  /** Human-readable summary line. */
  summary(): string {
    const cost = this.totalCostUsd > 0 ? `, $${this.totalCostUsd.toFixed(4)}` : "";
    return (
      `tokens: ${this.totalTokens.toLocaleString()} ` +
      `(in=${this.totalInputTokens.toLocaleString()}, out=${this.totalOutputTokens.toLocaleString()})${cost}`
    );
  }

  /** Build an after-model callback compatible with `Agent.afterModel(...)`. */
  callback(): (event: { model?: string; inputTokens?: number; outputTokens?: number }) => void {
    return (event) => {
      this.record(event.model ?? "unknown", event.inputTokens ?? 0, event.outputTokens ?? 0);
    };
  }
}
