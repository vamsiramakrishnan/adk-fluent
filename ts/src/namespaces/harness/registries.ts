/**
 * Hook registry, command registry, tool policy, task ledger, and task
 * registry. Mirrors `_harness/_hooks.py`, `_commands.py`, `_tool_policy.py`,
 * `_task_ledger.py`, `_tasks.py`.
 */

import { spawn } from "node:child_process";
import { asTool, type HarnessTool } from "./types.js";
import type { EventBus } from "./events.js";

// ─── HookRegistry ──────────────────────────────────────────────────────────

export type HookEvent =
  | "tool_call_start"
  | "tool_call_end"
  | "turn_start"
  | "turn_complete"
  | "edit"
  | "error"
  | "commit"
  | "compress";

export interface HookSpec {
  event: HookEvent;
  command: string;
}

/**
 * Registry of user-defined shell commands that fire on harness events.
 * Hooks run in the workspace cwd. Output is captured to stderr.
 */
export class HookRegistry {
  private readonly hooks: HookSpec[] = [];
  readonly workspace?: string;

  constructor(workspace?: string) {
    this.workspace = workspace;
  }

  on(event: HookEvent, command: string): this {
    this.hooks.push({ event, command });
    return this;
  }

  onEdit(command: string): this {
    return this.on("edit", command);
  }

  onError(command: string): this {
    return this.on("error", command);
  }

  onCommit(command: string): this {
    return this.on("commit", command);
  }

  onCompress(command: string): this {
    return this.on("compress", command);
  }

  list(event?: HookEvent): readonly HookSpec[] {
    return event ? this.hooks.filter((h) => h.event === event) : this.hooks;
  }

  /** Fire all hooks for `event`, substituting `{key}` placeholders. */
  async fire(event: HookEvent, vars: Record<string, string> = {}): Promise<void> {
    const matches = this.hooks.filter((h) => h.event === event);
    await Promise.all(matches.map((h) => this.runOne(h, vars)));
  }

  private runOne(hook: HookSpec, vars: Record<string, string>): Promise<void> {
    return new Promise((resolve) => {
      const cmd = hook.command.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
      const child = spawn("bash", ["-c", cmd], { cwd: this.workspace, stdio: "ignore" });
      child.on("close", () => resolve());
      child.on("error", () => resolve());
    });
  }
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
