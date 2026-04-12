/**
 * C — Context engineering namespace.
 *
 * Controls what history and state data an agent sees.
 * Two categories:
 * - History-filtering: suppress/filter conversation history
 * - Data-injection: inject state without touching history
 *
 * Compose with .add() (union). Suppression wins: if ANY child suppresses, composite does.
 *
 * Usage:
 *   agent.context(C.none())                           // suppress all history
 *   agent.context(C.window(5))                        // last 5 turn-pairs
 *   agent.context(C.none().add(C.fromState("key")))   // no history + inject state
 */

import type { State } from "../core/types.js";

/** A composable context transform descriptor. */
export class CTransform {
  constructor(
    public readonly kind: string,
    public readonly config: Record<string, unknown> = {},
    public readonly suppressHistory: boolean = false,
    public readonly children: CTransform[] = [],
  ) {}

  /** Compose: merge another context transform. Suppression wins. */
  add(other: CTransform): CTransform {
    return new CTransform(
      `${this.kind}+${other.kind}`,
      { ...this.config, ...other.config },
      this.suppressHistory || other.suppressHistory,
      [...this.children, other],
    );
  }

  /** Alias for add() — reads better for data-injection transforms. */
  inject(other: CTransform): CTransform {
    return this.add(other);
  }

  /** Pipe: apply a transform to the output of this one. */
  pipe(other: CTransform): CTransform {
    return new CTransform(
      `${this.kind}|${other.kind}`,
      { source: this, transform: other },
      this.suppressHistory || other.suppressHistory,
    );
  }
}

/**
 * C namespace — context engineering factories.
 *
 * All 33+ methods from the Python C namespace.
 */
export class C {
  // ------------------------------------------------------------------
  // History filtering (suppress history)
  // ------------------------------------------------------------------

  /** Suppress all conversation history. */
  static none(): CTransform {
    return new CTransform("none", {}, true);
  }

  /** Default ADK behavior (keep all history). */
  static default_(): CTransform {
    return new CTransform("default", {}, false);
  }

  /** Only user messages. */
  static userOnly(): CTransform {
    return new CTransform("user_only", { filter: "user" }, true);
  }

  /** User messages with strategy selection. */
  static user(strategy: "all" | "last" | "first" = "all"): CTransform {
    return new CTransform("user", { strategy }, true);
  }

  /** Last N turn-pairs. */
  static window(n = 5): CTransform {
    return new CTransform(`window(${n})`, { window: n }, true);
  }

  /** Alias for window(). */
  static lastNTurns(n: number): CTransform {
    return C.window(n);
  }

  /** Include user + outputs from named agents. */
  static fromAgents(...names: string[]): CTransform {
    return new CTransform(`fromAgents(${names.join(",")})`, { agents: names }, true);
  }

  /** Per-agent selective windowing. */
  static fromAgentsWindowed(agentWindows: Record<string, number>): CTransform {
    return new CTransform("fromAgentsWindowed", { agentWindows }, true);
  }

  /** Exclude messages from named agents. */
  static excludeAgents(...names: string[]): CTransform {
    return new CTransform(`excludeAgents(${names.join(",")})`, { excludeAgents: names }, true);
  }

  /** Hard limit by turns or tokens. */
  static truncate(opts: {
    maxTurns?: number;
    maxTokens?: number;
    strategy?: "head" | "tail";
  }): CTransform {
    return new CTransform("truncate", opts, true);
  }

  /** Filter events by metadata (author, type, tag). */
  static select(opts: { author?: string; type?: string; tag?: string }): CTransform {
    return new CTransform("select", opts, true);
  }

  /** Keep only specified fields from messages. */
  static project(...fields: string[]): CTransform {
    return new CTransform(`project(${fields.join(",")})`, { fields }, true);
  }

  // ------------------------------------------------------------------
  // Data injection (neutral — keep history)
  // ------------------------------------------------------------------

  /** Inject state keys as context. */
  static fromState(...keys: string[]): CTransform {
    return new CTransform(`fromState(${keys.join(",")})`, { stateKeys: keys }, false);
  }

  /** Template with {key} placeholders (resolved from state). */
  static template(text: string): CTransform {
    return new CTransform("template", { template: text }, false);
  }

  /** Inject scratchpad notes. */
  static notes(key = "default", format: "plain" | "markdown" = "plain"): CTransform {
    return new CTransform(`notes(${key})`, { notesKey: key, format }, false);
  }

  /** Write to scratchpad notes. */
  static writeNotes(opts?: {
    key?: string;
    strategy?: "append" | "replace";
    sourceKey?: string;
  }): CTransform {
    return new CTransform(
      "writeNotes",
      {
        notesKey: opts?.key ?? "default",
        strategy: opts?.strategy ?? "append",
        sourceKey: opts?.sourceKey,
      },
      false,
    );
  }

  // ------------------------------------------------------------------
  // Budget and fitting
  // ------------------------------------------------------------------

  /** Token budget constraint. */
  static budget(opts: {
    maxTokens?: number;
    overflow?: "truncate_oldest" | "summarize" | "drop";
  }): CTransform {
    return new CTransform(
      "budget",
      {
        maxTokens: opts.maxTokens ?? 8000,
        overflow: opts.overflow ?? "truncate_oldest",
      },
      true,
    );
  }

  /** Aggressive pruning to fit within a token limit. */
  static fit(opts?: { maxTokens?: number; strategy?: "strict" | "soft" }): CTransform {
    return new CTransform(
      "fit",
      {
        maxTokens: opts?.maxTokens ?? 4000,
        strategy: opts?.strategy ?? "strict",
      },
      true,
    );
  }

  /** Priority tier for context ordering. */
  static priority(tier = 2): CTransform {
    return new CTransform(`priority(${tier})`, { tier }, false);
  }

  // ------------------------------------------------------------------
  // Time-based
  // ------------------------------------------------------------------

  /** Importance-weighted by recency. */
  static recent(opts?: {
    decay?: "exponential" | "linear";
    halfLife?: number;
    minWeight?: number;
  }): CTransform {
    return new CTransform(
      "recent",
      {
        decay: opts?.decay ?? "exponential",
        halfLife: opts?.halfLife ?? 10,
        minWeight: opts?.minWeight ?? 0.1,
      },
      true,
    );
  }

  /** Prune stale items by age. */
  static fresh(opts?: { maxAge?: number; staleAction?: "drop" | "summarize" }): CTransform {
    return new CTransform(
      "fresh",
      {
        maxAge: opts?.maxAge ?? 3600,
        staleAction: opts?.staleAction ?? "drop",
      },
      true,
    );
  }

  /** Rolling window with optional compaction. */
  static rolling(opts?: { n?: number; summarize?: boolean }): CTransform {
    return new CTransform(
      "rolling",
      {
        n: opts?.n ?? 5,
        summarize: opts?.summarize ?? false,
      },
      true,
    );
  }

  // ------------------------------------------------------------------
  // Dedup and compaction
  // ------------------------------------------------------------------

  /** Remove duplicate messages. */
  static dedup(strategy: "exact" | "semantic" = "exact"): CTransform {
    return new CTransform("dedup", { strategy }, true);
  }

  /** Structural compaction (remove empty tool calls, etc.). */
  static compact(strategy: "tool_calls" | "all" = "tool_calls"): CTransform {
    return new CTransform("compact", { strategy }, true);
  }

  // ------------------------------------------------------------------
  // LLM-powered transforms
  // ------------------------------------------------------------------

  /** LLM-powered summarization. */
  static summarize(opts?: { scope?: "all" | "oldest" | "tools"; prompt?: string }): CTransform {
    return new CTransform(
      "summarize",
      {
        scope: opts?.scope ?? "all",
        prompt: opts?.prompt,
      },
      true,
    );
  }

  /** Semantic relevance filtering. */
  static relevant(opts?: { queryKey?: string; query?: string; topK?: number }): CTransform {
    return new CTransform(
      "relevant",
      {
        queryKey: opts?.queryKey,
        query: opts?.query,
        topK: opts?.topK ?? 5,
      },
      true,
    );
  }

  /** Extract structured data from context via LLM. */
  static extract(opts?: { key?: string }): CTransform {
    return new CTransform(
      "extract",
      {
        key: opts?.key ?? "extracted",
      },
      true,
    );
  }

  /** Distill context to key facts via LLM. */
  static distill(opts?: { key?: string }): CTransform {
    return new CTransform(
      "distill",
      {
        key: opts?.key ?? "facts",
      },
      true,
    );
  }

  /** Context quality validation via LLM. */
  static validate_(...checks: string[]): CTransform {
    return new CTransform("validate", { checks }, false);
  }

  // ------------------------------------------------------------------
  // Privacy
  // ------------------------------------------------------------------

  /** Redact sensitive content via regex. */
  static redact(patterns: string[], replacement = "[REDACTED]"): CTransform {
    return new CTransform("redact", { patterns, replacement }, false);
  }

  // ------------------------------------------------------------------
  // Conditional
  // ------------------------------------------------------------------

  /** Conditional context transform. */
  static when(predicate: (state: State) => boolean, transform: CTransform): CTransform {
    return new CTransform(
      `when(${transform.kind})`,
      {
        condition: predicate,
        child: transform,
      },
      transform.suppressHistory,
    );
  }

  // ------------------------------------------------------------------
  // Multi-agent patterns
  // ------------------------------------------------------------------

  /** Manus-style cascading context: progressive compression. */
  static manusCascade(opts?: { budget?: number }): CTransform {
    return new CTransform(
      "manusCascade",
      {
        budget: opts?.budget ?? 8000,
      },
      true,
    );
  }

  /** Pipeline-aware: user messages + state keys (for pipeline agents). */
  static pipelineAware(...keys: string[]): CTransform {
    return new CTransform(`pipelineAware(${keys.join(",")})`, { stateKeys: keys }, true);
  }

  /** Full transcript for multi-agent loops. */
  static sharedThread(): CTransform {
    return new CTransform("sharedThread", {}, false);
  }

  // ------------------------------------------------------------------
  // A2UI bridge
  // ------------------------------------------------------------------

  /** Include A2UI surface state in context. */
  static withUi(surfaceId?: string): CTransform {
    return new CTransform("withUi", { surfaceId }, false);
  }
}
