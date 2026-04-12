/**
 * Plan mode — plan-then-execute latch with observer subscribe, policy
 * wrapper, and before-tool hook factory.
 *
 * Mirrors `python/src/adk_fluent/_plan_mode/`. The latch is the dynamic
 * half (state flips as the LLM calls `enter_plan_mode` / `exit_plan_mode`);
 * `PlanModePolicy` is the glue that makes a base `PermissionPolicy` deny
 * mutating tools while the latch is planning; `planModeBeforeToolHook`
 * enforces the same rule at the tool-call layer for harnesses that don't
 * consult a `PermissionPolicy` directly.
 */

import { PermissionMode } from "./permissions.js";
import type { PermissionDecision, PermissionPolicy } from "./permissions.js";
import { asTool, type HarnessTool } from "./types.js";

export type PlanState = "off" | "planning" | "executing";

export const MUTATING_TOOLS: ReadonlySet<string> = new Set([
  "write_file",
  "edit_file",
  "bash",
  "run_code",
  "git_commit",
  "start_process",
]);

export type PlanObserver = (state: PlanState, plan: string) => void;

/**
 * Three-state plan-mode latch with observer subscribe. Transitions fire
 * every subscriber synchronously; exceptions raised by an observer are
 * swallowed so one broken listener cannot break the latch.
 */
export class PlanMode {
  private state_: PlanState = "off";
  private plan_ = "";
  private readonly observers: PlanObserver[] = [];

  get current(): PlanState {
    return this.state_;
  }

  get currentPlan(): string {
    return this.plan_;
  }

  get isPlanning(): boolean {
    return this.state_ === "planning";
  }

  get isExecuting(): boolean {
    return this.state_ === "executing";
  }

  /** Classify a tool name as mutating (write/edit/exec). */
  static isMutating(toolName: string): boolean {
    return MUTATING_TOOLS.has(toolName);
  }

  enter(): void {
    this.state_ = "planning";
    this.plan_ = "";
    this.notify();
  }

  exit(plan: string): void {
    this.state_ = "executing";
    this.plan_ = plan;
    this.notify();
  }

  reset(): void {
    this.state_ = "off";
    this.plan_ = "";
    this.notify();
  }

  /** Subscribe an observer. Returns an unsubscribe function. */
  subscribe(callback: PlanObserver): () => void {
    this.observers.push(callback);
    return () => {
      const i = this.observers.indexOf(callback);
      if (i >= 0) this.observers.splice(i, 1);
    };
  }

  private notify(): void {
    for (const cb of [...this.observers]) {
      try {
        cb(this.state_, this.plan_);
      } catch {
        /* observers must not break the latch */
      }
    }
  }

  /** LLM-callable `enter_plan_mode` / `exit_plan_mode` pair. */
  tools(): HarnessTool[] {
    return planModeTools(this);
  }
}

/** Build the `enter_plan_mode` / `exit_plan_mode` tool pair bound to a latch. */
export function planModeTools(latch: PlanMode): HarnessTool[] {
  return [
    asTool("enter_plan_mode", async () => {
      latch.enter();
      return { state: latch.current };
    }),
    asTool("exit_plan_mode", async (args: { plan: string }) => {
      latch.exit(args.plan);
      return { state: latch.current, plan: latch.currentPlan };
    }),
  ];
}

/**
 * Frozen wrapper that ties a base `PermissionPolicy` to a `PlanMode` latch.
 * While the latch is planning, `check()` routes through a policy forced
 * into `PermissionMode.PLAN`; otherwise it delegates to the base.
 */
export class PlanModePolicy {
  readonly base: PermissionPolicy;
  readonly latch: PlanMode;

  constructor(base: PermissionPolicy, latch: PlanMode) {
    this.base = base;
    this.latch = latch;
    Object.freeze(this);
  }

  check(toolName: string, args?: Record<string, unknown>): PermissionDecision {
    return this.effective().check(toolName, args);
  }

  /** Shim for callers expecting the plain `decide()` API. */
  decide(toolName: string): "allow" | "ask" | "deny" {
    return this.effective().decide(toolName);
  }

  get mode(): PermissionMode {
    return this.effective().mode;
  }

  get allow(): ReadonlySet<string> {
    return this.base.allow;
  }

  get deny(): ReadonlySet<string> {
    return this.base.deny;
  }

  get ask(): ReadonlySet<string> {
    return this.base.ask;
  }

  private effective(): PermissionPolicy {
    return this.latch.isPlanning ? this.base.withMode(PermissionMode.PLAN) : this.base;
  }
}

export interface PlanModeHookResult {
  error: string;
  planModeState: PlanState;
}

/**
 * Build a before-tool callback that blocks mutating tools while the latch
 * is planning. Returns `null` (meaning "proceed") otherwise. Use with any
 * harness tool layer that accepts an async `(toolName) => Promise<...>`
 * gate.
 */
export function planModeBeforeToolHook(
  latch: PlanMode,
): (toolName: string) => PlanModeHookResult | null {
  return (toolName: string) => {
    if (!latch.isPlanning) return null;
    if (!PlanMode.isMutating(toolName)) return null;
    return {
      error:
        `Plan mode denies mutating tool '${toolName}'. ` +
        `Call exit_plan_mode(plan) before touching the workspace.`,
      planModeState: latch.current,
    };
  };
}
