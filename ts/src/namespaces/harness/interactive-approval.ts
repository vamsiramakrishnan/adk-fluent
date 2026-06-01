/**
 * InteractiveApprovalHandler — a shipped human-in-the-loop permission handler.
 *
 * Port of `python/src/adk_fluent/_permissions/_interactive.py`.
 *
 * The permission layer knows how to *ask*: a policy returns
 * `PermissionDecision.ask(...)` and the `PermissionPlugin` defers to an
 * installed `PermissionHandler`. This module ships the missing
 * batteries-included handler so users don't hand-write one from scratch.
 *
 * `InteractiveApprovalHandler`:
 *
 * 1. Receives the `ask` decision the policy produced (tool name + input +
 *    suggested prompt).
 * 2. Renders an `ApprovalRequest` plus a matching `UI.confirm` surface
 *    ("Run `bash`(...)?") so any front-end can display the same dialog the
 *    console flow uses.
 * 3. Asks a pluggable `responder(request) -> boolean | ApprovalVerdict` for
 *    the verdict. The default responder is a console prompt for real CLI use;
 *    tests inject a fake responder so no real stdin is required.
 * 4. Optionally records the verdict in an `ApprovalMemory`. A verdict of
 *    `ApprovalVerdict.ALWAYS` / `NEVER` calls `ApprovalMemory.rememberTool`
 *    so the *same memory* short-circuits the next `ask` for that tool before
 *    the handler is consulted again.
 *
 * The handler exposes a `.handler` callable with the exact `PermissionHandler`
 * signature `(toolName, toolInput, decision) -> boolean | Promise<boolean>`
 * so it drops straight into
 * `H.permissionPlugin({ policy, handler: UI.approval({ responder }), memory })`.
 */

import { createInterface } from "node:readline";

import { UI, type UISurface } from "../ui.js";
import type { ApprovalMemory, PermissionDecision, PermissionHandler } from "./permissions.js";

/**
 * String verdicts a responder may return instead of a plain boolean.
 *
 * `ALLOW` / `DENY` are one-shot decisions for this call only. `ALWAYS` /
 * `NEVER` are remembered for every future call of the tool (via
 * `ApprovalMemory.rememberTool`) when a memory is wired.
 */
export const ApprovalVerdict = {
  ALLOW: "allow",
  DENY: "deny",
  ALWAYS: "always",
  NEVER: "never",
} as const;

export type ApprovalVerdictValue = (typeof ApprovalVerdict)[keyof typeof ApprovalVerdict];

const ALLOWING: ReadonlySet<string> = new Set([ApprovalVerdict.ALLOW, ApprovalVerdict.ALWAYS]);
const REMEMBERED: ReadonlySet<string> = new Set([ApprovalVerdict.ALWAYS, ApprovalVerdict.NEVER]);

/**
 * A single approval request handed to the responder. Carries everything a
 * console prompt or a UI surface needs to render the question, plus the
 * compiled `UI.confirm` surface itself. Frozen on construction.
 */
export class ApprovalRequest {
  readonly toolName: string;
  readonly toolInput: Record<string, unknown>;
  readonly prompt: string;
  readonly surface: UISurface;
  readonly decision?: PermissionDecision;

  constructor(opts: {
    toolName: string;
    toolInput: Record<string, unknown>;
    prompt: string;
    surface: UISurface;
    decision?: PermissionDecision;
  }) {
    this.toolName = opts.toolName;
    this.toolInput = { ...opts.toolInput };
    this.prompt = opts.prompt;
    this.surface = opts.surface;
    this.decision = opts.decision;
    Object.freeze(this.toolInput);
    Object.freeze(this);
  }
}

/**
 * A responder receives the request and returns either a boolean (allow/deny)
 * or an `ApprovalVerdict` string (allow/deny/always/never). May be async.
 */
export type Responder = (request: ApprovalRequest) => boolean | string | Promise<boolean | string>;

/** Render `{ path: "/x", n: 3 }` as `path="/x", n=3` for a prompt. */
function formatInput(input: Record<string, unknown>): string {
  const keys = Object.keys(input);
  if (keys.length === 0) return "";
  return keys.map((k) => `${k}=${JSON.stringify(input[k])}`).join(", ");
}

/**
 * Build the human-facing approval message. Prefers the policy's suggested
 * reason/prompt; otherwise synthesises ``Run `bash`(path="/x")?``.
 */
function defaultMessage(
  toolName: string,
  toolInput: Record<string, unknown>,
  prompt: string,
): string {
  if (prompt) return prompt;
  return `Run \`${toolName}\`(${formatInput(toolInput)})?`;
}

/**
 * Default responder: a blocking console prompt for real CLI use.
 * `y`/`yes` → allow, `a`/`always` → always, anything else → deny.
 */
function consoleResponder(request: ApprovalRequest): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return new Promise<string>((resolve) => {
    rl.question(`${request.prompt} [y]es / [n]o / [a]lways: `, (answer) => {
      rl.close();
      const normalised = answer.trim().toLowerCase();
      if (normalised === "a" || normalised === "always") resolve(ApprovalVerdict.ALWAYS);
      else if (normalised === "y" || normalised === "yes") resolve(ApprovalVerdict.ALLOW);
      else resolve(ApprovalVerdict.DENY);
    });
  });
}

export interface InteractiveApprovalOptions {
  /**
   * `responder(request) -> boolean | ApprovalVerdict`. Defaults to a console
   * prompt.
   */
  responder?: Responder;
  /**
   * Optional `ApprovalMemory`. When supplied, `always` / `never` verdicts are
   * persisted via `ApprovalMemory.rememberTool` so the next ask
   * short-circuits. Pass the *same* memory to `H.permissionPlugin`.
   */
  memory?: ApprovalMemory;
  /** Optional message builder to customise the rendered question. */
  message?: (toolName: string, toolInput: Record<string, unknown>, prompt: string) => string;
}

/**
 * A shipped, UI-bridged `PermissionHandler`.
 *
 * Usage:
 * ```ts
 * const handler = UI.approval({ responder: myResponder, memory });
 * const plugin = H.permissionPlugin({ policy, handler: handler.handler, memory });
 * ```
 *
 * Pass the *same* `ApprovalMemory` to both so an `always` verdict
 * short-circuits future asks.
 */
export class InteractiveApprovalHandler {
  private readonly responder: Responder;
  private readonly _memory?: ApprovalMemory;
  private readonly message: (
    toolName: string,
    toolInput: Record<string, unknown>,
    prompt: string,
  ) => string;

  constructor(opts: InteractiveApprovalOptions = {}) {
    this.responder = opts.responder ?? consoleResponder;
    this._memory = opts.memory;
    this.message = opts.message ?? defaultMessage;
    // Bind so `handler` can be passed by reference to the plugin.
    this.handler = this.handler.bind(this);
  }

  get memory(): ApprovalMemory | undefined {
    return this._memory;
  }

  /** Build the `ApprovalRequest` (message + confirm surface). */
  buildRequest(
    toolName: string,
    toolInput: Record<string, unknown>,
    decision?: PermissionDecision,
  ): ApprovalRequest {
    const prompt = decision?.reason ?? "";
    const message = this.message(toolName, { ...toolInput }, prompt);
    // ui.js does not import this module, so a top-level import is cycle-free.
    const surface = UI.confirm(message, {
      yes: "Allow",
      no: "Deny",
      yesAction: "approval_allow",
      noAction: "approval_deny",
    });
    return new ApprovalRequest({
      toolName,
      toolInput: { ...toolInput },
      prompt: message,
      surface,
      decision,
    });
  }

  /**
   * PermissionHandler protocol —
   * `(toolName, toolInput, decision) -> Promise<boolean>`.
   */
  handler: PermissionHandler = async (
    toolName: string,
    toolInput: Record<string, unknown>,
    decision: PermissionDecision,
  ): Promise<boolean> => {
    // A previously-remembered tool-level verdict short-circuits the prompt.
    // The plugin also checks this, but the handler is defensive in case it is
    // invoked without the plugin's pre-check (e.g. directly in tests).
    if (this._memory) {
      const recalled = this._memory.recall(toolName);
      if (recalled !== null) return recalled;
    }

    const request = this.buildRequest(toolName, toolInput, decision);
    const verdict = await this.responder(request);
    return this.resolve(toolName, verdict);
  };

  private resolve(toolName: string, verdict: boolean | string): boolean {
    if (typeof verdict === "boolean") return verdict;
    if (typeof verdict !== "string") {
      throw new TypeError(
        `approval responder must return a boolean or an ApprovalVerdict string, got ${typeof verdict}`,
      );
    }

    const normalised = verdict.trim().toLowerCase();
    if (
      normalised !== ApprovalVerdict.ALLOW &&
      normalised !== ApprovalVerdict.DENY &&
      normalised !== ApprovalVerdict.ALWAYS &&
      normalised !== ApprovalVerdict.NEVER
    ) {
      throw new Error(`unknown approval verdict: ${JSON.stringify(verdict)}`);
    }

    const granted = ALLOWING.has(normalised);
    if (REMEMBERED.has(normalised) && this._memory) {
      this._memory.rememberTool(toolName, granted);
    }
    return granted;
  }
}
