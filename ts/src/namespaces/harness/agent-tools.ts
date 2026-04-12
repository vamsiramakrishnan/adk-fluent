/**
 * Agent self-management tools — TodoWrite, plan mode, ask-user, worktrees.
 *
 * These mirror the equivalents in claude-code's `src/tools/`. They're the
 * "ceremony reducers" that turn a generic LLM into a coding agent: the
 * model uses `todo_write` to track its own task list, `enter_plan_mode` to
 * propose changes before touching files, and `enter_worktree` to isolate a
 * speculative refactor on its own branch.
 *
 * None of these touch the file system beyond `git worktree`, so they're
 * safe to add to any harness regardless of `SandboxPolicy.allowShell`.
 */

import { execFileSync } from "node:child_process";
import { asTool, type HarnessTool } from "./types.js";

// ─── TodoStore ─────────────────────────────────────────────────────────────

export type TodoStatus = "pending" | "in_progress" | "completed";

export interface TodoItem {
  content: string;
  activeForm: string;
  status: TodoStatus;
}

/**
 * In-memory todo list. The model owns the list; the harness only persists
 * it across tool calls. Mirrors Claude Code's `TodoWriteTool` semantics:
 * one task in_progress at a time, completed tasks stay visible until the
 * model overwrites the list.
 */
export class TodoStore {
  private items: TodoItem[] = [];

  list(): readonly TodoItem[] {
    return this.items;
  }

  /** Replace the entire list. The model always sends the full snapshot. */
  replace(items: TodoItem[]): void {
    // Shallow-validate. Cheap and the LLM will see the error.
    const inProgress = items.filter((t) => t.status === "in_progress").length;
    if (inProgress > 1) {
      throw new Error(`TodoStore: at most one task can be 'in_progress' (got ${inProgress})`);
    }
    this.items = items.map((t) => ({ ...t }));
  }

  clear(): void {
    this.items = [];
  }

  tools(): HarnessTool[] {
    return [
      asTool("todo_write", async (args: { todos: TodoItem[] }) => {
        this.replace(args.todos);
        return { count: this.items.length, items: this.items };
      }),
      asTool("todo_read", async () => ({ items: this.items })),
    ];
  }
}

// ─── PlanMode ──────────────────────────────────────────────────────────────

export type PlanModeState = "off" | "planning" | "executing";

/**
 * Plan-mode latch. When ON, the harness should reject every write/edit
 * tool call and surface the plan to the user instead. The harness wires
 * the latch into `PermissionPolicy` (or a `ToolPolicy` "ask" action).
 */
export class PlanMode {
  private state: PlanModeState = "off";
  private plan = "";

  get current(): PlanModeState {
    return this.state;
  }

  get currentPlan(): string {
    return this.plan;
  }

  /** Returns true iff the named tool is a write/edit/exec tool. */
  static isMutating(toolName: string): boolean {
    return MUTATING_TOOLS.has(toolName);
  }

  enter(): void {
    this.state = "planning";
    this.plan = "";
  }

  exit(plan: string): void {
    this.state = "executing";
    this.plan = plan;
  }

  reset(): void {
    this.state = "off";
    this.plan = "";
  }

  tools(): HarnessTool[] {
    return [
      asTool("enter_plan_mode", async () => {
        this.enter();
        return { state: this.state };
      }),
      asTool("exit_plan_mode", async (args: { plan: string }) => {
        this.exit(args.plan);
        return { state: this.state, plan: this.plan };
      }),
    ];
  }
}

const MUTATING_TOOLS = new Set([
  "write_file",
  "edit_file",
  "bash",
  "run_code",
  "git_commit",
  "start_process",
]);

// ─── AskUserQuestion ───────────────────────────────────────────────────────

export type AskUserHandler = (question: string, options?: string[]) => Promise<string>;

/**
 * Ask-user tool. The handler is supplied by the embedding application:
 * a CLI harness might prompt on stdin, a web UI might post a question to
 * a websocket. The default handler throws so SDK consumers don't silently
 * hang on a missing UI.
 */
export function askUserTool(handler?: AskUserHandler): HarnessTool {
  const fn =
    handler ??
    (async () => {
      throw new Error(
        "askUserTool: no handler installed. Pass H.askUser((q) => Promise<answer>) when wiring the harness.",
      );
    });
  return asTool("ask_user_question", async (args: { question: string; options?: string[] }) => {
    const answer = await fn(args.question, args.options);
    return { answer };
  });
}

// ─── Git worktree ──────────────────────────────────────────────────────────

/**
 * Git worktree manager. Spawns isolated worktrees of the workspace so the
 * agent can experiment on a branch without polluting the main checkout.
 * Each worktree gets its own filesystem path; the harness creates a
 * matching `SandboxPolicy` and `workspaceTools` for it before handing back
 * to the model.
 */
export class WorktreeManager {
  readonly workspace: string;
  private readonly created = new Map<string, string>();

  constructor(workspace: string) {
    this.workspace = workspace;
  }

  /** Create a new worktree on `branch`, rooted at `path`. */
  enter(opts: { branch: string; path: string; baseRef?: string }): string {
    const args = ["worktree", "add"];
    if (opts.baseRef) args.push("-b", opts.branch, opts.path, opts.baseRef);
    else args.push("-b", opts.branch, opts.path);
    execFileSync("git", args, { cwd: this.workspace, stdio: "pipe" });
    this.created.set(opts.branch, opts.path);
    return opts.path;
  }

  exit(branch: string, opts: { force?: boolean } = {}): void {
    const path = this.created.get(branch);
    if (!path) throw new Error(`No worktree for branch '${branch}'`);
    const args = ["worktree", "remove"];
    if (opts.force) args.push("--force");
    args.push(path);
    execFileSync("git", args, { cwd: this.workspace, stdio: "pipe" });
    this.created.delete(branch);
  }

  list(): string[] {
    return [...this.created.keys()];
  }

  tools(): HarnessTool[] {
    return [
      asTool("enter_worktree", async (args: { branch: string; path: string; baseRef?: string }) => {
        const path = this.enter(args);
        return { branch: args.branch, path };
      }),
      asTool("exit_worktree", async (args: { branch: string; force?: boolean }) => {
        this.exit(args.branch, { force: args.force });
        return { ok: true };
      }),
      asTool("list_worktrees", async () => ({ branches: this.list() })),
    ];
  }
}
