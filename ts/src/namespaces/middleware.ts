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

import { createRequire } from "node:module";

import type { CallbackFn, State } from "../core/types.js";

/**
 * CommonJS-style ``require`` bound to this ESM module's URL.
 *
 * ``@opentelemetry/api`` ships as CommonJS; loading it from an ESM module via
 * a dynamic ``import()`` would force every otel resolution to be async. The
 * tracer/meter must be resolved synchronously at middleware construction, so
 * we use ``createRequire`` to load the optional dependency on demand. A
 * missing module throws ``MODULE_NOT_FOUND`` which we catch to fall back to
 * the graceful no-op path — importing adk-fluent-ts never requires otel.
 */
const _require = createRequire(import.meta.url);

/**
 * Runtime hooks a middleware spec may carry.
 *
 * Mirrors the agent/model lifecycle hooks of the Python ``Middleware``
 * protocol (``before_agent`` / ``after_agent`` / ``before_model`` /
 * ``after_model`` / ``on_model_error``). A middleware runtime — or a test —
 * invokes these directly with a lightweight context. All hooks are optional
 * and async; ``ctx`` is an opaque per-invocation bag (see ``MiddlewareHookCtx``).
 */
export interface MiddlewareHooks {
  beforeAgent?(ctx: MiddlewareHookCtx, agentName: string): Promise<void>;
  afterAgent?(ctx: MiddlewareHookCtx, agentName: string): Promise<void>;
  beforeModel?(ctx: MiddlewareHookCtx, request: unknown): Promise<void>;
  afterModel?(ctx: MiddlewareHookCtx, response: unknown): Promise<void>;
  onModelError?(ctx: MiddlewareHookCtx, request: unknown, error: unknown): Promise<void>;
}

/**
 * Per-invocation context passed to middleware hooks.
 *
 * The runtime supplies the active ``agentName`` so model-boundary hooks
 * (which receive a request/response rather than a name) can attribute spans
 * and metrics to the owning agent — matching the Python
 * ``TraceMiddleware._ctx_agent_name`` resolution.
 */
export interface MiddlewareHookCtx {
  agentName?: string;
  [key: string]: unknown;
}

/** Descriptor for a single middleware in the composite. */
export interface MiddlewareSpec {
  name: string;
  config: Record<string, unknown>;
  /**
   * Optional runtime behavior attached to this spec. For most middleware the
   * ``{name, config}`` pair is a declarative descriptor compiled elsewhere;
   * for observability middleware (``trace`` / ``metrics``) the real
   * OpenTelemetry wiring is attached here so a runtime/test can drive the
   * agent + model lifecycle hooks directly.
   */
  hooks?: MiddlewareHooks;
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

  /**
   * OpenTelemetry span export.
   *
   * When ``@opentelemetry/api`` is importable, every agent invocation and
   * every model call is wrapped in a span via ``trace.getTracer("adk-fluent")``:
   *
   * - ``agent:{name}`` spans (beforeAgent → afterAgent) with attributes
   *   ``adk.agent.name`` and ``adk.agent.latency_ms``.
   * - ``model:{agent}`` spans (beforeModel → afterModel) with attributes
   *   ``adk.agent.name``, ``adk.model.name`` (when available),
   *   ``adk.model.latency_ms``, ``adk.model.input_tokens`` and
   *   ``adk.model.output_tokens`` (from ``response.usageMetadata``). Model
   *   errors are recorded on the span and the status set to ERROR.
   *
   * When OpenTelemetry is not installed this degrades to a graceful no-op
   * that emits a one-time process-level warning explaining how to enable it.
   * The import is lazy, so importing the package never requires otel.
   *
   * A custom ``tracer`` may be injected for advanced wiring/testing.
   */
  static trace(opts?: { exporter?: unknown; tracer?: unknown }): MComposite {
    return new MComposite([
      {
        name: "trace",
        config: { exporter: opts?.exporter },
        hooks: new TraceMiddleware(opts?.tracer),
      },
    ]);
  }

  /**
   * Metrics collection via OpenTelemetry.
   *
   * When ``@opentelemetry/api`` is importable, records via
   * ``metrics.getMeter("adk-fluent")``:
   *
   * - ``adk.agent.calls`` (counter) — per afterAgent, tagged ``agent``.
   * - ``adk.agent.latency`` (histogram, ms) — per agent invocation.
   * - ``adk.model.input_tokens`` / ``adk.model.output_tokens`` (counters) —
   *   from ``response.usageMetadata`` per model call.
   * - ``adk.agent.errors`` (counter) — per onModelError.
   *
   * Graceful no-op + one-time warning when otel is absent. A custom ``meter``
   * may be injected for advanced wiring/testing.
   */
  static metrics(opts?: { collector?: unknown; meter?: unknown }): MComposite {
    return new MComposite([
      {
        name: "metrics",
        config: { collector: opts?.collector },
        hooks: new MetricsMiddleware(opts?.meter),
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

// ====================================================================
// OpenTelemetry wiring (Feature #12 parity with Python middleware.py)
// ====================================================================

/**
 * Minimal structural types for the OpenTelemetry surface we use. Kept local
 * so the package has no hard dependency on ``@opentelemetry/api`` types — the
 * import is dynamic and entirely optional.
 */
interface OtelSpan {
  setAttribute(key: string, value: unknown): void;
  setStatus(status: { code: number; message?: string }): void;
  recordException(error: unknown): void;
  end(): void;
}
interface OtelTracer {
  startSpan(name: string): OtelSpan;
}
interface OtelCounter {
  add(value: number, attributes?: Record<string, unknown>): void;
}
interface OtelHistogram {
  record(value: number, attributes?: Record<string, unknown>): void;
}
interface OtelMeter {
  createCounter(name: string, options?: Record<string, unknown>): OtelCounter;
  createHistogram(name: string, options?: Record<string, unknown>): OtelHistogram;
}

/** OpenTelemetry ``SpanStatusCode.ERROR`` — hard-coded to avoid importing the enum. */
const OTEL_STATUS_ERROR = 2;

/**
 * Module-level latch so the "opentelemetry not installed" guidance is emitted
 * exactly once per process no matter how many M.trace()/M.metrics() instances
 * are created. Mirrors the Python ``_OTEL_WARNED`` latch.
 */
let _otelWarned = false;
const OTEL_INSTALL_HINT =
  "opentelemetry is not installed — M.trace()/M.metrics() are no-ops and " +
  "emit no spans or metrics. Enable real OpenTelemetry export with: " +
  "npm install @opentelemetry/api @opentelemetry/sdk-trace-base @opentelemetry/sdk-metrics";

/** Emit the install guidance exactly once per process. */
function warnOtelMissing(): void {
  if (_otelWarned) {
    return;
  }
  _otelWarned = true;
  console.warn(OTEL_INSTALL_HINT);
}

/** Test-only reset of the one-time warning latch. */
export function _resetOtelWarning(): void {
  _otelWarned = false;
}

/**
 * Lazily resolve the global tracer from ``@opentelemetry/api``.
 *
 * Uses ``require`` so resolution is synchronous (hooks are async, but the
 * tracer is needed at construction time) and so a missing module simply
 * throws and is caught — importing adk-fluent-ts never requires otel.
 * Returns ``null`` (and warns once) when the API is unavailable.
 */
function resolveTracer(): OtelTracer | null {
  try {
    const api = _require("@opentelemetry/api") as {
      trace?: { getTracer(name: string): OtelTracer };
    };
    if (api?.trace?.getTracer) {
      return api.trace.getTracer("adk-fluent");
    }
  } catch {
    // module not installed — fall through to the no-op + warning path.
  }
  warnOtelMissing();
  return null;
}

/** Lazily resolve the global meter from ``@opentelemetry/api`` (see resolveTracer). */
function resolveMeter(): OtelMeter | null {
  try {
    const api = _require("@opentelemetry/api") as {
      metrics?: { getMeter(name: string): OtelMeter };
    };
    if (api?.metrics?.getMeter) {
      return api.metrics.getMeter("adk-fluent");
    }
  } catch {
    // module not installed — fall through to the no-op + warning path.
  }
  warnOtelMissing();
  return null;
}

/** Best-effort extraction of the model name from an llm request. */
function modelNameFromRequest(request: unknown): string | undefined {
  const model = (request as { model?: unknown })?.model;
  if (typeof model === "string") {
    return model;
  }
  const inner = (model as { model?: unknown })?.model;
  if (typeof inner === "string") {
    return inner;
  }
  return undefined;
}

/** Return ``[inputTokens, outputTokens]`` from a response, 0 when absent. */
function usageTokens(response: unknown): [number, number] {
  const usage =
    (response as { usageMetadata?: Record<string, unknown> })?.usageMetadata ??
    (response as { usage_metadata?: Record<string, unknown> })?.usage_metadata;
  if (!usage) {
    return [0, 0];
  }
  const inTok = (usage.promptTokenCount ?? usage.prompt_token_count ?? 0) as number;
  const outTok = (usage.candidatesTokenCount ?? usage.candidates_token_count ?? 0) as number;
  return [Number(inTok) || 0, Number(outTok) || 0];
}

function ctxAgentName(ctx: MiddlewareHookCtx): string {
  return ctx?.agentName ?? "unknown";
}

/**
 * OpenTelemetry span export for agent and model boundaries.
 *
 * Implements {@link MiddlewareHooks}. When a tracer is available (injected or
 * resolved from the global provider) each agent invocation and model call is
 * wrapped in a span. When otel is absent every hook is a graceful no-op.
 */
export class TraceMiddleware implements MiddlewareHooks {
  private readonly tracer: OtelTracer | null;
  private readonly agentSpans = new Map<string, OtelSpan>();
  private readonly agentStarted = new Map<string, number>();
  private readonly modelSpans = new Map<string, OtelSpan>();
  private readonly modelStarted = new Map<string, number>();

  constructor(tracer?: unknown) {
    this.tracer = (tracer as OtelTracer | undefined) ?? resolveTracer();
  }

  async beforeAgent(_ctx: MiddlewareHookCtx, agentName: string): Promise<void> {
    if (!this.tracer) {
      return;
    }
    const span = this.tracer.startSpan(`agent:${agentName}`);
    span.setAttribute("adk.agent.name", agentName);
    this.agentSpans.set(agentName, span);
    this.agentStarted.set(agentName, Date.now());
  }

  async afterAgent(_ctx: MiddlewareHookCtx, agentName: string): Promise<void> {
    const span = this.agentSpans.get(agentName);
    this.agentSpans.delete(agentName);
    const started = this.agentStarted.get(agentName);
    this.agentStarted.delete(agentName);
    if (span) {
      if (started !== undefined) {
        span.setAttribute("adk.agent.latency_ms", Date.now() - started);
      }
      span.end();
    }
  }

  async beforeModel(ctx: MiddlewareHookCtx, request: unknown): Promise<void> {
    if (!this.tracer) {
      return;
    }
    const agentName = ctxAgentName(ctx);
    const span = this.tracer.startSpan(`model:${agentName}`);
    span.setAttribute("adk.agent.name", agentName);
    const model = modelNameFromRequest(request);
    if (model) {
      span.setAttribute("adk.model.name", model);
    }
    this.modelSpans.set(agentName, span);
    this.modelStarted.set(agentName, Date.now());
  }

  async afterModel(ctx: MiddlewareHookCtx, response: unknown): Promise<void> {
    const agentName = ctxAgentName(ctx);
    const span = this.modelSpans.get(agentName);
    this.modelSpans.delete(agentName);
    const started = this.modelStarted.get(agentName);
    this.modelStarted.delete(agentName);
    if (span) {
      if (started !== undefined) {
        span.setAttribute("adk.model.latency_ms", Date.now() - started);
      }
      const [inTok, outTok] = usageTokens(response);
      span.setAttribute("adk.model.input_tokens", inTok);
      span.setAttribute("adk.model.output_tokens", outTok);
      span.end();
    }
  }

  async onModelError(ctx: MiddlewareHookCtx, _request: unknown, error: unknown): Promise<void> {
    const agentName = ctxAgentName(ctx);
    const span = this.modelSpans.get(agentName);
    this.modelSpans.delete(agentName);
    this.modelStarted.delete(agentName);
    if (span) {
      try {
        span.recordException(error);
      } catch {
        // recordException is best-effort.
      }
      span.setStatus({ code: OTEL_STATUS_ERROR });
      span.end();
    }
  }
}

/**
 * Metrics collection via OpenTelemetry.
 *
 * Implements {@link MiddlewareHooks}. Records counters/histograms when a meter
 * is available (injected or resolved from the global provider); graceful
 * no-op otherwise.
 */
export class MetricsMiddleware implements MiddlewareHooks {
  private readonly meter: OtelMeter | null;
  private readonly started = new Map<string, number>();
  private readonly calls: OtelCounter | null;
  private readonly errors: OtelCounter | null;
  private readonly latency: OtelHistogram | null;
  private readonly inTokens: OtelCounter | null;
  private readonly outTokens: OtelCounter | null;

  constructor(meter?: unknown) {
    this.meter = (meter as OtelMeter | undefined) ?? resolveMeter();
    if (this.meter) {
      this.calls = this.meter.createCounter("adk.agent.calls", {
        unit: "1",
        description: "Agent invocations",
      });
      this.errors = this.meter.createCounter("adk.agent.errors", {
        unit: "1",
        description: "Model errors per agent",
      });
      this.latency = this.meter.createHistogram("adk.agent.latency", {
        unit: "ms",
        description: "Agent invocation latency",
      });
      this.inTokens = this.meter.createCounter("adk.model.input_tokens", {
        unit: "1",
        description: "Prompt tokens consumed",
      });
      this.outTokens = this.meter.createCounter("adk.model.output_tokens", {
        unit: "1",
        description: "Completion tokens produced",
      });
    } else {
      this.calls = null;
      this.errors = null;
      this.latency = null;
      this.inTokens = null;
      this.outTokens = null;
    }
  }

  async beforeAgent(_ctx: MiddlewareHookCtx, agentName: string): Promise<void> {
    this.started.set(agentName, Date.now());
  }

  async afterAgent(_ctx: MiddlewareHookCtx, agentName: string): Promise<void> {
    const attrs = { agent: agentName };
    this.calls?.add(1, attrs);
    const started = this.started.get(agentName);
    this.started.delete(agentName);
    if (started !== undefined) {
      this.latency?.record(Date.now() - started, attrs);
    }
  }

  async afterModel(ctx: MiddlewareHookCtx, response: unknown): Promise<void> {
    const agentName = ctxAgentName(ctx);
    const [inTok, outTok] = usageTokens(response);
    const attrs = { agent: agentName };
    if (inTok) {
      this.inTokens?.add(inTok, attrs);
    }
    if (outTok) {
      this.outTokens?.add(outTok, attrs);
    }
  }

  async onModelError(ctx: MiddlewareHookCtx, _request: unknown, _error: unknown): Promise<void> {
    const agentName = ctxAgentName(ctx);
    this.errors?.add(1, { agent: agentName });
  }
}
