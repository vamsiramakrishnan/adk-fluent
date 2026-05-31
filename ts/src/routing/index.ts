/**
 * Deterministic state-based routing.
 *
 * Mirrors Python's `Route` class. Use when the next step is decided by a
 * rule rather than by the LLM.
 *
 *   const router = new Route("tier")
 *     .eq("VIP", vipAgent)
 *     .contains("trial", trialAgent)
 *     .otherwise(defaultAgent);
 */

import { BuilderBase } from "../core/builder-base.js";
import type { State, StatePredicate } from "../core/types.js";
import type { CostTable } from "../namespaces/harness/usage.js";

interface Branch {
  predicate: StatePredicate;
  agent: BuilderBase | unknown;
  label: string;
}

/**
 * Reference token counts used to compare model costs deterministically.
 * Cost routing ranks candidate models, not absolute spend, so any fixed
 * probe size yields the same ordering. 1k in / 1k out is a neutral default.
 */
const PROBE_INPUT_TOKENS = 1_000;
const PROBE_OUTPUT_TOKENS = 1_000;

/**
 * Best-effort extraction of an agent's model name.
 *
 * Works for fluent builders (model lives in the builder config, surfaced by
 * `inspect()`) and for already-built native agents (a plain `.model`
 * property). Returns `undefined` when no model can be determined or the
 * model is not a plain string.
 */
function modelOf(agentOrBuilder: unknown): string | undefined {
  let model: unknown;
  if (agentOrBuilder instanceof BuilderBase) {
    model = agentOrBuilder.inspect().model;
  } else if (agentOrBuilder && typeof agentOrBuilder === "object" && "model" in agentOrBuilder) {
    model = (agentOrBuilder as { model: unknown }).model;
  }
  return typeof model === "string" ? model : undefined;
}

/**
 * Whether `costTable` carries a meaningful wildcard / flat default rate.
 *
 * The TS `CostTable` always exposes a `defaultRate`; a zero/zero default is
 * the "no wildcard" sentinel (mirrors Python's missing `"*"` entry). A flat
 * table (non-zero default) makes every model effectively known.
 */
function hasWildcardDefault(costTable: CostTable): boolean {
  const d = costTable.defaultRate;
  return d.inputPerMillion !== 0 || d.outputPerMillion !== 0;
}

/**
 * Estimate the per-call USD cost of `model` under `costTable`.
 *
 * An unknown model — one with no explicit entry and no wildcard/flat default
 * — costs `+Infinity` so it is never auto-selected when a known option
 * exists. Uses a fixed probe token count; only the relative ordering matters.
 */
function estimateCost(costTable: CostTable | undefined, model: string | undefined): number {
  if (costTable === undefined || model === undefined) {
    return Number.POSITIVE_INFINITY;
  }
  if (!costTable.rates.has(model) && !hasWildcardDefault(costTable)) {
    return Number.POSITIVE_INFINITY;
  }
  return costTable.cost(model, PROBE_INPUT_TOKENS, PROBE_OUTPUT_TOKENS);
}

export class Route extends BuilderBase<Record<string, unknown>> {
  private _key: string;
  private _branches: Branch[] = [];
  private _default: BuilderBase | unknown | null = null;

  constructor(key: string, name?: string) {
    super(name ?? `route_${key}`);
    this._key = key;
    this._config.set("_route_key", key);
  }

  /**
   * Begin a cost-aware route over candidate agents.
   *
   * Returns a {@link CostRoute} that selects among candidate agents by the
   * estimated per-call USD cost of each agent's model, using `costTable` (a
   * {@link CostTable}). The selection is deterministic and side-effect free:
   * model rates are known at build time, so `.cheapest(...)` resolves to a
   * single chosen agent with no LLM call.
   *
   * When `costTable` is omitted, every candidate model is treated as unknown
   * (`+Infinity` cost) and the first candidate is used as a tie-break.
   *
   * @example
   *   Route.byCost(costTable).cheapest(flashAgent, proAgent);
   */
  static byCost(costTable?: CostTable): CostRoute {
    return new CostRoute(costTable);
  }

  protected override _clone(): this {
    const clone = super._clone();
    (clone as Route)._key = this._key;
    (clone as Route)._branches = [...this._branches];
    (clone as Route)._default = this._default;
    return clone;
  }

  private _addBranch(predicate: StatePredicate, agent: BuilderBase | unknown, label: string): this {
    const next = this._clone();
    next._branches.push({ predicate, agent, label });
    return next;
  }

  /** Match when state[key] === value (strict equality). */
  eq(value: unknown, agent: BuilderBase | unknown): this {
    return this._addBranch((s: State) => s[this._key] === value, agent, `eq:${String(value)}`);
  }

  /** Match when state[key] !== value. */
  ne(value: unknown, agent: BuilderBase | unknown): this {
    return this._addBranch((s: State) => s[this._key] !== value, agent, `ne:${String(value)}`);
  }

  /** Match when String(state[key]).includes(sub). */
  contains(sub: string, agent: BuilderBase | unknown): this {
    return this._addBranch(
      (s: State) => typeof s[this._key] === "string" && (s[this._key] as string).includes(sub),
      agent,
      `contains:${sub}`,
    );
  }

  /** Match when state[key] > n (numeric). */
  gt(n: number, agent: BuilderBase | unknown): this {
    return this._addBranch((s: State) => Number(s[this._key]) > n, agent, `gt:${n}`);
  }

  /** Match when state[key] < n (numeric). */
  lt(n: number, agent: BuilderBase | unknown): this {
    return this._addBranch((s: State) => Number(s[this._key]) < n, agent, `lt:${n}`);
  }

  /** Match when state[key] >= n. */
  gte(n: number, agent: BuilderBase | unknown): this {
    return this._addBranch((s: State) => Number(s[this._key]) >= n, agent, `gte:${n}`);
  }

  /** Match when state[key] <= n. */
  lte(n: number, agent: BuilderBase | unknown): this {
    return this._addBranch((s: State) => Number(s[this._key]) <= n, agent, `lte:${n}`);
  }

  /** Custom predicate branch. */
  when(pred: StatePredicate, agent: BuilderBase | unknown): this {
    return this._addBranch(pred, agent, "when");
  }

  /** Default fallback. */
  otherwise(agent: BuilderBase | unknown): this {
    const next = this._clone();
    next._default = agent;
    return next;
  }

  build(): Record<string, unknown> {
    return {
      _type: "Route",
      name: this._config.get("name"),
      key: this._key,
      branches: this._branches.map((b) => ({
        label: b.label,
        predicate: b.predicate,
        agent: b.agent instanceof BuilderBase ? b.agent.build() : b.agent,
      })),
      default: this._default instanceof BuilderBase ? this._default.build() : this._default,
    };
  }
}

/**
 * Cost-aware selection among candidate agents.
 *
 * Created via {@link Route.byCost}. Picks a single agent based on the
 * estimated per-call USD cost of its model under a {@link CostTable}. Because
 * model rates are known at build time, the choice is fully deterministic and
 * involves no LLM call — consistent with the deterministic-routing philosophy
 * of {@link Route}.
 *
 * @example
 *   // Pick the cheapest model that can do the job.
 *   const chosen = Route.byCost(costTable).cheapest(flashAgent, proAgent);
 *
 * Resolution rules:
 *   - Each candidate's model is read from its builder config (via
 *     `inspect().model`) or, for built agents, the `.model` property.
 *   - A model unknown to the cost table (no entry and no wildcard/flat
 *     default) is treated as `+Infinity` cost and never auto-chosen when a
 *     known cheaper option exists.
 *   - Ties (including all-unknown candidates) break by declaration order —
 *     the first candidate wins.
 */
export class CostRoute {
  private readonly _costTable?: CostTable;

  constructor(costTable?: CostTable) {
    this._costTable = costTable;
  }

  /**
   * Return the candidate whose model has the lowest estimated cost.
   *
   * @param candidates One or more agent builders (or built agents) to choose
   *   between.
   * @returns The single cheapest candidate (unchanged), ready to drop into a
   *   pipeline, `.then()` chain, or `Route.otherwise(...)`.
   * @throws If no candidates are supplied.
   */
  cheapest<T>(...candidates: T[]): T {
    if (candidates.length === 0) {
      throw new Error("Route.byCost(...).cheapest() requires at least one candidate.");
    }
    let best = candidates[0];
    let bestCost = estimateCost(this._costTable, modelOf(best));
    for (const candidate of candidates.slice(1)) {
      const cost = estimateCost(this._costTable, modelOf(candidate));
      if (cost < bestCost) {
        best = candidate;
        bestCost = cost;
      }
    }
    return best;
  }

  /**
   * Return the candidate whose model has the highest *finite* cost.
   *
   * Symmetric counterpart to {@link cheapest} for callers who want to
   * deliberately escalate to the strongest known model. Candidates with
   * unknown models (`+Infinity` cost) are skipped; if every candidate is
   * unknown the first one is returned. Ties break by declaration order.
   *
   * @throws If no candidates are supplied.
   */
  costliest<T>(...candidates: T[]): T {
    if (candidates.length === 0) {
      throw new Error("Route.byCost(...).costliest() requires at least one candidate.");
    }
    let best = candidates[0];
    let bestCost = estimateCost(this._costTable, modelOf(best));
    let bestFinite = Number.isFinite(bestCost);
    for (const candidate of candidates.slice(1)) {
      const cost = estimateCost(this._costTable, modelOf(candidate));
      const finite = Number.isFinite(cost);
      // Prefer finite over infinite; among same finiteness, prefer higher cost.
      if ((finite && !bestFinite) || (finite && bestFinite && cost > bestCost)) {
        best = candidate;
        bestCost = cost;
        bestFinite = finite;
      }
    }
    return best;
  }
}
