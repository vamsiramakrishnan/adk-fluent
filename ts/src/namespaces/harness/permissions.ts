/**
 * Permission policies — pure data describing which tools an agent may call.
 *
 * Mirrors `python/src/adk_fluent/_harness/_permissions.py`. Policies are
 * immutable; merging produces a new policy with the union of decisions
 * (deny wins over ask wins over allow).
 */

import { toSet } from "./types.js";

/** What to do when a tool is invoked. */
export type Decision = "allow" | "ask" | "deny";

export interface PermissionPolicyOptions {
  allow?: Iterable<string>;
  ask?: Iterable<string>;
  deny?: Iterable<string>;
  allowPatterns?: readonly string[];
  denyPatterns?: readonly string[];
  /** "glob" (default) or "regex" — applies to both allow/deny patterns. */
  patternMode?: "glob" | "regex";
}

export class PermissionPolicy {
  readonly allow: ReadonlySet<string>;
  readonly ask: ReadonlySet<string>;
  readonly deny: ReadonlySet<string>;
  readonly allowPatterns: readonly string[];
  readonly denyPatterns: readonly string[];
  readonly patternMode: "glob" | "regex";

  constructor(opts: PermissionPolicyOptions = {}) {
    this.allow = toSet(opts.allow);
    this.ask = toSet(opts.ask);
    this.deny = toSet(opts.deny);
    this.allowPatterns = opts.allowPatterns ?? [];
    this.denyPatterns = opts.denyPatterns ?? [];
    this.patternMode = opts.patternMode ?? "glob";
  }

  /** Decide what to do for a tool call. Default: allow. */
  decide(toolName: string): Decision {
    if (this.deny.has(toolName)) return "deny";
    if (this.matchAny(toolName, this.denyPatterns)) return "deny";
    if (this.ask.has(toolName)) return "ask";
    if (this.allow.has(toolName)) return "allow";
    if (this.matchAny(toolName, this.allowPatterns)) return "allow";
    return "allow";
  }

  /** Merge with another policy. Deny > ask > allow. */
  merge(other: PermissionPolicy): PermissionPolicy {
    return new PermissionPolicy({
      allow: new Set([...this.allow, ...other.allow]),
      ask: new Set([...this.ask, ...other.ask]),
      deny: new Set([...this.deny, ...other.deny]),
      allowPatterns: [...this.allowPatterns, ...other.allowPatterns],
      denyPatterns: [...this.denyPatterns, ...other.denyPatterns],
      patternMode: other.patternMode ?? this.patternMode,
    });
  }

  private matchAny(name: string, patterns: readonly string[]): boolean {
    if (patterns.length === 0) return false;
    for (const p of patterns) {
      if (this.patternMode === "regex") {
        try {
          if (new RegExp(p).test(name)) return true;
        } catch {
          /* invalid regex — ignore */
        }
      } else if (globMatch(p, name)) {
        return true;
      }
    }
    return false;
  }
}

/** Minimal glob → regex (supports `*`, `?`, `**`). */
function globMatch(pattern: string, name: string): boolean {
  const re =
    "^" +
    pattern
      .replace(/[.+^${}()|[\]\\]/g, "\\$&")
      .replace(/\*\*/g, "::DOUBLESTAR::")
      .replace(/\*/g, "[^/]*")
      .replace(/::DOUBLESTAR::/g, ".*")
      .replace(/\?/g, ".") +
    "$";
  return new RegExp(re).test(name);
}

/**
 * Persistent record of user approval decisions so the same tool+args
 * pattern isn't asked twice in a session.
 */
export class ApprovalMemory {
  private readonly approved = new Set<string>();
  private readonly denied = new Set<string>();

  /** Approve `toolName` (optionally with a fingerprint of args). */
  approve(toolName: string, fingerprint?: string): void {
    this.approved.add(this.key(toolName, fingerprint));
  }

  deny(toolName: string, fingerprint?: string): void {
    this.denied.add(this.key(toolName, fingerprint));
  }

  remembers(toolName: string, fingerprint?: string): "approved" | "denied" | null {
    const k = this.key(toolName, fingerprint);
    if (this.approved.has(k)) return "approved";
    if (this.denied.has(k)) return "denied";
    return null;
  }

  clear(): void {
    this.approved.clear();
    this.denied.clear();
  }

  private key(name: string, fp?: string): string {
    return fp ? `${name}::${fp}` : name;
  }
}
