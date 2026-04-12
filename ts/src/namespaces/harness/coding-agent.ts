/**
 * `codingAgent` preset — the "build your own Claude Code in 5 lines" entry
 * point. Bundles every primitive a coding agent typically wants:
 *
 *   • Workspace tools (read_file, write_file, edit_file, glob, grep, ls, bash)
 *   • Web fetch + search
 *   • Process lifecycle (start_process, check_process, …)
 *   • Git tools + checkpointer + worktree manager
 *   • Polyglot code executor (`run_code` over python/node/ts/bash)
 *   • Todo list + plan mode + ask-user (the agent self-management trio)
 *   • Project memory (`CLAUDE.md`-style) + usage tracker + event bus
 *   • Sandbox + permissions wired to "ask before mutating"
 *
 * The intent is *zero ceremony*: the harness author writes
 * `H.codingAgent("/repo")` and gets back a ready-to-use bundle. Each piece
 * is still individually accessible on the returned object so the author
 * can swap or augment it.
 */

import { ArtifactStore } from "./artifacts.js";
import { askUserTool, PlanMode, TodoStore, WorktreeManager, type AskUserHandler } from "./agent-tools.js";
import { CodeExecutor, type CodeExecutorOptions } from "./code-executor.js";
import { EventBus } from "./events.js";
import { GitCheckpointer, gitTools } from "./git.js";
import { ProjectMemory } from "./memory.js";
import { ApprovalMemory, PermissionPolicy } from "./permissions.js";
import { processTools } from "./processes.js";
import { SandboxPolicy } from "./sandbox.js";
import { UsageTracker } from "./usage.js";
import { webTools } from "./web.js";
import { workspaceTools } from "./workspace.js";
import type { HarnessTool } from "./types.js";

export interface CodingAgentOptions {
  /** Allow writing & shell? Defaults true. Set false for "research only". */
  allowMutations?: boolean;
  /** Allow network egress? Defaults true. */
  allowNetwork?: boolean;
  /** Optional UI hook for `ask_user_question`. */
  onAskUser?: AskUserHandler;
  /** Path to a markdown memory file (defaults to `<workspace>/CLAUDE.md`). */
  memoryPath?: string;
  /** Hard cap on bash/process/code-executor output capture (bytes). */
  maxOutputBytes?: number;
  /** Override interpreters for the polyglot code executor. */
  interpreters?: CodeExecutorOptions["interpreters"];
  /** Set false to skip git tooling (useful for non-git workspaces). */
  enableGit?: boolean;
}

export interface CodingAgentBundle {
  /** Sandboxed root path (the workspace). */
  workspace: string;
  /** Every LLM-callable tool, ready to plug into `Agent.tools(...)`. */
  tools: HarnessTool[];
  /** Underlying primitives, exposed for swap-out / introspection. */
  sandbox: SandboxPolicy;
  permissions: PermissionPolicy;
  approvalMemory: ApprovalMemory;
  bus: EventBus;
  usage: UsageTracker;
  memory: ProjectMemory;
  artifacts: ArtifactStore;
  todos: TodoStore;
  planMode: PlanMode;
  worktrees: WorktreeManager | null;
  git: GitCheckpointer | null;
  executor: CodeExecutor;
}

/**
 * Build a fully-wired coding-agent bundle. Idempotent: calling it twice
 * with the same workspace gives two independent bundles (no shared state).
 *
 * Example
 * -------
 * ```typescript
 * import { Agent, H } from "adk-fluent-ts";
 *
 * const harness = H.codingAgent("/repo", { onAskUser: cliPrompt });
 * const agent = new Agent("coder", "gemini-2.5-pro")
 *   .instruct("You are a senior engineer. Use the provided tools.")
 *   .tools(harness.tools)
 *   .build();
 * ```
 */
export function codingAgent(workspace: string, opts: CodingAgentOptions = {}): CodingAgentBundle {
  const allowMutations = opts.allowMutations ?? true;
  const allowNetwork = opts.allowNetwork ?? true;
  const enableGit = opts.enableGit ?? true;
  const maxOutputBytes = opts.maxOutputBytes ?? 200_000;

  const sandbox = new SandboxPolicy({
    workspace,
    allowShell: allowMutations,
    allowNetwork,
    maxOutputBytes,
  });

  // Permission defaults model "Claude Code's safe default":
  //   - Read tools auto-allow.
  //   - Write/exec tools ask the embedding application.
  //   - Network goes through ask too if allowNetwork is true.
  const permissions = new PermissionPolicy({
    allow: ["read_file", "ls", "glob", "grep", "git_status", "git_diff", "git_log", "git_branch"],
    ask: allowMutations
      ? [
          "write_file",
          "edit_file",
          "bash",
          "run_code",
          "git_commit",
          "start_process",
          "stop_process",
          "enter_worktree",
          "exit_worktree",
        ]
      : [],
    deny: allowMutations ? [] : ["write_file", "edit_file", "bash", "run_code", "git_commit"],
  });
  const approvalMemory = new ApprovalMemory();

  const bus = new EventBus();
  const usage = new UsageTracker();
  const memory = new ProjectMemory(opts.memoryPath ?? `${workspace}/CLAUDE.md`);
  const artifacts = new ArtifactStore(`${workspace}/.harness/artifacts`);
  const todos = new TodoStore();
  const planMode = new PlanMode();
  const worktrees = enableGit ? new WorktreeManager(workspace) : null;
  const git = enableGit ? new GitCheckpointer(workspace) : null;

  const executor = new CodeExecutor(sandbox, {
    interpreters: opts.interpreters,
    onOutput: (chunk) => bus.emit({ kind: "text", text: chunk, timestamp: Date.now() }),
  });

  const tools: HarnessTool[] = [
    ...workspaceTools(sandbox, { readOnly: !allowMutations }),
    ...(allowNetwork ? webTools(sandbox) : []),
    ...(allowMutations ? processTools(sandbox) : []),
    ...(enableGit ? gitTools(workspace, { allowShell: allowMutations }) : []),
    ...executor.tools(),
    ...todos.tools(),
    ...planMode.tools(),
    ...(worktrees?.tools() ?? []),
    askUserTool(opts.onAskUser),
  ];

  return {
    workspace,
    tools,
    sandbox,
    permissions,
    approvalMemory,
    bus,
    usage,
    memory,
    artifacts,
    todos,
    planMode,
    worktrees,
    git,
    executor,
  };
}
