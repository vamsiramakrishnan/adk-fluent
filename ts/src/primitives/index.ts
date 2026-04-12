/**
 * Expression primitives — function-level building blocks for fluent
 * composition.
 *
 * Mirrors Python's primitives in `adk_fluent._primitives`:
 *   tap, expect, mapOver, gate, race, dispatch, join.
 *
 * These primitives produce zero-cost (no LLM) builder steps that can be
 * inserted anywhere in a Pipeline / FanOut / Loop / Fallback chain via
 * `.then()` or by passing them to `.step()` / `.branch()`.
 */

import { BuilderBase } from "../core/builder-base.js";
import type { State, StatePredicate } from "../core/types.js";

/**
 * Lightweight, hand-rolled primitive class. Each primitive is a tiny
 * BuilderBase subclass that records its kind in `_config["_kind"]` so the
 * runtime layer can dispatch on it.
 *
 * Factory helpers below call `Primitive.create()` to populate private
 * config / list fields up-front instead of poking at protected maps with
 * bracket notation.
 */
export class Primitive extends BuilderBase<Record<string, unknown>> {
  constructor(name: string, kind: string) {
    super(name);
    this._config.set("_kind", kind);
  }

  /**
   * Construct a Primitive with private payload baked in. Used by the
   * factory helpers (`tap`, `gate`, `mapOver`, ...) so they can stay free
   * of bracket-notation access into protected fields.
   */
  static create(
    name: string,
    kind: string,
    config: Record<string, unknown> = {},
    lists: Record<string, unknown[]> = {},
  ): Primitive {
    const p = new Primitive(name, kind);
    for (const [k, v] of Object.entries(config)) {
      p._config.set(k, v);
    }
    for (const [k, v] of Object.entries(lists)) {
      p._lists.set(k, v);
    }
    return p;
  }

  build(): Record<string, unknown> {
    // Primitives expose their underscore-prefixed config so the runtime
    // dispatcher can pick them up. The default ``_buildConfig`` skips
    // private keys, so we copy them out manually.
    const result: Record<string, unknown> = { _type: "Primitive" };
    for (const [k, v] of this._config) {
      result[k] = v;
    }
    for (const [k, v] of this._lists) {
      if (v.length === 0) continue;
      result[k] = v.map((item) => (item instanceof BuilderBase ? item.build() : item));
    }
    return result;
  }
}

/**
 * Inline observer step (no LLM, zero cost). Reads state, runs `fn` for its
 * side effects (logging, metrics, breakpoint), never mutates state.
 *
 *   pipeline.then(tap((s) => console.log("midpoint", s)))
 */
export function tap(fn: (state: State) => void, name = "tap"): Primitive {
  return Primitive.create(name, "tap", { _fn: fn });
}

/**
 * Inline state assertion. Throws if `pred(state)` is false. Unlike `tap`,
 * this is a contract check rather than a side-effect observer.
 */
export function expect(pred: StatePredicate, msg = "Assertion failed", name = "expect"): Primitive {
  return Primitive.create(name, "expect", { _pred: pred, _msg: msg });
}

/**
 * Map an agent over the items in `state[key]`. Returns a new list of
 * results in `state[key + "_results"]`.
 */
export function mapOver(key: string, agent: BuilderBase, name?: string): Primitive {
  return Primitive.create(
    name ?? `map_over_${key}`,
    "map_over",
    { _key: key },
    { _agents: [agent] },
  );
}

/**
 * Conditional execution: skip the wrapped agent unless `pred(state)`
 * returns true.
 */
export function gate(pred: StatePredicate, agent: BuilderBase, name?: string): Primitive {
  return Primitive.create(name ?? "gate", "gate", { _pred: pred }, { _agents: [agent] });
}

/**
 * First-to-complete wins. Runs all agents concurrently and returns the
 * result of the first one to finish.
 */
export function race(...agents: BuilderBase[]): Primitive {
  return Primitive.create("race", "race", {}, { _agents: agents });
}

/**
 * Fire-and-forget background task. Launches the agent without blocking the
 * pipeline; an optional `onComplete` callback fires when it finishes.
 */
export interface DispatchOptions {
  name?: string;
  onComplete?: (result: unknown) => void;
}

export function dispatch(agent: BuilderBase, opts: DispatchOptions = {}): Primitive {
  const config: Record<string, unknown> = {};
  if (opts.onComplete) config._on_complete = opts.onComplete;
  return Primitive.create(opts.name ?? "dispatch", "dispatch", config, { _agents: [agent] });
}

/**
 * Wait for all background tasks (launched via `dispatch`) to complete
 * before continuing the pipeline.
 */
export function join(name = "join"): Primitive {
  return new Primitive(name, "join");
}
