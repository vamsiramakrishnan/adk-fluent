/**
 * Core type definitions for adk-fluent-ts.
 *
 * These types provide the foundation for type-safe builder composition.
 */

/**
 * Generic state bag used for inter-agent data flow.
 */
export type State = Record<string, unknown>;

/**
 * A predicate over agent state.
 */
export type StatePredicate = (state: State) => boolean;

/**
 * A state transform function.
 */
export type StateTransform = (state: State) => State;

/**
 * A callback function (before/after agent/model/tool).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type CallbackFn = (...args: any[]) => any;

/**
 * A tool function that can be registered with an agent.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ToolFn = (...args: any[]) => any;

/**
 * Sentinel value for "not set" — distinct from undefined/null.
 */
const _UNSET_SYMBOL = Symbol("UNSET");
export type Unset = typeof _UNSET_SYMBOL;
export const UNSET: Unset = _UNSET_SYMBOL;

/**
 * Configuration for an UntilSpec (conditional loop).
 */
export interface UntilSpec {
  predicate: StatePredicate;
  max: number;
}

/**
 * Create an until() spec for conditional loops.
 *
 * Usage: `agent.timesUntil(until(pred, 5))`
 * Or: `agent.timesUntil(pred, { max: 5 })`
 */
export function until(predicate: StatePredicate, max = 10): UntilSpec {
  return { predicate, max };
}
