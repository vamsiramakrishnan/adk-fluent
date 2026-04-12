/**
 * Error recovery strategy — pure data describing what to do when a tool
 * call fails. Mirrors `python/src/adk_fluent/_harness/_error_strategy.py`.
 */

import { toSet } from "./types.js";

export type ErrorAction = "retry" | "skip" | "ask" | "propagate";

export interface ErrorStrategyOptions {
  retry?: Iterable<string>;
  skip?: Iterable<string>;
  ask?: Iterable<string>;
  fallbackMessage?: string;
}

export class ErrorStrategy {
  readonly retry: ReadonlySet<string>;
  readonly skip: ReadonlySet<string>;
  readonly ask: ReadonlySet<string>;
  readonly fallbackMessage: string;

  constructor(opts: ErrorStrategyOptions = {}) {
    this.retry = toSet(opts.retry);
    this.skip = toSet(opts.skip);
    this.ask = toSet(opts.ask);
    this.fallbackMessage = opts.fallbackMessage ?? "Tool call failed and was skipped.";
  }

  decide(toolName: string): ErrorAction {
    if (this.retry.has(toolName)) return "retry";
    if (this.skip.has(toolName)) return "skip";
    if (this.ask.has(toolName)) return "ask";
    return "propagate";
  }
}
