/**
 * Higher-order composition patterns.
 *
 * Mirrors Python's `adk_fluent._patterns`. Each function takes builders
 * and returns a new builder describing a common multi-agent topology.
 *
 *   reviewLoop, mapReduce, cascade, fanOutMerge, chain, conditional, supervised
 */

import { type BuilderBase } from "../core/builder-base.js";
import type { StatePredicate } from "../core/types.js";
import { Pipeline, FanOut, Loop, Fallback } from "../builders/workflow.js";
import { gate } from "../primitives/index.js";

/**
 * Worker / reviewer loop. The worker produces a draft (writes to
 * ``draft_key``); the reviewer scores it on ``quality_key``. Loops until
 * the score reaches ``target`` or ``maxRounds`` iterations elapse.
 */
export interface ReviewLoopOptions {
  qualityKey?: string;
  draftKey?: string;
  target?: number;
  maxRounds?: number;
  name?: string;
}

export function reviewLoop(
  worker: BuilderBase,
  reviewer: BuilderBase,
  opts: ReviewLoopOptions = {},
): BuilderBase {
  const qualityKey = opts.qualityKey ?? "quality";
  const target = opts.target ?? 0.8;
  const maxRounds = opts.maxRounds ?? 5;
  const name = opts.name ?? "review_loop";

  const loop = new Loop(name)
    .step(worker)
    .step(reviewer)
    .maxIterations(maxRounds)
    .until((s) => Number(s[qualityKey] ?? 0) >= target);

  return loop;
}

/**
 * Map-reduce pattern. ``mapper`` is applied to each item in
 * ``state[itemsKey]``; ``reducer`` aggregates the results into
 * ``state[resultKey]``.
 */
export interface MapReduceOptions {
  itemsKey?: string;
  resultKey?: string;
  name?: string;
}

export function mapReduce(
  mapper: BuilderBase,
  reducer: BuilderBase,
  opts: MapReduceOptions = {},
): BuilderBase {
  const itemsKey = opts.itemsKey ?? "items";
  const resultKey = opts.resultKey ?? "result";
  const name = opts.name ?? "map_reduce";

  return new Pipeline(name)
    .step(mapper)
    .step(reducer)
    .native((obj) => {
      (obj as Record<string, unknown>)._items_key = itemsKey;
      (obj as Record<string, unknown>)._result_key = resultKey;
    });
}

/**
 * Cascade: try ``agents[0]`` first, fall back to ``agents[1]``, then
 * ``agents[2]``, and so on. Equivalent to a Fallback chain.
 */
export function cascade(...agents: BuilderBase[]): BuilderBase {
  if (agents.length === 0) {
    throw new Error("cascade requires at least one agent");
  }
  if (agents.length === 1) {
    return agents[0];
  }
  let chain = new Fallback("cascade", [agents[0], agents[1]]);
  for (const a of agents.slice(2)) {
    chain = chain.attempt(a) as Fallback;
  }
  return chain;
}

/**
 * Fan-out to multiple agents in parallel, then merge the results into a
 * single state key.
 */
export function fanOutMerge(
  agents: BuilderBase[],
  opts: { mergeKey?: string; name?: string } = {},
): BuilderBase {
  const name = opts.name ?? "fan_out_merge";
  const mergeKey = opts.mergeKey ?? "merged";
  const f = new FanOut(name);
  let next: FanOut = f;
  for (const a of agents) {
    next = next.branch(a) as FanOut;
  }
  return next.native((obj) => {
    (obj as Record<string, unknown>)._merge_key = mergeKey;
  });
}

/**
 * Sequential pipeline shorthand. Equivalent to chaining ``.then()``.
 */
export function chain(...agents: BuilderBase[]): BuilderBase {
  if (agents.length === 0) {
    throw new Error("chain requires at least one agent");
  }
  const p = new Pipeline("chain");
  let next: Pipeline = p;
  for (const a of agents) {
    next = next.step(a) as Pipeline;
  }
  return next;
}

/**
 * Conditional execution. Runs ``thenAgent`` when the predicate returns
 * true; runs ``elseAgent`` otherwise. ``elseAgent`` is optional.
 */
export function conditional(
  pred: StatePredicate,
  thenAgent: BuilderBase,
  elseAgent?: BuilderBase,
): BuilderBase {
  if (!elseAgent) {
    return gate(pred, thenAgent, "conditional");
  }
  // Pipeline with both gates
  return new Pipeline("conditional")
    .step(gate(pred, thenAgent, "if"))
    .step(gate((s) => !pred(s), elseAgent, "else"));
}

/**
 * Supervised execution. The supervisor reviews the worker's output and may
 * cause a re-run by writing a falsy ``approved`` flag to state.
 */
export function supervised(
  worker: BuilderBase,
  supervisor: BuilderBase,
  opts: { approvedKey?: string; maxRounds?: number; name?: string } = {},
): BuilderBase {
  const approvedKey = opts.approvedKey ?? "approved";
  const maxRounds = opts.maxRounds ?? 3;
  const name = opts.name ?? "supervised";

  return new Loop(name)
    .step(worker)
    .step(supervisor)
    .maxIterations(maxRounds)
    .until((s) => Boolean(s[approvedKey]));
}
