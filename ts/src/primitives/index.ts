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
 */
export class Primitive extends BuilderBase<Record<string, unknown>> {
  constructor(name: string, kind: string) {
    super(name);
    this._config.set("_kind", kind);
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
  const p = new Primitive(name, "tap");
  p["_config"].set("_fn", fn);
  return p;
}

/**
 * Inline state assertion. Throws if `pred(state)` is false. Unlike `tap`,
 * this is a contract check rather than a side-effect observer.
 */
export function expect(
  pred: StatePredicate,
  msg = "Assertion failed",
  name = "expect",
): Primitive {
  const p = new Primitive(name, "expect");
  p["_config"].set("_pred", pred);
  p["_config"].set("_msg", msg);
  return p;
}

/**
 * Map an agent over the items in `state[key]`. Returns a new list of
 * results in `state[key + "_results"]`.
 */
export function mapOver(key: string, agent: BuilderBase, name?: string): Primitive {
  const p = new Primitive(name ?? `map_over_${key}`, "map_over");
  p["_config"].set("_key", key);
  p["_lists"].set("_agents", [agent]);
  return p;
}

/**
 * Conditional execution: skip the wrapped agent unless `pred(state)`
 * returns true.
 */
export function gate(
  pred: StatePredicate,
  agent: BuilderBase,
  name?: string,
): Primitive {
  const p = new Primitive(name ?? "gate", "gate");
  p["_config"].set("_pred", pred);
  p["_lists"].set("_agents", [agent]);
  return p;
}

/**
 * First-to-complete wins. Runs all agents concurrently and returns the
 * result of the first one to finish.
 */
export function race(...agents: BuilderBase[]): Primitive {
  const p = new Primitive("race", "race");
  p["_lists"].set("_agents", agents);
  return p;
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
  const p = new Primitive(opts.name ?? "dispatch", "dispatch");
  p["_lists"].set("_agents", [agent]);
  if (opts.onComplete) p["_config"].set("_on_complete", opts.onComplete);
  return p;
}

/**
 * Wait for all background tasks (launched via `dispatch`) to complete
 * before continuing the pipeline.
 */
export function join(name = "join"): Primitive {
  return new Primitive(name, "join");
}
