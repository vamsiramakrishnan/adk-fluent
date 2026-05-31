/**
 * E — Evaluation namespace.
 *
 * Build evaluation criteria, test cases, and comparison suites.
 * Compose criteria with .pipe() to chain multiple checks.
 *
 * Usage:
 *   agent.eval("What is 2+2?", { expect: "4" })
 *   const suite = E.suite(agent).add(E.case("prompt", { expect: "answer" })).run()
 */

import * as fs from "node:fs";

import type { CallbackFn, State } from "../core/types.js";

/** A single evaluation criterion descriptor. */
export interface ECriterion {
  name: string;
  config: Record<string, unknown>;
}

/** A composable evaluation criteria chain. */
export class EComposite {
  constructor(public readonly criteria: ECriterion[]) {}

  /** Chain: add another criterion. */
  pipe(other: EComposite): EComposite {
    return new EComposite([...this.criteria, ...other.criteria]);
  }

  /** Convert to a flat array. */
  toArray(): ECriterion[] {
    return [...this.criteria];
  }
}

/** An evaluation case descriptor. */
export class ECase {
  constructor(
    public readonly prompt: string,
    public readonly expect?: string,
    public readonly tools?: unknown[],
    public readonly rubrics?: string[],
    public readonly state?: State,
  ) {}
}

/** A conversation scenario for user simulation. */
export class EScenario {
  constructor(
    public readonly start: string,
    public readonly plan: string[],
    public readonly persona?: EPersonaSpec,
  ) {}
}

/** Persona specification. */
export interface EPersonaSpec {
  id: string;
  description: string;
  behaviors: string[];
}

// ---------------------------------------------------------------------------
// Regression gating — baseline comparison primitives
// ---------------------------------------------------------------------------

/** Tiny epsilon absorbing floating-point error at the exact-tolerance boundary. */
const REGRESSION_EPSILON = 1e-9;

/** Serialized shape of an {@link EvalReport} used for baselines. */
export interface EvalReportDict {
  scores: Record<string, number>;
  thresholds?: Record<string, number>;
  passed?: boolean;
  details?: Record<string, unknown>[];
}

/** A baseline accepted by the regression methods. */
export type BaselineInput = EvalReport | EvalReportDict | string;

/**
 * Per-metric comparison between a baseline and a candidate report.
 *
 * A dropped (missing) metric is treated as a regression — you can no longer
 * prove the behaviour still holds. New metrics never regress.
 */
export class MetricDelta {
  constructor(
    public readonly metric: string,
    public readonly baseline: number | undefined,
    public readonly current: number | undefined,
    public readonly tolerance: number = 0,
  ) {
    Object.freeze(this);
  }

  /** `current - baseline`. `undefined` if either side is missing. */
  get delta(): number | undefined {
    if (this.baseline === undefined || this.current === undefined) return undefined;
    return this.current - this.baseline;
  }

  /** True if a baseline metric is absent from the candidate report. */
  get isMissing(): boolean {
    return this.baseline !== undefined && this.current === undefined;
  }

  /** True if the metric is new (present in candidate, absent in baseline). */
  get isNew(): boolean {
    return this.baseline === undefined && this.current !== undefined;
  }

  /** True if this metric dropped beyond `tolerance` (or was dropped entirely). */
  get regressed(): boolean {
    if (this.isMissing) return true;
    const d = this.delta;
    if (d === undefined) return false; // new metric — nothing to regress against
    return d < -this.tolerance - REGRESSION_EPSILON;
  }

  /** True if the metric strictly increased versus the baseline. */
  get improved(): boolean {
    const d = this.delta;
    return d !== undefined && d > 0;
  }

  describe(): string {
    if (this.isMissing) {
      return `${this.metric}: MISSING (baseline=${this.baseline?.toFixed(3)}, dropped from report)`;
    }
    if (this.isNew) {
      return `${this.metric}: NEW (current=${this.current?.toFixed(3)})`;
    }
    const d = this.delta ?? 0;
    const arrow = this.regressed ? "regressed" : this.improved ? "improved" : "stable";
    const sign = d >= 0 ? "+" : "";
    return (
      `${this.metric}: ${this.baseline?.toFixed(3)} -> ${this.current?.toFixed(3)} ` +
      `(delta=${sign}${d.toFixed(3)}, tol=${this.tolerance}) [${arrow}]`
    );
  }
}

/**
 * Structured result of comparing a report against a baseline.
 *
 * `ok` is `true` when no tracked metric regressed beyond the tolerance.
 * Suitable for CI gating.
 */
export class RegressionResult {
  constructor(
    public readonly deltas: MetricDelta[],
    public readonly tolerance: number = 0,
  ) {
    Object.freeze(this.deltas);
    Object.freeze(this);
  }

  /** True if no tracked metric regressed beyond tolerance. */
  get ok(): boolean {
    return this.regressions.length === 0;
  }

  /** Metrics that regressed (dropped beyond tolerance or were removed). */
  get regressions(): MetricDelta[] {
    return this.deltas.filter((d) => d.regressed);
  }

  /** Metrics that strictly improved versus the baseline. */
  get improvements(): MetricDelta[] {
    return this.deltas.filter((d) => d.improved);
  }

  /** Return the {@link MetricDelta} for `metric` if present. */
  deltaFor(metric: string): MetricDelta | undefined {
    return this.deltas.find((d) => d.metric === metric);
  }

  /** Formatted text summary suitable for CI logs. */
  summary(): string {
    const lines: string[] = ["Regression Report", "=".repeat(50)];
    for (const d of this.deltas) lines.push(`  ${d.describe()}`);
    lines.push("=".repeat(50));
    if (this.ok) {
      lines.push("Overall: NO REGRESSION");
    } else {
      const names = this.regressions.map((d) => d.metric).join(", ");
      lines.push(`Overall: REGRESSION DETECTED (${names})`);
    }
    return lines.join("\n");
  }
}

/** Thrown by {@link EvalReport.assertNoRegression} on a detected regression. */
export class RegressionError extends Error {
  constructor(
    message: string,
    public readonly result: RegressionResult,
  ) {
    super(message);
    this.name = "RegressionError";
  }
}

/** Evaluation result wrapper. */
export class EvalReport {
  constructor(
    public readonly passed: boolean,
    public readonly scores: Record<string, number>,
    public readonly details: Record<string, unknown>[],
    public readonly thresholds: Record<string, number> = {},
  ) {}

  /** Overall pass rate. */
  get passRate(): number {
    const values = Object.values(this.scores);
    if (values.length === 0) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }

  // ------------------------------------------------------------------
  // Serialization — baselines round-trip through this format
  // ------------------------------------------------------------------

  /** Serialize the report to a JSON-compatible dict. Metric scores are preserved exactly. */
  toDict(): EvalReportDict {
    return {
      scores: { ...this.scores },
      thresholds: { ...this.thresholds },
      passed: this.passed,
      details: this.details.map((d) => ({ ...d })),
    };
  }

  /** Reconstruct an {@link EvalReport} from {@link EvalReport.toDict} output. */
  static fromDict(data: EvalReportDict): EvalReport {
    const scores: Record<string, number> = {};
    for (const [k, v] of Object.entries(data.scores ?? {})) scores[k] = Number(v);
    const thresholds: Record<string, number> = {};
    for (const [k, v] of Object.entries(data.thresholds ?? {})) thresholds[k] = Number(v);
    return new EvalReport(Boolean(data.passed), scores, data.details ?? [], thresholds);
  }

  /**
   * Persist this report as a golden baseline JSON file. Reuses {@link EvalReport.toDict}
   * so a saved report loads back via {@link EvalReport.loadBaseline} with identical metric
   * data. Returns `this` for chaining.
   */
  saveBaseline(path: string): EvalReport {
    fs.writeFileSync(path, JSON.stringify(this.toDict(), null, 2));
    return this;
  }

  /** Load a baseline report previously written by {@link EvalReport.saveBaseline}. */
  static loadBaseline(path: string): EvalReport {
    const data = JSON.parse(fs.readFileSync(path, "utf-8")) as EvalReportDict;
    return EvalReport.fromDict(data);
  }

  // ------------------------------------------------------------------
  // Regression gating
  // ------------------------------------------------------------------

  /** Normalize a baseline argument (report, dict, or path) into an {@link EvalReport}. */
  private static coerceBaseline(baseline: BaselineInput): EvalReport {
    if (baseline instanceof EvalReport) return baseline;
    if (typeof baseline === "string") return EvalReport.loadBaseline(baseline);
    return EvalReport.fromDict(baseline);
  }

  /**
   * Compare this report's metric scores against a baseline.
   *
   * A metric *regresses* when its score drops by more than `tolerance` relative to the
   * baseline, or when a metric present in the baseline is missing from this report. New,
   * improved, and stable metrics never count as regressions.
   */
  compareToBaseline(baseline: BaselineInput, opts?: { tolerance?: number }): RegressionResult {
    const tolerance = opts?.tolerance ?? 0;
    if (tolerance < 0) throw new Error(`tolerance must be >= 0, got ${tolerance}`);

    const base = EvalReport.coerceBaseline(baseline);
    const metrics = [...new Set([...Object.keys(base.scores), ...Object.keys(this.scores)])];
    const deltas = metrics.map(
      (m) => new MetricDelta(m, base.scores[m], this.scores[m], tolerance),
    );
    return new RegressionResult(deltas, tolerance);
  }

  /**
   * CI gate: throw {@link RegressionError} if any metric regressed. Returns the
   * {@link RegressionResult} on success so callers can inspect improvements.
   */
  assertNoRegression(baseline: BaselineInput, opts?: { tolerance?: number }): RegressionResult {
    const result = this.compareToBaseline(baseline, opts);
    if (!result.ok) throw new RegressionError(result.summary(), result);
    return result;
  }
}

/** Side-by-side comparison results. */
export class ComparisonReport {
  constructor(
    public readonly agents: string[],
    public readonly results: Map<string, EvalReport>,
  ) {}

  /** Get winner by average score. */
  get winner(): string | undefined {
    let best = "";
    let bestScore = -Infinity;
    for (const [name, report] of this.results) {
      if (report.passRate > bestScore) {
        bestScore = report.passRate;
        best = name;
      }
    }
    return best || undefined;
  }
}

/** Fluent evaluation suite builder. Immutable — every mutator returns a fresh clone. */
export class EvalSuite {
  readonly agent: unknown;
  readonly cases: ECase[];
  readonly criteria: EComposite[];

  constructor(agent: unknown, cases: ECase[] = [], criteria: EComposite[] = []) {
    this.agent = agent;
    this.cases = cases;
    this.criteria = criteria;
  }

  /** Internal: produce a clone with overridden fields. */
  private clone(overrides: { cases?: ECase[]; criteria?: EComposite[] }): EvalSuite {
    return new EvalSuite(this.agent, overrides.cases ?? this.cases, overrides.criteria ?? this.criteria);
  }

  /** Add an evaluation case. Returns a new EvalSuite; the original is unchanged. */
  add(testCase: ECase): EvalSuite {
    return this.clone({ cases: [...this.cases, testCase] });
  }

  /** Add evaluation criteria. Returns a new EvalSuite; the original is unchanged. */
  withCriteria(criteria: EComposite): EvalSuite {
    return this.clone({ criteria: [...this.criteria, criteria] });
  }

  /** Run the suite (placeholder — resolved at runtime). */
  async run(): Promise<EvalReport> {
    // At runtime, resolved by ADK evaluation infrastructure
    return new EvalReport(true, {}, []);
  }
}

/** Comparison suite for multiple agents. */
export class ComparisonSuite {
  readonly agents: unknown[];
  readonly cases: ECase[] = [];

  constructor(agents: unknown[]) {
    this.agents = agents;
  }

  /** Add an evaluation case. */
  add(testCase: ECase): this {
    this.cases.push(testCase);
    return this;
  }

  /** Run the comparison (placeholder — resolved at runtime). */
  async run(): Promise<ComparisonReport> {
    return new ComparisonReport([], new Map());
  }
}

/** Prebuilt user simulation personas. */
class PersonaNamespace {
  /** Expert persona: knows what they want, professional tone. */
  expert(): EPersonaSpec {
    return {
      id: "expert",
      description: "An expert user who knows what they want",
      behaviors: [
        "Uses precise technical language",
        "Has clear expectations for output format",
        "Asks follow-up questions when output is imprecise",
      ],
    };
  }

  /** Novice persona: relies on agent, conversational tone. */
  novice(): EPersonaSpec {
    return {
      id: "novice",
      description: "A novice user learning to use the system",
      behaviors: [
        "Uses informal, conversational language",
        "May not know exact terminology",
        "Relies on the agent for guidance",
        "Asks clarifying questions frequently",
      ],
    };
  }

  /** Evaluator persona: assessing capabilities. */
  evaluator(): EPersonaSpec {
    return {
      id: "evaluator",
      description: "An evaluator assessing the agent's capabilities",
      behaviors: [
        "Tests edge cases and boundary conditions",
        "Asks probing questions",
        "Evaluates consistency and accuracy",
        "May try to confuse or mislead the agent",
      ],
    };
  }

  /** Create a custom persona. */
  custom(id: string, description: string, behaviors: string[]): EPersonaSpec {
    return { id, description, behaviors };
  }
}

/**
 * E namespace — evaluation factories.
 *
 * All 16 methods + persona sub-namespace from the Python E namespace.
 */
export class E {
  /** Prebuilt user simulation personas. */
  static readonly persona = new PersonaNamespace();

  // ------------------------------------------------------------------
  // Criteria factories (return EComposite)
  // ------------------------------------------------------------------

  /** Tool trajectory matching criterion. */
  static trajectory(opts?: {
    threshold?: number;
    match?: "exact" | "in_order" | "any_order";
  }): EComposite {
    return new EComposite([
      {
        name: "trajectory",
        config: {
          threshold: opts?.threshold ?? 1.0,
          match: opts?.match ?? "exact",
        },
      },
    ]);
  }

  /** ROUGE-1 response match criterion. */
  static responseMatch(opts?: { threshold?: number }): EComposite {
    return new EComposite([
      {
        name: "response_match",
        config: { threshold: opts?.threshold ?? 0.8 },
      },
    ]);
  }

  /** LLM-as-a-judge semantic matching. */
  static semanticMatch(opts?: { threshold?: number; judgeModel?: string }): EComposite {
    return new EComposite([
      {
        name: "semantic_match",
        config: {
          threshold: opts?.threshold ?? 0.8,
          judgeModel: opts?.judgeModel,
        },
      },
    ]);
  }

  /** Hallucination detection criterion. */
  static hallucination(opts?: {
    threshold?: number;
    judgeModel?: string;
    checkIntermediate?: boolean;
  }): EComposite {
    return new EComposite([
      {
        name: "hallucination",
        config: {
          threshold: opts?.threshold ?? 0.5,
          judgeModel: opts?.judgeModel,
          checkIntermediate: opts?.checkIntermediate ?? false,
        },
      },
    ]);
  }

  /** Safety evaluation criterion. */
  static safety(opts?: { threshold?: number }): EComposite {
    return new EComposite([
      {
        name: "safety",
        config: { threshold: opts?.threshold ?? 1.0 },
      },
    ]);
  }

  /** Rubric-based response quality criterion. */
  static rubric(texts: string[], opts?: { threshold?: number; judgeModel?: string }): EComposite {
    return new EComposite([
      {
        name: "rubric",
        config: {
          texts,
          threshold: opts?.threshold ?? 0.8,
          judgeModel: opts?.judgeModel,
        },
      },
    ]);
  }

  /** Rubric-based tool use quality criterion. */
  static toolRubric(
    texts: string[],
    opts?: { threshold?: number; judgeModel?: string },
  ): EComposite {
    return new EComposite([
      {
        name: "tool_rubric",
        config: {
          texts,
          threshold: opts?.threshold ?? 0.8,
          judgeModel: opts?.judgeModel,
        },
      },
    ]);
  }

  /** User-defined custom metric. */
  static custom(name: string, fn: CallbackFn, opts?: { threshold?: number }): EComposite {
    return new EComposite([
      {
        name,
        config: { fn, threshold: opts?.threshold ?? 1.0 },
      },
    ]);
  }

  // ------------------------------------------------------------------
  // Case & scenario factories
  // ------------------------------------------------------------------

  /** Create a standalone evaluation case. */
  static case_(
    prompt: string,
    opts?: { expect?: string; tools?: unknown[]; rubrics?: string[]; state?: State },
  ): ECase {
    return new ECase(prompt, opts?.expect, opts?.tools, opts?.rubrics, opts?.state);
  }

  /** Create a conversation scenario for user simulation. */
  static scenario(start: string, plan: string[], opts?: { persona?: EPersonaSpec }): EScenario {
    return new EScenario(start, plan, opts?.persona);
  }

  // ------------------------------------------------------------------
  // Suite & comparison factories
  // ------------------------------------------------------------------

  /** Create an evaluation suite for an agent builder. */
  static suite(agent: unknown): EvalSuite {
    return new EvalSuite(agent);
  }

  /** Compare multiple agents on the same eval set. */
  static compare(...agents: unknown[]): ComparisonSuite {
    return new ComparisonSuite(agents);
  }

  // ------------------------------------------------------------------
  // File-based evaluation
  // ------------------------------------------------------------------

  /** Load eval set from a JSON file (placeholder — resolved at runtime). */
  static fromFile(path: string): ECase[] {
    // At runtime, reads and parses the file
    return [new ECase(`[from ${path}]`)];
  }

  /** Load all eval sets from a directory (placeholder — resolved at runtime). */
  static fromDir(path: string): ECase[] {
    // At runtime, reads all JSON files in the directory
    return [new ECase(`[from ${path}]`)];
  }

  // ------------------------------------------------------------------
  // Quality gate
  // ------------------------------------------------------------------

  /** Create a quality gate for pipelines. */
  static gate(criteria: EComposite, opts?: { threshold?: number; outputKey?: string }): EComposite {
    return new EComposite([
      {
        name: "gate",
        config: {
          criteria: criteria.criteria,
          threshold: opts?.threshold ?? 0.8,
          outputKey: opts?.outputKey ?? "eval_result",
        },
      },
    ]);
  }
}
