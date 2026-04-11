/**
 * M — Middleware namespace.
 *
 * Composable middleware for cross-cutting concerns.
 *
 * Usage:
 *   agent.middleware(M.retry({ maxAttempts: 3 }).pipe(M.log()))
 */

import type { CallbackFn } from "../core/types.js";

/** A composable middleware descriptor. */
export class MComposite {
  constructor(public readonly middlewares: MiddlewareSpec[]) {}

  /** Chain: stack another middleware. */
  pipe(other: MComposite): MComposite {
    return new MComposite([...this.middlewares, ...other.middlewares]);
  }
}

interface MiddlewareSpec {
  name: string;
  config: Record<string, unknown>;
}

/**
 * M namespace — middleware factories.
 */
export class M {
  /** Retry with exponential backoff. */
  static retry(opts?: { maxAttempts?: number; backoff?: number }): MComposite {
    return new MComposite([
      { name: "retry", config: { maxAttempts: opts?.maxAttempts ?? 3, backoff: opts?.backoff ?? 2.0 } },
    ]);
  }

  /** Structured event logging. */
  static log(): MComposite {
    return new MComposite([{ name: "log", config: {} }]);
  }

  /** Token usage tracking. */
  static cost(): MComposite {
    return new MComposite([{ name: "cost", config: {} }]);
  }

  /** Per-agent latency tracking. */
  static latency(): MComposite {
    return new MComposite([{ name: "latency", config: {} }]);
  }

  /** Restrict middleware to specific agents. */
  static scope(agents: string[], mw: MComposite): MComposite {
    return new MComposite([
      { name: "scope", config: { agents, middleware: mw.middlewares } },
    ]);
  }

  /** Conditional middleware. */
  static when(condition: CallbackFn, mw: MComposite): MComposite {
    return new MComposite([
      { name: "when", config: { condition, middleware: mw.middlewares } },
    ]);
  }

  /** Circuit breaker pattern. */
  static circuitBreaker(opts?: { maxFails?: number; resetAfter?: number }): MComposite {
    return new MComposite([
      {
        name: "circuit_breaker",
        config: { maxFails: opts?.maxFails ?? 5, resetAfter: opts?.resetAfter ?? 60 },
      },
    ]);
  }

  /** Per-agent timeout. */
  static timeout(seconds: number): MComposite {
    return new MComposite([{ name: "timeout", config: { seconds } }]);
  }

  /** Response caching. */
  static cache(opts?: { ttl?: number }): MComposite {
    return new MComposite([{ name: "cache", config: { ttl: opts?.ttl ?? 300 } }]);
  }

  /** Fallback to different model. */
  static fallbackModel(model: string): MComposite {
    return new MComposite([{ name: "fallback_model", config: { model } }]);
  }
}
