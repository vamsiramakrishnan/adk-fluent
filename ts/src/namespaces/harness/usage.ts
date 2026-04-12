/**
 * Token usage / cost tracker. Mirrors `python/src/adk_fluent/_usage/`.
 *
 * The module ships three layers:
 *   - `ModelRate` / `CostTable` — frozen per-model pricing
 *   - `TurnUsage` / `AgentUsage` — mutable accumulators scoped to a
 *     single turn or to the whole session per-agent
 *   - `UsageTracker` — the original flat tracker (still used by H.usage())
 */

/** Flat per-million token rate for one model. */
export interface ModelRate {
  readonly inputPerMillion: number;
  readonly outputPerMillion: number;
}

/** Frozen table of per-model rates plus a default fallback. */
export class CostTable {
  readonly rates: ReadonlyMap<string, ModelRate>;
  readonly defaultRate: ModelRate;

  constructor(
    rates: Iterable<[string, ModelRate]> = [],
    defaultRate: ModelRate = { inputPerMillion: 0, outputPerMillion: 0 },
  ) {
    this.rates = new Map(rates);
    this.defaultRate = defaultRate;
    Object.freeze(this);
  }

  /** Look up a rate by model name, falling back to `defaultRate`. */
  rateFor(model: string): ModelRate {
    return this.rates.get(model) ?? this.defaultRate;
  }

  /** Cost (USD) of `input`/`output` tokens for `model`. */
  cost(model: string, inputTokens: number, outputTokens: number): number {
    const r = this.rateFor(model);
    return (
      (inputTokens / 1_000_000) * r.inputPerMillion +
      (outputTokens / 1_000_000) * r.outputPerMillion
    );
  }

  /** Shortcut: uniform rate for every model. */
  static flat(inputPerMillion: number, outputPerMillion: number): CostTable {
    return new CostTable([], { inputPerMillion, outputPerMillion });
  }
}

/** Per-turn accumulator. */
export class TurnUsage {
  inputTokens = 0;
  outputTokens = 0;
  costUsd = 0;
  modelCalls = 0;

  add(input: number, output: number, cost: number): void {
    this.inputTokens += input;
    this.outputTokens += output;
    this.costUsd += cost;
    this.modelCalls += 1;
  }

  get totalTokens(): number {
    return this.inputTokens + this.outputTokens;
  }
}

/** Per-agent accumulator. Holds one `TurnUsage` per turn index. */
export class AgentUsage {
  readonly agent: string;
  readonly turns: TurnUsage[] = [];

  constructor(agent: string) {
    this.agent = agent;
  }

  turn(index: number): TurnUsage {
    while (this.turns.length <= index) this.turns.push(new TurnUsage());
    return this.turns[index];
  }

  get inputTokens(): number {
    return this.turns.reduce((s, t) => s + t.inputTokens, 0);
  }
  get outputTokens(): number {
    return this.turns.reduce((s, t) => s + t.outputTokens, 0);
  }
  get totalTokens(): number {
    return this.inputTokens + this.outputTokens;
  }
  get costUsd(): number {
    return this.turns.reduce((s, t) => s + t.costUsd, 0);
  }
}

export interface UsageTrackerOptions {
  costPerMillionInput?: number;
  costPerMillionOutput?: number;
  costTable?: CostTable;
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
  readonly costTable?: CostTable;
  readonly records: UsageRecord[] = [];
  readonly agents = new Map<string, AgentUsage>();

  constructor(opts: UsageTrackerOptions = {}) {
    this.costPerMillionInput = opts.costPerMillionInput ?? 0;
    this.costPerMillionOutput = opts.costPerMillionOutput ?? 0;
    this.costTable = opts.costTable;
  }

  /** Get or create a per-agent accumulator. */
  forAgent(name: string): AgentUsage {
    let a = this.agents.get(name);
    if (!a) {
      a = new AgentUsage(name);
      this.agents.set(name, a);
    }
    return a;
  }

  /** Record token usage for one model call. */
  record(model: string, inputTokens: number, outputTokens: number): UsageRecord {
    const totalTokens = inputTokens + outputTokens;
    const costUsd = this.costTable
      ? this.costTable.cost(model, inputTokens, outputTokens)
      : (inputTokens / 1_000_000) * this.costPerMillionInput +
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
