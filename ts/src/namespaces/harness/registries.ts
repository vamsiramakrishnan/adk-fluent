/**
 * Hook registry, command registry, tool policy, task ledger, and task
 * registry. Mirrors `_harness/_hooks.py`, `_commands.py`, `_tool_policy.py`,
 * `_task_ledger.py`, `_tasks.py`.
 */

import { spawn } from "node:child_process";
import { asTool, type HarnessTool } from "./types.js";
import type { EventBus } from "./events.js";

// ─── HookEvent ─────────────────────────────────────────────────────────────

/**
 * Canonical hook event names. Mirrors Python `_hooks._events.HookEvent`,
 * with six extra legacy values (`ToolCallStart`, `ToolCallEnd`, `TurnStart`,
 * `TurnComplete`, `Edit`, `Commit`, `Compress`, `ErrorEvent`) retained so
 * that existing `repl.ts` callers keep working.
 *
 * Use the const-object form — TypeScript widens this into both a namespace
 * of string constants and a string-union type under the same name via
 * declaration merging below.
 */
export const HookEvent = {
  // Python-parity canonical events
  PreToolUse: "pre_tool_use",
  PostToolUse: "post_tool_use",
  ToolError: "tool_error",
  PreModel: "pre_model",
  PostModel: "post_model",
  ModelError: "model_error",
  PreAgent: "pre_agent",
  PostAgent: "post_agent",
  AgentError: "agent_error",
  SessionStart: "session_start",
  UserPromptSubmit: "user_prompt_submit",
  SessionEnd: "session_end",
  OnEvent: "on_event",
  PreCompact: "pre_compact",
  PermissionRequest: "permission_request",
  Notification: "notification",
  // Legacy (TS-only) values kept for back-compat with existing callers.
  ToolCallStart: "tool_call_start",
  ToolCallEnd: "tool_call_end",
  TurnStart: "turn_start",
  TurnComplete: "turn_complete",
  Edit: "edit",
  Commit: "commit",
  Compress: "compress",
  ErrorEvent: "error",
} as const;

// eslint-disable-next-line no-redeclare
export type HookEvent = (typeof HookEvent)[keyof typeof HookEvent];

/** Frozen set of every canonical event name. */
export const ALL_HOOK_EVENTS: ReadonlySet<string> = Object.freeze(
  new Set(Object.values(HookEvent)),
);

// ─── HookContext ───────────────────────────────────────────────────────────

/**
 * Normalized context passed to every hook callable. Not every field is
 * populated for every event — consult the event taxonomy: tool events
 * populate `toolName`/`toolInput`, model events populate `model`/`response`,
 * and so on. The mutable `toolInput` slot is rewritten in place when a
 * `modify` decision fires, so downstream hooks see the rewritten args.
 */
export interface HookContext {
  event: string;
  sessionId?: string;
  invocationId?: string;
  agentName?: string;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  toolOutput?: unknown;
  model?: string;
  request?: unknown;
  response?: unknown;
  userMessage?: string;
  error?: Error;
  state?: Record<string, unknown>;
  extra?: Record<string, unknown>;
}

// ─── HookDecision ──────────────────────────────────────────────────────────

export type HookAction =
  | "allow"
  | "deny"
  | "modify"
  | "replace"
  | "ask"
  | "inject";

export interface HookDecisionFields {
  action: HookAction;
  reason?: string;
  toolInput?: Record<string, unknown>;
  output?: unknown;
  prompt?: string;
  systemMessage?: string;
  metadata?: Record<string, unknown>;
}

/**
 * Structured decision returned from a hook callable. Use the static
 * constructors (`HookDecision.allow()`, `.deny()`, etc.) instead of
 * building instances directly.
 */
export class HookDecision {
  readonly action: HookAction;
  readonly reason: string;
  readonly toolInput: Record<string, unknown> | undefined;
  readonly output: unknown;
  readonly prompt: string;
  readonly systemMessage: string;
  readonly metadata: Readonly<Record<string, unknown>>;

  constructor(fields: HookDecisionFields) {
    this.action = fields.action;
    this.reason = fields.reason ?? "";
    this.toolInput = fields.toolInput ? { ...fields.toolInput } : undefined;
    this.output = fields.output;
    this.prompt = fields.prompt ?? "";
    this.systemMessage = fields.systemMessage ?? "";
    this.metadata = Object.freeze({ ...(fields.metadata ?? {}) });
    Object.freeze(this);
  }

  /** Pass-through — no opinion. */
  static allow(): HookDecision {
    return new HookDecision({ action: "allow" });
  }

  /** Block the wrapped call and surface `reason` to the LLM. */
  static deny(reason: string = "Denied by hook"): HookDecision {
    return new HookDecision({ action: "deny", reason });
  }

  /** Rewrite tool arguments. Only valid for `PreToolUse`. */
  static modify(toolInput: Record<string, unknown>): HookDecision {
    if (toolInput === null || typeof toolInput !== "object") {
      throw new TypeError(
        "HookDecision.modify requires an object of tool arguments",
      );
    }
    return new HookDecision({ action: "modify", toolInput: { ...toolInput } });
  }

  /** Short-circuit the wrapped call and return `output` instead. */
  static replace(output: unknown): HookDecision {
    return new HookDecision({ action: "replace", output });
  }

  /** Raise a permission request with `prompt`. */
  static ask(prompt: string): HookDecision {
    return new HookDecision({ action: "ask", prompt });
  }

  /** Append `systemMessage` to the system message channel. */
  static inject(systemMessage: string): HookDecision {
    return new HookDecision({ action: "inject", systemMessage });
  }

  get isAllow(): boolean {
    return this.action === "allow";
  }

  /** True if this decision short-circuits the call (deny/replace/ask). */
  get isTerminal(): boolean {
    return (
      this.action === "deny" ||
      this.action === "replace" ||
      this.action === "ask"
    );
  }

  /** True if this decision does not alter the wrapped call's output. */
  get isSideEffect(): boolean {
    return this.action === "allow" || this.action === "inject";
  }
}

// ─── HookMatcher ───────────────────────────────────────────────────────────

export interface HookMatcherOptions {
  event: string;
  /** Regex (anchored) matched against `ctx.toolName`. */
  toolName?: string;
  /** Per-key glob patterns matched against `ctx.toolInput` values. */
  args?: Record<string, string>;
  /** Optional predicate with full access to the context. */
  predicate?: (ctx: HookContext) => boolean;
}

/**
 * Filter controlling which contexts a hook callable sees. All layers are
 * ANDed: event equality, optional anchored regex on `toolName`, optional
 * per-key fnmatch globs on `toolInput`, and an optional predicate.
 */
export class HookMatcher {
  readonly event: string;
  readonly toolName: string | undefined;
  readonly args: Readonly<Record<string, string>>;
  readonly predicate: ((ctx: HookContext) => boolean) | undefined;

  private readonly toolNameRegex: RegExp | undefined;
  private readonly argRegexes: ReadonlyMap<string, RegExp>;

  constructor(options: HookMatcherOptions) {
    if (!ALL_HOOK_EVENTS.has(options.event)) {
      throw new Error(
        `Unknown hook event '${options.event}'. Valid events: ${[...ALL_HOOK_EVENTS].sort().join(", ")}`,
      );
    }
    this.event = options.event;
    this.toolName = options.toolName;
    this.args = Object.freeze({ ...(options.args ?? {}) });
    this.predicate = options.predicate;
    this.toolNameRegex = options.toolName
      ? new RegExp(`^(?:${options.toolName})$`)
      : undefined;
    const regexes = new Map<string, RegExp>();
    for (const [key, pattern] of Object.entries(this.args)) {
      regexes.set(key, fnmatchToRegExp(pattern));
    }
    this.argRegexes = regexes;
    Object.freeze(this);
  }

  /** Return true if `ctx` should trigger the associated hook. */
  matches(ctx: HookContext): boolean {
    if (ctx.event !== this.event) return false;

    if (this.toolNameRegex) {
      const name = ctx.toolName ?? "";
      if (!this.toolNameRegex.test(name)) return false;
    }

    if (this.argRegexes.size > 0) {
      const input = ctx.toolInput ?? {};
      for (const [key, rx] of this.argRegexes) {
        const value = input[key];
        if (value === undefined || value === null) return false;
        if (!rx.test(String(value))) return false;
      }
    }

    if (this.predicate) {
      try {
        if (!this.predicate(ctx)) return false;
      } catch {
        return false;
      }
    }

    return true;
  }

  /** Match every context for `event` (no additional filters). */
  static any(event: string): HookMatcher {
    return new HookMatcher({ event });
  }

  /** Shorthand for matching a specific tool by name with optional arg globs. */
  static forTool(
    event: string,
    toolName: string,
    args: Record<string, unknown> = {},
  ): HookMatcher {
    const stringArgs: Record<string, string> = {};
    for (const [key, value] of Object.entries(args)) {
      stringArgs[key] = String(value);
    }
    return new HookMatcher({ event, toolName, args: stringArgs });
  }
}

function fnmatchToRegExp(pattern: string): RegExp {
  let out = "";
  for (let i = 0; i < pattern.length; i++) {
    const ch = pattern[i];
    if (ch === "*") out += ".*";
    else if (ch === "?") out += ".";
    else if (ch === "[") {
      // pass-through character class until closing ']'
      let j = i + 1;
      while (j < pattern.length && pattern[j] !== "]") j++;
      if (j === pattern.length) {
        out += "\\[";
      } else {
        out += pattern.slice(i, j + 1);
        i = j;
      }
    } else if ("\\^$.|+(){}".includes(ch as string)) {
      out += "\\" + ch;
    } else {
      out += ch;
    }
  }
  return new RegExp(`^${out}$`);
}

// ─── SystemMessageChannel ──────────────────────────────────────────────────

export const SYSTEM_MESSAGE_STATE_KEY = "_adkf_hook_system_messages";

/**
 * Transient system-message queue backed by a session state object. Hooks
 * that return `HookDecision.inject(msg)` append to this channel; a
 * before-model pump drains and prepends them to the next LLM request.
 */
export class SystemMessageChannel {
  private readonly state: Record<string, unknown> | undefined;

  constructor(state: Record<string, unknown> | undefined) {
    this.state = state;
  }

  private bucket(create: boolean): string[] | undefined {
    if (!this.state) return undefined;
    let bucket = this.state[SYSTEM_MESSAGE_STATE_KEY] as string[] | undefined;
    if (!bucket) {
      if (!create) return undefined;
      bucket = [];
      this.state[SYSTEM_MESSAGE_STATE_KEY] = bucket;
    }
    return bucket;
  }

  append(message: string): void {
    if (!message) return;
    const bucket = this.bucket(true);
    bucket?.push(message);
  }

  peek(): string[] {
    const bucket = this.bucket(false);
    return bucket ? [...bucket] : [];
  }

  /** Return pending messages and clear the channel. */
  drain(): string[] {
    const bucket = this.bucket(false);
    if (!bucket || bucket.length === 0) return [];
    const drained = [...bucket];
    bucket.length = 0;
    return drained;
  }

  get pendingCount(): number {
    const bucket = this.bucket(false);
    return bucket?.length ?? 0;
  }
}

// ─── HookRegistry ──────────────────────────────────────────────────────────

export type HookCallable = (
  ctx: HookContext,
) => HookDecision | void | undefined | Promise<HookDecision | void | undefined>;

export interface HookEntry {
  matcher: HookMatcher;
  fn?: HookCallable;
  command?: string;
  name: string;
  timeout: number;
  blocking: boolean;
  metadata: Readonly<Record<string, unknown>>;
}

export interface HookOnOptions {
  match?: HookMatcher;
  name?: string;
}

export interface HookShellOptions extends HookOnOptions {
  /** Maximum execution time (seconds). */
  timeout?: number;
  /** Await the subprocess before continuing. Defaults to false. */
  blocking?: boolean;
}

/** Back-compat legacy shell-only alias, kept so old code keeps compiling. */
export interface HookSpec {
  event: HookEvent;
  command: string;
}

/**
 * User-facing registry of hook callables and shell commands. Entries are
 * event-partitioned internally for O(1) dispatch. The registry supports
 * both the new Python-parity API (callable hooks + structured decisions)
 * and the legacy shell-based `.fire(event, vars)` pipeline used by the
 * REPL.
 */
export class HookRegistry {
  private readonly entriesByEvent = new Map<string, HookEntry[]>();
  readonly workspace: string | undefined;

  constructor(workspace?: string) {
    this.workspace = workspace;
  }

  // ------------------------------------------------------------ registration

  /**
   * Register a hook for `event`. Accepts either a callable returning a
   * `HookDecision` (new API) or a shell-command string (legacy API — same
   * as calling `.shell(event, cmd)`).
   */
  on(event: HookEvent, fn: HookCallable, opts?: HookOnOptions): this;
  on(event: HookEvent, command: string, opts?: HookShellOptions): this;
  on(
    event: HookEvent,
    fnOrCommand: HookCallable | string,
    opts: HookOnOptions & HookShellOptions = {},
  ): this {
    if (typeof fnOrCommand === "string") {
      return this.shell(event, fnOrCommand, opts);
    }
    const matcher = opts.match ?? HookMatcher.any(event);
    if (matcher.event !== event) {
      throw new Error(
        `HookMatcher event '${matcher.event}' must equal '${event}'`,
      );
    }
    const entry: HookEntry = {
      matcher,
      fn: fnOrCommand,
      name: opts.name ?? fnOrCommand.name ?? "hook",
      timeout: 30,
      blocking: true,
      metadata: Object.freeze({}),
    };
    this.append(event, entry);
    return this;
  }

  /** Register a shell-command hook for `event`. */
  shell(event: HookEvent, command: string, opts: HookShellOptions = {}): this {
    const matcher = opts.match ?? HookMatcher.any(event);
    if (matcher.event !== event) {
      throw new Error(
        `HookMatcher event '${matcher.event}' must equal '${event}'`,
      );
    }
    const entry: HookEntry = {
      matcher,
      command,
      name: opts.name ?? "shell_hook",
      timeout: opts.timeout ?? 30,
      blocking: opts.blocking ?? false,
      metadata: Object.freeze({}),
    };
    this.append(event, entry);
    return this;
  }

  private append(event: string, entry: HookEntry): void {
    let list = this.entriesByEvent.get(event);
    if (!list) {
      list = [];
      this.entriesByEvent.set(event, list);
    }
    list.push(entry);
  }

  // Legacy convenience wrappers kept for existing callers.
  onEdit(command: string): this {
    return this.shell(HookEvent.Edit, command);
  }
  onError(command: string): this {
    return this.shell(HookEvent.ErrorEvent, command);
  }
  onCommit(command: string): this {
    return this.shell(HookEvent.Commit, command);
  }
  onCompress(command: string): this {
    return this.shell(HookEvent.Compress, command);
  }

  /** Return a new registry containing entries from both sides. */
  merge(other: HookRegistry): HookRegistry {
    const merged = new HookRegistry(this.workspace ?? other.workspace);
    for (const [event, entries] of this.entriesByEvent) {
      merged.entriesByEvent.set(event, [...entries]);
    }
    for (const [event, entries] of other.entriesByEvent) {
      const existing = merged.entriesByEvent.get(event);
      if (existing) existing.push(...entries);
      else merged.entriesByEvent.set(event, [...entries]);
    }
    return merged;
  }

  // ------------------------------------------------------------ introspection

  /** Return a snapshot of entries registered for `event`. */
  entriesFor(event: HookEvent): readonly HookEntry[] {
    return [...(this.entriesByEvent.get(event) ?? [])];
  }

  /**
   * Back-compat listing of shell entries. Mirrors the old `list()` surface
   * that predated callable hooks — callable entries are excluded.
   */
  list(event?: HookEvent): readonly HookSpec[] {
    const out: HookSpec[] = [];
    const events = event
      ? [event]
      : ([...this.entriesByEvent.keys()] as HookEvent[]);
    for (const ev of events) {
      for (const entry of this.entriesByEvent.get(ev) ?? []) {
        if (entry.command !== undefined) {
          out.push({ event: ev, command: entry.command });
        }
      }
    }
    return out;
  }

  get registeredEvents(): readonly string[] {
    return [...this.entriesByEvent.keys()];
  }

  // ------------------------------------------------------------ dispatch

  /**
   * Run every matching entry for `ctx.event` and return the collapsed
   * decision. Entries run in registration order. Iteration stops at the
   * first terminal decision (`deny` / `replace` / `ask`). Non-terminal
   * decisions are folded: `modify` rewrites `ctx.toolInput` in place so
   * downstream hooks see the rewritten args, and `inject` is collected and
   * attached to the final decision's metadata under `pendingInjects` so the
   * plugin can drain it to the SystemMessageChannel.
   */
  async dispatch(ctx: HookContext): Promise<HookDecision> {
    const entries = this.entriesByEvent.get(ctx.event);
    if (!entries || entries.length === 0) return HookDecision.allow();

    let final: HookDecision = HookDecision.allow();
    const pendingInjects: string[] = [];

    for (const entry of entries) {
      if (!entry.matcher.matches(ctx)) continue;
      const decision = await this.runEntry(entry, ctx);
      if (decision.isAllow) continue;
      if (decision.action === "inject") {
        pendingInjects.push(decision.systemMessage);
        continue;
      }
      if (decision.action === "modify") {
        if (decision.toolInput && ctx.toolInput) {
          for (const k of Object.keys(ctx.toolInput)) delete ctx.toolInput[k];
          Object.assign(ctx.toolInput, decision.toolInput);
        } else if (decision.toolInput) {
          ctx.toolInput = { ...decision.toolInput };
        }
        continue;
      }
      final = decision;
      break;
    }

    if (pendingInjects.length > 0) {
      final = new HookDecision({
        action: final.action,
        reason: final.reason,
        toolInput: final.toolInput,
        output: final.output,
        prompt: final.prompt,
        systemMessage: final.systemMessage,
        metadata: { ...final.metadata, pendingInjects },
      });
    }
    return final;
  }

  private async runEntry(
    entry: HookEntry,
    ctx: HookContext,
  ): Promise<HookDecision> {
    if (entry.command !== undefined) {
      return this.runShell(entry, ctx);
    }
    if (!entry.fn) return HookDecision.allow();
    try {
      const result = await entry.fn(ctx);
      if (result === undefined || result === null) return HookDecision.allow();
      if (!(result instanceof HookDecision)) {
        return HookDecision.deny(
          `hook '${entry.name}' must return HookDecision, got ${typeof result}`,
        );
      }
      return result;
    } catch (exc) {
      const reason = exc instanceof Error ? exc.message : String(exc);
      return HookDecision.deny(`hook '${entry.name}' raised: ${reason}`);
    }
  }

  private async runShell(
    entry: HookEntry,
    ctx: HookContext,
  ): Promise<HookDecision> {
    if (entry.command === undefined) return HookDecision.allow();
    const command = renderShellCommand(entry.command, ctx);
    const env = buildShellEnv(ctx, this.workspace);

    const exec = (): Promise<number> =>
      new Promise((resolve) => {
        const child = spawn("bash", ["-c", command], {
          cwd: this.workspace,
          env,
          stdio: "ignore",
        });
        const timer = setTimeout(() => {
          try {
            child.kill();
          } catch {
            /* ignore */
          }
          resolve(-1);
        }, entry.timeout * 1000);
        child.on("close", (code) => {
          clearTimeout(timer);
          resolve(code ?? 0);
        });
        child.on("error", () => {
          clearTimeout(timer);
          resolve(-2);
        });
      });

    if (entry.blocking) {
      const exitCode = await exec();
      return new HookDecision({
        action: "allow",
        metadata: { shellExitCode: exitCode, shellCommand: command },
      });
    }
    // Fire-and-forget
    void exec();
    return HookDecision.allow();
  }

  // ------------------------------------------------------------ legacy API

  /**
   * Legacy shell-fire entry point used by the REPL. Substitutes `{key}`
   * placeholders against `vars` and awaits every matching shell hook for
   * `event`. Callable hooks are ignored — use `.dispatch()` for those.
   */
  async fire(
    event: HookEvent,
    vars: Record<string, string> = {},
  ): Promise<void> {
    const entries = this.entriesByEvent.get(event);
    if (!entries) return;
    const shells = entries.filter(
      (e): e is HookEntry & { command: string } => e.command !== undefined,
    );
    await Promise.all(
      shells.map(
        (entry) =>
          new Promise<void>((resolve) => {
            const cmd = entry.command.replace(
              /\{(\w+)\}/g,
              (_: string, k: string) => vars[k] ?? "",
            );
            const child = spawn("bash", ["-c", cmd], {
              cwd: this.workspace,
              stdio: "ignore",
            });
            child.on("close", () => resolve());
            child.on("error", () => resolve());
          }),
      ),
    );
  }
}

function renderShellCommand(template: string, ctx: HookContext): string {
  const fields: Record<string, string> = {
    event: ctx.event,
    tool_name: ctx.toolName ?? "",
    agent_name: ctx.agentName ?? "",
    session_id: ctx.sessionId ?? "",
    invocation_id: ctx.invocationId ?? "",
    user_message: ctx.userMessage ?? "",
    model: ctx.model ?? "",
    error: ctx.error ? String(ctx.error) : "",
  };
  const toolInput = ctx.toolInput ?? {};
  for (const [k, v] of Object.entries(toolInput)) {
    if (!(k in fields)) fields[k] = String(v);
  }

  let out = template.replace(
    /\{tool_input\[([^\]]+)\]\}/g,
    (_m: string, key: string) => shellQuote(String(toolInput[key] ?? "")),
  );
  out = out.replace(
    /\{([A-Za-z_][A-Za-z0-9_]*)\}/g,
    (_m: string, key: string) => shellQuote(fields[key] ?? ""),
  );
  return out;
}

function shellQuote(value: string): string {
  if (value === "") return "''";
  if (/^[A-Za-z0-9_\-./:=@%+,]+$/.test(value)) return value;
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function buildShellEnv(
  ctx: HookContext,
  workspace: string | undefined,
): Record<string, string | undefined> {
  const env: Record<string, string | undefined> = { ...process.env };
  env.ADKF_HOOK_EVENT = ctx.event;
  if (workspace) env.ADKF_HOOK_WORKSPACE = workspace;
  if (ctx.toolName) env.ADKF_HOOK_TOOL_NAME = ctx.toolName;
  if (ctx.agentName) env.ADKF_HOOK_AGENT_NAME = ctx.agentName;
  if (ctx.sessionId) env.ADKF_HOOK_SESSION_ID = ctx.sessionId;
  if (ctx.invocationId) env.ADKF_HOOK_INVOCATION_ID = ctx.invocationId;
  if (ctx.userMessage) env.ADKF_HOOK_USER_MESSAGE = ctx.userMessage;
  return env;
}

// ─── CommandRegistry ───────────────────────────────────────────────────────

export type CommandHandler = (args: string) => string | Promise<string>;

export interface CommandRegistration {
  name: string;
  handler: CommandHandler;
  description?: string;
}

/** Slash command registry for the REPL. */
export class CommandRegistry {
  readonly prefix: string;
  private readonly commands = new Map<string, CommandRegistration>();

  constructor(prefix = "/") {
    this.prefix = prefix;
  }

  register(name: string, handler: CommandHandler, description?: string): this {
    this.commands.set(name, { name, handler, description });
    return this;
  }

  isCommand(text: string): boolean {
    return text.startsWith(this.prefix);
  }

  /** Parse and execute a `/command rest` line. Returns the handler output. */
  async dispatch(text: string): Promise<string | null> {
    if (!this.isCommand(text)) return null;
    const stripped = text.slice(this.prefix.length).trim();
    const [name, ...rest] = stripped.split(/\s+/);
    const cmd = this.commands.get(name);
    if (!cmd) return `Unknown command: ${this.prefix}${name}`;
    return await cmd.handler(rest.join(" "));
  }

  list(): readonly CommandRegistration[] {
    return [...this.commands.values()];
  }
}

// ─── ToolPolicy: per-tool error recovery ───────────────────────────────────

export type ToolAction = "retry" | "skip" | "ask" | "propagate";

export interface ToolRule {
  action: ToolAction;
  maxAttempts?: number;
  backoff?: number;
  fallback?: string;
  handler?: (toolName: string, error: Error) => boolean | Promise<boolean>;
}

/**
 * Per-tool error recovery policy with backoff and EventBus integration.
 * Unlike `ErrorStrategy` (which maps tool sets → action), this is a
 * fluent builder with per-tool granularity.
 */
export class ToolPolicy {
  readonly default: ToolAction;
  private readonly rules = new Map<string, ToolRule>();
  private bus?: EventBus;

  constructor(opts: { default?: ToolAction } = {}) {
    this.default = opts.default ?? "propagate";
  }

  retry(toolName: string, opts: { maxAttempts?: number; backoff?: number } = {}): this {
    this.rules.set(toolName, {
      action: "retry",
      maxAttempts: opts.maxAttempts ?? 3,
      backoff: opts.backoff ?? 1.0,
    });
    return this;
  }

  skip(toolName: string, opts: { fallback?: string } = {}): this {
    this.rules.set(toolName, { action: "skip", fallback: opts.fallback });
    return this;
  }

  ask(toolName: string, handler: ToolRule["handler"]): this {
    this.rules.set(toolName, { action: "ask", handler });
    return this;
  }

  withBus(bus: EventBus): this {
    this.bus = bus;
    return this;
  }

  ruleFor(toolName: string): ToolRule {
    return this.rules.get(toolName) ?? { action: this.default };
  }

  /** Build an after-tool callback that applies the policy on errors. */
  afterToolHook(): (toolName: string, error: Error | null, result: unknown) => Promise<unknown> {
    return async (toolName, error, result) => {
      if (!error) return result;
      const rule = this.ruleFor(toolName);
      this.bus?.emit({
        kind: "tool_call_error",
        toolName,
        error: error.message,
        timestamp: Date.now(),
      });
      switch (rule.action) {
        case "skip":
          return rule.fallback ?? "Tool call failed and was skipped.";
        case "ask": {
          const ok = await rule.handler?.(toolName, error);
          if (ok) return result;
          throw error;
        }
        case "retry":
          // Caller is responsible for the actual retry loop; this hook
          // simply re-throws so the caller knows to retry.
          throw error;
        default:
          throw error;
      }
    };
  }
}

// ─── TaskRegistry: lightweight background-task tracker ─────────────────────

export interface TaskRecord {
  id: string;
  name: string;
  promise: Promise<unknown>;
  status: "pending" | "running" | "done" | "error";
  result?: unknown;
  error?: string;
  startedAt: number;
  endedAt?: number;
}

export class TaskRegistry {
  readonly maxTasks: number;
  private readonly tasks = new Map<string, TaskRecord>();
  private nextId = 1;

  constructor(opts: { maxTasks?: number } = {}) {
    this.maxTasks = opts.maxTasks ?? 10;
  }

  launch<T>(name: string, fn: () => Promise<T>): TaskRecord {
    if ([...this.tasks.values()].filter((t) => t.status === "running").length >= this.maxTasks) {
      throw new Error(`Max tasks reached (${this.maxTasks})`);
    }
    const id = `task-${this.nextId++}`;
    const promise = fn();
    const rec: TaskRecord = {
      id,
      name,
      promise,
      status: "running",
      startedAt: Date.now(),
    };
    this.tasks.set(id, rec);
    promise.then(
      (result) => {
        rec.status = "done";
        rec.result = result;
        rec.endedAt = Date.now();
      },
      (error) => {
        rec.status = "error";
        rec.error = (error as Error).message;
        rec.endedAt = Date.now();
      },
    );
    return rec;
  }

  get(id: string): TaskRecord | undefined {
    return this.tasks.get(id);
  }

  list(): readonly TaskRecord[] {
    return [...this.tasks.values()];
  }

  cancel(id: string): boolean {
    const t = this.tasks.get(id);
    if (!t || t.status !== "running") return false;
    // JavaScript promises aren't natively cancellable; we just mark
    // the record. Real cancellation requires the task to honor a token.
    t.status = "error";
    t.error = "cancelled";
    t.endedAt = Date.now();
    return true;
  }
}

/** Build LLM-callable tools that wrap a TaskRegistry. */
export function taskTools(registry: TaskRegistry): HarnessTool[] {
  return [
    asTool("launch_task", async (args: { name: string; command?: string }) => {
      // Tool surface intentionally simple — real launchers should be
      // wired in by the caller via `registry.launch(...)`.
      const rec = registry.launch(args.name, async () => args.command ?? args.name);
      return { id: rec.id, status: rec.status };
    }),
    asTool("check_task", async (args: { id: string }) => {
      const t = registry.get(args.id);
      if (!t) return { error: `No task '${args.id}'` };
      return {
        id: t.id,
        name: t.name,
        status: t.status,
        result: t.result,
        error: t.error,
      };
    }),
    asTool("list_tasks", async () => {
      return registry.list().map((t) => ({ id: t.id, name: t.name, status: t.status }));
    }),
  ];
}

// ─── TaskLedger: dispatch/join bridge with EventBus integration ────────────

/**
 * Bridges `dispatch()`/`join()` expression primitives to tool-level task
 * management. The LLM can launch, check, list, and cancel tasks.
 */
export class TaskLedger {
  readonly registry: TaskRegistry;
  private bus?: EventBus;

  constructor(opts: { maxTasks?: number } = {}) {
    this.registry = new TaskRegistry(opts);
  }

  withBus(bus: EventBus): this {
    this.bus = bus;
    return this;
  }

  tools(): HarnessTool[] {
    const base = taskTools(this.registry);
    if (!this.bus) return base;
    // Wrap each tool to also emit events.
    return base.map((tool) =>
      asTool(tool.toolName, async (args: unknown) => {
        this.bus?.emit({
          kind: "tool_call_start",
          toolName: tool.toolName,
          args: args as Record<string, unknown>,
          timestamp: Date.now(),
        });
        const result = await tool(args);
        this.bus?.emit({
          kind: "tool_call_end",
          toolName: tool.toolName,
          result,
          timestamp: Date.now(),
        });
        return result;
      }),
    );
  }
}
