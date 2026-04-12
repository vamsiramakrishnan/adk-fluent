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

/** Evaluation result wrapper. */
export class EvalReport {
  constructor(
    public readonly passed: boolean,
    public readonly scores: Record<string, number>,
    public readonly details: Record<string, unknown>[],
  ) {}

  /** Overall pass rate. */
  get passRate(): number {
    const values = Object.values(this.scores);
    if (values.length === 0) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
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

/** Fluent evaluation suite builder. */
export class EvalSuite {
  readonly agent: unknown;
  readonly cases: ECase[] = [];
  readonly criteria: EComposite[] = [];

  constructor(agent: unknown) {
    this.agent = agent;
  }

  /** Add an evaluation case. */
  add(testCase: ECase): this {
    this.cases.push(testCase);
    return this;
  }

  /** Add evaluation criteria. */
  withCriteria(criteria: EComposite): this {
    this.criteria.push(criteria);
    return this;
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
    return new EComposite([{
      name: "trajectory",
      config: {
        threshold: opts?.threshold ?? 1.0,
        match: opts?.match ?? "exact",
      },
    }]);
  }

  /** ROUGE-1 response match criterion. */
  static responseMatch(opts?: { threshold?: number }): EComposite {
    return new EComposite([{
      name: "response_match",
      config: { threshold: opts?.threshold ?? 0.8 },
    }]);
  }

  /** LLM-as-a-judge semantic matching. */
  static semanticMatch(opts?: {
    threshold?: number;
    judgeModel?: string;
  }): EComposite {
    return new EComposite([{
      name: "semantic_match",
      config: {
        threshold: opts?.threshold ?? 0.8,
        judgeModel: opts?.judgeModel,
      },
    }]);
  }

  /** Hallucination detection criterion. */
  static hallucination(opts?: {
    threshold?: number;
    judgeModel?: string;
    checkIntermediate?: boolean;
  }): EComposite {
    return new EComposite([{
      name: "hallucination",
      config: {
        threshold: opts?.threshold ?? 0.5,
        judgeModel: opts?.judgeModel,
        checkIntermediate: opts?.checkIntermediate ?? false,
      },
    }]);
  }

  /** Safety evaluation criterion. */
  static safety(opts?: { threshold?: number }): EComposite {
    return new EComposite([{
      name: "safety",
      config: { threshold: opts?.threshold ?? 1.0 },
    }]);
  }

  /** Rubric-based response quality criterion. */
  static rubric(
    texts: string[],
    opts?: { threshold?: number; judgeModel?: string },
  ): EComposite {
    return new EComposite([{
      name: "rubric",
      config: {
        texts,
        threshold: opts?.threshold ?? 0.8,
        judgeModel: opts?.judgeModel,
      },
    }]);
  }

  /** Rubric-based tool use quality criterion. */
  static toolRubric(
    texts: string[],
    opts?: { threshold?: number; judgeModel?: string },
  ): EComposite {
    return new EComposite([{
      name: "tool_rubric",
      config: {
        texts,
        threshold: opts?.threshold ?? 0.8,
        judgeModel: opts?.judgeModel,
      },
    }]);
  }

  /** User-defined custom metric. */
  static custom(
    name: string,
    fn: CallbackFn,
    opts?: { threshold?: number },
  ): EComposite {
    return new EComposite([{
      name,
      config: { fn, threshold: opts?.threshold ?? 1.0 },
    }]);
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
  static scenario(
    start: string,
    plan: string[],
    opts?: { persona?: EPersonaSpec },
  ): EScenario {
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
  static gate(
    criteria: EComposite,
    opts?: { threshold?: number; outputKey?: string },
  ): EComposite {
    return new EComposite([{
      name: "gate",
      config: {
        criteria: criteria.criteria,
        threshold: opts?.threshold ?? 0.8,
        outputKey: opts?.outputKey ?? "eval_result",
      },
    }]);
  }
}
