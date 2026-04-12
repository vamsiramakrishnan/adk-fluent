/**
 * H — Harness namespace. The TypeScript port of `python/src/adk_fluent/_harness/_namespace.py`.
 *
 * `H` is a purely static namespace. Every method returns a composable
 * building block. Combine them to construct your harness:
 *
 * ```typescript
 * import { Agent, H } from "adk-fluent-ts";
 *
 * const harness = new Agent("coder", "gemini-2.5-pro")
 *   .tools([
 *     ...H.workspace("/project"),
 *     ...H.web(),
 *     ...H.processes("/project"),
 *   ]);
 *
 * const config = H.config({
 *   permissions: H.autoAllow("read_file").merge(H.askBefore("bash")),
 *   sandbox: H.workspaceOnly("/project"),
 *   usage: H.usage(),
 *   memory: H.memory("/project/.agent-memory.md"),
 *   onError: H.onError({ retry: ["bash"], skip: ["glob"] }),
 * });
 * ```
 *
 * Naming: Python uses snake_case (`auto_allow`, `workspace_only`,
 * `tool_policy`); TypeScript uses camelCase (`autoAllow`,
 * `workspaceOnly`, `toolPolicy`). The semantics are identical.
 *
 * Stubbed-out features (not yet ported):
 * - `H.notebook(...)` — Jupyter notebook tools (requires .ipynb parser)
 * - `H.mcp(...)` / `H.mcpFromConfig(...)` — MCP toolset loaders
 *   (waiting for `@google/adk` to ship its MCP wiring)
 * - `H.manifold(...)` — capability discovery (requires SkillRegistry port)
 *
 * Calling these stubs throws a clear "not yet ported" error.
 */

import {
  PlanMode,
  TodoStore,
  WorktreeManager,
  askUserTool,
  type AskUserHandler,
} from "./agent-tools.js";
import { ArtifactStore } from "./artifacts.js";
import { CodeExecutor, type CodeExecutorOptions } from "./code-executor.js";
import { codingAgent, type CodingAgentBundle, type CodingAgentOptions } from "./coding-agent.js";
import { HarnessConfig, type HarnessConfigOptions } from "./config.js";
import { ErrorStrategy, type ErrorStrategyOptions } from "./error-strategy.js";
import {
  EventBus,
  EventDispatcher,
  SessionTape,
  type EventBusOptions,
  type SessionTapeOptions,
} from "./events.js";
import { GitCheckpointer, gitTools } from "./git.js";
import {
  BudgetMonitor,
  CancellationToken,
  ContextCompressor,
  ForkManager,
  type ContextCompressorOptions,
  type ForkManagerOptions,
} from "./lifecycle.js";
import { MemoryHierarchy, ProjectMemory, type ProjectMemoryOptions } from "./memory.js";
import { ApprovalMemory, PermissionPolicy } from "./permissions.js";
import { processTools } from "./processes.js";
import {
  CommandRegistry,
  HookRegistry,
  TaskLedger,
  TaskRegistry,
  ToolPolicy,
  taskTools,
} from "./registries.js";
import { JsonRenderer, PlainRenderer, RichRenderer, type RendererOptions } from "./renderer.js";
import { HarnessRepl, type ReplConfig } from "./repl.js";
import { SandboxPolicy, type SandboxPolicyOptions } from "./sandbox.js";
import { StreamingBash } from "./streaming.js";
import { UsageTracker, type UsageTrackerOptions } from "./usage.js";
import { webTools, type WebOptions } from "./web.js";
import { workspaceTools, type WorkspaceOptions } from "./workspace.js";
import type { HarnessTool } from "./types.js";

/**
 * Harness namespace — building blocks for AI coding harnesses.
 *
 * Every method is static; instantiating `H` is not supported.
 */
export class H {
  private constructor() {
    throw new Error("H is a static namespace; do not instantiate.");
  }

  // ─── Workspace tools ─────────────────────────────────────────────────────

  static workspace(path: string, opts: WorkspaceOptions = {}): HarnessTool[] {
    const sandbox = new SandboxPolicy({
      workspace: path,
      allowShell: true,
      allowNetwork: true,
    });
    return workspaceTools(sandbox, opts);
  }

  // ─── Permission policies ─────────────────────────────────────────────────

  static askBefore(...toolNames: string[]): PermissionPolicy {
    return new PermissionPolicy({ ask: toolNames });
  }

  static autoAllow(...toolNames: string[]): PermissionPolicy {
    return new PermissionPolicy({ allow: toolNames });
  }

  static deny(...toolNames: string[]): PermissionPolicy {
    return new PermissionPolicy({ deny: toolNames });
  }

  static allowPatterns(patterns: string[], mode: "glob" | "regex" = "glob"): PermissionPolicy {
    return new PermissionPolicy({ allowPatterns: patterns, patternMode: mode });
  }

  static denyPatterns(patterns: string[], mode: "glob" | "regex" = "glob"): PermissionPolicy {
    return new PermissionPolicy({ denyPatterns: patterns, patternMode: mode });
  }

  static approvalMemory(): ApprovalMemory {
    return new ApprovalMemory();
  }

  // ─── Sandbox policies ────────────────────────────────────────────────────

  static workspaceOnly(path?: string): SandboxPolicy {
    return new SandboxPolicy({ workspace: path });
  }

  static sandbox(opts: SandboxPolicyOptions = {}): SandboxPolicy {
    return new SandboxPolicy(opts);
  }

  // ─── Web tools ───────────────────────────────────────────────────────────

  static web(opts: WebOptions = {}): HarnessTool[] {
    const sandbox = new SandboxPolicy({ allowNetwork: true });
    return webTools(sandbox, opts);
  }

  // ─── Persistent memory ───────────────────────────────────────────────────

  static memory(path: string, opts: ProjectMemoryOptions = {}): ProjectMemory {
    return new ProjectMemory(path, opts);
  }

  static memoryHierarchy(paths: string[], stateKey = "project_memory"): MemoryHierarchy {
    return new MemoryHierarchy(paths, stateKey);
  }

  // ─── Token / cost tracking ───────────────────────────────────────────────

  static usage(opts: UsageTrackerOptions = {}): UsageTracker {
    return new UsageTracker(opts);
  }

  // ─── Process lifecycle ───────────────────────────────────────────────────

  static processes(path?: string, opts: { allowShell?: boolean } = {}): HarnessTool[] {
    const sandbox = new SandboxPolicy({
      workspace: path,
      allowShell: opts.allowShell ?? true,
    });
    return processTools(sandbox);
  }

  // ─── Streaming bash ─────────────────────────────────────────────────────

  /**
   * Build a `StreamingBash` executor for real-time command output.
   *
   * Use this when you want to consume stdout/stderr as it arrives instead
   * of waiting for the command to finish — long-running builds, dev
   * servers, or test runs where progressive feedback matters.
   *
   * ```ts
   * const streamer = H.streamingBash(H.workspaceOnly("/project"));
   * for await (const chunk of streamer.run("npm test")) {
   *   process.stdout.write(chunk);
   * }
   * ```
   */
  static streamingBash(sandbox: SandboxPolicy): StreamingBash {
    return new StreamingBash(sandbox);
  }

  // ─── Error strategy ──────────────────────────────────────────────────────

  static onError(opts: ErrorStrategyOptions = {}): ErrorStrategy {
    return new ErrorStrategy(opts);
  }

  // ─── Interrupt & resume ──────────────────────────────────────────────────

  static cancellationToken(): CancellationToken {
    return new CancellationToken();
  }

  // ─── Conversation forking ────────────────────────────────────────────────

  static forks(opts: ForkManagerOptions = {}): ForkManager {
    return new ForkManager(opts);
  }

  // ─── Event rendering ─────────────────────────────────────────────────────

  static renderer(format: "plain" | "rich" | "json" = "plain", opts: RendererOptions = {}) {
    if (format === "rich") return new RichRenderer(opts);
    if (format === "json") return new JsonRenderer();
    return new PlainRenderer(opts);
  }

  // ─── Git checkpoints + LLM-callable git tools ────────────────────────────

  static git(workspace: string): GitCheckpointer {
    return new GitCheckpointer(workspace);
  }

  static gitTools(workspace: string, opts: { allowShell?: boolean } = {}): HarnessTool[] {
    return gitTools(workspace, opts);
  }

  // ─── Hooks ───────────────────────────────────────────────────────────────

  static hooks(workspace?: string): HookRegistry {
    return new HookRegistry(workspace);
  }

  // ─── Artifacts ───────────────────────────────────────────────────────────

  static artifacts(path: string, opts: { maxInlineBytes?: number } = {}): ArtifactStore {
    return new ArtifactStore(path, opts);
  }

  // ─── Event subsystem ─────────────────────────────────────────────────────

  static dispatcher(): EventDispatcher {
    return new EventDispatcher();
  }

  static eventBus(opts: EventBusOptions = {}): EventBus {
    return new EventBus(opts);
  }

  static tape(opts: SessionTapeOptions = {}): SessionTape {
    return new SessionTape(opts);
  }

  // ─── Context compression ─────────────────────────────────────────────────

  static compressor(opts: ContextCompressorOptions = {}): ContextCompressor {
    return new ContextCompressor(opts);
  }

  static autoCompress(threshold = 100_000): number {
    return threshold;
  }

  // ─── Tasks ───────────────────────────────────────────────────────────────

  static tasks(opts: { maxTasks?: number } = {}): HarnessTool[] {
    return taskTools(new TaskRegistry(opts));
  }

  static taskLedger(opts: { maxTasks?: number } = {}): TaskLedger {
    return new TaskLedger(opts);
  }

  // ─── Slash commands ──────────────────────────────────────────────────────

  static commands(opts: { prefix?: string } = {}): CommandRegistry {
    return new CommandRegistry(opts.prefix ?? "/");
  }

  // ─── Tool policy ─────────────────────────────────────────────────────────

  static toolPolicy(opts: { default?: "retry" | "skip" | "ask" | "propagate" } = {}): ToolPolicy {
    return new ToolPolicy(opts);
  }

  // ─── Budget monitor ──────────────────────────────────────────────────────

  static budgetMonitor(maxTokens = 200_000): BudgetMonitor {
    return new BudgetMonitor(maxTokens);
  }

  // ─── REPL ────────────────────────────────────────────────────────────────

  static repl(
    agent: { ask?: (text: string) => Promise<string> },
    opts: {
      dispatcher?: EventDispatcher;
      hooks?: HookRegistry;
      compressor?: ContextCompressor;
      config?: ReplConfig;
    } = {},
  ): HarnessRepl {
    return new HarnessRepl(agent, opts);
  }

  // ─── Unified config ──────────────────────────────────────────────────────

  static config(opts: HarnessConfigOptions = {}): HarnessConfig {
    return new HarnessConfig(opts);
  }

  // ─── Polyglot code execution ─────────────────────────────────────────────

  /**
   * Build a polyglot `CodeExecutor` rooted at `workspace`. The returned
   * executor exposes `.tools()` (LLM-callable `run_code` + `which_languages`)
   * and `.run(language, source)` (programmatic).
   */
  static codeExecutor(workspace: string, opts: CodeExecutorOptions = {}): CodeExecutor {
    const sandbox = new SandboxPolicy({ workspace, allowShell: true });
    return new CodeExecutor(sandbox, opts);
  }

  /** Shorthand: `H.codeExecutor(...).tools()`. */
  static runCodeTools(workspace: string, opts: CodeExecutorOptions = {}): HarnessTool[] {
    return H.codeExecutor(workspace, opts).tools();
  }

  // ─── Agent self-management tools ─────────────────────────────────────────

  static todos(): TodoStore {
    return new TodoStore();
  }

  static planMode(): PlanMode {
    return new PlanMode();
  }

  static askUser(handler?: AskUserHandler): HarnessTool {
    return askUserTool(handler);
  }

  static worktrees(workspace: string): WorktreeManager {
    return new WorktreeManager(workspace);
  }

  // ─── Coding-agent preset ─────────────────────────────────────────────────

  /**
   * Build a fully-wired coding agent harness in one call.
   *
   * Returns a `CodingAgentBundle` with `tools` ready to plug into
   * `Agent.tools(...)` plus every primitive (sandbox, permissions, bus,
   * memory, executor, todos, …) exposed for inspection / overrides.
   */
  static codingAgent(workspace: string, opts: CodingAgentOptions = {}): CodingAgentBundle {
    return codingAgent(workspace, opts);
  }

  // ─── Stubs (not yet ported) ──────────────────────────────────────────────

  static notebook(_path?: string): never {
    throw new Error("H.notebook() is not yet ported to TypeScript");
  }

  static mcp(_servers: unknown[]): never {
    throw new Error("H.mcp() is not yet ported — waiting for @google/adk MCP wiring");
  }

  static mcpFromConfig(_path: string): never {
    throw new Error("H.mcpFromConfig() is not yet ported — waiting for @google/adk MCP wiring");
  }

  static manifold(_opts: unknown): never {
    throw new Error("H.manifold() is not yet ported — depends on SkillRegistry");
  }
}
