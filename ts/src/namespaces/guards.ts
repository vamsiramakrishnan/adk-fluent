/**
 * G — Guards (output validation) namespace.
 *
 * Guards validate/transform the LLM response (after_model).
 * Compose with .pipe() to chain multiple guards.
 *
 * Usage:
 *   agent.guard(G.length({ max: 500 }))
 *   agent.guard(G.json().pipe(G.schema(myZodSchema)))
 *   agent.guard(G.pii({ action: "redact" }))
 */

import type { CallbackFn, State } from "../core/types.js";

/** Descriptor for a single guard in the composite. */
export interface GuardSpec {
  name: string;
  check: CallbackFn;
  config?: Record<string, unknown>;
}

/** A composable guard descriptor. */
export class GComposite {
  constructor(public readonly guards: GuardSpec[]) {}

  /** Chain: add another guard. */
  pipe(other: GComposite): GComposite {
    return new GComposite([...this.guards, ...other.guards]);
  }

  /** Convert to a flat guard array for passing to builder. */
  toArray(): GuardSpec[] {
    return [...this.guards];
  }
}

/** Error thrown when a guard check fails. */
export class GuardViolation extends Error {
  constructor(
    public readonly guardName: string,
    public readonly phase: string,
    message: string,
  ) {
    super(message);
    this.name = "GuardViolation";
  }
}

/** PII detector interface. */
export interface PIIDetector {
  detect: (text: string) => Promise<string[]> | string[];
}

/** Content judge interface. */
export interface ContentJudge {
  judge: (text: string) => Promise<{ pass: boolean; reason?: string }> | { pass: boolean; reason?: string };
}

/**
 * G namespace — guard factories.
 *
 * All 21 methods from the Python G namespace.
 */
export class G {
  // ------------------------------------------------------------------
  // Core guards
  // ------------------------------------------------------------------

  /** Custom guard function. */
  static guard(fn: CallbackFn): GComposite {
    return new GComposite([{ name: "custom", check: fn }]);
  }

  /** Validate that output is valid JSON. */
  static json(): GComposite {
    return new GComposite([{
      name: "json",
      check: (response: string) => {
        try {
          JSON.parse(response);
        } catch (e) {
          throw new GuardViolation("json", "post_model", `Output is not valid JSON: ${e}`);
        }
      },
    }]);
  }

  /** Enforce max/min response length. */
  static length(opts: { min?: number; max?: number }): GComposite {
    const { min = 0, max = Infinity } = opts;
    return new GComposite([{
      name: "length",
      check: (response: string) => {
        const len = response.length;
        if (len < min) {
          throw new GuardViolation("length", "post_model", `Output too short (${len} < ${min})`);
        }
        if (len > max) {
          throw new GuardViolation("length", "post_model", `Output too long (${len} > ${max})`);
        }
      },
    }]);
  }

  /** Block or redact text matching a regex pattern. */
  static regex(
    pattern: string | RegExp,
    opts?: { action?: "block" | "redact"; replacement?: string },
  ): GComposite {
    const re = typeof pattern === "string" ? new RegExp(pattern, "g") : pattern;
    const action = opts?.action ?? "block";
    const replacement = opts?.replacement ?? "[REDACTED]";
    return new GComposite([{
      name: "regex",
      check: (response: string) => {
        if (action === "block" && re.test(response)) {
          throw new GuardViolation("regex", "post_model", `Output matches blocked pattern: ${re}`);
        }
        if (action === "redact") {
          return response.replace(re, replacement);
        }
        return undefined;
      },
      config: { pattern: re.source, action, replacement },
    }]);
  }

  /** Validate output against a schema (e.g., Zod). */
  static schema(zodSchema: { safeParse: (v: unknown) => { success: boolean; error?: unknown } }): GComposite {
    return new GComposite([{
      name: "schema",
      check: (response: string) => {
        const result = zodSchema.safeParse(JSON.parse(response));
        if (!result.success) {
          throw new GuardViolation("schema", "post_model", `Schema validation failed: ${result.error}`);
        }
      },
    }]);
  }

  /** Validate model output against a schema class. */
  static output(schemaCls: unknown): GComposite {
    return new GComposite([{
      name: "output",
      check: () => { /* resolved at runtime by ADK */ },
      config: { schema: schemaCls, phase: "post_model" },
    }]);
  }

  /** Validate model input against a schema class. */
  static input(schemaCls: unknown): GComposite {
    return new GComposite([{
      name: "input",
      check: () => { /* resolved at runtime by ADK */ },
      config: { schema: schemaCls, phase: "pre_model" },
    }]);
  }

  // ------------------------------------------------------------------
  // Resource guards
  // ------------------------------------------------------------------

  /** Enforce token budget. */
  static budget(opts?: { maxTokens?: number }): GComposite {
    const maxTokens = opts?.maxTokens ?? 4096;
    return new GComposite([{
      name: "budget",
      check: () => { /* resolved at runtime by ADK */ },
      config: { maxTokens },
    }]);
  }

  /** Enforce requests-per-minute limit. */
  static rateLimit(opts?: { rpm?: number }): GComposite {
    const rpm = opts?.rpm ?? 60;
    return new GComposite([{
      name: "rate_limit",
      check: () => { /* resolved at runtime by ADK */ },
      config: { rpm },
    }]);
  }

  /** Enforce maximum conversation turns. */
  static maxTurns(n: number): GComposite {
    return new GComposite([{
      name: "max_turns",
      check: () => { /* resolved at runtime by ADK */ },
      config: { maxTurns: n },
    }]);
  }

  // ------------------------------------------------------------------
  // Content safety guards
  // ------------------------------------------------------------------

  /** Detect and handle PII in output. */
  static pii(opts?: {
    action?: "block" | "redact";
    detector?: PIIDetector;
    threshold?: number;
    replacement?: string;
  }): GComposite {
    return new GComposite([{
      name: "pii",
      check: () => { /* resolved at runtime by ADK with detector */ },
      config: {
        action: opts?.action ?? "block",
        detector: opts?.detector,
        threshold: opts?.threshold ?? 0.8,
        replacement: opts?.replacement ?? "[PII]",
      },
    }]);
  }

  /** Block toxic content above threshold. */
  static toxicity(opts?: { threshold?: number; judge?: ContentJudge }): GComposite {
    return new GComposite([{
      name: "toxicity",
      check: () => { /* resolved at runtime by ADK with judge */ },
      config: {
        threshold: opts?.threshold ?? 0.5,
        judge: opts?.judge,
      },
    }]);
  }

  /** Block output discussing denied topics. */
  static topic(opts: { deny: string[] }): GComposite {
    return new GComposite([{
      name: "topic",
      check: () => { /* resolved at runtime by ADK */ },
      config: { deny: opts.deny },
    }]);
  }

  /** Require output to be grounded in provided sources. */
  static grounded(opts?: { sourcesKey?: string }): GComposite {
    return new GComposite([{
      name: "grounded",
      check: () => { /* resolved at runtime by ADK */ },
      config: { sourcesKey: opts?.sourcesKey ?? "sources" },
    }]);
  }

  /** Detect hallucinated content. */
  static hallucination(opts?: {
    threshold?: number;
    sourcesKey?: string;
    judge?: ContentJudge;
  }): GComposite {
    return new GComposite([{
      name: "hallucination",
      check: () => { /* resolved at runtime by ADK */ },
      config: {
        threshold: opts?.threshold ?? 0.5,
        sourcesKey: opts?.sourcesKey ?? "sources",
        judge: opts?.judge,
      },
    }]);
  }

  // ------------------------------------------------------------------
  // A2UI guard
  // ------------------------------------------------------------------

  /** Validate LLM-generated A2UI output. */
  static a2ui(opts?: {
    maxComponents?: number;
    allowedTypes?: string[];
    denyTypes?: string[];
  }): GComposite {
    return new GComposite([{
      name: "a2ui",
      check: () => { /* resolved at runtime by A2UI runtime */ },
      config: {
        maxComponents: opts?.maxComponents ?? 50,
        allowedTypes: opts?.allowedTypes,
        denyTypes: opts?.denyTypes,
      },
    }]);
  }

  // ------------------------------------------------------------------
  // Conditional
  // ------------------------------------------------------------------

  /** Conditionally apply a guard. */
  static when(predicate: (state: State) => boolean, guard: GComposite): GComposite {
    return new GComposite(guard.guards.map((g) => ({
      ...g,
      name: `when(${g.name})`,
      config: { ...g.config, condition: predicate },
    })));
  }

  // ------------------------------------------------------------------
  // Detector factories
  // ------------------------------------------------------------------

  /** Create a Google Cloud DLP PII detector. */
  static dlp(opts?: {
    project?: string;
    infoTypes?: string[];
    location?: string;
  }): PIIDetector {
    return {
      detect: () => {
        // At runtime, resolved by Cloud DLP integration
        return [];
      },
      ...opts,
    } as PIIDetector;
  }

  /** Create a regex-based PII detector. */
  static regexDetector(patterns: (string | RegExp)[]): PIIDetector {
    const regexes = patterns.map((p) => (typeof p === "string" ? new RegExp(p, "g") : p));
    return {
      detect: (text: string) => {
        const findings: string[] = [];
        for (const re of regexes) {
          const matches = text.match(re);
          if (matches) findings.push(...matches);
        }
        return findings;
      },
    };
  }

  /** Combine multiple PII detectors. */
  static multi(...detectors: PIIDetector[]): PIIDetector {
    return {
      detect: async (text: string) => {
        const all = await Promise.all(detectors.map((d) => d.detect(text)));
        return all.flat();
      },
    };
  }

  /** Wrap an async callable as a PII detector. */
  static custom(fn: (text: string) => Promise<string[]> | string[]): PIIDetector {
    return { detect: fn };
  }

  // ------------------------------------------------------------------
  // Judge factories
  // ------------------------------------------------------------------

  /** Create an LLM-based content judge. */
  static llmJudge(opts?: { model?: string }): ContentJudge {
    return {
      judge: () => {
        // At runtime, resolved by LLM judge integration
        return { pass: true };
      },
      ...opts,
    } as ContentJudge;
  }

  /** Wrap an async callable as a content judge. */
  static customJudge(
    fn: (text: string) => Promise<{ pass: boolean; reason?: string }> | { pass: boolean; reason?: string },
  ): ContentJudge {
    return { judge: fn };
  }
}
