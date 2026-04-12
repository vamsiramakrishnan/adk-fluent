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

interface Branch {
  predicate: StatePredicate;
  agent: BuilderBase | unknown;
  label: string;
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
