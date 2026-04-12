/**
 * M — Middleware namespace.
 *
 * Composable middleware for cross-cutting concerns.
 * Compose with .pipe() to stack middleware layers.
 *
 * Usage:
 *   agent.middleware(M.retry({ maxAttempts: 3 }).pipe(M.log()))
 *   agent.middleware(M.cost().pipe(M.latency()).pipe(M.trace()))
 */

import type { CallbackFn, State } from "../core/types.js";

/** Descriptor for a single middleware in the composite. */
export interface MiddlewareSpec {
  name: string;
  config: Record<string, unknown>;
}

/** A composable middleware descriptor. */
export class MComposite {
  constructor(public readonly middlewares: MiddlewareSpec[]) {}

  /** Chain: stack another middleware. */
  pipe(other: MComposite): MComposite {
    return new MComposite([...this.middlewares, ...other.middlewares]);
  }

  /** Convert to a flat middleware array for passing to builder. */
  toArray(): MiddlewareSpec[] {
    return [...this.middlewares];
  }
}

/**
 * M namespace — middleware factories.
 *
 * All 28 methods from the Python M namespace.
 */
export class M {
  // ------------------------------------------------------------------
  // Observability
  // ------------------------------------------------------------------

  /** Retry with exponential backoff. */
  static retry(opts?: { maxAttempts?: number; backoff?: number }): MComposite {
    return new MComposite([
      {
        name: "retry",
        config: { maxAttempts: opts?.maxAttempts ?? 3, backoff: opts?.backoff ?? 2.0 },
      },
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

  /** Topology event logging (loops, fanout, routes, fallbacks, timeouts). */
  static topologyLog(): MComposite {
    return new MComposite([{ name: "topology_log", config: {} }]);
  }

  /** Dispatch/join lifecycle logging. */
  static dispatchLog(): MComposite {
    return new MComposite([{ name: "dispatch_log", config: {} }]);
  }

  // ------------------------------------------------------------------
  // Scoping and conditional
  // ------------------------------------------------------------------

  /** Restrict middleware to specific agents. */
  static scope(agents: string[], mw: MComposite): MComposite {
    return new MComposite([
      {
        name: "scope",
        config: { agents, middleware: mw.middlewares },
      },
    ]);
  }

  /** Conditional middleware. */
  static when(condition: CallbackFn | ((state: State) => boolean), mw: MComposite): MComposite {
    return new MComposite([
      {
        name: "when",
        config: { condition, middleware: mw.middlewares },
      },
    ]);
  }

  // ------------------------------------------------------------------
  // Single-hook middleware
  // ------------------------------------------------------------------

  /** Pre-agent hook. */
  static beforeAgent(fn: CallbackFn): MComposite {
    return new MComposite([{ name: "before_agent", config: { fn } }]);
  }

  /** Post-agent hook. */
  static afterAgent(fn: CallbackFn): MComposite {
    return new MComposite([{ name: "after_agent", config: { fn } }]);
  }

  /** Pre-model hook. */
  static beforeModel(fn: CallbackFn): MComposite {
    return new MComposite([{ name: "before_model", config: { fn } }]);
  }

  /** Post-model hook. */
  static afterModel(fn: CallbackFn): MComposite {
    return new MComposite([{ name: "after_model", config: { fn } }]);
  }

  /** Loop iteration hook. */
  static onLoop(fn: CallbackFn): MComposite {
    return new MComposite([{ name: "on_loop", config: { fn } }]);
  }

  /** Timeout event hook. */
  static onTimeout(fn: CallbackFn): MComposite {
    return new MComposite([{ name: "on_timeout", config: { fn } }]);
  }

  /** Routing event hook. */
  static onRoute(fn: CallbackFn): MComposite {
    return new MComposite([{ name: "on_route", config: { fn } }]);
  }

  /** Fallback event hook. */
  static onFallback(fn: CallbackFn): MComposite {
    return new MComposite([{ name: "on_fallback", config: { fn } }]);
  }

  // ------------------------------------------------------------------
  // Reliability
  // ------------------------------------------------------------------

  /** Circuit breaker: trips open after N consecutive errors. */
  static circuitBreaker(opts?: { threshold?: number; resetAfter?: number }): MComposite {
    return new MComposite([
      {
        name: "circuit_breaker",
        config: {
          threshold: opts?.threshold ?? 5,
          resetAfter: opts?.resetAfter ?? 60,
        },
      },
    ]);
  }

  /** Per-agent execution timeout. */
  static timeout(seconds: number): MComposite {
    return new MComposite([{ name: "timeout", config: { seconds } }]);
  }

  /** Cache LLM responses with TTL. */
  static cache(opts?: { ttl?: number; keyFn?: CallbackFn }): MComposite {
    return new MComposite([
      {
        name: "cache",
        config: { ttl: opts?.ttl ?? 300, keyFn: opts?.keyFn },
      },
    ]);
  }

  /** Auto-downgrade to fallback model on failure. */
  static fallbackModel(model: string): MComposite {
    return new MComposite([{ name: "fallback_model", config: { model } }]);
  }

  /** Suppress duplicate model calls within a sliding window. */
  static dedup(opts?: { window?: number }): MComposite {
    return new MComposite([
      {
        name: "dedup",
        config: { window: opts?.window ?? 60 },
      },
    ]);
  }

  /** Probabilistic middleware: fires inner middleware only N% of the time. */
  static sample(rate: number, mw?: MComposite): MComposite {
    return new MComposite([
      {
        name: "sample",
        config: { rate, middleware: mw?.middlewares },
      },
    ]);
  }

  // ------------------------------------------------------------------
  // Distributed observability
  // ------------------------------------------------------------------

  /** OpenTelemetry span export. */
  static trace(opts?: { exporter?: unknown }): MComposite {
    return new MComposite([
      {
        name: "trace",
        config: { exporter: opts?.exporter },
      },
    ]);
  }

  /** Metrics collection. */
  static metrics(opts?: { collector?: unknown }): MComposite {
    return new MComposite([
      {
        name: "metrics",
        config: { collector: opts?.collector },
      },
    ]);
  }

  // ------------------------------------------------------------------
  // A2A-specific middleware
  // ------------------------------------------------------------------

  /** A2A-specific retry for remote agents. */
  static a2aRetry(opts?: {
    maxAttempts?: number;
    backoff?: number;
    agents?: string[];
    onRetry?: CallbackFn;
  }): MComposite {
    return new MComposite([
      {
        name: "a2a_retry",
        config: {
          maxAttempts: opts?.maxAttempts ?? 3,
          backoff: opts?.backoff ?? 2.0,
          agents: opts?.agents,
          onRetry: opts?.onRetry,
        },
      },
    ]);
  }

  /** Circuit breaker for A2A remote agents. */
  static a2aCircuitBreaker(opts?: {
    threshold?: number;
    resetAfter?: number;
    agents?: string[];
    onOpen?: CallbackFn;
    onClose?: CallbackFn;
  }): MComposite {
    return new MComposite([
      {
        name: "a2a_circuit_breaker",
        config: {
          threshold: opts?.threshold ?? 5,
          resetAfter: opts?.resetAfter ?? 60,
          agents: opts?.agents,
          onOpen: opts?.onOpen,
          onClose: opts?.onClose,
        },
      },
    ]);
  }

  /** Per-delegation timeout for A2A remote agents. */
  static a2aTimeout(opts?: {
    seconds?: number;
    agents?: string[];
    onTimeout?: CallbackFn;
  }): MComposite {
    return new MComposite([
      {
        name: "a2a_timeout",
        config: {
          seconds: opts?.seconds ?? 30,
          agents: opts?.agents,
          onTimeout: opts?.onTimeout,
        },
      },
    ]);
  }

  // ------------------------------------------------------------------
  // A2UI middleware
  // ------------------------------------------------------------------

  /** Log A2UI surface operations. */
  static a2uiLog(opts?: { level?: "info" | "debug" | "trace"; agents?: string[] }): MComposite {
    return new MComposite([
      {
        name: "a2ui_log",
        config: {
          level: opts?.level ?? "info",
          agents: opts?.agents,
        },
      },
    ]);
  }
}
