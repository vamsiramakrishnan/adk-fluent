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

/**
 * Coarse permission modes. `DEFAULT` respects the policy's explicit
 * allow/ask/deny rules verbatim. `PLAN` overrides the policy to deny any
 * mutating tool regardless of what the rules say. `ACCEPT_EDITS`
 * auto-allows common edit tools without prompting. `BYPASS` allows
 * everything — used for read-only replay or for tests.
 */
export enum PermissionMode {
  DEFAULT = "default",
  PLAN = "plan",
  ACCEPT_EDITS = "accept_edits",
  BYPASS = "bypass",
}

/** Behavior-oriented verdict (matches Python `PermissionBehavior`). */
export enum PermissionBehavior {
  ALLOW = "allow",
  ASK = "ask",
  DENY = "deny",
}

const MUTATING_FOR_PLAN: ReadonlySet<string> = new Set([
  "write_file",
  "edit_file",
  "bash",
  "run_code",
  "git_commit",
  "start_process",
]);

const AUTO_EDIT_TOOLS: ReadonlySet<string> = new Set([
  "write_file",
  "edit_file",
  "diff_edit_file",
  "apply_edit",
]);

/**
 * Rich verdict object returned by `PermissionPolicy.check()`. Mirrors
 * Python's `PermissionDecision`. `behavior` is the canonical field;
 * `isAllow` / `isAsk` / `isDeny` are sugar.
 */
export class PermissionDecision {
  readonly behavior: PermissionBehavior;
  readonly reason?: string;
  readonly mode: PermissionMode;

  constructor(behavior: PermissionBehavior, opts: { reason?: string; mode?: PermissionMode } = {}) {
    this.behavior = behavior;
    this.reason = opts.reason;
    this.mode = opts.mode ?? PermissionMode.DEFAULT;
    Object.freeze(this);
  }

  get isAllow(): boolean {
    return this.behavior === PermissionBehavior.ALLOW;
  }
  get isAsk(): boolean {
    return this.behavior === PermissionBehavior.ASK;
  }
  get isDeny(): boolean {
    return this.behavior === PermissionBehavior.DENY;
  }

  static allow(reason?: string, mode?: PermissionMode): PermissionDecision {
    return new PermissionDecision(PermissionBehavior.ALLOW, { reason, mode });
  }
  static ask(reason?: string, mode?: PermissionMode): PermissionDecision {
    return new PermissionDecision(PermissionBehavior.ASK, { reason, mode });
  }
  static deny(reason?: string, mode?: PermissionMode): PermissionDecision {
    return new PermissionDecision(PermissionBehavior.DENY, { reason, mode });
  }
}

export interface PermissionPolicyOptions {
  allow?: Iterable<string>;
  ask?: Iterable<string>;
  deny?: Iterable<string>;
  allowPatterns?: readonly string[];
  denyPatterns?: readonly string[];
  /** "glob" (default) or "regex" — applies to both allow/deny patterns. */
  patternMode?: "glob" | "regex";
  /** Coarse mode that layers on top of allow/ask/deny rules. */
  mode?: PermissionMode;
}

export class PermissionPolicy {
  readonly allow: ReadonlySet<string>;
  readonly ask: ReadonlySet<string>;
  readonly deny: ReadonlySet<string>;
  readonly allowPatterns: readonly string[];
  readonly denyPatterns: readonly string[];
  readonly patternMode: "glob" | "regex";
  readonly mode: PermissionMode;

  constructor(opts: PermissionPolicyOptions = {}) {
    this.allow = toSet(opts.allow);
    this.ask = toSet(opts.ask);
    this.deny = toSet(opts.deny);
    this.allowPatterns = opts.allowPatterns ?? [];
    this.denyPatterns = opts.denyPatterns ?? [];
    this.patternMode = opts.patternMode ?? "glob";
    this.mode = opts.mode ?? PermissionMode.DEFAULT;
  }

  /** Decide what to do for a tool call. Default: allow. */
  decide(toolName: string): Decision {
    return this.check(toolName).behavior as Decision;
  }

  /**
   * Rich check that returns a `PermissionDecision`. The precedence rules:
   * mode overrides (BYPASS / ACCEPT_EDITS / PLAN) first, then explicit
   * deny, then pattern deny, then explicit ask, then explicit allow, then
   * pattern allow, then a default `allow`.
   */
  check(toolName: string, _args?: Record<string, unknown>): PermissionDecision {
    if (this.mode === PermissionMode.BYPASS) {
      return PermissionDecision.allow("BYPASS mode", this.mode);
    }
    if (this.mode === PermissionMode.PLAN && MUTATING_FOR_PLAN.has(toolName)) {
      return PermissionDecision.deny(`Plan mode denies mutating tool '${toolName}'.`, this.mode);
    }
    if (this.deny.has(toolName) || this.matchAny(toolName, this.denyPatterns)) {
      return PermissionDecision.deny(`Policy denies '${toolName}'.`, this.mode);
    }
    if (this.mode === PermissionMode.ACCEPT_EDITS && AUTO_EDIT_TOOLS.has(toolName)) {
      return PermissionDecision.allow("ACCEPT_EDITS mode", this.mode);
    }
    if (this.ask.has(toolName)) {
      return PermissionDecision.ask(`Policy asks about '${toolName}'.`, this.mode);
    }
    if (this.allow.has(toolName) || this.matchAny(toolName, this.allowPatterns)) {
      return PermissionDecision.allow(undefined, this.mode);
    }
    return PermissionDecision.allow("default", this.mode);
  }

  /** Return a copy of this policy with a different `mode`. */
  withMode(mode: PermissionMode): PermissionPolicy {
    return new PermissionPolicy({
      allow: this.allow,
      ask: this.ask,
      deny: this.deny,
      allowPatterns: this.allowPatterns,
      denyPatterns: this.denyPatterns,
      patternMode: this.patternMode,
      mode,
    });
  }

  /** Merge with another policy. Deny > ask > allow. Other's mode wins. */
  merge(other: PermissionPolicy): PermissionPolicy {
    return new PermissionPolicy({
      allow: new Set([...this.allow, ...other.allow]),
      ask: new Set([...this.ask, ...other.ask]),
      deny: new Set([...this.deny, ...other.deny]),
      allowPatterns: [...this.allowPatterns, ...other.allowPatterns],
      denyPatterns: [...this.denyPatterns, ...other.denyPatterns],
      patternMode: other.patternMode ?? this.patternMode,
      mode: other.mode !== PermissionMode.DEFAULT ? other.mode : this.mode,
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
